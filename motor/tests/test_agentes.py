"""Fase 17: las estructuras de agentes como sujeto de control.

El Reglamento de 2024 no habla de agentes. Habla de sistemas de IA, y un agente
con herramientas es un sistema de IA: la diferencia no es juridica, es que su
superficie de riesgo no esta donde el catalogo la busca. Un clasificador
arriesga una prediccion mala. Un agente con una herramienta que escribe
arriesga una prediccion mala QUE ADEMAS ACTUA.

La decision que define este modulo es una NEGATIVA, y estas pruebas la sujetan:
el efecto de una herramienta no se deduce de su nombre.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from actaira_motor.agentes import leer
from actaira_motor.controles.agentes import correr
from actaira_motor.controles.modelo import Resultado

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "motor" / "tests" / "fixtures" / "repo-con-agentes"
REGLAS = RAIZ / "catalogo" / "reglas" / "agentes.json"


# --- la lectura -----------------------------------------------------------

def test_se_leen_las_herramientas_de_las_tres_formas_que_existen():
    a = leer(FIX)
    origenes = {h.origen for h in a.herramientas}
    assert {"mcp", "decorador"} <= origenes, origenes
    assert "ficheros.leer_fichero" in {h.nombre for h in a.herramientas}
    assert "reembolsar" in {h.nombre for h in a.herramientas}


def test_el_efecto_no_se_deduce_del_nombre(tmp_path):
    """`obtener_factura` emite una factura. Ese es todo el argumento.

    Clasificar por el nombre es lo que hace todo el mundo porque se pinta un
    panel en una tarde, y se equivoca en cuanto alguien nombra mal una
    herramienta, que es siempre.
    """
    (tmp_path / "a.py").write_text(
        "from marco import tool\n"
        "@tool\n"
        "def obtener_factura(n):\n"
        "    return emitir(n)\n"
        "@tool\n"
        "def borrar_todo():\n"
        "    pass\n", encoding="utf-8")
    a = leer(tmp_path)
    # Las dos salen igual: sin declarar. Ni la que suena a lectura se toma por
    # inofensiva ni la que suena a destruccion se toma por destructiva.
    assert {h.efecto for h in a.herramientas} == {"sin_declarar"}


def test_el_gemelo_una_herramienta_que_declara_su_efecto_se_reconoce(tmp_path):
    """Si no, «nunca declarado» se cumpliria no reconociendo nada nunca."""
    (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {"s": {"tools": [
        {"name": "leer", "annotations": {"readOnlyHint": True}},
        {"name": "escribir"}]}}}), encoding="utf-8")
    a = leer(tmp_path)
    por_nombre = {h.nombre: h for h in a.herramientas}
    assert por_nombre["s.leer"].efecto == "declarado"
    assert por_nombre["s.escribir"].efecto == "sin_declarar"
    assert "readOnlyHint" in por_nombre["s.leer"].anotaciones


def test_una_herramienta_declarada_y_luego_referenciada_no_cuenta_dos_veces(tmp_path):
    """La misma herramienta sale donde se define y donde se pasa en `tools=[]`.

    La segunda es una REFERENCIA, no una declaracion, y contarla aparte hacia
    que una herramienta perfectamente declarada apareciera tambien en la lista
    de las que no lo estan.
    """
    (tmp_path / "a.py").write_text(
        "from marco import tool\n"
        "from openai import client\n"
        "@tool(requires_approval=True)\n"
        "def pagar(x):\n"
        "    pass\n"
        "client.chat.completions.create(messages=[], tools=[pagar])\n", encoding="utf-8")
    a = leer(tmp_path)
    assert [h.nombre for h in a.herramientas] == ["pagar"]
    assert a.herramientas[0].efecto == "declarado"
    assert a.sin_declarar == []


def test_el_sujeto_es_el_arsenal_y_no_el_repositorio(tmp_path):
    """Anadir una herramienta invalida la evidencia sobre las herramientas.
    Tocar el README, no. Eso es lo que hace util la invalidacion."""
    import shutil

    copia = tmp_path / "repo"
    shutil.copytree(FIX, copia)
    antes = leer(copia).digest()

    (copia / "LEEME.md").write_text("da igual lo que ponga\n", encoding="utf-8")
    assert leer(copia).digest() == antes, "tocar prosa no cambia el arsenal"

    (copia / "otra.py").write_text(
        "from marco import tool\n@tool\ndef nueva():\n    pass\n", encoding="utf-8")
    assert leer(copia).digest() != antes, "anadir una herramienta SI cambia el sujeto"


# --- el control -----------------------------------------------------------

def test_el_hallazgo_no_es_que_sea_peligrosa_sino_que_no_consta():
    r = correr(FIX, REGLAS)
    assert r.resultado is Resultado.CON_HALLAZGOS
    ids = {h.regla_id for h in r.hallazgos}
    assert "ACT-AG-EFECTO-SIN-DECLARAR" in ids
    assert r.ejecucion.sujeto.tipo == "estructura-de-agentes"
    # Y lo que SI declara su efecto sale como senal, que es la otra mitad.
    assert any(s.regla_id == "ACT-AG-EFECTO-SIN-DECLARAR" for s in r.observacion.senales)


def test_un_servidor_conectado_sin_enumerar_su_arsenal_es_un_hallazgo():
    """Y este motor NO se inventa la lista: registrar el servidor y decir que
    no se conoce su arsenal es mas honesto que adivinarlo."""
    r = correr(FIX, REGLAS)
    assert any(h.regla_id == "ACT-AG-SERVIDOR-SIN-INVENTARIO" and h.localizacion == "facturacion"
               for h in r.hallazgos)
    assert any("no se inventan" in l.que["es"] for l in r.observacion.limites)


def test_delegacion_sin_tope_de_pasos_dispara_y_con_tope_no(tmp_path):
    base = ("from marco import Agent\n"
            "def escalar(c):\n"
            "    return Agent(nombre='hijo').run(c)\n")
    (tmp_path / "a.py").write_text(base, encoding="utf-8")
    sin = correr(tmp_path, REGLAS)
    assert any(h.regla_id == "ACT-AG-DELEGACION-SIN-TOPE" for h in sin.hallazgos)

    (tmp_path / "a.py").write_text(
        "from marco import Agent\n"
        "def escalar(c):\n"
        "    return Agent(nombre='hijo', max_steps=4).run(c)\n", encoding="utf-8")
    con = correr(tmp_path, REGLAS)
    assert not any(h.regla_id == "ACT-AG-DELEGACION-SIN-TOPE" for h in con.hallazgos)


def test_un_limite_de_gasto_no_acota_una_recursion(tmp_path):
    """Un limite de gasto no para un bucle: lo encarece. El tope tiene que ser
    de PASOS, y la regla mira eso y no «que haya algun limite»."""
    (tmp_path / "a.py").write_text(
        "from marco import Agent\n"
        "def escalar(c):\n"
        "    return Agent(nombre='hijo', max_cost=10).run(c)\n", encoding="utf-8")
    r = correr(tmp_path, REGLAS)
    assert any(h.regla_id == "ACT-AG-DELEGACION-SIN-TOPE" for h in r.hallazgos)
    assert not any(h.regla_id == "ACT-AG-SIN-LIMITES" for h in r.hallazgos)


def test_sin_estructura_de_agentes_dice_que_no_vio_ninguna_de_las_que_sabe_ver(tmp_path):
    """No es «no hay agentes»: es que no se encontro ninguna de las formas que
    este lector conoce. La primera seria una conclusion y la segunda un limite.
    """
    (tmp_path / "x.py").write_text("y = 1\n", encoding="utf-8")
    r = correr(tmp_path, REGLAS)
    assert r.resultado is Resultado.NO_APLICA
    assert r.ejecucion.estado.value == "no_aplicable"
    assert "no significa que no haya agentes" in r.ejecucion.motivo["es"]
    assert r.ejecucion.motivo["en"]


def test_el_control_publica_lo_que_no_puede_ver():
    """Cuatro limites, y los cuatro son los que de verdad importan en un agente."""
    r = correr(FIX, REGLAS)
    textos = " ".join(l.que["es"] for l in r.observacion.limites)
    for trozo in ("hace lo que declara", "se respeta en ejecución",
                  "encadena dos herramientas", "hereda los permisos"):
        assert trozo in textos, trozo


def test_el_control_de_agentes_nunca_afirma_cumplimiento():
    for repo in (FIX,):
        r = correr(repo, REGLAS)
        assert not r.resultado.afirma_cumplimiento
        if r.suficiencia:
            assert not r.suficiencia.estado.afirma_cumplimiento


def test_sin_hallazgos_el_agente_sigue_teniendo_tres_preguntas_abiertas(tmp_path):
    """Declararlo todo no cierra el articulo 14: la aprobacion, el registro de
    llamadas y el contenido externo que dirige la siguiente accion no se leen
    en el codigo."""
    (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {"s": {"tools": [
        {"name": "leer", "annotations": {"readOnlyHint": True}}]}}}), encoding="utf-8")
    (tmp_path / "a.py").write_text(
        "from openai import client\n"
        "client.chat.completions.create(messages=[], max_steps=5)\n", encoding="utf-8")
    r = correr(tmp_path, REGLAS)
    assert r.resultado is not Resultado.CON_HALLAZGOS
    assert r.suficiencia.estado.value == "insuficiente"
    ids = {f.que["es"][:30] for f in r.suficiencia.falta}
    assert len(ids) == 3, ids


# --- la pasada adversarial de la fase 17 ----------------------------------

def test_adv_un_marco_de_agentes_sin_inventario_legible_no_es_no_aplica(tmp_path):
    """El caso peligroso era el silencioso.

    Un repositorio que declara `crewai` y registra sus herramientas en un bucle
    no produce ninguna lectura, y salia NO_APLICABLE igual que uno que no tiene
    agentes. «No lo se ver» y «no hay» piden cosas distintas: la primera pide
    que alguien lo declare a mano, la segunda no pide nada.
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["crewai>=0.1", "langchain"]\n', encoding="utf-8")
    (tmp_path / "a.py").write_text(
        "HERRAMIENTAS = ['pagar', 'borrar']\n"
        "for h in HERRAMIENTAS:\n"
        "    registrar(h)\n", encoding="utf-8")

    a = leer(tmp_path)
    assert not a.hay_agente
    assert a.indicios_sin_lectura
    assert "crewai" in a.marcos_declarados

    r = correr(tmp_path, REGLAS)
    assert r.resultado is not Resultado.NO_APLICA
    assert r.suficiencia.estado.value == "indeterminada"
    assert "crewai" in r.suficiencia.falta[0].que["es"]
    assert r.suficiencia.falta[0].que_hacer["en"]


