"""Construye la portada en los SEIS idiomas, con las cifras sacadas del arbol.

    make portada

QUE CAMBIO Y POR QUE
---------------------
Antes esto reescribia los huecos de cifra DENTRO de `index.html`, que era un
fichero a mano. Funcionaba para las cifras y dejaba fuera lo demas: la portada
era la unica superficie del producto que solo existia en castellano, mientras
el panel y la consola llevaban dos idiomas desde su primera version. Un
producto que promete «expediente listo para enseñar, en español y en inglés»
y cuya propia portada no esta en ingles se contradice en la primera pantalla.

Asi que la pagina se arma de tres piezas, como las otras dos:

  plantilla/pagina.html   la estructura, con `__T:clave__` por cada texto
  textos.json             los idiomas
  cifras.py               los numeros, sacados del catalogo y del arbol

SEIS PAGINAS, NO UN CONMUTADOR DE JAVASCRIPT
----------------------------------------------
Cada idioma es un fichero de verdad con su `lang` y su direccion, y las seis
enlazan entre si. Un conmutador que reescribe el texto en el navegador habria
sido menos codigo y habria dado una pagina que no se puede enviar por correo,
que los buscadores indexan en un solo idioma, y que un lector de pantalla
pronuncia con el idioma equivocado hasta que alguien pulsa algo.

LAS TRADUCCIONES ESTAN ESCRITAS, NO GENERADAS
-----------------------------------------------
Y hay frases que NO se traducen literalmente porque literalmente no dicen lo
mismo. `INDETERMINADO` y `NO_CUMPLE` se quedan en castellano en los seis
idiomas: son valores que el motor emite, no prosa, y traducirlos los
inutilizaria para comparar dos documentos. Es la misma decision que tomo el
panel en D-83. Los identificadores de regla -- `ACT-09-UMBRAL` y familia -- y
los nombres de los verbos tampoco se tocan, por lo mismo.

LAS CIFRAS SIGUEN SIN ESCRIBIRSE A MANO
-----------------------------------------
`test_portada.py` recalcula cada numero de `index.html` desde el catalogo y
desde el arbol, y falla si no coincide. Correr esto no es una manera de
saltarse esa puerta: es la manera de satisfacerla.
"""
from __future__ import annotations

import html as _html
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SITIO = RAIZ / "sitio"
sys.path.insert(0, str(SITIO))
sys.path.insert(0, str(RAIZ / "herramientas"))
from cifras import de  # noqa: E402
from paginas import revisar_estructura, revisar_textos  # noqa: E402

# LOS DOS SITIOS A LOS QUE ESTA PAGINA MANDA A ALGUIEN, ESCRITOS UNA VEZ.
#
# La portada no tenia NI UN enlace externo: ni al repositorio -- con todo el
# argumento del producto siendo «el motor es el mismo fichero que puedes
# leer» -- ni a la licencia, ni a nadie. La seccion se titulaba «Cómo se paga»
# y no habia ni un boton en las tres tarjetas. Un visitante que quisiera
# empezar tenia que volver a subir y buscar el bloque de ordenes a mano.
REPO = "https://github.com/marcosmatalab/actaira-sys"

# EL CORREO, EN UNA SOLA LINEA.
#
# Estuvo supuesto (`hola@`) mientras la decision era «un correo en actaira.com»
# sin concretar cual, y la suposicion se decia aqui en vez de disimularse. Ya
# esta concretado.
#
# Sigue viviendo en UNA linea a proposito: cambiarlo es cambiar esto, y las seis
# paginas se rehacen solas. Escrito a mano en seis ficheros habria seis sitios
# donde queda el viejo.
CORREO = "marcosmata@actaira.com"

# Donde vive cada idioma y como se llama EN SU PROPIA LENGUA.
#
# El castellano manda en la raiz porque es el idioma en el que esta escrito el
# producto entero -- el catalogo, los motivos, el codigo -- y porque
# `test_portada.py` recalcula sus cifras sobre `sitio/index.html`.
IDIOMAS: dict[str, dict] = {
    "es": {"salida": Path("index.html"), "codigo": "ES", "nombre": "Español"},
    "en": {"salida": Path("en/index.html"), "codigo": "EN", "nombre": "English"},
    "fr": {"salida": Path("fr/index.html"), "codigo": "FR", "nombre": "Français"},
    "pt": {"salida": Path("pt/index.html"), "codigo": "PT", "nombre": "Português"},
    "it": {"salida": Path("it/index.html"), "codigo": "IT", "nombre": "Italiano"},
    "de": {"salida": Path("de/index.html"), "codigo": "DE", "nombre": "Deutsch"},
}


