r"""Los escapes que una auditoria externa marco como bloqueantes de produccion.

Cada prueba de aqui se escribio REPRODUCIENDO primero el escape contra el codigo
de entonces y comprobando que se ponia roja. Una prueba de seguridad que nunca
se vio fallar no demuestra que algo este cerrado: demuestra que esta escrita.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "motor" / "src"))

from actaira_motor.remediacion.contrato import Encargo          # noqa: E402
from actaira_motor.remediacion.fichero import RemediadorFichero  # noqa: E402
from actaira_motor.remediacion.red import (                      # noqa: E402
    VARIABLE_HTTP, VARIABLE_INTERNOS, DestinoNoPermitido, comprobar)


def _encargo(identificador: str) -> Encargo:
    return Encargo(
        no_conformidad_id=identificador,
        titulo={"es": "t", "en": "t"}, cuerpo={"es": "c", "en": "c"},
        obligacion_id="AIA-072", control_id="ACT-72-DRIFT", severidad="alta",
        responsable="datos", compromiso="2027-10-15")


# --- escritura de ficheros -------------------------------------------------

@pytest.mark.parametrize("malo", [
    "../escape",                  # el que reporto la auditoria
    "../../../escape",
    "x/../../fuera",
    "..",
    ".",
    "/etc/cron.d/actaira",        # ABSOLUTO: peor que el anterior
    "C:/Windows/Temp/actaira",
    ".oculto",
    "con espacio",
    "a" * 65,
])
def test_un_identificador_que_no_sirve_como_nombre_de_fichero_se_rechaza(malo):
    """El escape, y tres casos mas que la auditoria no llego a probar.

    `RemediadorFichero` hacia `carpeta / f"{id}.md"`. Con `../escape` el encargo
    salia del directorio de tickets, que es lo que se reporto. Con una ruta
    ABSOLUTA es peor: el operador `/` de `pathlib` descarta el lado izquierdo
    entero, asi que `/etc/cron.d/actaira` no escribe un directorio mas arriba,
    escribe exactamente donde diga el identificador. Escritura de ficheros en
    cualquier sitio donde alcance el proceso, desde un campo que rellena quien
    abre la no conformidad.

    Se rechaza en `Encargo` y no en el remediador porque el mismo identificador
    viaja a los remediadores de red, donde una barra tambien cambia a que
    recurso se llama.
    """
    with pytest.raises(ValueError) as e:
        _encargo(malo)
    assert "identificador" in str(e.value)


@pytest.mark.parametrize("bueno", ["NC-9", "nc_1.2", "A", "NC-2027-001"])
def test_un_identificador_normal_sigue_pasando(bueno):
    """Cerrarlo rechazandolo todo seria igual de inutil, y mas facil de no notar."""
    assert _encargo(bueno).no_conformidad_id == bueno


def test_el_remediador_comprueba_ADEMAS_donde_acaba_escribiendo():
    """La segunda barrera, que mira la ruta resuelta y no el texto.

    Las dos fallan por motivos distintos: `Encargo` mira el identificador, y
    esto mira donde cae el fichero de verdad. Lo que esta barrera NO hace --
    comprobar que la carpeta de destino sea legitima -- esta escrito en su
    docstring, porque aqui no se sabe donde empieza el espacio de un cliente.
    """
    from actaira_motor.remediacion.fichero import _exigir_dentro

    with tempfile.TemporaryDirectory() as tmp:
        carpeta = Path(tmp) / "tickets"
        carpeta.mkdir()
        _exigir_dentro(carpeta, "NC-9.md")                 # no lanza
        with pytest.raises(ValueError):
            _exigir_dentro(carpeta, "../fuera.md")


def test_el_encargo_normal_se_escribe_donde_toca():
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / "clientes" / "acme" / "tickets"
        d = RemediadorFichero(str(destino)).abrir(_encargo("NC-9"))
        escrito = Path(d.url).resolve()
        assert escrito.parent == destino.resolve()
        assert escrito.name == "NC-9.md"


# --- a donde se le permite hablar al remediador de red ---------------------

@pytest.mark.parametrize("destino", [
    "https://169.254.169.254/latest/meta-data/",   # metadatos en la nube
    "https://[::ffff:169.254.169.254]/x",          # la misma, mapeada a IPv6
    "https://127.0.0.1:8080/x",
    "https://localhost/x",
    "https://10.0.0.5/jira",
    "https://192.168.1.10/jira",
    "https://0.0.0.0/x",
    "file:///etc/passwd",
    "gopher://x/y",
])
def test_no_se_manda_la_credencial_del_cliente_a_un_destino_interno(destino):
    """SSRF, y aqui con la peticion ya firmada.

    `RemediadorHttp` adjunta la credencial del cliente a la peticion y la manda
    a donde diga `--destino`. Un destino interno llega al servicio de metadatos
    de la nube o a un servicio de la red privada, autenticado. Se prueba tambien
    la direccion de metadatos MAPEADA a IPv6, que es la que se cuela por debajo
    de una lista de rangos escrita a mano.
    """
    with pytest.raises(DestinoNoPermitido):
        comprobar(destino)


def test_un_destino_sin_cifrar_no_pasa_porque_la_peticion_lleva_el_token():
    with pytest.raises(DestinoNoPermitido) as e:
        comprobar("http://api.github.com/repos/x/y/issues")
    assert "credencial" in str(e.value)


def test_el_permiso_de_http_es_explicito_y_solo_afecta_al_cifrado(monkeypatch):
    """La via de escape para un servidor de pruebas, y su limite.

    Permitir texto plano NO permite ademas un destino interno: son dos
    comprobaciones distintas y hay que afirmar las dos por separado. Una via de
    escape que ademas apaga la de al lado es un interruptor general disfrazado.
    """
    monkeypatch.setenv(VARIABLE_HTTP, "1")
    comprobar("http://api.github.com/x")                   # cifrado: permitido
    with pytest.raises(DestinoNoPermitido):
        comprobar("http://127.0.0.1:8080/x")               # interno: sigue sin pasar


def test_un_host_interno_afirmado_por_el_operador_si_pasa(monkeypatch):
    """Un Jira en la intranet es un caso legitimo y tiene que poder decirse.

    Se afirma nombrandolo entero. No se admite comodin: un comodin convierte la
    afirmacion en un permiso general, y lo que queda no es una excepcion sino la
    ausencia de la regla.
    """
    monkeypatch.setenv(VARIABLE_INTERNOS, "jira.interno.acme")
    comprobar("https://jira.interno.acme/rest/api/3/issue")
    with pytest.raises(DestinoNoPermitido):
        comprobar("https://otro.interno.acme/x")


def test_una_redireccion_no_se_sigue_con_la_credencial_puesta():
    """Un 302 a una direccion interna consigue lo mismo que escribirla.

    Y sin que aparezca en ninguna configuracion que alguien pueda revisar, que
    es lo que lo hace peor que el caso directo.
    """
    import urllib.request

    from actaira_motor.remediacion.red import _SinRedirecciones

    manejador = _SinRedirecciones()
    peticion = urllib.request.Request("https://api.linear.app/graphql")
    with pytest.raises(DestinoNoPermitido) as e:
        manejador.redirect_request(peticion, None, 302, "Found", {},
                                   "https://169.254.169.254/latest/meta-data/")
    assert "credencial" in str(e.value)


# --- aislamiento entre clientes en el lado Go ------------------------------

def test_el_lado_go_resuelve_enlaces_antes_de_decidir_si_algo_esta_dentro():
    """El escape de aislamiento vive en Go y su prueba tambien; aqui se corre.

    Se deja constancia en la suite de Python porque es la que corre todo el
    mundo, y porque un escape de aislamiento entre clientes no puede depender de
    que quien audita tenga `go` instalado -- que es justo lo que le paso a la
    auditoria externa, que no pudo validar el lado Go en absoluto.
    """
    import shutil

    if not shutil.which("go"):
        pytest.skip("`go` no esta instalado: este escape queda SIN COMPROBAR aqui")
    r = subprocess.run(["go", "test", "./motor/", "-run", "Enlace|Hermano|Salida", "-count=1"],
                       cwd=RAIZ / "plataforma", capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr


def test_el_arbol_no_lee_un_enlace_que_sale_de_la_raiz():
    """La guarda del lado Python, y el limite que tiene.

    `Arbol._dentro` resuelve cada fichero y exige que caiga bajo la raiz, asi
    que un enlace DENTRO del arbol no se lee y se anota como ilegible. Lo que no
    puede ver es que la RAIZ MISMA sea el enlace: ahi resolverla lleva al
    destino y todo lo de debajo esta, efectivamente, dentro. Esa mitad la cierra
    `rutaSegura` en el lado Go, que es quien sabe donde empieza cada cliente.
    """
    from actaira_motor.controles.motor import Arbol

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        fuera = base / "otro"
        fuera.mkdir()
        (fuera / "confidencial.py").write_text("SECRETO = 1\n", encoding="utf-8")
        repo = base / "repo"
        repo.mkdir()
        (repo / "propio.py").write_text("x = 1\n", encoding="utf-8")
        try:
            os.symlink(fuera, repo / "atajo", target_is_directory=True)
        except OSError:
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(repo / "atajo"), str(fuera)],
                               capture_output=True)
            if r.returncode != 0:
                pytest.skip("este sistema no deja crear enlaces")

        a = Arbol.leer(repo)
        assert "propio.py" in a.todos
        assert not any("confidencial" in n for n in a.todos), (
            "leyo un fichero de fuera de la raiz a traves de un enlace")


# --- lo que no se pudo leer, en todos los caminos -------------------------

def test_el_lector_de_agentes_anota_lo_que_no_pudo_leer():
    """Tres `continue` callados, y el peor sitio posible para tenerlos.

    El arsenal de un agente se mide por lo que se encuentra, asi que «no
    encontre ninguna herramienta porque no pude leer el fichero donde estan» se
    parece muchisimo a «no hay herramientas». La primera es un limite y la
    segunda una conclusion.

    Es el mismo fallo que el plan tenia al descartar sus `ilegibles`, asomando
    por la otra ventana: lo encontro una barrida adversarial buscando `except`
    que se tragan y siguen, y no una prueba que alguien hubiera escrito.
    """
    from actaira_motor.agentes.lectura import leer as leer_agentes

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        (repo / "bien.py").write_text("import x\n", encoding="utf-8")
        # Un fichero que no es UTF-8: el caso que caia en el `continue`.
        (repo / "roto.py").write_bytes(b"\xff\xfe# esto no es utf-8\n")

        a = leer_agentes(repo)
        nombres = [n for n, _ in a.ilegibles]
        assert "roto.py" in nombres, (
            f"un fichero ilegible se descarto en silencio: {a.ilegibles}")
        assert all(motivo for _, motivo in a.ilegibles), "sin motivo no sirve de nada"


def test_lo_que_no_se_pudo_leer_SALE_en_el_control_de_agentes():
    """Anotarlo dentro y no publicarlo seria arreglarlo solo para el codigo.

    El dato tiene que llegar al documento que lee un auditor, o el arreglo no
    cambia nada de lo que se ve.
    """
    from actaira_motor.controles.agentes import correr

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        (repo / "mcp.json").write_text(
            '{"mcpServers": {"x": {"command": "y"}}}', encoding="utf-8")
        (repo / "roto.py").write_bytes(b"\xff\xfe# no es utf-8\n")

        res = correr(repo, RAIZ / "catalogo" / "reglas" / "agentes.json")
        textos = " ".join(l.que["es"] for l in res.observacion.limites)
        assert "no se pudieron leer" in textos, (
            f"el control no publica lo que no pudo leer: {textos[:300]}")
        assert "roto.py" in textos


def test_un_paquete_de_reglas_ROTO_revienta_en_vez_de_saltarse():
    """De ahi sale el TEXTO que se le manda a una persona en un ticket.

    Saltarselo no deja el encargo sin ese texto de forma visible: lo deja sin
    la regla, y quien reciba el ticket no sabra que lo que tiene delante no es
    lo que dice el catalogo. Y es un fichero DEL ARBOL: que no cargue es un
    defecto de esta casa, no una condicion del entorno.
    """
    import pytest

    from actaira_motor.remediacion.encargo import _reglas

    with tempfile.TemporaryDirectory() as tmp:
        carpeta = Path(tmp)
        (carpeta / "bueno.json").write_text(
            '{"paquete": "p", "obligacion": "AIA-072", "reglas": '
            '[{"id": "ACT-X", "titulo": {"es": "t", "en": "t"}}]}', encoding="utf-8")
        (carpeta / "roto.json").write_text("{esto no es json", encoding="utf-8")

        with pytest.raises(ValueError) as e:
            _reglas(carpeta)
        assert "roto.json" in str(e.value), "el error no dice cual se rompio"
