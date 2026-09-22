"""Fase 8: la caducidad cableada. El almacen, la revalidacion y la invalidacion selectiva."""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from actaira_motor.aplicabilidad.motor import Perfil
from actaira_motor.catalogo.cargador import cargar
from actaira_motor.evidencia.registro import Estado, Registro
from actaira_motor.vigilancia.almacen import Almacen
from actaira_motor.vigilancia.barrido import observar
from actaira_motor.vigilancia.reconciliar import reconciliar

FIX = Path("motor/tests/fixtures/clasificador-candidatos")
T0 = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)
PERFIL = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii")


@pytest.fixture(scope="module")
def cat():
    return cargar("catalogo")


def _barrer(cat, repo, ahora):
    return observar(cat, PERFIL, ahora.date(), repo, "catalogo/reglas", ahora)


def _reg(control="ACT-C-009", sujeto="sha256:aaa", cuando=T0, frescura=30, contenido=None):
    return Registro.nuevo("AIA-009", control, sujeto, cuando, contenido or {"r": "cumple"}, frescura)


# --- el almacen -------------------------------------------------------------

def test_el_almacen_solo_anade_y_revocar_no_borra(tmp_path):
    """Un expediente que se puede reescribir vale lo mismo que ninguno."""
    a = Almacen.abrir(tmp_path / "ev.jsonl")
    r = _reg()
    a.anadir([r], T0)
    a.revocar(r.id, "la clave del atestador se retiro", "Marta Iglesias", T0)
    assert len(a.registros()) == 1                 # la vieja sigue ahi
    assert r.id in a.revocadas()
    est, motivo = r.estado(T0, revocadas=a.revocadas())
    assert est is Estado.REVOCADA and "retiró" in motivo["es"] and "withdrawn" in motivo["en"]


def test_una_linea_ilegible_no_se_salta_en_silencio(tmp_path):
    ruta = tmp_path / "ev.jsonl"
    Almacen.abrir(ruta).anadir([_reg()], T0)
    with ruta.open("a", encoding="utf-8") as f:
        f.write("{esto no es json\n")
    with pytest.raises(ValueError, match="ilegible"):
        Almacen.abrir(ruta).registros()


def test_lo_mismo_otra_vez_se_revalida_no_se_duplica(tmp_path):
    """Si no, a los seis meses el tamano del almacen mide la frecuencia del cron."""
    a = Almacen.abrir(tmp_path / "ev.jsonl")
    assert a.anadir([_reg()], T0) == (1, 0)
    assert a.anadir([_reg(cuando=T0 + timedelta(days=1))], T0 + timedelta(days=1)) == (0, 1)
    assert len(a.registros()) == 1 and len(a.revalidaciones()) == 1


def test_el_gemelo_un_resultado_distinto_si_se_anade(tmp_path):
    """Si todo se tratara como revalidacion, un hallazgo nuevo no se guardaria."""
    a = Almacen.abrir(tmp_path / "ev.jsonl")
    a.anadir([_reg(contenido={"r": "cumple"})], T0)
    assert a.anadir([_reg(contenido={"r": "no_cumple"}, cuando=T0 + timedelta(days=1))],
                    T0 + timedelta(days=1)) == (1, 0)
    assert len(a.registros()) == 2


def test_la_revalidacion_mueve_el_reloj_de_la_frescura(tmp_path):
    a = Almacen.abrir(tmp_path / "ev.jsonl")
    r = _reg(frescura=30)
    a.anadir([r], T0)
    a.anadir([_reg(frescura=30, cuando=T0 + timedelta(days=25))], T0 + timedelta(days=25))
    est, _ = r.estado(T0 + timedelta(days=40), visto_de_nuevo=a.revalidaciones()[r.id])
    assert est is Estado.VALIDA


