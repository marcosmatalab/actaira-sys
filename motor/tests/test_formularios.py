"""Fase 5: el cuestionario, la declaracion firmada y la resta que hace el codigo."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from actaira_motor.catalogo.cargador import cargar, controles_declarados
from actaira_motor.evidencia.registro import Estado
from actaira_motor.formularios.cuestionario import construir, pendientes
from actaira_motor.formularios.declaracion import (
    Respuesta, admisible, huella_de_pregunta, registrar)

AHORA = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def cat():
    return cargar("catalogo")


def _resp(qid, valor, quien="Ana Ruiz", cargo="Responsable de IA", cuando=AHORA, just=None):
    return Respuesta(qid, valor, quien, cargo, cuando, just)


# --- el catalogo ------------------------------------------------------------

def test_el_catalogo_de_formularios_no_tiene_roturas(cat):
    assert cat.verificar_formularios(controles_declarados("catalogo/reglas")) == []


def test_toda_clausula_de_la_norma_tiene_quien_la_pregunte(cat):
    """Una clausula sin pregunta es un agujero que nadie ve: el plan la deja en
    `solo_formulario` y el formulario no la pide."""
    servidos = {i for q in cat.preguntas.values() for i in q.sirve_a}
    assert [c.id for c in cat.clausulas.values() if c.id not in servidos] == []


def test_hay_preguntas_que_sirven_a_los_dos_marcos_a_la_vez(cat):
    """El cruce no es decorativo: si ninguna pregunta cerrara las dos cosas, el
    producto seria dos productos."""
    cruzadas = [q.id for q in cat.preguntas.values()
                if any(i.startswith("AIA-") for i in q.sirve_a)
                and any(i.startswith(("ISO-", "A.")) for i in q.sirve_a)]
    assert len(cruzadas) >= 5, cruzadas


# --- admisibilidad ----------------------------------------------------------

def test_una_respuesta_corta_no_admite_y_dice_cuanto_le_falta(cat):
    p = cat.preguntas["F-RSK-1"]
    ok, motivos = admisible(p, "lo tenemos", None)
    assert not ok and "200" in motivos[0]


def test_una_respuesta_suficiente_admite(cat):
    p = cat.preguntas["F-RSK-1"]
    ok, motivos = admisible(p, "x" * 210, None)
    assert ok and motivos == []


def test_la_opcion_excluyente_no_convive_con_las_demas(cat):
    p = cat.preguntas["F-CLS-1"]
    ok, motivos = admisible(p, ["ninguna", "subliminal"], None)
    assert not ok and "excluye" in motivos[0]


def test_una_pregunta_de_intervalo_rechaza_una_respuesta_sin_unidad_de_tiempo(cat):
    p = cat.preguntas["F-SIS-4"]
    malo, _ = admisible(p, "los guardamos en el bucket de auditoria de la region eu-west-1", None)
    bueno, _ = admisible(p, "doce meses en el bucket de auditoria de la region eu-west-1", None)
    assert not malo and bueno


def test_una_respuesta_inadmisible_se_guarda_no_fiable_en_vez_de_perderse(cat):
    p = cat.preguntas["F-RSK-1"]
    reg = _resp("F-RSK-1", "corto").a_registro(p)
    est, motivo = reg.estado(AHORA)
    assert est is Estado.NO_FIABLE and "200" in motivo["es"]


# --- la huella de la pregunta, que es el foso -------------------------------

def test_si_se_reformula_la_pregunta_la_respuesta_anterior_sale_superada(cat):
    p = cat.preguntas["F-RSK-1"]
    reg = _resp("F-RSK-1", "x" * 210).a_registro(p)
    assert reg.estado(AHORA)[0] is Estado.VALIDA

    otra = replace(p, texto={"es": p.texto["es"] + " Detalle la escala.", "en": p.texto["en"]})
    est, motivo = reg.estado(AHORA, digest_actual_del_sujeto=huella_de_pregunta(otra))
    assert est is Estado.SUPERADA and "cambió" in motivo["es"]


def test_pero_mejorar_la_ayuda_no_invalida_ninguna_respuesta(cat):
    """El gemelo. Si la ayuda entrara en la huella, cada mejora de redaccion
    tiraria las respuestas de todos los clientes, y entonces nadie mejoraria
    nunca una redaccion."""
    p = cat.preguntas["F-RSK-1"]
    reg = _resp("F-RSK-1", "x" * 210).a_registro(p)
    otra = replace(p, ayuda={"es": "Texto de ayuda completamente distinto.", "en": "Totally different help."})
    assert reg.estado(AHORA, digest_actual_del_sujeto=huella_de_pregunta(otra))[0] is Estado.VALIDA


def test_una_respuesta_caduca_cuando_pasa_su_vigencia(cat):
    p = cat.preguntas["F-SIS-5"]           # 90 dias
    reg = _resp("F-SIS-5", "x" * 70).a_registro(p)
    assert reg.estado(AHORA + timedelta(days=89))[0] is Estado.VALIDA
    est, motivo = reg.estado(AHORA + timedelta(days=91))
    assert est is Estado.RANCIA and "90" in motivo["es"] and "90" in motivo["en"]


def test_una_respuesta_a_una_pregunta_que_ya_no_existe_se_dice_no_se_tira(cat):
    regs, sueltas = registrar(cat.preguntas, [_resp("F-QUE-NO-EXISTE", "algo")])
    assert regs == [] and "F-QUE-NO-EXISTE" in sueltas[0] and "Ana Ruiz" in sueltas[0]


# --- la resta ---------------------------------------------------------------

def _plan_con(cubre):
    return {"lineas": [{"obligacion_id": "AIA-072", "controles_cubiertos": list(cubre),
                        "cubre": [f"{c}: prosa" for c in cubre]}]}


def test_una_pregunta_desaparece_cuando_un_control_leyo_los_bytes(cat):
    c = construir(cat, _plan_con(["ACT-72-DRIFT", "ACT-15-EVALS"]), [], AHORA)
    q = [x for x in c["preguntas"] if x["id"] == "F-DES-1"][0]
    assert q["estado"] == "la_contesta_el_codigo"
    assert {d["control_id"] for d in q["cubierta_por"]} == {"ACT-72-DRIFT", "ACT-15-EVALS"}
    assert c["ahorro"]["preguntas_que_contesta_el_codigo"] >= 1


def test_el_gemelo_sin_ese_control_la_pregunta_si_se_hace(cat):
    """Si no apareciera nunca, el ahorro no seria una resta sino un agujero."""
    c = construir(cat, _plan_con([]), [], AHORA)
    q = [x for x in c["preguntas"] if x["id"] == "F-DES-1"][0]
    assert q["estado"] == "pendiente"
    assert c["ahorro"]["preguntas_que_contesta_el_codigo"] == 0


def test_el_ahorro_publica_los_controles_que_lo_produjeron(cat):
    c = construir(cat, _plan_con(["ACT-72-DRIFT"]), [], AHORA)
    assert "ACT-72-DRIFT" in c["ahorro"]["porque"]


# --- condicionales ----------------------------------------------------------

def test_una_pregunta_condicional_espera_a_la_que_la_gobierna(cat):
    c = construir(cat, None, [], AHORA)
    q = [x for x in c["preguntas"] if x["id"] == "F-SIS-8"][0]
    assert q["estado"] == "espera_a" and q["depende_de"] == "F-CLS-5"


def test_y_procede_o_no_segun_lo_que_se_contesto(cat):
    con = registrar(cat.preguntas, [_resp("F-CLS-5", ["interaccion"])])[0]
    sin = registrar(cat.preguntas, [_resp("F-CLS-5", ["ninguna"])])[0]
    a = [x for x in construir(cat, None, con, AHORA)["preguntas"] if x["id"] == "F-SIS-8"][0]
    b = [x for x in construir(cat, None, sin, AHORA)["preguntas"] if x["id"] == "F-SIS-8"][0]
    assert a["estado"] == "pendiente" and b["estado"] == "no_procede"


def test_lo_que_espera_no_entra_en_lo_pendiente_y_lo_rancio_si(cat):
    viejo = registrar(cat.preguntas, [_resp("F-SIS-5", "x" * 70, cuando=AHORA - timedelta(days=200))])[0]
    c = construir(cat, None, viejo, AHORA)
    ids = {q["id"] for q in pendientes(c)}
    assert "F-SIS-5" in ids and "F-SIS-8" not in ids


def test_se_puede_pedir_solo_lo_que_le_toca_a_la_direccion(cat):
    c = construir(cat, None, [], AHORA)
    assert {q["destinatario"] for q in pendientes(c, "direccion")} == {"direccion"}


# --- la razon de la pregunta ------------------------------------------------

def test_cada_pregunta_dice_por_que_se_hace_citando_el_catalogo(cat):
    c = construir(cat, None, [], AHORA)
    q = [x for x in c["preguntas"] if x["id"] == "F-LID-3"][0]
    marcos = {p["marco"] for p in q["por_que"]}
    assert marcos == {"ai-act", "iso42001"}
    assert any(p["referencia"]["es"] == "cláusula 5.3" for p in q["por_que"])


def test_y_la_referencia_esta_en_los_dos_idiomas(cat):
    """El gemelo de la fuga de la fase 3: una cadena de idioma formateada en el
    motor no se traduce nunca, y en ingles salia 'por: articulo 16'."""
    c = construir(cat, None, [], AHORA)
    for q in c["preguntas"]:
        for p in q["por_que"]:
            assert set(p["referencia"]) == {"es", "en"}
    q = [x for x in c["preguntas"] if x["id"] == "F-LID-3"][0]
    ens = {p["referencia"]["en"] for p in q["por_que"]}
    assert "clause 5.3" in ens and "Article 16" in ens


def test_el_cuestionario_no_emite_porcentajes(cat):
    """Acotado al cuerpo, no al documento entero.

    La primera version miraba `repr(c)` y tenia que descontar a mano la frase de
    la propia nota que dice que no hay porcentajes. Una puerta que tiene que
    perdonarse a si misma es la puerta que fallo tres veces en las fases
    anteriores (D-3, y la de la consola). Se mira donde de verdad podria
    colarse un numero: las preguntas y los recuentos.
    """
    c = construir(cat, _plan_con(["ACT-72-DRIFT"]), [], AHORA)
    cuerpo = repr({"preguntas": c["preguntas"], "recuento": c["recuento"],
                   "ahorro": {k: v for k, v in c["ahorro"].items() if k != "nota"}})
    assert "%" not in cuerpo
    assert "porcentaje" not in cuerpo and "por ciento" not in cuerpo
    assert all(isinstance(v, int) for v in c["recuento"].values())


# --- la regla 10 sobre las dos vistas de lo cubierto -------------------------

def test_la_prosa_y_los_identificadores_de_lo_cubierto_no_pueden_divergir():
    """Lo que encontro la pasada adversarial de la fase 5.

    El cuestionario leia `cubre`, que es prosa ("ACT-09-GATE: encontrado en
    ci.yml"), y comparaba la frase entera con un identificador. No casaba
    nunca, asi que la resta valia siempre cero: el ahorro era plausible y falso,
    la misma familia de defecto que el D-5 de la fase anterior. El arreglo fue
    publicar los identificadores como dato, desde el mismo `r["id"]` y en el
    mismo instante que la prosa, con esta puerta para que no puedan separarse.
    """
    from actaira_motor.controles.modelo import Resultado, ResultadoControl
    with pytest.raises(ValueError, match="regla 10"):
        ResultadoControl(control_id="ACT-C-09", obligacion_id="AIA-009",
                         resultado=Resultado.SIN_HALLAZGOS, cubre=("otra cosa",),
                         no_cubre=(), controles_cubiertos=("ACT-09-GATE",))


def test_y_el_gemelo_cuando_si_la_explica_no_protesta():
    from actaira_motor.controles.modelo import Resultado, ResultadoControl
    r = ResultadoControl(control_id="ACT-C-09", obligacion_id="AIA-009",
                         resultado=Resultado.SIN_HALLAZGOS, cubre=("ACT-09-GATE: encontrado en ci.yml",),
                         no_cubre=(), controles_cubiertos=("ACT-09-GATE",))
    assert r.controles_cubiertos == ("ACT-09-GATE",)


def test_sobre_el_repositorio_de_ejemplo_la_resta_de_verdad_resta(cat):
    """La puerta de extremo a extremo: con el plan real, alguna pregunta cae.

    Sin este test el arreglo anterior podria volver a romperse en el camino
    entre el motor y el cuestionario sin que nadie se entere, que es justo lo
    que paso.
    """
    from datetime import date as _date
    from actaira_motor.aplicabilidad.motor import Perfil
    from actaira_motor.formularios.plan import construir as construir_plan
    plan = construir_plan(cat, Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii"),
                          _date(2027, 12, 2), "motor/tests/fixtures/clasificador-candidatos",
                          "catalogo/reglas")
    q = construir(cat, plan, [], AHORA)
    assert q["ahorro"]["preguntas_que_contesta_el_codigo"] >= 1
    assert "ACT-09-GATE" in q["ahorro"]["porque"]
