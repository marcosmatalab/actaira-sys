"""Fase 9: los cuatro articulos comprobables que no tenian paquete.

11 (documentacion tecnica), 13 (instrucciones de uso), 19 (conservacion de los
registros) y 47 (declaracion UE de conformidad). Los cuatro se comprueban sobre
documentos y no sobre codigo, que es una familia distinta y trajo su propio
defecto.
"""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from actaira_motor.aplicabilidad.motor import Perfil
from actaira_motor.catalogo.cargador import cargar
from actaira_motor.controles.modelo import Resultado
from actaira_motor.controles.motor import Arbol, Paquete, correr_paquete
from actaira_motor.formularios.plan import construir as construir_plan

RAIZ = Path(__file__).resolve().parents[2]

FIX = Path("motor/tests/fixtures/clasificador-candidatos")
PERFIL = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii")


@pytest.fixture(scope="module")
def cat():
    return cargar("catalogo")


@pytest.fixture
def documentado(tmp_path):
    """Un repositorio que SI trae sus documentos, para los gemelos."""
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    (repo / "docs").mkdir()
    (repo / "docs" / "ANEXO-IV.md").write_text(
        "# Documentacion tecnica, Anexo IV\n"
        "Version del sistema: 2.4.1 (sha256:aa11bb22)\n"
        "## 2.e Supervision humana\n"
        "Evaluacion de las medidas del articulo 14: tres personas pueden anular.\n"
        "## 9 Vigilancia poscomercializacion\n"
        "Plan del articulo 72: metrica de deriva semanal con umbral y destinatario.\n",
        encoding="utf-8")
    (repo / "docs" / "INSTRUCCIONES-DE-USO.md").write_text(
        "# Instrucciones de uso\n"
        "Proveedor: Cribado Analytics S.L. Contacto: soporte@cribado.example\n"
        "Exactitud: 0.89 de precision y 0.84 de recall sobre el conjunto de 2027.\n"
        "Supervision humana: el revisor puede anular cualquier decision.\n",
        encoding="utf-8")
    (repo / "almacen.yml").write_text("retention_days: 400\n", encoding="utf-8")
    (repo / "DECLARACION-DE-CONFORMIDAD.md").write_text(
        "# Declaracion UE de conformidad\n"
        "Se expide bajo la exclusiva responsabilidad del proveedor.\n"
        "Sevilla, 1 de diciembre de 2027. Marta Iglesias, Directora de Cumplimiento.\n",
        encoding="utf-8")
    return repo


def _correr(repo, art):
    return correr_paquete(Arbol.leer(repo), Paquete.cargar(f"catalogo/reglas/{art}.json"))[0]


@pytest.mark.parametrize("art", ["art11", "art13", "art19", "art47"])
def test_sobre_un_repositorio_desnudo_los_cuatro_encuentran_algo(art):
    res = _correr(FIX, art)
    assert res.resultado is Resultado.CON_HALLAZGOS, art
    assert res.hallazgos, art


@pytest.mark.parametrize("art", ["art11", "art13", "art19", "art47"])
def test_y_el_gemelo_sobre_uno_documentado_no_encuentran_nada(documentado, art):
    """Sin esta mitad, cuatro paquetes que acusaran siempre pasarian igual."""
    res = _correr(documentado, art)
    assert res.hallazgos == (), (art, [h.regla_id for h in res.hallazgos])


def test_un_documento_que_falta_produce_UN_hallazgo_y_no_tres(tmp_path):
    """El defecto de la pasada: la ausencia de la declaracion producia tres
    hallazgos -- no existe, no dice responsabilidad exclusiva, sigue en
    borrador -- que son el mismo defecto contado tres veces. Un informe que
    multiplica un problema por sus consecuencias se lee una vez y se ignora a
    la siguiente."""
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    res = _correr(repo, "art47")
    assert [h.regla_id for h in res.hallazgos] == ["ACT-47-DECLARACION"]
    assert any("no hay fichero que mirar" in x for x in res.no_cubre)


def test_pero_si_el_documento_existe_y_esta_mal_si_se_dice(tmp_path):
    """El gemelo: `solo_si_hay_fichero` apaga la regla cuando no hay nada que
    mirar, no cuando lo que hay esta mal."""
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    (repo / "DECLARACION-DE-CONFORMIDAD.md").write_text(
        "# Declaracion UE de conformidad - BORRADOR\n"
        "Se expide bajo la exclusiva responsabilidad del proveedor.\n", encoding="utf-8")
    res = _correr(repo, "art47")
    assert [h.regla_id for h in res.hallazgos] == ["ACT-47-SIGUE-EN-BORRADOR"]


def test_la_retencion_se_encuentra_aunque_la_clave_lleve_guion_bajo(tmp_path):
    """`\\bretention\\b` no casa `retention_days`, porque despues de la palabra
    viene un caracter de palabra. Es el fallo de frontera de toda la vida y
    aqui habria dado un hallazgo falso a todo cliente que use esa clave."""
    repo = tmp_path / "repo"
    shutil.copytree(FIX, repo)
    (repo / "almacen.yml").write_text("retention_days: 400\n", encoding="utf-8")
    res = _correr(repo, "art19")
    assert "ACT-19-RETENCION-DECLARADA" in res.controles_cubiertos


