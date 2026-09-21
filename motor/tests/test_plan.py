"""El plan es el producto: que te ata, que se comprobo y que hay que preguntarte."""
from datetime import date
from pathlib import Path
import pytest
from conftest import CATALOGO
from actaira_motor.catalogo.cargador import cargar
from actaira_motor.aplicabilidad.motor import Perfil
from actaira_motor.formularios.plan import construir, indexar_paquetes, ESTADOS

RAIZ = Path(__file__).resolve().parents[2]
REGLAS = RAIZ / "catalogo" / "reglas"
FIX = Path(__file__).parent / "fixtures" / "clasificador-candidatos"
ALTO = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii", es_sector_publico=False,
              provee_modelo_uso_general=False, modelo_con_riesgo_sistemico=False)


@pytest.fixture(scope="module")
def cat():
    return cargar(CATALOGO)


def test_el_indice_de_paquetes_sale_del_contenido_y_no_del_nombre():
    idx = indexar_paquetes(REGLAS)
    assert [r.name for r in idx["AIA-009"]] == ["art09.json"]
    assert all(k.startswith("AIA-") for k in idx)


def test_una_obligacion_puede_tener_varios_analizadores():
    """El articulo 14 se mira en el arbol de ficheros Y en la estructura de
    agentes: son dos sujetos con dos digests y dos invalidaciones.

    Forzarlos al mismo paquete habria obligado a que un cambio en el arsenal
    invalidara la evidencia sobre el codigo, que es justo lo que la
    invalidacion por digest existe para evitar.
    """
    idx = indexar_paquetes(REGLAS)
    nombres = sorted(r.name for r in idx["AIA-014"])
    assert nombres == ["agentes.json", "art14.json"], nombres


def test_pero_dos_paquetes_no_pueden_definir_la_misma_regla(tmp_path):
    """Ahi si habria dos definiciones de lo mismo, y se anulan (regla 10)."""
    import shutil
    shutil.copy(REGLAS / "art09.json", tmp_path / "uno.json")
    shutil.copy(REGLAS / "art09.json", tmp_path / "dos.json")
    with pytest.raises(ValueError) as e:
        indexar_paquetes(tmp_path)
    assert "ACT-09-UMBRAL" in str(e.value)
    assert "se anulan" in str(e.value)


def test_el_plan_cubre_todas_las_obligaciones_sin_perder_ninguna(cat):
    plan = construir(cat, ALTO, date(2027, 12, 2), FIX, REGLAS)
    assert len(plan["lineas"]) == len(cat.obligaciones)
    assert sum(plan["recuento"].values()) == len(cat.obligaciones)
    assert set(plan["recuento"]) == set(ESTADOS)


def test_el_plan_encuentra_hallazgos_y_preguntas_a_la_vez(cat):
    plan = construir(cat, ALTO, date(2027, 12, 2), FIX, REGLAS)
    assert plan["recuento"]["con_hallazgos"] >= 5
    assert plan["total_preguntas"] >= 10


def test_ninguna_linea_del_plan_dice_que_la_obligacion_se_cumple(cat):
    """Una obligacion la cumple una organizacion, no un control.

    La primera version de este test buscaba las palabras prohibidas en el plan
    ENTERO y fallaba, porque las unicas apariciones estaban dentro de
    `nota_de_recuento`, que es la nota que las prohibe. Es el modo de fallo de
    la regla 12: una comprobacion que mira de lado y cuyo rojo, o su verde, no
    dice nada sobre lo que pretende medir. Se acota a las lineas, que es donde
    un agregado indebido apareceria de verdad, y las notas doctrinales quedan
    fuera a proposito y por escrito.
    """
    plan = construir(cat, ALTO, date(2027, 12, 2), FIX, REGLAS)
    import json, re
    texto = json.dumps(plan["lineas"], ensure_ascii=False).lower()
    # Por PALABRA y no por subcadena: la version anterior acusaba a `grade`
    # dentro de `degrada`, que es el mismo error de mirar de lado dos veces
    # seguidas. Una comprobacion que se dispara con una subcadena inocente se
    # relaja hasta que deja de disparar con la culpable.
    for prohibida in ("porcentaje", "percent", "score", "nota_global",
                      "puntuacion", "grade", "confidence", "rating"):
        hallada = re.search(rf"\b{prohibida}\b", texto)
        assert not hallada, f"{prohibida!r} en ...{texto[max(0, hallada.start()-90):hallada.end()+30]}"
    assert not any(isinstance(v, float) for l in plan["lineas"] for v in l.values())