def test_el_gemelo_sin_revalidar_esa_misma_evidencia_caduca(tmp_path):
    """Si la revalidacion no fuera necesaria, la caducidad seria decorativa."""
    r = _reg(frescura=30)
    est, motivo = r.estado(T0 + timedelta(days=40))
    assert est is Estado.RANCIA and "30" in motivo["es"]


# --- la invalidacion selectiva, que es el foso ------------------------------

def test_un_cambio_supera_solo_lo_que_de_verdad_lo_lee(cat, tmp_path):
    """LA propiedad del producto, en un test.

    Tocar un README supera los controles que leen documentacion y NO supera
    los que solo leen codigo Python. La alternativa -- el digest del
    repositorio entero -- pintaria un muro rojo cada vez que alguien corrige
    una errata, y un muro rojo se aprende a ignorar en dos semanas.
    """
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    regs, sujetos, esperados, _ = _barrer(cat, repo, T0)
    alm.anadir(regs, T0)
    assert reconciliar(alm, sujetos, T0, esperados=esperados).a_json()["a_reobservar"] == ["ACT-C-050"]

    (repo / "datos" / "README.md").write_text(
        (repo / "datos" / "README.md").read_text(encoding="utf-8") + "\n<!-- una errata -->\n",
        encoding="utf-8")
    _regs2, sujetos2, esperados2, _ = _barrer(cat, repo, T0 + timedelta(hours=1))
    rec = reconciliar(alm, sujetos2, T0 + timedelta(hours=1), esperados=esperados2).a_json()
    por_estado = {v["control_id"]: v["estado"] for v in rec["veredictos"]}
    assert por_estado["ACT-C-010"] == "superada"      # el articulo 10 lee la ficha de datos
    assert por_estado["ACT-C-014"] == "valida"        # el 14 solo mira codigo
    assert por_estado["ACT-C-012"] == "valida"
    assert 0 < len(rec["a_reobservar"]) < len(rec["veredictos"])


def test_y_un_cambio_en_el_codigo_si_supera_lo_que_lo_mira(cat, tmp_path):
    """El gemelo por el otro lado: si nada se superara nunca, esto seria un temporizador."""
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    regs, sujetos, esperados, _ = _barrer(cat, repo, T0)
    alm.anadir(regs, T0)
    (repo / "app" / "revision.py").write_text(
        (repo / "app" / "revision.py").read_text(encoding="utf-8") + "\nX = 1\n", encoding="utf-8")
    _r, sujetos2, esperados2, _ = _barrer(cat, repo, T0 + timedelta(hours=1))
    rec = reconciliar(alm, sujetos2, T0 + timedelta(hours=1), esperados=esperados2).a_json()
    por_estado = {v["control_id"]: v["estado"] for v in rec["veredictos"]}
    assert por_estado["ACT-C-014"] == "superada"


# --- lo que nunca se miro ---------------------------------------------------

def test_un_control_esperado_sin_evidencia_aparece_y_no_se_calla(cat, tmp_path):
    """Un informe limpio por no haber mirado es indistinguible de uno limpio."""
    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    rec = reconciliar(alm, {}, T0, esperados={"ACT-C-009": "AIA-009"}).a_json()
    assert rec["recuento"] == {"sin_evidencia": 1}
    assert rec["a_reobservar"] == ["ACT-C-009"]


# --- la cuarta negativa -----------------------------------------------------

