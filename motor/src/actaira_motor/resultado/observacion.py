"""Capa 2: lo que se vio. Hechos, y ningun veredicto.

LO QUE SE QUITA DE ESTE TIPO, Y ES EL CAMBIO ENTERO
-----------------------------------------------------
No hay campo `resultado`. No lo hay a proposito. Una observacion dice «en
servicio.py, linea 6, hay una llamada a un generador de imagen» y «en
salida.png no aparece ningun paquete XMP con digitalSourceType». Las dos son
comprobables abriendo el fichero. Ninguna de las dos dice si eso basta para el
articulo 50: eso es la capa 4, la decide una politica que se cita por su
identificador, y meterla aqui era lo que permitia que un cambio en una regla
moviera un veredicto sin que nadie viera por que.

LAS SENALES, QUE ANTES ERAN PROSA
-----------------------------------
`cubre` era una lista de frases en castellano: «3 artefactos leidos byte a
byte: a.png, b.png, c.png». Sirve para el informe y no sirve para nada mas:
no se puede consultar, no se puede cruzar con un requisito y no se puede
comprobar. Una `Senal` es lo mismo en estructura -- que se buscaba, donde
aparecio, con que regla -- y la frase se genera a partir de ella. Una sola
fuente, dos vistas (regla 10).

Y las senales son la mitad que faltaba: un control que solo publica hallazgos
solo sabe hablar de lo que esta mal, con lo que un repositorio impecable y uno
que no se miro producen el mismo informe vacio.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..controles.modelo import Hallazgo
from ..evidencia.registro import digest

ESQUEMA = "actaira/observacion/v1"


FUERZAS = ("comportamiento", "presencia", "aportado")
"""Las clases de senal, de la mas fuerte a la mas debil. El orden es el peso.

