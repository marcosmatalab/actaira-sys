"""La puerta que impide que una prueba saltada parezca una prueba verde.

EL FALLO QUE ESTO CIERRA, Y LO ENCONTRO UNA AUDITORIA AJENA
-------------------------------------------------------------
El auditor corrio la bateria en su maquina y conto 193 pruebas; aqui salian
205. La diferencia entera era `jsonschema`, que no tenia instalado: doce
pruebas del contrato entre el motor y la plataforma se SALTARON, la bateria
dijo «verde», y la unica senal de que el contrato no se habia comprobado era
una linea de resumen que nadie lee.

Una prueba saltada no es una prueba que pasa. Es una afirmacion que nadie
comprobo, contada en la columna de las comprobadas, que es exactamente la
primera negativa de esta casa aplicada a su propia bateria.

COMO SE CIERRA, SIN VOLVERSE INSUFRIBLE
-----------------------------------------
Esta puerta falla, no se salta, y nombra lo que deja de verificarse con cada
ausencia. Quien de verdad quiera correr sin una dependencia lo dice en voz
alta:

    ACTAIRA_SIN_VERIFICAR=node python3 -m pytest motor/tests

y entonces la bateria pasa CON esa renuncia escrita en el mandato que la
lanzo, que es una decision registrada en vez de un silencio.
"""
from __future__ import annotations

import importlib.util
import os
import shutil

import pytest

# Cada dependencia, con lo que se deja de comprobar si no esta. La segunda
# columna es lo unico que hace util a esta puerta: un mensaje que dice
# «falta jsonschema» no mueve a nadie, uno que dice que el contrato entre los
# dos lados del producto no se esta validando, si.
DEPENDENCIAS = {
    "jsonschema": "los seis documentos de la frontera motor-plataforma no se validan "
                  "contra su esquema, que es el unico sitio donde se detecta que un "
                  "lado cambio un campo y el otro no se entero",
    "PIL": "el marcado del articulo 50 no se mide sobre imagenes de verdad: ni la "
           "supervivencia a la cadena de publicacion ni el artefacto sin marcar",
    "yaml": "la plantilla de integracion continua se comprueba como texto y no "
            "como estructura, que es justo la comprobacion que mira de lado",
    "cryptography": "los sellos salen sin firma Ed25519, y lo que se comprueba "
                    "entonces es la raiz Merkle sola: integridad si, identidad no",
}

MANDADOS = {
    "node": "la consola no se construye ni se comprueba en un navegador de verdad, "
            "asi que sus tres vistas quedan sin verificar",
}


def _renunciadas() -> set[str]:
    return {x.strip() for x in os.environ.get("ACTAIRA_SIN_VERIFICAR", "").split(",") if x.strip()}


def test_no_falta_ninguna_dependencia_de_desarrollo():
    renunciadas = _renunciadas()
    faltan = []
    for nombre, consecuencia in DEPENDENCIAS.items():
        if nombre in renunciadas:
            continue
        if importlib.util.find_spec(nombre) is None:
            faltan.append(f"  - {nombre}: {consecuencia}")
    for nombre, consecuencia in MANDADOS.items():
        if nombre in renunciadas:
            continue
        if shutil.which(nombre) is None:
            faltan.append(f"  - {nombre}: {consecuencia}")
    assert not faltan, (
        "esta bateria NO esta comprobando lo que dice comprobar:\n"
        + "\n".join(faltan)
        + "\n\nInstalalo (`pip install -e '.[dev]'`) o renuncia a ello en voz alta con "
          "ACTAIRA_SIN_VERIFICAR=" + ",".join(n for n in list(DEPENDENCIAS) + list(MANDADOS)))


def test_el_gemelo_la_renuncia_se_puede_escribir_y_se_respeta(monkeypatch):
    """La otra mitad: si la puerta no se pudiera abrir, se abriria por la brava.

    Una puerta que no tiene salida termina desactivada entera -- comentada, o
    con un `-k 'not entorno'` metido en el mandato del cron -- y entonces no
    protege nada. Esta tiene salida, y la salida deja rastro.
    """
    monkeypatch.setenv("ACTAIRA_SIN_VERIFICAR", "jsonschema, node")
    assert _renunciadas() == {"jsonschema", "node"}


def test_y_una_renuncia_a_algo_que_no_existe_no_se_traga():
    """Escribir mal el nombre de la renuncia no puede silenciar otra cosa."""
    conocidas = set(DEPENDENCIAS) | set(MANDADOS)
    assert "jsonschema" in conocidas and "node" in conocidas
    assert "sarasa" not in conocidas
