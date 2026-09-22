"""Un motor, y los articulos son datos. Lo que sujeta esa frase."""
import json
from pathlib import Path
import pytest
from actaira_motor.controles.motor import Arbol, Paquete, correr_paquete, EXIGE
from actaira_motor.controles.modelo import Resultado

RAIZ = Path(__file__).resolve().parents[2]
REGLAS = RAIZ / "catalogo" / "reglas"
FIX = Path(__file__).parent / "fixtures" / "clasificador-candidatos"


def _genericos():
    for r in sorted(REGLAS.glob("*.json")):
        pk = Paquete.cargar(r)
        if pk.motor == "generico":
            yield pk


def test_ningun_articulo_esta_nombrado_en_el_codigo_del_motor():
    """Si el motor conociera un articulo por su nombre, los datos no mandarian.

    Se come su propia comida: usa `_codigo_sin_prosa`, que es lo que el motor
    aplica a los ficheros del cliente. La primera version partia el fuente por
    la primera comilla triple, y fallo en cuanto una funcion nueva menciono
    `ACT-12-VERSION` en SU docstring, que es prosa y no codigo. Una comprobacion
    con su propia definicion de que es codigo seria la segunda definicion de la
    misma propiedad, regla 10.
    """
    from actaira_motor.controles.motor import _codigo_sin_prosa
    fuente = (RAIZ / "motor" / "src" / "actaira_motor" / "controles" / "motor.py").read_text(encoding="utf-8")
    cuerpo = _codigo_sin_prosa(fuente)
    for aguja in ("art50", "ACT-09", "ACT-12", "AIA-0", "articulo"):
        assert aguja not in cuerpo, f"el motor generico nombra {aguja!r} en codigo ejecutable"


def test_todo_paquete_carga_y_declara_lo_que_su_tipo_exige():
    paquetes = list(_genericos())
    assert len(paquetes) >= 8
    for pk in paquetes:
        for r in pk.reglas:
            for campo in EXIGE[r.get("tipo", "llamada")]:
                assert campo in r, f"{r['id']} de tipo {r.get('tipo')} sin {campo}"


def test_un_paquete_mal_escrito_revienta_al_cargar_y_no_al_evaluar(tmp_path):
    """Regla 11: el KeyError a mitad de barrido fue un defecto real de la fase 3."""
    mal = tmp_path / "malo.json"
    mal.write_text(json.dumps({"obligacion": "AIA-999", "paquete": "x", "version": "1", "autor": "y",
                               "reglas": [{"id": "R1", "version": "1", "tipo": "llamada",
                                           "severidad": "alta", "que_busca": {"es": "z", "en": "z"},
                                           "titulo": {"es": "a", "en": "b"},
                                           "remediacion": {"es": "a", "en": "b"}}]}))
    with pytest.raises(ValueError) as e:
        Paquete.cargar(mal)
    assert "R1" in str(e.value) and "firmas" in str(e.value)


def test_toda_regla_trae_remediacion_en_los_dos_idiomas():
    for pk in _genericos():
        for r in pk.reglas:
            assert r["remediacion"]["es"].strip() and r["remediacion"]["en"].strip(), r["id"]
            assert r["titulo"]["es"].strip() and r["titulo"]["en"].strip(), r["id"]


def test_toda_regla_aportado_trae_su_pregunta_en_los_dos_idiomas():
    n = 0
    for pk in _genericos():
        for r in pk.reglas:
            if r.get("tipo") == "aportado":
                assert r["pregunta"]["es"].strip() and r["pregunta"]["en"].strip(), r["id"]
                n += 1
    assert n >= 6, "las preguntas al cliente son el puente con el formulario"


