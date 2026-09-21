r"""Las puertas que impiden que el producto diga una cosa en Linux y otra en Windows.

POR QUE ESTE FICHERO
---------------------
La auditoria externa corrio la suite en Linux y encontro un fallo. La misma
suite en Windows daba ocho, y uno de ellos no era un fallo de prueba sino del
PRODUCTO: `Arbol.leer` nombraba los ficheros con el separador del sistema, y
las reglas del catalogo acotan su alcance con expresiones escritas con barra.
En Windows `\.github/workflows/.*\.ya?ml$` no casaba con el nombre del fichero
de integracion continua, la regla concluia que no habia integracion continua y
EMITIA una no conformidad. El mismo repositorio, auditado en dos sistemas, daba
dos veredictos, y el de Windows era falso.

Eso es peor que fallar: es afirmar lo contrario de la verdad. La regla de oro
de esta casa es fallar hacia reportar, no hacia inventar, asi que cada cosa que
podia depender de la maquina tiene aqui su puerta.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "motor" / "src"))

from actaira_motor.controles.motor import Arbol                         # noqa: E402
from actaira_motor.rutas import es_nombre_canonico, nombre_en_el_arbol  # noqa: E402
from actaira_motor.texto.codigo import corregir_fuente                  # noqa: E402

FIXTURES = RAIZ / "motor" / "tests" / "fixtures"


@pytest.mark.parametrize("fixture", sorted(p.name for p in FIXTURES.iterdir() if p.is_dir()))
def test_el_arbol_nombra_los_ficheros_igual_en_todos_los_sistemas(fixture):
    """Ni un nombre con contrabarra, en ninguna de las cuatro vistas del arbol.

    Se miran las cuatro -- `todos`, `texto`, `codigo` e `ilegibles` -- y no solo
    la que fallaba, porque el defecto no estaba en una de ellas: estaba en la
    linea que fabricaba el nombre, y cualquiera de las cuatro que se saltara
    esa linea manana volveria a abrir el mismo agujero por otro sitio.
    """
    a = Arbol.leer(FIXTURES / fixture)
    vistas = {"todos": a.todos, "texto": list(a.texto), "codigo": list(a.codigo),
              "ilegibles": [n for n, _ in a.ilegibles]}
    malos = {v: [n for n in ns if not es_nombre_canonico(n)] for v, ns in vistas.items()}
    assert not any(malos.values()), f"nombres con separador del sistema: {malos}"


def test_el_nombre_canonico_lleva_barra_aunque_el_sistema_use_otra_cosa():
    """La unidad de la definicion, sin disco de por medio."""
    assert nombre_en_el_arbol(Path("/r"), Path("/r/a/b/c.py")) == "a/b/c.py"
    assert es_nombre_canonico("a/b/c.py")
    assert not es_nombre_canonico("a\\b\\c.py")


def test_las_reglas_del_catalogo_acotan_con_la_misma_barra_que_produce_el_arbol():
    """Los dos lados del contrato, comprobados contra la MISMA definicion.

    De poco sirve normalizar el nombre si manana alguien escribe un `solo_en`
    con contrabarra: el desajuste volveria, solo que desde el otro extremo.
    """
    malas = []
    for fichero in sorted((RAIZ / "catalogo" / "reglas").glob("*.json")):
        d = json.loads(fichero.read_text(encoding="utf-8"))
        for r in d.get("reglas", []):
            for campo in ("solo_en", "patrones"):
                v = r.get(campo)
                for patron in ([v] if isinstance(v, str) else (v or [])):
                    if "\\\\" in patron:
                        malas.append(f"{fichero.name}:{r['id']}:{campo}: {patron}")
    assert not malas, f"patrones con separador de Windows: {malas}"


def test_el_digest_del_arbol_no_depende_del_sistema_que_lo_lee():
    """El digest resume nombres ademas de contenidos, asi que el separador entraba.

    Una evidencia tomada en Linux y comprobada en Windows habria salido
    superada sin que nada hubiera cambiado, y la invalidacion selectiva entera
    cuelga de este valor.
    """
    a = Arbol.leer(FIXTURES / "clasificador-candidatos")
    assert all("\\" not in n for n in a.texto)
    assert a.digest() == Arbol.leer(FIXTURES / "clasificador-candidatos").digest()


def test_el_corrector_de_tildes_no_entra_en_las_llaves_de_una_f_string():
    """La pasada adversarial que encontro que la herramienta escribia el error.

    `actaira ortografia --arreglar` es lo que recomienda el mensaje de la
    puerta de ortografia. Sobre este fuente convertia la CLAVE `obligacion` en
    una con tilde, que es un KeyError en ejecucion. En Python 3.11 no pasaba,
    porque `tokenize` entregaba la f-string como un solo token; desde PEP 701
    la clave sale como su propio token y la guarda dejo de aplicarse.

    La prueba fija las dos mitades a la vez: la clave NO se toca y la prosa de
    alrededor SI, que es lo que distingue arreglarlo de desactivarlo.
    """
    fuente = (
        "def f(ctx, idioma):\n"
        "    return {'es': f'la obligacion {ctx[\"obligacion\"]} no se corrio',\n"
        "            'en': 'the obligation did not run'}\n"
    )
    salida = corregir_fuente(fuente)
    assert '["obligacion"]' in salida, "acentuo una clave de diccionario"
    assert "obligación" in salida, "y tampoco corrigio la prosa: eso es desactivarlo"
    assert "corrió" in salida


def test_el_corrector_si_corrige_la_prosa_que_vive_dentro_de_las_llaves():
    """La otra mitad: el Anexo V escribe castellano DENTRO de las llaves.

    Saltarse las llaves enteras habria dejado ese texto sin tildes para
    siempre, que es como se rompe un arreglo al hacerlo demasiado ancho.
    """
    fuente = (
        "def f(idioma):\n"
        "    return f'*{\"DERIVADA del codigo\" if idioma == \"es\" else \"DERIVED from code\"}*'\n"
    )
    assert "DERIVADA del código" in corregir_fuente(fuente)


def test_los_logos_incrustados_corresponden_a_los_png_que_hay_en_el_arbol():
    """Un artefacto precalculado que nadie vigila envejece en silencio.

    Los logos se reescalaban en CADA construccion con Pillow, y la salida de
    zlib depende de su version: dos maquinas sanas producian dos `consola.html`
    distintos y la puerta de reproducibilidad fallaba en cualquiera que no
    fuera la del ultimo `make`. Ahora el reescalado esta hecho una vez y
    versionado; lo que esta puerta impide es que el dato se quede viejo.
    """
    marca = RAIZ / "consola" / "marca"
    d = json.loads((marca / "incrustados.json").read_text(encoding="utf-8"))
    for nombre, info in d["logos"].items():
        crudo = (marca / nombre).read_bytes()
        assert hashlib.sha256(crudo).hexdigest() == info["origen_sha256"], (
            f"{nombre} cambio y nadie regenero: corre `python consola/marca/incrustar.py`")
        assert info["datauri"].startswith("data:image/png;base64,")


def test_construir_las_paginas_no_necesita_pillow():
    """Su propio docstring lo prometia y no era verdad.

    Decia que construir no necesita nada instalado mientras importaba Pillow.
    Se comprueba leyendo el fuente y no importando el modulo, porque aqui
    Pillow SI esta instalado y un import que funciona no demuestra nada.
    """
    for guion in (RAIZ / "consola" / "construir.py", RAIZ / "panel" / "construir.py"):
        fuente = guion.read_text(encoding="utf-8")
        cuerpo = fuente.split('"""', 2)[-1]
        assert "PIL" not in cuerpo and "Image" not in cuerpo, \
            f"{guion.name} sigue dependiendo de Pillow para construir"


