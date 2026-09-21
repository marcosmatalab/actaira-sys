"""Construye `consola.html` desde sus piezas. Cierra B-006.

POR QUE ESTO EXISTE, Y ES DEUDA QUE SE PAGO TARDE
--------------------------------------------------
La consola de la fase 1 se escribio con un guion de una sola vez que no quedo en
el arbol, asi que la pagina no era regenerable: sus datos si, por `make consola`,
pero su JavaScript y sus textos se editaban a mano sobre un fichero de 153 KB con
los logos incrustados. Es exactamente la clase de deuda que esta fase ha estado
arreglando en otros sitios, y se anoto como B-006 en cuanto aparecio.

Lo que cambia: la pagina se arma de cinco piezas, y cada una tiene un solo
dueno.

  plantilla/pagina.html   estructura, con dos huecos
  plantilla/estilo.css    tokens y diseno, con el logo como variable
  plantilla/logica.js     la regla generica, con dos huecos
  textos.json             los dos idiomas, para traducir sin tocar codigo
  marca/*.png             los logos, que se incrustan al construir

Y lo que importa de verdad: `datos.json` NO se escribe a mano nunca. Sale del
motor, y `test_la_tabla_reproduce_al_motor` compara las dos implementaciones en
3.240 combinaciones. Ese era el unico invariante en riesgo y ya estaba cubierto;
esto arregla lo demas.

ALTERNATIVA RECHAZADA: un empaquetador de verdad, con npm. Se rechaza porque
anade una cadena de construccion entera, y sus dependencias, para ensamblar
cuatro ficheros. El coste de esta version es que no minifica ni divide en
modulos; a cambio, `python3 consola/construir.py` no necesita nada instalado y
produce el mismo byte en cualquier maquina.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
import sys as _sys
_sys.path.insert(0, str(RAIZ.parent / "herramientas"))
from paginas import revisar_estructura  # noqa: E402
ANCHO_LOGO = 900

sys.path.insert(0, str(RAIZ / "marca"))
import incrustar as _incrustar  # noqa: E402


def _logo(nombre: str) -> str:
    """El logo ya reescalado, leido del dato versionado. NO requiere Pillow.

    Esto abria el PNG y lo recomprimia en cada construccion, y la salida de
    zlib depende de la version de Pillow instalada: dos maquinas sanas daban
    dos paginas distintas y la puerta de reproducibilidad fallaba en cualquiera
    que no fuera la del ultimo `make`. Ver `consola/marca/incrustar.py`.
    """
    return _incrustar.datauri(nombre)


def construir() -> str:
    datos = json.loads((RAIZ / "datos.json").read_text(encoding="utf-8"))
    textos = json.loads((RAIZ / "textos.json").read_text(encoding="utf-8"))

    # Que los textos cubran los dos idiomas no es un detalle de cortesia: el
    # producto se vende en Espana y se lee en Europa, y una clave que falte en
    # uno de los dos sale como `undefined` en la pantalla de un cliente.
    faltan = []
    for clave in textos["es"]:
        if clave not in textos["en"]:
            faltan.append(f"en.{clave}")
    for clave in textos["en"]:
        if clave not in textos["es"]:
            faltan.append(f"es.{clave}")
    if faltan:
        raise SystemExit(f"textos.json: claves que faltan en un idioma: {faltan}")

    css = (RAIZ / "plantilla" / "estilo.css").read_text(encoding="utf-8")
    css = css.replace("__LOGO_COLOR__", _logo("actaira-lockup.png"))
    css = css.replace("__LOGO_BLANCO__", _logo("actaira-lockup-white.png"))

    js = (RAIZ / "plantilla" / "logica.js").read_text(encoding="utf-8")
    js = js.replace("__DATOS__", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    js = js.replace("__TEXTOS__", json.dumps(textos, ensure_ascii=False, separators=(",", ":")))

    pagina = (RAIZ / "plantilla" / "pagina.html").read_text(encoding="utf-8")
    botones = "".join(
        f'<button data-l="{i}" aria-pressed="{str(i == "es").lower()}">'
        f'{i.upper()}</button>' for i in textos)
    salida = (pagina.replace("__ESTILO__", css)
                    .replace("__LOGICA__", js)
                    .replace("__IDIOMAS__", botones))
    # La MISMA puerta que el panel y la portada. Vivia dentro del
    # constructor del panel, asi que solo protegia al panel: esta pagina no
    # declaraba ni `<!doctype html>` ni `lang`, y llevaba asi desde la
    # primera version. Una puerta que no se puede reutilizar acaba
    # protegiendo solo lo que se acordo de protegerla.
    revisar_estructura(salida, "consola/consola.html")
    return salida


if __name__ == "__main__":
    salida = RAIZ / "consola.html"
    html = construir()
    salida.write_text(html, encoding="utf-8", newline="\n")
    print(f"{salida.relative_to(RAIZ.parent)}: {len(html) // 1024} KB, "
          f"{len(json.loads((RAIZ / 'textos.json').read_text(encoding='utf-8')))} idiomas")
