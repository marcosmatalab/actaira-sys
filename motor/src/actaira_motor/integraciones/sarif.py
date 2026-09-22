"""SARIF 2.1.0, para que los hallazgos salgan donde el equipo ya mira.

POR QUE SARIF Y NO UN INFORME PROPIO
--------------------------------------
Un informe bonito en un panel que hay que abrir a proposito lo lee el
responsable de cumplimiento una vez al trimestre. Un hallazgo en SARIF sale en
la pestana Security de GitHub, en la revision del pull request, y en el IDE del
que escribio la linea, el dia que la escribio. La diferencia entre las dos
cosas es si el defecto se arregla o se documenta.

Es ademas la unica forma de que esto no sea otra herramienta de GRC: el
hallazgo llega a quien puede arreglarlo, con la remediacion escrita al lado, y
no a quien tiene que justificarlo despues.

LO QUE NO SE INVENTA
---------------------
El motor sabe en QUE FICHERO esta el problema y casi nunca en que linea, asi
que no se escribe una linea. SARIF permite una localizacion con solo el
fichero, y un resultado sin fichero cuando la afirmacion es sobre el
repositorio entero -- "no existe ninguna evaluacion" no esta en ningun sitio
concreto. Apuntar a la linea 1 para que quede bonito seria exactamente la
clase de precision falsa que este producto existe para no emitir.
"""
from __future__ import annotations

from typing import Any

from .. import __version__

ESQUEMA = "https://json.schemastore.org/sarif-2.1.0.json"

NIVEL = {"alta": "error", "media": "warning", "baja": "note"}

SIN_FICHERO = ("(el repositorio entero)",)


def _regla(h: dict[str, Any], obligacion: dict[str, Any], idioma: str) -> dict[str, Any]:
    art = obligacion.get("articulo", "?")
    return {
        "id": h["regla_id"],
        "name": h["regla_id"].replace("-", ""),
        "shortDescription": {"text": obligacion["titulo"][idioma]},
        "fullDescription": {"text": h["remediacion"][idioma]},
        "help": {
            "text": h["remediacion"][idioma],
            "markdown": (f"**{h['regla_id']}** — {obligacion['titulo'][idioma]}\n\n"
                         f"{h['remediacion'][idioma]}\n\n"
                         f"_Reglamento (UE) 2024/1689, artículo {art} · "
                         f"paquete `{h['paquete']}` v{h['regla_version']}, {h['autor']}_"),
        },
        "defaultConfiguration": {"level": NIVEL.get(h["severidad"], "warning")},
        "properties": {
            "tags": ["ai-act", f"articulo-{art}", h["paquete"], obligacion.get("nivel", "")],
            "obligacion": obligacion["id"],
            "iso42001": obligacion.get("iso42001", []),
        },
    }


def exportar(plan: dict[str, Any], version_motor: str | None = None,
             idioma: str = "es") -> dict[str, Any]:
    """Convierte un plan en SARIF. Una regla por regla que disparo, no por catalogo.

    Declarar las 27 reglas del catalogo cuando solo dispararon 3 llenaria la
    pestana de Security de ruido gris. SARIF admite declarar solo las que
    aparecen y es lo correcto.
    """
    # La version del motor NO se escribe a mano aqui. Estaba puesta como
    # `"0.8.0"` por omision y el paquete iba ya por la 0.14: cualquiera que
    # llamara sin pasarla publicaba un SARIF que atribuia sus hallazgos a una
    # version del analizador que no los produjo. El campo existe justo para
    # que un auditor pueda volver a correr lo mismo, asi que mentir ahi le
    # quita al documento la propiedad por la que se publica.
    if version_motor is None:
        version_motor = __version__

    reglas: dict[str, dict[str, Any]] = {}
    resultados: list[dict[str, Any]] = []
    ilegibles = plan.get("ilegibles", [])

    for linea in plan.get("lineas", []):
        obligacion = {"id": linea["obligacion_id"], "articulo": linea["articulo"],
                      "titulo": linea["titulo"], "nivel": linea["nivel"],
                      "iso42001": linea.get("iso42001", [])}
        for h in linea.get("hallazgos", []):
            if h["regla_id"] not in reglas:
                reglas[h["regla_id"]] = _regla(h, obligacion, idioma)
            res: dict[str, Any] = {
                "ruleId": h["regla_id"],
                "level": NIVEL.get(h["severidad"], "warning"),
                "message": {"text": h["remediacion"][idioma]},
                "partialFingerprints": {
                    "actaira/v1": f"{h['regla_id']}:{h['localizacion']}"},
            }
            if h["localizacion"] not in SIN_FICHERO:
                res["locations"] = [{"physicalLocation": {
                    "artifactLocation": {"uri": h["localizacion"].split(" (")[0]}}}]
            else:
                res["message"]["text"] = (
                    ("Sobre el repositorio entero: " if idioma == "es"
                     else "About the whole repository: ") + res["message"]["text"])
            resultados.append(res)

    return {
        "$schema": ESQUEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "Actaira",
                # Los dos campos, y no solo `semanticVersion`: la especificacion
                # los define aparte y las herramientas que consumen SARIF leen
                # uno u otro segun cual. Publicar solo uno deja el documento sin
                # version para la mitad de sus lectores.
                "version": version_motor,
                "semanticVersion": version_motor,
                "informationUri": "https://actaira.com",
                "rules": [reglas[k] for k in sorted(reglas)],
            }},
            "results": resultados,
            "invocations": [{
                # NO es `True` a secas. Estaba clavado, asi que un barrido en el
                # que media docena de ficheros no se pudieron abrir se publicaba
                # como ejecucion correcta y sin hallazgos en esa parte del arbol.
                # Quien lee SARIF usa este campo exactamente para saber si puede
                # fiarse del silencio.
                "executionSuccessful": not ilegibles,
                "toolExecutionNotifications": [
                    {"level": "warning",
                     "message": {"text": (f"{x['fichero']}: {x['por_que']}")},
                     "descriptor": {"id": "actaira/ilegible"}}
                    for x in ilegibles],
                "properties": {
                    "ficheros_no_leidos": len(ilegibles),
                    "nota": {
                        "es": "Cada resultado cita el paquete de reglas, su versión y su autor. "
                              "Actaira no emite un veredicto de cumplimiento: emite lo que se "
                              "comprobo leyendo bytes y lo que no se pudo comprobar.",
                        "en": "Every result cites the rule pack, its version and its author. "
                              "Actaira does not issue a compliance verdict: it issues what was "
                              "checked by reading bytes and what could not be checked."}},
            }],
        }],
    }
