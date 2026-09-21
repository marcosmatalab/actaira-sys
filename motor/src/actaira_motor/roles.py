r"""Los ROLES del Reglamento, en UN solo sitio, y la negativa a inventarse uno.

QUE ESTABA ROTO, Y POR QUE ERA LO MAS GRAVE DEL PRODUCTO
----------------------------------------------------------
Habia cuatro vocabularios de roles y ninguno completo:

  catalogo y motor   proveedor, responsable_despliegue, importador, distribuidor,
                     representante_autorizado, fabricante_producto
  API en Go          ...pero `responsable_del_despliegue` y `fabricante_de_productos`
  panel en JavaScript  los de Go
  consola            los del motor

El panel manda `responsable_del_despliegue`. La API en Go lo valida contra su
propia lista -- que tiene el mismo error -- y lo deja pasar. El motor recibe un
rol que no conoce, no encuentra ninguna obligacion que ate a ese nombre, y
devuelve CERO obligaciones aplicables y CUARENTA Y OCHO no aplicables.

Reproducido:

    responsable_despliegue       ->  ata= 13   no_ata= 34
    responsable_del_despliegue   ->  ata=  0   no_ata= 48
    fabricante_producto          ->  ata=  1   no_ata= 47
    fabricante_de_productos      ->  ata=  0   no_ata= 48
    rol_inventado_zzz            ->  ata=  0   no_ata= 48

La ultima linea es la que importa mas que el desajuste. Un rol que no existe en
absoluto produce exactamente la misma respuesta que un rol valido al que no le
ata nada: «no te ata ninguna obligacion». El motor trataba «no se quien eres»
como «no te toca nada», y se lo decia a un cliente con la misma cara con la que
le dice todo lo demas. Para un producto cuya unica promesa es decir que ata a
quien, eso no es un fallo de validacion: es la afirmacion mas peligrosa que
puede emitir.

Y ademas faltaba un rol. `proveedor_modelo` -- el proveedor de un modelo de uso
general -- lo usan cinco obligaciones y nueve articulos del catalogo, y no
estaba en la lista de roles declarada de `obligaciones.json`. Un rol usado y no
declarado no se puede ofrecer en ninguna pantalla, asi que no habia forma de
que un proveedor de GPAI dijera que lo es.

COMO SE ARREGLA, Y POR QUE NO BASTA CON RENOMBRAR
---------------------------------------------------
Renombrar en tres sitios arregla hoy y vuelve a romperse en cuanto alguien
anada el cuarto. Lo que hace falta es que solo haya UNA definicion y que los
demas la lean:

  - Aqui viven los identificadores y sus nombres en los dos idiomas.
  - `plataforma/api/roles_generado.go` y `panel/roles.json` se GENERAN desde
    aqui con `herramientas/generar_roles.py`, y son lo que leen el lado Go y
    el panel. No se escriben a mano, y una puerta regenera y compara.
  - `exigir_conocidos` revienta con el rol delante en vez de devolver cero.

La regla de fondo es la de esta casa: entre no contestar y contestar que no te
ata nada, no contestar. Un rol desconocido es «no se», y «no se» no se parece
en nada a «no».
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROLES: dict[str, dict[str, str]] = {
    "proveedor": {
        "es": "proveedor",
        "en": "provider",
        "articulo": "3.3",
        "definicion_es": "quien desarrolla un sistema de IA, o lo manda desarrollar, y lo "
                         "introduce en el mercado o lo pone en servicio con su nombre o marca",
        "definicion_en": "who develops an AI system, or has one developed, and places it on "
                         "the market or puts it into service under their own name or trademark",
    },
    "responsable_despliegue": {
        "es": "responsable del despliegue",
        "en": "deployer",
        "articulo": "3.4",
        "definicion_es": "quien utiliza un sistema de IA bajo su propia autoridad, salvo uso "
                         "personal no profesional",
        "definicion_en": "who uses an AI system under their own authority, except for personal "
                         "non-professional use",
    },
    "representante_autorizado": {
        "es": "representante autorizado",
        "en": "authorised representative",
        "articulo": "3.5",
        "definicion_es": "quien, establecido en la Union, recibe mandato escrito de un proveedor "
                         "para cumplir sus obligaciones en su nombre",
        "definicion_en": "who, established in the Union, has a written mandate from a provider "
                         "to carry out their obligations on their behalf",
    },
    "importador": {
        "es": "importador",
        "en": "importer",
        "articulo": "3.6",
        "definicion_es": "quien, establecido en la Union, introduce en el mercado un sistema de "
                         "IA que lleva el nombre de una persona establecida fuera",
        "definicion_en": "who, established in the Union, places on the market an AI system "
                         "bearing the name of a person established outside",
    },
    "distribuidor": {
        "es": "distribuidor",
        "en": "distributor",
        "articulo": "3.7",
        "definicion_es": "quien, en la cadena de suministro y sin ser proveedor ni importador, "
                         "comercializa un sistema de IA",
        "definicion_en": "who, in the supply chain and being neither provider nor importer, "
                         "makes an AI system available on the market",
    },
    "fabricante_producto": {
        "es": "fabricante de productos",
        "en": "product manufacturer",
        "articulo": "25.3",
        "definicion_es": "quien introduce en el mercado un producto del Anexo I con un sistema "
                         "de IA de alto riesgo como componente de seguridad, con su nombre",
        "definicion_en": "who places on the market an Annex I product with a high-risk AI "
                         "system as a safety component, under their own name",
    },
    "proveedor_modelo": {
        "es": "proveedor de modelo de uso general",
        "en": "general-purpose AI model provider",
        "articulo": "53",
        "definicion_es": "quien introduce en el mercado un modelo de IA de uso general, con o "
                         "sin riesgo sistemico",
        "definicion_en": "who places on the market a general-purpose AI model, with or without "
                         "systemic risk",
        "nota_es": "Lo usan cinco obligaciones y nueve articulos del catalogo, y NO estaba en la "
                   "lista de roles declarada. Un rol usado y no declarado no se puede ofrecer en "
                   "ninguna pantalla, asi que no habia forma de que un proveedor de modelo de "
                   "uso general dijera que lo es.",
        "nota_en": "Five obligations and nine articles of the catalogue use it, and it was NOT "
                   "in the declared role list. A role that is used but not declared cannot be "
                   "offered on any screen, so there was no way for a general-purpose model "
                   "provider to say they are one.",
    },
}

CANONICOS: frozenset[str] = frozenset(ROLES)

ACTORES_ESPECIALES: frozenset[str] = frozenset({"todos"})
"""Lo que puede aparecer en el campo `actores` de un ARTICULO y no es un rol.

