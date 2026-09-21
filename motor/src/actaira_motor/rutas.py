r"""Como se NOMBRA un fichero dentro del arbol del cliente. Una sola definicion.

POR QUE ESTE FICHERO EXISTE
---------------------------
Habia cuatro sitios que construian el nombre relativo de un fichero, y los
cuatro escribian `str(p.relative_to(raiz))`. En Linux eso da `app/scoring.py`.
En Windows da `app\scoring.py`, y ahi empieza el fallo:

  - Las reglas del catalogo acotan su alcance con `solo_en`, y esas expresiones
    estan escritas con barra: `\.github/workflows/.*\.ya?ml$`. Contra un
    nombre con contrabarra NO casan.
  - Una regla de tipo `contenido` cuyo `solo_en` no casa con ningun fichero no
    se calla: concluye que el fichero no esta y EMITE UN HALLAZGO.

Es decir, el mismo repositorio auditado en Windows salia con no conformidades
que en Linux no tenia. El producto no fallaba ruidosamente ni se abstenia:
afirmaba, y afirmaba lo contrario de la verdad. Es el peor de los tres modos de
fallo posibles y el que la regla de oro prohibe -- fallar hacia reportar no es
fallar hacia INVENTAR -- asi que el nombre se normaliza en el unico sitio donde
se fabrica.

El nombre canonico de un fichero del arbol es su ruta relativa a la raiz con
barra, en todos los sistemas operativos. Es la misma forma que usan git, los
patrones del catalogo y SARIF, asi que ademas es la que el cliente reconoce.
"""
from __future__ import annotations

from pathlib import Path


def nombre_en_el_arbol(raiz: Path, fichero: Path) -> str:
    """La ruta de `fichero` relativa a `raiz`, con barra, en cualquier sistema.

    `PurePath.as_posix()` no toca el disco ni resuelve nada: solo cambia el
    separador. La resolucion de enlaces se decide antes y en otro sitio, que es
    una pregunta de aislamiento y no de nomenclatura.
    """
    return fichero.relative_to(raiz).as_posix()


def es_nombre_canonico(nombre: str) -> bool:
    """Si `nombre` ya esta en la forma que el resto del motor espera.

    Sirve para que las puertas puedan comprobar un arbol entero sin volver a
    tocar el disco, y para que un conector que fabrique nombres por su cuenta
    -- un tar, un zip, una API -- pueda validarse contra la misma definicion.
    """
    return "\\" not in nombre and not nombre.startswith("/")
