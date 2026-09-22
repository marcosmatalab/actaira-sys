r"""Las tipografias, DENTRO del arbol, y solo los caracteres que se usan.

POR QUE ESTE FICHERO EXISTE
-----------------------------
El panel, la consola y la portada traian las tipografias con un `<link>` a
`fonts.googleapis.com`. Tres cosas estaban mal a la vez, y la tercera es la que
no se puede dejar pasar en este producto.

1. El README promete que el panel es «un solo fichero, cero peticiones de red»
   y el manual dice que se abre sin servidor. Con el `<link>` puesto, abrirlo
   hacia una peticion a un tercero. La afirmacion era falsa, y la escribio esta
   casa.

2. La consola es el artefacto que existe para abrirse OFFLINE. Pedir una
   tipografia a internet para leerla es lo contrario de lo que es.

3. Y la que decide: cada carga del panel le contaba a Google la direccion IP de
   quien abre el expediente de cumplimiento de un cliente. Para una herramienta
   del Reglamento de IA y de la ISO 42001 eso no es un detalle de estilo -- es
   una transferencia a un tercero que el cliente no declaro, y hay
   jurisprudencia europea sobre exactamente ese `<link>` (LG Munchen I,
   3 O 17493/20, enero de 2022). La portada publicaba «0 telemetria» al lado.

Lo cazo la puerta del navegador el dia que se le pidio que afirmara lo que el
README ya decia: que la pagina no pide NADA fuera.

QUE HACE
----------
    python herramientas/fuentes.py --traer       baja, subconjunta y genera
    python herramientas/fuentes.py --comprobar   dice si lo generado esta bien

`--traer` necesita red y `fonttools`, y se corre A MANO, muy de vez en cuando.
Lo que se commitea es el CSS generado, con las tipografias dentro en base64,
para que CONSTRUIR el producto no necesite red ni `fonttools`: si construir
necesitara red, quien clone el arbol sin conexion no podria ni hacer la pagina.

POR QUE SE SUBCONJUNTA, Y NO SE INCRUSTA EL ALFABETO ENTERO
-------------------------------------------------------------
Google sirve trece ficheros por familia -- cirilico, griego, vietnamita... --
y solo el bloque `latin` de Newsreader son 129 KB POR CARA: dos caras son 258
KB en crudo y 345 KB en base64, viajando en cada carga de la portada para
pintar dos titulares.

Asi que se subconjunta a los caracteres que este producto escribe de verdad:
los 39 ficheros del catalogo, los textos de las tres pantallas en los seis
idiomas, y el ASCII imprimible entero como colchon. Eso son unos 140 caracteres
en vez de varios miles.

EL RIESGO DE SUBCONJUNTAR, Y LA PUERTA QUE LO CUBRE
-----------------------------------------------------
Un subconjunto es una afirmacion sobre el CONTENIDO, y el contenido crece. El
dia que el catalogo traiga un caracter que no se incrusto, el navegador lo
pintaria con la tipografia de respaldo del sistema en mitad de una frase: feo,
silencioso y dificil de atribuir.

Por eso `--comprobar` vuelve a contarlo -- lee el `cmap` real de lo incrustado,
no lo que el CSS declare -- y se pone roja si algo se sale. Es la puerta la que
permite subconjuntar sin que sea una apuesta.

LICENCIAS
-----------
Archivo, IBM Plex Mono y Newsreader son SIL Open Font License 1.1, que permite
redistribuirlas incrustadas y modificadas -- subconjuntar es modificar -- con
la atribucion puesta. Va en `NOTICE`, que es donde este arbol pone lo que no ha
escrito.
"""
from __future__ import annotations

import argparse
import base64
import re
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "tipografias"

# El navegador que se le dice a Google que somos. Sin esto contesta con `ttf`,
# que pesa tres veces mas: el formato depende de quien pregunta.
NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Dos ficheros y no uno, porque `Newsreader` solo la usa la portada y meterla
# en el panel serian trescientos kilobytes para no pintar nada.
JUEGOS = {
    "interfaz": ("https://fonts.googleapis.com/css2?family=Archivo:wght@400..700"
                 "&family=IBM+Plex+Mono:wght@400;500&display=swap"),
    "portada": ("https://fonts.googleapis.com/css2"
                "?family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap"),
}

# De donde sale el texto que este producto escribe. Si aparece otra fuente de
# texto visible, se anade aqui: la lista corta es el precio de que el
# subconjunto sea exacto en vez de aproximado.
DONDE_HAY_TEXTO = ("panel/textos.json", "panel/roles.json", "sitio/textos.json",
                   "consola/textos.json")

