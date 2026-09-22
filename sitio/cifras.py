"""Las cifras de la portada, sacadas del arbol y de nadie mas.

POR QUE ESTE FICHERO EXISTE
-----------------------------
La version anterior de actaira.com afirmaba «2.487 tests» y «16 limites
publicados». No salian de ningun sitio. Una pagina de producto que inventa una
cifra sobre su propia herramienta de cumplimiento es la peor tarjeta de
presentacion posible, y eso no se arregla corrigiendo el numero: se arregla
quitando la posibilidad de escribirlo a mano.

Y POR QUE LAS PRUEBAS SE CUENTAN LEYENDO EL CODIGO, NO CORRIENDOLO
-------------------------------------------------------------------
La primera puerta contaba lo que `pytest --collect-only` recogia AQUI, y eso
depende del entorno: el auditor externo, sin `jsonschema` instalado, recogio
193 donde esta casa recogia 205, porque doce pruebas del contrato se saltaban.
Una cifra publicada que cambia segun que tenga instalado quien la mide no es
una cifra sobre el producto, es una cifra sobre la maquina.

Asi que se cuentan las funciones `test_` leyendo los ficheros con `ast`. Sale
el mismo numero en cualquier maquina, sin importar nada y sin correr nada, y es
exactamente el numero de afirmaciones que el arbol se compromete a sostener.
"""
from __future__ import annotations

import ast
import glob
import json
from pathlib import Path


def pruebas(raiz: Path) -> int:
    """Las funciones `test_` del arbol. Deterministico: ni importa ni ejecuta."""
    n = 0
    for f in sorted((raiz / "motor" / "tests").glob("test_*.py")):
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and nodo.name.startswith("test_"):
                n += 1
    return n


def invalidacion_selectiva(raiz: Path) -> tuple[int, int]:
    """(superadas, total) al tocar UN fichero del repositorio de prueba.

    Es la medida que sostiene la afirmacion del foso, asi que se mide y no se
    escribe. Antes estaba puesta a mano en la portada y ya se habia quedado
    vieja dos veces: la primera al arreglar la invalidacion excesiva (D-14) y
    la segunda al anadir el paquete del articulo 5, que sumo un control mas al
    denominador sin que nadie tocara la pagina.
    """
    import shutil, sys, tempfile
    from datetime import datetime, timedelta, timezone

    sys.path.insert(0, str(raiz / "motor" / "src"))
    from actaira_motor.aplicabilidad.motor import Perfil
    from actaira_motor.catalogo.cargador import cargar
    from actaira_motor.vigilancia.almacen import Almacen
    from actaira_motor.vigilancia.barrido import observar
    from actaira_motor.vigilancia.reconciliar import reconciliar

    cat = cargar(str(raiz / "catalogo"))
    perfil = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii")
    t0 = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        shutil.copytree(raiz / "motor" / "tests" / "fixtures" / "clasificador-candidatos", repo)
        alm = Almacen.abrir(Path(tmp) / "ev.jsonl")
        regs, _s, _e, _ = observar(cat, perfil, t0.date(), repo, raiz / "catalogo" / "reglas", t0)
        alm.anadir(regs, t0)
        leeme = repo / "datos" / "README.md"
        leeme.write_text(leeme.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        t1 = t0 + timedelta(hours=1)
        _r, sujetos, esperados, _ = observar(cat, perfil, t1.date(), repo,
                                             raiz / "catalogo" / "reglas", t1)
        rec = reconciliar(alm, sujetos, t1, esperados=esperados).a_json()["recuento"]
    return rec.get("superada", 0), rec.get("superada", 0) + rec.get("valida", 0)


# La unica palabra que viaja DENTRO de una cifra, y por eso vive aqui.
#
# Las barras dicen «14 / 14 superados». El numero sale del arbol y la palabra
# no, asi que la portada inglesa decia «superados» en medio de una frase en
# ingles. Se resuelve dando idioma a quien calcula la cifra, y no parcheando la
# palabra despues: parchear una palabra dentro de un valor ya calculado es
# inventarse una segunda fuente para lo mismo.
SUPERADOS = {"es": "superados", "en": "superseded", "fr": "remplacées",
             "pt": "substituídas", "it": "sostituite", "de": "ersetzt"}


def de(raiz: str | Path, idioma: str = "es") -> dict[str, str]:
    """Todas las cifras de la portada, con la etiqueta con la que se publican."""
    import sys
    raiz = Path(raiz)
    sys.path.insert(0, str(raiz / "motor" / "src"))
    from actaira_motor.catalogo.cargador import cargar

    cat = cargar(str(raiz / "catalogo"))
    reglas = sum(len(json.load(open(f, encoding="utf-8"))["reglas"])
                 for f in glob.glob(str(raiz / "catalogo" / "reglas" / "*.json")))
    cruzadas = len([q for q in cat.preguntas.values()
                    if any(i.startswith("AIA-") for i in q.sirve_a)
                    and any(i.startswith(("ISO-", "A.")) for i in q.sirve_a)])
    return {
        "obligaciones del Reglamento": str(len(cat.obligaciones)),
        "controles y cláusulas ISO": f"{len(cat.controles_iso)}+{len(cat.clausulas)}",
        "reglas de código": str(reglas),
        "pruebas": str(pruebas(raiz)),
        "Preguntas del banco": str(len(cat.preguntas)),
        "Que sirven a los dos marcos a la vez": str(cruzadas),
        "Que tu código contesta solo": str(len([q for q in cat.preguntas.values()
                                                if q.salta_si_cubre])),
        **_barras(raiz, idioma),
    }


def _barras(raiz: Path, idioma: str = "es") -> dict[str, str]:
    """Las tres barras de la comparacion, derivadas de UNA medida.

    La de en medio se mide; las otras dos son lo que darian las dos maneras que
    usan los demas -- invalidar por el digest del repositorio entero, y caducar
    por el nombre del control -- sobre exactamente el mismo caso. Derivarlas de
    la misma medida es lo que impide que la comparacion se vuelva favorable
    sola cuando cambie el denominador.
    """
    superadas, total = invalidacion_selectiva(raiz)
    return {
        "Digest del repositorio entero": f"{total} / {total} {SUPERADOS[idioma]}",
        "Actaira: digest del sujeto": f"{superadas} / {total} {SUPERADOS[idioma]}",
        "Caducidad por nombre de control": f"0 / {total} {SUPERADOS[idioma]}",
    }


if __name__ == "__main__":
    for k, v in de(Path(__file__).resolve().parents[1]).items():
        print(f"{v:>8}  {k}")
