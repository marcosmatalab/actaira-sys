"""Capa 5: la conclusion juridica. Actaira la REGISTRA y no la emite.

LA CUARTA NEGATIVA, CONVERTIDA EN TIPO DE DATOS
-------------------------------------------------
No existe ninguna funcion en este arbol que construya una `Decision` sin una
persona dentro. No es una convencion ni un aviso en el README: el constructor
la exige y revienta sin ella. Un producto de cumplimiento que puede emitir una
conclusion juridica por su cuenta acabara emitiendola, porque siempre hay un
informe que queda mejor con una conclusion al final.

QUE ATA UNA DECISION, Y POR QUE ES UN DIGEST Y NO UNA FECHA
-------------------------------------------------------------
`sobre` es el digest del conjunto de suficiencias sobre el que se decidio. Si
manana cambia una sola de ellas, el digest cambia y la decision queda
atada a un estado del expediente que ya no es el actual: visible, sin que nadie
tenga que acordarse. Una decision atada a una fecha no tiene esa propiedad --
«firmado el 3 de abril» no dice sobre que se firmo -- y es la forma mas comun
de que una aprobacion sobreviva a los hechos que la justificaban.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..evidencia.registro import digest

ESQUEMA = "actaira/decision/v1"


@dataclass(frozen=True)
class Decision:
    sobre: str                 # digest del conjunto de suficiencias
    requisitos: tuple[str, ...]
    quien: str
    cargo: str
    cuando: str
    conclusion: str            # las palabras de quien firma, no las de Actaira
    firma: str | None = None
    clave_publica: str | None = None

    def __post_init__(self) -> None:
        for campo in ("quien", "cargo", "conclusion", "sobre"):
            if not str(getattr(self, campo)).strip():
                raise ValueError(
                    f"una decision sin `{campo}` no es una decision de nadie. Actaira "
                    "registra conclusiones juridicas, no las emite.")
        if not self.requisitos:
            raise ValueError("una decision sin requisitos no decide sobre nada")

    @property
    def id(self) -> str:
        return digest(self.cuerpo())

    def cuerpo(self) -> dict[str, Any]:
        return {"esquema": ESQUEMA, "sobre": self.sobre,
                "requisitos": sorted(self.requisitos), "quien": self.quien,
                "cargo": self.cargo, "cuando": self.cuando,
                "conclusion": self.conclusion}

    def a_json(self) -> dict[str, Any]:
        d = dict(self.cuerpo())
        d.update({"id": self.id, "firma": self.firma, "clave_publica": self.clave_publica})
        return d


    def sigue_atada(self, suficiencias) -> bool:
        """Que esta decision siga hablando del expediente que hay ahora.

        Existe como metodo y no como una comparacion suelta en cada sitio para
        que la pregunta se pueda hacer. Sin ella, `sobre` es un campo que nadie
        mira y una aprobacion sobrevive indefinidamente a los hechos que la
        justificaban, que es el modo de fallo de todas las herramientas que
        guardan aprobaciones con una fecha al lado.
        """
        return self.sobre == digest_de_suficiencias(suficiencias)


def digest_de_suficiencias(suficiencias) -> str:
    """El digest del conjunto, ordenado por requisito. UNA definicion (regla 10).

    Vive aqui, junto a quien lo consume, y no en quien lo produce: si cada lado
    lo calculara a su manera, la comprobacion de que una decision sigue atada a
    su expediente estaria comparando dos formas distintas de resumir lo mismo.
    """
    return digest([s.a_json() for s in sorted(suficiencias, key=lambda x: x.requisito_id)])
