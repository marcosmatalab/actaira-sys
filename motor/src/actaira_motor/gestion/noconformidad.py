"""La cláusula 10.2: no conformidad y acción correctiva, sin el botón de cerrar.

POR QUE ESTO NO ES UN CAMPO `estado` EN UNA FILA
--------------------------------------------------
Todas las herramientas de GRC guardan la no conformidad como un registro con
un campo `estado` que alguien cambia. Eso tiene dos consecuencias y las dos se
ven en cualquier auditoría:

  1. El historial se pierde o vive en otra tabla que nadie cruza, así que «¿por
     qué esto estuvo seis meses abierto?» no tiene respuesta.
  2. Y cerrar es escribir una palabra. Un `estado = "cerrada"` no distingue
     entre «comprobamos que la causa dejó de producir el efecto» y «pasó el
     tiempo y alguien lo dio por bueno», que es exactamente la diferencia que
     la cláusula 10.2 exige revisar.

Aquí la no conformidad NO se guarda: se guardan sus TRANSICIONES, en el mismo
almacén encadenado que la evidencia técnica, y el estado se calcula al leer.
Es la misma decisión que el módulo de evidencia toma y por la misma razón: un
estado almacenado es una segunda fuente de verdad sobre lo que ya dicen las
fechas.

LA REGLA QUE HACE ESTO UTIL, Y ES UNA SOLA
--------------------------------------------
`EJECUTADA` no es cerrada. La cláusula 10.2 pide revisar la EFICACIA de la
acción correctiva, y eso es una observación posterior, no la misma acción
mirada otra vez. Para llegar a `VERIFICADA` hace falta el identificador de una
evidencia tomada DESPUÉS de ejecutar, y el constructor lo exige. Sin esa regla,
el ciclo de mejora de la 10.2 es un formulario.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from ..evidencia.registro import Registro

CONTROL = "ISO-10.2"
OBLIGACION = "ISO-10.2"


class EstadoNC(str, Enum):
    ABIERTA = "abierta"          # se detecto y nadie ha hecho nada todavia
    EN_ANALISIS = "en_analisis"  # se esta buscando la causa
    CON_ACCION = "con_accion"    # hay accion, responsable y fecha comprometida
    EJECUTADA = "ejecutada"      # la accion se hizo, y consta quien y cuando
    VERIFICADA = "verificada"    # y se comprobo que la causa dejo de producir el efecto

    @property
    def cerrada(self) -> bool:
        """Solo VERIFICADA. `EJECUTADA` es «lo hicimos», no «funciono».

        Los cuatro estados anteriores NO son grados de cierre: son sitios
        distintos del ciclo, y fundir los dos ultimos es lo que convierte la
        mejora continua en una lista de tareas hechas.
        """
        return self is EstadoNC.VERIFICADA

    @property
    def afirma_cumplimiento(self) -> bool:
        """Siempre False, como en el motor y en la suficiencia.

        Que una no conformidad este verificada dice que ESA desviacion dejo de
        producirse. No dice que la organizacion cumpla: hay mas requisitos, y
        alguno puede no haberse mirado nunca.
        """
        return False


ORDEN = (EstadoNC.ABIERTA, EstadoNC.EN_ANALISIS, EstadoNC.CON_ACCION,
         EstadoNC.EJECUTADA, EstadoNC.VERIFICADA)


@dataclass(frozen=True)
class Transicion:
    """Un movimiento de la no conformidad, con quien lo hizo y cuando.

    Es lo que de verdad se guarda. Una transicion sin persona no se puede
    construir: un ciclo de mejora en el que los cambios de estado no tienen
    autor no se puede auditar, y ese es todo el trabajo de la clausula 10.2.
    """

    no_conformidad_id: str
    a: EstadoNC
    quien: str
    cargo: str
    cuando: str
    nota: str = ""
    # Solo en las transiciones que lo necesitan, y el constructor lo exige:
    causa_raiz: str | None = None          # para salir de EN_ANALISIS
    accion: str | None = None              # para CON_ACCION
    responsable: str | None = None         # para CON_ACCION
    compromiso: str | None = None          # fecha comprometida, para CON_ACCION
    evidencia_de_eficacia: str | None = None   # para VERIFICADA
    # Solo en la transicion que ABRE: de donde salio y que se desvio. Van en la
    # transicion y no en un fichero aparte para que el almacen encadenado sea
    # la unica fuente: si vivieran fuera, se podrian editar sin romper nada.
    origen: str | None = None
    descripcion: str | None = None

    def __post_init__(self) -> None:
        for campo in ("no_conformidad_id", "quien", "cargo", "cuando"):
            if not str(getattr(self, campo)).strip():
                raise ValueError(
                    f"una transicion sin '{campo}' no se puede auditar: un ciclo de mejora "
                    "donde los cambios de estado no tienen autor no es un ciclo de mejora")
        if self.a is EstadoNC.CON_ACCION and not (self.accion and self.responsable
                                                  and self.compromiso):
            raise ValueError(
                f"{self.no_conformidad_id}: pasar a CON_ACCION exige accion, responsable y fecha "
                "comprometida. Una accion sin dueno y sin fecha es una intencion.")
        if self.a is EstadoNC.ABIERTA and not (self.origen and self.descripcion):
            raise ValueError(
                f"{self.no_conformidad_id}: la transicion que abre una no conformidad dice de "
                "donde salio y que se desvio. Sin eso, lo que hay es un identificador.")
        if self.a is EstadoNC.VERIFICADA and not self.evidencia_de_eficacia:
            raise ValueError(
                f"{self.no_conformidad_id}: pasar a VERIFICADA exige el identificador de una "
                "evidencia de eficacia. La clausula 10.2 pide revisar si la accion FUNCIONO, y "
                "eso es una observacion posterior, no la misma accion mirada otra vez.")

    def a_registro(self, frescura_dias: int | None = 90) -> Registro:
        """La transicion, como evidencia. Va al mismo almacen encadenado.

        No hay un segundo mecanismo de almacenamiento para la gestion: la
        cadena de sellos, la frescura y la invalidacion por digest valen igual
        para un cambio de estado de una no conformidad que para una lectura de
        bytes. Dos almacenes habrian sido dos maneras de perder lo mismo.
        """
        return Registro.nuevo(
            obligacion_id=OBLIGACION, control_id=CONTROL,
            sujeto_digest=f"nc:{self.no_conformidad_id}",
            observado_en=datetime.fromisoformat(self.cuando),
            contenido=self.a_json(), frescura_dias=frescura_dias)

    def a_json(self) -> dict[str, Any]:
        d = {"no_conformidad_id": self.no_conformidad_id, "a": self.a.value,
             "quien": self.quien, "cargo": self.cargo, "cuando": self.cuando}
        for campo in ("nota", "causa_raiz", "accion", "responsable", "compromiso",
                      "evidencia_de_eficacia", "origen", "descripcion"):
            v = getattr(self, campo)
            if v:
                d[campo] = v
        return d

    @staticmethod
    def de_json(d: dict[str, Any]) -> "Transicion":
        return Transicion(
            no_conformidad_id=d["no_conformidad_id"], a=EstadoNC(d["a"]),
            quien=d["quien"], cargo=d["cargo"], cuando=d["cuando"], nota=d.get("nota", ""),
            causa_raiz=d.get("causa_raiz"), accion=d.get("accion"),
            responsable=d.get("responsable"), compromiso=d.get("compromiso"),
            evidencia_de_eficacia=d.get("evidencia_de_eficacia"),
            origen=d.get("origen"), descripcion=d.get("descripcion"))


@dataclass(frozen=True)
class NoConformidad:
    """El estado de una no conformidad AHORA, calculado desde sus transiciones."""

    id: str
    origen: str                  # de donde salio: un hallazgo, una auditoria, una reclamacion
    descripcion: str
    abierta_en: str
    estado: EstadoNC
    transiciones: tuple[Transicion, ...]
    causa_raiz: str | None = None
    accion: str | None = None
    responsable: str | None = None
    compromiso: str | None = None
    evidencia_de_eficacia: str | None = None

    def incoherencias(self) -> list[str]:
        """Lo que no encaja dentro de la propia no conformidad.

        Las tres salieron de atacar esto despues de escribirlo, y las tres
        pasaban las comprobaciones del constructor, que solo mira UNA
        transicion cada vez. Estas miran la historia entera:

          1. verificada sin haber ejecutado nada: se comprobo la eficacia de
             una accion que no consta que se hiciera;
          2. verificada sin causa raiz ni accion: es dar por buena una
             desviacion sin haber analizado nada, que es lo que la clausula
             10.2 llama expresamente corregir sin corregir la causa;
          3. y la evidencia de eficacia es ANTERIOR a la ejecucion. Eso no es
             revisar si funciono: es haber mirado antes de hacerlo.
        """
        fuera: list[str] = []
        if self.estado is not EstadoNC.VERIFICADA:
            return fuera
        ejecuciones = [t for t in self.transiciones if t.a is EstadoNC.EJECUTADA]
        if not ejecuciones:
            fuera.append(
                f"{self.id}: verificada sin que conste ninguna ejecucion. Se comprobo la "
                "eficacia de una accion que nadie dice haber hecho.")
        if not self.causa_raiz or not self.accion:
            fuera.append(
                f"{self.id}: verificada sin causa raiz o sin accion. La clausula 10.2 pide "
                "corregir Y eliminar la causa; sin causa analizada, lo que se cerro fue el "
                "sintoma.")
        verif = next((t for t in self.transiciones if t.a is EstadoNC.VERIFICADA), None)
        if ejecuciones and verif and verif.cuando < max(t.cuando for t in ejecuciones):
            fuera.append(
                f"{self.id}: la verificacion es anterior a la ejecucion. Eso no es revisar si "
                "la accion funciono: es haber mirado antes de hacerla.")
        return fuera

    def estancada(self, ahora: datetime, dias: int = 90) -> bool:
        """Abierta hace mucho y sin fecha comprometida a la que faltar.

        `vencida` no la ve: sin compromiso no hay fecha que pasar, asi que una
        no conformidad que nadie analizo nunca se quedaba invisible para
        siempre. Es el agujero mas comodo de todos, porque premia no
        comprometerse a nada.
        """
        if self.estado.cerrada or self.compromiso:
            return False
        return self.dias_abierta(ahora) > dias

    def vencida(self, ahora: datetime) -> bool:
        """Que la fecha comprometida haya pasado y la cosa siga sin verificarse.

        `EJECUTADA` tambien cuenta como vencida si nadie comprobo la eficacia:
        haber hecho la accion no es haber cerrado, y una no conformidad que
        lleva cuatro meses «ejecutada» sin verificar es justo la que un auditor
        encuentra.
        """
        if self.estado.cerrada or not self.compromiso:
            return False
        return ahora.date() > datetime.fromisoformat(self.compromiso).date()

    def dias_abierta(self, ahora: datetime) -> int:
        fin = ahora
        if self.estado.cerrada and self.transiciones:
            fin = datetime.fromisoformat(self.transiciones[-1].cuando)
        return (fin - datetime.fromisoformat(self.abierta_en)).days

    def a_json(self) -> dict[str, Any]:
        return {"id": self.id, "origen": self.origen, "descripcion": self.descripcion,
                "abierta_en": self.abierta_en, "estado": self.estado.value,
                "causa_raiz": self.causa_raiz, "accion": self.accion,
                "responsable": self.responsable, "compromiso": self.compromiso,
                "evidencia_de_eficacia": self.evidencia_de_eficacia,
                "transiciones": [t.a_json() for t in self.transiciones]}


def reconstruir(nc_id: str, origen: str, descripcion: str,
                transiciones: list[Transicion]) -> NoConformidad:
    """El estado de la no conformidad, calculado en orden cronologico.

    Se ordena por FECHA y no por el orden en que llegaron: el almacen admite
    que dos pasadas escriban en cualquier orden, y reconstruir por orden de
    llegada haria que el estado dependiera de cual gano la carrera.

    Y NO se retrocede: si una transicion vieja llega despues de una nueva, el
    estado se queda en el mas avanzado que se haya alcanzado de verdad. Lo
    contrario seria que una escritura tardia reabriera algo cerrado sin que
    nadie lo decidiera.
    """
    if not transiciones:
        raise ValueError(f"{nc_id}: una no conformidad sin ninguna transicion no existe; "
                         "la primera es la que la abre")
    ordenadas = tuple(sorted(transiciones, key=lambda t: t.cuando))
    estado = EstadoNC.ABIERTA
    campos: dict[str, Any] = {}
    for t in ordenadas:
        if ORDEN.index(t.a) >= ORDEN.index(estado):
            estado = t.a
        for campo in ("causa_raiz", "accion", "responsable", "compromiso",
                      "evidencia_de_eficacia"):
            if getattr(t, campo):
                campos[campo] = getattr(t, campo)
    return NoConformidad(
        id=nc_id, origen=origen, descripcion=descripcion,
        abierta_en=ordenadas[0].cuando, estado=estado, transiciones=ordenadas, **campos)


def transiciones_del_almacen(almacen) -> dict[str, list[Transicion]]:
    """Todas las transiciones guardadas, agrupadas por no conformidad."""
    fuera: dict[str, list[Transicion]] = {}
    for r in almacen.registros():
        if r.control_id != CONTROL:
            continue
        t = Transicion.de_json(r.contenido)
        fuera.setdefault(t.no_conformidad_id, []).append(t)
    return fuera


def desde_el_almacen(almacen, nc_id: str, origen: str | None = None,
                     descripcion: str | None = None) -> NoConformidad:
    """Reconstruye UNA no conformidad. El origen sale de su propia apertura."""
    ts = transiciones_del_almacen(almacen).get(nc_id, [])
    if not ts:
        raise ValueError(f"{nc_id}: no hay ninguna transicion suya en el almacen")
    apertura = min(ts, key=lambda t: t.cuando)
    return reconstruir(nc_id, origen or apertura.origen or "",
                       descripcion or apertura.descripcion or "", ts)


def todas_del_almacen(almacen) -> list[NoConformidad]:
    """Todas las no conformidades del almacen, reconstruidas."""
    fuera = []
    for nc_id, ts in sorted(transiciones_del_almacen(almacen).items()):
        apertura = min(ts, key=lambda t: t.cuando)
        fuera.append(reconstruir(nc_id, apertura.origen or "",
                                 apertura.descripcion or "", ts))
    return fuera


def vencidas(ncs: list[NoConformidad], ahora: datetime) -> list[NoConformidad]:
    """Las que pasaron su fecha y nadie ha verificado su eficacia."""
    return [n for n in ncs if n.vencida(ahora)]


def desatendidas(ncs: list[NoConformidad], ahora: datetime,
                 dias: int = 90) -> list[NoConformidad]:
    """Las vencidas MAS las estancadas, que son dos maneras de no hacer nada.

    Van juntas porque para quien mira el panel son lo mismo -- hay que
    ocuparse -- y separadas en el dato porque no se arreglan igual: una pide
    ejecutar lo comprometido y la otra pide comprometerse a algo.
    """
    return [n for n in ncs if n.vencida(ahora) or n.estancada(ahora, dias)]