# LOS SIMBOLOS QUE VAN A PROPOSITO CON LA TIPOGRAFIA DEL SISTEMA.
#
# Ninguna de estas tres familias los trae, tampoco en el `latin` completo de
# Google: ya se pintaban con el respaldo del sistema ANTES de incrustar nada, y
# eso esta bien -- son iconos, no texto, y el sistema los dibuja mejor.
#
# Estan escritos aqui uno a uno, y no se filtran por rango, porque la lista
# corta es lo que hace que la puerta siga siendo exacta: el dia que alguien
# meta un icono nuevo en la pagina, la puerta lo dice y habra que decidir si va
# aqui o si hace falta otra tipografia. Filtrar «todo lo que parezca un simbolo»
# seria apagar la comprobacion.
DEL_SISTEMA = {
    "\u25b8",  # ▸  el triangulo de `<summary>` cerrado
    "\u25be",  # ▾  el de abierto
    "\u263c",  # ☼  el boton de tema claro
    "\u263e",  # ☾  el de tema oscuro
}

CABECERA = """/* GENERADO POR `herramientas/fuentes.py --traer`. NO SE EDITA A MANO.
 *
 * Las tipografias van aqui dentro, en base64, subconjuntadas a los caracteres
 * que este producto escribe. No se le piden a nadie.
 *
 * El porque esta entero en la cabecera de ese fichero; el resumen es que el
 * panel promete ser un solo fichero que se abre sin servidor, que la consola
 * existe para leerse offline, y que pedirle la tipografia a Google le cuenta a
 * Google quien abre el expediente de un cliente.
 *
 * SIL Open Font License 1.1. La atribucion esta en `NOTICE`.
 */
"""


def caracteres_del_producto() -> set[str]:
    """Todo lo que estas pantallas pueden llegar a escribir.

    El catalogo entero mas los textos de la interfaz, y el ASCII imprimible
    como colchon: los identificadores, las rutas y el JSON en crudo que el panel
    ensena salen de ahi y no de ningun fichero de texto.
    """
    trozos = [chr(c) for c in range(0x20, 0x7F)]
    for f in sorted((RAIZ / "catalogo").rglob("*.json")):
        trozos.append(f.read_text(encoding="utf-8"))
    for rel in DONDE_HAY_TEXTO:
        f = RAIZ / rel
        if f.is_file():
            trozos.append(f.read_text(encoding="utf-8"))
    # Y lo que las propias paginas llevan escrito a mano.
    for rel in ("panel/plantilla/pagina.html", "consola/plantilla/pagina.html",
                "sitio/plantilla/pagina.html", "panel/plantilla/estilo.css",
                "consola/plantilla/estilo.css"):
        f = RAIZ / rel
        if f.is_file():
            trozos.append(f.read_text(encoding="utf-8"))
    return set("".join(trozos)) - DEL_SISTEMA


def _bajar(url: str) -> bytes:
    pet = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR})
    with urllib.request.urlopen(pet, timeout=60) as r:
        return r.read()


def traer() -> int:
    try:
        from fontTools import subset as recortar
        from fontTools.ttLib import TTFont
    except ImportError:
        print("`--traer` necesita fonttools y brotli: pip install fonttools brotli",
              file=sys.stderr)
        return 1
    import io

    quiero = caracteres_del_producto()
    puntos = sorted(ord(c) for c in quiero)
    print(f"  el producto escribe {len(puntos)} caracteres distintos")

    SALIDA.mkdir(exist_ok=True)
    for nombre, peticion in JUEGOS.items():
        css = _bajar(peticion).decode("utf-8")
        bloques = re.findall(r"/\*\s*([a-z-]+)\s*\*/\s*(@font-face\s*\{.*?\})", css, re.S)
        if not bloques:
            raise SystemExit(f"la respuesta de Google para {nombre!r} no trae `@font-face`")

        fuera, crudo, recortado = [CABECERA], 0, 0
        for subconjunto, bloque in bloques:
            # `latin` trae todo lo que este producto necesita; los demas
            # bloques son alfabetos que no habla.
            if subconjunto != "latin":
                continue
            urls = re.findall(r"url\((https://[^)]+\.woff2)\)", bloque)
            if len(urls) != 1:
                raise SystemExit(f"un bloque de {nombre} trae {len(urls)} ficheros")
            datos = _bajar(urls[0])
            crudo += len(datos)

            fuente = TTFont(io.BytesIO(datos))

            # FIJAR LOS EJES QUE NADIE USA.
            #
            # `Newsreader` es variable en `opsz` (tamano optico, de 6 a 72) y
            # esa maquinaria sobrevive al recorte: 129 KB se quedaban en 92,
            # para un eje que estas paginas no mueven -- el CSS no escribe
            # `font-variation-settings` en ningun sitio. Fijandolo, la
            # tipografia se vuelve estatica y cae a una fraccion.
            #
            # `wght` NO se toca: `Archivo` cubre de 400 a 700 con un solo
            # fichero y aplanarla obligaria a bajar cuatro.
            ejes = {a.axisTag: a for a in fuente["fvar"].axes} if "fvar" in fuente else {}
            if "opsz" in ejes:
                from fontTools.varLib import instancer
                # 16 es el tamano al que se leen estos titulares en pantalla.
                fuente = instancer.instantiateVariableFont(fuente, {"opsz": 16})

            opciones = recortar.Options()
            opciones.flavor = "woff2"
            # Las variables se conservan: `Archivo` cubre de 400 a 700 con un
            # solo fichero, y aplanarla obligaria a bajar cuatro.
            opciones.retain_gids = False
            opciones.layout_features = ["*"]
            recortador = recortar.Subsetter(options=opciones)
            recortador.populate(unicodes=puntos)
            recortador.subset(fuente)
            buf = io.BytesIO()
            fuente.flavor = "woff2"
            fuente.save(buf)
            corto = buf.getvalue()
            recortado += len(corto)

            # El `unicode-range` se REESCRIBE con lo que de verdad quedo dentro.
            # Dejar el de Google diria que la tipografia cubre cosas que ya no
            # trae, y el navegador se lo creeria: pintaria un hueco en vez de
            # caer al respaldo.
            cmap = set(TTFont(io.BytesIO(corto)).getBestCmap())
            rango = ", ".join(f"U+{c:04X}" for c in sorted(cmap))
            metido = "data:font/woff2;base64," + base64.b64encode(corto).decode("ascii")
            nuevo = re.sub(r"unicode-range:[^;]+;", f"unicode-range: {rango};", bloque)
            nuevo = nuevo.replace(urls[0], metido)

            familia = re.search(r"font-family:\s*'([^']+)'", bloque).group(1)
            peso = re.search(r"font-weight:\s*([^;]+);", bloque).group(1).strip()
            fuera.append(f"/* {familia} {peso} · {len(cmap)} caracteres · "
                         f"{len(corto) / 1024:.0f} KB */\n{nuevo}")
            print(f"  {familia:<16} peso {peso:<9} "
                  f"{len(datos) / 1024:6.1f} KB -> {len(corto) / 1024:5.1f} KB")

        if not recortado:
            raise SystemExit(f"no salio ningun bloque `latin` de {nombre!r}")
        destino = SALIDA / f"{nombre}.css"
        destino.write_text("\n".join(fuera) + "\n", encoding="utf-8", newline="\n")
        print(f"  {nombre}.css: {crudo / 1024:.0f} KB en crudo -> "
              f"{recortado / 1024:.0f} KB recortados -> "
              f"{destino.stat().st_size / 1024:.0f} KB en base64")
    return 0


