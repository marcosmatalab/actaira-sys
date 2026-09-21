"""Las transformaciones de una cadena de publicacion, aplicadas de verdad.

POR QUE ESTE MODULO EXISTE
---------------------------
`Entrada.pipeline` llevaba desde la fase 2 en el contrato del articulo 50 y NO
lo leia nadie: dos cadenas distintas producian el mismo resultado, byte a byte.
Una auditoria externa lo reprodujo. Un campo que se acepta y se ignora es peor
que un campo que no existe, porque el que lo rellena cree que esta midiendo
algo.

LA AFIRMACION QUE PERMITE MEDIR
--------------------------------
El articulo 50(2) obliga a marcar la salida generada en un formato legible por
maquina, y no nombra ningun formato. Un marcado de metadatos se escribe en un
instante y lo destruye cualquier recompresion posterior. Asi que la pregunta
util no es «esta marcado», sino «sigue marcado DESPUES de tu cadena real de
publicacion», y esa es una propiedad de la cadena, no del marcado.

LO QUE NO SE HACE
------------------
No se inventa la cadena del cliente. Si no declara ninguna, no se mide nada y
se dice en `no_cubre`. Si declara una transformacion que este modulo no conoce,
NO se salta en silencio: se devuelve como desconocida y el control sale
INDETERMINADO. Saltarse un paso y seguir midiendo daria un numero mas bonito
sobre una cadena que no es la suya.

POR QUE SE SIMULA CADA PASO DOS VECES
---------------------------------------
Aqui habia una medicion que no medía lo que decía. Cada paso se aplicaba con
`Image.open(...).save(...)` de Pillow, que descarta los metadatos SIEMPRE, asi
que el resultado era el mismo para cualquier cadena: el marcado moria en el
primer paso, fuera el que fuera. Rotar noventa grados salia igual de destructivo
que quitar los metadatos a proposito.

Eso no es una medicion de la cadena del cliente: es una medicion de Pillow. Y su
respuesta no dependia de la entrada, que es la forma mas silenciosa de que un
control deje de informar -- no falla, no se rompe, simplemente dice siempre lo
mismo y nadie lo nota porque lo que dice suena a mala noticia razonable.

La pregunta de la que depende de verdad no se puede contestar leyendo bytes: si
las herramientas CONCRETAS del cliente conservan los metadatos o no. Un
`convert` de ImageMagick con `-strip` los tira; sin `-strip`, los conserva. Dos
cadenas con los mismos nombres de paso dan resultados opuestos.

Asi que no se elige una de las dos hipotesis y se presenta como la verdad: se
aplican las dos y se devuelven las dos.

  conservando   modela herramientas que arrastran el XMP paso a paso. Es el
                mejor caso posible para el cliente.
  descartando   modela herramientas que reescriben los pixeles y nada mas. Es
                el peor, y es lo que hace media herramienta de optimizacion de
                imagenes sin decirlo.

Si el marcado no sobrevive ni conservando, el problema es la cadena y se dice.
Si sobrevive conservando y no descartando, el problema NO es la cadena: es que
un marcado que vive solo en los metadatos es fragil por construccion, y lo que
hay que decirle al cliente es que compruebe sus herramientas o que anada un
marcado que no viaje en los metadatos.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

# Las ocho transformaciones corrientes de una cadena de publicacion. Los
# nombres son los que el cliente escribe en su perfil.
CONOCIDAS = (
    "recomprimir_jpeg_85", "recomprimir_jpeg_60", "redimensionar_mitad",
    "recortar_10", "rotar_90", "a_jpeg", "a_png", "quitar_metadatos",
)

BORRAN_A_PROPOSITO = frozenset({"quitar_metadatos"})
"""Los pasos que se saltan la hipotesis de «herramientas que conservan».

