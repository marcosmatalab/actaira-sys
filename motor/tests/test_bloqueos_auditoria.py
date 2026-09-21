"""Los bloqueos que encontro la auditoria externa, cada uno con su gemelo.

Una auditoria de seguridad ajena reprodujo nueve fallos criticos sobre el arbol
de la fase 12. Este fichero no existe para dejar constancia de que se
arreglaron: existe para que NINGUNO pueda volver, y por eso cada arreglo trae
su pareja -- regla 9 del constitucional de este repositorio. Una prueba que
solo comprueba que el caso malo ya no pasa se satisface tambien borrando la
funcionalidad entera, que es el modo de fallo que la regla persigue.

  B1  un PNG con basura llamada `caBX` terminaba el control en `cumple`
  B2  la cadena de publicacion declarada se aceptaba y se ignoraba
  B3  un enlace simbolico leia un fichero de fuera del repositorio
"""
from pathlib import Path

import pytest
from conftest import CATALOGO

from actaira_motor.controles.art50 import Entrada, correr
from actaira_motor.controles.marcado import read_facts, write_marking
from actaira_motor.controles.modelo import Resultado
from actaira_motor.controles.motor import Arbol

RAIZ = Path(__file__).resolve().parents[2]
REGLAS = RAIZ / "catalogo" / "reglas" / "art50.json"
FIX = Path(__file__).parent / "fixtures"


def _png(ruta: Path) -> Path:
    from PIL import Image
    Image.new("RGB", (24, 24), (7, 7, 7)).save(ruta)
    return ruta


def _con_cabx(ruta: Path) -> Path:
    """Le pega al PNG un trozo que dice llamarse C2PA y no lo es.

    Es literalmente lo que hizo el auditor: cuatro letras y relleno. No hay
    manifiesto, no hay firma, no hay cadena de confianza. Si el control se
    conforma con esto, se conforma con cualquier cosa.
    """
    import struct, zlib
    datos = ruta.read_bytes()
    corte = datos.rindex(b"IEND") - 4
    basura = b"no soy un manifiesto, soy relleno"
    trozo = (struct.pack(">I", len(basura)) + b"caBX" + basura
             + struct.pack(">I", zlib.crc32(b"caBX" + basura) & 0xFFFFFFFF))
    ruta.write_bytes(datos[:corte] + trozo + datos[corte:])
    return ruta


# --------------------------------------------------------------------------
# B1. El peor de los nueve: un falso «cumple» sobre basura.
# --------------------------------------------------------------------------

def test_b1_un_trozo_que_dice_llamarse_c2pa_no_es_marcado_observado(tmp_path):
    art = _con_cabx(_png(tmp_path / "salida.png"))
    assert read_facts(art).c2pa == "present_unverified"
    assert not read_facts(art).has_marking

    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,)), REGLAS)
    # Desde la fase 14 esto se comprueba en la capa donde vive: la SUFICIENCIA.
    # Antes se miraba el enumerado, y el enumerado fundia «no se puede decidir»
    # con «no le tocaba mirar» y con «el analizador se rompio».
    assert r.suficiencia.estado.value == "indeterminada", "presencia no es validez"
    assert "C2PA" in r.motivo_indeterminado["es"]
    assert "c2patool" in r.suficiencia.falta[0].que_hacer["es"], \
        "una suficiencia indeterminada dice como resolverse"
    assert not any(h.regla_id == "ACT-50-MARCA-AUSENTE" for h in r.hallazgos), \
        "tampoco es un hallazgo: no se sabe, y se dice"


def test_b1_gemelo_sin_nada_encima_si_es_hallazgo(tmp_path):
    """La mitad que impide arreglar B1 devolviendo INDETERMINADO siempre."""
    art = _png(tmp_path / "salida.png")
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,)), REGLAS)
    assert r.resultado is Resultado.CON_HALLAZGOS
    assert any(h.regla_id == "ACT-50-MARCA-AUSENTE" for h in r.hallazgos)


def test_b1_gemelo_el_marcado_de_verdad_sigue_contando(tmp_path):
    """Y la que impide arreglarlo negandose a reconocer nada."""
    art = _png(tmp_path / "salida.png")
    write_marking(art)
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,)), REGLAS)
    assert not any(h.regla_id == "ACT-50-MARCA-AUSENTE" for h in r.hallazgos)
    # El marcado leido byte a byte SI cuenta: la observacion esta entre lo que
    # la suficiencia se apoya. Que la suficiencia no sea «suficiente» es otra
    # cosa: este fixture ademas genera texto, y eso queda por contestar.
    assert r.observacion.id in r.suficiencia.se_apoya_en
    assert all("texto" in f.que["es"] or "asistente" in f.que["es"]
               for f in r.suficiencia.falta), [f.que["es"][:50] for f in r.suficiencia.falta]


def test_b1_ningun_estado_del_motor_afirma_cumplimiento():
    """La raiz del fallo era el nombre: un estado que se llamaba `cumple`.

    Mientras exista un valor que se lea como «cumple», alguien lo pondra en un
    informe delante de un auditor. Los cinco estados dicen lo que se observo, y
    ninguno dice lo que eso significa en derecho.
    """
    for estado in Resultado:
        assert not estado.afirma_cumplimiento
        assert "cumpl" not in estado.value


