"""El Anexo IV: cada seccion dice de donde sale, o dice que falta."""
from datetime import date
from pathlib import Path
import pytest
from conftest import CATALOGO
from actaira_motor.catalogo.cargador import cargar
from actaira_motor.aplicabilidad.motor import Perfil
from actaira_motor.controles.motor import Arbol
from actaira_motor.formularios.plan import construir
from actaira_motor.expediente.anexoiv import generar, a_markdown

RAIZ = Path(__file__).resolve().parents[2]
SPEC = RAIZ / "catalogo" / "ai-act" / "anexo-iv.json"
FIX = Path(__file__).parent / "fixtures" / "clasificador-candidatos"
ALTO = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii", es_sector_publico=False,
              provee_modelo_uso_general=False, modelo_con_riesgo_sistemico=False,
              fines_militares=False, solo_investigacion=False, es_codigo_abierto=False)


@pytest.fixture(scope="module")
def anexo():
    cat = cargar(CATALOGO)
    plan = construir(cat, ALTO, date(2027, 12, 2), FIX, RAIZ / "catalogo" / "reglas")
    return generar(SPEC, Arbol.leer(FIX), plan, cuando=date(2026, 9, 20))


def test_estan_los_nueve_puntos_del_anexo(anexo):
    puntos = {s["punto"].split(".")[0] for s in anexo["secciones"]}
    assert puntos == {"1", "2", "3", "4", "5", "6", "7", "8", "9"}


def test_ninguna_seccion_queda_en_blanco_sin_decir_por_que(anexo):
    """La regla del modulo: nunca en blanco y nunca inventada."""
    for s in anexo["secciones"]:
        if s["procedencia"] == "ausente":
            assert s["motivo_ausencia"], s["id"]
            assert s["motivo_ausencia"]["es"].strip() and s["motivo_ausencia"]["en"].strip(), s["id"]
        else:
            assert s["contenido"] or s["aporte_humano"], s["id"]


def test_toda_seccion_derivada_nombra_sus_ficheros(anexo):
    for s in anexo["secciones"]:
        if s["procedencia"].startswith("derivada"):
            assert s["de_donde"], f"{s['id']} dice derivada y no nombra de donde"


def test_las_secciones_derivadas_salen_del_arbol_de_verdad(anexo):
    por_id = {s["id"]: s for s in anexo["secciones"]}
    assert por_id["AIV-1-a"]["contenido"]["version"] == "2.4.1"
    assert por_id["AIV-1-a"]["contenido"]["nombre"] == "cribado-candidatos"
    assert por_id["AIV-1-c"]["contenido"]["total"] == 3
    assert por_id["AIV-1-c"]["contenido"]["fijadas"] == 2, "solo dos estan fijadas con =="
    assert por_id["AIV-2-c"]["contenido"]["modulos"] >= 3


def test_una_seccion_de_control_trae_los_hallazgos_del_plan(anexo):
    por_id = {s["id"]: s for s in anexo["secciones"]}
    a14 = por_id["AIV-2-e"]
    assert a14["procedencia"] == "derivada"
    reglas = {h["regla"] for h in a14["contenido"]["hallazgos"]}
    assert {"ACT-14-ANULAR", "ACT-14-PARADA"} <= reglas


def test_sin_ficha_de_datos_el_punto_2d_dice_exactamente_que_falta(anexo):
    por_id = {s["id"]: s for s in anexo["secciones"]}
    d = por_id["AIV-2-d"]
    assert d["procedencia"] == "ausente"
    assert "ficha" in d["motivo_ausencia"]["es"] and "2.d" in d["motivo_ausencia"]["es"]


def test_un_aporte_humano_va_firmado_y_fechado():
    cat = cargar(CATALOGO)
    plan = construir(cat, ALTO, date(2027, 12, 2), FIX, RAIZ / "catalogo" / "reglas")
    aportes = {"AIV-4": {"texto": "La metrica es F1 sobre la particion de prueba de 2026.",
                         "firmado_por": "Responsable de producto", "fecha": "2026-09-20"}}
    a = generar(SPEC, Arbol.leer(FIX), plan, aportes=aportes, cuando=date(2026, 9, 20))
    s = [x for x in a["secciones"] if x["id"] == "AIV-4"][0]
    assert s["procedencia"] == "aportada"
    assert s["aporte_humano"]["firmado_por"] and s["aporte_humano"]["fecha"]


def test_el_markdown_imprime_la_procedencia_de_todas_las_secciones(anexo):
    for idioma in ("es", "en"):
        md = a_markdown(anexo, idioma)
        assert md.count("## ") == anexo["total_secciones"]
        for s in anexo["secciones"]:
            assert s["titulo"][idioma] in md
    es, en = a_markdown(anexo, "es"), a_markdown(anexo, "en")
    assert "AUSENTE" in es and "MISSING" in en


def test_sin_arbol_todo_sale_ausente_y_no_revienta():
    a = generar(SPEC, None, None, cuando=date(2026, 9, 20))
    assert a["recuento"]["ausente"] == a["total_secciones"]
    assert all(s["motivo_ausencia"] for s in a["secciones"])


def test_el_punto_1e_no_contesta_con_el_corredor_de_la_ci(anexo):
    """D-5 de la pasada adversarial: era plausible y era falso, la peor combinacion."""
    por_id = {s["id"]: s for s in anexo["secciones"]}
    e = por_id["AIV-1-e"]
    assert not any(".github" in f for f in e["de_donde"]), e["de_donde"]
    if e["procedencia"] == "ausente":
        assert "integración continua" in e["motivo_ausencia"]["es"]


def test_el_punto_1e_si_deriva_de_un_manifiesto_de_despliegue(tmp_path):
    """El gemelo: si no derivara nunca, el arreglo habria roto la seccion."""
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n# memory: 8Gi, cpus: 4\n")
    (tmp_path / "app.py").write_text("x = 1\n")
    a = generar(SPEC, Arbol.leer(tmp_path), None, cuando=date(2026, 9, 20))
    e = [s for s in a["secciones"] if s["id"] == "AIV-1-e"][0]
    assert e["procedencia"] == "derivada" and "Dockerfile" in e["de_donde"]


def test_el_punto_2h_no_afirma_medidas_sino_patrones_observados(anexo):
    """D-6: afirmar medidas a partir de una expresion regular es Actaira opinando."""
    por_id = {s["id"]: s for s in anexo["secciones"]}
    h = por_id["AIV-2-h"]
    if h["procedencia"].startswith("derivada"):
        assert "advertencia" in h["contenido"]
        assert "no medidas" in h["contenido"]["advertencia"]["es"]
        assert "patrones" in h["contenido"]


def test_el_markdown_dice_cuando_corta(anexo):
    """D-7: un expediente que pierde contenido sin decirlo no es un expediente."""
    import copy
    g = copy.deepcopy(anexo)
    g["secciones"][0]["contenido"] = {"relleno": ["x" * 80 for _ in range(40)]}
    for idioma, aguja in (("es", "Cortado"), ("en", "Truncated")):
        md = a_markdown(g, idioma)
        assert aguja in md
        assert g["secciones"][0]["id"] in md


def test_el_markdown_no_avisa_de_corte_cuando_no_corta(anexo):
    """El gemelo del anterior."""
    md = a_markdown(anexo, "es")
    assert "Cortado" not in md