def test_la_vigilancia_dice_que_mirar_y_no_decide_nada(cat, tmp_path):
    """Nunca actuar sobre lo observado. Quien decide si eso bloquea un
    despliegue es la puerta del cliente, con su criterio escrito.

    Acotado a los veredictos, y no al documento entero, por quinta vez en este
    arbol: la primera version miraba el JSON completo y se acusaba a si misma,
    porque la nota que dice "NO decide si eso bloquea un despliegue" contiene
    la palabra "bloquea". Una puerta que tiene que perdonarse a si misma esta
    mirando de lado. Ya esta escrito como B-005 y aqui vuelve a pasar: la
    leccion no es afinar esta, es escribir las siguientes acotadas desde el
    principio.
    """
    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    rec = reconciliar(alm, {}, T0, esperados={"ACT-C-009": "AIA-009"}).a_json()
    for i in ("es", "en"):
        assert rec["nota_de_no_accion"][i]
    cuerpo = json.dumps({"veredictos": rec["veredictos"], "recuento": rec["recuento"],
                         "a_reobservar": rec["a_reobservar"]}, ensure_ascii=False).lower()
    for prohibido in ("bloquea", "aprobado", "aprueba", "conforme", "cumple", "%"):
        assert prohibido not in cuerpo, prohibido
    assert all(v["accion"] in ("nada", "reobservar", "corregir") for v in rec["veredictos"])


