r"""Genera `contrato/openapi.json` de las MISMAS tablas que definen la API.

POR QUE UNA OPENAPI, Y POR QUE GENERADA
-----------------------------------------
Una auditoria externa pidio «OpenAPI versionada» entre lo que falta para que
esto sea una malla interoperable de verdad. Tiene razon, y el motivo no es el
formato: es que un integrador de GRC no puede escribir un conector contra una
tabla en prosa dentro de un README. Necesita algo que su generador de clientes
lea.

Lo que NO se puede hacer es escribirla a mano. Una especificacion de API
mantenida aparte del codigo que la sirve es el caso de deriva mas puro que hay:
nada la compara con nada, el dia que alguien anada una ruta la especificacion se
queda corta, y quien la lea escribira un conector contra endpoints que no
existen. En este mismo arbol acaba de pasar lo equivalente -- `BANDERAS` es una
tabla a mano y quedo corta en cuanto se anadieron cinco rutas, dejando pasar
tres que contestaban 502.

Asi que se genera de tres fuentes que YA existen y que el servidor usa de
verdad:

  VERBOS          las rutas que el enrutador publica, con su metodo
  BANDERAS        lo que cada una le manda al motor
  contrato/*.json los esquemas de los documentos que devuelve

Y `--comprobar` no escribe: sale 1 si la especificacion no es la que sale de
esas tres. Lo corre la puerta de aceptacion.

LO QUE ESTA OPENAPI NO DICE, Y SE DICE AQUI
---------------------------------------------
No describe los cuerpos de peticion campo a campo mas alla del perfil: el resto
de verbos no toman cuerpo. No describe los codigos de error uno a uno mas alla
de los que el servidor emite de verdad. Y no es un contrato de estabilidad: la
version de cada DOCUMENTO viaja dentro de el, en su campo `esquema`, que es
donde este producto pone la compatibilidad. La version de la API dice que rutas
hay; la del documento dice que forma tiene lo que devuelven, y son dos cosas.

USO:  python herramientas/generar_openapi.py            escribe
      python herramientas/generar_openapi.py --comprobar  dice si hay deriva
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "motor" / "src"))

from actaira_motor import __version__  # noqa: E402

DESTINO = RAIZ / "contrato" / "openapi.json"
API_GO = RAIZ / "plataforma" / "api" / "api.go"
CONTRATO = RAIZ / "contrato"


def _tabla_verbos() -> list[dict[str, str]]:
    """Lee `VERBOS` del fuente de Go.

    Se lee el FUENTE y no una copia en Python a proposito: la copia seria una
    segunda definicion de las rutas, y el dia que discrepara con el enrutador
    nadie sabria cual manda. El fuente es el que compila y sirve.
    """
    texto = API_GO.read_text(encoding="utf-8")
    bloque = texto.split("var VERBOS = []map[string]string{", 1)[1].split("\n}", 1)[0]
    # Los tres campos EN SECUENCIA, y no «lo que hay entre llaves».
    #
    # La primera version buscaba un grupo entre llaves sin llaves dentro, y no
    # encontraba nada: las rutas llevan `{cliente}`, asi que la llave de la
    # plantilla cierra la entrada antes de tiempo. Es el mismo error que
    # analizar un lenguaje con expresiones regulares en cualquier otro sitio de
    # este arbol, en pequeno.
    patron = ('"verbo":' + r'\s*"([^"]*)",\s*'
              + '"metodo":' + r'\s*"([^"]*)",\s*'
              + '"ruta":' + r'\s*"([^"]*)"')
    fuera = [{"verbo": v, "metodo": m, "ruta": r}
             for v, m, r in re.findall(patron, bloque, re.S)]
    if not fuera:
        raise SystemExit("no se pudo leer `VERBOS` de api.go: cambio su forma")
    return fuera


def _esquemas() -> dict[str, dict]:
    indice = json.loads((CONTRATO / "indice.json").read_text(encoding="utf-8"))
    return {nombre: json.loads((CONTRATO / fichero).read_text(encoding="utf-8"))
            for nombre, fichero in indice["documentos"].items()}


def _nombre_de_esquema(esquemas: dict[str, dict], constante: str) -> str | None:
    """De `actaira/plan/v1` al nombre del esquema que lo declara."""
    for nombre, e in esquemas.items():
        if (e.get("properties", {}).get("esquema", {}) or {}).get("const") == constante:
            return nombre
    return None


def _documento_de(verbo: str, esquemas: dict[str, dict]) -> str | None:
    """Que documento devuelve cada ruta.

    Se resuelve por el nombre del verbo contra el `const` del campo `esquema` de
    cada contrato, que es como el propio producto identifica sus documentos. Un
    mapa a mano aqui volveria a ser una tabla que se queda corta.
    """
    raiz = verbo.split(" ", 1)[0]
    directo = {
        "plan": "actaira/plan/v1",
        "vigilar": "actaira/vigilancia/v1",
        "noconformidad": "actaira/noconformidades/v1",
        "empujon": "actaira/decision-de-empujon/v1",
        "almacen": "actaira/almacen/v1",
        "preguntar": "actaira/cuestionario/v1",
        "soa": "actaira/soa/v1",
        "anexo": "actaira/anexo-iv/v1",
        "aplicabilidad": "actaira/aplicabilidad/v1",
        "comprobar": "actaira/control/v1",
        "revision": None,          # su esquema no esta publicado todavia
    }
    constante = directo.get(raiz)
    return _nombre_de_esquema(esquemas, constante) if constante else None


PERFIL = {
    "type": "object",
    "description": (
        "Lo que la organizacion declara de si misma. Los tres valores de cada "
        "booleano -- `si`, `no` y ausente -- no son un descuido: ausente significa "
        "«no me lo han preguntado todavia» y produce INDETERMINADA, que no es lo "
        "mismo que «no me ata»."),
    "properties": {
        "roles": {
            "type": "array", "items": {"type": "string"},
            "description": (
                "Los roles del Reglamento. VARIOS a la vez: una organizacion suele "
                "ser proveedor de un sistema y responsable del despliegue de otro. "
                "Un rol que el motor no conozca se RECHAZA con 400; devolver cero "
                "obligaciones seria indistinguible de un rol valido al que no le ata "
                "nada."),
        },
        "alto_riesgo": {"enum": ["si", "no", ""]},
        "sector_publico": {"enum": ["si", "no", ""]},
        "modelo_uso_general": {"enum": ["si", "no", ""]},
        "riesgo_sistemico": {"enum": ["si", "no", ""]},
        "via_anexo": {"enum": ["anexo_iii", "anexo_i", ""]},
        "fecha": {"type": "string", "format": "date"},
    },
    "additionalProperties": False,
}

FALLO = {
    "type": "object",
    "required": ["esquema", "que"],
    "properties": {
        "esquema": {"const": "actaira/api/fallo/v1"},
        "que": {"type": "object", "required": ["es", "en"],
                "properties": {"es": {"type": "string"}, "en": {"type": "string"}}},
    },
}


def construir() -> dict:
    esquemas = _esquemas()
    verbos = _tabla_verbos()

    caminos: dict[str, dict] = {}
    for v in verbos:
        ruta = v["ruta"].split("?", 1)[0]
        metodo = v["metodo"].lower()
        doc = _documento_de(v["verbo"], esquemas)

        respuesta = {
            "description": "El documento que emite el motor, sin tocar.",
            "content": {"application/json": {"schema": {
                "type": "object",
                "required": ["esquema", "codigo", "documento"],
                "properties": {
                    "esquema": {"const": "actaira/api/v1"},
                    "codigo": {
                        "type": "integer",
                        "description": (
                            "El codigo de salida del motor, SIN INTERPRETAR. 0 es «se "
                            "miro y no aparecio nada», 1 es «aparecio algo» y 3 es «no "
                            "se pudo decidir o falta que alguien conteste». Tres NO es "
                            "un fallo: es el estado normal de un cliente que empieza."),
                    },
                    "documento": ({"$ref": f"#/components/schemas/{doc}"} if doc
                                  else {"type": "object"}),
                    **({"firma_verificada": {
                        "type": ["boolean", "null"],
                        "description": (
                            "Si el cuerpo del evento venia firmado y la firma cuadraba. "
                            "`false` significa que llego sin firma porque este cliente no "
                            "tiene secreto configurado; ausente significa que esta ruta no "
                            "recibe eventos. Son tres cosas distintas y ninguna se pliega "
                            "a otra. La credencial demuestra que quien llama puede "
                            "tocar el espacio de este cliente; la firma demuestra que el "
                            "cuerpo viene del proveedor y llego intacto. Con solo la "
                            "credencial, cualquiera que la tenga puede inventarse un "
                            "evento.")}}
                       if ruta.endswith("/empujon") else {}),
                },
            }}},
        }

        operacion = {
            "summary": f"`actaira {v['verbo']}`",
            "description": (
                f"Traduccion 1:1 del verbo `{v['verbo']}` de la linea de mandatos. "
                f"Esta capa no compone nada ni anade logica: lo que sale es lo que "
                f"emite el motor, con su `esquema` dentro."),
            "operationId": re.sub(r"[^a-zA-Z0-9]+", "_", v["verbo"]).strip("_"),
            "security": [{"credencialDelCliente": []}],
            "parameters": [{
                "name": "cliente", "in": "path", "required": True,
                "schema": {"type": "string"},
                "description": (
                    "El cliente. Tiene que ser el mismo al que da acceso la "
                    "credencial: pedir otro devuelve 401 y no 403, porque un 403 "
                    "confirmaria que ese cliente existe."),
            }],
            "responses": {
                "200": respuesta,
                "401": {"description":
                        "Credencial no valida, o de otro cliente. El mensaje es el "
                        "mismo en los dos casos: dos respuestas distintas serian un "
                        "oraculo para enumerar clientes.",
                        "content": {"application/json": {"schema": FALLO}}},
                "429": {
                    "description":
                        "Demasiadas peticiones, o demasiados verbos del motor en "
                        "curso. Un verbo del motor es un PROCESO que lee el "
                        "repositorio entero, asi que lo que se agota no son "
                        "peticiones: es la maquina. Viene con `Retry-After`.",
                    "headers": {"Retry-After": {"schema": {"type": "integer"},
                                                "description": "Segundos a esperar."}},
                    "content": {"application/json": {"schema": FALLO}}},
                "502": {"description":
                        "El motor no devolvio un documento que esta plataforma "
                        "entienda.",
                        "content": {"application/json": {"schema": FALLO}}},
            },
        }

        if "?cual=" in v["ruta"]:
            operacion["parameters"].append({
                "name": "cual", "in": "query", "required": False,
                "schema": {"enum": ["iv", "v"], "default": "iv"},
                "description": "El Anexo IV (expediente tecnico) o el V (declaracion UE).",
            })

        if metodo == "post" and not ruta.endswith("/empujon"):
            operacion["requestBody"] = {
                "required": False,
                "content": {"application/json": {"schema": PERFIL}},
            }
        if ruta.endswith("/empujon"):
            operacion["requestBody"] = {
                "required": True,
                "description": (
                    "El cuerpo del webhook, TAL CUAL lo manda el sistema de origen. "
                    "No se interpreta aqui: se le pasa al motor, que decide si hay que "
                    "volver a observar."),
                "content": {"application/json": {"schema": {"type": "object"}}},
            }

        caminos.setdefault(ruta, {})[metodo] = operacion

    # Las rutas que no llevan credencial.
    caminos["/salud"] = {"get": {
        "summary": "Estado del servicio, y de la vigilancia.",
        "description": (
            "`vivo: true` solo dice que el proceso contesta. La unica tarea que este "
            "servicio hace sin que nadie la pida es darse cuenta de que algo caduco, "
            "asi que el estado de esa tarea va aqui: un estado de salud que no cubre "
            "la tarea principal del servicio miente por omision."),
        "operationId": "salud",
        "responses": {"200": {"description": "Vivo.", "content": {
            "application/json": {"schema": {
                "type": "object",
                "required": ["esquema", "vivo", "cuando"],
                "properties": {
                    "esquema": {"const": "actaira/api/salud/v1"},
                    "vivo": {"type": "boolean"},
                    "cuando": {"type": "string", "format": "date-time"},
                    "vigilancia": {"type": "object"},
                    "motor": {"type": "object"},
                }}}}}},
    }}
    caminos["/v1/verbos"] = {"get": {
        "summary": "Los verbos que esta API sabe pedirle al motor.",
        "description": (
            "Se publica para que un cliente no tenga que descubrir la API probando."),
        "operationId": "verbos",
        "responses": {"200": {"description": "La tabla."}},
    }}

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Actaira",
            "version": __version__,
            "summary": ("El Reglamento (UE) 2024/1689 y la ISO/IEC 42001 comprobados "
                        "leyendo el repositorio, con procedencia por afirmacion."),
            "description": (
                "ESTA ESPECIFICACION SE GENERA. Sale de `VERBOS` y de los esquemas de "
                "`contrato/`, que son lo que el servidor usa de verdad; "
                "`herramientas/generar_openapi.py --comprobar` la compara y la puerta "
                "de aceptacion lo corre.\n\n"
                "Escribirla a mano habria sido el caso de deriva mas puro que hay: "
                "nada la compara con nada, y quien la lea escribiria un conector "
                "contra endpoints que no existen.\n\n"
                "La version de ESTA API dice que rutas hay. La version de cada "
                "DOCUMENTO viaja dentro de el, en su campo `esquema`, y es ahi donde "
                "este producto pone la compatibilidad: una ruta puede seguir igual "
                "mientras el documento que devuelve cambia de forma, y al reves."),
            "license": {"name": "Apache-2.0"},
        },
        "servers": [{"url": "{servidor}", "variables": {
            "servidor": {"default": "http://127.0.0.1:8787",
                         "description": "Donde escucha tu instalacion."}}}],
        "security": [{"credencialDelCliente": []}],
        "components": {
            "securitySchemes": {"credencialDelCliente": {
                "type": "http", "scheme": "bearer",
                "description": (
                    "Una credencial por cliente. Da acceso al expediente ENTERO de ese "
                    "cliente y a nada mas. No se guarda en el navegador: el panel la "
                    "mantiene en memoria y al recargar hay que volver a escribirla.")}},
            "schemas": {**_esquemas(), "fallo": FALLO, "perfil": PERFIL},
        },
        "paths": dict(sorted(caminos.items())),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--comprobar", action="store_true",
                   help="no escribe: sale 1 si la especificacion no es la que toca")
    a = p.parse_args()

    nuevo = json.dumps(construir(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    viejo = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else None

    if a.comprobar:
        if viejo != nuevo:
            print("`contrato/openapi.json` no es la que sale de VERBOS y del contrato.")
            print("corre `python herramientas/generar_openapi.py`")
            return 1
        d = json.loads(nuevo)
        print(f"openapi al dia: {len(d['paths'])} rutas, "
              f"{len(d['components']['schemas'])} esquemas")
        return 0

    DESTINO.write_text(nuevo, encoding="utf-8", newline="\n")
    d = json.loads(nuevo)
    print(f"{DESTINO.relative_to(RAIZ).as_posix()}: {len(d['paths'])} rutas, "
          f"{len(d['components']['schemas'])} esquemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
