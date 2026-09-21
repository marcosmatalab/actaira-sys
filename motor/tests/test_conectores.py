"""Fase 18: el contrato de conector, y las cuatro negativas que lo definen.

El contrato va ANTES que los conectores, y no al reves. Un contrato sacado del
primer conector real acaba teniendo su forma: `owner/repo`, `pull_request`,
`installation_id`, y entonces el de Azure DevOps no encaja y el «adaptador
generico» acaba siendo un `if` dentro del de GitHub.

Por eso el primer conector que lo implementa es el LOCAL: un directorio. Si el
contrato aguanta un directorio y un repositorio remoto sin un `if`, aguanta los
demas.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from actaira_motor.conectores import registro
from actaira_motor.conectores.contrato import (Conector, Fuente, elegir,
                                               sin_secretos)
from actaira_motor.conectores.git import ConectorGit, ErrorDelConector
from actaira_motor.conectores.local import ConectorLocal

HAY_GIT = subprocess.run(["which", "git"], capture_output=True).returncode == 0


# --- el contrato ----------------------------------------------------------

def test_todos_los_conectores_cumplen_el_mismo_protocolo():
    for c in registro():
        assert isinstance(c, Conector), c.nombre
        assert c.nombre and c.version
        assert c.limites(), f"{c.nombre}: un conector siempre trae menos de lo que hay"


def test_ningun_conector_tiene_un_metodo_que_decida():
    """Un conector trae ficheros y dice de donde salieron. Nada mas.

    Si evaluara, meteria la doctrina de esta casa en el codigo de integracion
    de un tercero, que es un sitio donde nadie la audita.
    """
    prohibidos = ("evaluar", "juzgar", "puntuar", "clasificar", "cumple",
                  "resultado", "veredicto", "score")
    for c in registro():
        for nombre in dir(c):
            if nombre.startswith("_"):
                continue
            assert not any(p in nombre.lower() for p in prohibidos), (c.nombre, nombre)


def test_el_local_va_el_ultimo_para_no_tragarse_una_url():
    """Resuelve casi cualquier cosa que parezca una ruta: si fuera el primero,
    se tragaria una URL de git que casualmente existiera como directorio."""
    nombres = [c.nombre for c in registro()]
    assert nombres.index("local") == len(nombres) - 1


def test_una_ubicacion_que_nadie_sabe_traer_lo_dice():
    with pytest.raises(ValueError, match="ningun conector"):
        elegir("ftp://algo/que/nadie/trae")


# --- la segunda regla: la referencia inmutable ----------------------------

def test_un_directorio_local_declara_que_no_es_reproducible(tmp_path):
    """La tentacion es poner la fecha de modificacion y llamarlo referencia.

    No lo es: una referencia inmutable identifica un contenido ANTES de leerlo
    y le sirve a otro para traerlo igual. Un directorio local no le sirve a
    nadie mas, y decirlo es mejor que fingirlo.
    """
    f = ConectorLocal().fuente(str(tmp_path))
    assert f.referencia_inmutable is None
    assert not f.reproducible
    assert "referencia inmutable" in f.detalles["nota"]


def test_y_lo_publica_tambien_como_limite(tmp_path):
    limites = ConectorLocal().limites()
    assert any("no se puede repetir" in l.que["es"] for l in limites)
    assert all(l.que["en"] for l in limites)


def test_git_se_niega_a_materializar_sin_referencia_inmutable(tmp_path):
    """Materializarla daria un arbol que manana es otro."""
    f = Fuente("git", "1.0.0", "https://ejemplo/x.git", "main", None)
    with pytest.raises(ErrorDelConector, match="no se podria repetir|no tiene referencia"):
        ConectorGit().materializar(f, tmp_path / "destino")


def test_git_no_pregunta_cuando_la_referencia_ya_es_un_commit():
    """Resolver cuesta una llamada de red. Si ya es inmutable, no hay nada que
    resolver, y el conector no llama a nadie."""
    sha = "a" * 40
    f = ConectorGit().fuente("https://ejemplo/x.git", sha)
    assert f.referencia_inmutable == sha
    assert f.reproducible
    assert "ya era un commit" in f.detalles["resuelto_por"]


# --- la tercera regla: nada del cliente se queda --------------------------

def test_el_local_no_copia_el_directorio_a_ningun_sitio(tmp_path):
    """Copiarlo habria dejado una segunda copia del codigo del cliente en un
    sitio que el no eligio."""
    (tmp_path / "x.py").write_text("y = 1\n", encoding="utf-8")
    c = ConectorLocal()
    raiz = c.materializar(c.fuente(str(tmp_path)), tmp_path / "otro")
    assert raiz == tmp_path.resolve()
    assert not (tmp_path / "otro").exists(), "no se crea ningun destino"


def test_git_se_niega_a_escribir_en_un_destino_que_no_esta_vacio(tmp_path):
    destino = tmp_path / "d"
    destino.mkdir()
    (destino / "algo").write_text("ya habia algo\n", encoding="utf-8")
    f = Fuente("git", "1.0.0", "https://ejemplo/x.git", "main", "b" * 40)
    with pytest.raises(ErrorDelConector, match="no esta vacio"):
        ConectorGit().materializar(f, destino)


# --- la cuarta regla: las credenciales no entran en el expediente ---------

def test_la_puerta_de_secretos_reconoce_los_que_se_ven_de_verdad():
    casos = [
        "ghp_" + "a" * 36,
        "github_pat_" + "b" * 30,
        "glpat-" + "c" * 20,
        "sk-" + "d" * 32,
        "AKIA" + "E" * 16,
        "https://usuario:contrasena@servidor/repo.git",
        "-----BEGIN RSA PRIVATE KEY-----",
    ]
    for c in casos:
        assert sin_secretos(f"algo antes {c} algo despues"), c


def test_y_no_se_inventa_secretos_donde_no_los_hay():
    """El gemelo: un patron que salte con cualquier cosa se desactiva en una
    semana, y con el se desactiva la puerta entera."""
    for limpio in ("https://github.com/marcosmatalab/actaira.git",
                   "sha256:aa11bb22", "el token va en la variable de entorno",
                   "commit a1b2c3d4e5f6", "usuario@empresa.com"):
        assert sin_secretos(limpio) == [], limpio


def test_ninguna_fuente_emitida_lleva_secretos_dentro(tmp_path):
    """Se comprueba sobre el JSON que se emite, que es lo que acaba firmado."""
    import json

    f = ConectorLocal().fuente(str(tmp_path))
    assert sin_secretos(json.dumps(f.a_json(), ensure_ascii=False)) == []


@pytest.mark.skipif(not HAY_GIT, reason="git no esta instalado")
def test_un_error_de_git_sale_sin_la_url_con_credenciales(tmp_path):
    """De aqui sale a un log, y de un log sale a cualquier sitio."""
    with pytest.raises(ErrorDelConector) as e:
        ConectorGit().fuente("https://usuario:secretisimo@127.0.0.1:1/x.git", "main")
    assert "secretisimo" not in str(e.value)


# --- que el conector alimenta al motor sin que el motor sepa de conectores -

@pytest.mark.skipif(not HAY_GIT, reason="git no esta instalado")
def test_el_motor_observa_lo_que_trae_el_conector_sin_saber_de_donde(tmp_path):
    """El motor recibe una ruta. No sabe si vino de un directorio o de un clon,
    y esa ignorancia es el contrato funcionando."""
    from actaira_motor.controles.motor import Arbol

    origen = tmp_path / "origen"
    origen.mkdir()
    (origen / "x.py").write_text("y = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(origen)], check=True)
    subprocess.run(["git", "-C", str(origen), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(origen), "-c", "user.email=a@b", "-c", "user.name=a",
                    "commit", "-qm", "uno"], check=True)

    c = ConectorGit()
    f = c.fuente(str(origen), "HEAD")
    assert f.reproducible, "un repositorio de verdad si resuelve a un commit"
    raiz = c.materializar(f, tmp_path / "destino")
    a = Arbol.leer(raiz)
    assert "x.py" in a.ficheros
    assert not (raiz / ".git").exists(), "el clon no deja el .git del cliente detras"


# --- el verbo, de punta a punta -------------------------------------------

import json as _json
import os
import subprocess as _sp
import sys as _sys

RAIZ = Path(__file__).resolve().parents[2]
ENT = {**os.environ, "PYTHONPATH": str(RAIZ / "motor" / "src"), "PYTHONIOENCODING": "utf-8"}
FIX = str(RAIZ / "motor" / "tests" / "fixtures" / "repo-con-agentes")


def _cli(*args):
    return _sp.run([_sys.executable, "-m", "actaira_motor.cli", *args],
                   cwd=RAIZ, env=ENT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_conectar_se_niega_a_observar_lo_que_no_se_puede_repetir():
    """Y NO lo hace en silencio ni lo hace igual: para y lo explica.

    Es una decision de producto discutible y por eso tiene salida: quien
    quiera observar un directorio local -que es el caso de un cliente que no
    da acceso a su repositorio- lo dice en voz alta y sigue.
    """
    r = _cli("conectar", FIX, "--alto-riesgo", "si", "--via-anexo", "anexo_iii")
    assert r.returncode == 4
    assert "no se podra" in r.stdout and "acepto-que-no-se-puede-repetir" in r.stdout

    con = _cli("conectar", FIX, "--alto-riesgo", "si", "--via-anexo", "anexo_iii",
               "--fecha", "2027-12-15", "--acepto-que-no-se-puede-repetir")
    assert con.returncode in (0, 1, 3), con.stderr


def test_el_plan_que_sale_de_un_conector_lleva_su_fuente_y_sus_limites():
    """Sin eso, el expediente afirma sobre un arbol y no dice cual ni que se
    quedo fuera al traerlo."""
    r = _cli("conectar", FIX, "--alto-riesgo", "si", "--via-anexo", "anexo_iii",
             "--fecha", "2027-12-15", "--acepto-que-no-se-puede-repetir", "--json")
    plan = _json.loads(r.stdout)
    assert plan["fuente"]["conector"] == "local"
    assert plan["fuente"]["reproducible"] is False
    assert plan["limites_del_conector"], "un conector siempre trae menos de lo que hay"
    assert all(l["que"]["es"] and l["que"]["en"] for l in plan["limites_del_conector"])


def test_y_ese_plan_no_lleva_ni_un_secreto_dentro():
    r = _cli("conectar", FIX, "--alto-riesgo", "si", "--via-anexo", "anexo_iii",
             "--fecha", "2027-12-15", "--acepto-que-no-se-puede-repetir", "--json")
    assert sin_secretos(r.stdout) == []


def test_una_ubicacion_que_nadie_trae_sale_con_error_y_lo_dice():
    r = _cli("conectar", "ftp://nadie/trae/esto")
    assert r.returncode == 4
    assert "ningun conector" in r.stderr


# --- el empujon como disparador -------------------------------------------

def _gh(sha="b" * 40, antes="a" * 40, modificados=("docs/logo.png",),
        anadidos=(), eliminados=(), commits=None, **extra):
    cuerpo = {"ref": "refs/heads/main", "after": sha, "before": antes,
              "repository": {"clone_url": "https://github.com/x/y.git", "full_name": "x/y"},
              "commits": commits if commits is not None else [
                  {"added": list(anadidos), "modified": list(modificados),
                   "removed": list(eliminados)}]}
    cuerpo.update(extra)
    return cuerpo


def test_los_cuatro_proveedores_se_traducen_a_lo_mismo():
    """Lo unico que cambia entre proveedores son los nombres de los campos.

    Escribir la logica cuatro veces habria dado cuatro sitios donde arreglar
    un fallo, asi que es una tabla y no un `if` encadenado.
    """
    from actaira_motor.conectores.eventos import traducir

    casos = {
        "github": _gh(),
        "gitlab": {"object_kind": "push", "ref": "refs/heads/main",
                   "checkout_sha": "b" * 40, "before": "a" * 40,
                   "project": {"git_http_url": "https://gl/x.git"}},
        "bitbucket": {"repository": {"links": {"html": {"href": "https://bb/x"}}},
                      "push": {"changes": [{"new": {"name": "main",
                                                    "target": {"hash": "c" * 40}},
                                            "old": {"target": {"hash": "a" * 40}}}]}},
        "azure": {"eventType": "git.push",
                  "resource": {"repository": {"remoteUrl": "https://az/x"},
                               "refUpdates": [{"name": "refs/heads/main",
                                               "oldObjectId": "a" * 40,
                                               "newObjectId": "d" * 40}]}},
    }
    for esperado, payload in casos.items():
        e = traducir(payload)
        assert e.proveedor == esperado
        assert e.referencia == "main"
        assert len(e.referencia_inmutable) == 40
        assert e.ubicacion
        assert e.antes == "a" * 40, f"{esperado}: sin la base, la lista de ficheros no sirve"


def test_una_rama_recien_creada_no_sale_de_ningun_commit():
    """Cuarenta ceros es «esta rama no existia», y tratarlo como un commit
    habria hecho comparar contra la nada."""
    from actaira_motor.conectores.eventos import traducir

    assert traducir(_gh(antes="0" * 40)).antes is None


def test_un_payload_que_no_se_entiende_NO_se_ignora():
    """Un proveedor cambia su formato, los eventos dejan de traducirse y la
    vigilancia se para sin que nadie se entere. El cliente sigue creyendo que
    la tiene, que es peor que no tenerla."""
    from actaira_motor.conectores.eventos import NoSeEntiende, traducir

    with pytest.raises(NoSeEntiende, match="NO se ignora"):
        traducir({"algo": "que no es un empujon"})


def test_ni_uno_con_un_sha_que_no_es_un_sha():
    """El gemelo del anterior: entender a medias es peor que no entender."""
    from actaira_motor.conectores.eventos import NoSeEntiende, traducir

    with pytest.raises(NoSeEntiende):
        traducir(_gh(sha="no-soy-un-commit"))


def test_el_mismo_empujon_entregado_tres_veces_decide_lo_mismo():
    """Los proveedores reentregan. La idempotencia NO se resuelve con una tabla
    de eventos vistos -que habria sido otro estado que mantener- sino porque la
    decision depende del SUJETO, y el mismo commit da el mismo sujeto."""
    from actaira_motor.conectores.eventos import Decision, decidir, traducir

    e = traducir(_gh(), "evt-1")
    decisiones = {decidir(e, "b" * 40, "b" * 40)[0] for _ in range(3)}
    assert decisiones == {Decision.REVALIDAR}


# --- el filtro barato, que es el argumento de coste entero ----------------

def test_un_empujon_que_solo_toca_lo_que_el_motor_no_abre_se_ignora():
    """Y esta vez se comprueba DE VERDAD, que la version anterior no lo hacia.

    La primera version de este test pasaba el mismo digest por los dos lados y
    ponia `LEEME.md` en la lista de ficheros, que la funcion no miraba: salia
    REVALIDAR por la igualdad de digests y el nombre del test atribuia ese
    verde al filtro de ficheros, que no existia. Es el modo de fallo de la
    regla 12 -- una comprobacion que mira de lado -- y ademas el mas caro,
    porque su verde certificaba una funcion que no estaba escrita.
    """
    from actaira_motor.conectores.eventos import (Decision, decidir,
                                                  lector_del_motor, traducir)

    e = traducir(_gh(modificados=("docs/captura.png",)))
    decision, motivo = decidir(e, "a" * 40, "b" * 40, lee_contenido=lector_del_motor())
    assert decision is Decision.IGNORAR, motivo["es"]
    assert not decision.cuesta_computo
    assert "docs/captura.png" in motivo["es"] and motivo["en"]


def test_y_el_gemelo_si_toca_un_fichero_que_el_motor_abre_si_cuesta():
    """Si no, «no cuesta computo» se cumpliria no observando nunca."""
    from actaira_motor.conectores.eventos import (Decision, decidir,
                                                  lector_del_motor, traducir)

    e = traducir(_gh(modificados=("app/modelo.py",)))
    decision, motivo = decidir(e, "a" * 40, "b" * 40, lee_contenido=lector_del_motor())
    assert decision is Decision.REOBSERVAR and decision.cuesta_computo
    assert "app/modelo.py" in motivo["es"]


def test_un_fichero_nuevo_cuesta_una_observacion_aunque_nadie_lo_abra():
    """El digest del arbol resume tambien los NOMBRES de los que no abre.

    Sin esta rama, anadir un .png no habria cambiado nada segun el filtro y si
    habria cambiado el digest: la evidencia siguiente se habria tomado por
    valida sobre un sujeto que ya no era el mismo.
    """
    from actaira_motor.conectores.eventos import (Decision, decidir,
                                                  lector_del_motor, traducir)

    for caso in ({"anadidos": ("docs/nuevo.png",)}, {"eliminados": ("docs/viejo.png",)}):
        e = traducir(_gh(modificados=(), **caso))
        d, motivo = decidir(e, "a" * 40, "b" * 40, lee_contenido=lector_del_motor())
        assert d is Decision.REOBSERVAR, (caso, motivo["es"])
        assert "añadieron o se borraron" in motivo["es"]


def test_y_esa_afirmacion_sobre_el_digest_es_cierta(tmp_path):
    """El gemelo del anterior, contra el motor de verdad y no contra su fama.

    Que el digest del arbol cubra los nombres de los ficheros que no lee es el
    hecho del que depende la rama de arriba. Si algun dia deja de ser cierto,
    la rama sobra; si deja de ser cierto y nadie lo nota, el filtro empieza a
    ignorar empujones que si cambian el sujeto.
    """
    from actaira_motor.controles.motor import Arbol

    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    antes = Arbol.leer(tmp_path).digest()
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n")
    assert Arbol.leer(tmp_path).digest() != antes, "un fichero que no se lee tambien cuenta"


def test_la_definicion_de_lo_que_el_motor_abre_es_UNA(tmp_path):
    """Regla 10: dos definiciones de la misma propiedad se anulan.

    El filtro pregunta por NOMBRES, sin disco, porque el codigo no esta -- ese
    es el ahorro entero. Si esa pregunta la contestara una lista propia, el dia
    que alguien anadiera `.tf` al motor y no a la lista, un cambio en un
    fichero de Terraform se ignoraria en silencio. Aqui se comprueba contra el
    arbol de verdad y no contra la lista.
    """
    from actaira_motor.conectores.eventos import lector_del_motor
    from actaira_motor.controles.motor import Arbol

    for nombre in ("a.py", "b.yml", "c.toml", "d.md", "e.txt", "f.json", "g.ini",
                   "h.cfg", "Dockerfile", "i.png", "j.bin", "k.tf", "l.ipynb"):
        (tmp_path / nombre).write_text("x = 1\n", encoding="utf-8")
    a = Arbol.leer(tmp_path)
    lee = lector_del_motor()
    assert {f for f in a.todos if lee(f)} == set(a.texto), \
        "el filtro y el arbol no coinciden en que ficheros se abren"


def test_sin_saber_que_abre_el_motor_no_se_ignora_nada():
    """Se pierde una optimizacion, que es el lado por el que hay que fallar."""
    from actaira_motor.conectores.eventos import Decision, decidir, traducir

    e = traducir(_gh(modificados=("docs/captura.png",)))
    d, motivo = decidir(e, "a" * 40, "b" * 40)
    assert d is Decision.REOBSERVAR
    assert "no se sabe qué ficheros abre el motor" in motivo["es"]


def test_un_empujon_que_sale_de_otro_commit_no_se_ignora():
    """Su lista de ficheros describe otro tramo, no el que va de lo observado
    a lo de ahora. Creersela seria saltarse todo lo que paso en medio."""
    from actaira_motor.conectores.eventos import (Decision, decidir,
                                                  lector_del_motor, traducir)

    e = traducir(_gh(antes="9" * 40, modificados=("docs/captura.png",)))
    d, motivo = decidir(e, "a" * 40, "b" * 40, lee_contenido=lector_del_motor())
    assert d is Decision.REOBSERVAR
    assert "otro tramo" in motivo["es"]


def test_una_lista_recortada_no_se_cree_nunca():
    """Los cuatro proveedores recortan y ninguno avisa igual. Creerse una lista
    recortada es exactamente no observar un cambio que si ocurrio."""
    from actaira_motor.conectores.eventos import (Decision, TOPE_DE_COMMITS, decidir,
                                                  lector_del_motor, traducir)

    uno = {"added": [], "modified": ["docs/captura.png"], "removed": []}
    casos = {
        "forzado": _gh(forced=True),
        "rama nueva": _gh(created=True),
        "veinte commits": _gh(commits=[uno] * TOPE_DE_COMMITS),
        "sin commits": _gh(commits=[]),
        "gitlab recortado": {"object_kind": "push", "ref": "refs/heads/main",
                             "checkout_sha": "b" * 40, "before": "a" * 40,
                             "total_commits_count": 40, "commits": [uno],
                             "project": {"git_http_url": "https://gl/x.git"}},
    }
    for nombre, payload in casos.items():
        e = traducir(payload)
        assert not e.lista_completa, nombre
        assert e.por_que_no_completa, f"{nombre}: y se dice por que"
        d, _ = decidir(e, "a" * 40, e.referencia_inmutable, lee_contenido=lector_del_motor())
        assert d is Decision.REOBSERVAR, nombre


def test_pero_una_lista_normal_si_se_cree():
    """El gemelo: un guardia que no deja pasar nada se quita en una semana."""
    from actaira_motor.conectores.eventos import traducir

    e = traducir(_gh())
    assert e.lista_completa and e.por_que_no_completa == ""


def test_bitbucket_y_azure_lo_dicen_en_vez_de_disimularlo():
    """No mandan que ficheros toco cada commit. Con ellos el filtro barato no
    se puede aplicar, y eso se publica en vez de fingir una lista vacia."""
    from actaira_motor.conectores.eventos import traducir

    bb = traducir({"repository": {"links": {"html": {"href": "https://bb/x"}}},
                   "push": {"changes": [{"new": {"name": "main",
                                                 "target": {"hash": "c" * 40}},
                                         "old": {"target": {"hash": "a" * 40}}}]}})
    assert bb.ficheros_tocados == () and not bb.lista_completa
    assert "no manda que ficheros" in bb.por_que_no_completa


# --- la cadena de empujones inertes ---------------------------------------

def test_sin_cadena_el_filtro_barato_solo_serviria_una_vez():
    """El segundo empujon sale del primero, que ya no es lo ultimo observado.

    Ese es el motivo de que la cadena exista, y se comprueba enfrentando los
    dos casos: sin cadena cuesta un clon, con cadena no.
    """
    from actaira_motor.conectores.eventos import (Decision, decidir,
                                                  lector_del_motor, traducir)

    segundo = traducir(_gh(antes="b" * 40, sha="c" * 40, modificados=("docs/otra.png",)))
    lee = lector_del_motor()
    assert decidir(segundo, "a" * 40, "c" * 40, lee_contenido=lee)[0] is Decision.REOBSERVAR
    assert decidir(segundo, "a" * 40, "c" * 40, lee_contenido=lee,
                   inerte=("b" * 40,))[0] is Decision.IGNORAR


def test_la_cadena_encadena_de_verdad_y_no_por_pertenencia():
    """Dos anotaciones que salen del MISMO commit son una bifurcacion, y una
    bifurcacion no es una cadena: el arbol de una rama no dice nada de la otra."""
    from actaira_motor.conectores.eventos import (Decision, decidir,
                                                  lector_del_motor, traducir)

    # sale de "b", pero la cabeza ya es "c": no encadena
    e = traducir(_gh(antes="b" * 40, sha="d" * 40, modificados=("docs/otra.png",)))
    d, motivo = decidir(e, "a" * 40, "d" * 40, lee_contenido=lector_del_motor(),
                        inerte=("b" * 40, "c" * 40))
    assert d is Decision.REOBSERVAR and "otro tramo" in motivo["es"]


def test_la_cadena_tiene_tope_y_llegar_al_tope_CUESTA():
    """Cien eslabones son una afirmacion sobre un arbol que nadie ha visto
    desde hace cien empujones. El tope no ahorra computo: lo gasta."""
    from actaira_motor.conectores.eventos import (Decision, TOPE_DE_CADENA_INERTE,
                                                  decidir, lector_del_motor, traducir)

    cadena = tuple(f"{i:040x}" for i in range(TOPE_DE_CADENA_INERTE))
    e = traducir(_gh(antes=cadena[-1], sha="e" * 40, modificados=("docs/otra.png",)))
    d, motivo = decidir(e, "a" * 40, "e" * 40, lee_contenido=lector_del_motor(),
                        inerte=cadena)
    assert d is Decision.REOBSERVAR and d.cuesta_computo
    assert "tope" in motivo["es"] and motivo["en"]


def test_una_reentrega_de_un_empujon_ya_ignorado_no_cuesta_un_clon():
    """La idempotencia tiene que valer para los DOS caminos.

    Sin esta rama, reentregar un empujon ignorado caia en REOBSERVAR -- su
    `antes` ya no es la cabeza -- y la propiedad se habria sostenido para el
    camino de REVALIDAR y no para el otro.
    """
    from actaira_motor.conectores.eventos import (Decision, decidir,
                                                  lector_del_motor, traducir)

    e = traducir(_gh(antes="a" * 40, sha="b" * 40, modificados=("docs/otra.png",)))
    d, motivo = decidir(e, "a" * 40, "b" * 40, lee_contenido=lector_del_motor(),
                        inerte=("b" * 40, "c" * 40))
    assert d is Decision.REVALIDAR and not d.cuesta_computo
    assert "reentrega" in motivo["es"]


def test_un_sujeto_que_nunca_se_observo_no_se_revalida():
    """Revalidar es «volvi a ver lo mismo», y no se puede volver a ver algo que
    no se vio nunca. Fundirlos haria que un sujeto nuevo entrara al expediente
    como si llevara ahi desde siempre."""
    from actaira_motor.conectores.eventos import Decision, decidir, traducir

    e = traducir(_gh())
    assert decidir(e, None, "sha256:algo")[0] is Decision.REOBSERVAR
    assert decidir(e, "sha256:algo", None)[0] is Decision.REOBSERVAR


def test_los_cuatro_valores_de_la_decision_son_alcanzables():
    """Un enumerado con valores que nadie devuelve promete cuatro salidas y da
    dos. `NO_TRADUCIBLE` sale por el verbo, que es donde hay que emitirlo."""
    from actaira_motor.conectores.eventos import (Decision, decidir,
                                                  lector_del_motor, traducir)

    lee = lector_del_motor()
    vistas = {
        decidir(traducir(_gh()), None, "b" * 40)[0],
        decidir(traducir(_gh()), "b" * 40, "b" * 40)[0],
        decidir(traducir(_gh()), "a" * 40, "b" * 40, lee_contenido=lee)[0],
    }
    salida = _json.loads(_sp.run(
        [_sys.executable, "-m", "actaira_motor.cli", "empujon", "-", "--json"],
        cwd=RAIZ, env=ENT, input='{"no":"soy un empujon"}', capture_output=True,
        text=True, encoding="utf-8", errors="replace").stdout)
    vistas.add(Decision(salida["decision"]))
    assert vistas == set(Decision), sorted(d.value for d in set(Decision) - vistas)


# --- el verbo del empujon, de punta a punta -------------------------------

def _repo_de_verdad(tmp_path: Path) -> tuple[str, str]:
    """Un repositorio git local: el conector lo trae sin tocar la red."""
    origen = tmp_path / "origen.git"
    origen.mkdir()
    (origen / "app.py").write_text("import mlflow\n", encoding="utf-8")
    (origen / "LEEME.md").write_text("# x\n", encoding="utf-8")
    for orden in (["init", "-q", "-b", "main", "."], ["add", "-A"],
                  ["-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "uno"]):
        _sp.run(["git", *orden], cwd=origen, check=True, capture_output=True)
    sha = _sp.run(["git", "rev-parse", "HEAD"], cwd=origen, check=True,
                  capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    return str(origen), sha


def _empuja(tmp_path: Path, nombre: str, antes: str, sha: str, **kw) -> str:
    ruta = tmp_path / nombre
    ruta.write_text(_json.dumps(_gh(sha=sha, antes=antes, **kw)), encoding="utf-8")
    return str(ruta)


@pytest.mark.skipif(not HAY_GIT, reason="git no esta instalado")
def test_el_camino_barato_entero_por_la_linea_de_ordenes(tmp_path):
    """Registrar la fuente y que el empujon siguiente NO cueste un clon.

    Es el argumento de coste medido donde el cliente lo va a medir: dos verbos
    y un codigo de salida, sin tocar la red y sin traer el codigo dos veces.
    """
    origen, sha = _repo_de_verdad(tmp_path)
    alm = str(tmp_path / "ev.jsonl")
    con = _cli("conectar", origen, "--referencia", "main", "--alto-riesgo", "si",
               "--via-anexo", "anexo_iii", "--fecha", "2027-12-15",
               "--almacen", alm, "--registrar")
    assert con.returncode in (0, 1, 3), con.stderr
    assert "fuente registrada" in con.stdout

    # mismo commit: revalidar, y codigo 0 porque no hay trabajo que hacer
    p = tmp_path / "igual.json"
    p.write_text(_json.dumps(_gh(sha=sha, antes="0" * 40,
                                 **{"repository": {"clone_url": origen,
                                                   "full_name": "x/y"}})),
                 encoding="utf-8")
    r = _cli("empujon", str(p), "--almacen", alm)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "revalidar" in r.stdout


@pytest.mark.skipif(not HAY_GIT, reason="git no esta instalado")
def test_y_la_cadena_de_inertes_se_encadena_por_la_linea_de_ordenes(tmp_path):
    """Dos empujones seguidos que no tocan nada legible, y ninguno cuesta.

    Sin `--registrar` el primero no deja rastro y el segundo vuelve a costar:
    se comprueban los dos lados, porque el que importa es el segundo.
    """
    origen, sha = _repo_de_verdad(tmp_path)
    alm = str(tmp_path / "ev.jsonl")
    repo = {"repository": {"clone_url": origen, "full_name": "x/y"}}
    assert _cli("conectar", origen, "--referencia", "main", "--alto-riesgo", "si",
                "--via-anexo", "anexo_iii", "--fecha", "2027-12-15",
                "--almacen", alm, "--registrar").returncode in (0, 1, 3)

    uno = tmp_path / "1.json"
    uno.write_text(_json.dumps(_gh(sha="1" * 40, antes=sha,
                                   modificados=("docs/a.png",), **repo)), encoding="utf-8")
    dos = tmp_path / "2.json"
    dos.write_text(_json.dumps(_gh(sha="2" * 40, antes="1" * 40,
                                   modificados=("docs/b.png",), **repo)), encoding="utf-8")

    # sin registrar: el primero se ignora, y el segundo vuelve a costar
    assert _cli("empujon", str(uno), "--almacen", alm).returncode == 0
    caro = _cli("empujon", str(dos), "--almacen", alm)
    assert caro.returncode == 3 and "reobservar" in caro.stdout

    # registrando: el segundo tampoco cuesta
    r1 = _cli("empujon", str(uno), "--almacen", alm, "--registrar",
              "--ahora", "2026-09-20T10:00:00+00:00")
    assert r1.returncode == 0 and "ignorar" in r1.stdout
    r2 = _cli("empujon", str(dos), "--almacen", alm, "--registrar",
              "--ahora", "2026-09-20T10:01:00+00:00")
    assert r2.returncode == 0 and "ignorar" in r2.stdout, r2.stdout
    assert "cadena sin observar: 1" in r2.stdout


@pytest.mark.skipif(not HAY_GIT, reason="git no esta instalado")
def test_lo_que_se_anota_al_ignorar_dice_que_NO_es_una_observacion(tmp_path):
    """Un registro que dice «el arbol estaba asi» sin que nadie lo haya mirado
    seria la tercera negativa rota: inferir lo no observado."""
    origen, sha = _repo_de_verdad(tmp_path)
    alm = str(tmp_path / "ev.jsonl")
    repo = {"repository": {"clone_url": origen, "full_name": "x/y"}}
    _cli("conectar", origen, "--referencia", "main", "--alto-riesgo", "si",
         "--via-anexo", "anexo_iii", "--fecha", "2027-12-15", "--almacen", alm, "--registrar")
    uno = tmp_path / "1.json"
    uno.write_text(_json.dumps(_gh(sha="1" * 40, antes=sha,
                                   modificados=("docs/a.png",), **repo)), encoding="utf-8")
    _cli("empujon", str(uno), "--almacen", alm, "--registrar",
         "--ahora", "2026-09-20T10:00:00+00:00")

    lineas = [_json.loads(l)["registro"]
              for l in Path(alm).read_text(encoding="utf-8").splitlines()]
    inertes = [l for l in lineas if l.get("control_id") == "ACT-C-INERTE"]
    assert len(inertes) == 1, [l.get("control_id") for l in lineas]
    c = inertes[0]["contenido"]
    assert c["no_es_una_observacion"]["es"] and c["no_es_una_observacion"]["en"]
    assert c["desde"] == sha and c["hasta"] == "1" * 40
    assert inertes[0]["sujeto_digest"], "el sujeto es la ubicacion y la rama, no un arbol"
    assert c["modificados"] == ["docs/a.png"]
    # Y lo que NO lleva: ni un digest de arbol, ni un resultado, ni nada que
    # se pueda leer como «se miro y estaba bien».
    plano = _json.dumps(inertes[0], ensure_ascii=False).lower()
    for prohibida in ("cumple", "sin_hallazgos", "resultado", "conforme"):
        assert prohibida not in plano, prohibida


@pytest.mark.skipif(not HAY_GIT, reason="git no esta instalado")
def test_un_empujon_a_otra_rama_no_dice_que_nunca_se_observo(tmp_path):
    """Se observo la ubicacion; lo que no se observo es ESA rama. Decir «nunca
    se observo este sujeto» habria sido comodo y habria sido falso."""
    origen, sha = _repo_de_verdad(tmp_path)
    alm = str(tmp_path / "ev.jsonl")
    _cli("conectar", origen, "--referencia", "main", "--alto-riesgo", "si",
         "--via-anexo", "anexo_iii", "--fecha", "2027-12-15", "--almacen", alm, "--registrar")
    otra = tmp_path / "otra.json"
    payload = _gh(sha="1" * 40, antes=sha,
                  **{"repository": {"clone_url": origen, "full_name": "x/y"}})
    payload["ref"] = "refs/heads/desarrollo"
    otra.write_text(_json.dumps(payload), encoding="utf-8")
    r = _cli("empujon", str(otra), "--almacen", alm)
    assert r.returncode == 3
    assert "desarrollo" in r.stdout and "nunca se observó este sujeto" not in r.stdout


def test_un_cuerpo_que_no_se_entiende_sale_con_la_misma_forma_que_los_demas():
    """Quien recibe webhooks quiere UNA forma de respuesta, no dos."""
    r = _sp.run([_sys.executable, "-m", "actaira_motor.cli", "empujon", "-", "--json"],
                cwd=RAIZ, env=ENT, input='{"no":"soy un empujon"}',
                capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 4
    salida = _json.loads(r.stdout)
    assert salida["decision"] == "no_traducible"
    assert salida["cuesta_computo"] is False
    assert salida["motivo"]["es"] and salida["motivo"]["en"]
