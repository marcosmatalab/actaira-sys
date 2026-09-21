"""El contrato que obedece todo control, y la frontera que publica cada uno.

PORTADO de actaira v2.3.0 `src/actaira/controls/model.py`, notas D-40 y D-41.
Lo que cambia respecto al original, y por que:

  * `Outcome` se queda igual, con sus cuatro valores. No se anaden ni se
    quitan. La tentacion de un quinto valor "parcial" se rechaza: parcial es
    exactamente lo que `covers` y `no_cubre` expresan sin mentir.
  * `Finding` NO se reimporta del original. El `Finding` de actaira main
    incorporo `rule_version`, `author` y `pack`, y esa version es estrictamente
    mejor porque hace imposible publicar un hallazgo sin decir quien escribio
    la regla. Se usa esa.
  * Se anade `remediacion`, que en el original no existia como campo del
    resultado sino como un comando `fix` aparte. Es un campo de DATOS de la
    regla, escrito por una persona. Un modelo puede ayudar a redactarla fuera
    de linea; no la genera en ejecucion, porque entonces el hallazgo seria una
    opinion de Actaira y no una cita.

Por que cuatro resultados y no dos: porque "no lo encontre" y "no esta" son
afirmaciones distintas y normalmente solo una de las dos es cierta. Fundirlas
es el error que convierte una herramienta de evidencia en una de marketing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Resultado(str, Enum):
    """Lo unico que un control puede concluir, y ninguna de las cinco es «cumple».

    ESTE ENUM SE RENOMBRO EN LA FASE 13 Y EL RENOMBRE ES EL ARREGLO
    ----------------------------------------------------------------
    Se llamaba `CUMPLE`. Una auditoria externa encontro que un PNG con un
    trozo de basura llamado `caBX` -- sin manifiesto C2PA verificable, sin
    XMP, sin nada -- terminaba en `cumple`. El defecto no estaba solo en la
    condicion del articulo 50: estaba en que existiera un estado llamado
    «cumple» al alcance de un control tecnico.

    Un control lee bytes. Puede decir que BUSCO algo y NO LO ENCONTRO, que lo
    encontro, que no pudo mirar, que no le tocaba mirar, o que se rompio
    mirando. Ninguna de esas cinco cosas es cumplir una obligacion juridica,
    y mientras el nombre sugiera lo contrario alguien acabara leyendolo asi:
    primero el que escribe una regla nueva, y despues el cliente.

    La segunda negativa de esta casa -- nunca juzgar, solo citar -- no se
    sostiene con una nota al pie si el tipo de datos dice otra cosa.
    """

    SIN_HALLAZGOS = "sin_hallazgos"      # se busco y no aparecio lo que se busca
    CON_HALLAZGOS = "con_hallazgos"      # aparecio
    INDETERMINADO = "indeterminado"      # no se pudo decidir, y se dice por que
    NO_APLICA = "no_aplica"              # ninguna regla del paquete aplicaba
    ERROR = "error"                      # el analizador se rompio: NO es lo mismo

    @property
    def afirma_cumplimiento(self) -> bool:
        """Siempre False, y esta propiedad existe para que se vea en el codigo.

        Ningun estado de un control tecnico afirma cumplimiento. Si algun dia
        alguien anade uno que lo haga, tendra que cambiar esta linea a mano y
        explicar por que, que es exactamente la friccion que se busca.
        """
        return False


@dataclass(frozen=True)
class Hallazgo:
    """Una observacion, y los cuatro campos que dicen de quien es.

    `severidad` es una CADENA escrita por el autor del paquete de reglas, no un
    enumerado nuestro y no un calculo. No se agrega, no se ordena y no se suma:
    la primera negativa prohibe el pliegue, y un enumerado con `rank` dentro es
    un pliegue esperando a que alguien lo llame.
    """

    regla_id: str
    regla_version: str
    autor: str
    paquete: str
    severidad: str
    localizacion: str
    remediacion_es: str
    remediacion_en: str

    def a_json(self) -> dict[str, Any]:
        return {
            "regla_id": self.regla_id,
            "regla_version": self.regla_version,
            "autor": self.autor,
            "paquete": self.paquete,
            "severidad": self.severidad,
            "localizacion": self.localizacion,
            "remediacion": {"es": self.remediacion_es, "en": self.remediacion_en},
        }


def proyectar(ejecucion, observacion, suficiencia=None) -> Resultado:
    """Las cinco capas, vistas como el enumerado viejo. UNA sola definicion.

    `Resultado` deja de ser el modelo y pasa a ser una PROYECCION de las capas
    de `actaira_motor.resultado`, que es lo que siempre fue sin decirlo: cuatro
    afirmaciones de naturaleza distinta metidas en un tipo. Se conserva porque
    el SARIF, el expediente y la consola lo consumen, y porque romperlo de
    golpe habria obligado a tocar catorce sitios a la vez.

    Proyeccion quiere decir una direccion y una sola: de las capas al
    enumerado, nunca al reves. Y el orden importa -- de menos informacion a
    mas -- porque una ejecucion rota no produce observaciones, y una
    observacion con hallazgos ya no necesita preguntarle a la suficiencia.
    `ResultadoControl` comprueba que el valor que trae coincide con este, asi
    que las dos vistas no pueden separarse sin que algo reviente (regla 10).
    """
    from ..resultado.ejecucion import EstadoEjecucion
    from ..resultado.suficiencia import EstadoSuficiencia

    if ejecucion.estado is EstadoEjecucion.FALLIDA:
        return Resultado.ERROR
    if ejecucion.estado is EstadoEjecucion.NO_APLICABLE:
        return Resultado.NO_APLICA
    if observacion.hallazgos:
        return Resultado.CON_HALLAZGOS
    if suficiencia is not None:
        if suficiencia.estado is EstadoSuficiencia.INDETERMINADA:
            return Resultado.INDETERMINADO
        if suficiencia.estado is EstadoSuficiencia.NO_EXIGIBLE:
            return Resultado.NO_APLICA
        if suficiencia.estado is EstadoSuficiencia.INSUFICIENTE:
            # Insuficiente SIN hallazgos no es «esta mal»: es «falta algo por
            # aportar». Se proyecta a INDETERMINADO y no a CON_HALLAZGOS
            # porque inventar un hallazgo que ninguna regla produjo seria
            # emitir una observacion que nadie observo.
            return Resultado.INDETERMINADO
    return Resultado.SIN_HALLAZGOS


@dataclass(frozen=True)
class ResultadoControl:
    """Lo que un control devuelve, con su frontera dentro y no en una nota al pie.

    `cubre` y `no_cubre` no son documentacion: son parte del resultado y viajan
    con el a la evidencia y al informe. Un CUMPLE cuyo `no_cubre` esta vacio es
    un control que afirma haberlo mirado todo, y el cargador lo rechaza salvo
    que la regla declare expresamente que su alcance es total.
    """

    control_id: str
    obligacion_id: str
    resultado: Resultado
    cubre: tuple[str, ...]
    no_cubre: tuple[str, ...]
    controles_cubiertos: tuple[str, ...] = ()
    hallazgos: tuple[Hallazgo, ...] = ()
    # Bilingue desde la fase 12: era una cadena en castellano que el plan
    # copiaba en las DOS claves de una pregunta, asi que un cliente que pedia el
    # expediente en ingles recibia castellano dentro del campo `en`. La puerta
    # que recorre los documentos buscando prosa suelta lo encontro.
    motivo_indeterminado: dict[str, str] | None = None
    inspeccionado: tuple[str, ...] = ()
    # Las capas de las que esto es una proyeccion. Opcionales mientras quedan
    # controles sin migrar; cuando esten todos, dejan de serlo y `resultado`
    # pasa a ser una propiedad calculada en vez de un campo.
    ejecucion: Any = None
    observacion: Any = None
    suficiencia: Any = None

    @classmethod
    def de(cls, ejecucion, observacion, suficiencia=None, *,
           obligacion_id: str, idioma_frases: str = "es") -> "ResultadoControl":
        """Construye la proyeccion desde las capas. La via nueva.

        `controles_cubiertos` ya no se pasa: sale de las senales. Se pasaba, y
        el motor generico lo construia en paralelo a ellas -- dos listas con lo
        mismo dentro, mantenidas a mano en el mismo bucle. El articulo 50 no lo
        pasaba, asi que sus reglas limpias no aparecian como cubiertas y el
        plan las contaba como «no evaluadas»: dos deberes del articulo 50
        salian sin evaluar habiendose evaluado (regla 10, otra vez).
        """
        controles_cubiertos = tuple(dict.fromkeys(s.regla_id for s in observacion.senales))
        mirado, fuera = observacion.frases(idioma_frases)
        # Cuantos ficheros se leyeron es un hecho de EJECUCION, no una senal, y
        # por eso se deriva aqui, al proyectar, en vez de escribirlo a mano en
        # cada control. Va primero porque es lo que contesta «esto se miro?».
        if ejecucion.leidos:
            mirado = (f"{len(ejecucion.leidos)} ficheros analizados",) + mirado
        # EL MOTIVO DE UN INDETERMINADO, CUANDO LA SUFICIENCIA NO TRAE UNO
        # ------------------------------------------------------------------
        # Una suficiencia INSUFICIENTE no lleva `motivo`: lleva `falta`, que es
        # mas util porque cada falta dice ademas QUE HACER y a quien le toca.
        # Al proyectarla a INDETERMINADO hay que escribir el motivo, y se
        # escribe DESDE las faltas en vez de pedir que se escriba dos veces.
        # Si se pidiera a mano, la suficiencia y el motivo podrian discrepar.
        motivo = None
        if suficiencia is not None:
            if suficiencia.motivo:
                motivo = suficiencia.motivo
            elif suficiencia.falta:
                motivo = {i: "; ".join(f.que[i] for f in suficiencia.falta)
                          for i in ("es", "en")}
        return cls(
            control_id=observacion.control_id, obligacion_id=obligacion_id,
            resultado=proyectar(ejecucion, observacion, suficiencia),
            cubre=mirado, no_cubre=fuera, controles_cubiertos=controles_cubiertos,
            hallazgos=observacion.hallazgos, motivo_indeterminado=motivo,
            inspeccionado=tuple(ejecucion.leidos),
            ejecucion=ejecucion, observacion=observacion, suficiencia=suficiencia)

    def __post_init__(self) -> None:
        if self.ejecucion is not None and self.observacion is not None:
            debido = proyectar(self.ejecucion, self.observacion, self.suficiencia)
            if debido is not self.resultado:
                raise ValueError(
                    f"{self.control_id}: el resultado dice {self.resultado.value} y las capas "
                    f"proyectan {debido.value}. Una vista derivada que discrepa de su fuente "
                    "es peor que no tenerla (regla 10).")
        if self.motivo_indeterminado is not None and \
           set(self.motivo_indeterminado) != {"es", "en"}:
            raise ValueError(
                f"{self.control_id}: el motivo de un INDETERMINADO va en los dos idiomas. "
                "Un expediente pedido en ingles no puede traer una frase en castellano.")
        if self.resultado is Resultado.INDETERMINADO and not self.motivo_indeterminado:
            raise ValueError(
                f"{self.control_id}: un INDETERMINADO sin motivo escrito es un "
                "NO_CUMPLE disfrazado. La tercera negativa exige nombrar la causa."
            )
        for cid in self.controles_cubiertos:
            if not any(c.startswith(cid + ":") for c in self.cubre):
                raise ValueError(
                    f"{self.control_id}: declara cubierto '{cid}' y ninguna linea de `cubre` lo "
                    "explica. Las dos vistas salen del mismo sitio o se anulan (regla 10).")
        # UN «SIN HALLAZGOS» CON HALLAZGOS DENTRO
        # -----------------------------------------
        # Lo encontro la separacion en capas de la fase 14, y llevaba ahi desde
        # la fase 2. El articulo 50 calculaba su resultado final mirando solo
        # los artefactos sin marcar, y se olvidaba de los hallazgos de
        # generacion de texto que ya llevaba en la lista: devolvia
        # SIN_HALLAZGOS con un hallazgo dentro. Nada fallaba, el hallazgo
        # viajaba en el JSON, y el informe lo contaba en la columna de los
        # limpios. Ni la auditoria externa ni la revision lo vieron; lo vio la
        # proyeccion, que es exactamente para lo que se hizo.
        if self.resultado is Resultado.SIN_HALLAZGOS and self.hallazgos:
            raise ValueError(
                f"{self.control_id}: dice SIN_HALLAZGOS y trae {len(self.hallazgos)} hallazgos "
                f"({', '.join(h.regla_id for h in self.hallazgos[:3])}). Un resultado limpio con "
                "hallazgos dentro es la forma mas silenciosa de perder un hallazgo.")
        if self.resultado is Resultado.SIN_HALLAZGOS and not self.cubre:
            raise ValueError(
                f"{self.control_id}: un CUMPLE tiene que decir QUE cubre. "
                "Un CUMPLE sin alcance es la afirmacion que este diseno existe para impedir."
            )

    def a_json(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "obligacion_id": self.obligacion_id,
            "resultado": self.resultado.value,
            "cubre": list(self.cubre),
            "no_cubre": list(self.no_cubre),
            "controles_cubiertos": list(self.controles_cubiertos),
            "inspeccionado": list(self.inspeccionado),
            "motivo_indeterminado": self.motivo_indeterminado,
            "hallazgos": [h.a_json() for h in self.hallazgos],
        }


@dataclass
class Pasada:
    """El conjunto de resultados de una ejecucion. Cuenta, nunca agrega.

    D-41: once CUMPLE de catorce no es el setenta y ocho por ciento de nada.
    `recuento` devuelve enteros por resultado y no existe ningun metodo que
    devuelva un flotante. El test `test_sin_agregados` lo sujeta.
    """

    resultados: list[ResultadoControl] = field(default_factory=list)

    def recuento(self) -> dict[str, int]:
        salida = {r.value: 0 for r in Resultado}
        for res in self.resultados:
            salida[res.resultado.value] += 1
        return salida

    def a_json(self) -> dict[str, Any]:
        return {
            "recuento": self.recuento(),
            "total_controles_corridos": len(self.resultados),
            "resultados": [r.a_json() for r in self.resultados],
        }
