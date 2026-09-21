"""Del estado de un ticket ajeno al ciclo de la cláusula 10.2, con techo.

LA REGLA, QUE ES UNA SOLA Y ES UNA NEGATIVA
---------------------------------------------
Ningún estado externo llega a `VERIFICADA`. Da igual que el ticket se llame
«Done», «Closed», «Verified» o «Validated by QA»: lo que dice es que alguien
dio el trabajo por hecho en su tablero. `VERIFICADA` dice que se comprobó que
la causa dejó de producir el efecto, y para eso hace falta el identificador de
una evidencia tomada DESPUÉS de ejecutar.

La tentación es obvia y es por lo que todos los productos de cumplimiento la
aceptan: si el ticket cerrado cerrara la no conformidad, el panel se pondría
verde solo y nadie tendría que volver a mirar. Ése es el problema, no la
solución.

Y LA SEGUNDA, QUE ES LA QUE SE OLVIDA
---------------------------------------
Un estado que no está en la tabla **no se ignora**. Un equipo añade una columna
«En revisión de seguridad» a su tablero, los tickets se paran ahí, y el ciclo
de mejora deja de moverse sin que nadie se entere. Es el mismo modo de fallo
que el de los empujones que dejan de traducirse: el cliente sigue creyendo que
tiene vigilancia.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..gestion.noconformidad import ORDEN, EstadoNC, Transicion
from .contrato import TECHO, Delegacion


class EstadoQueNoConocemos(Exception):
    """El tablero tiene una columna que esta tabla no sabe leer.

    No se ignora: un ciclo de mejora que se para en una columna desconocida se
    para en silencio, y el silencio es indistinguible de ir bien.
    """


class SinAutor(Exception):
    """El otro sistema no dice quién movió el ticket.

    Una transición sin persona no se puede auditar, y escribir «sistema» en su
    lugar sería inventar el autor que la cláusula 10.2 pide. Se dice que falta
    y no se mueve nada.
    """


# Las columnas de cada sistema, y a donde llevan. Es una tabla por sistema y no
# una lista de sinonimos global porque «Done» no significa lo mismo en un
# tablero de ingenieria que en uno de cumplimiento, y fundirlos habria hecho
# que la traduccion dependiera de quien nombro la columna.
TABLAS: dict[str, dict[str, str]] = {
    "jira": {
        "to do": EstadoNC.ABIERTA.value,
        "backlog": EstadoNC.ABIERTA.value,
        "open": EstadoNC.ABIERTA.value,
        "in progress": EstadoNC.EN_ANALISIS.value,
        "in review": EstadoNC.EJECUTADA.value,
        "done": EstadoNC.EJECUTADA.value,
        "closed": EstadoNC.EJECUTADA.value,
        "resolved": EstadoNC.EJECUTADA.value,
    },
    "linear": {
        "backlog": EstadoNC.ABIERTA.value,
        "todo": EstadoNC.ABIERTA.value,
        "unstarted": EstadoNC.ABIERTA.value,
        "started": EstadoNC.EN_ANALISIS.value,
        "in progress": EstadoNC.EN_ANALISIS.value,
        "completed": EstadoNC.EJECUTADA.value,
        "done": EstadoNC.EJECUTADA.value,
        "canceled": EstadoNC.ABIERTA.value,   # cancelado NO es hecho
    },
    "github": {
        "open": EstadoNC.ABIERTA.value,
        "closed": EstadoNC.EJECUTADA.value,
    },
    "fichero": {
        "escrito": EstadoNC.ABIERTA.value,
    },
}


def traducir_estado(sistema: str, estado_externo: str) -> EstadoNC:
    """La columna del otro, en el ciclo nuestro. Nunca más arriba del techo.

    El techo se comprueba AQUI y no solo en la tabla: una tabla es un dato que
    alguien edita, y la unica manera de que el techo sea una propiedad del
    codigo es que el codigo lo imponga aunque la tabla mienta.
    """
    tabla = TABLAS.get(sistema)
    if tabla is None:
        raise EstadoQueNoConocemos(
            f"no hay tabla de estados para el sistema {sistema!r}. Los que hay: "
            + ", ".join(sorted(TABLAS)) + ". Esto NO se ignora: un ciclo de mejora que se "
            "para en un sistema que nadie sabe leer se para en silencio.")
    clave = (estado_externo or "").strip().lower()
    if clave not in tabla:
        raise EstadoQueNoConocemos(
            f"{sistema}: la columna {estado_externo!r} no esta en la tabla. Las que hay: "
            + ", ".join(sorted(tabla)) + ". Anadir una columna al tablero y que el ciclo se "
            "pare ahi sin que nadie se entere es el modo de fallo que esto evita.")
    estado = EstadoNC(tabla[clave])
    if ORDEN.index(estado) > ORDEN.index(TECHO):
        raise ValueError(
            f"{sistema}/{estado_externo}: la tabla lleva a {estado.value}, por encima del "
            f"techo {TECHO.value}. Ningun estado externo cierra una no conformidad: "
            "VERIFICADA exige una evidencia de eficacia tomada DESPUES de ejecutar.")
    return estado


@dataclass(frozen=True)
class Lectura:
    """Lo que la delegación permite afirmar, y lo que no."""

    delegacion: Delegacion
    estado: EstadoNC
    puede_mover: bool
    por_que_no: dict[str, str] | None = None

    def a_json(self) -> dict[str, Any]:
        d = {"delegacion": self.delegacion.a_json(), "estado": self.estado.value,
             "puede_mover": self.puede_mover}
        if self.por_que_no:
            d["por_que_no"] = self.por_que_no
        return d


def leer(delegacion: Delegacion) -> Lectura:
    """Qué dice esta delegación, y si con eso se puede mover algo.

    Se separa de mover a propósito: la lectura sale igual para un ticket sin
    autor que para uno con él, y lo que cambia es si con ella se puede escribir
    una transición. Fundirlas habría hecho que un ticket sin autor se leyera
    como un ticket sin cambios.
    """
    estado = traducir_estado(delegacion.sistema, delegacion.estado_externo)
    if not delegacion.actor.strip():
        return Lectura(delegacion, estado, False, {
            "es": (f"{delegacion.sistema} no dice quién movió {delegacion.referencia}: una "
                   "transición sin persona no se puede auditar, y aquí no se escribe "
                   "«sistema» en su lugar"),
            "en": (f"{delegacion.sistema} does not say who moved {delegacion.referencia}: a "
                   "transition without a person cannot be audited, and «system» is not "
                   "written in their place")})
    if not delegacion.cuando.strip():
        return Lectura(delegacion, estado, False, {
            "es": f"{delegacion.referencia} no trae cuándo se movió: una transición sin fecha "
                  "no se puede ordenar, y el estado se calcula por fecha",
            "en": f"{delegacion.referencia} carries no date: a transition cannot be ordered "
                  "without one, and state is computed by date"})
    return Lectura(delegacion, estado, True)


def mover(estado_actual: EstadoNC, lectura: Lectura,
          cargo_por_defecto: str = "") -> tuple[Transicion | None, dict[str, str]]:
    """La transición que esta lectura autoriza, o None y por qué no.

    **Sólo hacia delante.** Un tablero es una herramienta de trabajo y las
    tarjetas se arrastran: si arrastrarla hacia atrás reabriera la no
    conformidad, el ciclo de la 10.2 dependería de cómo alguien organiza su
    semana. `reconstruir` ya se niega a retroceder al leer; negarse aquí, al
    escribir, evita además llenar el almacén encadenado de transiciones que no
    significan nada y que un auditor tendría que descartar a mano.

    Y no se puede construir de otra manera: la transición a ABIERTA exige de
    dónde salió y qué se desvió, y un sistema de tickets no lo sabe. Un
    `mover` que devolviera esa transición reventaría al construirla, que es
    peor que decir que no.
    """
    d = lectura.delegacion
    if not lectura.puede_mover:
        return None, (lectura.por_que_no or {
            "es": "esta lectura no autoriza ninguna transición",
            "en": "this reading authorises no transition"})
    if ORDEN.index(lectura.estado) <= ORDEN.index(estado_actual):
        return None, {
            "es": (f"{d.sistema}:{d.referencia} está en «{d.estado_externo}», que aquí es "
                   f"{lectura.estado.value}, y la no conformidad ya está en "
                   f"{estado_actual.value}: una no conformidad no retrocede porque alguien "
                   f"arrastre una tarjeta"),
            "en": (f"{d.sistema}:{d.referencia} is in «{d.estado_externo}», which here is "
                   f"{lectura.estado.value}, and the nonconformity is already at "
                   f"{estado_actual.value}: a nonconformity does not go back because someone "
                   f"drags a card")}
    if lectura.estado is EstadoNC.CON_ACCION:
        # No hay tabla que lleve aqui hoy, y si alguna llegara habria que traer
        # accion, responsable y compromiso del ticket. Se dice en vez de
        # construir una transicion que reventaria.
        return None, {
            "es": ("pasar a CON_ACCION exige acción, responsable y fecha comprometida, y eso "
                   "no sale del estado de un ticket"),
            "en": ("moving to CON_ACCION requires action, owner and committed date, and that "
                   "does not come from a ticket's state")}
    cargo = (d.cargo_del_actor or cargo_por_defecto).strip()
    if not cargo:
        return None, {
            "es": (f"{d.referencia}: consta quién ({d.actor}) pero no en calidad de qué. "
                   f"Pásalo con --cargo si en ese sistema no se guarda."),
            "en": (f"{d.referencia}: who ({d.actor}) is recorded but not in what capacity. "
                   f"Pass it with --cargo if that system does not store it.")}
    t = Transicion(
        no_conformidad_id=d.no_conformidad_id, a=lectura.estado,
        quien=d.actor, cargo=cargo, cuando=d.cuando,
        nota=f"{d.sistema}:{d.referencia} -> {d.estado_externo}")
    return t, {
        "es": f"{d.sistema}:{d.referencia} mueve la no conformidad a {lectura.estado.value}",
        "en": f"{d.sistema}:{d.referencia} moves the nonconformity to {lectura.estado.value}"}