# --------------------------------------------------------------------------
# B2. Se aceptaba un `pipeline` y no se aplicaba: el parametro decorativo.
# --------------------------------------------------------------------------

def test_b2_la_cadena_declarada_se_aplica_de_verdad(tmp_path):
    pytest.importorskip("PIL")
    art = _png(tmp_path / "salida.png")
    write_marking(art)
    sin = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,)), REGLAS)
    con = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,),
                         pipeline=("a_jpeg",)), REGLAS)
    assert sin.a_json() != con.a_json(), \
        "si declarar una cadena no cambia nada, el parametro era decorativo"
    assert sin.ejecucion.sujeto.digest != con.ejecucion.sujeto.digest, \
        "la cadena declarada forma parte del sujeto: si no, cambiarla no invalidaria nada"
    assert con.resultado is Resultado.CON_HALLAZGOS

    # QUE hallazgo, y no solo que haya uno. Esta linea decia
    # `ACT-50-PIPE-BORRA` para `a_jpeg`, y era correcto para lo que el motor
    # hacia entonces y no para lo que pasa de verdad.
    #
    # La simulacion aplicaba cada paso con `Image.open(...).save(...)` de
    # Pillow, que descarta los metadatos SIEMPRE. Con eso la respuesta no
    # dependia de la cadena: cualquier paso, incluido rotar noventa grados,
    # salia tan destructivo como quitar los metadatos a proposito. Una medicion
    # cuya respuesta no cambia con la entrada no mide la entrada.
    #
    # Ahora se miden las dos hipotesis -- herramientas que arrastran el XMP y
    # herramientas que no -- y salen dos hallazgos distintos, que es la
    # diferencia entre «tu cadena lo destruye» y «tu cadena lo conserva SI tus
    # herramientas lo conservan, y este motor no puede saber si lo hacen».
    assert any(h.regla_id == "ACT-50-PIPE-FRAGIL" for h in con.hallazgos), \
        "convertir a JPEG conserva el marcado con una herramienta que arrastre el XMP"

    # Y la otra rama: un paso cuyo PROPOSITO es borrar si destruye, siempre.
    borra = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,),
                           pipeline=("quitar_metadatos",)), REGLAS)
    assert any(h.regla_id == "ACT-50-PIPE-BORRA" for h in borra.hallazgos), \
        "quitar los metadatos a proposito tiene que salir como destruccion, no como fragilidad"
    assert con.suficiencia is None, "con hallazgos, la suficiencia no anade nada"
    assert any("a_jpeg" in h.localizacion for h in con.hallazgos), \
        "el hallazgo nombra el paso que borro el marcado"


def test_b2_gemelo_una_cadena_que_no_borra_nada_no_inventa_hallazgo(tmp_path):
    """La pareja: copiar el fichero no puede quitarle el marcado."""
    pytest.importorskip("PIL")
    art = _png(tmp_path / "salida.png")
    write_marking(art)
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,),
                       pipeline=()), REGLAS)
    assert not any(h.regla_id == "ACT-50-PIPE-BORRA" for h in r.hallazgos)
    assert r.observacion.id in r.suficiencia.se_apoya_en


def test_b2_un_paso_desconocido_no_se_salta_en_silencio(tmp_path):
    pytest.importorskip("PIL")
    art = _png(tmp_path / "salida.png")
    write_marking(art)
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,),
                       pipeline=("pasar_por_instagram",)), REGLAS)
    assert r.suficiencia.estado.value == "indeterminada"
    assert "pasar_por_instagram" in r.motivo_indeterminado["es"]
    assert "pasar_por_instagram" in r.motivo_indeterminado["en"]
    assert "pasar_por_instagram" in r.suficiencia.falta[0].que["en"]


# --------------------------------------------------------------------------
# B3. El enlace simbolico que salia de la raiz.
# --------------------------------------------------------------------------

def test_b3_un_enlace_que_sale_de_la_raiz_no_se_lee_y_se_declara(tmp_path):
    fuera = tmp_path / "fuera"; fuera.mkdir()
    (fuera / "secreto.md").write_text("AWS_SECRET_ACCESS_KEY=no-deberia-leerse\n", encoding="utf-8")
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "propio.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "enlace.md").symlink_to(fuera / "secreto.md")

    a = Arbol.leer(repo)
    assert "enlace.md" not in a.ficheros
    assert all("AWS_SECRET" not in t for t in a.texto.values())
    assert any(n == "enlace.md" for n, _ in a.ilegibles), \
        "no se lee, pero tampoco se calla: aparece en ilegibles con su motivo"


def test_b3_gemelo_un_enlace_que_apunta_dentro_si_se_lee(tmp_path):
    """La pareja que impide arreglar B3 dejando de seguir enlaces."""
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "propio.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "alias.py").symlink_to(repo / "propio.py")

    a = Arbol.leer(repo)
    assert "alias.py" in a.ficheros
    assert not a.ilegibles