def test_ningun_guion_del_arbol_invoca_python3_por_su_nombre():
    """`python3` no existe en Windows, y ahi la puerta reventaba en vez de medir.

    Lo que rompe es una INVOCACION, no una mencion, asi que se miran los TOKENS
    de cadena y no el texto de la linea. La primera version de esta puerta
    buscaba con una expresion regular y se cazo a si misma: marcaba el
    comentario que explica por que no se usa `python3`. Una puerta que no
    distingue el uso de la explicacion del uso se acaba desactivando.
    """
    import io
    import tokenize

    # El nombre prohibido se arma en tiempo de ejecucion en vez de escribirse
    # entero. Si estuviera escrito, esta puerta se cazaria a si misma, y la
    # salida natural seria eximir a este fichero de la regla. Una regla con
    # lista de exentos es una regla que manana cubre menos de lo que dice.
    prohibido = "python" + "3"
    malos = []
    for py in sorted((RAIZ / "motor").rglob("*.py")):
        if "fixtures" in py.parts:
            continue
        fuente = py.read_text(encoding="utf-8")
        for tok in tokenize.generate_tokens(io.StringIO(fuente).readline):
            if tok.type != tokenize.STRING:
                continue
            try:
                valor = ast.literal_eval(tok.string)
            except (ValueError, SyntaxError):
                continue
            if valor == prohibido:
                malos.append(f"{py.relative_to(RAIZ)}:{tok.start[0]}")
    assert not malos, f"invocan python3 por su nombre: {malos}"