def test_el_fixture_del_clasificador_da_hallazgos_reales_y_no_ruido():
    arbol = Arbol.leer(FIX)
    por_obl = {}
    for pk in _genericos():
        res, preg = correr_paquete(arbol, pk)
        por_obl[pk.obligacion] = (res, preg)
    # registra con version de modelo, asi que el 12 no tiene hallazgos
    assert por_obl["AIA-012"][0].resultado is not Resultado.CON_HALLAZGOS
    # tiene aprobacion pero no anulacion ni parada
    ids14 = {h.regla_id for h in por_obl["AIA-014"][0].hallazgos}
    assert ids14 == {"ACT-14-ANULAR", "ACT-14-PARADA"}
    # tiene evals y CI pero no pruebas de inyeccion
    ids15 = {h.regla_id for h in por_obl["AIA-015"][0].hallazgos}
    assert ids15 == {"ACT-15-INYECCION"}


def test_una_regla_sin_pareja_no_dispara_si_no_hay_disparo(tmp_path):
    """Si el repositorio no invoca el modelo, el articulo 12 no le aplica."""
    (tmp_path / "x.py").write_text("def f():\n    return 1\n")
    pk = [p for p in _genericos() if p.obligacion == "AIA-012"][0]
    res, _ = correr_paquete(Arbol.leer(tmp_path), pk)
    assert res.resultado in (Resultado.NO_APLICA, Resultado.CON_HALLAZGOS)
    assert not any(h.regla_id == "ACT-12-SIN-REGISTRO" for h in res.hallazgos)


def test_invocar_sin_registrar_si_dispara(tmp_path):
    """El gemelo del anterior. Regla 9."""
    (tmp_path / "y.py").write_text(
        "import openai\nclient = openai.OpenAI()\n"
        "client.chat.completions.create(model='x', messages=[])\n")
    pk = [p for p in _genericos() if p.obligacion == "AIA-012"][0]
    res, _ = correr_paquete(Arbol.leer(tmp_path), pk)
    assert any(h.regla_id == "ACT-12-SIN-REGISTRO" for h in res.hallazgos)


def test_un_readme_que_dice_que_NO_existe_no_satisface_el_control(tmp_path):
    """D-4 de la pasada adversarial de la fase 3, y era el ataque serio.

    Antes: un README con "NO hay forma de aprobar ni de anular ni kill_switch"
    satisfacia tres de las cinco reglas del articulo 14.
    """
    (tmp_path / "app.py").write_text(
        "import openai\nc = openai.OpenAI()\nc.chat.completions.create(model='x', messages=[])\n")
    (tmp_path / "README.md").write_text(
        "# Sistema\n\nNO hay forma de aprobar ni de anular ni kill_switch. Pendiente.\n")
    pk = [p for p in _genericos() if p.obligacion == "AIA-014"][0]
    res, _ = correr_paquete(Arbol.leer(tmp_path), pk)
    ids = {h.regla_id for h in res.hallazgos}
    assert {"ACT-14-APROBACION", "ACT-14-ANULAR", "ACT-14-PARADA"} <= ids


def test_un_comentario_tampoco_satisface_el_control(tmp_path):
    """El mismo ataque desde dentro del codigo."""
    (tmp_path / "app.py").write_text(
        "import openai\n# TODO: falta anular, kill_switch y aprobar\n"
        "c = openai.OpenAI()\nc.chat.completions.create(model='x', messages=[])\n")
    pk = [p for p in _genericos() if p.obligacion == "AIA-014"][0]
    res, _ = correr_paquete(Arbol.leer(tmp_path), pk)
    ids = {h.regla_id for h in res.hallazgos}
    assert {"ACT-14-APROBACION", "ACT-14-ANULAR", "ACT-14-PARADA"} <= ids


