"""El contrato entre el motor y la plataforma, validado contra los documentos de verdad.

El motor es Python y la plataforma es Go. La frontera es un proceso y un JSON,
y sin un contrato escrito esa frontera se rompe en SILENCIO: el motor cambia el
nombre de un campo, la plataforma lo lee como vacio, y el cliente ve un
expediente incompleto sin que falle nada en ninguno de los dos lados.

Esta puerta genera cada documento de verdad -- no un ejemplo guardado, que
envejeceria -- y lo valida contra su esquema.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema", reason="dependencia de desarrollo")

from actaira_motor.aplicabilidad.motor import Perfil
from actaira_motor.catalogo.cargador import cargar
from actaira_motor.controles.motor import Arbol
from actaira_motor.expediente.anexoiv import generar as gen_iv
from actaira_motor.expediente.anexov import generar as gen_v
from actaira_motor.expediente.soa import generar as gen_soa
from actaira_motor.formularios.cuestionario import construir as gen_q
from actaira_motor.formularios.plan import construir as gen_plan
from actaira_motor.vigilancia.almacen import Almacen
from actaira_motor.vigilancia.barrido import observar
from actaira_motor.vigilancia.reconciliar import reconciliar

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "motor" / "tests" / "fixtures" / "clasificador-candidatos"
CUANDO = date(2027, 12, 2)
AHORA = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)
PERFIL = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii")


def _esquema(nombre: str) -> dict:
    return json.loads((RAIZ / "contrato" / f"{nombre}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cat():
    return cargar(str(RAIZ / "catalogo"))


@pytest.fixture(scope="module")
def plan(cat):
    return gen_plan(cat, PERFIL, CUANDO, str(FIX), str(RAIZ / "catalogo" / "reglas"))


@pytest.fixture(scope="module")
def cuestionario(cat, plan):
    return gen_q(cat, plan, [], AHORA, cat.formularios)


def _validar(doc, nombre):
    jsonschema.validate(doc, _esquema(nombre))


def test_el_plan_cumple_su_contrato(plan):
    _validar(plan, "plan")


def test_el_cuestionario_cumple_su_contrato(cuestionario):
    _validar(cuestionario, "cuestionario")


def test_la_soa_cumple_su_contrato(cat, plan, cuestionario):
    _validar(gen_soa(cat, plan, cuestionario, cuando=CUANDO), "soa")


def test_el_anexo_iv_cumple_su_contrato(plan):
    doc = gen_iv(RAIZ / "catalogo" / "ai-act" / "anexo-iv.json",
                 Arbol.leer(FIX), plan, cuando=CUANDO)
    _validar(doc, "anexo-iv")


def test_el_anexo_v_cumple_su_contrato(cuestionario):
    doc = gen_v(RAIZ / "catalogo" / "ai-act" / "anexo-v.json",
                Arbol.leer(FIX), cuestionario, CUANDO)
    _validar(doc, "anexo-v")


def test_la_vigilancia_cumple_su_contrato(cat, tmp_path):
    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    regs, sujetos, esperados, _ = observar(
        cat, PERFIL, CUANDO, str(FIX), str(RAIZ / "catalogo" / "reglas"), AHORA)
    alm.anadir(regs, AHORA)
    _validar(reconciliar(alm, sujetos, AHORA, esperados=esperados).a_json(), "vigilancia")


def test_una_seccion_ausente_del_anexo_iv_trae_su_motivo(plan):
    """El esquema lo exige y aqui se comprueba que el motor lo cumple de verdad:
    una seccion en blanco es indistinguible de una que nadie escribio."""
    doc = gen_iv(RAIZ / "catalogo" / "ai-act" / "anexo-iv.json",
                 Arbol.leer(FIX), plan, cuando=CUANDO)
    ausentes = [s for s in doc["secciones"] if s["procedencia"] == "ausente"]
    assert ausentes
    for s in ausentes:
        assert s.get("motivo_ausencia"), s["id"]


def test_una_declaracion_sin_firma_lleva_su_aviso(cuestionario):
    """Tambien lo exige el esquema: sin firma, el aviso de BORRADOR es obligatorio,
    y es la unica manera de que la palabra no se pueda quitar por otra via."""
    doc = gen_v(RAIZ / "catalogo" / "ai-act" / "anexo-v.json",
                Arbol.leer(FIX), cuestionario, CUANDO)
    assert doc["firmado"] is False and doc["aviso"] is not None
    with pytest.raises(jsonschema.ValidationError):
        _validar({**doc, "aviso": None}, "anexo-v")


# Lo que vive en `contrato/` y NO describe un documento del motor.
#
# `indice.json` es el indice, y `openapi.json` describe la API que SIRVE esos
# documentos, que es otra cosa: dice que rutas hay, no que forma tiene lo que
# devuelven. Se listan aqui, arriba y con nombre, en vez de saltarlos dentro de
# cada puerta: un fichero que se cuele en `contrato/` sin ser ninguna de las dos
# cosas tiene que romper algo, y si cada puerta lleva su propia excepcion,
# acaban divergiendo y el fichero nuevo pasa por el hueco entre ellas.
NO_SON_DOCUMENTOS = {"indice", "openapi"}


def test_el_indice_del_contrato_nombra_todos_los_esquemas_y_ninguno_de_mas():
    indice = _esquema("indice")
    en_disco = {p.stem for p in (RAIZ / "contrato").glob("*.json")} - NO_SON_DOCUMENTOS
    assert set(indice["documentos"]) == en_disco, set(indice["documentos"]) ^ en_disco
    for i in ("es", "en"):
        assert indice["por_que_existe"][i] and indice["lo_que_el_esquema_no_puede_decir"][i]


def test_todo_esquema_declara_su_version_en_el_campo_esquema():
    """Sin version en el propio documento, la plataforma no puede saber si el
    JSON que acaba de leer lo entiende."""
    for p in sorted((RAIZ / "contrato").glob("*.json")):
        if p.stem in NO_SON_DOCUMENTOS:
            continue
        e = json.loads(p.read_text(encoding="utf-8"))
        # `capas.json` no describe UN documento sino cuatro, asi que la
        # comprobacion recorre sus definiciones. La regla es la misma para las
        # cuatro y por eso se escribe una vez: cada documento dice su version
        # dentro, porque al otro lado de la frontera no hay nadie a quien
        # preguntarle que esquema acaba de leer.
        candidatos = list(e.get("$defs", {}).values()) if "$defs" in e else [e]
        mirados = 0
        for c in candidatos:
            if "properties" not in c or "esquema" not in c["properties"]:
                continue
            mirados += 1
            const = c["properties"]["esquema"]["const"]
            assert const.startswith("actaira/") and const.endswith("/v1"), p.name
            assert "esquema" in c["required"], p.name
        assert mirados, f"{p.name}: ningun documento declara su version"


# --- el castellano que se escapa de un documento ----------------------------

FUNCIONALES = (" de ", " la ", " el ", " que ", " los ", " las ", " para ", " con ",
               " una ", " por ", " del ", " se ")

# Campos que TODAVIA salen solo en castellano, con su motivo. La lista existe
# para que la deuda sea visible y no pueda crecer en silencio: anadir un campo
# aqui obliga a escribir por que, y quitarlo es el trabajo de B-011.
SOLO_CASTELLANO = {
    "regla_aplicabilidad": "la regla que decidio la aplicabilidad, con su identificador dentro",
    "cubre": "el alcance en prosa de lo que un control leyo",
    "no_cubre": "lo que un control NO mira, en prosa",
    "motivo_indeterminado": "la causa de un INDETERMINADO, escrita por el motor",
    "_nota": "clave de ejemplo de los ficheros de respuestas",
}


def _prosa_suelta(nodo, ruta=""):
    """Cadenas largas en castellano que no cuelgan de una clave `es`."""
    fuera = []
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            if k == "es":
                continue                      # su pareja `en` la comprueba el esquema
            if k in SOLO_CASTELLANO:
                continue
            fuera += _prosa_suelta(v, f"{ruta}.{k}")
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            fuera += _prosa_suelta(v, f"{ruta}[{i}]")
    elif isinstance(nodo, str):
        if len(nodo.split()) >= 6 and any(f in f" {nodo} " for f in FUNCIONALES):
            fuera.append((ruta, nodo[:80]))
    return fuera


def test_ningun_documento_emite_castellano_suelto(cat, plan, cuestionario, tmp_path):
    """Un cliente que pide el expediente en ingles no puede recibir frases en
    castellano dentro. El `detalle` de la vigilancia lo hacia: era una cadena
    que salia de `Registro.estado()` y acababa impresa tal cual."""
    from actaira_motor.vigilancia.almacen import Almacen
    from actaira_motor.vigilancia.barrido import observar
    from actaira_motor.vigilancia.reconciliar import reconciliar

    alm = Almacen.abrir(tmp_path / "ev.jsonl")
    regs, sujetos, esperados, _ = observar(
        cat, PERFIL, CUANDO, str(FIX), str(RAIZ / "catalogo" / "reglas"), AHORA)
    alm.anadir(regs, AHORA)

    documentos = {
        "plan": plan,
        "cuestionario": cuestionario,
        "soa": gen_soa(cat, plan, cuestionario, cuando=CUANDO),
        "vigilancia": reconciliar(alm, sujetos, AHORA, esperados=esperados).a_json(),
        "anexo-v": gen_v(RAIZ / "catalogo" / "ai-act" / "anexo-v.json",
                         Arbol.leer(FIX), cuestionario, CUANDO),
    }
    sueltas = {n: _prosa_suelta(d) for n, d in documentos.items()}
    sueltas = {n: v for n, v in sueltas.items() if v}
    assert sueltas == {}, sueltas


def test_la_lista_de_deuda_en_castellano_explica_cada_campo():
    """El gemelo de la puerta anterior: una lista de excepciones sin motivo
    escrito se convierte en el sitio donde se esconde lo que molesta."""
    for campo, motivo in SOLO_CASTELLANO.items():
        assert len(motivo.split()) >= 4, campo


# --- las cinco capas cruzan la frontera, y con su forma ---------------------

def _valida(nombre_def: str, doc: dict) -> None:
    """Valida contra UNA de las definiciones de capas.json.

    Se valida contra la rama concreta y no contra el `oneOf` del fichero
    entero: `oneOf` diria «encaja en alguna» y lo que hace falta saber es que
    una ejecucion encaja en `ejecucion`. Un contrato que solo dice «es una de
    las cuatro» deja pasar una observacion emitida donde iba una ejecucion.
    """
    entero = _esquema("capas")
    sub = dict(entero["$defs"][nombre_def])
    sub["$defs"] = entero["$defs"]
    jsonschema.validate(doc, sub)


def test_la_ejecucion_del_motor_generico_cumple_el_contrato():
    from actaira_motor.controles.motor import Paquete, correr_paquete
    arbol = Arbol.leer(FIX)
    res, _ = correr_paquete(arbol, Paquete.cargar(RAIZ / "catalogo" / "reglas" / "art12.json"))
    _valida("ejecucion", res.ejecucion.a_json())
    _valida("observacion", res.observacion.a_json())


def test_la_ejecucion_del_articulo_50_tambien():
    from actaira_motor.controles.art50 import Entrada, correr as correr50
    res = correr50(Entrada(RAIZ / "motor" / "tests" / "fixtures" / "repo-con-generacion"),
                   RAIZ / "catalogo" / "reglas" / "art50.json")
    _valida("ejecucion", res.ejecucion.a_json())
    _valida("observacion", res.observacion.a_json())
    if res.suficiencia is not None:
        _valida("suficiencia", res.suficiencia.a_json())


def test_una_observacion_sin_limites_no_pasa_el_contrato():
    """El invariante vive en el tipo Y en el esquema, y comparten la razon.

    Que una observacion sin limites afirma haberlo mirado todo lo sujeta el
    constructor en Python. Al otro lado de la frontera no hay constructor, solo
    JSON, asi que el mismo invariante tiene que estar en el esquema: `minItems`
    en `limites`. Sin eso, la plataforma en Go podria fabricar una observacion
    que el motor nunca habria podido construir.
    """
    doc = {"esquema": "actaira/observacion/v1", "id": "sha256:x",
           "ejecucion_id": "sha256:y", "control_id": "ACT-C-009",
           "hallazgos": [], "senales": [], "limites": []}
    with pytest.raises(jsonschema.ValidationError):
        _valida("observacion", doc)


def test_una_decision_sin_persona_no_pasa_el_contrato():
    doc = {"esquema": "actaira/decision/v1", "id": "sha256:x", "sobre": "sha256:s",
           "requisitos": ["AIA-050"], "quien": "", "cargo": "responsable",
           "cuando": "2027-12-02T10:00:00+00:00", "conclusion": "vale"}
    with pytest.raises(jsonschema.ValidationError):
        _valida("decision", doc)


def test_el_gemelo_una_decision_firmada_si_pasa():
    doc = {"esquema": "actaira/decision/v1", "id": "sha256:x", "sobre": "sha256:s",
           "requisitos": ["AIA-050"], "quien": "Marta Iglesias",
           "cargo": "responsable de IA", "cuando": "2027-12-02T10:00:00+00:00",
           "conclusion": "lo doy por bueno", "firma": None, "clave_publica": None}
    _valida("decision", doc)


def test_el_plan_publica_la_procedencia_de_cada_linea():
    """Sin los identificadores, el plan seria una afirmacion sin de donde sale."""
    plan = gen_plan(cargar(str(RAIZ / "catalogo")), PERFIL, CUANDO, str(FIX),
                    str(RAIZ / "catalogo" / "reglas"))
    jsonschema.validate(plan, _esquema("plan"))
    con_capas = [l for l in plan["lineas"] if l.get("ejecucion_id")]
    assert con_capas, "ninguna linea publica su ejecucion: la procedencia se perdio"
    for l in con_capas:
        assert l["observacion_id"], l["obligacion_id"]
        assert l["ejecucion_id"].startswith("sha256:")


# --- la puerta que encontro el hueco de la fase 20 -------------------------

VERBOS_CON_JSON = {
    "aplicabilidad": (["aplicabilidad", "--alto-riesgo", "si", "--fecha", "2027-12-02"],
                      "actaira/aplicabilidad/v1", "aplicabilidad"),
    "plan": (["plan", "{fix}", "--alto-riesgo", "si", "--fecha", "2027-12-02"],
             "actaira/plan/v1", "plan"),
    "vigilar": (["vigilar", "{fix}", "--alto-riesgo", "si", "--almacen", "{alm}",
                 "--ahora", "2027-12-02T10:00:00+00:00"],
                "actaira/vigilancia/v1", "vigilancia"),
    "preguntar": (["preguntar", "{fix}", "--alto-riesgo", "si", "--fecha", "2027-12-02"],
                  "actaira/cuestionario/v1", "cuestionario"),
    "soa": (["soa", "{fix}", "--alto-riesgo", "si", "--fecha", "2027-12-02"],
            "actaira/soa/v1", "soa"),
    "anexo": (["anexo", "{fix}", "--alto-riesgo", "si", "--fecha", "2027-12-02"],
              "actaira/anexo-iv/v1", "anexo-iv"),
    "noconformidad": (["noconformidad", "listar", "--almacen", "{alm}"],
                      "actaira/noconformidades/v1", "noconformidades"),
    "revision": (["revision", "--almacen", "{alm}"],
                 "actaira/revision-por-la-direccion/v1", None),
    "empujon": (["empujon", "{empujon}", "--almacen", "{alm}"],
                "actaira/decision-de-empujon/v1", "decision-de-empujon"),
    "conectar": (["conectar", "{fix}", "--alto-riesgo", "si", "--fecha", "2027-12-02",
                  "--acepto-que-no-se-puede-repetir"], "actaira/plan/v1", "plan"),
}


@pytest.fixture(scope="module")
def _salidas(tmp_path_factory):
    """Corre CADA verbo con --json una vez y guarda lo que emite."""
    import os
    import subprocess
    import sys

    tmp = tmp_path_factory.mktemp("verbos")
    alm = str(tmp / "ev.jsonl")
    empujon = tmp / "empujon.json"
    empujon.write_text(json.dumps({
        "ref": "refs/heads/main", "after": "a" * 40, "before": "b" * 40,
        "repository": {"clone_url": "https://github.com/x/y.git", "full_name": "x/y"},
        "commits": [{"added": [], "modified": ["docs/a.png"], "removed": []}]}),
        encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(RAIZ / "motor" / "src"),
           "PYTHONIOENCODING": "utf-8"}
    fuera = {}
    for nombre, (args, _, _) in VERBOS_CON_JSON.items():
        concretos = [a.format(fix=str(FIX), alm=alm, empujon=str(empujon)) for a in args]
        r = subprocess.run([sys.executable, "-m", "actaira_motor.cli", *concretos, "--json"],
                           cwd=RAIZ, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        fuera[nombre] = (r.stdout, r.returncode, r.stderr)
    return fuera


def test_todo_verbo_que_emite_json_emite_un_DOCUMENTO(_salidas):
    """El hueco que encontro la API: tres verbos emitian JSON sin `esquema`.

    Uno de ellos -`noconformidad listar`- emitia directamente una lista, que no
    es un documento: no declara version, no se puede extender sin romper a
    quien la lea por posicion, y no tiene sitio donde decir que EJECUTADA no es
    cerrada. La frontera lo rechazaba, que era lo correcto, y nadie lo habia
    notado porque el contrato solo se comprobaba sobre los documentos que YA
    tenian esquema. Una puerta que solo mira donde ya se miro no es una puerta.
    """
    for nombre, (salida, codigo, err) in _salidas.items():
        assert salida.strip(), f"{nombre}: no emitio nada (codigo {codigo}) {err[:120]}"
        doc = json.loads(salida)
        assert isinstance(doc, dict), f"{nombre}: emite una lista, no un documento"
        esperado = VERBOS_CON_JSON[nombre][1]
        assert doc.get("esquema") == esperado, f"{nombre}: esquema={doc.get('esquema')!r}"


def test_y_ese_documento_valida_contra_su_esquema_publicado(_salidas):
    """El gemelo. Declarar una version que nadie comprueba es peor que no
    declararla: da la seguridad sin dar la propiedad."""
    mirados = 0
    for nombre, (salida, _, _) in _salidas.items():
        contrato = VERBOS_CON_JSON[nombre][2]
        if contrato is None:
            continue          # `revision` emite markdown envuelto, no un documento de datos
        _validar(json.loads(salida), contrato)
        mirados += 1
    assert mirados >= 9, mirados


def _sin_notas(x):
    """Lo mismo, sin los campos que EXPLICAN la prohibicion.

    La primera version de esta puerta fallaba porque la unica aparicion de
    «porcentaje» en el plan esta dentro de `nota_de_recuento`, que es la nota
    que lo prohibe. Es el mismo modo de fallo que ya se corrigio en
    `test_ninguna_linea_del_plan_dice_que_la_obligacion_se_cumple`, y merece
    corregirse igual y no relajando la lista: una comprobacion cuyo rojo se
    dispara con la frase que explica la regla no dice nada sobre si la regla se
    cumple, y quien la vea roja la relajara hasta que deje de disparar con la
    culpable tambien.
    """
    if isinstance(x, dict):
        return {k: _sin_notas(v) for k, v in x.items() if not k.startswith("nota")}
    if isinstance(x, list):
        return [_sin_notas(v) for v in x]
    return x


def test_ningun_documento_de_ningun_verbo_afirma_cumplimiento(_salidas):
    """La primera negativa, comprobada sobre TODO lo que sale del motor a la vez
    y no articulo por articulo."""
    import re

    for nombre, (salida, _, _) in _salidas.items():
        texto = json.dumps(_sin_notas(json.loads(salida)), ensure_ascii=False).lower()
        for prohibida in ("porcentaje", "percent", "score", "nota_global",
                          "puntuacion", "confidence", "rating"):
            hallada = re.search(rf"\b{prohibida}\b", texto)
            assert not hallada, (
                f"{nombre}: {prohibida!r} en "
                f"...{texto[max(0, hallada.start() - 80):hallada.end() + 20]}")
        assert not any(isinstance(v, float) for v in _planos(json.loads(salida))), nombre


def _planos(x):
    """Todos los valores hoja de un documento, para buscar un float suelto.

    Un numero con decimales dentro de un documento de cumplimiento es casi
    siempre una proporcion disfrazada, y la primera negativa las prohibe. Los
    recuentos son enteros.
    """
    if isinstance(x, dict):
        for v in x.values():
            yield from _planos(v)
    elif isinstance(x, list):
        for v in x:
            yield from _planos(v)
    else:
        yield x


def test_ningun_estado_que_se_emite_sale_sin_nombre(_salidas):
    """Un estado sin nombre sale en crudo en la pantalla de un cliente ingles.

    Los estados son identificadores y viajan sin traducir, que es correcto:
    traducirlos los inutilizaria para comparar dos documentos. Lo que no puede
    faltar es el vocabulario que dice como se leen, y tiene que publicarlo el
    MOTOR: si lo tuviera la pantalla, el dia que se anada un estado la pantalla
    enseniaria la clave y nadie lo notaria hasta que lo viera un cliente.
    """
    from actaira_motor.vocabulario import sin_nombre

    def estados_de(x):
        if isinstance(x, dict):
            for clave, valor in x.items():
                if clave in ("estado", "situacion", "decision") and isinstance(valor, str):
                    yield valor
                if clave in ("recuento", "recuento_de_requisitos") and isinstance(valor, dict):
                    yield from valor
                yield from estados_de(valor)
        elif isinstance(x, list):
            for v in x:
                yield from estados_de(v)

    for nombre, (salida, _, _) in _salidas.items():
        doc = json.loads(salida)
        huerfanos = sin_nombre(estados_de(doc))
        assert not huerfanos, f"{nombre}: estados sin nombre publicado: {huerfanos}"


def test_y_el_documento_publica_los_que_usa(_salidas):
    """El gemelo: un vocabulario que existe en el motor y no viaja en el
    documento no le sirve a quien lo lee."""
    for nombre in ("plan", "aplicabilidad", "noconformidad"):
        doc = json.loads(_salidas[nombre][0])
        tabla = doc.get("nombres_de_estado")
        assert tabla, f"{nombre}: no publica el vocabulario de sus estados"
        for clave, v in tabla.items():
            assert v["es"] and v["en"], f"{nombre}.{clave}"


def test_el_estado_del_almacen_cumple_su_contrato(tmp_path):
    """El documento que sostiene la unica afirmacion frente a un tercero.

    `almacen verificar` solo sabia imprimir prosa, asi que la plataforma no lo
    podia consumir, ninguna pantalla podia ensenar el estado de la evidencia, y
    el esquema no existia. Se publica ahora, y se valida en los dos casos que
    importan: el almacen que verifica y el que no.
    """
    import json as _json
    import os
    import subprocess
    import sys as _sys
    from datetime import datetime, timezone

    from actaira_motor.evidencia.registro import Registro
    from actaira_motor.vigilancia.almacen import Almacen

    T = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)
    ruta = tmp_path / "ev.jsonl"

    def pedir():
        r = subprocess.run(
            [_sys.executable, "-m", "actaira_motor.cli", "almacen", "verificar",
             "--almacen", str(ruta), "--json"],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONPATH": str(RAIZ / "motor" / "src"),
                 "PYTHONUTF8": "1"})
        return _json.loads(r.stdout)

    # 1. No existe todavia: es el estado normal de un cliente el primer dia.
    d = pedir()
    _validar(d, "almacen")
    assert d["existe"] is False and d["verifica"] is False

    # 2. Con observaciones, verifica y trae cabeza.
    a = Almacen.abrir(str(ruta))
    a.anadir([Registro.nuevo("AIA-009", "ACT-C-009", "sha256:a", T, {"x": 1}, 30)], T)
    d = pedir()
    _validar(d, "almacen")
    assert d["verifica"] is True and d["cabeza"].startswith("sha256:")
    assert d["cabeza_es_la_esperada"] is None, (
        "sin una cabeza anotada FUERA esa comprobacion no se ha hecho, y `null` "
        "no es lo mismo que `true`")

    # 3. Tocado a mano: no verifica, y lo dice.
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    x = _json.loads(lineas[0]); x["registro"]["frescura_dias"] = 9999
    ruta.write_text(_json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")
    d = pedir()
    _validar(d, "almacen")
    assert d["verifica"] is False and d["roturas"]


def test_la_openapi_es_la_que_sale_del_enrutador_y_del_contrato():
    """Una especificacion de API escrita a mano es la deriva en estado puro.

    Nada la compara con nada; el dia que alguien anade una ruta se queda corta,
    y quien la lea escribira un conector contra endpoints que no existen. En
    este mismo arbol acaba de pasar lo equivalente: `BANDERAS` es una tabla a
    mano, quedo corta al anadir cinco rutas, y tres de ellas contestaban 502
    con la puerta en verde.

    Asi que se genera de `VERBOS` -- leido del fuente de Go que compila y sirve
    -- y de los esquemas de `contrato/`, y esta puerta corre el generador en
    modo comprobacion.
    """
    import subprocess
    import sys as _sys

    r = subprocess.run(
        [_sys.executable, str(RAIZ / "herramientas" / "generar_openapi.py"), "--comprobar"],
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr


def test_la_openapi_nombra_todos_los_esquemas_que_devuelve():
    """Una ruta que devuelve un documento sin esquema publicado no sirve.

    El integrador puede llamarla y no puede saber que le va a llegar, que es
    justo lo que una OpenAPI existe para evitar. Se permite que falte -- hay un
    documento cuyo esquema todavia no esta publicado -- pero tiene que verse:
    lo que no se admite es que falte en silencio.
    """
    import json as _json

    d = _json.loads((RAIZ / "contrato" / "openapi.json").read_text(encoding="utf-8"))
    sin_esquema = []
    for ruta, ops in d["paths"].items():
        for metodo, op in ops.items():
            cuerpo = (op.get("responses", {}).get("200", {})
                      .get("content", {}).get("application/json", {}))
            props = cuerpo.get("schema", {}).get("properties", {})
            if "documento" not in props:
                continue          # /salud y /v1/verbos no devuelven un documento
            if "$ref" not in props["documento"]:
                sin_esquema.append(f"{metodo.upper()} {ruta}")

    # Hoy es exactamente uno, y se nombra para que se vea que es una deuda
    # conocida y no un descuido.
    assert sin_esquema == ["GET /v1/clientes/{cliente}/revision"], (
        f"rutas que devuelven un documento sin esquema publicado: {sin_esquema}. "
        f"Si has anadido una, publica su esquema en `contrato/` y anadelo al "
        f"indice; si has publicado el de `revision`, actualiza esta puerta.")
