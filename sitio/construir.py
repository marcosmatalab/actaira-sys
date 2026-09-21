"""Escribe en la portada las cifras que salen del arbol. No se editan a mano.

Es el mismo trato que recibio la consola en B-006: lo que se puede derivar del
arbol se deriva, porque un numero escrito a mano envejece en silencio y nadie
mira una pagina de producto con la misma atencion que un test.

    make portada

Reescribe SOLO los huecos de cifra -- `<b>...</b>` junto a su etiqueta -- y no
toca ni una palabra del texto. La puerta de `test_portada.py` comprueba
despues que lo escrito es lo que `cifras.de()` calcula, asi que correr esto no
es una manera de saltarsela: es la manera de satisfacerla.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "sitio"))
from cifras import de  # noqa: E402


def escribir(portada: Path, cifras: dict[str, str]) -> list[str]:
    html = portada.read_text(encoding="utf-8")
    cambios = []

    def bloque(m: re.Match) -> str:
        valor, etiqueta = m.group(1), m.group(2)
        nuevo = cifras.get(etiqueta.strip())
        if nuevo is None or nuevo == valor:
            return m.group(0)
        cambios.append(f"{etiqueta.strip()}: {valor} -> {nuevo}")
        return f"<div><b>{nuevo}</b>{etiqueta}</div>"

    def barra(m: re.Match) -> str:
        etiqueta, valor = m.group(1), m.group(2)
        nuevo = cifras.get(etiqueta.strip())
        if nuevo is None or nuevo == valor:
            return m.group(0)
        cambios.append(f"{etiqueta.strip()}: {valor} -> {nuevo}")
        return f"<span>{etiqueta}</span><b>{nuevo}</b>"

    html = re.sub(r"<div><b>([^<]+)</b>([^<]+)</div>", bloque, html)
    html = re.sub(r"<span>([^<]+)</span><b>([^<]+)</b>", barra, html)
    portada.write_text(html, encoding="utf-8", newline="\n")
    return cambios


if __name__ == "__main__":
    cambios = escribir(RAIZ / "sitio" / "index.html", de(RAIZ))
    print("\n".join("  " + c for c in cambios) if cambios
          else "  la portada ya dice lo que el arbol dice")
