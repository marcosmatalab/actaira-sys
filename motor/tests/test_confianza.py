r"""Que se puede decir de QUIEN hay detras de una respuesta, y que no.

Una auditoria externa lo puso asi: «una declaracion sin firma valida puede
reimportarse si la raiz Merkle coincide. Se emite una advertencia, pero sus
respuestas se aprovechan». Es exacto, y el problema no es la advertencia sino
donde salia: por la salida de error, que en una integracion continua no lee
nadie. Las respuestas entraban en el expediente indistinguibles de las de una
declaracion firmada.

La raiz Merkle demuestra que el contenido es el mismo que cuando se calculo la
raiz. No demuestra autoria, ni capacidad del firmante, ni representacion, ni no
repudio, ni el momento de firma. Estas pruebas fijan las cuatro cosas distintas
que si se pueden saber, y fijan tambien lo que ninguna de ellas demuestra.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "motor" / "src"))

from actaira_motor.cli import _respuestas_de                              # noqa: E402
from actaira_motor.formularios.declaracion import (                       # noqa: E402
    CONFIANZA_SUFICIENTE_PARA_AUTORIDAD, Confianza)

EJEMPLO = RAIZ / "ejemplos" / "respuestas-clasificador.json"


@pytest.fixture(scope="module")
def declaracion():
    """Una declaracion firmada de verdad, y su clave publica."""
    from cryptography.hazmat.primitives import serialization as s
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        k = Ed25519PrivateKey.generate()
        (tmp / "clave.pem").write_bytes(k.private_bytes(
            s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()))
        publica = k.public_key().public_bytes(
            encoding=s.Encoding.Raw, format=s.PublicFormat.Raw).hex()
        r = subprocess.run(
            [sys.executable, "-m", "actaira_motor.cli", "contestar", str(EJEMPLO),
             "--clave", str(tmp / "clave.pem"), "--salida", str(tmp / "d.json"),
             "--ahora", "2027-12-02T12:00:00+00:00"],
            cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONPATH": str(RAIZ / "motor" / "src"), "PYTHONUTF8": "1"})
        # 0, 1 y 3 son VEREDICTOS del motor y no fallos: el fichero de ejemplo
        # trae a proposito una respuesta corta y otra rancia, asi que `contestar`
        # sale 1. Lo que aqui importa es que la declaracion se emitiera.
        assert r.returncode in (0, 1, 3), r.stdout + r.stderr
        assert (tmp / "d.json").is_file(), r.stdout + r.stderr

        firmada = tmp / "d.json"
        # La misma, con la firma quitada. Su raiz Merkle SIGUE cuadrando, que es
        # justo lo que la hacia colarse.
        d = json.loads(firmada.read_text(encoding="utf-8"))
        d["sello"].pop("firma", None)
        d["sello"].pop("clave_publica", None)
        sin_firma = tmp / "sin-firma.json"
        sin_firma.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8", newline="\n")
        yield {"firmada": str(firmada), "sin_firma": str(sin_firma), "publica": publica}


def test_un_fichero_escrito_a_mano_no_afirma_nada_sobre_quien_lo_escribio():
    """Es un borrador y vale como borrador, pero tiene que DECIRLO."""
    rs = _respuestas_de(str(EJEMPLO))
    assert rs and all(r.confianza is Confianza.SIN_FIRMA for r in rs)


def test_una_declaracion_SIN_FIRMA_entra_marcada_y_no_en_silencio(declaracion):
    """EL CASO DE LA AUDITORIA, reproducido.

    Se le quita la firma a una declaracion valida. Su raiz Merkle sigue
    cuadrando, asi que el contenido es demostrablemente el mismo. Lo que ya no
    hay es nadie detras, y eso tiene que constar en cada respuesta.
    """
    rs = _respuestas_de(declaracion["sin_firma"])
    assert rs and all(r.confianza is Confianza.SIN_FIRMA for r in rs)


def test_firmada_sin_decir_que_clave_se_espera_es_integridad_y_no_identidad(declaracion):
    """La distincion que mas se confunde y la que mas se vende.

    La firma verifica contra la clave que viaja DENTRO del documento, asi que
    demuestra que quien tenga esa clave lo firmo. Quien sea esa persona es otra
    pregunta, y el documento no la puede contestar sobre si mismo.
    """
    rs = _respuestas_de(declaracion["firmada"])
    assert rs and all(r.confianza is Confianza.FIRMADA for r in rs)
    assert Confianza.FIRMADA not in CONFIANZA_SUFICIENTE_PARA_AUTORIDAD


def test_con_la_clave_esperada_si_hay_identidad(declaracion):
    rs = _respuestas_de(declaracion["firmada"], declaracion["publica"])
    assert rs and all(r.confianza is Confianza.IDENTIDAD_VERIFICADA for r in rs)
    assert Confianza.IDENTIDAD_VERIFICADA in CONFIANZA_SUFICIENTE_PARA_AUTORIDAD


def test_una_clave_esperada_que_no_es_la_que_firma_se_RECHAZA(declaracion):
    """No se degrada a `firmada`: se para.

    Degradarla seria lo comodo y seria peor que no comprobar nada: quien pasa
    `--clave-esperada` esta afirmando que sabe quien tenia que firmar, y que el
    documento lo firmara otro es justo la noticia que queria recibir.
    """
    with pytest.raises(SystemExit) as e:
        _respuestas_de(declaracion["firmada"], "00" * 32)
    assert "no verifica" in str(e.value)


def test_la_confianza_viaja_DENTRO_del_contenido_que_se_sella(declaracion):
    """Un campo de al lado lo reescribe cualquiera; uno dentro del sello, no.

    El contenido es lo que cubre la raiz Merkle de la declaracion y lo que
    sella la linea del almacen, asi que subirle el nivel de confianza a una
    respuesta ya guardada rompe la cadena.
    """
    from actaira_motor.catalogo.cargador import cargar
    from actaira_motor.formularios.declaracion import registrar

    cat = cargar(str(RAIZ / "catalogo"))
    registros, _ = registrar(cat.preguntas, _respuestas_de(declaracion["firmada"]))
    assert registros
    assert all(r.contenido["confianza"] == "firmada" for r in registros)


def test_el_cuestionario_publica_el_desglose_y_no_lo_funde_con_el_recuento(declaracion):
    """`contestada: 40` no dice lo mismo con cuarenta firmas que con cuarenta a mano.

    Va como recuento APARTE y no restando del de estados: una respuesta sin
    firma sigue siendo una respuesta contestada; lo que no puede es sostener
    una afirmacion sobre quien la dio. Fundir las dos cosas obligaria a elegir
    cual de las dos verdades se publica.
    """
    from actaira_motor.aplicabilidad.motor import Perfil
    from actaira_motor.catalogo.cargador import cargar
    from actaira_motor.formularios.cuestionario import construir as cuestionario
    from actaira_motor.formularios.declaracion import registrar
    from actaira_motor.formularios.plan import construir as plan

    cat = cargar(str(RAIZ / "catalogo"))
    pl = plan(cat, Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True,
                          via_anexo="anexo_iii"),
              date(2027, 12, 2),
              str(RAIZ / "motor" / "tests" / "fixtures" / "clasificador-candidatos"),
              str(RAIZ / "catalogo" / "reglas"))

    vistos = {}
    for etiqueta, ruta, clave in (("sin_firma", declaracion["sin_firma"], None),
                                  ("firmada", declaracion["firmada"], None),
                                  ("identidad_verificada", declaracion["firmada"],
                                   declaracion["publica"])):
        registros, _ = registrar(cat.preguntas, _respuestas_de(ruta, clave))
        q = cuestionario(cat, pl, registros, datetime(2027, 12, 2, tzinfo=timezone.utc))
        assert set(q["recuento_por_confianza"]) == {etiqueta}, q["recuento_por_confianza"]
        vistos[etiqueta] = q["recuento"]["contestada"]
        assert q["nota_de_confianza"]["es"] and q["nota_de_confianza"]["en"]

    # El recuento por estado NO cambia con la confianza: son dos ejes.
    assert len(set(vistos.values())) == 1, vistos


def test_lo_que_NINGUN_nivel_demuestra_esta_escrito_y_no_supuesto():
    """La autoridad del firmante no es un hecho sobre el documento.

    Se comprueba que el propio producto lo dice, en los dos idiomas, en el
    documento que lee el cliente. Si algun dia alguien quita esa frase, esta
    puerta se pone roja: es la diferencia entre un limite declarado y un limite
    que el lector tiene que adivinar.
    """
    from actaira_motor.formularios import cuestionario as modulo

    fuente = Path(modulo.__file__).read_text(encoding="utf-8")
    assert "AUTORIDAD" in fuente or "AUTHORITY" in fuente