def _rango(css: str) -> set[int]:
    """Los puntos de codigo que lo incrustado sabe pintar, segun el CSS."""
    puntos: set[int] = set()
    for crudo in re.findall(r"unicode-range:\s*([^;]+);", css):
        for parte in crudo.split(","):
            parte = parte.strip().replace("U+", "")
            if "-" in parte:
                a, z = parte.split("-")
                puntos.update(range(int(a, 16), int(z, 16) + 1))
            elif parte:
                puntos.add(int(parte, 16))
    return puntos


def comprobar() -> int:
    """Que lo generado exista, no pida nada fuera, y cubra lo que se escribe."""
    ficheros = {n: SALIDA / f"{n}.css" for n in JUEGOS}
    faltan = [f.name for f in ficheros.values() if not f.is_file()]
    if faltan:
        print(f"faltan tipografias generadas: {faltan}. Correr `--traer`", file=sys.stderr)
        return 1

    cubierto: set[int] = set()
    caras = 0
    peso = 0.0
    for _nombre, f in ficheros.items():
        css = f.read_text(encoding="utf-8")
        pide = re.findall(r"url\((?!data:)([^)]+)\)", css)
        if pide:
            print(f"{f.name} pide cosas fuera: {pide[:3]}", file=sys.stderr)
            return 1
        cubierto |= _rango(css)
        caras += len(re.findall(r"@font-face", css))
        peso += f.stat().st_size / 1024

    # LO QUE SE ESCRIBE TIENE QUE CABER EN LO QUE SE INCRUSTO.
    #
    # Se compara contra el `unicode-range` que este mismo guion reescribio con
    # el `cmap` real del fichero recortado, asi que no es una declaracion: es lo
    # que la tipografia trae dentro.
    fuera = sorted(c for c in caracteres_del_producto()
                   if ord(c) > 0x1F and ord(c) not in cubierto)
    if fuera:
        print(f"este producto escribe {len(fuera)} caracteres que las tipografias "
              f"incrustadas no traen: "
              f"{[f'{c!r} U+{ord(c):04X}' for c in fuera[:8]]}. "
              f"Hay que volver a correr `--traer`", file=sys.stderr)
        return 1

    print(f"tipografias: {caras} caras en {len(ficheros)} ficheros, {peso:.0f} KB, "
          f"ninguna peticion fuera, y los {len(caracteres_del_producto())} caracteres "
          f"que este producto escribe caben en lo incrustado")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Las tipografias, dentro del arbol.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--traer", action="store_true",
                   help="baja, subconjunta y genera (necesita red y fonttools)")
    g.add_argument("--comprobar", action="store_true", help="dice si lo generado esta bien")
    a = p.parse_args()
    return traer() if a.traer else comprobar()


if __name__ == "__main__":
    raise SystemExit(main())
