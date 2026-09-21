"""Capa 4: para ESTE requisito, alcanza lo que hay? Y si no, que falta.

LA FRONTERA QUE ESTE MODULO SOSTIENE
--------------------------------------
Un control puede decir «en estos tres ficheros no aparece ningun marcado».
Solo una politica de suficiencia puede decir «para el articulo 50(2), eso no
alcanza». Y ninguna de las dos puede decir «esta empresa incumple»: eso lo
firma una persona, en la capa 5.

Antes esta capa no existia y su trabajo lo hacia un valor del enumerado,
`INDETERMINADO`, escrito a mano dentro de cada control. Consecuencias que se
vieron en produccion:

  * cada control decidia por su cuenta que era «suficiente», asi que la misma
    pregunta tenia dos respuestas segun quien la mirara;
  * cambiar el criterio obligaba a tocar el codigo del control, con lo que un
    cambio de politica y un cambio de observacion entraban en el mismo commit
    y despues nadie podia decir cual movio el veredicto;
  * y no habia donde escribir POR QUE la politica es esa, asi que el criterio
    vivia en la cabeza de quien escribio el control.

POR QUE `SUFICIENTE` NO ES `CUMPLE`
-------------------------------------
SUFICIENTE dice que la evidencia que el requisito pide esta, esta fresca y es
valida. Es una afirmacion sobre el EXPEDIENTE. Cumplir es una afirmacion sobre
la conducta de una organizacion, y no se sigue de la primera: un expediente
completo de una practica mal hecha sigue siendo un expediente completo.

Por eso `afirma_cumplimiento` esta aqui tambien, y tambien devuelve False
siempre. Si algun dia alguien quiere que devuelva True, tendra que cambiar dos
lineas en dos modulos y explicar las dos.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..evidencia.registro import digest

ESQUEMA = "actaira/suficiencia/v1"


class EstadoSuficiencia(str, Enum):
    SUFICIENTE = "suficiente"        # esta lo que el requisito pide, fresco y valido
    INSUFICIENTE = "insuficiente"    # falta algo concreto, y se nombra
    INDETERMINADA = "indeterminada"  # no se puede decidir, y se dice por que
    NO_EXIGIBLE = "no_exigible"      # el requisito no ata a este perfil hoy

    @property
    def afirma_cumplimiento(self) -> bool:
        """Siempre False. Ver el encabezado de este modulo."""
        return False


@dataclass(frozen=True)
class Falta:
    """Lo que falta, con lo que hay que hacer para que deje de faltar.

    `que_hacer` no es amabilidad: una falta sin accion es una queja, y una lista
    de quejas es lo que hace que un informe de cumplimiento acabe en un cajon.
    """

    que: dict[str, str]
    que_hacer: dict[str, str]
    quien: str                 # el rol al que le toca, no una persona

    def __post_init__(self) -> None:
        for campo, valor in (("que", self.que), ("que_hacer", self.que_hacer)):
            if set(valor) != {"es", "en"}:
                raise ValueError(f"`{campo}` de una falta va en los dos idiomas")

    def a_json(self) -> dict[str, Any]:
        return {"que": self.que, "que_hacer": self.que_hacer, "quien": self.quien}


@dataclass(frozen=True)
class Suficiencia:
    requisito_id: str
    estado: EstadoSuficiencia
    politica: str              # el identificador de la politica que decidio
    politica_version: str
    se_apoya_en: tuple[str, ...] = ()      # identificadores de evidencia VALIDA
    falta: tuple[Falta, ...] = ()
    motivo: dict[str, str] | None = None   # solo para INDETERMINADA y NO_EXIGIBLE

    def __post_init__(self) -> None:
        if self.estado is EstadoSuficiencia.SUFICIENTE:
            if self.falta:
                raise ValueError(
                    f"{self.requisito_id}: suficiente y con faltas a la vez. Si falta algo, "
                    "es insuficiente; si no falta nada, la lista va vacia.")
            if not self.se_apoya_en:
                raise ValueError(
                    f"{self.requisito_id}: suficiente sin apoyarse en ninguna evidencia. "
                    "Eso no es un expediente completo, es un expediente vacio.")
        if self.estado is EstadoSuficiencia.INSUFICIENTE and not self.falta:
            raise ValueError(
                f"{self.requisito_id}: insuficiente sin decir QUE falta es un no_cumple "
                "disfrazado. La tercera negativa exige nombrar la causa.")
        if self.estado in (EstadoSuficiencia.INDETERMINADA, EstadoSuficiencia.NO_EXIGIBLE) \
                and not self.motivo:
            raise ValueError(f"{self.requisito_id}: {self.estado.value} sin motivo escrito")
        if self.motivo is not None and set(self.motivo) != {"es", "en"}:
            raise ValueError(f"{self.requisito_id}: el motivo va en los dos idiomas")

    @property
    def id(self) -> str:
        return digest(self.cuerpo())

    def cuerpo(self) -> dict[str, Any]:
        return {"esquema": ESQUEMA, "requisito_id": self.requisito_id,
                "estado": self.estado.value, "politica": self.politica,
                "politica_version": self.politica_version,
                "se_apoya_en": sorted(self.se_apoya_en),
                "falta": [f.a_json() for f in self.falta], "motivo": self.motivo}

    def a_json(self) -> dict[str, Any]:
        d = dict(self.cuerpo()); d["id"] = self.id
        return d


def desde_evidencia(requisito_id: str, registros, ahora, *, politica: str,
                    politica_version: str, revocadas=frozenset(),
                    revalidaciones=None, digests_actuales=None) -> Suficiencia:
    """Construye la suficiencia MIRANDO el estado de cada evidencia.

    EL AGUJERO QUE ESTO CIERRA
    ----------------------------
    `se_apoya_en` es una lista de identificadores, y nada impedia construir una
    suficiencia SUFICIENTE apoyada en evidencia rancia, superada o revocada. El
    tipo decia «esta, esta fresca y es valida» y solo comprobaba que la lista no
    estuviera vacia: la parte cara de la afirmacion -- la frescura y la validez --
    quedaba a cargo de quien llamara, que es justo donde se pierden.

    Ahora la suficiencia solo se puede construir por aqui cuando viene de
    evidencia, y cada registro pasa por `estado()` con el reloj que se le pase.
    Lo que no cuenta NO desaparece: sale en `falta`, con su motivo y con que
    hacer, porque «tu evidencia caduco» y «nunca tuviste evidencia» piden
    acciones distintas y fundirlas es el error que este arbol persigue.
    """
    from ..evidencia.registro import Estado

    revalidaciones = revalidaciones or {}
    digests_actuales = digests_actuales or {}
    validas, caidas = [], []
    for r in registros:
        estado, motivo = r.estado(
            ahora,
            digest_actual_del_sujeto=digests_actuales.get(r.sujeto_digest),
            revocadas=revocadas,
            visto_de_nuevo=revalidaciones.get(r.id))
        if estado.cuenta:
            validas.append(r.id)
        else:
            caidas.append((r, estado, motivo))

    if not registros:
        return Suficiencia(
            requisito_id=requisito_id, estado=EstadoSuficiencia.INSUFICIENTE,
            politica=politica, politica_version=politica_version,
            falta=(Falta(
                que={"es": "no hay ninguna evidencia observada para este requisito",
                     "en": "there is no observed evidence for this requirement"},
                que_hacer={"es": "corre el control que lo cubre, o aporta lo que pide",
                           "en": "run the control that covers it, or supply what it asks for"},
                quien="tecnico"),))

    if not validas:
        return Suficiencia(
            requisito_id=requisito_id, estado=EstadoSuficiencia.INSUFICIENTE,
            politica=politica, politica_version=politica_version,
            falta=tuple(Falta(
                que={"es": f"la evidencia {r.id[:23]}... esta {e.value}: {m['es']}",
                     "en": f"evidence {r.id[:23]}... is {e.value}: {m['en']}"},
                que_hacer={"es": ("vuelve a observar" if e is Estado.RANCIA
                                  else "aporta evidencia nueva para este sujeto"),
                           "en": ("observe it again" if e is Estado.RANCIA
                                  else "supply fresh evidence for this subject")},
                quien="tecnico") for r, e, m in caidas))

    # Hay evidencia que cuenta. Lo caido sigue nombrandose: que una parte valga
    # no borra que otra haya caducado, y callarlo seria decir que el expediente
    # esta mejor de lo que esta.
    return Suficiencia(
        requisito_id=requisito_id,
        estado=EstadoSuficiencia.SUFICIENTE if not caidas else EstadoSuficiencia.INSUFICIENTE,
        politica=politica, politica_version=politica_version,
        se_apoya_en=tuple(validas),
        falta=tuple(Falta(
            que={"es": f"la evidencia {r.id[:23]}... esta {e.value}: {m['es']}",
                 "en": f"evidence {r.id[:23]}... is {e.value}: {m['en']}"},
            que_hacer={"es": ("vuelve a observar" if e is Estado.RANCIA
                              else "aporta evidencia nueva para este sujeto"),
                       "en": ("observe it again" if e is Estado.RANCIA
                              else "supply fresh evidence for this subject")},
            quien="tecnico") for r, e, m in caidas))
