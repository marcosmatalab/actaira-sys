"""Fase 19: la remediacion delegada, y el techo que la hace honesta.

La regla entera de este modulo es una negativa: ningun estado de ningun tablero
cierra una no conformidad. Es tambien la unica funcionalidad que todos los
productos de cumplimiento implementan al reves, porque si el ticket cerrado
cerrara la no conformidad el panel se pondria verde solo. Eso es el problema,
no la solucion.
"""
from __future__ import annotations

import json
import os
import subprocess as _sp
import sys as _sys
import urllib.request
from pathlib import Path

import pytest

from actaira_motor.gestion.noconformidad import ORDEN, EstadoNC
from actaira_motor.remediacion.contrato import (TECHO, Delegacion, Encargo,
                                                LimiteDelRemediador, elegir,
                                                emitible, nombres)
from actaira_motor.remediacion.fichero import RemediadorFichero
from actaira_motor.remediacion.rest import (ErrorDelRemediador, RemediadorHttp,
                                            PERFILES, _rellenar, _ruta,
                                            cargar_perfil)
from actaira_motor.remediacion.traduccion import (TABLAS, EstadoQueNoConocemos,
                                                  Lectura, leer, mover,
                                                  traducir_estado)

RAIZ = Path(__file__).resolve().parents[2]
ENT = {**os.environ, "PYTHONPATH": str(RAIZ / "motor" / "src"), "PYTHONIOENCODING": "utf-8"}


def _encargo(**kw) -> Encargo:
    base = dict(no_conformidad_id="NC-1", titulo={"es": "t", "en": "t"},
                cuerpo={"es": "c", "en": "c"}, obligacion_id="AIA-072",
                control_id="ACT-72-DRIFT", severidad="alta",
                responsable="equipo de datos", compromiso="2026-10-15")
    base.update(kw)
    return Encargo(**base)


# --- el techo, que es la regla entera -------------------------------------

def test_ningun_estado_externo_llega_a_verificada():
    """Da igual que la columna se llame «Done», «Closed» o «Verified by QA».

    Lo que dice es que alguien dio el trabajo por hecho en su tablero.
    VERIFICADA dice que se comprobo que la causa dejo de producir el efecto, y
    eso exige una evidencia tomada DESPUES de ejecutar.
    """
    assert TECHO is EstadoNC.EJECUTADA
    for sistema, tabla in TABLAS.items():
        for columna, destino in tabla.items():
            e = traducir_estado(sistema, columna)
            assert ORDEN.index(e) <= ORDEN.index(TECHO), (sistema, columna, e)
            assert e is not EstadoNC.VERIFICADA


def test_y_el_techo_lo_impone_el_codigo_aunque_la_tabla_mienta(monkeypatch):
    """El gemelo, y el que importa: una tabla es un dato que alguien edita.

    Si el techo viviera solo en los valores de la tabla, bastaria con que
    alguien escribiera «verificada» en un fichero para que un ticket cerrado
    cerrara una no conformidad. Aqui la tabla miente a proposito y el codigo se
    niega igual.
    """
    monkeypatch.setitem(TABLAS, "mentirosa", {"done": EstadoNC.VERIFICADA.value})
    with pytest.raises(ValueError, match="por encima del techo"):
        traducir_estado("mentirosa", "Done")


def test_la_delegacion_publica_ese_limite_para_que_viaje_con_ella():
    """Un limite que no viaja con lo que afirma deja a quien lo lee creyendo
    que el ticket cerrado cerro algo."""
    r = RemediadorHttp("https://x", cargar_perfil("jira"))
    textos = " ".join(l.que["es"] for l in r.limites())
    assert "no cierra la no conformidad" in textos
    assert all(l.que["es"] and l.que["en"] for l in r.limites())


# --- lo que no se entiende no se ignora -----------------------------------

def test_una_columna_que_no_esta_en_la_tabla_NO_se_ignora():
    """Un equipo anade «En revision de seguridad», los tickets se paran ahi, y
    el ciclo de mejora deja de moverse sin que nadie se entere."""
    with pytest.raises(EstadoQueNoConocemos, match="no esta en la tabla"):
        traducir_estado("jira", "En revision de seguridad")