def _href(desde: str, hacia: str) -> str:
    """La direccion relativa de un idioma visto desde otro.

    Se calcula y no se escribe: escribirla eran treinta pares a mano, y el dia
    que se anade un idioma hay que acordarse de los seis que ya estaban.
    """
    if desde == hacia:
        return "./"
    subir = "./" if desde == "es" else "../"
    return subir if hacia == "es" else f"{subir}{hacia}/"


def _conmutador(idioma: str) -> str:
    """Los seis enlaces. `aria-current` dice cual estas leyendo a quien no ve el color."""
    fuera = []
    for otro, conf in IDIOMAS.items():
        actual = ' aria-current="page"' if otro == idioma else ""
        fuera.append(
            f'<a href="{_href(idioma, otro)}" hreflang="{otro}" lang="{otro}"'
            f'{actual} title="{_html.escape(conf["nombre"])}">{conf["codigo"]}</a>')
    return "".join(fuera)


def construir(idioma: str, textos: dict, valores: dict[str, str]) -> str:
    conf = IDIOMAS[idioma]
    plantilla = (SITIO / "plantilla" / "pagina.html").read_text(encoding="utf-8")

    def pon(m: re.Match) -> str:
        k = m.group(1)
        if k not in textos[idioma]:
            raise SystemExit(f"la plantilla pide {k!r} y {idioma} no lo tiene")
        return textos[idioma][k]

    html = re.sub(r"__T:([a-z0-9_]+)__", pon, plantilla)
    html = (html
            .replace("__LANG__", idioma)
            .replace("__IDIOMAS__", _conmutador(idioma))
            .replace("__REPO__", REPO)
            .replace("__CORREO__", CORREO))

    # LAS CIFRAS SE INYECTAN POR CLAVE, NO POR ETIQUETA.
    #
    # Antes se buscaba el texto de la etiqueta dentro del HTML ya construido.
    # Eso funcionaba mientras hubo una sola pagina y se rompio en silencio con
    # la segunda: traducida la etiqueta, ya no casa con la clave que devuelve
    # `cifras.de()`, y la cifra se quedaba con el valor de la plantilla. Por
    # clave no hay nada que adivinar, y con seis idiomas eso deja de ser una
    # comodidad.
    def cifra(m: re.Match) -> str:
        k = m.group(1)
        if k not in valores:
            raise SystemExit(f"la plantilla pide la cifra {k!r} y el arbol no la da. "
                             f"Las que hay: {sorted(valores)}")
        return valores[k]

    html = re.sub(r"__C:([^_]+(?:_[^_]+)*)__", cifra, html)

    # Un hueco sin rellenar sale a la pagina como `__ALGO__` y nadie lo mira.
    sobran = sorted(set(re.findall(r"__[A-Z][A-Z_]*__", html)))
    if sobran:
        raise SystemExit(f"quedan huecos sin rellenar en {idioma}: {sobran}")

    revisar_estructura(html, f"sitio/{conf['salida'].as_posix()}")
    return html


def main() -> int:
    textos = json.loads((SITIO / "textos.json").read_text(encoding="utf-8"))
    revisar_textos(textos)
    faltan = [i for i in IDIOMAS if i not in textos]
    if faltan:
        raise SystemExit(f"`textos.json` no trae {faltan}")

    for idioma in IDIOMAS:
        # `cifras.de()` sabe en que idioma se le pide: la unica palabra que
        # viaja dentro de una cifra -- «superados» -- sale de ahi.
        html = construir(idioma, textos, de(RAIZ, idioma))
        destino = SITIO / IDIOMAS[idioma]["salida"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8", newline="\n")
        print(f"  sitio/{IDIOMAS[idioma]['salida'].as_posix()}: "
              f"{len(html) // 1024} KB, lang={idioma}")
    print(f"  {len(textos['es'])} textos en {len(IDIOMAS)} idiomas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