# --------------------------------------------------------------------------
# B4. El almacen se editaba a mano y lo leia como si nada.
#
# El auditor abrio el `.jsonl`, cambio un veredicto y una frescura, y el motor
# devolvio la version editada sin una palabra. «Solo se anade» era una promesa
# sobre como escribe esta casa, no un hecho sobre un fichero de texto que esta
# en el disco del cliente.
# --------------------------------------------------------------------------
import json as _json
from datetime import datetime, timezone

from actaira_motor.evidencia.registro import Estado, Registro
from actaira_motor.vigilancia.almacen import Almacen, AlmacenAlterado

T0 = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)


def _reg(contenido=None, frescura=30):
    return Registro.nuevo("AIA-009", "ACT-C-009", "sha256:aaa", T0,
                          contenido or {"resultado": "con_hallazgos"}, frescura)


def _lineas(ruta: Path) -> list[dict]:
    return [_json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def _escribir(ruta: Path, lineas: list[dict]) -> None:
    ruta.write_text("".join(_json.dumps(d, ensure_ascii=False, sort_keys=True) + "\n"
                            for d in lineas), encoding="utf-8")


def test_b4_editar_un_veredicto_a_mano_se_ve(tmp_path):
    ruta = tmp_path / "ev.jsonl"
    Almacen.abrir(ruta).anadir([_reg()], T0)

    ls = _lineas(ruta)
    ls[0]["registro"]["contenido"]["resultado"] = "sin_hallazgos"
    _escribir(ruta, ls)

    with pytest.raises(AlmacenAlterado, match="no coincide con su sello"):
        Almacen.abrir(ruta).registros()


def test_b4_editar_la_frescura_tambien_se_ve(tmp_path):
    """El caso que el identificador NO cubre, y por eso hace falta el sello.

    `frescura_dias` no entra en el resumen del registro -- es politica, no
    observacion -- asi que cambiarlo de 30 a 3000 dejaba el identificador
    cuadrando perfectamente mientras la evidencia pasaba a no caducar nunca.
    Recalcular el identificador no lo habria detectado: lo detecta el sello de
    la linea, que cubre la linea entera.
    """
    ruta = tmp_path / "ev.jsonl"
    r = _reg(frescura=30)
    Almacen.abrir(ruta).anadir([r], T0)

    ls = _lineas(ruta)
    ls[0]["registro"]["frescura_dias"] = 3000
    assert ls[0]["registro"]["id"] == r.id, "el identificador sigue cuadrando: por eso no basta"
    _escribir(ruta, ls)

    with pytest.raises(AlmacenAlterado, match="no coincide con su sello"):
        Almacen.abrir(ruta).registros()


def test_b4_quitar_una_linea_se_ve(tmp_path):
    ruta = tmp_path / "ev.jsonl"
    alm = Almacen.abrir(ruta)
    alm.anadir([_reg({"a": 1})], T0)
    alm.anadir([_reg({"b": 2})], T0)
    alm.anadir([_reg({"c": 3})], T0)

    ls = _lineas(ruta)
    _escribir(ruta, [ls[0], ls[2]])
    roturas = Almacen.abrir(ruta).verificar_cadena()
    assert roturas and "orden" in roturas[0]


def test_b4_cambiarlas_de_orden_se_ve(tmp_path):
    ruta = tmp_path / "ev.jsonl"
    alm = Almacen.abrir(ruta)
    alm.anadir([_reg({"a": 1})], T0)
    alm.anadir([_reg({"b": 2})], T0)

    ls = _lineas(ruta)
    _escribir(ruta, [ls[1], ls[0]])
    assert Almacen.abrir(ruta).verificar_cadena()


def test_b4_reescribirlo_entero_no_cuela_por_el_identificador(tmp_path):
    """Quien reescribe el fichero puede recalcular la cadena. No el resumen.

    Es la segunda capa, y comprueba otra propiedad: la cadena dice que la LINEA
    es la que se escribio, el identificador dice que el REGISTRO resume lo que
    afirma resumir. Las dos usan la misma definicion de cuerpo -- regla 10 --
    asi que no pueden discrepar entre si, solo con la realidad.
    """
    ruta = tmp_path / "ev.jsonl"
    Almacen.abrir(ruta).anadir([_reg()], T0)

    ls = _lineas(ruta)
    ls[0]["registro"]["contenido"]["resultado"] = "sin_hallazgos"
    # el atacante rehace la cadena entera, que es lo que puede hacer de verdad
    cuerpo = {k: v for k, v in ls[0].items() if k != "sello"}
    from actaira_motor.evidencia.registro import digest
    ls[0]["sello"] = digest(cuerpo)
    _escribir(ruta, ls)

    with pytest.raises(AlmacenAlterado, match="editado despues de observarse"):
        Almacen.abrir(ruta).registros()


def test_b4_gemelo_un_almacen_intacto_se_lee_entero(tmp_path):
    """La mitad que impide arreglar B4 negandose a leer nada."""
    ruta = tmp_path / "ev.jsonl"
    alm = Almacen.abrir(ruta)
    alm.anadir([_reg({"a": 1})], T0)
    alm.anadir([_reg({"b": 2})], T0)
    alm.revocar(_reg({"a": 1}).id, "la clave se retiro", "Marta Iglesias", T0)

    alm2 = Almacen.abrir(ruta)
    assert alm2.verificar_cadena() == []
    assert len(alm2.registros()) == 2
    assert len(alm2.revocadas()) == 1


def test_b4_gemelo_la_cadena_sobrevive_a_seguir_anadiendo(tmp_path):
    """Y la que impide arreglarlo rompiendo la escritura incremental."""
    ruta = tmp_path / "ev.jsonl"
    cabezas = []
    for i in range(5):
        Almacen.abrir(ruta).anadir([_reg({"i": i})], T0)
        alm = Almacen.abrir(ruta)
        assert alm.verificar_cadena() == []
        cabezas.append(alm.cabeza())
    assert len(set(cabezas)) == 5, "cada linea mueve la cabeza: si no, no ancla nada"


def test_b4_una_respuesta_no_admisible_no_vuelve_valida_del_almacen(tmp_path):
    """Lo que el auditor no vio, y es de la misma familia.

    `a_json` no escribia `estado_declarado`, asi que una respuesta que el motor
    habia JUZGADO no admisible se guardaba y volvia a leerse como evidencia
    valida. El motor decidia bien y su propio almacen borraba la decision.
    """
    ruta = tmp_path / "ev.jsonl"
    malo = Registro.nuevo("AIA-009", "ACT-C-009", "sha256:bbb", T0, {"valor": "sin justificar"})
    malo = type(malo)(**{**malo.__dict__, "estado_declarado": Estado.NO_FIABLE,
                         "motivo": "la respuesta no trae justificacion"})
    Almacen.abrir(ruta).anadir([malo], T0)

    vuelto = Almacen.abrir(ruta).registros()[0]
    assert vuelto.estado_declarado is Estado.NO_FIABLE
    assert vuelto.motivo == "la respuesta no trae justificacion"
    assert vuelto.estado(T0)[0] is Estado.NO_FIABLE


def test_b4_un_almacen_de_la_version_anterior_no_se_acepta_en_silencio(tmp_path):
    """Sin cadena no se puede afirmar que no fue alterado, y eso se dice."""
    ruta = tmp_path / "ev.jsonl"
    Almacen.abrir(ruta).anadir([_reg()], T0)
    ls = _lineas(ruta)
    for campo in ("n", "previo", "sello"):
        ls[0].pop(campo)
    _escribir(ruta, ls)

    with pytest.raises(AlmacenAlterado, match="version anterior"):
        Almacen.abrir(ruta).registros()


# --------------------------------------------------------------------------
# B5 a B8. La linea de mandatos: lo que el producto contesta a un `echo $?`.
#
# Los cuatro son el mismo fallo con cuatro caras: el verbo hace lo correcto por
# dentro y lo cuenta mal por fuera. En una integracion continua eso no es un
# detalle de presentacion, es la diferencia entre una puerta y un adorno.
# --------------------------------------------------------------------------
import os
import subprocess
import sys

ENTORNO = {**os.environ, "PYTHONPATH": str(RAIZ / "motor" / "src"),
           "PYTHONIOENCODING": "utf-8"}
FIXCLA = RAIZ / "motor" / "tests" / "fixtures" / "clasificador-candidatos"


def _actaira(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "actaira_motor.cli", *args],
                          cwd=RAIZ, env=ENTORNO, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _veredictos(salida: str) -> dict:
    return _json.loads(salida)


def test_b5_pedir_un_rol_no_anade_el_de_proveedor(tmp_path):
    """`action="append"` con defecto no sustituye: amplia.

    Y aqui eso no es un parametro mal leido: es atribuirle a una empresa un
    papel juridico que no dijo tener, con las obligaciones que lo acompanan.
    """
    r = _actaira("aplicabilidad", "--rol", "responsable_despliegue", "--json")
    assert r.returncode == 0, r.stderr
    d = _veredictos(r.stdout)
    solo = _actaira("aplicabilidad", "--rol", "proveedor", "--json")
    assert d["recuento"] != _veredictos(solo.stdout)["recuento"], \
        "pedir responsable_despliegue devolvia el recuento del proveedor"


def test_b5_gemelo_sin_pedir_ninguno_se_asume_proveedor():
    """La mitad que impide arreglar B5 quitando el defecto entero."""
    a = _veredictos(_actaira("aplicabilidad", "--json").stdout)["recuento"]
    b = _veredictos(_actaira("aplicabilidad", "--rol", "proveedor", "--json").stdout)["recuento"]
    assert a == b


def test_b5_y_se_pueden_pedir_dos_roles_a_la_vez():
    """Y la que impide arreglarlo aceptando solo uno."""
    uno = _veredictos(_actaira("aplicabilidad", "--rol", "proveedor", "--json").stdout)
    dos = _veredictos(_actaira("aplicabilidad", "--rol", "proveedor",
                               "--rol", "responsable_despliegue", "--json").stdout)
    assert dos["recuento"]["ata"] >= uno["recuento"]["ata"]


# El perfil se resuelve a proposito: con todo sin contestar, casi ningun
# paquete llega a correr y el plan sale 3 por falta de datos, que es correcto y
# no es lo que estas dos pruebas miran.
PERFIL_CLI = ("--alto-riesgo", "si", "--via-anexo", "anexo_iii", "--fecha", "2027-12-15")


def test_b8_el_plan_con_hallazgos_no_sale_con_cero():
    r = _actaira("plan", str(FIXCLA), *PERFIL_CLI)
    assert r.returncode == 1, f"salio {r.returncode} con hallazgos delante:\n{r.stdout[-500:]}"


def test_b8_y_el_formato_de_salida_no_cambia_el_veredicto():
    """El `return 0` vivia DENTRO de la rama que imprime JSON.

    Un formato de impresion que cambia un codigo de salida es el fallo de
    diseno que convierte `--json` en una manera de saltarse la puerta sin
    querer, en el momento en que alguien encadena el plan con `jq`.
    """
    sin = _actaira("plan", str(FIXCLA), *PERFIL_CLI)
    con = _actaira("plan", str(FIXCLA), *PERFIL_CLI, "--json")
    assert sin.returncode == con.returncode == 1


def test_b8_gemelo_un_repositorio_sin_hallazgos_no_sale_con_uno(tmp_path):
    """La pareja: si el arreglo fuera «devuelve 1 siempre», esto lo caza."""
    (tmp_path / "vacio.txt").write_text("nada\n", encoding="utf-8")
    r = _actaira("plan", str(tmp_path), "--json")
    assert r.returncode in (0, 3), f"salio {r.returncode}"
    plan = _veredictos(r.stdout)
    assert not any(l["hallazgos"] for l in plan["lineas"])


def test_b6_verificar_sin_clave_esperada_dice_que_no_establece_identidad(tmp_path):
    sello = tmp_path / "s.json"
    r = _actaira("sellar", str(FIXCLA), "--salida", str(sello))
    assert r.returncode == 0, r.stderr
    v = _actaira("verificar", str(sello))
    assert "identidad" in v.stdout, v.stdout


def test_b6_y_ahora_hay_por_donde_pasarla(tmp_path):
    """El defecto no era el aviso: era que no habia manera de resolverlo.

    La separacion integridad/identidad estaba bien escrita en la funcion y no
    tenia salida desde la linea de mandatos, asi que TODO sello firmado salia
    con el mismo aviso y el aviso dejaba de significar nada.
    """
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    k = Ed25519PrivateKey.generate()
    pem = tmp_path / "k.pem"
    pem.write_bytes(k.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()))
    publica = k.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw).hex()

    sello = tmp_path / "s.json"
    assert _actaira("sellar", str(FIXCLA), "--salida", str(sello),
                    "--clave", str(pem)).returncode == 0

    buena = _actaira("verificar", str(sello), "--clave-esperada", publica)
    assert buena.returncode == 0, buena.stdout
    assert "VERIFICA" in buena.stdout and "NO VERIFICA" not in buena.stdout

    otra = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw).hex()
    mala = _actaira("verificar", str(sello), "--clave-esperada", otra)
    assert mala.returncode == 1, mala.stdout
    assert "no es la esperada" in mala.stdout