def test_el_gemelo_el_codigo_de_verdad_si_satisface(tmp_path):
    """Regla 9: si las dos de arriba pasaran tambien sin arreglo, no probarian nada."""
    (tmp_path / "app.py").write_text(
        "import openai\n"
        "def aprobar(x, revisor): return {'revisado_por': revisor}\n"
        "def override(x): return None\n"
        "kill_switch = False\n"
        "c = openai.OpenAI()\nc.chat.completions.create(model='x', messages=[])\n")
    pk = [p for p in _genericos() if p.obligacion == "AIA-014"][0]
    res, _ = correr_paquete(Arbol.leer(tmp_path), pk)
    ids = {h.regla_id for h in res.hallazgos}
    assert "ACT-14-APROBACION" not in ids and "ACT-14-PARADA" not in ids


# --- los manifiestos sin extension (arreglo del gemelo 1.e de la fase 4) ---

def test_un_dockerfile_se_lee_aunque_no_tenga_extension(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n# memory: 8Gi\n")
    (tmp_path / "Makefile").write_text("todo:\n\tpytest\n")
    a = Arbol.leer(tmp_path)
    assert "Dockerfile" in a.texto and "Makefile" in a.texto


def test_pero_un_dockerfile_no_entra_en_codigo(tmp_path):
    """El gemelo: si entrara en `codigo`, un comentario suyo satisfaria reglas (D-4)."""
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n# aqui hay un kill_switch\n")
    a = Arbol.leer(tmp_path)
    assert "Dockerfile" not in a.codigo
    assert all("kill_switch" not in v for v in a.codigo.values())


def test_y_un_fichero_sin_extension_que_no_es_de_despliegue_no_se_lee(tmp_path):
    """La lista es cerrada a proposito: LICENSE o CHANGELOG no son manifiestos."""
    (tmp_path / "LICENSE").write_text("Apache 2.0\n")
    a = Arbol.leer(tmp_path)
    assert "LICENSE" not in a.texto and "LICENSE" in a.todos


# --- fase 9: el sexto tipo, `contenido_prohibido` ---------------------------

def _pk_prohibido(tmp_path, patron, ambito="documentacion"):
    import json
    ruta = tmp_path / "pk.json"
    ruta.write_text(json.dumps({
        "paquete": "prueba/prohibido", "version": "1.0.0", "autor": "Prueba",
        "obligacion": "AIA-047",
        "reglas": [{"id": "ACT-X-PROHIBIDO", "version": "1.0.0", "tipo": "contenido_prohibido",
                    "severidad": "alta",
                    "que_busca": {"es": "la palabra prohibida",
                                  "en": "the forbidden word"},
                    "titulo": {"es": "x", "en": "x"},
                    "remediacion": {"es": "quitala", "en": "remove it"},
                    "ambito": ambito, "patrones": [patron]}]}, ensure_ascii=False),
        encoding="utf-8")
    return Paquete.cargar(ruta)


def test_contenido_prohibido_dispara_cuando_el_patron_esta(tmp_path):
    """El simetrico de `contenido`, y hacia falta.

    `contenido` solo sabe exigir presencia. Escribir "esto NO puede aparecer"
    con una expresion regular negativa produce una regla que no dispara nunca
    y que parece que funciona, que es la peor forma de fallar que tiene este
    motor: la primera version de ACT-47-SIGUE-EN-BORRADOR era exactamente eso.
    """
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "DECLARACION.md").write_text("# Declaracion — BORRADOR\n", encoding="utf-8")
    res, _ = correr_paquete(Arbol.leer(repo), _pk_prohibido(tmp_path, r"(?i)\bBORRADOR\b"))
    assert res.resultado is Resultado.CON_HALLAZGOS
    assert res.hallazgos[0].localizacion == "DECLARACION.md"


def test_y_el_gemelo_cuando_no_esta_cubre(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "DECLARACION.md").write_text("# Declaracion, firmada el 2 de diciembre\n", encoding="utf-8")
    res, _ = correr_paquete(Arbol.leer(repo), _pk_prohibido(tmp_path, r"(?i)\bBORRADOR\b"))
    assert res.resultado is Resultado.SIN_HALLAZGOS
    assert "ACT-X-PROHIBIDO" in res.controles_cubiertos
