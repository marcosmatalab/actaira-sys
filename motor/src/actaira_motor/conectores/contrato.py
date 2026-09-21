"""El contrato que cumple todo conector, y la puerta que impide filtrar secretos."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

ESQUEMA = "actaira/fuente/v1"


@dataclass(frozen=True)
class Fuente:
    """De dónde salió el código, con precisión suficiente para repetirlo.

    `referencia_inmutable` es lo único que hace reproducible una evidencia. Una
    fuente que dice «rama main» describe un sitio, no un contenido: mañana es
    otro contenido y la observación de ayer ya no se puede comprobar. Si el
    conector no puede resolverla, `referencia_inmutable` queda a None y el
    motor lo trata como lo que es -no se puede repetir- en vez de fingir que sí.
    """

    conector: str                 # "local" | "git" | ...
    conector_version: str
    ubicacion: str                # lo que el cliente escribió: una URL, una ruta
    referencia_pedida: str        # "main", "v2.1", "HEAD", ""
    referencia_inmutable: str | None = None    # el commit, o None si no se pudo
    detalles: dict[str, str] = field(default_factory=dict)

    @property
    def reproducible(self) -> bool:
        return self.referencia_inmutable is not None

    def a_json(self) -> dict[str, Any]:
        return {"esquema": ESQUEMA, "conector": self.conector,
                "conector_version": self.conector_version,
                "ubicacion": self.ubicacion, "referencia_pedida": self.referencia_pedida,
                "referencia_inmutable": self.referencia_inmutable,
                "reproducible": self.reproducible, "detalles": self.detalles}


@dataclass(frozen=True)
class LimiteDelConector:
    """Lo que este conector NO puede traer, dicho por él mismo.

    Existe porque un conector siempre trae menos de lo que hay: submódulos que
    no se clonan, ficheros grandes que viven en otro almacén, ramas que el
    token no alcanza. Si el límite no viaja con la fuente, el motor observa un
    árbol incompleto creyendo que está completo, que es la peor manera posible
    de equivocarse: no falla nada y el expediente sale limpio.
    """

    que: dict[str, str]
    por_que: str

    def a_json(self) -> dict[str, Any]:
        return {"que": self.que, "por_que": self.por_que}


# Lo que NO puede aparecer en un documento que se firma. La lista es corta y
# gruesa a proposito: un patron fino deja pasar el token del proximo proveedor.
_SECRETOS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"),                    # GitHub
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"glpat-[A-Za-z0-9_\-]{16,}"),                     # GitLab
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),                  # Slack
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                           # claves de API
    re.compile(r"AKIA[0-9A-Z]{16}"),                              # AWS
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"://[^/\s:]+:[^/\s@]+@"),                         # usuario:clave en una URL
)


def sin_secretos(texto: str) -> list[str]:
    """Los secretos que aparecen en un texto. Lista vacía es lista vacía.

    Se aplica al JSON que el conector emite ANTES de que entre en la evidencia.
    El día que un token acabe dentro de un expediente firmado, el expediente
    hay que retirarlo entero: no se puede editar sin romper la firma, y no se
    puede dejar. Por eso la comprobación va en la frontera y no en la revisión.
    """
    return [m.group(0)[:12] + "..." for p in _SECRETOS for m in p.finditer(texto)]


def redactar(texto: str) -> str:
    """El mismo texto con los secretos tachados. MISMA definicion de secreto.

    Detectar y tachar comparten los patrones a proposito: si cada uno tuviera
    los suyos, el detector podria encontrar algo que el redactor no tacha, que
    es la peor combinacion -- la puerta avisa y el texto sigue filtrando.
    """
    for p in _SECRETOS:
        texto = p.sub("[secreto retirado]", texto)
    return texto


@runtime_checkable
class Conector(Protocol):
    """Traer ficheros y decir de dónde salieron. Nada más.

    Cuatro metodos y ninguno devuelve un veredicto. Un conector que evaluara
    metería la doctrina de esta casa en un sitio donde nadie la audita: en el
    código de integración de un tercero.
    """

    nombre: str
    version: str

    def resuelve(self, ubicacion: str) -> bool:
        """Si este conector sabe traer esa ubicacion. Sin efectos."""

    def fuente(self, ubicacion: str, referencia: str = "") -> Fuente:
        """Resuelve la referencia a algo inmutable, sin traer los ficheros todavia."""

    def materializar(self, fuente: Fuente, destino: Path) -> Path:
        """Deja los ficheros en `destino`, que es del que llama. Devuelve la raiz."""

    def limites(self) -> tuple[LimiteDelConector, ...]:
        """Lo que este conector NO trae, para que viaje con la observacion."""


_REGISTRO: list[Conector] = []


def registro() -> list[Conector]:
    """Los conectores disponibles. Se registran al importarse, en orden."""
    if not _REGISTRO:
        from .git import ConectorGit
        from .local import ConectorLocal
        # El LOCAL va el ultimo a proposito: resuelve casi cualquier cosa que
        # parezca una ruta, asi que si fuera el primero se tragaria una URL de
        # git que casualmente existiera como directorio.
        _REGISTRO.extend([ConectorGit(), ConectorLocal()])
    return list(_REGISTRO)


def elegir(ubicacion: str) -> Conector:
    for c in registro():
        if c.resuelve(ubicacion):
            return c
    raise ValueError(
        f"ningun conector sabe traer {ubicacion!r}. Los que hay: "
        + ", ".join(c.nombre for c in registro()))