def test_el_ahorro_de_barridos_se_publica_con_su_lista(cat, tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    regs, sujetos, esperados, _ = _barrer(cat, repo, T0)
    alm.anadir(regs, T0)
    rec = reconciliar(alm, sujetos, T0, esperados=esperados).a_json()
    ah = rec["ahorro_de_barridos"]
    assert ah["controles_con_evidencia"] > ah["hay_que_volver_a_correr"]
    assert len(rec["a_reobservar"]) == ah["hay_que_volver_a_correr"]


def test_el_verbo_devuelve_tres_cuando_hay_trabajo_y_cero_cuando_no(cat, tmp_path):
    """Tres es 'hay trabajo', no 'esto ha reventado'. Una puerta de CI los trata distinto."""
    from actaira_motor.cli import main
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    alm = str(tmp_path / "ev.jsonl")
    base = ["vigilar", str(repo), "--alto-riesgo", "si", "--almacen", alm, "--json"]
    assert main(base + ["--ahora", T0.isoformat(), "--registrar"]) == 3     # nada observado aun
    # el articulo 50 nunca tendra evidencia aqui, asi que se mira el recuento
    salida = reconciliar(Almacen.abrir(alm), {}, T0).a_json()
    assert salida["recuento"]


# --- SARIF, que es como el hallazgo llega a quien puede arreglarlo ----------

def test_el_sarif_es_valido_y_cita_su_paquete_y_su_version(cat, tmp_path):
    from actaira_motor.formularios.plan import construir as construir_plan
    from actaira_motor.integraciones.sarif import exportar

    plan = construir_plan(cat, PERFIL, date(2027, 12, 2), str(FIX), "catalogo/reglas")
    s = exportar(plan)
    run = s["runs"][0]
    assert s["version"] == "2.1.0" and s["$schema"].endswith("sarif-2.1.0.json")
    assert run["tool"]["driver"]["name"] == "Actaira"
    assert run["results"], "el repositorio de ejemplo tiene hallazgos de sobra"
    ids = {r["ruleId"] for r in run["results"]}
    declaradas = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert ids == declaradas, "toda regla citada se declara, y ninguna de mas"
    for r in run["tool"]["driver"]["rules"]:
        assert "v" in r["help"]["markdown"] and r["properties"]["obligacion"].startswith("AIA-")
        assert r["defaultConfiguration"]["level"] in ("error", "warning", "note")


def test_el_sarif_no_inventa_una_linea_que_no_sabe(cat):
    """Apuntar a la linea 1 para que quede bonito es precision falsa, que es
    justo lo que esta casa no emite."""
    from actaira_motor.formularios.plan import construir as construir_plan
    from actaira_motor.integraciones.sarif import exportar

    plan = construir_plan(cat, PERFIL, date(2027, 12, 2), str(FIX), "catalogo/reglas")
    run = exportar(plan)["runs"][0]
    for r in run["results"]:
        for loc in r.get("locations", []):
            assert "region" not in loc["physicalLocation"]
    sin_fichero = [r for r in run["results"] if "locations" not in r]
    assert sin_fichero, "los hallazgos sobre el repositorio entero no se cuelgan de un fichero"
    for r in sin_fichero:
        assert r["message"]["text"].startswith("Sobre el repositorio entero")


def _flujo() -> str:
    from pathlib import Path as P
    return P("integraciones/github/actaira.yml").read_text(encoding="utf-8")


def test_el_flujo_de_integracion_continua_no_decide_por_el_cliente():
    """Ningun paso puede parar nada mientras el cliente no lo pida.

    La primera version ofrecia la puerta COMENTADA, y comentarla tenia un
    coste escondido: encenderla obligaba a editar la plantilla, con lo que la
    siguiente actualizacion del fichero se la llevaba por delante. Ahora la
    puerta esta escrita y colgada de una variable del repositorio, que es una
    decision que se toma en los ajustes, se ve en la pantalla y sobrevive a que
    la plantilla cambie. El defecto sigue siendo el mismo: no para nada.
    """
    y = _flujo()
    assert "upload-sarif" in y and "actaira vigilar" in y
    for i, l in enumerate(y.splitlines()):
        if l.strip() != "exit 1":
            continue
        # Un `exit 1` solo vale si el paso que lo contiene esta condicionado a
        # que el cliente lo haya pedido.
        anteriores = "\n".join(y.splitlines()[max(0, i - 8):i])
        assert "vars.ACTAIRA_BLOQUEA == 'si'" in anteriores, \
            f"la linea {i + 1} para el despliegue sin que el cliente lo haya pedido"


def test_la_puerta_distingue_un_hallazgo_de_una_pregunta_sin_contestar():
    """1 es un hallazgo y 3 es el cuestionario a medias, y no son lo mismo.

    Colgar la puerta de «el paso fallo» las funde: el despliegue se para porque
    alguien no ha contestado catorce preguntas de gobierno, y a la tercera vez
    la organizacion apaga la puerta. Asi se pierden las puertas de verdad.
    """
    y = _flujo()
    assert "steps.plan.outputs.codigo == '1'" in y
    assert "steps.plan.outcome == 'failure'" not in y


def test_el_flujo_es_yaml_de_verdad_y_no_solo_un_texto_que_lo_parece():
    """La plantilla se comprueba como dato, no como cadena.

    Buscar `contents: write` con un `in` acierta mientras nadie escriba
    `contents:   write`, y ese es exactamente el tipo de comprobacion que mira
    de lado: parece que valida la estructura y valida la tipografia.
    """
    yaml = pytest.importorskip("yaml")
    d = yaml.safe_load(_flujo())
    assert d["permissions"] == {}, "nada por defecto"
    tareas = d["jobs"]
    assert set(tareas) == {"comprobar", "registrar"}
    assert tareas["comprobar"]["permissions"] == {"contents": "read",
                                                  "security-events": "write"}
    assert tareas["registrar"]["permissions"] == {"contents": "write"}
    assert tareas["registrar"]["needs"] == "comprobar"
    assert "pull_request" in tareas["registrar"]["if"]
    assert d["concurrency"]["cancel-in-progress"] is False, \
        "una cadena de sellos no admite dos escritores a la vez"


def test_pero_la_puerta_existe_y_se_puede_encender():
    """El gemelo. «No decide por el cliente» se cumple tambien no teniendo
    puerta ninguna, y entonces el producto no sirve para lo que se compra."""
    y = _flujo()
    assert "vars.ACTAIRA_BLOQUEA == 'si'" in y, "hay una puerta y se enciende sin tocar el fichero"
    assert "exit 1" in y
    assert "ACTAIRA_BLOQUEA=si" in y, "y la plantilla dice como encenderla"


def test_el_flujo_no_pide_mas_permisos_de_los_que_gasta():
    """`contents: read` con un `git push` debajo: no fallaba en la revision,
    fallaba el dia que un cliente lo copiaba. Y al arreglarlo, la tarea que
    mira no puede heredar el permiso de escribir de la tarea que escribe."""
    y = _flujo()
    assert "permissions: {}" in y, "nada por defecto; cada tarea pide lo suyo"
    assert y.count("contents: write") == 1, "solo la tarea que empuja escribe"
    # la tarea que empuja es la unica que hace git push
    trozo = y[y.index("  registrar:"):]
    assert "git push" in trozo
    assert "git push" not in y[:y.index("  registrar:")], \
        "la tarea que solo mira no empuja nada"


def test_el_flujo_clava_la_version_de_lo_que_instala():
    """`pip install actaira-motor` a secas instala lo que haya publicado hoy."""
    y = _flujo()
    assert "actaira-motor==" in y
    assert "pip install actaira-motor\n" not in y


def test_y_dice_en_voz_alta_que_las_acciones_no_vienen_ancladas():
    """No se publica un digest inventado, y tampoco se calla que falta.

    Una plantilla que usa `@v4` sin decirlo deja al cliente creyendo que ancla
    algo. La plantilla lo dice, y trae el mandato que lo resuelve.
    """
    from pathlib import Path as P
    y = _flujo()
    assert "ANCLA LAS ACCIONES" in y and "anclar.sh" in y
    assert P("integraciones/github/anclar.sh").is_file()


# --- la pasada adversarial de la fase 8 -------------------------------------

def test_un_fichero_nuevo_que_no_casa_no_supera_una_regla_de_fichero(cat, tmp_path):
    """D-14. El sujeto de una regla de `fichero` son los nombres QUE CASAN.

    La primera version usaba la lista entera del repositorio, asi que anadir
    un apunte superaba la evidencia de que existe un directorio de
    evaluaciones. Sobreinvalidar produce el mismo muro rojo que el digest del
    repositorio entero, solo que mas dificil de explicar.
    """
    from actaira_motor.controles.motor import Arbol, Paquete, sujeto_de
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    pk = Paquete.cargar("catalogo/reglas/art15.json")
    antes, _ = sujeto_de(Arbol.leer(repo), pk)
    (repo / "NOTAS.txt").write_text("nada que ver con las evaluaciones\n", encoding="utf-8")
    assert sujeto_de(Arbol.leer(repo), pk)[0] == antes


def test_y_el_gemelo_un_fichero_que_si_casa_lo_supera(cat, tmp_path):
    """Si nunca cambiara, la regla de fichero no vigilaria nada."""
    from actaira_motor.controles.motor import Arbol, Paquete, sujeto_de
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    pk = Paquete.cargar("catalogo/reglas/art15.json")
    antes, _ = sujeto_de(Arbol.leer(repo), pk)
    (repo / "evals" / "test_robustez.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    assert sujeto_de(Arbol.leer(repo), pk)[0] != antes


def test_subir_la_version_del_paquete_supera_su_evidencia(cat, tmp_path):
    """Reglas nuevas hacen otra pregunta, asi que la respuesta vieja no vale.
    Es deliberado y es la unica invalidacion que dispara Actaira y no el cliente."""
    from actaira_motor.controles.motor import Arbol, Paquete, sujeto_de
    from dataclasses import replace as _replace
    arbol = Arbol.leer(FIX)
    pk = Paquete.cargar("catalogo/reglas/art14.json")
    assert sujeto_de(arbol, pk)[0] != sujeto_de(arbol, _replace(pk, version="2.0.0"))[0]


def test_las_fechas_se_comparan_como_fechas_y_no_como_texto():
    """D-15. El caso en el que el orden por texto y el orden real discrepan.

    Una revalidacion escrita como `2027-12-02T08:00:00-02:00` ocurre a las
    10:00 UTC, DESPUES de una observacion de las 09:00 UTC. Ordenadas como
    cadenas, la revalidacion parece anterior, `max()` devuelve la observacion,
    y la evidencia caduca una hora antes de lo que debe. Lo que escribe esta
    casa va normalizado a UTC, pero un almacen puede traer lineas de otra
    herramienta, y el fallo seria silencioso.
    """
    r = Registro.nuevo("AIA-009", "ACT-C-009", "sha256:a",
                       datetime(2027, 12, 2, 9, 0, tzinfo=timezone.utc), {}, 1)
    reval = datetime(2027, 12, 2, 8, 0, tzinfo=timezone(timedelta(hours=-2))).isoformat()
    assert reval < r.observado_en, "el orden como texto es el contrario: ese es el defecto"

    ahora = datetime(2027, 12, 3, 9, 30, tzinfo=timezone.utc)
    assert r.estado(ahora)[0] is Estado.RANCIA                      # sin revalidar, caducada
    assert r.estado(ahora, visto_de_nuevo=reval)[0] is Estado.VALIDA  # con ella, todavia no


def test_evidencia_de_algo_que_ya_no_ata_se_dice_y_no_cuenta(tmp_path):
    """D-16. Sostener el expediente de hoy con una observacion sobre otra cosa."""
    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    alm.anadir([_reg(control="ACT-C-009")], T0)
    rec = reconciliar(alm, {}, T0, esperados={"ACT-C-072": "AIA-072"}).a_json()
    por = {v["control_id"]: v["estado"] for v in rec["veredictos"]}
    assert por["ACT-C-009"] == "fuera_de_alcance"
    assert por["ACT-C-072"] == "sin_evidencia"
    assert rec["a_reobservar"] == ["ACT-C-072"]


# --- el modo que corre el vencimiento de la plataforma ----------------------

def test_solo_almacen_dice_que_caduco_sin_tocar_el_repositorio(cat, tmp_path):
    """Para saber QUE CADUCO no hace falta el codigo del cliente: hace falta su
    almacen y un reloj. Pedirle el repositorio a quien no ha empujado nada
    obligaria ademas a tener una copia fresca de su codigo permanentemente."""
    from actaira_motor.cli import main
    alm = tmp_path / "ev.jsonl"
    regs, _s, _e, _ = _barrer(cat, FIX, T0)
    Almacen.abrir(alm).anadir(regs, T0)

    # sin repositorio y sin caducar: nada que hacer
    assert main(["vigilar", "--solo-almacen", "--almacen", str(alm),
                 "--ahora", (T0 + timedelta(days=1)).isoformat(), "--json"]) == 0
    # sin repositorio y caducado: hay trabajo
    assert main(["vigilar", "--solo-almacen", "--almacen", str(alm),
                 "--ahora", (T0 + timedelta(days=45)).isoformat(), "--json"]) == 3


def test_sin_esperados_no_es_lo_mismo_que_esperar_nada(tmp_path):
    """El defecto que casi se cuela: `esperados={}` significa «se miro y no se
    esperaba nada», y con esa lectura TODA la evidencia del almacen salia
    `fuera_de_alcance`. `None` significa «en esta pasada no se ha mirado que se
    espera», que es la verdad cuando no hay repositorio."""
    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    alm.anadir([_reg(control="ACT-C-009")], T0)
    vacio = reconciliar(alm, {}, T0, esperados={}).a_json()
    ninguno = reconciliar(alm, {}, T0, esperados=None).a_json()
    assert vacio["recuento"] == {"fuera_de_alcance": 1}
    assert ninguno["recuento"] == {"valida": 1}


def test_sin_repositorio_nada_sale_superado(cat, tmp_path):
    """El gemelo. Sin sujetos de AHORA no se puede saber si algo cambio, y
    marcarlo como superado seria afirmar un cambio que nadie observo."""
    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    regs, _s, _e, _ = _barrer(cat, FIX, T0)
    alm.anadir(regs, T0)
    rec = reconciliar(alm, {}, T0 + timedelta(days=1), esperados=None).a_json()
    assert "superada" not in rec["recuento"]
