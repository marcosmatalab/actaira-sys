"""Construye `panel.html` desde sus piezas, como la consola y por lo mismo.

La consola de la fase 1 se escribio con un guion de una sola vez que no quedo
en el arbol, y la pagina dejo de ser regenerable. Aqui se arranca ya armado:

  plantilla/pagina.html   estructura
  plantilla/estilo.css    tokens y diseno, con el logo como variable
  plantilla/logica.js     el transporte y el pintado, con dos huecos
  textos.json             los dos idiomas, para traducir sin tocar codigo
  ../consola/marca/*.png  los logos, que se incrustan al construir

LO QUE ESTE FICHERO COMPRUEBA ANTES DE ESCRIBIR NADA
------------------------------------------------------
Que los dos idiomas tengan las MISMAS claves. Una clave que falte en uno de los
dos sale como `undefined` en la pantalla de un cliente, y eso no lo detecta
ningun test de unidad porque el fallo esta en el dato, no en el codigo.

Y que la logica no toque el almacenamiento del navegador. La credencial que
maneja esta pagina vale para leer el expediente entero de un cliente; guardarla
donde la lea cualquier script que acabe en la pagina seria regalarla.
"""
from __future__ import annotations

import json
import sys
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MARCA = RAIZ.parent / "consola" / "marca"
ANCHO_LOGO = 900

sys.path.insert(0, str(MARCA))
import incrustar as _incrustar  # noqa: E402

sys.path.insert(0, str(RAIZ.parent / "herramientas"))
from paginas import revisar_estructura, revisar_textos  # noqa: E402

PROHIBIDO_EN_LA_LOGICA = (
    "localStorage", "sessionStorage", "indexedDB", "document.cookie",
)
"""Lo que esta pagina no puede usar, y no es una preferencia de estilo.

La credencial vale para leer el expediente entero de un cliente. Un token en el
almacenamiento del navegador lo lee cualquier script que acabe en la pagina, y
ademas sobrevive a cerrar la pestana, asi que el descuido dura meses.
"""


def _logo(nombre: str) -> str:
    """El logo ya reescalado, leido del dato versionado. NO requiere Pillow.

    Esto abria el PNG y lo recomprimia en cada construccion, y la salida de
    zlib depende de la version de Pillow instalada: dos maquinas sanas daban
    dos paginas distintas y la puerta de reproducibilidad fallaba en cualquiera
    que no fuera la del ultimo `make`. Ver `consola/marca/incrustar.py`.
    """
    return _incrustar.datauri(nombre)


# `revisar_textos` SE IMPORTA, Y ANTES ERA UNA COPIA QUE MIRABA DOS IDIOMAS.
#
# Aqui vivia una version propia escrita cuando la pagina tenia `es` y `en`, y
# comparaba exactamente esos dos por su nombre. La pagina paso a seis idiomas y
# la comprobacion no: una clave que faltara en aleman, en frances, en italiano o
# en portugues salia como `undefined` en la pantalla de ese cliente y ninguna
# puerta lo veia -- que es literalmente el fallo que el docstring de esta
# funcion decia estar evitando.
#
# La version de `herramientas/paginas.py` compara TODOS los idiomas contra todos
# y ya la usaba la portada. Tener dos definiciones de la misma propiedad es la
# regla 10 de esta casa, y la que se quedo corta es siempre la copia.
#
# Se deja importada con este nombre a proposito: `motor/tests/test_panel.py`
# la lee de este modulo, asi que la prueba que la cubre sigue apuntando a la
# unica definicion que hay.


ANTES_DE_UNA_REGEX = set("(,=:[!&|?{};+-*%~^<>") | {"return", "typeof", "case", "in", "of"}