def test_adv_el_gemelo_sin_marco_ni_herramientas_si_es_no_aplica(tmp_path):
    """Si no, «no aplica» dejaria de existir y todo repositorio del mundo
    tendria una suficiencia indeterminada sobre agentes."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["requests"]\n', encoding="utf-8")
    (tmp_path / "a.py").write_text("y = 1\n", encoding="utf-8")
    a = leer(tmp_path)
    assert not a.indicios_sin_lectura
    assert correr(tmp_path, REGLAS).resultado is Resultado.NO_APLICA


def test_adv_y_con_marco_Y_herramientas_legibles_tampoco_hay_indicio(tmp_path):
    """El indicio es la AUSENCIA de lectura, no la presencia del marco."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["langchain"]\n', encoding="utf-8")
    (tmp_path / "a.py").write_text(
        "from marco import tool\n@tool\ndef leer_algo():\n    pass\n", encoding="utf-8")
    a = leer(tmp_path)
    assert a.marcos_declarados and a.hay_agente
    assert not a.indicios_sin_lectura


def test_adv_mover_una_herramienta_de_fichero_no_invalida_el_arsenal(tmp_path):
    """Si la localizacion entrara en el digest, un refactor invalidaria toda la
    evidencia sobre el arsenal sin que el arsenal cambiara.

    Lo que identifica a la estructura es QUE puede hacer y si consta, no donde
    esta escrito. La localizacion sigue viajando como procedencia.
    """
    (tmp_path / "a.py").write_text(
        "from marco import tool\n@tool\ndef pagar():\n    pass\n", encoding="utf-8")
    antes = leer(tmp_path).digest()

    (tmp_path / "a.py").unlink()
    (tmp_path / "b.py").write_text(
        "from marco import tool\n\n\n@tool\ndef pagar():\n    pass\n", encoding="utf-8")
    assert leer(tmp_path).digest() == antes, "mover no cambia lo que el agente puede hacer"
    assert "b.py" in leer(tmp_path).herramientas[0].localizacion


def test_adv_pero_declarar_su_efecto_SI_cambia_el_sujeto(tmp_path):
    """El gemelo: si nada cambiara el digest, no habria invalidacion ninguna."""
    (tmp_path / "a.py").write_text(
        "from marco import tool\n@tool\ndef pagar():\n    pass\n", encoding="utf-8")
    antes = leer(tmp_path).digest()
    (tmp_path / "a.py").write_text(
        "from marco import tool\n@tool(requires_approval=True)\ndef pagar():\n    pass\n",
        encoding="utf-8")
    assert leer(tmp_path).digest() != antes