def test_ni_un_sistema_del_que_no_hay_tabla():
    with pytest.raises(EstadoQueNoConocemos, match="no hay tabla"):
        traducir_estado("monday", "Done")


def test_pero_las_que_si_estan_se_traducen():
    """El gemelo: un guardia que no deja pasar nada se quita en una semana."""
    assert traducir_estado("jira", "In Progress") is EstadoNC.EN_ANALISIS
    assert traducir_estado("linear", "completed") is EstadoNC.EJECUTADA
    assert traducir_estado("github", "closed") is EstadoNC.EJECUTADA


def test_cancelado_no_es_hecho():
    """Linear distingue `canceled` de `completed`, y fundirlos habria hecho que
    renunciar a arreglar algo contara como haberlo arreglado."""
    assert traducir_estado("linear", "canceled") is EstadoNC.ABIERTA


# --- no se inventa el autor -----------------------------------------------

def _deleg(**kw) -> Delegacion:
    base = dict(sistema="jira", referencia="ACT-1", url="https://x/ACT-1",
                no_conformidad_id="NC-1", estado_externo="Done", actor="Ana Ruiz",
                cargo_del_actor="responsable de calidad",
                cuando="2026-09-10T09:00:00+00:00")
    base.update(kw)
    return Delegacion(**base)


def test_sin_autor_no_se_mueve_nada_y_se_dice():
    """Escribir «sistema» en lugar de la persona seria inventar justo el dato
    que la clausula 10.2 pide."""
    l = leer(_deleg(actor=""))
    assert l.estado is EstadoNC.EJECUTADA, "la lectura sale igual: lo que cambia es si mueve"
    assert not l.puede_mover
    assert "no se escribe «sistema»" in l.por_que_no["es"] and l.por_que_no["en"]
    t, por_que = mover(EstadoNC.CON_ACCION, l)
    assert t is None and por_que["es"]


def test_ni_sin_fecha_porque_el_estado_se_calcula_por_fecha():
    l = leer(_deleg(cuando=""))
    assert not l.puede_mover and "sin fecha" in l.por_que_no["es"]


def test_con_autor_y_fecha_si_mueve():
    """El gemelo. Sin el, «no se inventa el autor» se cumpliria no moviendo
    nunca nada, que es la manera comoda de pasar la prueba."""
    t, por_que = mover(EstadoNC.CON_ACCION, leer(_deleg()))
    assert t is not None and t.a is EstadoNC.EJECUTADA
    assert t.quien == "Ana Ruiz" and t.cargo == "responsable de calidad"
    assert "jira:ACT-1" in t.nota and por_que["es"] and por_que["en"]


def test_quien_sin_en_calidad_de_que_no_basta():
    """Son dos preguntas distintas, y la segunda es la que hace responsable a
    alguien. Casi ningun sistema de tickets guarda la segunda."""
    t, por_que = mover(EstadoNC.CON_ACCION, leer(_deleg(cargo_del_actor="")))
    assert t is None and "en calidad de qué" in por_que["es"]
    t2, _ = mover(EstadoNC.CON_ACCION, leer(_deleg(cargo_del_actor="")),
                  cargo_por_defecto="responsable de calidad")
    assert t2 is not None and t2.cargo == "responsable de calidad"


# --- solo hacia delante ---------------------------------------------------

def test_arrastrar_la_tarjeta_hacia_atras_no_reabre_nada():
    """Un tablero es una herramienta de trabajo y las tarjetas se arrastran. Si
    eso reabriera la no conformidad, el ciclo de la 10.2 dependeria de como
    alguien organiza su semana."""
    t, por_que = mover(EstadoNC.EJECUTADA, leer(_deleg(estado_externo="To Do")))
    assert t is None and "no retrocede" in por_que["es"] and por_que["en"]


def test_y_el_mismo_estado_dos_veces_tampoco_escribe_dos_transiciones():
    """La idempotencia de la sincronizacion: leer el mismo ticket cada hora no
    puede llenar el almacen de transiciones identicas."""
    t, _ = mover(EstadoNC.EJECUTADA, leer(_deleg(estado_externo="Done")))
    assert t is None