def test_b7_una_declaracion_emitida_se_puede_volver_a_importar(tmp_path):
    """El circuito se cerraba con cero respuestas contestadas, EN SILENCIO.

    `contestar` escribe `{sello, registros}` y el lector solo miraba
    `respuestas`, asi que volver al cuestionario al mes siguiente con la
    declaracion en la mano mostraba el formulario entero en blanco.
    """
    fuente = RAIZ / "ejemplos" / "respuestas-clasificador.json"
    decl = tmp_path / "declaracion.json"
    assert _actaira("contestar", str(fuente), "--salida", str(decl)).returncode in (0, 1)

    a_mano = _veredictos(_actaira("preguntar", "--respuestas", str(fuente), "--json").stdout)
    de_vuelta = _veredictos(_actaira("preguntar", "--respuestas", str(decl), "--json").stdout)
    assert de_vuelta["recuento"]["contestada"] == a_mano["recuento"]["contestada"] > 0
    assert de_vuelta["recuento"] == a_mano["recuento"]


def test_b7_pero_una_declaracion_manipulada_no_se_reimporta(tmp_path):
    """Si no, reimportar seria la manera comoda de blanquear una edicion."""
    fuente = RAIZ / "ejemplos" / "respuestas-clasificador.json"
    decl = tmp_path / "declaracion.json"
    _actaira("contestar", str(fuente), "--salida", str(decl))

    d = _json.loads(decl.read_text(encoding="utf-8"))
    d["sello"]["registros"][0]["contenido"]["valor"] = "lo que a mi me conviene"
    decl.write_text(_json.dumps(d, ensure_ascii=False), encoding="utf-8")

    r = _actaira("preguntar", "--respuestas", str(decl), "--json")
    assert r.returncode != 0
    assert "no verifica" in (r.stdout + r.stderr)