def test_ya_no_queda_ninguna_obligacion_comprobable_sin_paquete(cat):
    """La puerta que cierra la fase: `vigilar` declaraba cuatro en voz alta."""
    from datetime import datetime, timezone
    from actaira_motor.vigilancia.barrido import observar
    _r, _s, _e, sin_paquete = observar(
        cat, PERFIL, date(2027, 12, 2), str(FIX), "catalogo/reglas",
        datetime(2027, 12, 2, tzinfo=timezone.utc))
    assert sin_paquete == []


def test_el_plan_entero_sigue_sin_inventarse_un_cumple(cat, documentado):
    """Ni con todos los documentos en su sitio: un CUMPLE de control no es un
    cumplimiento de obligacion, y el plan no tiene ese estado."""
    plan = construir_plan(cat, PERFIL, date(2027, 12, 2), str(documentado), "catalogo/reglas")
    estados = {l["estado"] for l in plan["lineas"]}
    assert "cumple" not in estados
    assert estados <= {"comprobada", "con_hallazgos", "a_preguntar", "solo_formulario",
                       "futura", "no_ata", "sin_resolver"}


# --- el articulo 5, con las dos prohibiciones del Reglamento (UE) 2026/1744 --

def test_generar_imagen_sin_filtro_dispara(tmp_path):
    """La salvaguarda que el artículo 5 le pide al proveedor, leida en el codigo.

    La intencion no se lee. Las salvaguardas si: un punto de generacion que no
    pasa por ningun filtro antes de devolver la salida es una ausencia
    observable, y es exactamente lo que la modificacion de 2026 le exige al
    proveedor. Lo que este control NO dice es si el sistema esta generando
    contenido prohibido: dice que no hay salvaguarda que ensenar.
    """
    from actaira_motor.controles.motor import Arbol, Paquete, correr_paquete
    from actaira_motor.controles.modelo import Resultado

    (tmp_path / "estudio.py").write_text(
        "from openai import client\n"
        "def retrato(prompt):\n"
        "    return client.images.generate(prompt=prompt)\n", encoding="utf-8")
    pk = Paquete.cargar(RAIZ / "catalogo" / "reglas" / "art05.json")
    res, preguntas = correr_paquete(Arbol.leer(tmp_path), pk)
    assert res.resultado is Resultado.CON_HALLAZGOS
    assert any(h.regla_id == "ACT-05-GEN-SIN-FILTRO" for h in res.hallazgos)
    assert not res.resultado.afirma_cumplimiento


def test_el_gemelo_con_filtro_en_el_mismo_fichero_no_dispara(tmp_path):
    """Y aqui el control se calla, que es la mitad que impide que grite siempre."""
    from actaira_motor.controles.motor import Arbol, Paquete, correr_paquete

    (tmp_path / "estudio.py").write_text(
        "from openai import client\n"
        "def retrato(prompt):\n"
        "    salida = client.images.generate(prompt=prompt)\n"
        "    if client.moderations.create(input=salida).flagged:\n"
        "        return None\n"
        "    return salida\n", encoding="utf-8")
    pk = Paquete.cargar(RAIZ / "catalogo" / "reglas" / "art05.json")
    res, _ = correr_paquete(Arbol.leer(tmp_path), pk)
    assert not any(h.regla_id == "ACT-05-GEN-SIN-FILTRO" for h in res.hallazgos)
    assert any(s.regla_id == "ACT-05-GEN-SIN-FILTRO" for s in res.observacion.senales), \
        "que el filtro esta es una SENAL: si no se publicara, el informe seria el mismo que si no se hubiera mirado"


def test_pero_tener_filtro_no_cierra_el_articulo_5(tmp_path):
    """Lo que este motor puede leer es que el filtro ESTA, no que funcione.

    Si tener una llamada bastara para cerrar el articulo, el producto premiaria
    poner un `if False` delante de la generacion. Las tres preguntas que quedan
    -- que detecta, el consentimiento y la politica de uso -- siguen abiertas.
    """
    from actaira_motor.controles.motor import Arbol, Paquete, correr_paquete

    (tmp_path / "estudio.py").write_text(
        "from openai import client\n"
        "s = client.images.generate(prompt='x')\n"
        "client.moderations.create(input=s)\n", encoding="utf-8")
    pk = Paquete.cargar(RAIZ / "catalogo" / "reglas" / "art05.json")
    _res, preguntas = correr_paquete(Arbol.leer(tmp_path), pk)
    ids = {p.regla_id for p in preguntas}
    assert {"ACT-05-FILTRO-SIN-DESCRIBIR", "ACT-05-CONSENTIMIENTO",
            "ACT-05-INTENCION-DEL-DESPLIEGUE"} <= ids, ids


def test_el_paquete_del_articulo_5_dice_lo_que_no_puede_ver():
    """Un paquete sobre una PROHIBICION que no publicara sus limites seria la
    segunda negativa rota por el sitio mas caro posible."""
    d = json.loads((RAIZ / "catalogo" / "reglas" / "art05.json").read_text(encoding="utf-8"))
    limites = d["lo_que_este_paquete_no_puede_ver"]
    assert "consentimiento" in limites["es"] and "intención" in limites["es"]
    assert limites["en"]
    assert "2026/1744" in d["por_que_este_paquete_existe"]["es"]