def test_pero_hacia_delante_si():
    t, _ = mover(EstadoNC.ABIERTA, leer(_deleg(estado_externo="In Progress")))
    assert t is not None and t.a is EstadoNC.EN_ANALISIS


def test_con_accion_no_sale_del_estado_de_un_ticket(monkeypatch):
    """Exige accion, responsable y fecha comprometida. Construir la transicion
    sin ellos reventaria, que es peor que decir que no."""
    monkeypatch.setitem(TABLAS["jira"], "comprometido", EstadoNC.CON_ACCION.value)
    t, por_que = mover(EstadoNC.ABIERTA, leer(_deleg(estado_externo="comprometido")))
    assert t is None and "acción, responsable y fecha" in por_que["es"]


# --- el contrato ----------------------------------------------------------

def test_un_encargo_sin_dueno_ni_fecha_no_se_puede_construir():
    """Es la misma regla que la transicion a CON_ACCION: una accion sin dueno y
    sin fecha es una intencion."""
    for campo in ("responsable", "compromiso"):
        with pytest.raises(ValueError, match=campo):
            _encargo(**{campo: ""})


def test_y_el_titulo_va_en_los_dos_idiomas():
    """Un ticket en castellano dentro de un expediente pedido en ingles es el
    mismo defecto que ya se corrigio en las senales."""
    with pytest.raises(ValueError, match="los dos idiomas"):
        _encargo(titulo={"es": "solo castellano"})


def test_las_rutas_del_cliente_no_salen_salvo_que_alguien_lo_pida():
    """Un ticket lo lee mucha mas gente que un expediente firmado."""
    assert "src/modelo.py" not in _encargo().texto("es")
    con = _encargo(localizaciones=("src/modelo.py",))
    assert "src/modelo.py" in con.texto("es")
    assert "dónde se vio" in con.texto("es") and "where it was seen" in con.texto("en")


def test_lo_que_sale_pasa_por_la_misma_puerta_de_secretos_que_el_conector():
    """UNA definicion de secreto. Dos habrian sido dos sitios donde afinar el
    patron y uno donde olvidarse."""
    e = _encargo(cuerpo={"es": "usa el token ghp_" + "a" * 36, "en": "x"})
    assert "ghp_" not in e.texto("es")
    assert "[secreto retirado]" in e.texto("es")
    with pytest.raises(ValueError, match="credencial"):
        emitible({"nota": "https://usuario:contrasena@servidor/repo.git"})


def test_ningun_remediador_tiene_un_metodo_que_verifique():
    """Verificar es una observacion posterior y vive en el motor. Un remediador
    que verificara meteria la doctrina de esta casa en el codigo de
    integracion de un tercero, donde nadie la audita."""
    prohibidos = ("verificar", "cerrar", "aprobar", "cumple", "eficacia", "resultado")
    for tipo in (RemediadorHttp, RemediadorFichero):
        for nombre in dir(tipo):
            if nombre.startswith("_"):
                continue
            assert not any(p in nombre.lower() for p in prohibidos), (tipo.__name__, nombre)


def test_el_de_fichero_va_el_ultimo_para_no_tragarse_una_url(tmp_path):
    assert nombres()[-1] == "fichero"
    assert not RemediadorFichero.resuelve("https://x.atlassian.net")
    assert RemediadorFichero.resuelve(str(tmp_path))


def test_un_destino_de_red_sin_perfil_lo_dice_en_vez_de_adivinar():
    with pytest.raises(ErrorDelRemediador, match="necesita un perfil"):
        elegir("https://x.atlassian.net")


def test_un_destino_que_nadie_sabe_hablar_lo_dice():
    with pytest.raises(ValueError, match="ningun remediador"):
        elegir("ftp://nadie/habla/esto")


# --- los perfiles ---------------------------------------------------------