def test_b7_ni_una_con_dos_listas_de_registros_que_no_coinciden(tmp_path):
    """La copia de fuera no la cubre la raiz, y por eso ya no se escribe.

    Un fichero de la version anterior trae las dos. No se elige una: elegir
    seria decidir en silencio cual de las dos versiones de la verdad vale, que
    es justo como el fallo paso desapercibido.
    """
    fuente = RAIZ / "ejemplos" / "respuestas-clasificador.json"
    decl = tmp_path / "declaracion.json"
    _actaira("contestar", str(fuente), "--salida", str(decl))

    d = _json.loads(decl.read_text(encoding="utf-8"))
    de_fuera = _json.loads(_json.dumps(d["sello"]["registros"]))
    de_fuera[0]["contenido"]["valor"] = "lo que a mi me conviene"
    d["registros"] = de_fuera
    decl.write_text(_json.dumps(d, ensure_ascii=False), encoding="utf-8")

    r = _actaira("preguntar", "--respuestas", str(decl), "--json")
    assert r.returncode != 0
    assert "dos listas de registros" in (r.stdout + r.stderr)


def test_b7_y_un_fichero_que_no_es_ni_una_cosa_ni_la_otra_lo_dice(tmp_path):
    malo = tmp_path / "x.json"
    malo.write_text('{"cosas": []}', encoding="utf-8")
    r = _actaira("preguntar", "--respuestas", str(malo), "--json")
    assert r.returncode != 0
    assert "respuestas" in (r.stdout + r.stderr) and "registros" in (r.stdout + r.stderr)