def test_el_almacen_nunca_escribe_sin_candado_en_ningun_sistema():
    """La rama que no existia, y que costaba el expediente de un cliente.

    `_bloquear` tenia dos ramas: `fcntl.flock` en POSIX y una funcion VACIA
    fuera de POSIX, documentada como «la siguiente lectura detecta la
    bifurcacion». Detectarla despues no es una mitigacion: la cadena se
    encadena hacia atras, asi que la rotura no se recose y el almacen queda
    `AlmacenAlterado` para siempre -- que en este modulo no es un error de
    operacion sino un incidente.

    Esta puerta fija la propiedad, no la implementacion: en cualquier sistema
    donde corra esto tiene que haber un mecanismo de candado de verdad, o el
    camino de escritura tiene que negarse a escribir. Lo que no puede haber es
    una tercera opcion silenciosa.
    """
    from actaira_motor.vigilancia import almacen as alm

    assert alm._flock is not None or alm._msvcrt is not None, (
        "en este sistema no hay candado y el modulo lo tiene que decir, no suplirlo")


def test_ocho_escritores_a_la_vez_dejan_la_cadena_entera():
    """El caso de verdad: ocho pasadas de integracion continua simultaneas.

    El test que ya existia usaba ocho procesos y fallaba de forma intermitente
    en Windows -- una linea que decia ser la cuarta en el quinto sitio. Se
    repite aqui contra la interfaz publica y se comprueba ademas el RECUENTO,
    que es lo que distingue «no se corrompio» de «se perdieron escrituras».
    """
    import concurrent.futures
    import subprocess
    import tempfile

    guion = (
        "import sys\n"
        "from datetime import datetime, timezone\n"
        "from actaira_motor.evidencia.registro import Registro\n"
        "from actaira_motor.vigilancia.almacen import Almacen\n"
        "T = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)\n"
        "r = Registro.nuevo('AIA-009', 'ACT-C-009', 'sha256:' + sys.argv[2], T,\n"
        "                   {'quien': sys.argv[2]}, 30)\n"
        "Almacen.abrir(sys.argv[1]).anadir([r], T)\n"
    )
    entorno = dict(os.environ)
    entorno["PYTHONPATH"] = str(RAIZ / "motor" / "src")
    entorno["PYTHONUTF8"] = "1"
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "ev.jsonl"
        gpath = Path(tmp) / "escritor.py"
        gpath.write_text(guion, encoding="utf-8")

        def correr(i):
            return subprocess.run([sys.executable, str(gpath), str(ruta), f"p{i}"],
                                  env=entorno, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            res = list(ex.map(correr, range(8)))
        malos = [r.stderr[-300:] for r in res if r.returncode]
        assert not malos, malos

        from actaira_motor.vigilancia.almacen import Almacen
        a = Almacen.abrir(str(ruta))
        assert a.verificar_cadena() == [], "la cadena se bifurco con ocho escritores"
        assert len(a.registros()) == 8, (
            f"se serializo pero se perdieron escrituras: {len(a.registros())} de 8")


def test_ningun_fichero_de_texto_del_arbol_lleva_finales_de_linea_de_windows():
    """Un fichero generado en Windows salia con CRLF y en Linux con LF.

    `open(..., "w")` traduce cada salto a `os.linesep` salvo que se le diga lo
    contrario, asi que los mismos guiones producian bytes distintos segun la
    maquina. Rompia tres cosas a la vez, y ninguna de las tres apuntaba a la
    causa: la puerta de reproducibilidad compara bytes y fallaba; `gofmt -l`
    marcaba el fichero generado entero; y un diff de revision salia completo
    sobre un fichero que no habia cambiado, que es la forma de conseguir que
    nadie lea los diffs.

    Es la misma familia que el separador de rutas: algo que depende del sistema
    operativo colandose en un artefacto que tiene que ser igual en todas partes.
    """
    TEXTO = {".py", ".json", ".md", ".go", ".js", ".css", ".html", ".yml",
             ".yaml", ".toml", ".cfg", ".ini", ".txt", ".sh", ".mod"}
    malos = []
    for p in sorted(RAIZ.rglob("*")):
        if not p.is_file() or any(x in p.parts for x in ("__pycache__", ".pytest_cache",
                                                         ".git", "node_modules")):
            continue
        if p.suffix not in TEXTO and p.name not in ("Makefile", "NOTICE", "LICENSE"):
            continue
        if b"\r\n" in p.read_bytes():
            malos.append(p.relative_to(RAIZ).as_posix())
    assert not malos, f"llevan CRLF: {malos}"
