"""Las tildes de los textos en castellano que viven DENTRO del codigo.

El catalogo tiene su puerta desde la fase 7, pero no todo el castellano que ve
un cliente sale del catalogo: los motivos de ausencia del Anexo IV, las notas
de las declaraciones y los avisos del CLI se escriben en Python. Ese texto se
quedo sin corregir y la puerta no lo veia, asi que el expediente decia
«no se encontro ninguna declaracion de dependencias» delante de un auditor.

COMO SE LOCALIZA, Y POR QUE NO VALE UN BUSCAR-Y-REEMPLAZAR
------------------------------------------------------------
Un `.py` esta lleno de cadenas que NO son para el cliente: identificadores,
expresiones regulares, claves de diccionario, docstrings. Acentuarlas romperia
el programa o llenaria el diff de ruido.

Lo que se corrige es exactamente el valor `es` de un diccionario que tambien
tiene `en`, que es la forma que tiene este arbol de decir «esto es texto
bilingue para una persona». Se localiza con `ast`, que da la posicion exacta
del nodo, y se reescriben SOLO los tokens de cadena dentro de ese tramo, con lo
que la concatenacion implicita de varias lineas se maneja sola.
"""
from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

from .ortografia import corregir


def _tramos_es(fuente: str) -> tuple[list[tuple], list[tuple]]:
    """Las posiciones del castellano para personas, en DOS clases.

    Devuelve `(hojas, literales)`:

      hojas      tramos de una cadena que es prosa ENTERA. Todo lo que caiga
                 dentro es texto para una persona.
      literales  tramos de una f-string cuya parte literal es prosa pero cuyas
                 llaves son codigo. Dentro solo se corrige el texto de fuera de
                 las llaves.

    POR QUE DOS Y NO UNA, QUE ES COMO ESTABA
    -----------------------------------------
    Habia una sola lista y se tomaba el tramo ENTERO del valor `es`, f-strings
    incluidas. Con eso, `f"la obligacion {ctx['obligacion']} ..."` marcaba como
    prosa tambien la clave `'obligacion'`, que es codigo. En Python 3.11 no se
    notaba porque `tokenize` entregaba la f-string como un solo token y
    `_corregir_fuera_de_llaves` salvaba el caso; desde PEP 701 (Python 3.12) la
    clave sale como su propio token `STRING` y se acentuaba, produciendo un
    `KeyError` en ejecucion. La herramienta que arregla la ortografia escribia
    el error, y lo escribia justo cuando el mensaje de la puerta pedia correrla.

    La leccion que queda en la forma: la prosa no se decide por el texto de un
    token sino por el NODO que lo contiene. Un `Constant` de cadena es prosa;
    una `FormattedValue` es codigo; y si dentro de esas llaves vuelve a haber
    prosa -- `f"*{'DERIVADA del codigo' if idioma == 'es' else ...}*"`, que es
    como escribe el Anexo V -- el recorrido del arbol la encuentra por su
    cuenta y la anota como hoja. No hace falta descender a mano.
    """
    hojas: list[tuple] = []
    literales: list[tuple] = []

    def _anotar(v) -> None:
        if v.end_lineno is None:
            return
        tramo = (v.lineno, v.col_offset, v.end_lineno, v.end_col_offset)
        if isinstance(v, ast.JoinedStr):
            literales.append(tramo)
        elif isinstance(v, ast.Constant) and isinstance(v.value, str):
            hojas.append(tramo)

    arbol = ast.parse(fuente)

    for n in ast.walk(arbol):
        if not isinstance(n, ast.Dict):
            continue
        claves = [k.value for k in n.keys
                  if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        if "es" not in claves or "en" not in claves:
            continue
        for k, v in zip(n.keys, n.values):
            if isinstance(k, ast.Constant) and k.value == "es":
                _anotar(v)

    # La otra forma que tiene este arbol de escribir castellano para una
    # persona: `"..." if idioma == "es" else "..."`. La encontro el propio
    # producto, porque el encabezado de la declaracion UE de conformidad seguia
    # diciendo "Declaracion" mientras el resto del documento ya llevaba tildes.
    for n in ast.walk(arbol):
        if not isinstance(n, ast.IfExp) or not isinstance(n.test, ast.Compare):
            continue
        izq, ops, der = n.test.left, n.test.ops, n.test.comparators
        if not (isinstance(izq, ast.Name) and izq.id == "idioma"
                and len(ops) == 1 and isinstance(ops[0], ast.Eq)
                and isinstance(der[0], ast.Constant) and der[0].value == "es"):
            continue
        _anotar(n.body)
    return hojas, literales


def _dentro(tok, tramos) -> bool:
    for l0, c0, l1, c1 in tramos:
        if (tok.start[0], tok.start[1]) >= (l0, c0) and (tok.end[0], tok.end[1]) <= (l1, c1):
            return True
    return False


def _corregir_fuera_de_llaves(texto: str) -> str:
    """Corrige el texto de una cadena SIN entrar en las llaves de una f-string.

    Esto costo un identificador. `tokenize` entrega una f-string entera como un
    solo token, asi que corregir el token acentuaba tambien lo de dentro de las
    llaves: `f"{_CLAUSULA_FUENTE['es']}"` se convirtio en
    `f"{_Cláusula_FUENTE['es']}"` y el modulo dejo de importar. Una herramienta
    que arregla la ortografia y rompe el programa no la usa nadie dos veces.

    Las llaves dobles son escapes y no abren expresion; se tratan como texto.
    """
    fuera, i, dentro = [], 0, 0
    while i < len(texto):
        c = texto[i]
        if c in "{}" and i + 1 < len(texto) and texto[i + 1] == c:
            fuera.append(texto[i:i + 2]); i += 2; continue
        if c == "{":
            dentro += 1; fuera.append(c); i += 1; continue
        if c == "}":
            dentro = max(0, dentro - 1); fuera.append(c); i += 1; continue
        j = i
        while j < len(texto) and texto[j] not in "{}":
            j += 1
        trozo = texto[i:j]
        fuera.append(trozo if dentro else corregir(trozo))
        i = j
    return "".join(fuera)


# PEP 701 partio las f-strings en tres tipos de token a partir de Python 3.12.
# En 3.11 y antes no existen, asi que se piden con `getattr` y el codigo vale
# para las dos formas de tokenizar sin ramificar por version del interprete.
_F_INICIO = getattr(tokenize, "FSTRING_START", None)
_F_MEDIO = getattr(tokenize, "FSTRING_MIDDLE", None)
_F_FIN = getattr(tokenize, "FSTRING_END", None)


# PEP 701 partio las f-strings en tres tipos de token a partir de Python 3.12.
# En 3.11 y antes no existen, asi que se piden con `getattr` y el resto del
# codigo vale para las dos formas de tokenizar sin ramificar por version.
_F_MEDIO = getattr(tokenize, "FSTRING_MIDDLE", None)


def _es_una_fstring(tok) -> bool:
    """Si el token es una f-string entera, que es como las entrega Python 3.11."""
    prefijo = tok.string[:3].lower()
    return "f" in prefijo.split('"')[0].split("'")[0]


def corregir_fuente(fuente: str) -> str:
    """Devuelve el fuente con las tildes puestas. Idempotente, y no toca nada mas.

    Se corrige un token cuando, y solo cuando, el arbol sintactico dice que lo
    que ocupa es prosa:

      - cae dentro de una HOJA -- una cadena que es prosa entera -- sea la que
        sea su clase de token;
      - o es la parte literal de una f-string marcada como tal. Desde PEP 701
        esa parte llega como `FSTRING_MIDDLE`; en Python 3.11 y antes llega la
        f-string entera como un `STRING` y hay que saltarse sus llaves a mano,
        que es lo que hace `_corregir_fuera_de_llaves`.

    Lo que NO se corrige nunca es un token que este dentro de las llaves de una
    f-string sin ser ademas hoja por su cuenta. Ahi vive el codigo: claves de
    diccionario, nombres, llamadas. Acentuar uno rompe el programa, y esta
    funcion lo hizo hasta que se separaron las dos clases de tramo.
    """
    hojas, literales = _tramos_es(fuente)
    if not hojas and not literales:
        return fuente
    lineas = fuente.splitlines(keepends=True)
    ediciones: list[tuple[int, int, int, str]] = []
    for tok in tokenize.generate_tokens(io.StringIO(fuente).readline):
        es_cadena = tok.type == tokenize.STRING
        es_medio = _F_MEDIO is not None and tok.type == _F_MEDIO
        if not (es_cadena or es_medio):
            continue
        if _dentro(tok, hojas):
            pass                          # prosa entera: se corrige
        elif _dentro(tok, literales) and (es_medio or _es_una_fstring(tok)):
            pass                          # parte literal de una f-string
        else:
            continue
        if tok.start[0] != tok.end[0]:
            continue                      # una cadena de varias lineas: se deja
        origen = lineas[tok.start[0] - 1][tok.start[1]:tok.end[1]]
        if origen != tok.string:
            # El token no coincide con el fuente que ocupa: pasa con algunos
            # escapes de `FSTRING_MIDDLE`, que llegan ya decodificados.
            # Reescribir ahi cambiaria bytes que nadie ha mirado, asi que se
            # deja estar en vez de arriesgar el fichero.
            continue
        nuevo = _corregir_fuera_de_llaves(tok.string)
        if nuevo != tok.string:
            ediciones.append((tok.start[0], tok.start[1], tok.end[1], nuevo))
    for ln, c0, c1, nuevo in sorted(ediciones, reverse=True):
        linea = lineas[ln - 1]
        lineas[ln - 1] = linea[:c0] + nuevo + linea[c1:]
    return "".join(lineas)


def sucios(raiz: str | Path) -> list[str]:
    """Los modulos a los que les faltan tildes en su texto para personas."""
    fuera = []
    for ruta in sorted(Path(raiz).rglob("*.py")):
        fuente = ruta.read_text(encoding="utf-8")
        if corregir_fuente(fuente) != fuente:
            fuera.append(str(ruta))
    return fuera