def test_el_gemelo_del_guardia_de_agregados_muerde():
    """Regla 9. Y ademas fija que NO se dispara con `degrada`, que fue el defecto."""
    import re
    assert re.search(r"\bscore\b", 'la "score": 0.9 del modelo')
    assert not re.search(r"\bgrade\b", "un sistema que se degrada en silencio")


def test_el_plan_no_hereda_la_conclusion_entre_marcos(cat):
    plan = construir(cat, ALTO, date(2027, 12, 2), FIX, REGLAS)
    assert "no se hereda" in plan["nota_cruce"]["es"].lower()
    con_iso = [l for l in plan["lineas"] if l["iso42001"]]
    assert len(con_iso) >= 15


def test_sin_repositorio_el_plan_sigue_saliendo_y_lo_dice(cat):
    plan = construir(cat, ALTO, date(2027, 12, 2), None, REGLAS)
    assert plan["recuento"]["con_hallazgos"] == 0
    assert plan["recuento"]["a_preguntar"] + plan["recuento"]["solo_formulario"] > 10


def test_una_pyme_sin_alto_riesgo_tiene_un_plan_corto(cat):
    p = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=False, es_sector_publico=False,
               provee_modelo_uso_general=False, modelo_con_riesgo_sistemico=False)
    plan = construir(cat, p, date(2026, 9, 20), FIX, REGLAS)
    atan = [l for l in plan["lineas"] if l["estado"] not in ("no_ata", "futura")]
    # La propiedad, no el numero: el numero cambia cada vez que el catalogo
    # crece y entonces el test mide el tamano del catalogo en vez de medir que
    # a una pyme sin alto riesgo NO le caen las obligaciones del alto riesgo.
    articulos = {l["articulo"] for l in atan}
    alto_riesgo = {"9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
                   "20", "21", "22", "23", "24", "25", "26", "27", "43", "47", "49",
                   "72", "73"}
    assert not (articulos & alto_riesgo), sorted(articulos & alto_riesgo)
    assert "5" in articulos, "las practicas prohibidas atan a todo el mundo"
    assert "50" in articulos, "la transparencia del articulo 50 tambien"
    assert len(atan) < 10, sorted(articulos)


def test_el_estado_comprobada_es_alcanzable(cat, tmp_path):
    """La pasada adversarial pregunto si sobraba. No sobra: hay un paquete sin preguntas."""
    (tmp_path / "telemetria.py").write_text(
        "from opentelemetry import metrics\n"
        "DRIFT_UMBRAL = 0.1\n"
        "def alerta_si_supera_umbral(v):\n"
        "    if v > DRIFT_UMBRAL: notify_suspend(v)\n")
    (tmp_path / "monitoring.py").write_text("def observar(): pass\n")
    (tmp_path / "drift_deriva.py").write_text("def psi_por_ventana(): pass\n")
    plan = construir(cat, ALTO, date(2027, 12, 2), tmp_path, REGLAS)
    a72 = [l for l in plan["lineas"] if l["articulo"] == "72"][0]
    assert a72["preguntas"] == [], "art. 72 es el paquete sin preguntas y por eso puede cerrarse solo"
    assert plan["recuento"]["comprobada"] >= 1