def test_b4_el_verbo_del_almacen_distingue_intacto_de_alterado(tmp_path):
    ruta = tmp_path / "ev.jsonl"
    Almacen.abrir(ruta).anadir([_reg()], T0)
    bien = _actaira("almacen", "--almacen", str(ruta))
    assert bien.returncode == 0 and "cadena intacta" in bien.stdout

    ls = _lineas(ruta)
    ls[0]["registro"]["contenido"]["resultado"] = "sin_hallazgos"
    _escribir(ruta, ls)
    mal = _actaira("almacen", "--almacen", str(ruta))
    assert mal.returncode == 5, mal.stdout
    assert "NO ES EL QUE SE ESCRIBIO" in mal.stdout


# --------------------------------------------------------------------------
# La pasada adversarial de la fase 13: atacar los arreglos, no los fallos.
# --------------------------------------------------------------------------

def test_adv_truncar_el_almacen_deja_una_cadena_que_verifica(tmp_path):
    """Y esta prueba existe para que eso este ESCRITO, no para celebrarlo.

    Un prefijo de una cadena valida es una cadena valida. Ningun mecanismo
    interno puede distinguir un almacen truncado de uno que aun no ha crecido,
    asi que decir «la cadena demuestra que no fue alterado» seria falso. Lo que
    lo detecta esta en la prueba de al lado.
    """
    ruta = tmp_path / "ev.jsonl"
    alm = Almacen.abrir(ruta)
    for i in range(4):
        alm.anadir([_reg({"i": i})], T0)

    _escribir(ruta, _lineas(ruta)[:2])
    assert Almacen.abrir(ruta).verificar_cadena() == [], \
        "un prefijo verifica, y por eso hace falta anclar la cabeza fuera"


def test_adv_pero_la_cabeza_anclada_si_lo_detecta(tmp_path):
    ruta = tmp_path / "ev.jsonl"
    alm = Almacen.abrir(ruta)
    for i in range(4):
        alm.anadir([_reg({"i": i})], T0)
    anclada = Almacen.abrir(ruta).cabeza()

    _escribir(ruta, _lineas(ruta)[:2])
    mal = Almacen.abrir(ruta).comprobar_cabeza(anclada)
    assert mal and "quitaron lineas del final" in mal

    r = _actaira("almacen", "--almacen", str(ruta), "--cabeza-esperada", anclada)
    assert r.returncode == 5, r.stdout


def test_adv_gemelo_la_cabeza_correcta_no_da_falsa_alarma(tmp_path):
    ruta = tmp_path / "ev.jsonl"
    Almacen.abrir(ruta).anadir([_reg()], T0)
    cabeza = Almacen.abrir(ruta).cabeza()
    r = _actaira("almacen", "--almacen", str(ruta), "--cabeza-esperada", cabeza)
    assert r.returncode == 0 and "es la cabeza esperada" in r.stdout


def test_adv_revocar_no_puede_tapar_una_rotura(tmp_path):
    """`anadir` releia la cadena entera; `revocar` no, y por ahi se extendia.

    Una rotura tapada bajo cuatro lineas nuevas y perfectamente selladas es
    peor que una rotura visible: la cadena sigue rota, pero el incidente queda
    a cuatro pantallas de scroll del sitio donde alguien mira.
    """
    ruta = tmp_path / "ev.jsonl"
    r = _reg()
    Almacen.abrir(ruta).anadir([r], T0)
    ls = _lineas(ruta)
    ls[0]["registro"]["contenido"]["resultado"] = "sin_hallazgos"
    _escribir(ruta, ls)

    with pytest.raises(AlmacenAlterado, match="no se anade a un almacen que no verifica"):
        Almacen.abrir(ruta).revocar(r.id, "da igual", "quien sea", T0)