Se escriben en una tupla ordenada y no en un conjunto porque el orden ES la
informacion: permite preguntar «cual es la mas fuerte que respalda esta
obligacion» sin repartir esa decision por los consumidores.
"""


@dataclass(frozen=True)
class Senal:
    """Lo que SI se encontro de lo que la regla buscaba. El gemelo del hallazgo.

    Existe por la regla 9 llevada al dato y no solo a las pruebas: si el tipo
    solo permite registrar ausencias, el informe solo sabe hablar de ausencias,
    y «no encontre nada malo» acaba leyendose como «esta bien».
    """

    regla_id: str
    regla_version: str
    paquete: str
    que_se_buscaba: dict[str, str]
    localizacion: str
    fuerza: str = "presencia"
    """QUE CLASE de cosa se encontro. Ni todas las senales pesan lo mismo.

    Una auditoria externa lo puso asi: el motor comprueba una SENAL, no la
    correccion, la suficiencia ni la eficacia de un control. Encontrar un
    fichero llamado `dataset-card.md` no demuestra que el origen de los datos
    sea licito, ni que se haya evaluado la representatividad, ni que los sesgos
    esten dentro de umbrales aprobados.

    Es cierto, y el arreglo no es dejar de mirar los ficheros: es dejar de
    presentar las dos cosas con la misma cara. El informe decia «comprobada»
    igual cuando una regla habia encontrado una LLAMADA en el arbol sintactico
    -- que es una afirmacion sobre lo que el programa HACE -- que cuando habia
    encontrado un nombre de fichero que casa con una expresion regular.

    Tres valores, del mas fuerte al mas debil:

      comportamiento  se encontro una llamada, o la ausencia de la pareja de
                      una llamada, en el arbol sintactico. Es una afirmacion
                      sobre lo que el codigo hace, no sobre lo que dice tener.
      presencia       caso un nombre de fichero o una linea de texto. Dice que
                      el artefacto ESTA, y no dice nada de lo que hay dentro.
      aportado        no se leyo nada: se le pregunto a una persona.

    El valor por omision es `presencia`, que es el mas debil de los que
    observan: una senal construida sin declarar su fuerza no puede reclamar la
    mas fuerte por descuido.
    """

    def __post_init__(self) -> None:
        if set(self.que_se_buscaba) != {"es", "en"}:
            raise ValueError(f"{self.regla_id}: `que_se_buscaba` va en los dos idiomas")
        if self.fuerza not in FUERZAS:
            raise ValueError(
                f"{self.regla_id}: fuerza {self.fuerza!r}, y las que hay son {sorted(FUERZAS)}")

    def a_json(self) -> dict[str, Any]:
        return {"regla_id": self.regla_id, "regla_version": self.regla_version,
                "paquete": self.paquete, "fuerza": self.fuerza, "que_se_buscaba": self.que_se_buscaba,
                "localizacion": self.localizacion}


@dataclass(frozen=True)
class Limite:
    """Lo que esta observacion NO cubre. Viaja con ella, no en una nota al pie.

    Un limite sin motivo es una coletilla. `por_que` obliga a decir si no se
    miro porque la regla no lo alcanza, porque el fichero no se pudo leer o
    porque hace falta algo que el cliente no aporto: son tres acciones
    distintas para quien lee el informe.
    """

    que: dict[str, str]
    por_que: str        # "fuera_del_alcance_de_la_regla" | "no_legible" | "falta_aporte"

    MOTIVOS = ("fuera_del_alcance_de_la_regla", "no_legible", "falta_aporte", "otro_instrumento")

    def __post_init__(self) -> None:
        if set(self.que) != {"es", "en"}:
            raise ValueError("el limite va en los dos idiomas")
        if self.por_que not in Limite.MOTIVOS:
            raise ValueError(f"motivo de limite desconocido: {self.por_que!r}")

    def a_json(self) -> dict[str, Any]:
        return {"que": self.que, "por_que": self.por_que}


@dataclass(frozen=True)
class Observacion:
    ejecucion_id: str
    control_id: str
    hallazgos: tuple[Hallazgo, ...] = ()
    senales: tuple[Senal, ...] = ()
    limites: tuple[Limite, ...] = ()

    def __post_init__(self) -> None:
        if not self.limites:
            raise ValueError(
                f"{self.control_id}: una observacion sin limites afirma haberlo mirado todo. "
                "Si de verdad su alcance es total, eso se declara con un limite que lo diga.")

    @property
    def id(self) -> str:
        return digest(self.cuerpo())

    def cuerpo(self) -> dict[str, Any]:
        """Lo que identifica a esta observacion: lo que se vio, y nada mas.

        `ejecucion_id` NO entra, y la razon es la misma por la que el almacen
        distingue una observacion nueva de una revalidacion. Dos pasadas que
        ven exactamente lo mismo sobre el mismo sujeto han visto LO MISMO: son
        una observacion observada dos veces, no dos observaciones. Si la
        identidad arrastrara el identificador de la ejecucion -- que lleva el
        reloj dentro -- cada pasada del cron escribiria un registro nuevo, el
        almacen mediria la frecuencia del cron en vez de la actividad del
        cliente, y no habria manera de comprobar que el motor es reproducible.

        La ejecucion sigue viajando en `a_json` como procedencia. Procedencia e
        identidad son cosas distintas y fundirlas cuesta exactamente esto.
        """
        return {"esquema": ESQUEMA, "control_id": self.control_id,
                "hallazgos": [h.a_json() for h in self.hallazgos],
                "senales": [s.a_json() for s in self.senales],
                "limites": [l.a_json() for l in self.limites]}

    def a_json(self) -> dict[str, Any]:
        d = dict(self.cuerpo())
        d.update({"id": self.id, "ejecucion_id": self.ejecucion_id})
        return d

    def frases(self, idioma: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(lo mirado, lo no cubierto) en prosa, generado desde las senales.

        La prosa se deriva del dato y no al reves. Antes eran dos cosas
        escritas a mano en cada control, y por eso una decia «3 artefactos» y
        otra «tres artefactos» y ninguna se podia consultar.
        """
        mirado = tuple(f"{s.regla_id}: {s.que_se_buscaba[idioma]} -> {s.localizacion}"
                       for s in self.senales)
        fuera = tuple(l.que[idioma] for l in self.limites)
        return mirado, fuera