`quitar_metadatos` no es una transformacion que de paso pierda el marcado: es
una transformacion cuyo PROPOSITO es quitarlo. Reponerlo despues, aunque sea
para modelar una cadena cuidadosa, seria modelar una cadena que hace y deshace
lo mismo, y la respuesta saldria «sobrevive» para una cadena que por definicion
lo borra. Un modelo que contradice la definicion de su propia entrada no esta
siendo generoso: esta mintiendo.
"""


@dataclass(frozen=True)
class Paso:
    nombre: str
    salida: Path
    aplicado: bool
    motivo: str | None = None


def _pillow():
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        return False


def _xmp_de(ruta: Path) -> str | None:
    """El DigitalSourceType que trae el fichero, si trae alguno reconocible."""
    from .marcado import read_facts

    return read_facts(ruta).digital_source_type


def _reponer_xmp(salida: Path, source_type: str | None) -> None:
    """Vuelve a escribir el XMP que la transformacion se llevo por delante.

    Es lo que hace una herramienta que conserva metadatos, y la unica forma de
    modelarla con Pillow, que los descarta al guardar sin excepcion. Sin esto,
    la rama `conservando` seria identica a la rama `descartando` y la medicion
    volveria a dar siempre la misma respuesta.
    """
    if source_type is None:
        return
    from .marcado import write_marking

    try:
        write_marking(salida, source_type=source_type)
    except (OSError, ValueError):
        pass          # el formato de salida no admite XMP: se ve en la medicion


def aplicar(origen: Path, pasos: tuple[str, ...], destino: Path, *,
            conservar_metadatos: bool = False) -> tuple[list[Paso], list[str]]:
    """Aplica los pasos en orden. Devuelve (lo hecho, los nombres desconocidos).

    Cada paso escribe su propio fichero, asi que se puede decir EN QUE PASO se
    perdio el marcado y no solo que se perdio. Esa diferencia es la que
    convierte una medicion en una remediacion: el cliente no tiene que cambiar
    su cadena entera, tiene que cambiar un paso.
    """
    desconocidos = [p for p in pasos if p not in CONOCIDAS]
    if desconocidos:
        return [], desconocidos
    if not pasos:
        return [], []
    if not _pillow():
        return [Paso(p, origen, False, "Pillow no esta instalado: `pip install actaira-motor[marcado]`")
                for p in pasos], []

    from PIL import Image

    destino.mkdir(parents=True, exist_ok=True)
    hechos: list[Paso] = []
    actual = origen
    # Lo que traia el ORIGINAL. Se lee una vez y se repone en cada paso: una
    # herramienta que conserva metadatos conserva los que habia, no los que
    # este modulo crea que deberia haber.
    marca_original = _xmp_de(origen) if conservar_metadatos else None
    for i, nombre in enumerate(pasos, 1):
        im = Image.open(actual)
        sufijo = ".jpg" if nombre in ("recomprimir_jpeg_85", "recomprimir_jpeg_60", "a_jpeg") else ".png"
        salida = destino / f"{i:02d}-{nombre}{sufijo}"
        if nombre == "recomprimir_jpeg_85":
            im.convert("RGB").save(salida, "JPEG", quality=85)
        elif nombre == "recomprimir_jpeg_60":
            im.convert("RGB").save(salida, "JPEG", quality=60)
        elif nombre == "redimensionar_mitad":
            im.resize((max(1, im.width // 2), max(1, im.height // 2))).save(salida)
        elif nombre == "recortar_10":
            dx, dy = max(1, im.width // 10), max(1, im.height // 10)
            im.crop((dx, dy, max(dx + 1, im.width - dx), max(dy + 1, im.height - dy))).save(salida)
        elif nombre == "rotar_90":
            im.rotate(90, expand=True).save(salida)
        elif nombre == "a_jpeg":
            im.convert("RGB").save(salida, "JPEG")
        elif nombre == "a_png":
            im.convert("RGBA").save(salida, "PNG")
        elif nombre == "quitar_metadatos":
            # Reescribir los pixeles sin nada mas. Es lo que hace media
            # herramienta de optimizacion de imagenes sin decirlo.
            # `Image.new` + `putdata(list(im.getdata()))` hacia esto mismo, pero
            # `getdata` esta depreciado y desaparece en Pillow 14 (octubre de
            # 2027), y `pyproject` declara `pillow>=10` sin techo: el dia que
            # esa version salga, este paso -- que simula la herramienta que
            # borra los metadatos -- habria reventado en una instalacion nueva.
            # `frombytes`/`tobytes` es API estable desde siempre y no arrastra
            # ningun metadato, que es justo lo que este paso quiere.
            limpio = Image.frombytes(im.mode, im.size, im.tobytes())
            limpio.save(salida)
        if nombre in BORRAN_A_PROPOSITO:
            # A partir de aqui no se repone NADA, ni en la hipotesis generosa.
            # Reponer despues de un borrado deliberado hacia que
            # `quitar_metadatos` seguido de cualquier cosa resucitara el
            # marcado: la cadena que MAS lo destruye salia como la que lo
            # conserva, y solo por el orden de los pasos.
            marca_original = None
        elif conservar_metadatos:
            _reponer_xmp(salida, marca_original)
        hechos.append(Paso(nombre, salida, True))
        actual = salida
    return hechos, []


def copiar_a(origen: Path, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)
    return destino
