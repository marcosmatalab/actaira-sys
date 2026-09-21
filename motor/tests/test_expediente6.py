"""Fase 6: la declaracion de aplicabilidad y la declaracion UE de conformidad."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from actaira_motor.aplicabilidad.motor import Perfil
from actaira_motor.catalogo.cargador import cargar
from actaira_motor.controles.motor import Arbol
from actaira_motor.expediente.anexov import a_markdown as av_md, generar as gen_v
from actaira_motor.expediente.soa import a_markdown as soa_md, generar as gen_soa
from actaira_motor.formularios.cuestionario import construir as gen_q
from actaira_motor.formularios.declaracion import Respuesta, registrar
from actaira_motor.formularios.plan import construir as gen_plan

FIX = "motor/tests/fixtures/clasificador-candidatos"
SPEC_V = "catalogo/ai-act/anexo-v.json"
CUANDO = date(2027, 12, 2)
AHORA = datetime(2027, 12, 2, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def cat():
    return cargar("catalogo")


@pytest.fixture(scope="module")
def plan(cat):
    return gen_plan(cat, Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii"),
                    CUANDO, FIX, "catalogo/reglas")


def _q(cat, plan, respuestas, ahora=AHORA):
    regs, _ = registrar(cat.preguntas, respuestas)
    return gen_q(cat, plan, regs, ahora, cat.formularios)


def _r(qid, valor, cuando=AHORA - timedelta(days=30), just=None):
    return Respuesta(qid, valor, "Marta Iglesias", "Directora de Cumplimiento", cuando, just)


# --- la declaracion de aplicabilidad ---------------------------------------

def test_la_soa_cubre_los_treinta_y_ocho_controles_del_anexo_a(cat, plan):
    soa = gen_soa(cat, plan, None, cuando=CUANDO)
    assert len(soa["controles"]) == len(cat.controles_iso)


def test_la_soa_incluye_sola_cuando_el_reglamento_lo_trae(cat, plan):
    soa = gen_soa(cat, plan, None, cuando=CUANDO)
    fila = [f for f in soa["controles"] if f["control_id"] == "A.2.2"][0]
    assert fila["incluido"] is True and fila["procedencia"] == "derivada"
    assert "17" in fila["justificacion"]["es"] and "AIA-017" in fila["derivada_de"]


def test_pero_no_excluye_nunca_por_su_cuenta(cat, plan):
    """La asimetria deliberada. Incluir de mas cuesta trabajo; excluir de menos
    cuesta la certificacion."""
    soa = gen_soa(cat, plan, None, cuando=CUANDO)
    assert soa["recuento"]["excluidos"] == 0
    huerfanos = [f for f in soa["controles"] if f["incluido"] is None]
    assert huerfanos and all(f["procedencia"] == "pendiente_de_justificar" for f in huerfanos)


def test_el_gemelo_una_persona_si_puede_excluir_y_queda_su_nombre(cat, plan):
    soa = gen_soa(cat, plan, None, decisiones={"A.5.5": {
        "incluido": False, "justificacion": {"es": "no desarrollamos, solo desplegamos", "en": "deploy only"},
        "quien": "Marta Iglesias", "cargo": "Directora de Cumplimiento", "cuando": "2027-11-30"}},
        cuando=CUANDO)
    fila = [f for f in soa["controles"] if f["control_id"] == "A.5.5"][0]
    assert fila["incluido"] is False and fila["procedencia"] == "aportada"
    assert fila["decidido_por"]["quien"] == "Marta Iglesias"
    assert soa["recuento"]["excluidos"] == 1


def test_una_obligacion_sin_resolver_no_dice_que_ata(cat):
    """Lo que encontro la pasada de la fase 6: el articulo 53 salia justificando
    A.10.3 con un 'ata a este perfil' que nadie habia decidido todavia.

    El plan se construye AQUI y no se toma del fixture: con el catalogo
    completo, un perfil que ya ha contestado casi todo deja pocas obligaciones
    sin resolver, y entonces el caso que esta prueba vigila no aparece. Se
    fabrica a proposito un perfil que solo ha dicho su rol, que es ademas el
    estado en el que esta cualquiera el primer dia.
    """
    apenas = Perfil(roles=frozenset({"proveedor"}))
    plan = gen_plan(cat, apenas, CUANDO, FIX, "catalogo/reglas")
    soa = gen_soa(cat, plan, None, cuando=CUANDO)
    # Se busca la propiedad, no un identificador concreto: A.10.3 dejo de
    # cumplirla al crecer el cruce, y un test atado a un identificador mide
    # el catalogo de un dia en vez de la regla.
    sin_resolver = [f for f in soa["controles"]
                    if f["procedencia"] == "derivada_sin_resolver"]
    assert sin_resolver, "ningun control cuelga solo de una obligacion sin resolver"
    for fila in sin_resolver:
        assert "todavía no se ha contestado" in fila["justificacion"]["es"]
        assert fila["incluido"] is True      # entra igual: quitarlo seria decidir por omision


def test_la_soa_sin_aprobar_lo_dice_en_su_cara(cat, plan):
    soa = gen_soa(cat, plan, None, cuando=CUANDO)
    assert soa["aprobada_por"] is None
    assert "6.1.3" in soa_md(soa, "es")
    assert "borrador" in soa_md(soa, "es")


def test_y_aprobada_lleva_el_nombre_y_el_cargo(cat, plan):
    soa = gen_soa(cat, plan, None, cuando=CUANDO,
                  aprobada_por={"quien": "Marta Iglesias", "cargo": "Directora de Cumplimiento",
                                "cuando": "2027-12-01"})
    md = soa_md(soa, "es")
    assert "Aprobada por" in md and "Marta Iglesias" in md


def test_la_soa_no_emite_ningun_porcentaje(cat, plan):
    soa = gen_soa(cat, plan, None, cuando=CUANDO)
    assert all(isinstance(v, int) for v in soa["recuento"].values())
    assert "%" not in soa_md(soa, "es") and "%" not in soa_md(soa, "en")


def test_la_soa_esta_entera_en_los_dos_idiomas(cat, plan):
    soa = gen_soa(cat, plan, None, cuando=CUANDO)
    for f in soa["controles"]:
        assert set(f["justificacion"]) == {"es", "en"}
    en = soa_md(soa, "en")
    assert "derivada" not in en and "con_hallazgos" not in en and "clausula" not in en


# --- la declaracion UE de conformidad ---------------------------------------

def test_sin_firma_el_documento_sale_marcado_borrador(cat, plan):
    doc = gen_v(SPEC_V, Arbol.leer(FIX), _q(cat, plan, []), CUANDO)
    assert doc["firmado"] is False and doc["aviso"] is not None
    assert "BORRADOR" in av_md(doc, "es") and "DRAFT" in av_md(doc, "en")


def test_con_la_firma_del_punto_8_deja_de_serlo(cat, plan):
    """El gemelo: si nunca se quitara, la marca no significaria nada."""
    q = _q(cat, plan, [_r("F-CNF-4", "Sevilla, 1 de diciembre de 2027. Marta Iglesias, Directora de "
                                     "Cumplimiento, en nombre de Cribado Analytics S.L.")])
    doc = gen_v(SPEC_V, Arbol.leer(FIX), q, CUANDO)
    assert doc["firmado"] is True and doc["aviso"] is None
    assert "BORRADOR" not in av_md(doc, "es")


def test_una_firma_caducada_no_firma(cat, plan):
    """La caducidad llega hasta aqui: una declaracion sostenida por una respuesta
    vieja es el fallo silencioso de todo este sector."""
    vieja = _r("F-CNF-4", "Sevilla, 1 de diciembre de 2025. Marta Iglesias, Directora de "
                          "Cumplimiento, en nombre de Cribado Analytics S.L.",
               cuando=AHORA - timedelta(days=800))
    doc = gen_v(SPEC_V, Arbol.leer(FIX), _q(cat, plan, [vieja]), CUANDO)
    assert doc["firmado"] is False
    p8 = [p for p in doc["puntos"] if p["punto"] == "8"][0]
    assert p8["procedencia"] == "ausente"


def test_el_documento_nunca_dice_que_el_sistema_cumple(cat, plan):
    """Dice que el proveedor DECLARA que cumple, que es lo que dice el articulo
    47 y no es lo mismo. La diferencia entre las dos frases es todo el negocio."""
    q = _q(cat, plan, [_r("F-CNF-4", "x" * 90)])
    md = av_md(gen_v(SPEC_V, Arbol.leer(FIX), q, CUANDO), "es")
    assert "El proveedor declara que" in md
    assert "no es, y no puede ser, una comprobación" in md.lower()


def test_el_punto_5_solo_entra_si_hay_datos_personales(cat, plan):
    no = gen_v(SPEC_V, Arbol.leer(FIX), _q(cat, plan, [_r("F-CNF-1", False)]), CUANDO)
    si = gen_v(SPEC_V, Arbol.leer(FIX), _q(cat, plan, [_r("F-CNF-1", True)]), CUANDO)
    p_no = [p for p in no["puntos"] if p["punto"] == "5"][0]
    p_si = [p for p in si["puntos"] if p["punto"] == "5"][0]
    assert p_no["procedencia"] == "no_procede"
    assert p_si["procedencia"] == "formula" and "2016/679" in p_si["texto"]["es"]


def test_y_sin_contestar_esa_pregunta_tampoco_entra(cat, plan):
    """Entrar por defecto meteria en la declaracion una afirmacion de conformidad
    con el RGPD que nadie ha hecho."""
    doc = gen_v(SPEC_V, Arbol.leer(FIX), _q(cat, plan, []), CUANDO)
    assert [p for p in doc["puntos"] if p["punto"] == "5"][0]["procedencia"] == "no_procede"


def test_el_punto_1_se_deriva_del_repositorio(cat, plan):
    doc = gen_v(SPEC_V, Arbol.leer(FIX), _q(cat, plan, []), CUANDO)
    p1 = [p for p in doc["puntos"] if p["punto"] == "1"][0]
    assert p1["procedencia"] == "derivada" and p1["contenido"]["nombre"] == "cribado-candidatos"


def test_un_punto_aportado_nombra_la_pregunta_que_falta(cat, plan):
    doc = gen_v(SPEC_V, Arbol.leer(FIX), _q(cat, plan, []), CUANDO)
    p2 = [p for p in doc["puntos"] if p["punto"] == "2"][0]
    assert p2["procedencia"] == "ausente" and p2["falta_la_pregunta"] == "F-PRV-2"


# --- la pasada adversarial de la fase 6 -------------------------------------

def test_la_soa_no_dice_que_un_control_de_la_norma_este_comprobado(cat, plan):
    """D-11. La primera version etiquetaba 'comprobada' y 'contestada', que en
    una declaracion de aplicabilidad se lee como 'implantado'. El generador no
    sabe eso: sabe que hay evidencia tecnica de una obligacion que el cruce ata
    a este control, que es bastante menos. Heredar la conclusion es lo que la
    nota de alcance prohibe desde la fase 1, y este modulo la infringio."""
    soa = gen_soa(cat, plan, None, cuando=CUANDO)
    estados = {f["estado_de_implantacion"]["estado"] for f in soa["controles"]}
    assert "comprobada" not in estados and "contestada" not in estados
    assert estados <= {"con_evidencia_tecnica", "con_hallazgos", "con_respuesta_firmada",
                       "sin_evidencia_todavia", "fuera_del_cruce"}
    for i in ("es", "en"):
        assert "nota_de_no_herencia" in soa and soa["nota_de_no_herencia"][i]
        assert soa["nota_de_no_herencia"][i] in soa_md(soa, i)


def test_una_justificacion_humana_con_barras_no_parte_la_tabla(cat, plan):
    """D-12. Una barra vertical o un salto de linea escritos por una persona
    partian la tabla y el documento salia ilegible sin avisar."""
    soa = gen_soa(cat, plan, None, decisiones={"A.5.5": {
        "incluido": False,
        "justificacion": {"es": "no aplica | solo desplegamos\nlo decidio el comite",
                          "en": "n/a | deploy only\ndecided by the committee"},
        "quien": "Marta Iglesias", "cargo": "Directora", "cuando": "2027-11-30"}}, cuando=CUANDO)
    md = soa_md(soa, "es")
    filas = [l for l in md.splitlines() if l.startswith("| `")]
    assert len(filas) == len(soa["controles"])
    assert "\\|" in md


def test_una_respuesta_de_lista_no_sale_como_repr_de_python(cat, plan):
    """D-13. Un `['ISO 24029', 'ISO 5259']` dentro de una declaracion UE de
    conformidad dice a gritos que nadie la leyo antes de firmarla."""
    q = _q(cat, plan, [_r("F-CNF-2", ["EN ISO/IEC 24029-2:2023, aplicada en su totalidad",
                                      "EN ISO/IEC 5259-4, aplicada en parte"])])
    md = av_md(gen_v(SPEC_V, Arbol.leer(FIX), q, CUANDO), "es")
    assert "- EN ISO/IEC 24029-2:2023, aplicada en su totalidad" in md
    assert "['" not in md
