"""La declaracion UE de conformidad del articulo 47, y la palabra BORRADOR.

LA DECISION QUE DEFINE ESTE MODULO
-----------------------------------
Los puntos 3 y 4 del Anexo V no son datos que se rellenan. Son AFIRMACIONES:
que la declaracion se expide bajo la exclusiva responsabilidad del proveedor, y
que el sistema es conforme con el Reglamento. Un programa no puede hacerlas.
Puede reunir todo lo demas, colocar las dos formulas donde van, y parar ahi.

Asi que este generador arma el documento entero y lo emite con la palabra
BORRADOR en el encabezado mientras no exista la respuesta del punto 8, que es
la firma con su lugar, su fecha, su nombre y su cargo. No hay bandera, ni
parametro, ni modo experto que quite esa palabra por otra via: se quita cuando
hay firma. Un software que emitiera una declaracion de conformidad firmada
seria exactamente el producto que este existe para no ser.

Y hay una segunda linea, mas fina: aunque haya firma, el documento NUNCA dice
que el sistema cumple. Dice que el proveedor declara que cumple, que es lo que
dice el Reglamento y no lo mismo. La diferencia entre las dos frases es todo el
negocio.

DE DONDE SALE CADA PUNTO
-------------------------
  derivada   del repositorio, con las fuentes citadas
  aportada   de una respuesta admisible y vigente del cuestionario
  formula    texto fijo del catalogo, que la firma asume
  ausente    con el motivo y con el identificador de la pregunta que falta

Un punto `aportada` cuya respuesta caduco no cuenta como aportada: sale ausente
diciendo que la respuesta esta rancia. Una declaracion sostenida por respuestas
viejas es el modo de fallo silencioso de todo este sector.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ..controles.motor import Arbol
from .anexoiv import EXTRACTORES

ESQUEMA = "actaira/anexo-v/v1"

AVISO_BORRADOR = {
    "es": "BORRADOR. No hay respuesta al punto 8 del Anexo V, que es la firma con su lugar, su fecha, "
          "el nombre y el cargo de quien firma y la persona en cuyo nombre lo hace. Sin ella esto no "
          "es una declaración UE de conformidad: es su contenido reunido y ordenado.",
    "en": "DRAFT. There is no answer to point 8 of Annex V, which is the signature with its place, its "
          "date, the name and position of the signatory and the person on whose behalf they sign. "
          "Without it this is not an EU declaration of conformity: it is its content gathered and ordered.",
}

NO_ES_UN_VEREDICTO = {
    "es": "Este documento recoge lo que el proveedor declara. No es, y no puede ser, una comprobación de "
          "que el sistema cumpla: eso lo afirma quien firma, bajo su exclusiva responsabilidad, y lo "
          "verifica en su caso un organismo notificado o una autoridad.",
    "en": "This document records what the provider declares. It is not, and cannot be, a check that the "
          "system complies: that is affirmed by the signatory, under their sole responsibility, and "
          "verified where applicable by a notified body or an authority.",
}


def _identificacion(arbol: Arbol | None, ctx: dict) -> tuple[dict | None, Any]:
    """El punto 1 reusa el extractor del Anexo IV, no escribe uno paralelo."""
    if arbol is None:
        return None, {"es": "no se dio repositorio del que sacar nombre y versión",
                      "en": "no repository given to take name and version from"}
    return EXTRACTORES["version_y_proveedor"](arbol, ctx)


def _respuesta_vigente(cuestionario: dict[str, Any] | None, pregunta_id: str) -> dict[str, Any] | None:
    for q in (cuestionario or {}).get("preguntas", []):
        if q["id"] == pregunta_id:
            return q if q.get("estado") == "contestada" else None
    return None


def _procede(punto: dict[str, Any], cuestionario: dict[str, Any] | None) -> bool:
    """El `si` del punto se evalua contra las respuestas, igual que en el cuestionario."""
    cond = punto.get("si")
    if not cond:
        return True
    q = _respuesta_vigente(cuestionario, cond["pregunta"])
    if q is None:
        # Sin respuesta vigente el punto NO entra, y esto es deliberado: entrar
        # por defecto meteria en la declaracion un texto que afirma conformidad
        # con el RGPD sin que nadie haya dicho que se tratan datos personales.
        return False
    valor = q.get("valor")
    lista = valor if isinstance(valor, (list, tuple)) else [valor]
    if "vale" in cond:
        return cond["vale"] in lista
    if "contiene" in cond:
        return cond["contiene"] in lista
    return True


def generar(catalogo_anexo: str | Path, arbol: Arbol | None,
            cuestionario: dict[str, Any] | None, cuando: date | None = None) -> dict[str, Any]:
    spec = json.loads(Path(catalogo_anexo).read_text(encoding="utf-8"))
    cuando = cuando or date.today()
    puntos: list[dict[str, Any]] = []
    firmado = False

    for p in spec["puntos"]:
        fila: dict[str, Any] = {"id": p["id"], "punto": p["punto"], "titulo": p["titulo"]}

        if not _procede(p, cuestionario):
            fila["procedencia"] = "no_procede"
            fila["motivo"] = {
                "es": f"este punto solo entra según lo contestado en {p['si']['pregunta']}",
                "en": f"this point only applies depending on the answer to {p['si']['pregunta']}"}
            puntos.append(fila)
            continue

        if p["origen"] == "formula":
            fila["procedencia"] = "formula"
            fila["texto"] = spec["formulas"][p["formula"]]
            fila["la_asume_quien_firma"] = True

        elif p["origen"] == "derivada":
            datos, fuentes = _identificacion(arbol, {})
            if datos is None:
                fila["procedencia"] = "ausente"
                fila["motivo"] = fuentes
            else:
                fila["procedencia"] = "derivada"
                fila["contenido"] = datos
                fila["de_donde"] = fuentes
                fila["tambien_humana"] = p.get("tambien_humana", False)

        else:                                    # aportada
            q = _respuesta_vigente(cuestionario, p["pregunta"])
            if q is None:
                fila["procedencia"] = "ausente"
                fila["falta_la_pregunta"] = p["pregunta"]
                fila["motivo"] = {
                    "es": f"falta una respuesta admisible y vigente a {p['pregunta']}",
                    "en": f"an admissible and current answer to {p['pregunta']} is missing"}
            else:
                fila["procedencia"] = "aportada"
                fila["contenido"] = q.get("valor")
                fila["respondida_por"] = q.get("respondida_por")
                fila["cargo"] = q.get("cargo")
                fila["cuando"] = q.get("cuando")
                fila["registro_id"] = q.get("registro_id")
                if p.get("es_la_firma"):
                    firmado = True
        puntos.append(fila)

    recuento: dict[str, int] = {}
    for f in puntos:
        recuento[f["procedencia"]] = recuento.get(f["procedencia"], 0) + 1

    return {
        "esquema": ESQUEMA,
        "referencia": spec["referencia"],
        "fecha": cuando.isoformat(),
        "firmado": firmado,
        "aviso": None if firmado else AVISO_BORRADOR,
        "no_es_un_veredicto": NO_ES_UN_VEREDICTO,
        "nota_de_firma": spec["nota_de_firma"],
        "recuento": recuento,
        "puntos": puntos,
    }


def _contenido(valor: Any) -> list[str]:
    """Una lista se imprime como lista, no como `['a', 'b']`.

    Parece cosmetico y no lo es: este documento se registra ante una autoridad,
    y un `repr` de Python dentro de una declaracion UE de conformidad dice a
    gritos que nadie lo leyo antes de firmarlo.
    """
    if isinstance(valor, bool):
        return ["si" if valor else "no"]
    if isinstance(valor, (list, tuple)):
        return [f"- {v}" for v in valor]
    return [str(valor)]


def a_markdown(doc: dict[str, Any], idioma: str = "es") -> str:
    cab = "Declaración UE de conformidad" if idioma == "es" else "EU declaration of conformity"
    marca = "" if doc["firmado"] else (" — BORRADOR" if idioma == "es" else " — DRAFT")
    lineas = [f"# {cab}{marca}", "", f"*{doc['referencia'][idioma]}* — {doc['fecha']}", ""]
    if doc["aviso"]:
        lineas += ["> **" + doc["aviso"][idioma] + "**", ""]
    lineas += ["> " + doc["no_es_un_veredicto"][idioma], ""]

    for p in doc["puntos"]:
        lineas.append(f"## {p['punto']}. {p['titulo'][idioma]}")
        if p["procedencia"] == "formula":
            lineas += ["", p["texto"][idioma], ""]
        elif p["procedencia"] == "derivada":
            lineas += ["", f"*{'DERIVADA del código' if idioma == 'es' else 'DERIVED from code'}*",
                       "", "```json", json.dumps(p["contenido"], ensure_ascii=False, indent=2), "```", ""]
        elif p["procedencia"] == "aportada":
            quien = f"{p.get('respondida_por')} ({p.get('cargo')})"
            lineas += ["", f"*{'APORTADA por' if idioma == 'es' else 'SUPPLIED by'} {quien}*", ""]
            lineas += _contenido(p.get("contenido")) + [""]
        elif p["procedencia"] == "no_procede":
            lineas += ["", f"*{'NO PROCEDE' if idioma == 'es' else 'NOT APPLICABLE'}*: "
                           + p["motivo"][idioma], ""]
        else:
            lineas += ["", f"*{'AUSENTE' if idioma == 'es' else 'MISSING'}*: " + p["motivo"][idioma], ""]
    return "\n".join(lineas)