def test_adv_lo_indecidible_se_dice_aunque_haya_hallazgos(tmp_path):
    """Callar lo que no se pudo decidir porque hay otra cosa que contar.

    Dos artefactos sin marcar y uno con un trozo C2PA sin verificar daba dos
    hallazgos y ni una palabra del tercero, con lo que quien lo leyera entendia
    que el resto estaba bien. Es la tercera negativa por omision.
    """
    desnudo = _png(tmp_path / "desnudo.png")
    dudoso = _con_cabx(_png(tmp_path / "dudoso.png"))
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(desnudo, dudoso)), REGLAS)

    assert r.resultado is Resultado.CON_HALLAZGOS
    assert any("dudoso.png" in n for n in r.no_cubre), \
        "el artefacto indecidible tiene que aparecer en la frontera del resultado"
    assert any(h.localizacion == "desnudo.png" for h in r.hallazgos)


def test_adv_gemelo_sin_nada_dudoso_la_frontera_no_inventa_dudas(tmp_path):
    desnudo = _png(tmp_path / "desnudo.png")
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(desnudo,)), REGLAS)
    assert not any("C2PA" in n for n in r.no_cubre)


# --------------------------------------------------------------------------
# Lo que la segunda revision pidio comprobar y no estaba comprobado.
# --------------------------------------------------------------------------

def test_adv_dos_escritores_a_la_vez_no_bifurcan_la_cadena(tmp_path):
    """El bloqueo del fichero, ejercitado de verdad y no solo escrito.

    Dos pasadas de integracion continua simultaneas calcularian el mismo
    `previo` y produciran dos lineas con el mismo numero de orden. Se ponen en
    fila con `flock`, y esto lo comprueba con procesos de verdad: un hilo no
    vale, porque el bloqueo es entre procesos.
    """
    import concurrent.futures

    ruta = tmp_path / "ev.jsonl"
    guion = RAIZ / "motor" / "tests" / "_escritor.py"
    guion.write_text(
        "import sys\n"
        "from datetime import datetime, timezone\n"
        "from actaira_motor.evidencia.registro import Registro\n"
        "from actaira_motor.vigilancia.almacen import Almacen\n"
        "T = datetime(2027,12,2,10,0,tzinfo=timezone.utc)\n"
        "r = Registro.nuevo('AIA-009','ACT-C-009','sha256:aaa',T,{'quien':sys.argv[2]},30)\n"
        "Almacen.abrir(sys.argv[1]).anadir([r], T)\n", encoding="utf-8")
    try:
        def correr(i):
            return subprocess.run([sys.executable, str(guion), str(ruta), f"p{i}"],
                                  cwd=RAIZ, env=ENTORNO, capture_output=True, text=True, encoding="utf-8", errors="replace")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            res = list(ex.map(correr, range(8)))
    finally:
        guion.unlink(missing_ok=True)

    assert all(r.returncode == 0 for r in res), [r.stderr[-300:] for r in res if r.returncode]
    alm = Almacen.abrir(ruta)
    assert alm.verificar_cadena() == [], "ocho escritores a la vez bifurcaron la cadena"
    assert len(alm.registros()) == 8
    numeros = [d["n"] for d in _lineas(ruta)]
    assert numeros == list(range(1, len(numeros) + 1)), numeros


