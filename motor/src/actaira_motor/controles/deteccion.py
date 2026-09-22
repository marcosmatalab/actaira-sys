"""Encuentra en el codigo los puntos donde ocurre el hecho que un articulo regula.

ESTE ES EL PUENTE QUE NO TIENE NADIE, Y POR ESO ES EL NUCLEO DEL PRODUCTO
-------------------------------------------------------------------------
Un GRC pregunta "genera tu sistema contenido sintetico" en un formulario. Aqui
se abre el arbol sintactico y se busca la llamada. La diferencia entre las dos
cosas es todo el producto.

POR QUE AST Y NO EXPRESIONES REGULARES
---------------------------------------
Rechazado `grep` sobre el fuente. Una expresion regular no distingue una
llamada de una cadena, de un comentario o de un nombre de variable, y el modo
de fallo que produce es el peor: un falso positivo en un informe de
cumplimiento destruye la confianza en todos los verdaderos. El AST lo
distingue por construccion. Coste: solo lee Python, y un fichero con sintaxis
que este interprete no acepta produce INDETERMINADO con su motivo escrito,
nunca se salta en silencio. Regla 11.

POR QUE LAS FIRMAS SON DATOS Y NO CODIGO
-----------------------------------------
Las firmas viven en `catalogo/reglas/*.json`, escritas por una persona, con su
version, su paquete y su autor. El detector es generico y no conoce ni a OpenAI
ni a Anthropic por su nombre. Anadir un proveedor nuevo es una linea de JSON y
una revision humana, no un despliegue del motor. Segunda negativa: Actaira no
tiene opinion sobre que llamada es una generacion, cita la regla que lo dice.

LO QUE ESTE MODULO NO PUEDE AFIRMAR, DICHO AQUI
------------------------------------------------
Que una llamada este escrita no prueba que se ejecutara, y que no lo este no
prueba que no ocurriera: la configuracion y el codigo DECLARAN, no demuestran
comportamiento. Un import dinamico, una llamada por `getattr` o un servicio en
otro lenguaje son invisibles. Eso no se trata como ausencia: se publica como
limite del control y sale en el informe.
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..rutas import nombre_en_el_arbol


@dataclass(frozen=True)
class Regla:
    id: str
    version: str
    paquete: str
    autor: str
    severidad: str
    firmas: tuple[str, ...]
    titulo: dict[str, str]
    remediacion: dict[str, str]
    # Lo que la regla BUSCA, en los dos idiomas. Viaja a la senal y de ahi al
    # expediente, asi que no puede ser una cadena suelta en castellano: un
    # informe pedido en ingles traeria castellano dentro.
    que_busca: dict[str, str] = field(default_factory=dict)
    requiere_ademas: str | None = None
    requiere_import: tuple[str, ...] = ()


@dataclass(frozen=True)
class Aparicion:
    regla_id: str
    fichero: str
    linea: int
    columna: int
    llamada: str


def cargar_paquete(ruta: str | Path) -> list[Regla]:
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    # `_version` se lee y no se usa: cada regla trae la suya. Esta aqui para que
    # un paquete que no declare la del paquete falle AL CARGARSE, que es donde
    # se puede decir cual es el fichero malo.
    paquete, _version, autor = d["paquete"], d["version"], d["autor"]
    salida = []
    for r in d["reglas"]:
        salida.append(Regla(
            id=r["id"], version=r["version"], paquete=paquete, autor=autor,
            severidad=r["severidad"], firmas=tuple(r.get("firmas", ())),
            titulo=r["titulo"], remediacion=r["remediacion"],
            que_busca=r.get("que_busca", {"es": r["titulo"]["es"], "en": r["titulo"]["en"]}),
            requiere_ademas=r.get("requiere_ademas"),
            requiere_import=tuple(r.get("requiere_import", ())),
        ))
    return salida


def _ruta_punteada(nodo: ast.AST) -> str:
    """El nombre de la llamada tal y como esta escrito, sin resolver alias."""
    partes: list[str] = []
    actual: Any = nodo
    while isinstance(actual, ast.Attribute):
        partes.append(actual.attr)
        actual = actual.value
    if isinstance(actual, ast.Name):
        partes.append(actual.id)
    elif isinstance(actual, ast.Call):
        partes.append("()")
    return ".".join(reversed(partes))


def _importa_paquete(arbol: ast.AST) -> set[str]:
    """Que paquetes de primer nivel importa el fichero."""
    out: set[str] = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.add(a.name.split(".")[0]); out.add(a.name)
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            out.add(n.module.split(".")[0]); out.add(n.module)
    return out


def _casa(ruta: str, firma: str) -> bool:
    """Casa por sufijo de segmentos: `client.images.generate` casa `images.generate`.

    Por sufijo y no por igualdad porque el nombre de la variable del cliente es
    del cliente y cambia en cada repositorio. Por segmentos y no por subcadena
    porque `mis_images.generate` no es `images.generate` y una subcadena no los
    distingue.
    """
    a, b = ruta.split("."), firma.split(".")
    return len(a) >= len(b) and a[-len(b):] == b


@dataclass
class Barrido:
    apariciones: list[Aparicion]
    ficheros_leidos: int
    ficheros_ilegibles: list[tuple[str, str]]

    @property
    def por_regla(self) -> dict[str, list[Aparicion]]:
        d: dict[str, list[Aparicion]] = {}
        for a in self.apariciones:
            d.setdefault(a.regla_id, []).append(a)
        return d


def barrer(raiz: str | Path, reglas: list[Regla]) -> Barrido:
    raiz = Path(raiz)
    apariciones: list[Aparicion] = []
    ilegibles: list[tuple[str, str]] = []
    leidos = 0
    for py in sorted(raiz.rglob("*.py")):
        if any(p in {".git", "__pycache__", ".venv", "node_modules"} for p in py.parts):
            continue
        try:
            arbol = ast.parse(py.read_text(encoding="utf-8", errors="strict"))
        except (SyntaxError, UnicodeDecodeError) as e:
            ilegibles.append((nombre_en_el_arbol(raiz, py), f"{type(e).__name__}: {e}"))
            continue
        leidos += 1
        paquetes = _importa_paquete(arbol)
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            ruta = _ruta_punteada(nodo.func)
            if not ruta:
                continue
            for regla in reglas:
                # La firma sola no basta: la pasada adversarial de la fase 2
                # demostro que `correo.messages.create` casa `messages.create`.
                # El fichero tiene que importar ademas el paquete del proveedor.
                if regla.requiere_import and not (paquetes & set(regla.requiere_import)):
                    continue
                if any(_casa(ruta, f) for f in regla.firmas):
                    apariciones.append(Aparicion(
                        regla.id, nombre_en_el_arbol(raiz, py), nodo.lineno, nodo.col_offset, ruta))
    return Barrido(apariciones, leidos, ilegibles)