def _codigo_sin_prosa(js: str) -> str:
    """El JavaScript sin comentarios, sin literales de texto y sin expresiones
    regulares, recorrido caracter a caracter.

    Esto era tres sustituciones con expresiones regulares y las tres se
    equivocaban en cuanto se cruzaban entre si: la de comentarios solo veia los
    que empiezan la linea, la de cadenas borraba el `//` de una URL, y la de
    expresiones regulares confundia `/\\/+$/` con una division. Analizar un
    lenguaje con expresiones regulares es justo la clase de herramienta que
    «casi funciona» y por eso se relaja hasta que deja de mirar.

    Un recorrido de un paso no es un analizador de JavaScript, y no pretende
    serlo: distingue cinco estados -codigo, cadena, plantilla, comentario y
    expresion regular- y eso basta para las dos preguntas que se le hacen
    despues, que son si aparece una palabra y si aparece una division.
    """
    fuera, i, n = [], 0, len(js)
    ultimo = ""                      # ultimo caracter significativo del codigo
    while i < n:
        c = js[i]
        if c == "/" and i + 1 < n and js[i + 1] == "/":
            while i < n and js[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and js[i + 1] == "*":
            fin = js.find("*/", i + 2)
            i = n if fin < 0 else fin + 2
            continue
        if c in "\"'":
            comilla, i = c, i + 1
            while i < n and js[i] != comilla:
                i += 2 if js[i] == "\\" else 1
            i += 1
            fuera.append('""')
            ultimo = '"'
            continue
        if c == "`":
            # Una plantilla NO es solo texto: lo que va dentro de `${...}` es
            # codigo, y borrarlo entero dejaba fuera del alcance de las dos
            # puertas todo lo que se escribe ahi. Una division dentro de una
            # plantilla es una division igual.
            i += 1
            fuera.append('""')
            while i < n and js[i] != "`":
                if js[i] == "\\":
                    i += 2
                    continue
                if js[i] == "$" and i + 1 < n and js[i + 1] == "{":
                    hondura, j = 1, i + 2
                    while j < n and hondura:
                        hondura += {"{": 1, "}": -1}.get(js[j], 0)
                        j += 1
                    fuera.append(" " + _codigo_sin_prosa(js[i + 2:j - 1]) + " ")
                    i = j
                    continue
                i += 1
            i += 1
            ultimo = "`"
            continue
        if c == "/" and (ultimo in ANTES_DE_UNA_REGEX or ultimo == ""):
            i += 1
            dentro_de_clase = False
            while i < n and (dentro_de_clase or js[i] != "/"):
                if js[i] == "\\":
                    i += 1
                elif js[i] == "[":
                    dentro_de_clase = True
                elif js[i] == "]":
                    dentro_de_clase = False
                elif js[i] == "\n":
                    break
                i += 1
            i += 1
            while i < n and js[i].isalpha():
                i += 1
            fuera.append("RE")
            ultimo = "E"
            continue
        fuera.append(c)
        if not c.isspace():
            ultimo = c
        i += 1
    return "".join(fuera)


def revisar_logica(js: str) -> None:
    codigo = _codigo_sin_prosa(js)
    malas = [p for p in PROHIBIDO_EN_LA_LOGICA if p in codigo]
    if malas:
        raise SystemExit(
            f"logica.js usa {malas}: la credencial de esta pagina vale para leer el "
            "expediente entero de un cliente y no se guarda en el navegador.")
    # Una division es casi siempre una proporcion disfrazada, y la primera
    # negativa las prohibe. Aqui ya no quedan barras de comentario ni de
    # expresion regular, asi que cualquier barra que sobreviva divide.
    for numero, linea in enumerate(codigo.splitlines(), 1):
        if "/" in linea:
            raise SystemExit(
                f"logica.js divide en la linea {numero}, y una division aqui es una "
                f"proporcion disfrazada: {linea.strip()}")


def revisar_accesibilidad(pagina: str, textos: dict) -> None:
    """Lo que la pagina tiene que cumplir para que se pueda usar sin ver y sin raton.

    POR QUE ESTO ES UNA PUERTA DEL BUILD Y NO UNA REVISION
    -------------------------------------------------------
    La accesibilidad no se rompe de golpe: se rompe un control cada vez, cuando
    alguien anade un boton con prisa. Una revision manual la encuentra meses
    despues, cuando ya hay veinte, y entonces el arreglo es un proyecto en vez
    de una linea. Aqui se comprueba al construir, que es el unico momento en el
    que cuesta nada.

    Lo que se comprueba son propiedades ESTRUCTURALES, que es lo que se puede
    comprobar leyendo el HTML. Lo que NO se comprueba -- y se dice, porque un
    listado de comprobaciones invita a creer que estan todas -- es el contraste
    real de los colores compuestos, el orden de tabulacion percibido y si los
    textos se entienden. Eso lo mira una persona, y esta puerta no la sustituye.
    """
    import re

    fallos = []

    # 1. Todo control interactivo tiene un nombre que un lector puede anunciar.
    #
    #    Un `<button>` vacio -- y los de esta pagina lo estan, porque el texto lo
    #    pone el JavaScript segun el idioma -- solo es anunciable si trae `id`,
    #    y el id es lo que ata el boton a su clave de texto. Sin esa atadura, el
    #    boton sale mudo en los dos idiomas.
    for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", pagina, re.S):
        atributos, dentro = m.group(1), m.group(2).strip()
        tiene_id = re.search(r'\bid="([^"]+)"', atributos)
        if not dentro and not tiene_id and "aria-label" not in atributos:
            fallos.append(f"un <button> sin texto, sin id y sin aria-label: {m.group(0)[:70]}")

    # 2. Todo `input` y `select` tiene etiqueta: dentro de un <label>, o con
    #    `aria-label`, o apuntado por `aria-labelledby`.
    for etiqueta in ("input", "select"):
        for m in re.finditer(rf"<{etiqueta}\b([^>]*)>", pagina):
            atributos = m.group(1)
            if 'type="hidden"' in atributos:
                continue
            ident = re.search(r'\bid="([^"]+)"', atributos)
            if not ident:
                fallos.append(f"un <{etiqueta}> sin id, asi que nada lo puede etiquetar")
                continue
            envuelto = re.search(
                r"<label\b[^>]*>(?:(?!</label>).)*" + re.escape(m.group(0)),
                pagina, re.S)
            if not (envuelto or "aria-label" in atributos
                    or "aria-labelledby" in atributos
                    or f'for="{ident.group(1)}"' in pagina):
                fallos.append(f"<{etiqueta} id=\"{ident.group(1)}\"> no tiene etiqueta")

    # 3. Un solo `<h1>`, y ningun salto de nivel.
    niveles = [int(x) for x in re.findall(r"<h([1-6])\b", pagina)]
    if niveles.count(1) != 1:
        fallos.append(f"hay {niveles.count(1)} encabezados <h1> y tiene que haber uno")
    for antes, despues in zip(niveles, niveles[1:]):
        if despues > antes + 1:
            fallos.append(f"el encabezado salta de h{antes} a h{despues}: "
                          f"un lector anuncia la estructura y ahi aparece un hueco")

    # 4. `lang` en la raiz. Sin el, un lector de pantalla pronuncia el castellano
    #    con las reglas del ingles y no se entiende nada.
    if not re.search(r'<html\b[^>]*\blang="', pagina):
        fallos.append("el <html> no declara `lang`")

    # 5. El foco del teclado se ve. Es lo primero que quita cualquier hoja de
    #    estilo para «que quede limpio», y sin el la pagina se puede recorrer
    #    con el teclado pero no se puede saber donde estas.
    if "focus-visible" not in pagina:
        fallos.append("no hay ninguna regla de `:focus-visible`: el foco del teclado "
                      "no se ve, y sin verlo el teclado no sirve")
    if re.search(r"outline\s*:\s*none", pagina) and "focus-visible" not in pagina:
        fallos.append("se quita el `outline` sin reponer el foco")

    # 6. Las claves de texto que la pagina pide existen en los dos idiomas.
    #    Un boton que pide una clave que no esta sale vacio, y un boton vacio es
    #    justamente el caso 1 por la puerta de atras.
    for idioma in textos:
        faltan = [c for c in re.findall(r'"#[a-z0-9-]+": "([a-z0-9_]+)"',
                                        (Path(__file__).resolve().parent
                                         / "plantilla" / "logica.js").read_text(encoding="utf-8"))
                  if c not in textos[idioma]]
        if faltan:
            fallos.append(f"la pagina pide claves que {idioma} no tiene: {sorted(set(faltan))}")

    if fallos:
        raise SystemExit("accesibilidad:\n  " + "\n  ".join(fallos))


def construir() -> str:
    textos = json.loads((RAIZ / "textos.json").read_text(encoding="utf-8"))
    revisar_textos(textos)

# LAS TIPOGRAFIAS VAN DELANTE, Y VIENEN DE DENTRO.
    #
    # Antes las traia un `<link>` a `fonts.googleapis.com` en la plantilla. Eso
    # rompia la promesa de esta pagina -- un solo fichero que se abre sin servidor
    # -- y le contaba a Google quien abre el expediente de un cliente. El porque
    # entero esta en `herramientas/fuentes.py`.
    #
    # Delante del estilo porque un `@font-face` tiene que estar declarado antes de
    # que alguien use su familia.
    fuentes = (RAIZ.parent / "tipografias" / "interfaz.css").read_text(encoding="utf-8")
    css = fuentes + (RAIZ / "plantilla" / "estilo.css").read_text(encoding="utf-8")
    css = css.replace("__LOGO_COLOR__", _logo("actaira-lockup.png"))
    css = css.replace("__LOGO_BLANCO__", _logo("actaira-lockup-white.png"))

    js = (RAIZ / "plantilla" / "logica.js").read_text(encoding="utf-8")
    revisar_logica(js)
    js = js.replace("__TEXTOS__", json.dumps(textos, ensure_ascii=False, separators=(",", ":")))
    # El vocabulario de roles lo GENERA `herramientas/generar_roles.py` desde
    # el motor. Se incrusta aqui en vez de pedirlo por red para que la pagina
    # siga siendo un solo fichero que se abre sin servidor.
    roles = (RAIZ / "roles.json").read_text(encoding="utf-8")
    js = js.replace("__ROLES__", json.dumps(json.loads(roles), ensure_ascii=False,
                                            separators=(",", ":")))

    pagina = (RAIZ / "plantilla" / "pagina.html").read_text(encoding="utf-8")
    # Un boton por idioma de `textos.json`, generado. Escribirlos a mano en la
    # plantilla es la lista que se queda corta el dia que se anade el septimo.
    botones = "".join(
        f'<button data-l="{i}" aria-pressed="{str(i == "es").lower()}">'
        f'{i.upper()}</button>' for i in textos)
    salida = (pagina.replace("__ESTILO__", css)
                    .replace("__LOGICA__", js)
                    .replace("__IDIOMAS__", botones))
    # LA PUERTA COMPARTIDA, ADEMAS DE LA DE AQUI.
    #
    # `revisar_accesibilidad` es de este fichero y cubre lo que solo el panel
    # necesita; `revisar_estructura` es la de las tres paginas y cubre lo que
    # todas comparten -- el doctype, el `lang`, los encabezados, el foco y, desde
    # que la consola perdio dos vistas por ello, que no haya UN SOLO id repetido.
    # El panel era la unica pagina que no la llamaba, por el mismo motivo por el
    # que existio: la comprobacion nacio dentro de este constructor, se saco para
    # que la usaran las otras dos, y el original se quedo aqui sin volver a
    # mirarse. Se llaman las dos.
    revisar_estructura(salida, "panel/panel.html")
    revisar_accesibilidad(salida, textos)
    return salida


if __name__ == "__main__":
    salida = RAIZ / "panel.html"
    html = construir()
    salida.write_text(html, encoding="utf-8", newline="\n")
    textos = json.loads((RAIZ / "textos.json").read_text(encoding="utf-8"))
    print(f"{salida.relative_to(RAIZ.parent)}: {len(html) // 1024} KB, "
          f"{len(textos)} idiomas, {len(textos['es'])} claves cada uno")
