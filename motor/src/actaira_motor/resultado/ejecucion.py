"""Capa 1: que corrio, sobre que, con que version, y que no pudo leer.

POR QUE ESTO ES UNA CAPA Y NO UN CAMPO
----------------------------------------
«El analizador se rompio» y «el analizador miro y no encontro nada» producian
el mismo tipo de dato y se distinguian por un valor del enumerado. Cualquier
codigo que hiciera `if resultado is not CON_HALLAZGOS` trataba las dos igual,
y la segunda es una observacion mientras la primera es la AUSENCIA de
observacion. Un expediente que cuenta un analizador roto en la columna de los
limpios es un expediente que miente por omision.

Separarlo tiene ademas un efecto que no se ve hasta que hace falta: la
ejecucion es lo que se repite. Dos ejecuciones del mismo analizador sobre el
mismo sujeto con la misma version tienen que dar la misma observacion, y con
la ejecucion como objeto propio eso se puede COMPROBAR en vez de prometerse.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..evidencia.registro import digest

ESQUEMA = "actaira/ejecucion/v1"


class EstadoEjecucion(str, Enum):
    COMPLETADA = "completada"        # corrio de principio a fin
    FALLIDA = "fallida"              # se rompio: NO hay observacion que valga
    NO_APLICABLE = "no_aplicable"    # no le tocaba mirar, y se dice por que

    @property
    def hay_observacion(self) -> bool:
        """Solo una ejecucion completada produce una observacion que valga.

        Existe como propiedad y no como comparacion suelta para que quien lea
        una observacion tenga que preguntarse antes si hubo ejecucion. Es la
        friccion que evita contar un analizador roto como un repositorio limpio.
        """
        return self is EstadoEjecucion.COMPLETADA


@dataclass(frozen=True)
class Sujeto:
    """Sobre QUE corrio. El digest es lo que ata la evidencia, no el nombre.

    Un sujeto con nombre y sin digest es un sujeto que no se puede volver a
    identificar: a la evidencia la supera el digest sobre el que se tomo, asi
    que sin el no hay invalidacion selectiva, solo un muro rojo cada vez que
    alguien toca cualquier cosa.
    """

    tipo: str            # "repositorio" | "artefacto" | "modelo" | "despliegue" | ...
    nombre: str
    digest: str

    def a_json(self) -> dict[str, Any]:
        return {"tipo": self.tipo, "nombre": self.nombre, "digest": self.digest}


@dataclass(frozen=True)
class Ejecucion:
    analizador: str
    analizador_version: str
    paquete: str
    paquete_version: str
    sujeto: Sujeto
    empezo: str
    termino: str
    estado: EstadoEjecucion
    motivo: dict[str, str] | None = None
    leidos: tuple[str, ...] = ()
    ilegibles: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.estado is not EstadoEjecucion.COMPLETADA and not self.motivo:
            raise ValueError(
                f"{self.analizador}: una ejecucion {self.estado.value} sin motivo escrito "
                "es indistinguible de una que no encontro nada. Nombra la causa.")
        if self.motivo is not None and set(self.motivo) != {"es", "en"}:
            raise ValueError(
                f"{self.analizador}: el motivo va en los dos idiomas. Un expediente "
                "pedido en ingles no puede traer una frase en castellano.")
        if self.estado is EstadoEjecucion.COMPLETADA and not self.leidos and not self.ilegibles:
            raise ValueError(
                f"{self.analizador}: una ejecucion completada que no leyo NI UN fichero y "
                "tampoco declara ilegibles no miro nada. Si de verdad no habia nada que "
                "mirar, eso es NO_APLICABLE con su motivo.")

    @property
    def id(self) -> str:
        return digest(self.cuerpo())

    def cuerpo(self) -> dict[str, Any]:
        """Lo que identifica a esta ejecucion. UNA definicion (regla 10).

        NI `empezo` NI `termino` entran: dos ejecuciones identicas que
        ocurrieron a horas distintas son la misma ejecucion repetida, y si el
        identificador cambiara con el reloj la reproducibilidad no se podria
        comprobar nunca.

        La primera version solo dejaba fuera `termino`, decia en su docstring
        que el identificador no cambiaba con el reloj, y cambiaba con el reloj:
        `empezo` seguia dentro. La prueba que lo cubria variaba `termino` y
        ninguna variaba `empezo`, asi que su verde no decia nada sobre lo que
        el nombre del test prometia. Lo encontro la puerta de la API que
        compara el documento de HTTP con el de la linea de mandatos, ejecutando
        dos veces lo mismo: doce ejecuciones identicas daban doce
        identificadores.

        Es la misma decision que toma `Observacion.cuerpo()` al dejar fuera
        `ejecucion_id`: la identidad es el CONTENIDO y la procedencia viaja
        aparte. El cuando sale en `a_json()`, que es donde va lo que describe
        la ocasion y no la cosa.
        """
        return {"esquema": ESQUEMA, "analizador": self.analizador,
                "analizador_version": self.analizador_version,
                "paquete": self.paquete, "paquete_version": self.paquete_version,
                "sujeto": self.sujeto.a_json(),
                "estado": self.estado.value, "motivo": self.motivo,
                "leidos": sorted(self.leidos),
                "ilegibles": sorted([list(x) for x in self.ilegibles])}

    def reproducible_como(self, otra: "Ejecucion") -> bool:
        """Dos ejecuciones son la misma cuando coincide su contenido.

        Comparte la definicion con `cuerpo()`, y por tanto con `id`. Antes
        tenia la suya -- quitaba `empezo` por su cuenta -- y las dos
        definiciones DISCREPABAN: `reproducible_como` decia que si y los
        identificadores decian que no. Regla 10 en su forma peor, que no es que
        una se olvide de actualizar, sino que las dos contesten cosas
        distintas a la misma pregunta.
        """
        return self.cuerpo() == otra.cuerpo()

    def a_json(self) -> dict[str, Any]:
        d = dict(self.cuerpo())
        d.update({"id": self.id, "empezo": self.empezo, "termino": self.termino})
        return d

    @staticmethod
    def ahora() -> str:
        return datetime.now(timezone.utc).isoformat()
