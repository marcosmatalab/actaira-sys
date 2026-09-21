"""De dónde sale el texto de un ticket, y por qué no lo escribimos aquí.

EL ENCARGO NO SE REDACTA: SE BUSCA
------------------------------------
Un hallazgo trae el identificador de la regla que lo produjo, y esa regla trae
su título y su remediación **escritos por una persona y en los dos idiomas**.
Ése es el texto que tiene que llegar al ticket: es el que alguien redactó para
que se pueda hacer, es el que un auditor puede contrastar con el catálogo, y es
el que no cambia cada vez que el modelo redacta otra vez lo mismo con otras
palabras. Segunda negativa de la casa: un modelo nunca redacta reglas ni
remediaciones en ejecución.

Cuando la no conformidad no viene de una regla -una auditoría, una reclamación,
algo que alguien vio- no hay texto bilingüe que buscar. Entonces se pone el del
cliente **tal cual lo escribió**, en un campo que dice que es suyo, y no se
finge una traducción: un `en` que repite el castellano es peor que no tenerlo,
porque quien lee en inglés no sabe que está leyendo otro idioma.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contrato import Encargo


def _reglas(directorio: Path) -> dict[str, dict[str, Any]]:
    """Todas las reglas del catálogo, por identificador.

    Se lee el contenido y no el nombre del fichero, por lo mismo que el índice
    de paquetes: un nombre que decide comportamiento es una segunda fuente de
    verdad sobre a qué sirve un paquete.
    """
    fuera: dict[str, dict[str, Any]] = {}
    for ruta in sorted(Path(directorio).glob("*.json")):
        try:
            d = json.loads(ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            # UN PAQUETE ROTO REVIENTA. No se salta.
            #
            # De aqui sale el TEXTO que se le manda a una persona en un ticket:
            # el titulo de la regla y su remediacion, escritos a mano y en los
            # dos idiomas. Saltarse un paquete ilegible no deja el ticket sin
            # ese texto de forma visible: lo deja sin la regla, y entonces el
            # encargo sale con lo generico o no sale, y quien lo reciba no
            # sabra que lo que tiene delante no es lo que el catalogo dice.
            #
            # Y es un fichero DEL ARBOL, no del cliente: que no cargue es un
            # defecto de esta casa, no una condicion del entorno. Fallar
            # ruidosamente con su nombre delante es lo unico util.
            raise ValueError(
                f"{ruta}: no se pudo leer el paquete de reglas ({type(e).__name__}: {e}). "
                f"De aqui sale el texto que se le manda a una persona en un ticket, "
                f"asi que saltarselo produciria un encargo sin el texto del catalogo "
                f"y nadie lo notaria.") from e
        for r in d.get("reglas", []):
            if isinstance(r, dict) and r.get("id"):
                fuera[r["id"]] = {**r, "paquete": d.get("paquete", ruta.stem),
                                  "obligacion": d.get("obligacion", "")}
    return fuera


def de_no_conformidad(nc: Any, reglas: Path | str | None, responsable: str,
                      compromiso: str, severidad: str = "",
                      obligacion: str = "", localizaciones: tuple[str, ...] = (),
                      ) -> tuple[Encargo, dict[str, str]]:
    """El encargo, y una nota que dice de dónde salió cada palabra.

    La nota viaja con el encargo a propósito. Un ticket cuyo texto puede venir
    del catálogo o del cliente y no dice de cuál de los dos obliga a quien lo
    lee a adivinar quién se comprometió a qué.
    """
    regla = _reglas(Path(reglas)).get(nc.origen, {}) if reglas else {}
    if regla and isinstance(regla.get("titulo"), dict) and isinstance(
            regla.get("remediacion"), dict):
        titulo = {i: f"[{nc.origen}] {regla['titulo'][i]}" for i in ("es", "en")}
        cuerpo = dict(regla["remediacion"])
        procedencia = {
            "es": (f"el texto de este encargo es el de la regla {nc.origen} del catálogo, "
                   f"escrito por una persona y contrastable con él"),
            "en": (f"this request's text is that of catalogue rule {nc.origen}, written by a "
                   f"person and checkable against it")}
        cliente = nc.descripcion
    else:
        # Sin regla detras no hay texto bilingue, y no se finge uno.
        titulo = {i: f"[{nc.origen}] {nc.descripcion[:70]}" for i in ("es", "en")}
        cuerpo = {i: "" for i in ("es", "en")}
        procedencia = {
            "es": (f"«{nc.origen}» no es una regla del catálogo, así que el texto es el que "
                   f"escribió el cliente y no se ha traducido"),
            "en": (f"«{nc.origen}» is not a catalogue rule, so the text is the client's own "
                   f"and has not been translated")}
        cliente = nc.descripcion
    return Encargo(
        no_conformidad_id=nc.id, titulo=titulo, cuerpo=cuerpo,
        obligacion_id=obligacion or regla.get("obligacion") or "ISO-10.2",
        control_id=nc.origen, severidad=severidad or regla.get("severidad", "media"),
        responsable=responsable, compromiso=compromiso,
        localizaciones=tuple(localizaciones), etiquetas=("actaira", nc.id),
        texto_del_cliente=cliente), procedencia