def test_los_perfiles_que_vienen_de_serie_estan_completos():
    """Anadir un sistema es un fichero JSON y sus pruebas, no un despliegue. Lo
    que no puede ser es que el fichero este a medias y reviente en produccion."""
    perfiles = sorted(PERFILES.glob("*.json"))
    assert {p.stem for p in perfiles} >= {"jira", "linear", "github"}
    for ruta in perfiles:
        d = cargar_perfil(ruta.stem)
        assert d["sistema"] in TABLAS, f"{ruta.name}: sin tabla de estados no se puede leer"
        for paso in ("abrir", "consultar"):
            assert d[paso]["url"] and d[paso].get("metodo")
        assert d["abrir"]["ruta_referencia"]
        assert d["consultar"]["ruta_estado"]
        assert d["credencial"]["variable"].startswith("ACTAIRA_")
        for l in d.get("limites", []):
            assert l["que"]["es"] and l["que"]["en"] and l["por_que"]


def test_la_plantilla_no_usa_format_y_por_eso_aguanta_una_llave(tmp_path):
    """Una remediacion que mencione `{modelo}` habria reventado la llamada con
    `format`, o -peor- habria leido un atributo."""
    salida = _rellenar({"a": "hola {titulo} y {modelo}"}, {"titulo": "x"})
    assert salida["a"] == "hola x y {modelo}"


def test_las_rutas_de_respuesta_leen_listas_y_diccionarios():
    d = {"data": {"issues": [{"id": "ENG-1"}]}}
    assert _ruta(d, "data.issues.0.id") == "ENG-1"
    assert _ruta(d, "data.no.existe") is None


# --- de punta a punta, con el transporte sustituido -----------------------

class _Falso:
    """El servidor de tickets, escrito a mano.

    Existe porque una integracion que solo se prueba contra un servidor de
    verdad no se prueba nunca en integracion continua, y entonces lo unico que
    se comprueba de ella es que importa.
    """

    def __init__(self, respuestas: list) -> None:
        self.respuestas = list(respuestas)
        self.vistas: list[urllib.request.Request] = []

    def __call__(self, peticion: urllib.request.Request):
        self.vistas.append(peticion)
        return self.respuestas.pop(0)


def test_jira_de_punta_a_punta_sin_tocar_la_red(monkeypatch, tmp_path):
    monkeypatch.setenv("ACTAIRA_JIRA_TOKEN", "c2VjcmV0bw==")
    falso = _Falso([
        {"key": "ACT-7", "self": "https://x.atlassian.net/rest/api/3/issue/7"},
        {"fields": {"status": {"name": "In Progress"},
                    "assignee": {"displayName": "Ana Ruiz"},
                    "statuscategorychangedate": "2026-09-10T09:00:00+00:00"}},
    ])
    r = RemediadorHttp("https://x.atlassian.net", cargar_perfil("jira"), falso)
    d = r.abrir(_encargo())
    assert d.referencia == "ACT-7" and d.sistema == "jira"
    cuerpo = json.loads(falso.vistas[0].data.decode("utf-8"))
    assert cuerpo["fields"]["summary"] == "t"
    assert "NC-1" in cuerpo["fields"]["labels"]
    assert falso.vistas[0].headers["Authorization"] == "Basic c2VjcmV0bw=="

    fresca = r.consultar(d)
    assert fresca.estado_externo == "In Progress" and fresca.actor == "Ana Ruiz"
    t, _ = mover(EstadoNC.ABIERTA, leer(fresca), cargo_por_defecto="responsable de calidad")
    assert t is not None and t.a is EstadoNC.EN_ANALISIS


def test_linear_habla_graphql_y_el_mismo_perfil_lo_describe(monkeypatch):
    """Que uno hable REST y el otro GraphQL no cambia nada: los dos son una
    peticion POST con un cuerpo JSON y una respuesta JSON."""
    monkeypatch.setenv("ACTAIRA_LINEAR_TOKEN", "lin_x")
    falso = _Falso([
        {"data": {"issueCreate": {"issue": {"identifier": "ENG-42",
                                            "url": "https://linear.app/ENG-42",
                                            "state": {"name": "Todo"}}}}},
        {"data": {"issue": {"identifier": "ENG-42", "url": "https://linear.app/ENG-42",
                            "updatedAt": "2026-09-11T09:00:00+00:00",
                            "state": {"type": "completed"},
                            "assignee": {"name": "Luis Gil"}}}},
    ])
    r = RemediadorHttp("equipo-123", cargar_perfil("linear"), falso)
    d = r.abrir(_encargo())
    assert d.referencia == "ENG-42"
    enviado = json.loads(falso.vistas[0].data.decode("utf-8"))
    assert enviado["variables"]["e"] == "equipo-123"
    fresca = r.consultar(d)
    assert traducir_estado("linear", fresca.estado_externo) is EstadoNC.EJECUTADA


