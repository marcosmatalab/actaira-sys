"""Las dos herramientas que leen el codigo sin ejecutarlo, con UNA sola forma
de correrse.

POR QUE ESTO ES UN FICHERO Y NO DOS LINEAS EN LA PUERTA
---------------------------------------------------------
Ni `ruff` ni `mypy` estaban declarados en `pyproject.toml` ni los corria nadie.
Eso no es lo mismo que no usarlos: lanzados a secas, el primero daba 187 quejas
y el segundo 38 errores, y ninguna de las dos cifras significaba nada, porque no
habia ninguna declaracion de QUE reglas cumple este arbol. Una lista de 187
cosas que nadie va a mirar parece control y no lo es.

Las reglas estan ahora en `pyproject.toml`, con el porque de cada familia
elegida y de cada una descartada. Esto es lo que las corre y lo que compara
`mypy` contra la deuda declarada.

LOS DOS NO SE TRATAN IGUAL, Y ES DELIBERADO
---------------------------------------------
`ruff` tiene que salir LIMPIO. Las reglas que se eligieron son las que cazan
defectos -- un nombre que no existe, una variable que se calcula y se tira, un
`except` que se traga la causa -- y para esas no hay deuda que valga: son
baratas de arreglar y caras de ignorar.

`mypy` NO sale limpio, y no se finge que si. Quedan 38 errores, todos revisados
uno a uno, y ninguno esconde un fallo de ejecucion: son estrechamientos de tipo
que el analizador no sabe hacer. Arreglarlos de verdad es anotar doce modulos
del nucleo de un motor de cumplimiento, y eso tiene su propio riesgo: se hace a
proposito y no de paso. Asi que se declaran en una LISTA con nombre y se vigila
que no cambie.

POR QUE LA LISTA SE MIRA EN LOS DOS SENTIDOS
----------------------------------------------
Un tope numerico se cumple arreglando uno facil y metiendo uno grave. Y una
lista que solo se pone roja cuando CRECE se queda larga de mas en cuanto alguien
arregla algo, y a partir de ahi deja de decir cuanta deuda hay. Asi que sobrar
tambien es rojo, con el mandato que lo arregla.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONOCIDOS = RAIZ / "herramientas" / "mypy-conocidos.txt"

_ERROR = re.compile(r"^(?P<f>.+?):\d+: error: .*\[(?P<c>[a-z-]+)\]\s*$")


class NoSePuedeMedir(Exception):
    """La herramienta no esta instalada, asi que no se ha medido nada.

    Es una excepcion propia porque quien la recoge tiene que distinguirla de
    «he mirado y esta mal». La puerta la traduce a OMITIDA con su motivo, y en
    integracion continua -- donde se corre con `--sin-omitir` -- eso es un rojo:
    alli esta todo instalado, asi que no poder medir significa que algo falta.
    """


def _correr(orden: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([sys.executable, "-m", *orden], cwd=RAIZ,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError as e:                              # pragma: no cover
        raise NoSePuedeMedir(str(e)) from e


def _instalado(modulo: str) -> None:
    r = _correr([modulo, "--version"])
    if r.returncode != 0:
        raise NoSePuedeMedir(
            f"`{modulo}` no esta instalado. Sale de `pip install -e \".[dev]\"`, "
            f"que es donde vive todo lo que la puerta necesita.")


def ruff() -> tuple[int, str]:
    """Devuelve (cuantas quejas, el texto). Cero es lo unico que vale."""
    _instalado("ruff")
    r = _correr(["ruff", "check", "--output-format=concise", "."])
    quejas = [x for x in r.stdout.splitlines() if re.match(r"^\S+:\d+:\d+: ", x)]
    return len(quejas), "\n  ".join(quejas[:25])


def _leer_conocidos() -> list[str]:
    if not CONOCIDOS.is_file():
        return []
    return sorted(x.strip() for x in CONOCIDOS.read_text(encoding="utf-8").splitlines()
                  if x.strip() and not x.lstrip().startswith("#"))


def mypy() -> list[str]:
    """Los errores de hoy, como `fichero: codigo`, ordenados y con repeticiones.

    Con repeticiones a proposito: dos errores del mismo codigo en el mismo
    fichero son dos, y una lista que los funda en uno dejaria colar el segundo.

    NO se guarda el numero de linea. Seria mas preciso y seria inservible: la
    lista se pondria roja cada vez que alguien anade un comentario encima, y una
    puerta que se pone roja por algo que no es un defecto se acaba apagando.
    """
    _instalado("mypy")
    r = _correr(["mypy"])
    fuera = []
    for linea in r.stdout.splitlines():
        m = _ERROR.match(linea.strip())
        if m:
            fuera.append(f"{Path(m.group('f')).as_posix()}: {m.group('c')}")
    return sorted(fuera)


def comparar(hoy: list[str], conocidos: list[str]) -> tuple[list[str], list[str]]:
    """(los que sobran de la lista, los que faltan en la lista).

    Se compara como MULTICONJUNTO y no como conjunto: si se arregla uno de dos
    errores iguales en el mismo fichero, eso tiene que verse.
    """
    restantes = list(conocidos)
    nuevos = []
    for x in hoy:
        if x in restantes:
            restantes.remove(x)
        else:
            nuevos.append(x)
    return restantes, nuevos


def escribir_conocidos() -> int:
    hoy = mypy()
    cabecera = []
    if CONOCIDOS.is_file():
        for linea in CONOCIDOS.read_text(encoding="utf-8").splitlines():
            if linea.strip() and not linea.lstrip().startswith("#"):
                break
            cabecera.append(linea)
    CONOCIDOS.write_text("\n".join(cabecera + hoy) + "\n",
                         encoding="utf-8", newline="\n")
    print(f"{CONOCIDOS.relative_to(RAIZ).as_posix()}: {len(hoy)} conocidos")
    return 0


def main() -> int:
    if "--escribir-conocidos" in sys.argv:
        return escribir_conocidos()
    try:
        n, texto = ruff()
        hoy = mypy()
    except NoSePuedeMedir as e:
        print(f"OMITIDA: {e}", file=sys.stderr)
        return 0
    salida = 0
    if n:
        print(f"ruff: {n} quejas\n  {texto}")
        salida = 1
    else:
        print("ruff: limpio")
    sobran, nuevos = comparar(hoy, _leer_conocidos())
    if nuevos:
        print(f"mypy: {len(nuevos)} error(es) que no estaban declarados:\n  "
              + "\n  ".join(nuevos))
        salida = 1
    if sobran:
        print(f"mypy: {len(sobran)} de la lista ya no ocurren. Se arreglaron y la "
              f"lista se quedo larga:\n  " + "\n  ".join(sobran)
              + "\n  corre `python herramientas/lint.py --escribir-conocidos`")
        salida = 1
    if not nuevos and not sobran:
        print(f"mypy: {len(hoy)} errores, los mismos que la lista declara")
    return salida


if __name__ == "__main__":
    raise SystemExit(main())