`todos` no es un rol: es un cuantificador sobre ellos. Lo llevan el articulo 2
(ambito de aplicacion), el 3 (definiciones) y el 113 (entrada en vigor), que no
atan a un papel concreto de la cadena de suministro sino a cualquiera.

Se declara aparte y no se mete en `ROLES` a proposito. Metido ahi apareceria en
el desplegable del panel, y «todos» no es algo que una organizacion pueda ser:
elegirlo no significaria nada y el motor no sabria que hacer con ello. La
distincion cuesta tres lineas y evita que la puerta que comprueba el
vocabulario tenga que mirar para otro lado, que es como las puertas se aflojan.

Una OBLIGACION nunca puede llevarlo: sus `roles` tienen que ser canonicos, o el
motor no podria decidir a quien ata.
"""


class RolDesconocido(ValueError):
    """Un rol que no esta en el vocabulario. NO es «no te ata nada».

    Es una excepcion propia porque quien la recoge tiene que hacer algo
    distinto que con un perfil valido y vacio: aqui no se ha resuelto la
    aplicabilidad de nadie, y presentarla como si se hubiera resuelto es lo que
    hacia el motor antes.
    """


def exigir_conocidos(roles) -> frozenset[str]:
    """Devuelve los roles si los conoce todos, y REVIENTA si no.

    Se llama en el borde -- al construir un `Perfil` -- y no en cada regla: un
    rol invalido tiene que parar la ejecucion entera antes de que produzca un
    documento, porque un documento producido es un documento que alguien lee.

    El mensaje trae los roles validos. Un error que dice «rol desconocido» y no
    dice cuales hay obliga a quien lo lee a buscar en el codigo, y quien busca
    en el codigo acaba copiando el nombre equivocado, que es exactamente como
    empezo esto.
    """
    roles = frozenset(roles)
    fuera = sorted(roles - CANONICOS)
    if fuera:
        raise RolDesconocido(
            f"rol o roles desconocidos: {fuera}. Los del Reglamento son "
            f"{sorted(CANONICOS)}. No se resuelve la aplicabilidad de un rol que no se "
            f"conoce: devolver «no te ata ninguna obligacion» seria indistinguible de "
            f"un perfil valido al que de verdad no le ata nada.")
    return roles


def nombres(idioma: str = "es") -> dict[str, str]:
    """Como se lee cada rol. Para las pantallas, que NO tienen su propia lista."""
    return {k: v[idioma] for k, v in ROLES.items()}


def a_contrato() -> dict[str, Any]:
    """El documento que se publica en `contrato/roles.json`.

    Es la unica forma que tienen el lado Go y las dos pantallas de saber que
    roles hay. Antes cada uno llevaba su lista escrita a mano, y dos de las
    cuatro estaban mal.
    """
    return {
        "esquema": "actaira/roles/v1",
        "nota": {
            "es": "Generado desde `motor/src/actaira_motor/roles.py`. NO se edita a mano. "
                  "Había cuatro listas de roles escritas por separado y dos estaban mal: el "
                  "panel mandaba `responsable_del_despliegue`, la API lo validaba contra su "
                  "propia lista equivocada y lo dejaba pasar, y el motor devolvia cero "
                  "obligaciones aplicables a un responsable del despliegue de verdad.",
            "en": "Generated from `motor/src/actaira_motor/roles.py`. NOT edited by hand. There "
                  "were four separately written role lists and two were wrong: the panel sent "
                  "`responsable_del_despliegue`, the API validated it against its own wrong "
                  "list and let it through, and the engine returned zero applicable obligations "
                  "to a real deployer.",
        },
        "roles": [
            {"id": k, "articulo": v["articulo"],
             "nombre": {"es": v["es"], "en": v["en"]},
             "definicion": {"es": v["definicion_es"], "en": v["definicion_en"]}}
            for k, v in ROLES.items()
        ],
    }


def escribir_contrato(destino: str | Path) -> Path:
    destino = Path(destino)
    destino.write_text(
        json.dumps(a_contrato(), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    return destino
