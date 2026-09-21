r"""Precalcula los logos incrustados. Se corre A MANO, no al construir.

POR QUE NO SE HACE AL CONSTRUIR, QUE ES DONDE ESTABA
-----------------------------------------------------
`consola/construir.py` y `panel/construir.py` tenian cada uno una funcion
`_logo` que abria el PNG con Pillow, lo reescalaba y lo volvia a comprimir en
cada construccion. Su docstring prometia que la pagina «produce el mismo byte
en cualquier maquina». No lo hacia:

  - La salida de `Image.save(..., "PNG", optimize=True)` depende de la version
    de Pillow y de la de zlib que lleve debajo. Dos maquinas sanas daban dos
    base64 distintos y por tanto dos `consola.html` distintos.
  - La puerta `test_la_construccion_es_reproducible` comparaba el HTML del
    arbol con el recien construido, asi que fallaba en cualquier maquina cuya
    Pillow no fuera la del que hizo el ultimo `make consola`. Es justo el
    criterio de aceptacion «todas las pruebas verdes desde una instalacion
    limpia», y no se cumplia.
  - Y el mismo docstring prometia que construir «no necesita nada instalado»,
    cuando exigia Pillow.

La correccion no es fijar la version de Pillow -- eso traslada el problema al
que instale el paquete manana -- sino sacar la compresion del camino de
construccion. El reescalado se hace UNA vez, su resultado se versiona como
dato, y construir pasa a ser lo que decia ser: una funcion pura de ficheros
del arbol, sin dependencias binarias.

LO QUE IMPIDE QUE EL DATO SE QUEDE VIEJO
-----------------------------------------
Un artefacto precalculado que nadie vigila es un artefacto que envejece en
silencio: alguien cambia el logo, olvida regenerar, y la pagina sigue
ensenando el anterior sin que ninguna prueba se queje. Por eso
`incrustados.json` guarda ademas el sha256 del PNG de origen, y
`test_portabilidad` compara ese sha con el fichero que hay en disco. Cambiar el
logo sin regenerar deja la suite en rojo, con el nombre del fichero delante.

USO:  python consola/marca/incrustar.py     (requiere Pillow; solo aqui)
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

MARCA = Path(__file__).resolve().parent
LOGOS = ("actaira-lockup.png", "actaira-lockup-white.png")
ANCHO = 900
DESTINO = MARCA / "incrustados.json"


def incrustar() -> dict:
    from PIL import Image

    salida: dict = {"ancho": ANCHO, "logos": {}}
    for nombre in LOGOS:
        crudo = (MARCA / nombre).read_bytes()
        im = Image.open(io.BytesIO(crudo)).convert("RGBA")
        alto = round(im.size[1] * ANCHO / im.size[0])
        im = im.resize((ANCHO, alto), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, "PNG", optimize=True)
        salida["logos"][nombre] = {
            "origen_sha256": hashlib.sha256(crudo).hexdigest(),
            "alto": alto,
            "datauri": "data:image/png;base64," + base64.b64encode(b.getvalue()).decode(),
        }
    return salida


def cargar() -> dict:
    """Lo que leen los dos constructores. Una definicion, dos usuarios.

    Antes habia dos funciones `_logo` identicas, una en cada constructor, y esa
    duplicacion es la que dejaba que el panel y la consola pudieran divergir en
    el reescalado sin que nada lo notara.
    """
    return json.loads(DESTINO.read_text(encoding="utf-8"))


def datauri(nombre: str) -> str:
    d = cargar()
    if nombre not in d["logos"]:
        raise SystemExit(
            f"{DESTINO.name}: no trae {nombre!r}. Corre `python consola/marca/incrustar.py`.")
    return d["logos"][nombre]["datauri"]


if __name__ == "__main__":
    DESTINO.write_text(
        json.dumps(incrustar(), ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    print(f"{DESTINO}: {len(LOGOS)} logos a {ANCHO} px de ancho")
