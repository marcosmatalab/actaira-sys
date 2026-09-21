"""Un remediador y muchos sistemas de tickets, porque el que cambia es el perfil.

POR QUE UNO Y NO TRES
-----------------------
El mismo argumento que el conector de git. Jira, Linear y las incidencias de
GitHub son tres productos distintos, pero para lo único que aquí hace falta
-crear un elemento de trabajo y leer en qué columna está- los tres son una
petición HTTP con un cuerpo JSON y una respuesta JSON. Escribir tres
integraciones para usar la misma primitiva habría dado tres veces el
mantenimiento y tres sitios donde arreglar el mismo fallo.

Lo que SÍ es distinto entre ellos son los nombres de los campos y la forma del
cuerpo, y eso es un dato: un perfil JSON con plantillas y rutas. Añadir un
sistema nuevo es un fichero y sus pruebas, no un despliegue. Que Linear hable
GraphQL y Jira REST no cambia nada: GraphQL es una petición POST con un cuerpo
JSON y una respuesta JSON, que es exactamente lo que el perfil describe.

LAS CREDENCIALES NO LAS GESTIONA ESTE MODULO
----------------------------------------------
Se leen del entorno, con el nombre que el perfil diga, y no se guardan en
ninguna parte ni salen en ningún mensaje de error. Un producto de cumplimiento
que se guarda los tokens de sus clientes se convierte en el objetivo más
valioso de su propia cadena de suministro, y la manera de no serlo es no
tenerlos.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from . import red
from pathlib import Path
from typing import Any, Callable

from ..conectores.contrato import redactar
from .contrato import Delegacion, Encargo, LimiteDelRemediador

PERFILES = Path(__file__).parent / "perfiles"
LIMITE_SEGUNDOS = 30


class ErrorDelRemediador(Exception):
    """Falla, y con un mensaje del que ya se han quitado los secretos."""


def _ruta(d: Any, camino: str) -> Any:
    """Un valor dentro de una respuesta, por una ruta con puntos e índices."""
    for paso in camino.split("."):
        if paso == "":
            continue
        try:
            d = d[int(paso)] if paso.lstrip("-").isdigit() else d[paso]
        except (KeyError, IndexError, TypeError, ValueError):
            return None
    return d


def _rellenar(plantilla: Any, valores: dict[str, str]) -> Any:
    """Sustituye {campo} en cualquier hoja de texto de la plantilla.

    Recursivo y sin `eval` ni `format`: `format` habría dejado que una llave
    dentro del texto del cliente -una remediación que mencione `{modelo}`-
    reventara la llamada o, peor, leyera un atributo.
    """
    if isinstance(plantilla, str):
        out = plantilla
        for clave, valor in valores.items():
            out = out.replace("{" + clave + "}", valor)
        return out
    if isinstance(plantilla, dict):
        return {k: _rellenar(v, valores) for k, v in plantilla.items()}
    if isinstance(plantilla, list):
        return [_rellenar(v, valores) for v in plantilla]
    return plantilla


def cargar_perfil(nombre_o_ruta: str) -> dict[str, Any]:
    ruta = Path(nombre_o_ruta)
    if not ruta.is_file():
        ruta = PERFILES / f"{nombre_o_ruta}.json"
    if not ruta.is_file():
        hay = sorted(p.stem for p in PERFILES.glob("*.json"))
        raise ErrorDelRemediador(
            f"no hay perfil {nombre_o_ruta!r}. Los que vienen de serie: {', '.join(hay)}. "
            "Uno nuevo es un fichero JSON, no un despliegue.")
    perfil = json.loads(ruta.read_text(encoding="utf-8"))
    faltan = [c for c in ("sistema", "abrir", "consultar", "credencial") if c not in perfil]
    if faltan:
        raise ErrorDelRemediador(f"{ruta.name}: le faltan {faltan}")
    return perfil


def _http(peticion: urllib.request.Request) -> Any:
    try:
        # `red.pedir` y no `urlopen` a secas. Esta peticion lleva la credencial
        # del cliente en una cabecera, asi que antes de salir hay que saber a
        # donde va: ver `red.py`. Lo que hacia esta linea era mandarla a donde
        # dijera `--destino`, siguiendo redirecciones y sin techo de lectura.
        crudo = red.pedir(peticion, LIMITE_SEGUNDOS)
    except red.DestinoNoPermitido as e:
        raise ErrorDelRemediador(redactar(str(e))) from None
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")[:300]
        raise ErrorDelRemediador(
            redactar(f"{peticion.get_method()} {peticion.full_url} -> {e.code}: {cuerpo}")
        ) from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise ErrorDelRemediador(redactar(f"no se pudo hablar con el sistema: {e}")) from None
    try:
        return json.loads(crudo) if crudo.strip() else {}
    except json.JSONDecodeError:
        raise ErrorDelRemediador("la respuesta no es JSON: este perfil no encaja") from None


class RemediadorHttp:
    """Habla con lo que el perfil diga. El transporte se puede sustituir.

    `transporte` existe para las pruebas y no como adorno: una integración que
    sólo se prueba contra un servidor de verdad no se prueba nunca en
    integración continua, y entonces lo único que se comprueba de ella es que
    importa.
    """

    nombre = "http"
    version = "1.0.0"

    def __init__(self, destino: str, perfil: dict[str, Any],
                 transporte: Callable[[urllib.request.Request], Any] = _http) -> None:
        self.destino = destino
        self.perfil = perfil
        self.sistema = perfil["sistema"]
        self._transporte = transporte

    @staticmethod
    def resuelve(destino: str) -> bool:
        """Si ESTE remediador es el que atiende ese destino.

        Sigue admitiendo `http://` aqui a proposito: `resuelve` solo decide QUE
        remediador se usa, y responder que no a un `http://` haria que el
        producto contestara «no hay remediador para ese destino», que es un
        mensaje falso. Quien rechaza el texto plano es `red.comprobar`, en el
        momento de mandar, y ahi el mensaje dice lo que de verdad pasa: que a
        esa peticion se le adjunta la credencial del cliente.
        """
        return bool(re.match(r"^https?://", destino))

    @classmethod
    def desde(cls, destino: str, perfil: str = "", **ajustes: Any) -> "RemediadorHttp":
        if not perfil:
            raise ErrorDelRemediador(
                "un destino de red necesita un perfil: --perfil jira, --perfil linear, "
                "--perfil github, o la ruta de uno tuyo.")
        return cls(destino, cargar_perfil(perfil),
                   ajustes.get("transporte") or _http)

    # -- credenciales: del entorno, y de ningun otro sitio ------------------

    def _cabeceras(self) -> dict[str, str]:
        variable = self.perfil["credencial"]["variable"]
        valor = os.environ.get(variable, "")
        if not valor:
            raise ErrorDelRemediador(
                f"falta la variable de entorno {variable}. Este modulo NO guarda "
                "credenciales: se leen del entorno de quien ejecuta y no se escriben en "
                "ninguna parte.")
        plantilla = self.perfil["credencial"]["cabeceras"]
        return {k: v.replace("{credencial}", valor) for k, v in plantilla.items()}

    def _llamar(self, paso: dict[str, Any], valores: dict[str, str]) -> Any:
        cuerpo = _rellenar(paso.get("cuerpo", {}), valores)
        url = _rellenar(paso["url"], valores)
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo else None
        cabeceras = {"Content-Type": "application/json", **self._cabeceras()}
        peticion = urllib.request.Request(
            url, data=datos, headers=cabeceras, method=paso.get("metodo", "POST"))
        return self._transporte(peticion)

    # -- el contrato --------------------------------------------------------

    def abrir(self, encargo: Encargo, idioma: str = "es") -> Delegacion:
        valores = {
            "destino": self.destino.rstrip("/"),
            "titulo": encargo.titulo[idioma],
            "cuerpo": encargo.texto(idioma),
            "responsable": encargo.responsable,
            "compromiso": encargo.compromiso,
            "severidad": encargo.severidad,
            "nc": encargo.no_conformidad_id,
            "etiquetas": ", ".join(encargo.etiquetas),
        }
        r = self._llamar(self.perfil["abrir"], valores)
        ref = _ruta(r, self.perfil["abrir"]["ruta_referencia"])
        if not ref:
            raise ErrorDelRemediador(
                f"{self.sistema}: la respuesta no trae la referencia del ticket en "
                f"{self.perfil['abrir']['ruta_referencia']!r}. Sin referencia no hay vuelta: "
                "la no conformidad quedaria delegada en algo que no se puede consultar.")
        url = _ruta(r, self.perfil["abrir"].get("ruta_url", "")) or ""
        return Delegacion(
            sistema=self.sistema, referencia=str(ref), url=str(url),
            no_conformidad_id=encargo.no_conformidad_id,
            estado_externo=str(_ruta(r, self.perfil["abrir"].get("ruta_estado", "")) or ""),
            detalles={"destino": self.destino})

    def consultar(self, delegacion: Delegacion) -> Delegacion:
        """Lo último que dice el otro sistema. CRUDO, y sin traducir aquí.

        Traducir en el remediador habría metido la doctrina de esta casa -que
        ningún estado externo cierra una no conformidad- dentro del código de
        integración de un tercero, que es donde nadie la audita.
        """
        paso = self.perfil["consultar"]
        r = self._llamar(paso, {"destino": self.destino.rstrip("/"),
                                "referencia": delegacion.referencia})
        estado = _ruta(r, paso["ruta_estado"])
        if estado is None:
            raise ErrorDelRemediador(
                f"{self.sistema}: la respuesta no trae el estado en {paso['ruta_estado']!r}. "
                "Un estado que no se puede leer NO es un estado sin cambios.")
        return Delegacion(
            sistema=self.sistema, referencia=delegacion.referencia,
            url=delegacion.url or str(_ruta(r, paso.get("ruta_url", "")) or ""),
            no_conformidad_id=delegacion.no_conformidad_id,
            estado_externo=str(estado),
            actor=str(_ruta(r, paso.get("ruta_actor", "")) or ""),
            cargo_del_actor=str(_ruta(r, paso.get("ruta_cargo", "")) or ""),
            cuando=str(_ruta(r, paso.get("ruta_cuando", "")) or ""),
            detalles={"destino": self.destino})

    def limites(self) -> tuple[LimiteDelRemediador, ...]:
        propios = tuple(
            LimiteDelRemediador(l["que"], l["por_que"]) for l in self.perfil.get("limites", []))
        return propios + (
            LimiteDelRemediador(
                {"es": "que el ticket se cierre no cierra la no conformidad: VERIFICADA exige "
                       "una evidencia de eficacia tomada DESPUÉS de ejecutar, y el estado de "
                       "un tablero no la aporta",
                 "en": "closing the ticket does not close the nonconformity: VERIFICADA "
                       "requires effectiveness evidence taken AFTER execution, and a board's "
                       "state does not provide it"},
                "otro_instrumento"),
            LimiteDelRemediador(
                {"es": "lo que pase dentro del sistema de tickets sin dejar autor no se puede "
                       "escribir aquí: una transición sin persona no se puede auditar",
                 "en": "whatever happens in the ticket system without leaving an author "
                       "cannot be written here: a transition without a person cannot be "
                       "audited"},
                "no_legible"),
        )
