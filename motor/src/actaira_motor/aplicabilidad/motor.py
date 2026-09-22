"""Que obligaciones atan a ESTE sistema, por rol, por alcance y por fecha.

PORTADO EN CONCEPTO de plazum `nucleo/aplicabilidad` (Go, 1.246 lineas con
fuzz tests). Lo que se trae es el diseno, no el codigo: alli el espacio de
aplicabilidad se resuelve sobre un corpus normativo generico y aqui sobre dos
catalogos concretos, asi que portar el Go habria sido traducir una abstraccion
que no hace falta. Lo que si se trae literal es la regla que lo hace util: cada
respuesta cita LA REGLA QUE LA PRODUJO, y una respuesta sin regla no se emite.

POR QUE HAY CUATRO SITUACIONES Y NO DOS
---------------------------------------
"Te aplica" y "no te aplica" no cubren el caso que mas se da al empezar de
cero, que es que el perfil todavia no dice lo que hace falta para decidir.
Meter eso en "no te aplica" es la forma mas silenciosa de dejar a alguien sin
cumplir: el sistema le dice que esta limpio porque no le preguntaron.

  ATA            le ata hoy
  FUTURA         le atara desde una fecha, que se nombra
  NO_ATA         no le ata, y se dice por que regla
  INDETERMINADA  el perfil no alcanza para decidir, y se dice que falta

La tercera negativa en su forma mas concreta: INDETERMINADA jamas se pliega a
NO_ATA. El recuento las mantiene separadas y el informe las imprime aparte.

POR QUE EL RELOJ ES UN ARGUMENTO Y NUNCA UNA LLAMADA
-----------------------------------------------------
`resolver()` recibe `cuando`. No lee `date.today()` por dentro. Una funcion de
decision que lee el reloj no es reproducible, y un expediente que no se puede
recomputar manana con el mismo resultado no es evidencia de nada. Es la misma
regla que la constitucion de actaira fija para todo el camino de decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from ..catalogo.cargador import Catalogo, Obligacion
from ..roles import exigir_conocidos


class Situacion(str, Enum):
    ATA = "ata"
    FUTURA = "futura"
    NO_ATA = "no_ata"
    INDETERMINADA = "indeterminada"


# Las obligaciones que sobreviven a la exclusion de codigo abierto del articulo
# 2(12). No es una lista de excepciones al estilo prohibido: es el texto del
# Reglamento, que nombra el articulo 5 y el articulo 50 y el alto riesgo.
SOBREVIVEN_AL_CODIGO_ABIERTO = ("AIA-005", "AIA-050")


@dataclass(frozen=True)
class Perfil:
    """Lo que la organizacion ha respondido. `None` significa sin responder.

    Tres valores por campo booleano y no dos: True, False y None. El None no es
    un descuido de tipado, es el unico que permite distinguir "he dicho que no"
    de "no me lo han preguntado todavia", y esa distincion es la que produce
    INDETERMINADA en vez de un falso NO_ATA.
    """

    roles: frozenset[str] = frozenset()
    # Exclusiones de ambito del articulo 2. Van antes que todo lo demas porque
    # pueden vaciar el plan entero, y casi ningun catalogo las modela.
    fines_militares: bool | None = None
    solo_investigacion: bool | None = None
    es_codigo_abierto: bool | None = None
    es_alto_riesgo: bool | None = None
    # POR DONDE llega a ser de alto riesgo: "anexo_iii" (sistema autonomo del
    # Anexo III, articulo 6.2) o "anexo_i" (componente de seguridad de un
    # producto ya regulado, articulo 6.1). Desde el Reglamento (UE) 2026/1744
    # no es un detalle de clasificacion: decide la FECHA, y son ocho meses.
    via_anexo: str | None = None
    categoria_anexo_iii: str | None = None
    es_sector_publico: bool | None = None
    provee_modelo_uso_general: bool | None = None
    modelo_con_riesgo_sistemico: bool | None = None
    genera_contenido_sintetico: bool | None = None
    interactua_con_personas: bool | None = None
    usa_biometria: bool | None = None

    def __post_init__(self) -> None:
        """Un rol que no existe para el Reglamento para aqui. No sigue.

        POR QUE EN EL CONSTRUCTOR Y NO EN CADA VERBO
        ----------------------------------------------
        `resolver` comparaba `perfil.roles & set(obl.roles)` y, si no cruzaban,
        ponia NO_ATA. Con eso, un rol inexistente producia el mismo documento
        que un rol valido al que de verdad no le ata nada: cero obligaciones
        aplicables, cuarenta y ocho no aplicables, y ni una palabra sobre que el
        motor no habia reconocido a quien preguntaba.

        Eso no es un descuido de validacion en un producto cualquiera. Este
        producto existe para decir que ata a quien; decirle «no te ata nada» a
        alguien cuyo rol no se ha entendido es la afirmacion mas peligrosa que
        puede emitir, y ademas es la que mas se parece a una buena noticia, asi
        que es la que menos se cuestiona.

        Y paso de verdad: el panel mandaba `responsable_del_despliegue`, la API
        lo validaba contra su propia lista -- que tenia el mismo error que el
        panel -- y el motor le contestaba a un responsable del despliegue real
        que no le ataba ninguna de sus trece obligaciones.

        Va en `__post_init__` y no en los ocho sitios del CLI que construyen un
        `Perfil` porque una comprobacion que hay que acordarse de llamar es una
        comprobacion que el noveno sitio no llamara.

        Roles VACIOS si se admiten: es «todavia no me lo han preguntado», y el
        propio `resolver` ya lo convierte en INDETERMINADA con ROL-000. La
        distincion entre no haber contestado y haber contestado algo que no
        existe es justo la que faltaba.
        """
        object.__setattr__(self, "roles", exigir_conocidos(self.roles))

    def sin_responder(self) -> tuple[str, ...]:
        return tuple(
            k for k, v in self.__dict__.items() if v is None
        )


@dataclass(frozen=True)
class Veredicto:
    obligacion_id: str
    situacion: Situacion
    regla: str
    desde: date | None = None
    falta_responder: tuple[str, ...] = ()

    def a_json(self) -> dict[str, Any]:
        return {
            "obligacion_id": self.obligacion_id,
            "situacion": self.situacion.value,
            "regla": self.regla,
            "desde": self.desde.isoformat() if self.desde else None,
            "falta_responder": list(self.falta_responder),
        }


# Cada regla es (id, funcion). El id viaja en el veredicto: sin el, la respuesta
# seria una opinion del motor y no una cita, que es la segunda negativa.
def _alcance(obl: Obligacion, p: Perfil) -> tuple[bool | None, str, tuple[str, ...]]:
    """Decide si el ALCANCE de la obligacion cubre este perfil.

    Devuelve (si/no/no-se, id de regla, campos que faltan). El None del primer
    elemento es lo que se convierte en INDETERMINADA aguas arriba.
    """
    a = obl.alcance
    if a == "todo_sistema":
        return True, "ALC-001 alcance universal: la obligacion no distingue por tipo de sistema", ()
    if a == "alto_riesgo":
        if p.es_alto_riesgo is None:
            return None, "ALC-010 alto riesgo sin resolver", ("es_alto_riesgo",)
        return p.es_alto_riesgo, "ALC-011 alcance limitado a sistemas de alto riesgo del articulo 6", ()
    if a == "alto_riesgo_sector_publico":
        if p.es_alto_riesgo is None or p.es_sector_publico is None:
            faltan = tuple(c for c, v in (("es_alto_riesgo", p.es_alto_riesgo), ("es_sector_publico", p.es_sector_publico)) if v is None)
            return None, "ALC-020 alto riesgo en sector publico sin resolver", faltan
        return bool(p.es_alto_riesgo and p.es_sector_publico), "ALC-021 alcance limitado a organismos publicos con sistemas de alto riesgo", ()
    if a == "modelo_uso_general":
        if p.provee_modelo_uso_general is None:
            return None, "ALC-030 modelo de uso general sin resolver", ("provee_modelo_uso_general",)
        return p.provee_modelo_uso_general, "ALC-031 alcance limitado a proveedores de modelos de IA de uso general", ()
    if a == "modelo_riesgo_sistemico":
        if p.modelo_con_riesgo_sistemico is None:
            return None, "ALC-040 riesgo sistemico sin resolver", ("modelo_con_riesgo_sistemico",)
        return p.modelo_con_riesgo_sistemico, "ALC-041 alcance limitado a modelos con riesgo sistemico del articulo 51", ()
    return None, f"ALC-999 alcance '{a}' no reconocido por este motor", ()


def _excluido(obl: Obligacion, p: Perfil) -> tuple[bool, str]:
    """Las exclusiones de ambito del articulo 2, que van antes que el rol.

    Solo se aplican cuando el perfil las responde que SI. Sin responder no se
    aplican, y el plan las publica aparte como salvedad: convertir todo el plan
    en indeterminado porque nadie ha dicho si el proyecto es de codigo abierto
    seria tan falso como ignorarlas.
    """
    if p.fines_militares is True:
        return True, "EXC-2-3 articulo 2(3): uso exclusivamente militar, de defensa o de seguridad nacional"
    if p.solo_investigacion is True:
        return True, "EXC-2-6 articulo 2(6): investigacion y desarrollo cientificos como unica finalidad"
    if p.es_codigo_abierto is True:
        if obl.id in SOBREVIVEN_AL_CODIGO_ABIERTO:
            return False, ""
        if p.es_alto_riesgo is True:
            return False, ""
        if p.es_alto_riesgo is None:
            return False, ""          # sin resolver el alto riesgo no se excluye nada
        return True, ("EXC-2-12 articulo 2(12): sistema divulgado con licencia libre y de codigo "
                      "abierto, no de alto riesgo y fuera del articulo 5 y del articulo 50")
    return False, ""


def exclusiones_sin_responder(p: Perfil) -> tuple[str, ...]:
    """Las exclusiones que nadie ha respondido y que podrian vaciar el plan."""
    return tuple(c for c in ("fines_militares", "solo_investigacion", "es_codigo_abierto")
                 if getattr(p, c) is None)


def resolver(catalogo: Catalogo, perfil: Perfil, cuando: date) -> list[Veredicto]:
    """El espacio de aplicabilidad completo para este perfil en esta fecha."""
    salida: list[Veredicto] = []
    for obl in catalogo.obligaciones.values():
        fuera, regla_exc = _excluido(obl, perfil)
        if fuera:
            salida.append(Veredicto(obl.id, Situacion.NO_ATA, regla_exc))
            continue
        if not perfil.roles:
            salida.append(Veredicto(obl.id, Situacion.INDETERMINADA,
                                    "ROL-000 no se ha declarado ningun rol", falta_responder=("roles",)))
            continue
        if not (perfil.roles & set(obl.roles)):
            salida.append(Veredicto(
                obl.id, Situacion.NO_ATA,
                f"ROL-010 la obligacion ata a {sorted(obl.roles)} y el perfil declara {sorted(perfil.roles)}"))
            continue

        cubre, regla_alcance, faltan = _alcance(obl, perfil)
        if cubre is None:
            salida.append(Veredicto(obl.id, Situacion.INDETERMINADA, regla_alcance, falta_responder=faltan))
            continue
        if not cubre:
            salida.append(Veredicto(obl.id, Situacion.NO_ATA, regla_alcance))
            continue

        # LA FECHA, QUE DESDE 2026 PUEDE NO TENER RESPUESTA
        # ---------------------------------------------------
        # Si la obligacion trae calendario partido y el perfil no dice por que
        # via es de alto riesgo, la fecha NO se puede contestar. Elegir una
        # seria inventar ocho meses en una direccion o en la otra, asi que sale
        # INDETERMINADA pidiendo el dato, que es la tercera negativa aplicada a
        # algo tan aburrido como una fecha.
        # LA VIA SOLO SE PREGUNTA A QUIEN DICE SER DE ALTO RIESGO
        # ---------------------------------------------------------
        # El calendario partido separa dos maneras de SER de alto riesgo, asi
        # que a quien ha dicho que NO lo es, preguntarle por cual de las dos le
        # aplica es una pregunta sin respuesta. Para ese perfil se toma la
        # fecha TEMPRANA de las dos, que es la unica que no le puede quitar
        # plazo, y el artículo 6 -- que ata a todo el mundo porque clasificar
        # es lo que dice si eres de alto riesgo o no -- deja de pedir un dato
        # que nadie que no sea de alto riesgo puede dar.
        if perfil.es_alto_riesgo is True:
            fecha = obl.desde(perfil.via_anexo)
        elif obl.aplica_desde_por_via:
            fecha = min(obl.aplica_desde_por_via.values())
        else:
            fecha = obl.aplica_desde
        if fecha is None:
            salida.append(Veredicto(
                obl.id, Situacion.INDETERMINADA,
                "FEC-030 el Reglamento (UE) 2026/1744 parte el calendario del Capitulo III: "
                "2 de diciembre de 2027 por el Anexo III y 2 de agosto de 2028 por el Anexo I. "
                "Sin saber por que via es de alto riesgo, la fecha no se puede contestar",
                falta_responder=("via_anexo",)))
            continue
        if cuando >= fecha:
            salida.append(Veredicto(obl.id, Situacion.ATA,
                                    f"FEC-010 aplicable desde {fecha.isoformat()}, y hoy es {cuando.isoformat()}",
                                    desde=fecha))
        else:
            salida.append(Veredicto(obl.id, Situacion.FUTURA,
                                    f"FEC-020 aplicable desde {fecha.isoformat()}, posterior a {cuando.isoformat()}",
                                    desde=fecha))
    return salida


def recuento(veredictos: list[Veredicto]) -> dict[str, int]:
    """Cuenta por situacion. Enteros, nunca una proporcion. Primera negativa."""
    r = {s.value: 0 for s in Situacion}
    for v in veredictos:
        r[v.situacion.value] += 1
    return r