def test_sin_la_variable_de_entorno_se_para_y_lo_explica(monkeypatch):
    """Este modulo NO guarda credenciales. Se leen del entorno de quien ejecuta
    y no se escriben en ninguna parte."""
    monkeypatch.delenv("ACTAIRA_JIRA_TOKEN", raising=False)
    r = RemediadorHttp("https://x", cargar_perfil("jira"), _Falso([{}]))
    with pytest.raises(ErrorDelRemediador, match="ACTAIRA_JIRA_TOKEN"):
        r.abrir(_encargo())


def test_una_respuesta_sin_referencia_no_se_da_por_buena(monkeypatch):
    """Sin referencia no hay vuelta: la no conformidad quedaria delegada en
    algo que no se puede consultar."""
    monkeypatch.setenv("ACTAIRA_JIRA_TOKEN", "x")
    r = RemediadorHttp("https://x", cargar_perfil("jira"), _Falso([{"errores": ["nope"]}]))
    with pytest.raises(ErrorDelRemediador, match="no trae la referencia"):
        r.abrir(_encargo())


def test_un_estado_que_no_se_puede_leer_NO_es_un_estado_sin_cambios(monkeypatch):
    monkeypatch.setenv("ACTAIRA_JIRA_TOKEN", "x")
    r = RemediadorHttp("https://x", cargar_perfil("jira"), _Falso([{"fields": {}}]))
    with pytest.raises(ErrorDelRemediador, match="no trae el estado"):
        r.consultar(_deleg())


# --- el verbo -------------------------------------------------------------

