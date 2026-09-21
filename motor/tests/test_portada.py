"""La portada no inventa cifras. Esta puerta existe porque la anterior si lo hacia.

La version previa de actaira.com afirmaba «2.487 tests» y «16 limites
publicados», numeros que no salian de ningun sitio. Una pagina de producto que
inventa una cifra sobre su propia herramienta de cumplimiento es la peor
tarjeta de presentacion posible, y el problema no se arregla corrigiendo la
cifra: se arregla con una puerta que la recalcula.

Cada numero de la portada se saca del catalogo y del arbol, y si no coincide,
esto falla.
"""
from __future__ import annotations

import glob
import json
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTADA = RAIZ / "sitio" / "index.html"


@pytest.fixture(scope="module")
def html():
    return PORTADA.read_text(encoding="utf-8")


def _cifras_de(html: str) -> dict[str, str]:
    """Las cifras destacadas: las de `.facts` y las de las barras."""
    fuera = {}
    for m in re.finditer(r"<div><b>([^<]+)</b>([^<]+)</div>", html):
        fuera[m.group(2).strip()] = m.group(1).strip()
    for m in re.finditer(r"<span>([^<]+)</span><b>([^<]+)</b>", html):
        fuera[m.group(1).strip()] = m.group(2).strip()
    return fuera


def _cifras_calculadas() -> dict[str, str]:
    import importlib.util
    spec = importlib.util.spec_from_file_location("cifras", RAIZ / "sitio" / "cifras.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.de(RAIZ)


def test_las_cifras_de_la_portada_salen_del_arbol(html):
    """Ninguna cifra de la portada se escribe: todas se recalculan aqui."""
    cifras, esperado = _cifras_de(html), _cifras_calculadas()
    for etiqueta, valor in esperado.items():
        assert cifras.get(etiqueta) == valor, (etiqueta, cifras.get(etiqueta), valor)


def test_el_numero_de_pruebas_no_depende_de_lo_que_tenga_instalado_quien_mide(html):
    """La puerta anterior contaba lo que `pytest --collect-only` recogia AQUI.

    El auditor externo, sin `jsonschema`, recogio 193 donde esta casa recogia
    205: doce pruebas del contrato se saltaban y la cifra publicada cambiaba
    con la maquina. Una cifra sobre el producto no puede depender del entorno
    de quien la mide, asi que se cuentan las funciones `test_` leyendo el
    codigo -- ni importa ni ejecuta -- y sale igual en todas partes.

    Y sigue siendo una cota INFERIOR de lo que se recoge de verdad, porque una
    funcion parametrizada se recoge varias veces. La portada nunca dice mas
    pruebas de las que hay.
    """
    import subprocess
    import sys

    dicho = int(_cifras_de(html)["pruebas"])
    assert dicho == int(_cifras_calculadas()["pruebas"])

    # `sys.executable` y no "python3": el nombre `python3` no existe en Windows,
    # asi que esta puerta reventaba con FileNotFoundError en vez de comparar
    # nada. Una puerta que no corre en la maquina del que audita no es una
    # puerta, y ademas garantiza que se mide con el MISMO interprete que corre
    # la suite y no con otro que haya en el PATH.
    salida = subprocess.run([sys.executable, "-m", "pytest", "motor/tests", "-q",
                             "--collect-only"],
                            cwd=RAIZ, capture_output=True, text=True,
                            encoding="utf-8", errors="replace").stdout
    m = re.search(r"(\d+) tests? collected", salida)
    assert m, salida[-400:]
    assert dicho <= int(m.group(1)), \
        f"la portada dice {dicho} y se recogen {m.group(1)}: nunca hacia arriba"


def test_la_medida_de_la_invalidacion_selectiva_es_reproducible(html):
    """Las tres barras se vuelven a medir aqui. No se creen, y ya no se escriben.

    Estaban puestas a mano y se quedaron viejas dos veces: al arreglar la
    invalidacion excesiva (D-14) y al anadir el paquete del articulo 5, que
    sumo un control al denominador sin que nadie tocara la pagina. Ahora las
    escribe `make portada` desde la misma medicion que las comprueba, que es
    una fuente y dos vistas en vez de dos copias (regla 10).
    """
    import re as _re

    esperado = _cifras_calculadas()
    cifras = _cifras_de(html)
    for etiqueta in ("Digest del repositorio entero", "Actaira: digest del sujeto",
                     "Caducidad por nombre de control"):
        assert cifras.get(etiqueta) == esperado[etiqueta], etiqueta

    # Y la afirmacion que las tres barras sostienen: la manera de Actaira supera
    # MENOS que invalidar por el digest del repositorio entero, y MAS que
    # caducar por el nombre del control, que no supera nada nunca. Si algun dia
    # dejara de ser cierta, la comparacion de la portada seria propaganda.
    sup = lambda k: int(_re.match(r"(\d+)", esperado[k]).group(1))
    assert sup("Caducidad por nombre de control") < sup("Actaira: digest del sujeto") \
        < sup("Digest del repositorio entero")