def test_adv_ninguna_ruta_del_motor_afirma_cumplimiento(tmp_path):
    """Recorre TODOS los paquetes de reglas, no solo el del articulo 50.

    La revision pregunto si queda alguna ruta que emita un «cumple» a partir de
    una senal de presencia. La respuesta no puede ser «he mirado el articulo
    50»: se corre cada paquete del catalogo contra un repositorio vacio y otro
    con ruido, y se exige que ningun resultado limpio salga sin publicar QUE
    miro. Un SIN_HALLAZGOS sin frontera es indistinguible de no haber mirado.
    """
    from actaira_motor.controles.motor import Arbol, Paquete, correr_paquete

    (tmp_path / "ruido.py").write_text(
        "# aqui se menciona seguridad, gestion de riesgos, logging y cifrado\n"
        "TEXTO = 'tenemos un sistema de gestion de riesgos y registros de auditoria'\n",
        encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# Proyecto\nCumplimos el Reglamento de IA y la ISO 42001.\n", encoding="utf-8")
    arbol = Arbol.leer(tmp_path)

    paquetes = sorted((RAIZ / "catalogo" / "reglas").glob("*.json"))
    assert len(paquetes) >= 10, "el barrido tiene que recorrer el catalogo entero"
    limpios = 0
    for ruta in paquetes:
        pk = Paquete.cargar(ruta)
        if pk.motor == "art50":
            continue                      # tiene su propio barrido, arriba
        res, _ = correr_paquete(arbol, pk)
        assert not res.resultado.afirma_cumplimiento
        if res.resultado is Resultado.SIN_HALLAZGOS:
            limpios += 1
            assert res.cubre, f"{ruta.name}: limpio y sin decir que miro"
            assert res.no_cubre, f"{ruta.name}: limpio y sin decir que NO cubre"
    assert limpios, "si ningun paquete sale limpio, esta prueba no comprueba nada"


def test_adv_un_readme_que_lo_promete_todo_no_satisface_ningun_paquete(tmp_path):
    """El gemelo del anterior: prosa que afirma cumplir no es una observacion."""
    from actaira_motor.controles.motor import Arbol, Paquete, correr_paquete

    (tmp_path / "CUMPLIMIENTO.md").write_text(
        "# Declaracion\n\n"
        "Este sistema implementa gestion de riesgos, supervision humana, registros\n"
        "automaticos, ciberseguridad, gobernanza de datos, documentacion tecnica,\n"
        "vigilancia poscomercializacion y notificacion de incidentes graves.\n",
        encoding="utf-8")
    arbol = Arbol.leer(tmp_path)
    for ruta in sorted((RAIZ / "catalogo" / "reglas").glob("*.json")):
        pk = Paquete.cargar(ruta)
        if pk.motor == "art50":
            continue
        res, _ = correr_paquete(arbol, pk)
        for c in res.cubre:
            assert "CUMPLIMIENTO.md" not in c, \
                f"{ruta.name}: un documento que se promete a si mismo entro como cobertura"


def test_adv_migrar_un_almacen_viejo_no_lo_declara_intacto(tmp_path):
    """La compatibilidad hacia atras, resuelta sin mentir.

    Encadenar un almacen que no tenia cadena y callarlo seria la manera comoda
    de blanquear un fichero editado: entra sin cadena y sale con pinta de
    expediente impecable. Cada linea migrada sale marcada, y la marca va DENTRO
    del sello, asi que quitarla rompe la cadena.
    """
    viejo = tmp_path / "viejo.jsonl"
    Almacen.abrir(viejo).anadir([_reg({"a": 1})], T0)
    Almacen.abrir(viejo).anadir([_reg({"b": 2})], T0)
    ls = _lineas(viejo)
    for l in ls:
        for campo in ("n", "previo", "sello"):
            l.pop(campo)
    _escribir(viejo, ls)

    nuevo = tmp_path / "nuevo.jsonl"
    migradas, ya = Almacen.abrir(viejo).migrar_a(Almacen.abrir(nuevo))
    assert (migradas, ya) == (2, 0)

    alm = Almacen.abrir(nuevo)
    assert alm.verificar_cadena() == []
    assert len(alm.registros()) == 2
    assert alm.sin_cadena_demostrable() == 2, "las lineas migradas siempre lo dicen"

    # y la marca no se puede quitar sin romper la cadena
    ls = _lineas(nuevo)
    del ls[0]["origen"]
    _escribir(nuevo, ls)
    assert Almacen.abrir(nuevo).verificar_cadena(), \
        "quitar la marca de migracion tiene que romper el sello"


def test_adv_lo_que_se_anade_despues_de_migrar_ya_no_lleva_la_marca(tmp_path):
    """El gemelo: la marca es de las lineas viejas, no una mancha permanente."""
    viejo = tmp_path / "viejo.jsonl"
    Almacen.abrir(viejo).anadir([_reg({"a": 1})], T0)
    ls = _lineas(viejo)
    for campo in ("n", "previo", "sello"):
        ls[0].pop(campo)
    _escribir(viejo, ls)

    nuevo = tmp_path / "nuevo.jsonl"
    Almacen.abrir(viejo).migrar_a(Almacen.abrir(nuevo))
    Almacen.abrir(nuevo).anadir([_reg({"b": 2})], T0)

    alm = Almacen.abrir(nuevo)
    assert alm.verificar_cadena() == []
    assert alm.sin_cadena_demostrable() == 1
    assert len(alm.registros()) == 2


def test_adv_migrar_se_niega_a_escribir_encima(tmp_path):
    viejo = tmp_path / "viejo.jsonl"
    Almacen.abrir(viejo).anadir([_reg()], T0)
    with pytest.raises(AlmacenAlterado, match="no esta vacio"):
        Almacen.abrir(viejo).migrar_a(Almacen.abrir(viejo))


def test_adv_el_verbo_migrar_exige_decirlo_en_voz_alta(tmp_path):
    viejo = tmp_path / "viejo.jsonl"
    Almacen.abrir(viejo).anadir([_reg()], T0)
    ls = _lineas(viejo)
    for campo in ("n", "previo", "sello"):
        ls[0].pop(campo)
    _escribir(viejo, ls)

    callado = _actaira("almacen", "migrar", "--almacen", str(viejo),
                       "--destino", str(tmp_path / "n1.jsonl"))
    assert callado.returncode == 4
    assert "NO se puede declarar intacto" in callado.stdout
    assert not (tmp_path / "n1.jsonl").exists()

    dicho = _actaira("almacen", "migrar", "--almacen", str(viejo),
                     "--destino", str(tmp_path / "n2.jsonl"),
                     "--acepto-que-no-se-puede-demostrar")
    assert dicho.returncode == 0, dicho.stdout
    assert "migrada_sin_cadena" in dicho.stdout