def _cli(*args):
    return _sp.run([_sys.executable, "-m", "actaira_motor.cli", *args],
                   cwd=RAIZ, env=ENT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _con_una_nc(tmp_path) -> str:
    alm = str(tmp_path / "ev.jsonl")
    r = _cli("noconformidad", "abrir", "--id", "NC-1", "--quien", "Ana Ruiz",
             "--cargo", "responsable de calidad", "--origen", "ACT-72-DRIFT",
             "--descripcion", "No hay metrica de deriva ni umbral que alerte",
             "--almacen", alm, "--ahora", "2026-09-01T09:00:00+00:00")
    assert r.returncode == 0, r.stderr
    return alm


def test_el_verbo_delega_y_deja_la_delegacion_en_el_almacen(tmp_path):
    alm = _con_una_nc(tmp_path)
    destino = str(tmp_path / "encargos")
    r = _cli("remediar", "abrir", "--destino", destino, "--id", "NC-1",
             "--responsable", "equipo de datos", "--compromiso", "2026-10-15",
             "--almacen", alm, "--ahora", "2026-09-01T10:00:00+00:00")
    assert r.returncode == 0, r.stderr
    assert (Path(destino) / "NC-1.md").is_file()
    lineas = [json.loads(l)["registro"]
              for l in Path(alm).read_text(encoding="utf-8").splitlines()]
    deleg = [l for l in lineas if l["control_id"] == "ACT-R-DELEGACION"]
    assert len(deleg) == 1
    assert deleg[0]["contenido"]["limites"], "los limites viajan con la delegacion"


def test_sin_dueno_ni_fecha_el_verbo_se_niega(tmp_path):
    alm = _con_una_nc(tmp_path)
    r = _cli("remediar", "abrir", "--destino", str(tmp_path / "e"), "--id", "NC-1",
             "--almacen", alm)
    assert r.returncode == 4 and "una intencion" in r.stderr


def test_sincronizar_dice_en_voz_alta_que_nada_de_esto_cierra(tmp_path):
    alm = _con_una_nc(tmp_path)
    destino = str(tmp_path / "encargos")
    _cli("remediar", "abrir", "--destino", destino, "--id", "NC-1",
         "--responsable", "equipo de datos", "--compromiso", "2026-10-15",
         "--almacen", alm, "--ahora", "2026-09-01T10:00:00+00:00")
    r = _cli("remediar", "sincronizar", "--destino", destino, "--almacen", alm,
             "--ahora", "2026-09-02T10:00:00+00:00")
    assert r.returncode == 0, r.stderr
    assert "ninguna de estas llega a VERIFICADA" in r.stdout
    assert "evidencia de eficacia" in r.stdout


def test_delegar_no_cambia_el_estado_de_la_no_conformidad(tmp_path):
    """Abrir un ticket no es analizar la causa ni comprometerse a nada. Si
    delegar moviera el estado, el panel se pondria a media asta por haber
    escrito un ticket."""
    alm = _con_una_nc(tmp_path)
    _cli("remediar", "abrir", "--destino", str(tmp_path / "e"), "--id", "NC-1",
         "--responsable", "equipo de datos", "--compromiso", "2026-10-15",
         "--almacen", alm, "--ahora", "2026-09-01T10:00:00+00:00")
    r = _cli("noconformidad", "listar", "--almacen", alm, "--json")
    ncs = json.loads(r.stdout)["no_conformidades"]
    assert len(ncs) == 1 and ncs[0]["estado"] == "abierta"


# --- lo que encontro la pasada adversarial de la fase 19 ------------------

def test_una_delegacion_de_otro_sistema_no_se_consulta_aqui(tmp_path):
    """Encontrado atacando esto. Con una delegacion en Jira y un --destino de
    carpeta, el remediador de fichero devolvia la delegacion intacta y su
    estado se traducia como si se hubiera preguntado a Jira. Nunca se pregunto
    a nadie, y el ciclo avanzaba con una respuesta que nadie dio.
    """
    alm = _con_una_nc(tmp_path)
    # se mete a mano una delegacion de jira, que es lo que pasaria si el
    # cliente delego en Jira y luego sincroniza apuntando a una carpeta
    from actaira_motor.evidencia.registro import Registro
    from actaira_motor.vigilancia.almacen import Almacen
    from datetime import datetime, timezone

    a = Almacen.abrir(alm)
    cuando = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    a.anadir([Registro.nuevo(
        obligacion_id="ISO-10.2", control_id="ACT-R-DELEGACION",
        sujeto_digest="nc:NC-1", observado_en=cuando,
        contenido={"delegacion": _deleg().a_json()}, frescura_dias=None)], cuando)

    r = _cli("remediar", "sincronizar", "--destino", str(tmp_path / "carpeta"),
             "--almacen", alm, "--ahora", "2026-09-02T10:00:00+00:00")
    assert r.returncode == 3, r.stdout
    assert "es de jira y este destino habla fichero" in r.stderr
    assert "0 movidas" in r.stdout
    # y la no conformidad NO se movio
    ncs = json.loads(_cli("noconformidad", "listar", "--almacen", alm,
                          "--json").stdout)["no_conformidades"]
    assert ncs[0]["estado"] == "abierta"


def test_el_texto_del_encargo_sale_del_catalogo_cuando_lo_hay(tmp_path):
    """Segunda negativa: un modelo nunca redacta remediaciones en ejecucion.

    La regla trae su titulo y su remediacion escritos por una persona y en los
    dos idiomas, y ese es el texto que llega al ticket: el que un auditor puede
    contrastar con el catalogo.
    """
    alm = str(tmp_path / "ev.jsonl")
    _cli("noconformidad", "abrir", "--id", "NC-9", "--quien", "Ana", "--cargo", "calidad",
         "--origen", "ACT-72-DRIFT", "--descripcion", "visto en la revision",
         "--almacen", alm, "--ahora", "2026-09-01T09:00:00+00:00")
    destino = tmp_path / "e"
    r = _cli("remediar", "abrir", "--destino", str(destino), "--id", "NC-9",
             "--responsable", "datos", "--compromiso", "2026-10-15", "--almacen", alm,
             "--ahora", "2026-09-01T10:00:00+00:00")
    assert r.returncode == 0, r.stderr
    assert "del catálogo" in r.stdout
    guardado = json.loads((destino / "NC-9.json").read_text(encoding="utf-8"))
    assert guardado["cuerpo"]["es"] != guardado["cuerpo"]["en"], "bilingue de verdad"
    assert guardado["texto_del_cliente"] == "visto en la revision"


def test_y_cuando_no_lo_hay_no_se_finge_una_traduccion(tmp_path):
    """Un `en` que repite el castellano es peor que no tenerlo: quien lee en
    ingles no sabe que esta leyendo otro idioma."""
    alm = str(tmp_path / "ev.jsonl")
    _cli("noconformidad", "abrir", "--id", "NC-8", "--quien", "Ana", "--cargo", "calidad",
         "--origen", "auditoria-interna-2026", "--descripcion", "El inventario no cuadra",
         "--almacen", alm, "--ahora", "2026-09-01T09:00:00+00:00")
    destino = tmp_path / "e"
    r = _cli("remediar", "abrir", "--destino", str(destino), "--id", "NC-8",
             "--responsable", "datos", "--compromiso", "2026-10-15", "--almacen", alm,
             "--ahora", "2026-09-01T10:00:00+00:00")
    assert "no se ha traducido" in r.stdout
    guardado = json.loads((destino / "NC-8.json").read_text(encoding="utf-8"))
    assert guardado["cuerpo"] == {"es": "", "en": ""}
    assert guardado["texto_del_cliente"] == "El inventario no cuadra"


def test_un_encargo_sin_texto_de_ninguno_de_los_dos_no_se_construye():
    with pytest.raises(ValueError, match="sin texto"):
        _encargo(cuerpo={"es": "", "en": ""}, texto_del_cliente="")


def test_por_muchas_veces_que_se_sincronice_nunca_se_cierra(tmp_path, monkeypatch):
    """La propiedad, y no un caso: se sincroniza doce veces contra un ticket
    que dice «Done» desde la primera, y la no conformidad se queda en ejecutada.

    Es el verbo entero y no la funcion pura: el techo tiene que sobrevivir al
    camino que de verdad corre un cliente, que es el que tiene el almacen, el
    reloj y la reconstruccion del estado por fechas.
    """
    import actaira_motor.remediacion.rest as rest
    from actaira_motor import cli

    alm = _con_una_nc(tmp_path)
    monkeypatch.setenv("ACTAIRA_JIRA_TOKEN", "x")
    respuestas = [{"key": "ACT-7", "self": "https://j/7"}] + [
        {"fields": {"status": {"name": "Done"},
                    "assignee": {"displayName": "Ana Ruiz"},
                    "statuscategorychangedate": f"2026-09-{d:02d}T09:00:00+00:00"}}
        for d in range(2, 20)]
    monkeypatch.setattr(rest, "_http", lambda p: respuestas.pop(0))

    assert cli.main(["remediar", "abrir", "--destino", "https://j", "--perfil", "jira",
                     "--id", "NC-1", "--responsable", "datos", "--compromiso", "2026-10-15",
                     "--almacen", alm, "--ahora", "2026-09-01T10:00:00+00:00"]) == 0
    for dia in range(2, 14):
        cli.main(["remediar", "sincronizar", "--destino", "https://j", "--perfil", "jira",
                  "--almacen", alm, "--cargo", "responsable de calidad",
                  "--ahora", f"2026-09-{dia:02d}T10:00:00+00:00"])

    ncs = json.loads(_cli("noconformidad", "listar", "--almacen", alm,
                          "--json").stdout)["no_conformidades"]
    assert len(ncs) == 1
    assert ncs[0]["estado"] == "ejecutada", "el techo aguanta doce pasadas"
    assert ncs[0]["evidencia_de_eficacia"] is None
    movimientos = [t for t in ncs[0]["transiciones"] if t["a"] == "ejecutada"]
    assert len(movimientos) == 1, "y no escribe doce transiciones identicas"
