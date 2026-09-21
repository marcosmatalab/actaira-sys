r"""Rellena las CIFRAS de la documentacion desde el arbol. Una fuente, un texto.

POR QUE ESTE FICHERO
---------------------
`docs/ARQUITECTURA.md` empieza diciendo, con estas palabras: «Toda cifra de este
documento sale de un comando que se cita al lado. Ninguna esta escrita a mano».

No era verdad, y no lo era por mucho. El documento decia 24 obligaciones cuando
hay 48, 60 pares del cruce cuando hay 101, 56 preguntas cuando hay 90 y 205
pruebas cuando hay mas de quinientas. Su propio sello de version decia 0.1.0 con
el paquete en 0.14. Es decir: el documento que describe el producto describia
uno que tenia la mitad de tamano, y lo hacia mientras afirmaba que sus cifras
eran comprobables.

Lo que hace dano ahi no es cada numero. Es que la frase de la cabecera convierte
una lista de cifras viejas en una lista de cifras AVALADAS: quien lee deja de
comprobarlas porque el documento le ha dicho que ya estan comprobadas. Una
promesa de procedencia sin nada que la sostenga es peor que no darla.

COMO SE ARREGLA, Y POR QUE NO A MANO
--------------------------------------
Corregir los veinte numeros deja el documento bien hoy y mal dentro de un mes,
porque el mecanismo que los dejo viejos sigue intacto: son numeros escritos a
mano en prosa que nadie vuelve a mirar. Es exactamente lo que ya paso con el
campo `por_que_estan_los_113`, que llevaba la cifra en el NOMBRE y seguia
diciendo 113 con 115 articulos dentro.

Asi que las cifras se marcan y se generan:

    <!--cifra:obligaciones-->48<!--/cifra-->

El marcador es feo y es a proposito: se ve en el diff, sobrevive al renderizado
de Markdown -- un comentario HTML no se pinta -- y hace imposible editar la
cifra sin notar que hay un generador detras.

`--comprobar` no escribe: sale 1 si alguna esta vieja. Lo corre la puerta de
aceptacion, asi que el documento no puede volver a envejecer en silencio.

USO:  python herramientas/generar_docs.py            escribe
      python herramientas/generar_docs.py --comprobar  dice si hay deriva
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "motor" / "src"))

from actaira_motor import __version__                                  # noqa: E402
from actaira_motor.catalogo.cargador import cargar                     # noqa: E402

# El README entraba aqui tarde y por lo mismo que entro ARQUITECTURA.md: tenia
# DOS cifras escritas a mano y las dos estaban viejas. La insignia decia 180
# pruebas con 591 en el arbol, y la prosa decia «Diecinueve» defectos
# adversariales con noventa y tantos en el backlog. Es el documento que mas
# gente lee y el unico que no estaba bajo este mecanismo.
DOCS = (RAIZ / "docs" / "ARQUITECTURA.md", RAIZ / "README.md")

_MARCA = re.compile(r"<!--cifra:([a-z0-9_]+)-->(.*?)<!--/cifra-->", re.S)


def _pruebas() -> int:
    """Las funciones `test_` del arbol. UNA definicion, la de la portada.

    Aqui habia una segunda implementacion de este mismo recuento, y las dos
    discrepaban: esta usaba `rglob` y la de `sitio/cifras.py` usa `glob`, asi
    que esta contaba 562 donde aquella contaba 561. Dos cifras con el mismo
    nombre en el mismo producto, y publicadas las dos.

    Y la que estaba mal era esta. El fichero de mas es
    `motor/tests/fixtures/clasificador-candidatos/evals/test_exactitud.py`, que
    NO es una prueba del producto: es una prueba que vive dentro del
    repositorio de EJEMPLO, el que el producto analiza como sujeto. Contarla
    hinchaba la cifra del README con una prueba de mentira, que es peor que
    quedarse corto: la cifra existe para que alguien se fie de ella.

    Asi que no se arregla copiando el `glob` bueno aqui -- eso dejaria dos
    definiciones de acuerdo por ahora --, se arregla llamando a la unica que
    hay. Es la regla 10 de la casa: dos copias no se suman, se anulan.
    """
    sys.path.insert(0, str(RAIZ / "sitio"))
    from cifras import pruebas
    return pruebas(RAIZ)


def _pruebas_go() -> int:
    n = 0
    for go in sorted((RAIZ / "plataforma").rglob("*_test.go")):
        n += len(re.findall(r"^func Test\w+\(", go.read_text(encoding="utf-8"), re.M))
    return n


def _indeterminadas_con_perfil_vacio() -> int:
    from datetime import date

    from actaira_motor.aplicabilidad.motor import Perfil, Situacion, resolver

    c = cargar(str(RAIZ / "catalogo"))
    return sum(1 for v in resolver(c, Perfil(), date(2027, 12, 2))
               if v.situacion is Situacion.INDETERMINADA)


def _defectos_adversariales() -> int:
    """Los defectos con numero que el backlog da por cerrados.

    Se cuentan del propio fichero y no de la memoria de nadie: el README decia
    «Diecinueve hasta hoy» mucho despues de pasar de noventa, que es la misma
    clase de cifra avalada y falsa que este modulo existe para quitar.
    """
    crudo = (RAIZ / "docs" / "BACKLOG.md").read_text(encoding="utf-8")
    # El numero puede ir seguido de punto o de coma: hay una entrada que
    # empieza «D-23, y esta la cometio el propio arreglo». Una expresion que
    # solo admitia el punto se dejaba esa fuera y publicaba una menos, que en
    # un modulo dedicado a que las cifras sean ciertas tiene su gracia.
    return len(set(re.findall(r"\*\*(D-\d+)[.,]", crudo)))


def cifras() -> dict[str, str]:
    c = cargar(str(RAIZ / "catalogo"))
    por_nivel = Counter(o.nivel for o in c.obligaciones.values())
    iso_nivel = Counter(x.nivel for x in c.controles_iso.values())
    reglas = sorted((RAIZ / "catalogo" / "reglas").glob("*.json"))
    n_reglas = sum(len(json.loads(r.read_text(encoding="utf-8")).get("reglas", []))
                   for r in reglas)
    return {
        "version": __version__,
        "obligaciones": str(len(c.obligaciones)),
        "obligaciones_maquina": str(por_nivel.get("maquina", 0)),
        "obligaciones_generable": str(por_nivel.get("generable", 0)),
        "obligaciones_juzgada": str(por_nivel.get("juzgada", 0)),
        "obligaciones_organizativa": str(por_nivel.get("organizativa", 0)),
        "requisitos": str(len(c.requisitos)),
        "huecos": str(len(c.huecos_de_cobertura())),
        "controles_iso": str(len(c.controles_iso)),
        "controles_iso_maquina": str(iso_nivel.get("maquina", 0)),
        "clausulas": str(len(c.clausulas)),
        "pares": str(len(c.pares)),
        "pares_rotos": str(len(c.verificar_cruce())),
        "preguntas": str(len(c.preguntas)),
        "paquetes_de_reglas": str(len(reglas)),
        "reglas": str(n_reglas),
        "pruebas": str(_pruebas()),
        "defectos_adversariales": str(_defectos_adversariales()),
        "pruebas_go": str(_pruebas_go()),
        # El ejemplo trabajado de la seccion 2: cuantas obligaciones quedan sin
        # resolver con un perfil VACIO. Es la cifra que sostiene la afirmacion
        # de que ningun camino lleva de un perfil sin responder a un resultado
        # limpio, asi que tiene que salir del motor y no de la memoria de nadie.
        "indeterminadas_perfil_vacio": str(_indeterminadas_con_perfil_vacio()),
    }


def aplicar(texto: str, valores: dict[str, str]) -> tuple[str, list[str]]:
    """Devuelve (texto al dia, lista de las que estaban viejas)."""
    viejas: list[str] = []

    def _uno(m: re.Match) -> str:
        clave, tenia = m.group(1), m.group(2)
        if clave not in valores:
            raise SystemExit(
                f"el documento pide la cifra {clave!r} y el generador no la conoce. "
                f"Las que hay: {sorted(valores)}")
        if tenia != valores[clave]:
            viejas.append(f"{clave}: decia {tenia} y son {valores[clave]}")
        return f"<!--cifra:{clave}-->{valores[clave]}<!--/cifra-->"

    return _MARCA.sub(_uno, texto), viejas


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--comprobar", action="store_true",
                   help="no escribe: sale 1 si alguna cifra esta vieja")
    a = p.parse_args()

    valores = cifras()
    todas_viejas: list[str] = []
    marcadas = 0
    for doc in DOCS:
        crudo = doc.read_text(encoding="utf-8")
        marcadas += len(_MARCA.findall(crudo))
        nuevo, viejas = aplicar(crudo, valores)
        todas_viejas += [f"{doc.name} {x}" for x in viejas]
        if nuevo != crudo and not a.comprobar:
            doc.write_text(nuevo, encoding="utf-8", newline="\n")

    if a.comprobar:
        if todas_viejas:
            print("cifras viejas en la documentacion:")
            for x in todas_viejas:
                print("  " + x)
            print("corre `python herramientas/generar_docs.py`")
            return 1
        print(f"{marcadas} cifras al dia en {len(DOCS)} documento(s)")
        return 0
    print(("actualizadas:\n  " + "\n  ".join(todas_viejas)) if todas_viejas
          else f"{marcadas} cifras ya estaban al dia")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
