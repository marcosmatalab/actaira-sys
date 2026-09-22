r"""La puerta de aceptacion entera, escrita una vez y ejecutable en cualquier sitio.

POR QUE ESTE FICHERO EXISTE, Y QUE ESTABA ROTO
-----------------------------------------------
`make todo` era la puerta de aceptacion del producto: catalogo, consola, panel,
portada, suite, las demostraciones de cada fase, el contrato con el lado Go y la
API. Tenia dos defectos, y el segundo es peor que el primero.

1. No corria fuera de un bash con GNU make. Usaba `python3` -- que no existe en
   Windows -- rutas bajo `/tmp`, `rm -rf`, `sleep`, `curl`, `mktemp` y sustitucion
   de procesos. Un criterio de aceptacion que solo se puede comprobar en una de
   las maquinas donde corre el producto no es un criterio: es una costumbre.

2. Y sobre todo: NO PODIA PONERSE ROJO. El propio Makefile documenta, sobre
   tres lineas del objetivo `contrato`, que `| tail` se come el codigo de salida
   y que por eso un test de Go en rojo no rompia `make todo`. La correccion se
   aplico a esas tres lineas y no al resto: `fase2` acaba en `|| true`, y
   `fase3` a `fase8` acaban en `; true` o en `| head`. De los trece objetivos
   que `todo` encadenaba, la mayoria no podian fallar por construccion.

   Eso es la version de puerta del fallo que este producto existe para no
   tener: algo que siempre dice que si, y que por decir siempre que si se deja
   de leer. La auditoria externa lo vio por el sintoma -- «make todo termina con
   error» -- pero el sintoma era menos grave que la causa, porque un objetivo
   que falla al menos se nota.

QUE HACE ESTE FICHERO DISTINTO
-------------------------------
Cada fase es una funcion que AFIRMA algo concreto sobre la salida, no un
`echo` seguido de un volcado. Si la afirmacion no se cumple, la fase falla, y
el runner sale con codigo distinto de cero nombrando cual fue. Una fase que
solo imprimiera seria una demostracion, y una demostracion no es una puerta.

Las fases que necesitan algo que puede no estar -- `go`, la rueda instalada, un
puerto libre -- no se saltan en silencio: declaran OMITIDA con el motivo, y el
resumen final distingue las tres cosas que pueden pasar. Saltar sin decirlo es
como se consigue un verde que no cubre lo que parece.

USO
----
    python herramientas/todo.py              todas las fases
    python herramientas/todo.py catalogo api solo esas
    python herramientas/todo.py --listar     los nombres
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MOTOR_SRC = RAIZ / "motor" / "src"
FIXTURE = RAIZ / "motor" / "tests" / "fixtures" / "clasificador-candidatos"
PY = sys.executable
"""El interprete que corre ESTE guion, y no un nombre que buscar en el PATH.

`python3` no existe en Windows, y `python` puede ser otro. Medir el producto
con un interprete distinto del que se esta usando para medirlo es una fuente de
desacuerdos que no aporta nada.
"""


class Omitida(Exception):
    """La fase no se puede correr aqui, y eso NO es un aprobado.

    Se lanza con el motivo, el motivo se imprime y el resumen la cuenta aparte.
    """


@dataclass
class Resultado:
    nombre: str
    estado: str                       # "ok" | "fallo" | "omitida"
    detalle: str = ""
    lineas: list[str] = field(default_factory=list)


def entorno() -> dict[str, str]:
    """El entorno de los subprocesos. UTF-8 explicito, y el motor en el camino.

    Sin `PYTHONIOENCODING` la salida del CLI se codifica con la pagina de
    codigos de la consola de Windows y el castellano con tildes -- que es todo
    el castellano de este producto -- llega roto o revienta.
    """
    e = dict(os.environ)
    e["PYTHONPATH"] = str(MOTOR_SRC) + os.pathsep + e.get("PYTHONPATH", "")
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


# El codigo de salida del CLI es un VEREDICTO, no un fallo. Esta escrito en
# `cli.py` y hay que respetarlo aqui, o esta puerta mide lo que no es:
#
#   0  se miro y no aparecio nada
#   1  aparecio algo
#   3  no se pudo decidir, o falta que alguien conteste
#   4  el analizador se rompio
#   5  el almacen no es el que esta casa escribio
#
# Una herramienta de cumplimiento que encuentra hallazgos ha hecho su trabajo.
# Tratar el 1 como error -- que es lo que hacia la primera version de este
# runner -- pondria la puerta en rojo justo cuando el producto funciona, y la
# salida natural de eso es bajar el liston hasta que no mire nada.
VEREDICTOS = frozenset({0, 1, 3})
ROTURAS = frozenset({4, 5})


def cli(*args: str, veredictos: frozenset[int] | None = None,
        entrada: str | None = None) -> tuple[int, str]:
    """Corre un verbo y devuelve `(codigo, salida)`.

    Revienta solo si el codigo NO esta entre los veredictos esperados: ahi el
    analizador se rompio, o el verbo se invoco mal, y las dos cosas son fallos
    del producto o de esta puerta, no del sujeto que se mide.
    """
    r = subprocess.run([PY, "-m", "actaira_motor.cli", *args], cwd=RAIZ, env=entorno(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       input=entrada)
    esperados = VEREDICTOS if veredictos is None else veredictos
    if r.returncode not in esperados:
        motivo = ("el analizador se rompio" if r.returncode in ROTURAS
                  else "codigo fuera del contrato")
        raise AssertionError(
            f"`actaira {' '.join(args)}` salio {r.returncode} ({motivo}); "
            f"se esperaba uno de {sorted(esperados)}:\n"
            f"{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.returncode, r.stdout


def _afirma(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise AssertionError(mensaje)


# --------------------------------------------------------------------------
# Las fases. Cada una AFIRMA; ninguna se limita a imprimir.
# --------------------------------------------------------------------------

def fase_catalogo(reg: list[str]) -> None:
    sys.path.insert(0, str(MOTOR_SRC))
    from actaira_motor.catalogo.cargador import cargar, controles_declarados

    c = cargar(str(RAIZ / "catalogo"))
    rotos = c.verificar_cruce()
    _afirma(not rotos, f"pares del cruce rotos: {rotos[:5]}")
    malos = c.verificar_formularios(controles_declarados(str(RAIZ / "catalogo" / "reglas")))
    _afirma(not malos, f"formularios rotos: {malos[:5]}")
    huecos = c.huecos_de_cobertura()
    reg.append(f"obligaciones {len(c.obligaciones)} | requisitos {len(c.requisitos)} | "
               f"controles ISO {len(c.controles_iso)} | clausulas {len(c.clausulas)}")
    reg.append(f"preguntas {len(c.preguntas)} | pares {len(c.pares)} | huecos {len(huecos)}")
    _afirma(len(c.obligaciones) > 0 and len(c.requisitos) > 0, "el catalogo carga vacio")


def _reproducible(directorio: str, salida: str, reg: list[str]) -> None:
    import importlib.util

    d = RAIZ / directorio
    spec = importlib.util.spec_from_file_location(f"act_{directorio}", d / "construir.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[f"act_{directorio}"] = m
    spec.loader.exec_module(m)
    a, b = m.construir(), m.construir()
    _afirma(a == b, f"{directorio}: dos construcciones seguidas dan bytes distintos")
    disco = (d / salida).read_text(encoding="utf-8")
    _afirma(a == disco, f"{directorio}/{salida} no coincide con lo que construir.py produce")
    reg.append(f"{directorio}/{salida}: {len(a) // 1024} KB, reproducible")


def fase_consola(reg: list[str]) -> None:
    _reproducible("consola", "consola.html", reg)


def fase_panel(reg: list[str]) -> None:
    _reproducible("panel", "panel.html", reg)
    servido = (RAIZ / "plataforma" / "api" / "panel.html").read_text(encoding="utf-8")
    _afirma(servido == (RAIZ / "panel" / "panel.html").read_text(encoding="utf-8"),
            "el panel que sirve la API no es el que produce panel/construir.py: "
            "corre `make panel`")
    reg.append("el panel servido por la API coincide con el construido")


def fase_portada(reg: list[str]) -> None:
    sys.path.insert(0, str(RAIZ / "sitio"))
    r = subprocess.run([PY, str(RAIZ / "sitio" / "construir.py")], cwd=RAIZ, env=entorno(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    _afirma(r.returncode == 0, f"sitio/construir.py salio {r.returncode}: {r.stderr[-800:]}")
    reg.append((r.stdout.strip().splitlines() or ["portada construida"])[-1])


def fase_suite(reg: list[str]) -> None:
    r = subprocess.run([PY, "-m", "pytest", "motor/tests", "-q"], cwd=RAIZ, env=entorno(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    cola = [x for x in r.stdout.strip().splitlines() if x.strip()][-1:]
    reg.extend(cola)
    _afirma(r.returncode == 0, f"la suite salio {r.returncode}:\n{r.stdout[-3000:]}")


def fase_articulo50(reg: list[str]) -> None:
    """Un repositorio que genera y no aporta artefactos NO puede salir conforme."""
    _, salida = cli("comprobar", str(FIXTURE.parent / "repo-con-generacion"))
    d = json.loads(salida)
    _afirma(d["resultado"] != "CUMPLE",
            f"un repositorio que genera sin aportar artefactos salio {d['resultado']}")
    _afirma(d.get("motivo_indeterminado"), "no dice por que quedo indeterminado")
    reg.append(f"repo-con-generacion: {d['resultado']} (y dice el motivo)")


def fase_sello(reg: list[str]) -> None:
    """Sellar y verificar SIN RED, y ademas que un sello tocado no verifique."""
    sys.path.insert(0, str(MOTOR_SRC))
    from cryptography.hazmat.primitives import serialization as s
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from actaira_motor.evidencia.sello import verificar

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        k = Ed25519PrivateKey.generate()
        (t / "clave.pem").write_bytes(k.private_bytes(
            s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()))
        cli("sellar", str(FIXTURE.parent / "repo-con-generacion"),
            "--clave", str(t / "clave.pem"), "--salida", str(t / "sello.json"),
            "--ahora", "2026-09-20T00:00:00+00:00")
        d = json.loads((t / "sello.json").read_text(encoding="utf-8"))
        ok, _ = verificar(d, clave_esperada=d["clave_publica"])
        _afirma(ok, "un sello recien emitido no verifica")

        # Las tres mitades que importan, y las tres se encontraron mirando.
        #
        # 1) Un REGISTRO tocado rompe la raiz de Merkle.
        tocado = json.loads(json.dumps(d))
        if tocado["registros"]:
            tocado["registros"][0]["actaira_tocado"] = True
        ok, _ = verificar(tocado, clave_esperada=d["clave_publica"])
        _afirma(not ok, "se toco un registro y el sello siguio verificando")

        # 2) Un campo AÑADIDO al sello no puede colarse por no estar firmado.
        #    Verificaba, y eso permite blanquear una afirmacion sin romper la
        #    firma: basta con escribir al lado de lo que si esta firmado.
        anadido = json.loads(json.dumps(d))
        anadido["estado"] = "conforme"
        ok, motivos = verificar(anadido, clave_esperada=d["clave_publica"])
        _afirma(not ok, "un campo sin firmar viajo dentro de un sello VERIFICADO")
        _afirma(any("no cubre" in m for m in motivos), f"y no dijo por que: {motivos}")

        # 3) Sin decir que clave se espera, integridad NO es identidad.
        ok, motivos = verificar(d)
        _afirma(not ok, "verifico sin que nadie dijera que clave esperaba")
    reg.append("sello: verifica sin red; y NO verifica si se toca un registro, "
               "si se anade un campo sin firmar, o si nadie dice que clave espera")


def fase_plan(reg: list[str]) -> None:
    _, salida = cli("plan", str(FIXTURE), "--rol", "proveedor", "--alto-riesgo", "si",
                 "--sector-publico", "no", "--modelo-uso-general", "no",
                 "--riesgo-sistemico", "no", "--fecha", "2027-12-02")
    _afirma(salida.strip(), "el plan salio vacio")
    reg.append(salida.strip().splitlines()[0][:110])


def fase_anexos(reg: list[str]) -> None:
    for cual in ("iv", "v"):
        _, salida = cli("anexo", str(FIXTURE), "--cual", cual, "--alto-riesgo", "si",
                     "--fecha", "2027-12-02",
                     "--respuestas", str(RAIZ / "ejemplos" / "respuestas-clasificador.json"))
        _afirma(salida.strip(), f"el Anexo {cual.upper()} salio vacio")
        reg.append(f"Anexo {cual.upper()}: {len(salida.splitlines())} lineas")


def fase_formularios(reg: list[str]) -> None:
    _, salida = cli("preguntar", str(FIXTURE), "--alto-riesgo", "si", "--fecha", "2027-12-02",
                 "--respuestas", str(RAIZ / "ejemplos" / "respuestas-clasificador.json"))
    _afirma(salida.strip(), "`preguntar` salio vacio")
    _, en = cli("preguntar", str(FIXTURE), "--alto-riesgo", "si", "--fecha", "2027-12-02",
             "--respuestas", str(RAIZ / "ejemplos" / "respuestas-clasificador.json"),
             "--destinatario", "direccion", "--idioma", "en")
    _afirma(en.strip(), "`preguntar --idioma en` salio vacio")
    reg.append(f"preguntar: {len(salida.splitlines())} lineas es, {len(en.splitlines())} en")


def fase_soa(reg: list[str]) -> None:
    _, salida = cli("soa", str(FIXTURE), "--alto-riesgo", "si", "--fecha", "2027-12-02",
                 "--respuestas", str(RAIZ / "ejemplos" / "respuestas-clasificador.json"))
    _afirma(salida.strip(), "la SoA salio vacia")
    reg.append(f"SoA: {len(salida.splitlines())} lineas")


def fase_vigilancia(reg: list[str]) -> None:
    """La invalidacion es SELECTIVA: tocar un README no supera un control del 14."""
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        repo = t / "repo"
        shutil.copytree(FIXTURE, repo)
        alm = str(t / "ev.jsonl")
        cli("vigilar", str(repo), "--alto-riesgo", "si", "--almacen", alm,
            "--ahora", "2027-12-02T10:00:00+00:00", "--registrar")
        primera = (t / "ev.jsonl").read_text(encoding="utf-8").count("\n")
        cli("vigilar", str(repo), "--alto-riesgo", "si", "--almacen", alm,
            "--ahora", "2027-12-02T11:00:00+00:00", "--registrar")
        segunda = (t / "ev.jsonl").read_text(encoding="utf-8").count("\n")
        _afirma(segunda >= primera, "el almacen encogio entre dos pasadas")
        _, salida = cli("vigilar", str(repo), "--alto-riesgo", "si", "--almacen", alm,
                     "--ahora", "2027-12-03T10:00:00+00:00")
        _afirma(salida.strip(), "vigilar no dijo nada")
        reg.append(f"vigilancia: {primera} lineas tras la primera, {segunda} tras la segunda")


def fase_caducidad(reg: list[str]) -> None:
    """Lo unico que hace la suscripcion: darse cuenta sola, sin que nadie empuje."""
    with tempfile.TemporaryDirectory() as tmp:
        alm = str(Path(tmp) / "ev.jsonl")
        cli("vigilar", str(FIXTURE), "--alto-riesgo", "si", "--almacen", alm,
            "--ahora", "2027-12-02T10:00:00+00:00", "--registrar")
        _, pronto = cli("vigilar", "--solo-almacen", "--almacen", alm,
                     "--ahora", "2027-12-03T10:00:00+00:00")
        _, tarde = cli("vigilar", "--solo-almacen", "--almacen", alm,
                    "--ahora", "2028-01-16T10:00:00+00:00")
        _afirma(pronto.strip() != tarde.strip(),
                "cuarenta y cinco dias despues dice exactamente lo mismo que al dia "
                "siguiente: la caducidad no esta haciendo nada")
        reg.append("caducidad: al dia siguiente y 45 dias despues dicen cosas distintas")


def fase_sarif(reg: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "actaira.sarif"
        cli("plan", str(FIXTURE), "--alto-riesgo", "si", "--fecha", "2027-12-02",
            "--sarif", str(ruta))
        d = json.loads(ruta.read_text(encoding="utf-8"))
        _afirma(d.get("version") == "2.1.0", f"SARIF con version {d.get('version')!r}")
        _afirma(d.get("runs"), "SARIF sin `runs`")
        herramienta = d["runs"][0]["tool"]["driver"]
        _afirma(herramienta.get("version"), "SARIF sin version de la herramienta")
        reg.append(f"SARIF 2.1.0 | herramienta {herramienta.get('version')} | "
                   f"{len(d['runs'][0].get('results', []))} resultados")


def fase_contrato(reg: list[str]) -> None:
    r = subprocess.run([PY, "-m", "pytest", "motor/tests/test_contrato.py", "-q"],
                       cwd=RAIZ, env=entorno(), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    _afirma(r.returncode == 0, f"el contrato salio {r.returncode}:\n{r.stdout[-2000:]}")
    esquemas = len(list((RAIZ / "contrato").glob("*.json"))) - 1
    reg.append(f"contrato verde | {esquemas} esquemas publicados")


def arrancar_servidor(comando: list[str], *, cwd: Path, env: dict[str, str],
                      registro: Path) -> tuple[subprocess.Popen, Callable[[], str]]:
    """Arranca el servidor con su bitacora en un FICHERO, y devuelve como leerla.

    POR QUE NO UN `PIPE`
    ----------------------
    Con `stdout=PIPE` y nadie leyendo, el buffer del sistema operativo se llena
    -- son unos pocos kilobytes, no un limite configurable -- y el servidor SE
    BLOQUEA escribiendo su siguiente linea de bitacora. No se muere, no cierra
    el puerto y no dice nada: simplemente deja de contestar.

    Esto no es teorico. Las tres fases que levantan un servidor lo hacian asi, y
    la fase `api` salia roja de vez en cuando con `ConnectionResetError` sin que
    hubiera nada roto en el producto. Se vio al medir latencias: veinticinco
    llamadas seguidas iban bien y a partir de ahi TODAS se quedaban colgadas,
    incluidas las que no arrancan ningun proceso. Parecia el limitador de
    concurrencia -- que es lo que uno mira primero -- y era el arnes
    estrangulando al servidor por su propia bitacora.

    Un rojo intermitente es peor que un rojo: el rojo se arregla, y el
    intermitente se vuelve a correr hasta que sale verde.

    Un fichero no se llena, se lee entero cuando algo falla, y de paso queda
    como prueba de lo que el servidor dijo mientras se le media.
    """
    bitacora = open(registro, "w", encoding="utf-8")
    proceso = subprocess.Popen(comando, cwd=cwd, env=env,
                               stdout=bitacora, stderr=subprocess.STDOUT, text=True)
    proceso.bitacora = bitacora                       # type: ignore[attr-defined]

    def dijo(cuanto: int = 1500) -> str:
        try:
            bitacora.flush()
            return registro.read_text(encoding="utf-8", errors="replace")[-cuanto:]
        except OSError:
            return "(sin bitacora)"

    return proceso, dijo


def parar_servidor(proceso: subprocess.Popen) -> None:
    """Lo para, y cierra su bitacora. Nunca revienta: se llama desde un `finally`."""
    proceso.terminate()
    try:
        proceso.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proceso.kill()
    bitacora = getattr(proceso, "bitacora", None)
    if bitacora is not None:
        bitacora.close()


def lanzador_del_motor(carpeta: Path) -> Path:
    """Escribe un ejecutable `actaira` que reenvia al CLI de este arbol.

    Lo usan la fase de la API -- que necesita que el servidor pueda invocar el
    motor como un proceso aparte, que es la frontera de la arquitectura -- y la
    fase de Go, donde tres pruebas del nucleo de la suscripcion se saltaban
    solas por no encontrarlo.

    Esas tres eran justamente las del revisor de vencimientos, es decir, las
    del unico trabajo que el producto hace sin que nadie lo pida. Se saltaban
    diciendolo, que es mejor que fallar en silencio, pero el efecto practico
    era que nunca corrian en ninguna parte.
    """
    exe = carpeta / ("actaira.cmd" if os.name == "nt" else "actaira")
    if os.name == "nt":
        exe.write_text(
            "@echo off\r\n"
            'set "PYTHONPATH=' + str(MOTOR_SRC) + '"\r\n'
            "set PYTHONUTF8=1\r\n"
            "set PYTHONIOENCODING=utf-8\r\n"
            f'"{PY}" -m actaira_motor.cli %*\r\n', encoding="utf-8")
    else:
        exe.write_text(
            "#!/bin/sh\n"
            f'PYTHONPATH="{MOTOR_SRC}" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 '
            f'exec "{PY}" -m actaira_motor.cli "$@"\n', encoding="utf-8")
        os.chmod(exe, 0o700)
    return exe


def fase_go(reg: list[str]) -> None:
    if not shutil.which("go"):
        raise Omitida("`go` no esta en el PATH")
    plataforma = RAIZ / "plataforma"
    sin_formato = subprocess.run(["gofmt", "-l", "."], cwd=plataforma,
                                 capture_output=True, text=True).stdout.strip()
    _afirma(not sin_formato, f"gofmt tiene cosas que decir:\n{sin_formato}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        exe = lanzador_del_motor(tmp)
        env = dict(os.environ)
        # CON el motor en el camino y CON un repositorio de ejemplo.
        #
        # Sin esto, tres pruebas se saltan solas -- las del revisor de
        # vencimientos, que es el unico trabajo que la suscripcion hace por su
        # cuenta -- y se saltan en todas partes, porque nadie instala la rueda
        # antes de correr `go test`. Un salto que ocurre siempre no es un salto
        # condicional: es una prueba que no existe.
        env["PATH"] = str(tmp) + os.pathsep + env.get("PATH", "")
        env["ACTAIRA_FIXTURE"] = str(FIXTURE)
        for orden in (["go", "vet", "./..."],
                      ["go", "test", "./...", "-count=1", "-v"]):
            r = subprocess.run(orden, cwd=plataforma, env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            salida = r.stdout
            if r.returncode != 0:
                # EL DIAGNOSTICO, y no la cola de la salida.
                #
                # Esto cortaba los ultimos 2500 caracteres de stdout, y con
                # `-v` la salida de Go son miles de lineas: el `--- FAIL` y su
                # motivo quedaban en medio y se perdian. La puerta decia «salio
                # 1» y ensenaba el final de otros paquetes que SI habian
                # pasado, asi que para saber que se rompio habia que volver a
                # correrlo todo a mano. Una puerta que se pone roja sin decir
                # por que se acaba corriendo dos veces siempre, y la segunda es
                # la que de verdad cuesta.
                filas = salida.splitlines()
                fallos = [x.strip() for x in filas if x.lstrip().startswith("--- FAIL")]
                porque = [x.strip() for x in filas if "_test.go:" in x]
                _afirma(False,
                        f"`{' '.join(orden)}` salio {r.returncode}\n  "
                        + "\n  ".join(fallos[:10] + porque[:15])
                        + (f"\n  {r.stderr[-600:]}" if r.stderr.strip() else ""))

    # LOS SALTOS SE MIRAN, Y SE MIRAN POR SU MOTIVO.
    #
    # Hay dos clases y confundirlas afloja la puerta o la vuelve imposible de
    # cumplir. Un salto por algo que ESTA FASE PUEDE APORTAR -- el motor
    # instalado, un repositorio de ejemplo -- es una prueba que no corre en
    # ninguna parte, y por tanto una prueba que no existe: eso es rojo. Un
    # salto porque ESTE SISTEMA no puede correrla -- los bits de permisos
    # POSIX en Windows, que Go sintetiza y no informan -- es una limitacion de
    # la maquina y no del producto: eso se DICE, con su nombre, y no se
    # esconde.
    #
    # La primera version de esta puerta exigia cero saltos y se cazo a si
    # misma: marcaba la prueba que comprueba que la via de escape de permisos
    # no sirve de atajo donde si se puede medir, que en Windows no se puede
    # correr por construccion.
    lineas_salida = salida.splitlines()
    saltadas: list[tuple[str, str]] = []
    for i, l in enumerate(lineas_salida):
        if "--- SKIP:" not in l:
            continue
        nombre = l.split("SKIP:")[1].strip().split(" ")[0]
        # El motivo va ANTES del `--- SKIP:`, no despues: `go test -v` imprime
        # primero lo que el test escribio y luego el veredicto. Mirar la linea
        # siguiente daba el `=== RUN` del test de al lado, asi que esta puerta
        # imprimia un motivo que no era el de esa prueba. Un diagnostico que
        # nombra la causa equivocada es peor que no dar causa.
        motivo = ""
        for j in range(i - 1, max(-1, i - 6), -1):
            anterior = lineas_salida[j].strip()
            if anterior.startswith("=== RUN") or anterior.startswith("--- "):
                break
            if ": " in anterior:
                motivo = anterior.split(": ", 1)[1]
                break
        saltadas.append((nombre, motivo))

    APORTABLES = ("no esta instalado", "ACTAIRA_FIXTURE", "binario")
    evitables = [n for n, m in saltadas if any(x in m for x in APORTABLES)]
    _afirma(not evitables,
            f"con el motor disponible siguen saltandose {len(evitables)} pruebas por "
            f"algo que esta fase SI aporta: {evitables}. Una prueba que se salta en "
            f"todas partes es una prueba que no existe.")

    corridas = sum(1 for l in lineas_salida if "--- PASS:" in l)
    reg.append(f"go: gofmt limpio, vet limpio, {corridas} pruebas corridas, "
               f"{len(saltadas)} saltadas por el sistema")
    for nombre, motivo in saltadas:
        reg.append(f"  saltada  {nombre}: {motivo[:95] or '(sin motivo declarado)'}")

    # EL DETECTOR DE CARRERAS, AQUI Y NO SOLO EN LA INTEGRACION CONTINUA.
    #
    # `-race` vivia unicamente en el flujo de CI, y solo en el trabajo de
    # Linux. Eso dejaba a quien desarrolla sin poder correrlo en la maquina
    # donde escribe, asi que en la practica no se corria: una carrera de datos
    # se descubria -- si se descubria -- despues de empujar.
    #
    # Y se descubrio una. `preparar()` del planificador ESCRIBE campos y lo
    # llaman los dos metodos exportados, `Correr` y `UnaPasada`; ninguna prueba
    # los llamaba a la vez, asi que el detector no tenia nada que ver y la
    # carrera paso tres pasadas adversariales. Al escribir la prueba que si los
    # llama a la vez, `-race` canto CUATRO avisos contra el codigo de entonces.
    #
    # NECESITA UN COMPILADOR DE C, y por eso esto no es una afirmacion de la
    # fase sino una linea que dice lo que paso. Si no lo hay, se DICE en vez de
    # callarse: la alternativa -- declarar la fase omitida -- pondria en rojo a
    # todo el que corra la puerta sin compilador de C, y una puerta que se pone
    # roja donde el producto esta bien enseña a apagarla.
    cc = next((x for x in ("gcc", "clang", "cc") if shutil.which(x)), None)
    if cc is None:
        reg.append("  sin detector de carreras: no hay compilador de C en el PATH "
                   "(`-race` lo necesita). Lo corre la matriz en Linux.")
        return
    env_race = dict(env)
    env_race["CGO_ENABLED"] = "1"
    r = subprocess.run(["go", "test", "-race", "./...", "-count=1"],
                       cwd=plataforma, env=env_race, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    todo_race = r.stdout + r.stderr
    _afirma("WARNING: DATA RACE" not in todo_race,
            "hay una carrera de datos:\n  "
            + "\n  ".join(todo_race.split("WARNING: DATA RACE", 1)[-1].splitlines()[:18]))
    _afirma(r.returncode == 0,
            f"`go test -race` salio {r.returncode}:\n  "
            + "\n  ".join([x for x in todo_race.splitlines() if "FAIL" in x][:10]))
    reg.append(f"  y bajo el detector de carreras ({cc}): sin una sola carrera")


def fase_api(reg: list[str]) -> None:
    """Levanta la API de verdad y comprueba el aislamiento por credencial."""
    if not shutil.which("go"):
        raise Omitida("`go` no esta en el PATH")
    import secrets
    import socket

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "clientes" / "acme").mkdir(parents=True)
        shutil.copytree(FIXTURE, t / "clientes" / "acme" / "trabajo")
        token = "demo-" + secrets.token_urlsafe(24)
        cred = t / "cred.json"
        cred.write_text(json.dumps({token: "acme"}), encoding="utf-8")
        os.chmod(cred, 0o600)

        # El servidor invoca el motor como un proceso aparte, que es la
        # frontera de la arquitectura. Aqui se le da un lanzador que reenvia al
        # CLI de este arbol en vez de exigir la rueda instalada: lo que esta
        # fase mide es el transporte y el aislamiento por credencial, no el
        # empaquetado -- eso lo mide `paquete`, y por separado, porque cuando
        # una fase mide dos cosas a la vez su rojo no dice cual se rompio.
        motor_exe = lanzador_del_motor(t)

        binario = t / ("actaira-api.exe" if os.name == "nt" else "actaira-api")
        r = subprocess.run(["go", "build", "-o", str(binario), "./cmd/actaira-api"],
                           cwd=RAIZ / "plataforma", capture_output=True, text=True)
        _afirma(r.returncode == 0, f"no compila el servidor: {r.stderr[-1500:]}")

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            puerto = s.getsockname()[1]
        base = f"http://127.0.0.1:{puerto}"

        env = dict(os.environ)
        if os.name == "nt":
            # En Windows los bits de `os.Stat` no dicen quien lee el fichero, y
            # el servidor se niega a arrancar sin una afirmacion del operador.
            # Aqui el fichero acaba de crearse en un temporal del proceso, asi
            # que la afirmacion es cierta y se hace explicita.
            env["ACTAIRA_PERMISOS_AFIRMADOS_POR_EL_OPERADOR"] = "1"
        proceso, dijo = arrancar_servidor(
            [str(binario), "--clientes", str(t / "clientes"), "--credenciales", str(cred),
             "--motor", str(motor_exe), "--escucha", f"127.0.0.1:{puerto}",
             # La vigilancia, arrancada de verdad y con un intervalo corto para
             # que de mas de una pasada mientras dura esta fase.
             "--revisar-cada", "2s", "--bitacora", str(t / "vigilancia.jsonl")],
            cwd=RAIZ / "plataforma", env=env, registro=t / "servidor.log")
        try:
            salud = None
            for _ in range(60):
                if proceso.poll() is not None:
                    raise AssertionError(
                        f"el servidor murio al arrancar:\n{dijo()}")
                try:
                    with urllib.request.urlopen(base + "/salud", timeout=1) as resp:
                        salud = resp.read().decode("utf-8")
                    break
                except (urllib.error.URLError, OSError):
                    time.sleep(0.25)
            _afirma(salud is not None, "el servidor no respondio a /salud en 15 s")

            cuerpo = json.dumps({"roles": ["proveedor"], "alto_riesgo": "si",
                                 "via_anexo": "anexo_iii", "fecha": "2027-12-02"}).encode()

            # Sin credencial NO se pasa. Es la mitad que de verdad importa.
            codigo = 0
            pet = urllib.request.Request(base + "/v1/clientes/acme/plan", data=cuerpo,
                                         headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(pet, timeout=20)
            except urllib.error.HTTPError as e:
                codigo = e.code
            _afirma(codigo in (401, 403),
                    f"sin credencial se contesto {codigo or 200}: eso es un servidor abierto")

            pet = urllib.request.Request(
                base + "/v1/clientes/acme/plan", data=cuerpo,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(pet, timeout=120) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            _afirma(d.get("documento", {}).get("esquema"), "la respuesta no trae esquema")
            ata_prov = d["documento"]["recuento"]

            # El camino ENTERO con el rol que estaba roto, y con dos a la vez.
            #
            # El panel mandaba `responsable_del_despliegue`, la API lo validaba
            # contra su propia lista -- con el mismo error -- y el motor
            # contestaba cero obligaciones. Aqui se comprueba que el nombre
            # canonico llega y ata, que el de entonces se RECHAZA en el borde, y
            # que declarar dos roles no obliga a elegir uno.
            def _plan(roles):
                cuerpo = json.dumps({"roles": roles, "alto_riesgo": "si",
                                     "via_anexo": "anexo_iii",
                                     "fecha": "2027-12-02"}).encode()
                pet = urllib.request.Request(
                    base + "/v1/clientes/acme/plan", data=cuerpo,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {token}"})
                try:
                    with urllib.request.urlopen(pet, timeout=120) as resp:
                        return resp.status, json.loads(resp.read().decode("utf-8"))
                except urllib.error.HTTPError as e:
                    return e.code, None

            _, resp = _plan(["responsable_despliegue"])
            ata_resp = resp["documento"]["recuento"]
            _afirma(sum(v for k, v in ata_resp.items() if k != "no_ata") > 0,
                    "un responsable del despliegue recibe un plan vacio")

            estado_malo, _ = _plan(["responsable_del_despliegue"])
            _afirma(estado_malo >= 400,
                    f"el nombre de rol equivocado se acepto con {estado_malo} en vez de "
                    f"rechazarse: es el fallo que devolvia cero obligaciones")

            _, resp = _plan(["proveedor", "responsable_despliegue"])
            ata_dos = resp["documento"]["recuento"]
            _afirma(ata_dos["no_ata"] < min(ata_prov["no_ata"], ata_resp["no_ata"]),
                    "declarar dos roles no ato mas obligaciones que declarar uno")

            # LA VIGILANCIA CORRE DE VERDAD, y no solo existe como paquete.
            #
            # Aqui estaba el fallo mas caro de los que encontro la auditoria:
            # `main` construia el servidor pasandole el revisor como `nil`, y
            # el campo no se leia en ningun sitio. El paquete `vencimientos`
            # compilaba, tenia sus pruebas verdes y el producto en marcha no lo
            # invocaba jamas. La vigilancia continua, que es lo unico que la
            # suscripcion hace sin que nadie la pida, se reducia a que alguien
            # se acordara de llamar a un endpoint.
            #
            # Se comprueba contra el servidor LEVANTADO, porque una prueba de
            # unidad del planificador habria seguido pasando con el `nil`
            # puesto: lo que fallaba no era el planificador, era el cableado.
            estado = json.loads(salud)
            vig = estado.get("vigilancia") or {}
            _afirma(vig.get("activa") is True,
                    f"el servidor arranco sin vigilancia: {estado}")

            bitacora = t / "vigilancia.jsonl"
            pasadas = 0
            for _ in range(80):
                if bitacora.exists():
                    pasadas = sum(
                        1 for linea in bitacora.read_text(encoding="utf-8").splitlines()
                        if linea.strip() and json.loads(linea).get("tipo") == "pasada")
                    if pasadas >= 2:
                        break
                time.sleep(0.25)
            _afirma(pasadas >= 2,
                    f"la vigilancia dice estar activa y en 20 s solo dio {pasadas} pasadas: "
                    f"esta cableada pero no corre")

            with urllib.request.urlopen(base + "/salud", timeout=5) as resp:
                vig2 = json.loads(resp.read().decode("utf-8"))["vigilancia"]
            _afirma(vig2["pasadas"] >= 2,
                    f"/salud dice {vig2['pasadas']} pasadas y la bitacora {pasadas}")

            # EL ALMACEN DE EVIDENCIA SE ESCRIBE DESDE LA PLATAFORMA.
            #
            # Lo leen TRES rutas -- `almacen`, `vencimientos` y `revision` -- y
            # durante un tiempo no lo escribio ninguna: la ruta de `vigilar` no
            # pasaba `--registrar`, asi que el motor observaba y tiraba lo
            # observado. A traves de la plataforma el expediente estaba SIEMPRE
            # vacio, y con el la vigilancia, los vencimientos y la revision por
            # la direccion. Tres pantallas correctas encima de un fichero que no
            # existe (B-004).
            #
            # Ninguna prueba lo veia porque todas eran ciertas por separado: el
            # verbo registra cuando se le pide, la ruta contesta 200, el
            # documento valida contra su esquema. Lo que fallaba era el CABLEADO,
            # que es lo mismo que le paso al revisor de vencimientos cuando se
            # construia con `nil`. Por eso se comprueba aqui, contra el servidor
            # levantado, y no en unidad.
            def _almacen():
                pet = urllib.request.Request(
                    base + "/v1/clientes/acme/almacen",
                    headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(pet, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))["documento"]

            def _vigilar():
                pet = urllib.request.Request(
                    base + "/v1/clientes/acme/vigilar", data=cuerpo,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(pet, timeout=180) as resp:
                    return json.loads(resp.read().decode("utf-8"))["documento"]

            antes = _almacen()
            _afirma(antes["existe"] is False and antes["observaciones"] == 0,
                    f"el cliente de esta fase arranca con almacen: {antes['ruta']}")

            uno = _vigilar()
            despues = _almacen()
            _afirma(despues["existe"] and despues["observaciones"] > 0,
                    f"se vigilo y el almacen sigue vacio: la plataforma no escribe "
                    f"evidencia, asi que `vencimientos` y `revision` leen de un "
                    f"fichero que no existe. Vigilancia dijo {uno.get('registradas')} "
                    f"registradas y el almacen {despues}")
            _afirma(despues["verifica"] and not despues["roturas"],
                    f"la plataforma escribio una cadena que no verifica: {despues}")
            _afirma(uno["registradas"] == despues["observaciones"],
                    f"vigilancia dice {uno['registradas']} registradas y el almacen "
                    f"tiene {despues['observaciones']} observaciones")

            # Y que la SEGUNDA pasada revalide en vez de duplicar. Sin esto, el
            # tamano del almacen mide la frecuencia con la que alguien pulsa el
            # boton en vez de la actividad del cliente, y la frescura se
            # quedaria quieta aunque se este mirando cada dia.
            dos = _vigilar()
            otra_vez = _almacen()
            _afirma(dos["registradas"] == 0 and dos["revalidadas"] > 0,
                    f"la segunda pasada volvio a registrar en vez de revalidar: {dos}")
            _afirma(otra_vez["observaciones"] == despues["observaciones"],
                    f"el almacen crecio al repetir la misma observacion: "
                    f"{despues['observaciones']} -> {otra_vez['observaciones']}")

            # Y que las dos rutas que LEEN ese almacen vean lo escrito. Es la
            # mitad que de verdad importa: lo otro es un fichero con lineas.
            for ruta, cuantos in (("vencimientos", "veredictos"), ("revision", "entradas")):
                pet = urllib.request.Request(
                    base + f"/v1/clientes/acme/{ruta}",
                    headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(pet, timeout=60) as resp:
                    doc = json.loads(resp.read().decode("utf-8"))["documento"]
                _afirma(len(doc.get(cuantos) or []) > 0,
                        f"`{ruta}` no ve la evidencia que `vigilar` acaba de escribir: "
                        f"{cuantos} vacio con {otra_vez['observaciones']} observaciones "
                        f"en el almacen")

            reg.append(f"evidencia: la plataforma escribe -- {uno['registradas']} "
                       f"observaciones, cadena que verifica, cabeza "
                       f"{str(despues['cabeza'])[:19]}... -- y al repetir revalida "
                       f"{dos['revalidadas']} sin duplicar ninguna")

            reg.append(f"API: /salud responde, sin credencial {codigo}, "
                       f"con credencial esquema {d['documento']['esquema']}")
            reg.append(f"vigilancia: activa, {vig2['pasadas']} pasadas sin que nadie "
                       f"empuje nada, {vig2['avisos_sin_entregar']} avisos sin entregar")

            # LOS TOPES, contra el servidor levantado.
            #
            # Un verbo del motor arranca un proceso que lee el repositorio
            # entero, y no habia nada que limitara cuantos corren a la vez: N
            # peticiones eran N procesos, y como un solo binario sirve a todos
            # los clientes, el que se quedaba sin maquina no era solo el que
            # empujo. Se comprueba aqui y no en unidad porque lo que puede
            # fallar es el CABLEADO -- el limitador existia y podia no estar
            # enchufado, que es exactamente lo que le pasaba a la vigilancia.
            motor_estado = vig2 and json.loads(
                urllib.request.urlopen(base + "/salud", timeout=5).read().decode("utf-8"))
            topes = motor_estado["motor"]
            _afirma(topes["tope_global"] > 0 and topes["tope_por_cliente"] > 0,
                    f"el servidor arranco sin topes de concurrencia: {topes}")
            _afirma(topes["tope_por_cliente"] <= topes["tope_global"],
                    f"el tope por cliente pasa del global: {topes}")

            # Se lanzan mas planes a la vez de los que el tope permite y se
            # exige que alguno salga 429 CON `Retry-After`: sin esa cabecera,
            # un cliente bien escrito reintenta en bucle y convierte el tope en
            # una tormenta.
            import concurrent.futures

            def _uno(_):
                pet = urllib.request.Request(
                    base + "/v1/clientes/acme/plan", data=cuerpo,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {token}"})
                try:
                    with urllib.request.urlopen(pet, timeout=180) as resp:
                        return resp.status, ""
                except urllib.error.HTTPError as e:
                    return e.code, e.headers.get("Retry-After", "")

            cuantos = topes["tope_por_cliente"] + 3
            with concurrent.futures.ThreadPoolExecutor(max_workers=cuantos) as ex:
                salidas = list(ex.map(_uno, range(cuantos)))
            rechazos = [x for x in salidas if x[0] == 429]
            _afirma(rechazos,
                    f"{cuantos} planes a la vez con tope {topes['tope_por_cliente']} y "
                    f"ninguno se rechazo: el limitador no esta enchufado. Salidas: {salidas}")
            _afirma(all(x[1] for x in rechazos),
                    f"hubo 429 sin cabecera `Retry-After`: {rechazos}")
            _afirma(any(x[0] == 200 for x in salidas),
                    f"se rechazaron TODOS: un tope que no deja pasar nada no es un tope. "
                    f"Salidas: {salidas}")
            reg.append(f"topes: {cuantos} planes a la vez con tope "
                       f"{topes['tope_por_cliente']}/cliente -> "
                       f"{sum(1 for x in salidas if x[0] == 200)} corrieron, "
                       f"{len(rechazos)} rechazados con Retry-After")
            reg.append(f"roles: proveedor no_ata={ata_prov['no_ata']}, "
                       f"responsable no_ata={ata_resp['no_ata']}, "
                       f"los dos no_ata={ata_dos['no_ata']}, "
                       f"nombre equivocado -> {estado_malo}")
        finally:
            parar_servidor(proceso)


def fase_paquete(reg: list[str]) -> None:
    """Construye la rueda, la instala en un entorno VIRGEN y corre el verbo.

    Es la fase que sostiene el criterio de aceptacion «todas las pruebas verdes
    desde una instalacion limpia». Mide tres cosas que ninguna otra mide:

      - que el catalogo viaja DENTRO de la rueda. Vive en la raiz del arbol,
        que es donde lo revisa un jurista, y se copia al empaquetar. Si esa
        copia se rompiera, el motor instalado cargaria un catalogo vacio y no
        ataria ninguna obligacion a nadie: el peor fallo posible, y silencioso.
      - que el punto de entrada `actaira` existe y responde.
      - que no hace falta nada del arbol para correrlo.
    """
    try:
        import build  # noqa: F401
    except ImportError:
        raise Omitida("falta `build` (pip install build) para construir la rueda") from None

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        r = subprocess.run([PY, "-m", "build", "--wheel", "--outdir", str(t), "."],
                           cwd=RAIZ, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        _afirma(r.returncode == 0, f"no se construye la rueda:\n{r.stdout[-2000:]}")
        ruedas = sorted(t.glob("*.whl"))
        _afirma(ruedas, "no salio ninguna rueda")

        import zipfile
        dentro = zipfile.ZipFile(ruedas[-1]).namelist()
        catalogo = [x for x in dentro if "_catalogo" in x]
        _afirma(len(catalogo) > 20,
                f"la rueda solo trae {len(catalogo)} ficheros de catalogo: "
                f"un motor instalado con el catalogo a medias no ata nada a nadie")

        venv = t / "venv"
        r = subprocess.run([PY, "-m", "venv", str(venv)], capture_output=True, text=True)
        _afirma(r.returncode == 0, f"no se crea el entorno virgen: {r.stderr[-800:]}")
        binarios = venv / ("Scripts" if os.name == "nt" else "bin")
        pip = binarios / ("pip.exe" if os.name == "nt" else "pip")
        r = subprocess.run([str(pip), "install", "-q", str(ruedas[-1])],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        _afirma(r.returncode == 0, f"la rueda no instala:\n{r.stdout[-1500:]}{r.stderr[-1500:]}")

        actaira = binarios / ("actaira.exe" if os.name == "nt" else "actaira")
        _afirma(actaira.exists(), f"la rueda no dejo el punto de entrada en {actaira}")
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # `cwd=t` a proposito: fuera del arbol. Si el motor instalado necesitara
        # algo del repositorio para funcionar, aqui se veria.
        r = subprocess.run([str(actaira), "aplicabilidad", "--rol", "proveedor",
                            "--alto-riesgo", "si", "--fecha", "2027-12-02"],
                           cwd=t, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        _afirma(r.returncode in VEREDICTOS,
                f"el motor instalado salio {r.returncode}:\n{r.stdout[-1200:]}{r.stderr[-1200:]}")
        _afirma(r.stdout.strip(), "el motor instalado no dijo nada")
        reg.append(f"rueda {ruedas[-1].name}: {len(catalogo)} ficheros de catalogo dentro, "
                   f"instala en entorno virgen y responde fuera del arbol")


# Los ficheros que le dicen a alguien como instalar esto. Si aparece uno
# nuevo, se anade aqui: la lista corta es el precio de que la puerta sea
# exacta en vez de aproximada.
DONDE_SE_INSTRUYE_INSTALAR = (
    "README.md",
    # El README en ingles y el manual en los dos idiomas mandan instalar
    # tambien, y son ahora los documentos por los que alguien entra. Se anaden
    # el mismo dia que nacen: la unica forma de que esta lista se quede corta
    # es que un documento nuevo diga `pip install actaira-motor` y nadie lo
    # comprobara, que es exactamente el fallo que esta fase existe para cazar.
    "README.en.md",
    "docs/MANUAL.md",
    "docs/MANUAL.en.md",
    "integraciones/README.md",
    "integraciones/github/actaira.yml",
    "docs/ARQUITECTURA.md",
    "sitio/textos.json",
)


def fase_instalacion(reg: list[str]) -> None:
    """Que lo que se manda instalar EXISTA.

    El README, la portada y la plantilla de integracion continua decian las
    tres `pip install actaira-motor`. Ese paquete no esta publicado en PyPI, y
    no lo estaba cuando se escribieron: la PRIMERA orden que lee quien llega al
    repositorio fallaba con un 404. No es un defecto del producto -- el
    producto instala y corre perfectamente -- es un defecto de lo que el
    producto dice de si mismo, y en la primera linea.

    No se comprueba contra la red a proposito. Una puerta que pregunta a PyPI
    se pone roja el dia que PyPI este caido, y entonces se aprende a ignorarla.
    Lo que se comprueba es que los documentos y la casa digan LO MISMO: hay una
    sola declaracion, `PUBLICADO_EN_PYPI`, y los documentos tienen que seguirla.
    """
    sys.path.insert(0, str(MOTOR_SRC))
    from actaira_motor import PUBLICADO_EN_PYPI

    desde_pypi = "pip install actaira-motor"
    desde_repo = "pip install git+https://github.com/marcosmatalab/actaira-sys"

    malos = []
    for rel in DONDE_SE_INSTRUYE_INSTALAR:
        fichero = RAIZ / rel
        _afirma(fichero.exists(), f"{rel} no existe y esta en la lista")
        for numero, linea in enumerate(fichero.read_text(encoding="utf-8").splitlines(), 1):
            pelada = linea.strip().lstrip("#").lstrip(">").strip()
            # Un comentario o una nota PUEDEN nombrar la via que no vale: es
            # justo donde se explica por que no vale. Lo que no puede es ser
            # una instruccion.
            if pelada.startswith("//") or linea.lstrip().startswith(("#", ">", "|")):
                continue
            if not PUBLICADO_EN_PYPI and desde_pypi in linea and desde_repo not in linea:
                malos.append(f"{rel}:{numero} manda instalar de PyPI y ahi no hay nada: "
                             f"{linea.strip()[:80]}")
            if PUBLICADO_EN_PYPI and desde_repo in linea:
                malos.append(f"{rel}:{numero} sigue instalando del repositorio con el "
                             f"paquete ya publicado: {linea.strip()[:80]}")

    _afirma(not malos, "instalacion:\n  " + "\n  ".join(malos))
    donde = "PyPI" if PUBLICADO_EN_PYPI else "el repositorio"
    reg.append(f"lo que se manda instalar sale de {donde}, y los "
               f"{len(DONDE_SE_INSTRUYE_INSTALAR)} documentos que lo dicen coinciden")


def fase_documentacion(reg: list[str]) -> None:
    """Que lo que los documentos AFIRMAN sobre el arbol siga siendo lo que hay.

    `docs/ARQUITECTURA.md` decia 24 obligaciones con 48 en el catalogo, 60
    pares con 101 y 205 pruebas con mas de quinientas, y lo decia bajo una
    frase que prometia que ninguna cifra estaba escrita a mano. Esa frase es lo
    que hacia dano: convierte una lista de cifras viejas en una lista de cifras
    avaladas, y quien lee deja de comprobarlas.
    """
    for guion, que in (("generar_docs.py", "las cifras de la documentacion"),
                       ("generar_roles.py", "los derivados del vocabulario de roles"),
                       ("generar_openapi.py", "la especificacion de la API")):
        r = subprocess.run([PY, str(RAIZ / "herramientas" / guion), "--comprobar"],
                           cwd=RAIZ, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        _afirma(r.returncode == 0, f"{que}: {r.stdout}{r.stderr}")
        reg.append(r.stdout.strip().splitlines()[-1])

    sys.path.insert(0, str(MOTOR_SRC))
    from actaira_motor import __version__

    flujo = (RAIZ / "integraciones" / "github" / "actaira.yml").read_text(encoding="utf-8")
    import re as _re
    clavadas = set(_re.findall(r'ACTAIRA_VERSION:\s*"([^"]+)"', flujo))
    # La plantilla clava una ETIQUETA de git (`v0.15.0`) mientras no haya
    # paquete publicado, y el paquete se llama `0.15.0`. Misma version, dos
    # convenciones. Ver el mismo comentario en `test_documentacion.py`.
    clavadas = {v[1:] if v.startswith("v") else v for v in clavadas}
    _afirma(clavadas == {__version__},
            f"la plantilla de integracion continua instala {sorted(clavadas)} y el "
            f"paquete es {__version__}: un cliente que la copie correria otra version")
    cambios = (RAIZ / "docs" / "CAMBIOS.md")
    _afirma(cambios.is_file() and __version__ in cambios.read_text(encoding="utf-8"),
            f"el registro de cambios no dice que trae la {__version__}")
    reg.append(f"version {__version__} en el paquete, en la plantilla y en el registro "
               f"de cambios")

    # LAS IMAGENES QUE EL README ENSENA, QUE EXISTAN.
    #
    # Es el documento que mas gente lee y el unico que ensena la pantalla. Una
    # imagen rota no rompe nada, no falla ninguna prueba y se ve desde el
    # primer segundo: es la forma mas barata que tiene este repositorio de
    # parecer abandonado. Y el que las genera -- `herramientas/navegador.py
    # --capturas` -- puede renombrar una salida sin que nadie se entere.
    import re as _re2

    # Los documentos que ENSENAN la pantalla, y la carpeta desde la que cada uno
    # la referencia. El README esta en la raiz y el manual en `docs/`, asi que la
    # misma imagen se escribe de dos formas distintas.
    CON_IMAGENES = {
        "README.md": "docs/imagenes/",
        "README.en.md": "docs/imagenes/",
        "docs/MANUAL.md": "imagenes/",
        "docs/MANUAL.en.md": "imagenes/",
    }
    todas, faltan, sin_alt = set(), [], []
    for rel, prefijo in CON_IMAGENES.items():
        fichero = RAIZ / rel
        _afirma(fichero.is_file(), f"{rel} no existe y esta en la lista")
        texto = fichero.read_text(encoding="utf-8")
        # Las dos formas de poner una imagen: Markdown y `<img>`. Mirar solo una
        # dejaria la mitad del manual sin comprobar.
        citadas = set(_re2.findall(rf'src="({prefijo}[^"]+)"', texto))
        citadas |= set(_re2.findall(rf'!\[[^\]]*\]\(({prefijo}[^)]+)\)', texto))
        _afirma(citadas, f"{rel} no ensena ni una imagen de la pantalla")
        base = fichero.parent
        for x in sorted(citadas):
            ruta = (base / x).resolve()
            todas.add(ruta)
            if not ruta.is_file():
                faltan.append(f"{rel} -> {x}")
        # Y que ninguna se quede sin texto alternativo. Es lo primero que lee
        # alguien con un lector de pantalla, y este producto tiene una fase
        # entera dedicada a la accesibilidad de sus otras dos paginas.
        sin_alt += [f"{rel}: {x[:70]}" for x in _re2.findall(r'<img [^>]*>', texto)
                    if 'alt="' not in x or 'alt=""' in x]
        sin_alt += [f"{rel}: ![]({x})" for x in _re2.findall(r'!\[\]\(([^)]+)\)', texto)]

    _afirma(not faltan,
            f"hay documentos que ensenan imagenes que no existen: {faltan}. "
            f"Se regeneran con `python herramientas/navegador.py --capturas` y "
            f"`--gif`")
    _afirma(not sin_alt, f"hay imagenes sin texto alternativo: {sin_alt}")

    # Y al reves: una captura que ya no ensena nadie. No es un fallo del
    # producto, pero son megabytes que viajan en cada clon para siempre, y el
    # generador que las hace puede renombrar una salida sin que nadie note que
    # la vieja se queda.
    carpeta = RAIZ / "docs" / "imagenes"
    huerfanas = sorted(x.name for x in carpeta.glob("*")
                       if x.resolve() not in todas)
    _afirma(not huerfanas,
            f"hay imagenes en docs/imagenes/ que no ensena ningun documento: "
            f"{huerfanas}. O se citan, o se borran")

    peso = sum(x.stat().st_size for x in todas) / 1e6
    reg.append(f"las {len(todas)} imagenes de los {len(CON_IMAGENES)} documentos "
               f"existen, todas con texto alternativo y todas citadas, "
               f"{peso:.1f} MB en total")

    # Y QUE LOS ENLACES LLEVEN A ALGUN SITIO.
    #
    # Estos cuatro documentos se enlazan entre si, mandan a la plantilla de
    # integracion continua, a la licencia y al registro de cambios. Un enlace
    # roto en el documento que alguien lee primero no rompe nada y se ve desde
    # el primer segundo, que es la peor combinacion posible: nadie se entera
    # hasta que lo pulsa un cliente.
    #
    # NO se comprueban los `http`: una puerta que pregunta a la red se pone
    # roja el dia que la red este mal y se aprende a ignorar. Aqui se comprueba
    # lo que este arbol controla, que es lo que este arbol puede romper.
    enlaces, rotos = 0, []
    for rel in CON_IMAGENES:
        fichero = RAIZ / rel
        texto = fichero.read_text(encoding="utf-8")
        for destino in _re2.findall(r"\]\(([^)#][^)]*)\)", texto):
            if destino.startswith(("http://", "https://", "mailto:")):
                continue
            enlaces += 1
            if not (fichero.parent / destino.split("#")[0]).exists():
                rotos.append(f"{rel} -> {destino}")
    _afirma(not rotos, f"hay enlaces que no llevan a ningun sitio: {rotos}")
    reg.append(f"los {enlaces} enlaces internos de esos documentos existen")

    # Y QUE LAS ORDENES QUE MANDAN TECLEAR EXISTAN, CON SUS BANDERAS.
    #
    # `fase_instalacion` ya comprueba la PRIMERA orden que lee alguien -- la de
    # instalar -- porque mando a un 404 durante meses. Las demas no las
    # comprobaba nadie, y el manual manda teclear treinta y dos.
    #
    # Una bandera renombrada en el motor deja el manual mandando teclear algo
    # que contesta «unrecognized arguments» y, lo que es peor, lo deja
    # exactamente igual de creible: nada falla, nada se pone rojo, y el defecto
    # solo lo encuentra el primer cliente que copie la linea.
    #
    # Se le pregunta al CLI de verdad con `--help` en vez de leer `cli.py` con
    # un analizador: un analizador a medias de argparse se relaja hasta que deja
    # de mirar, y aqui lo que se quiere saber es lo que el binario acepta.
    citadas: set[tuple[str, str]] = set()
    for rel in CON_IMAGENES:
        texto = (RAIZ / rel).read_text(encoding="utf-8")
        for verbo, resto in _re2.findall(r"`?actaira ([a-z]+)([^`\n]*)`?", texto):
            citadas.add((verbo, resto.strip()))

    malas: list[str] = []
    ayudas: dict[str, str] = {}
    for verbo, resto in sorted(citadas):
        if verbo not in ayudas:
            r = subprocess.run([PY, "-m", "actaira_motor.cli", verbo, "--help"],
                               cwd=RAIZ, env=entorno(), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            ayudas[verbo] = r.stdout if r.returncode == 0 else ""
            if r.returncode != 0:
                malas.append(f"los documentos mandan `actaira {verbo}` y ese verbo no existe")
        for bandera in _re2.findall(r"(--[a-z-]+)", resto):
            if ayudas[verbo] and bandera not in ayudas[verbo]:
                malas.append(f"los documentos mandan `actaira {verbo} {bandera}` "
                             f"y ese verbo no acepta esa bandera")
    _afirma(not malas, "ordenes que no existen:\n  " + "\n  ".join(sorted(set(malas))))
    reg.append(f"las {len(citadas)} ordenes que esos documentos mandan teclear existen, "
               f"con sus banderas ({len(ayudas)} verbos)")

    # Y QUE LA DOCUMENTACION INGLESA GLOSE CADA PALABRA CASTELLANA QUE MANDA
    # TECLEAR.
    #
    # Los verbos, las banderas y los valores son palabras castellanas, y se
    # quedan asi: el motor emite ESE MISMO vocabulario dentro de los documentos
    # que produce, asi que dos pasadas de lo mismo se comparan linea a linea.
    # Un juego de nombres ingleses seria DOS nombres para un verbo, que es el
    # fallo con el que este arbol ha tropezado cuatro veces -- los roles, la
    # lista blanca de banderas, la tabla de vistas y las cifras publicadas.
    #
    # El precio de esa decision lo paga quien lee en ingles, y se paga con un
    # glosario. Lo que esta puerta impide es que el glosario se quede corto: el
    # dia que el manual ingles nombre un verbo nuevo sin glosarlo, ahi se queda
    # una palabra que quien lee no puede ni pronunciar.
    manual_en = (RAIZ / "docs" / "MANUAL.en.md").read_text(encoding="utf-8")
    _afirma("## The vocabulary is Spanish" in manual_en,
            "el manual ingles ya no trae el glosario del vocabulario castellano")
    glosario = manual_en.split("## The vocabulary is Spanish", 1)[1]
    for linea in glosario.splitlines():
        if linea.startswith('## '):
            glosario = glosario.split(linea, 1)[0]
            break
    glosados = set(_re2.findall(r"`([^`]+)`", glosario))

    sueltas: set[str] = set()
    for rel in ("README.en.md", "docs/MANUAL.en.md"):
        for linea in (RAIZ / rel).read_text(encoding="utf-8").splitlines():
            if "actaira" not in linea:
                continue
            sueltas |= {v for v in _re2.findall(r"actaira(?:-api)? ([a-z]+)", linea)
                        if v != "api"}
            sueltas |= set(_re2.findall(r"(--[a-z-]+)", linea))
    faltan_glosa = sorted(x for x in sueltas if x not in glosados)
    _afirma(not faltan_glosa,
            f"la documentacion inglesa manda teclear palabras castellanas que el "
            f"glosario no explica: {faltan_glosa}")

    # Y EL GLOSARIO DE VERBOS, COMPLETO CONTRA EL CLI.
    #
    # Comprobar solo los verbos que la documentacion CITA deja pasar el defecto
    # de siempre: el glosario dice «here is the whole first one» y se queda en
    # dieciseis de dieciocho sin que nada lo diga. Se quedo, el dia que nacio.
    #
    # Los verbos se leen de `actaira --help`, que es la unica lista que no
    # puede mentir sobre si misma.
    r = subprocess.run([PY, "-m", "actaira_motor.cli", "--help"], cwd=RAIZ,
                       env=entorno(), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    _afirma(r.returncode == 0, f"`actaira --help` salio {r.returncode}")
    dentro = _re2.search(r"\{([a-z,]+)\}", r.stdout)
    _afirma(dentro, "no se pueden leer los verbos de `actaira --help`")
    verbos_del_motor = set(dentro.group(1).split(","))
    sin_glosar = sorted(verbos_del_motor - glosados)
    _afirma(not sin_glosar,
            f"el glosario ingles dice ser el vocabulario entero y le faltan verbos "
            f"que el motor tiene: {sin_glosar}")

    reg.append(f"el glosario ingles cubre las {len(sueltas)} palabras castellanas "
               f"que esa documentacion manda teclear, y los "
               f"{len(verbos_del_motor)} verbos que el motor tiene")


def fase_identidad(reg: list[str]) -> None:
    """OIDC y papeles, contra el servidor LEVANTADO.

    Las pruebas de unidad del verificador de testigos pasarian aunque el
    servidor no lo llamara: lo que falla en estos casos casi nunca es la
    comprobacion, es el CABLEADO. Le paso a la vigilancia -- el paquete estaba
    escrito, probado y `main` le pasaba `nil` -- asi que aqui se levanta el
    binario y se le habla.

    El emisor es un doble local: una clave RSA de este proceso. Eso demuestra
    que el servidor verifica firmas, reclamaciones y papeles, y no que hable
    con un proveedor concreto: un doble emite lo que quien lo escribio creia
    que emite un proveedor, asi que esta de acuerdo con el verificador por
    construccion.

    De eso se ocupa `identidad_real`, que levanta un Keycloak y le habla. Esta
    fase se queda porque es RAPIDA y no necesita docker: cubre los casos de
    ataque -- `alg:none`, caducado, otra audiencia -- que exigen forjar
    testigos, y un proveedor de verdad no forja testigos malos a peticion.
    """
    if not shutil.which("go"):
        raise Omitida("`go` no esta en el PATH")
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
    except ImportError:
        raise Omitida("falta `cryptography` para firmar los testigos") from None

    import base64
    import json as _json
    import secrets
    import socket
    from datetime import datetime, timedelta, timezone

    def b64(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        for quien in ("acme", "beta"):
            (t / "clientes" / quien).mkdir(parents=True)
            shutil.copytree(FIXTURE, t / "clientes" / quien / "trabajo")

        clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        publica = clave.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        emisor = t / "emisor.json"
        emisor.write_text(_json.dumps(
            {"iss": "https://idp.local/pruebas", "aud": "actaira",
             "claves": {"k1": publica}}), encoding="utf-8")
        os.chmod(emisor, 0o600)

        cred = t / "cred.json"
        cred.write_text(_json.dumps({"est-" + secrets.token_urlsafe(24): "acme"}),
                        encoding="utf-8")
        os.chmod(cred, 0o600)

        exe = lanzador_del_motor(t)
        binario = t / ("api.exe" if os.name == "nt" else "api")
        r = subprocess.run(["go", "build", "-o", str(binario), "./cmd/actaira-api"],
                           cwd=RAIZ / "plataforma", capture_output=True, text=True)
        _afirma(r.returncode == 0, f"no compila el servidor: {r.stderr[-800:]}")

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            puerto = s.getsockname()[1]
        base = f"http://127.0.0.1:{puerto}"

        env = dict(os.environ)
        if os.name == "nt":
            env["ACTAIRA_PERMISOS_AFIRMADOS_POR_EL_OPERADOR"] = "1"
        proceso, dijo = arrancar_servidor(
            [str(binario), "--clientes", str(t / "clientes"),
             "--credenciales", str(cred), "--emisor", str(emisor),
             "--motor", str(exe), "--escucha", f"127.0.0.1:{puerto}",
             "--revisar-cada", "0"],
            cwd=RAIZ / "plataforma", env=env, registro=t / "servidor.log")
        try:
            vivo = False
            for _ in range(60):
                if proceso.poll() is not None:
                    raise AssertionError(
                        f"el servidor murio: {dijo(1200)}")
                try:
                    urllib.request.urlopen(base + "/salud", timeout=1).read()
                    vivo = True
                    break
                except (urllib.error.URLError, OSError):
                    time.sleep(0.25)
            _afirma(vivo, "el servidor no respondio a /salud")

            ahora = datetime.now(timezone.utc)

            def testigo(cliente="acme", roles=("admin",), **extra):
                cuerpo = {"iss": "https://idp.local/pruebas", "aud": "actaira",
                          "sub": "prueba@local",
                          "exp": int((ahora + timedelta(hours=1)).timestamp()),
                          "iat": int((ahora - timedelta(minutes=1)).timestamp()),
                          "actaira_cliente": cliente, "roles": list(roles)}
                cuerpo.update(extra)
                cab = b64(_json.dumps({"alg": "RS256", "typ": "JWT",
                                       "kid": "k1"}).encode())
                cue = b64(_json.dumps(cuerpo).encode())
                firma = clave.sign(f"{cab}.{cue}".encode(),
                                   padding.PKCS1v15(), hashes.SHA256())
                return f"{cab}.{cue}.{b64(firma)}"

            def llamar(metodo, ruta, tok, datos=None, cabeceras=None):
                pet = urllib.request.Request(
                    base + ruta, data=datos, method=metodo,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {tok}", **(cabeceras or {})})
                try:
                    with urllib.request.urlopen(pet, timeout=240) as resp:
                        return resp.status
                except urllib.error.HTTPError as e:
                    return e.code

            perfil = _json.dumps({"roles": ["proveedor"], "alto_riesgo": "si",
                                  "via_anexo": "anexo_iii",
                                  "fecha": "2027-12-02"}).encode()
            leer = "/v1/clientes/acme/noconformidades"
            plan = "/v1/clientes/acme/plan"

            casos = [
                ("admin observa lo suyo", "POST", plan, testigo(), perfil, 200),
                ("lectura NO observa", "POST", plan,
                 testigo(roles=("lectura",)), perfil, 403),
                ("lectura SI lee", "GET", leer,
                 testigo(roles=("lectura",)), None, 200),
                ("sin papeles, nada", "GET", leer, testigo(roles=()), None, 403),
                ("papel inventado, nada", "GET", leer,
                 testigo(roles=("root",)), None, 403),
                ("acme NO lee beta", "GET", "/v1/clientes/beta/noconformidades",
                 testigo(), None, 401),
                ("caducado", "GET", leer,
                 testigo(exp=int((ahora - timedelta(hours=2)).timestamp())), None, 401),
                ("otra audiencia", "GET", leer,
                 testigo(aud="otro-servicio"), None, 401),
            ]
            malos = []
            for nombre, metodo, ruta, tok, datos, esperado in casos:
                salio = llamar(metodo, ruta, tok, datos)
                if salio != esperado:
                    malos.append(f"{nombre}: se esperaba {esperado} y salio {salio}")

            # El fallo mas facil de cometer y el mas dificil de ver.
            salio = llamar("POST", plan, testigo(roles=("lectura",)), perfil,
                           {"X-Roles": "admin", "X-Actaira-Cliente": "beta",
                            "X-Tenant-Id": "beta", "X-User-Roles": "admin"})
            if salio != 403:
                malos.append(f"unas cabeceras de roles dieron permisos: {salio}")

            _afirma(not malos, "identidad:\n  " + "\n  ".join(malos))
            reg.append(f"OIDC contra el servidor levantado: {len(casos) + 1} casos, "
                       f"papeles, aislamiento entre clientes y cabeceras ignoradas")
            reg.append("  (el emisor es un doble local; contra uno de verdad "
                       "lo prueba la fase `identidad_real`)")
        finally:
            parar_servidor(proceso)

def fase_identidad_real(reg: list[str]) -> None:
    """Lo mismo que `identidad`, pero contra un proveedor que no escribimos.

    La fase anterior firma los testigos con una clave de su propio proceso, asi
    que el emisor y el verificador estan de acuerdo POR CONSTRUCCION: el doble
    emite lo que quien lo escribio creia que emite un proveedor. Aqui el
    testigo lo firma un Keycloak de verdad -- certificado por la OpenID
    Foundation, levantado en un contenedor -- y las claves se leen de su juego
    publicado, no se escriben a mano.

    No hacen falta credenciales de nadie. Eso era lo que parecia bloquear esto,
    y no lo era: el proveedor se levanta aqui.

    Se OMITE si no hay docker, con su motivo, en vez de contarse como aprobada.
    """
    try:
        from cryptography.hazmat.primitives import serialization  # noqa: F401
    except ImportError:
        raise Omitida("falta `cryptography` para leer el juego de claves") from None
    if not shutil.which("go"):
        raise Omitida("`go` no esta en el PATH")

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import idp

    motivo = idp.disponible()
    if motivo:
        raise Omitida(f"{motivo}; sin el, el unico emisor es el doble local")

    import json as _json
    import secrets
    import socket

    try:
        base_idp, lo_arranque_yo = idp.levantar()
    except idp.NoSePuede as e:
        raise Omitida(str(e)) from None

    try:
        idp.configurar(base_idp)
        tok_ana = idp.testigo(base_idp, "ana")
        tok_beto = idp.testigo(base_idp, "beto")
        conf = idp.emisor(base_idp)

        cab = idp.cabecera(tok_ana)
        cla = idp.reclamaciones(tok_ana)

        # Lo que el doble no podia ensenar, comprobado como PROPIEDAD y no como
        # curiosidad: si algun dia Keycloak deja de mandar `aud` como lista,
        # esta puerta lo dice en vez de seguir pasando por otro camino.
        _afirma(isinstance(cla.get("aud"), list) and "actaira" in cla["aud"],
                f"se esperaba `aud` como LISTA con actaira dentro, y vino {cla.get('aud')!r}")
        _afirma(cab.get("kid") in conf["claves"],
                "el `kid` del testigo no esta en el juego de claves publicado")
        ajenos = [r for r in cla.get("roles", []) if r not in
                  ("lectura", "observacion", "remediacion", "admin")]
        _afirma(ajenos, "el proveedor no metio ningun rol propio: esta prueba ya "
                        "no comprueba que los roles desconocidos se ignoren")
        _afirma(cla.get("actaira_cliente") == "acme",
                f"el testigo no trae `actaira_cliente`: {cla.get('actaira_cliente')!r}")

        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            for quien in ("acme", "beta"):
                (t / "clientes" / quien).mkdir(parents=True)
                shutil.copytree(FIXTURE, t / "clientes" / quien / "trabajo")

            emisor = t / "emisor.json"
            emisor.write_text(_json.dumps(conf), encoding="utf-8")
            os.chmod(emisor, 0o600)
            cred = t / "cred.json"
            cred.write_text(_json.dumps({"est-" + secrets.token_urlsafe(24): "acme"}),
                            encoding="utf-8")
            os.chmod(cred, 0o600)

            exe = lanzador_del_motor(t)
            binario = t / ("api.exe" if os.name == "nt" else "api")
            r = subprocess.run(["go", "build", "-o", str(binario), "./cmd/actaira-api"],
                               cwd=RAIZ / "plataforma", capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            _afirma(r.returncode == 0, f"no compila el servidor: {r.stderr[-800:]}")

            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                puerto = s.getsockname()[1]
            base = f"http://127.0.0.1:{puerto}"

            env = dict(os.environ)
            if os.name == "nt":
                env["ACTAIRA_PERMISOS_AFIRMADOS_POR_EL_OPERADOR"] = "1"
            proceso, dijo = arrancar_servidor(
                [str(binario), "--clientes", str(t / "clientes"),
                 "--credenciales", str(cred), "--emisor", str(emisor),
                 "--motor", str(exe), "--escucha", f"127.0.0.1:{puerto}",
                 "--revisar-cada", "0"],
                cwd=RAIZ / "plataforma", env=env, registro=t / "servidor.log")
            try:
                vivo = False
                for _ in range(60):
                    if proceso.poll() is not None:
                        raise AssertionError(
                            f"el servidor murio: {dijo(1200)}")
                    try:
                        urllib.request.urlopen(base + "/salud", timeout=1).read()
                        vivo = True
                        break
                    except (urllib.error.URLError, OSError):
                        time.sleep(0.25)
                _afirma(vivo, "el servidor no respondio a /salud")

                def llamar(metodo, ruta, tok, datos=None, cabeceras=None):
                    pet = urllib.request.Request(
                        base + ruta, data=datos, method=metodo,
                        headers={"Content-Type": "application/json",
                                 "Authorization": f"Bearer {tok}",
                                 **(cabeceras or {})})
                    try:
                        with urllib.request.urlopen(pet, timeout=240) as resp:
                            return resp.status
                    except urllib.error.HTTPError as e:
                        return e.code

                perfil = _json.dumps({"roles": ["proveedor"], "alto_riesgo": "si",
                                      "via_anexo": "anexo_iii",
                                      "fecha": "2027-12-02"}).encode()
                leer_acme = "/v1/clientes/acme/noconformidades"
                leer_beta = "/v1/clientes/beta/noconformidades"

                casos = [
                    # Ana es de acme y solo tiene lectura, segun KEYCLOAK.
                    ("ana lee lo suyo", "GET", leer_acme, tok_ana, None, 200),
                    ("ana NO observa", "POST", "/v1/clientes/acme/plan",
                     tok_ana, perfil, 403),
                    ("ana NO lee beta", "GET", leer_beta, tok_ana, None, 401),
                    # Beto es de beta y tiene lectura y observacion.
                    ("beto lee lo suyo", "GET", leer_beta, tok_beto, None, 200),
                    ("beto observa lo suyo", "POST", "/v1/clientes/beta/plan",
                     tok_beto, perfil, 200),
                    ("beto NO lee acme", "GET", leer_acme, tok_beto, None, 401),
                    # Y un testigo del reino `master`, que es un testigo
                    # LEGITIMO del mismo proveedor emitido para otra cosa.
                    ("otro reino del mismo proveedor", "GET", leer_acme,
                     idp._admin(base_idp), None, 401),
                ]
                malos = []
                for nombre, metodo, ruta, tok, datos, esperado in casos:
                    salio = llamar(metodo, ruta, tok, datos)
                    if salio != esperado:
                        malos.append(f"{nombre}: se esperaba {esperado} y salio {salio}")

                # Las cabeceras siguen sin dar permisos, tambien con un testigo
                # que no escribimos nosotros.
                salio = llamar("POST", "/v1/clientes/acme/plan", tok_ana, perfil,
                               {"X-Roles": "admin", "X-Actaira-Cliente": "beta",
                                "X-Tenant-Id": "beta"})
                if salio != 403:
                    malos.append(f"unas cabeceras de roles dieron permisos: {salio}")

                _afirma(not malos, "identidad real:\n  " + "\n  ".join(malos))
                reg.append(f"Keycloak {idp.VERSION_LEGIBLE} REAL en contenedor: "
                           f"{len(casos) + 1} casos con testigos que NO escribio "
                           f"esta casa, claves leidas de su JWKS")
                reg.append(f"  aud vino como lista {cla['aud']}, y con "
                           f"{len(ajenos)} roles del propio proveedor que se ignoran")
                reg.append("  (Entra ID sigue sin probarse: `iss` con inquilino, "
                           "`oid` en vez de `sub`, roles en `wids`)")
            finally:
                parar_servidor(proceso)
    finally:
        if lo_arranque_yo:
            idp.parar()

# Las pruebas que cambian de respuesta segun el sistema. No son todas: son las
# que YA cazaron un defecto que solo se veia desde el otro lado.
#
#   test_conectores   D-94: `chmod 0600` sobre un directorio le quita el
#                     permiso de entrar, asi que el conector de git quedaba
#                     roto en todo POSIX. Cinco pruebas verdes en Windows.
#   test_entorno      D-93: el extra `dev` no declaraba `pyyaml`. Verde en
#                     Windows porque el interprete lo traia por otra via.
#   test_portabilidad finales de linea, rutas y permisos.
SENSIBLES_AL_SISTEMA = ("test_conectores.py", "test_entorno.py",
                        "test_portabilidad.py")


def fase_matriz(reg: list[str]) -> None:
    """Que la puerta se corra en DOS sistemas, y que no deje de correrse.

    B-004 no era un hueco de medida, era uno de proceso: todo lo que esta
    puerta mide se media en un solo sistema, y los dos defectos que solo se
    ven desde el otro llevaban meses invisibles. La matriz de integracion
    continua es el arreglo, pero un fichero de flujo de trabajo que nadie ha
    ejecutado es una promesa, no una comprobacion. Asi que esta fase hace dos
    cosas distintas:

      1. AFIRMA sobre el fichero de la matriz. Si alguien le quita un sistema,
         o afloja el `--sin-omitir`, o deja de exigir cero saltadas bajo el
         detector de carreras, esto se pone rojo. Es lo que impide que B-004
         se reabra por edicion.
      2. Si desde aqui se alcanza un SEGUNDO sistema -- WSL, en una maquina
         Windows -- corre en el las pruebas sensibles al sistema de verdad. Si
         no se alcanza, se OMITE con el motivo, que es lo que esta casa hace
         con lo que no puede medir.

    Lo segundo es una MUESTRA y se dice: la suite entera en los dos sistemas es
    trabajo de la integracion continua, no de la maquina de quien desarrolla.
    """
    try:
        import yaml
    except ImportError:
        raise Omitida("falta `yaml` para leer el fichero de la matriz") from None

    flujo = RAIZ / ".github" / "workflows" / "ci.yml"
    _afirma(flujo.exists(), f"no existe {flujo}: sin el, nadie corre esto en dos sistemas")
    doc = yaml.safe_load(flujo.read_text(encoding="utf-8"))
    crudo = flujo.read_text(encoding="utf-8")

    tareas = doc.get("jobs", {})
    _afirma("puerta" in tareas, "el flujo no tiene la tarea `puerta`")
    estrategia = tareas["puerta"].get("strategy", {})
    matriz = estrategia.get("matrix", {})

    sistemas = matriz.get("sistema", [])
    faltan = [s for s in ("ubuntu-latest", "windows-latest") if s not in sistemas]
    _afirma(not faltan, f"la matriz no corre en {faltan}. Los dos defectos que "
                        f"cerraron B-004 solo se veian uno en cada sistema")

    _afirma(estrategia.get("fail-fast") is False,
            "sin `fail-fast: false` el primer rojo cancela el otro sistema, que "
            "es justo el dato por el que existe la matriz")

    pitones = [str(v) for v in matriz.get("python", [])]
    _afirma(len(pitones) >= 2,
            f"la matriz prueba una sola version de Python ({pitones}): "
            f"`pyproject.toml` promete mas de una")

    _afirma("--sin-omitir" in crudo,
            "el flujo no corre la puerta con `--sin-omitir` en ninguna parte: "
            "sin eso, una fase que deje de poder medirse se calla y el resumen "
            "sigue diciendo «0 en rojo»")
    _afirma("-race" in crudo,
            "el flujo no corre las pruebas de la plataforma bajo el detector de "
            "carreras, que es lo que B-004 pedia")
    _afirma("se saltaron" in crudo and "exit 1" in crudo,
            "el flujo no falla cuando se saltan pruebas en un agente donde no "
            "falta nada: una prueba que se salta no es una que pasa")

    reg.append(f"matriz declarada: {len(sistemas)} sistemas x {len(pitones)} "
               f"versiones de Python, sin omisiones en Linux y con -race")

    # --- y ahora, el otro sistema de verdad, si se alcanza ------------------
    #
    # ESTA FASE MIDE DOS COSAS, Y LA SEGUNDA NO SIEMPRE SE PUEDE MEDIR.
    #
    # Lo de arriba -- que el flujo declare los dos sistemas y no afloje -- se
    # comprobo y paso. Correr ADEMAS el otro sistema desde aqui es un extra que
    # depende de la maquina, y en un agente de integracion continua no depende:
    # ahi el otro sistema lo corre la propia matriz, en su propio trabajo.
    #
    # La primera version levantaba `Omitida` en ese caso, y con `--sin-omitir`
    # -- que es como corre la integracion continua en Linux -- eso ponia la
    # puerta ROJA por no poder hacer algo que ahi no hay que hacer. Una puerta
    # que se pone roja donde el producto esta bien ensena a apagar la puerta.
    #
    # Asi que no se omite: se dice en una linea que esa mitad no se midio y
    # por que. Lo que NO se hace es callarlo.
    def _sin_segundo_sistema(motivo: str) -> None:
        reg.append(f"  la otra mitad no se midio aqui: {motivo}")

    if os.name != "nt":
        _sin_segundo_sistema("desde este sistema no se alcanza otro; en la "
                             "integracion continua lo cubre la propia matriz")
        return
    if not shutil.which("wsl.exe"):
        _sin_segundo_sistema("no hay WSL instalado")
        return
    # QUE `wsl.exe` EXISTA NO ES QUE HAYA UN LINUX DETRAS.
    #
    # El agente de Windows de la integracion continua trae el ejecutable y CERO
    # distribuciones, asi que cualquier orden devuelve el texto de ayuda de
    # `wsl --install`. La primera version de esta fase lo tomaba por la salida
    # de pytest y se ponia ROJA por no reconocerla, que es poner en rojo el
    # producto por como esta montado el agente.
    sonda = subprocess.run(["wsl.exe", "-e", "true"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=120)
    if sonda.returncode != 0:
        _sin_segundo_sistema("hay `wsl.exe` pero ninguna distribucion detras")
        return

    ruta = str(RAIZ).replace("\\", "/")
    unidad, resto = ruta[0].lower(), ruta[2:]
    dentro = f"/mnt/{unidad}{resto}"
    guion = (
        f'V=$HOME/.venvs/actaira; '
        f'[ -x $V/bin/python ] || {{ echo FALTA_ENTORNO; exit 9; }}; '
        f'cd "{dentro}" || {{ echo NO_LLEGA_AL_ARBOL; exit 9; }}; '
        f'PYTHONPATH="{dentro}/motor/src" $V/bin/python -m pytest '
        + " ".join(f"motor/tests/{n}" for n in SENSIBLES_AL_SISTEMA)
        + ' -q 2>&1 | tail -4'
    )
    r = subprocess.run(["wsl.exe", "-e", "bash", "-lc", guion],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    salida = (r.stdout or "").replace("\x00", "").strip()
    if "FALTA_ENTORNO" in salida:
        _sin_segundo_sistema(
            "hay WSL sin entorno preparado. Una vez: `wsl -e bash -lc "
            "'python3 -m venv $HOME/.venvs/actaira && "
            "$HOME/.venvs/actaira/bin/pip install -e \"<el arbol>[dev]\"'`")
        return
    if "NO_LLEGA_AL_ARBOL" in salida:
        _sin_segundo_sistema(f"WSL no ve el arbol en {dentro}")
        return

    ultima = salida.splitlines()[-1] if salida else ""
    _afirma("failed" not in ultima and "error" not in ultima.lower(),
            f"las pruebas sensibles al sistema fallan en el OTRO sistema:\n"
            f"  {salida[-900:]}")
    _afirma("passed" in ultima,
            f"no se reconoce el resultado del otro sistema: {ultima!r}")
    reg.append(f"y corridas de verdad en el otro sistema (WSL): {ultima}")
    reg.append("  (es una MUESTRA -- las tres que ya cazaron un defecto de "
               "sistema --, no la suite entera)")



def fase_navegador(reg: list[str]) -> None:
    """El panel abierto en un navegador de verdad: las once vistas, pulsadas.

    Vive en `herramientas/navegador.py` porque necesita Playwright y un
    Chromium, y esta fase es la unica de la puerta que depende de algo que hay
    que descargar. Si no esta, se declara OMITIDA con el motivo -- y en la
    integracion continua, donde se corre con `--sin-omitir`, una omision es un
    rojo, que es exactamente lo que se quiere: el dia que Chromium deje de
    instalarse, el sintoma no puede volver a quedarse sin puerta en silencio.

    Es la unica fase que EJECUTA el JavaScript de las dos pantallas. Las demas
    leen el fichero; esta lo corre.

    Y son dos porque la consola tampoco lo tenia, con el mismo resultado: los
    tres `<main>` compartian id con su boton de pestana, conmutar de vista
    escondia las pestanas en vez de los paneles, y dos de las tres vistas -- el
    cuestionario entero y la declaracion de aplicabilidad -- no se podian
    alcanzar nunca. Veinte pruebas en verde, cero errores de consola, y todas
    leen el fichero. La leccion que dejo el panel se aplico al panel y no al
    artefacto de al lado.
    """
    import navegador
    navegador.puerta(reg)
    # La consola NO necesita la pila: es un fichero suelto que se abre con
    # `file://`, y eso es ademas la mitad de lo que promete.
    navegador.consola(reg)


def fase_fuentes(reg: list[str]) -> None:
    """Que las paginas no le pidan NADA a un tercero.

    Las tres traian las tipografias con un `<link>` a `fonts.googleapis.com`, y
    eso rompia tres cosas a la vez: el README promete que el panel es un solo
    fichero con cero peticiones de red, la consola existe para leerse sin
    conexion, y cada carga le contaba a Google la direccion IP de quien abre el
    expediente de cumplimiento de un cliente -- que en una herramienta del
    Reglamento de IA es una transferencia a un tercero sin declarar, con
    jurisprudencia europea sobre ese mismo `<link>`.

    Lo cazo la fase `navegador` el dia que se le pidio afirmar lo que el README
    ya decia. Esta fase lo sujeta MAS BARATO y en los tres artefactos: el
    navegador solo abre el panel, y la consola y la portada no los abre nadie.
    """
    r = subprocess.run([PY, str(RAIZ / "herramientas" / "fuentes.py"), "--comprobar"],
                       cwd=RAIZ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    _afirma(r.returncode == 0, f"tipografias: {r.stdout}{r.stderr}")
    reg.append(r.stdout.strip().splitlines()[-1])

    # Y que NINGUNA pagina construida CARGUE nada de fuera. Se mira el
    # artefacto servido y no la plantilla: lo que le llega a un cliente es el
    # artefacto.
    #
    # Cargar no es enlazar. Un `<a href>` a GitHub es un enlace: no se pide
    # nada hasta que alguien lo pulsa, y esa es su funcion. Lo que no puede
    # haber es algo que el navegador se traiga SOLO al abrir la pagina --
    # `<link rel=stylesheet>`, `<script src>`, `<img src>`, una `@import` o una
    # `url()` de CSS -- porque eso ocurre sin que nadie lo pida y le dice a un
    # tercero que alguien abrio esta pagina.
    #
    # La primera version de esta afirmacion no distinguia las dos cosas y se
    # puso roja por los enlaces al repositorio. Una puerta que confunde un
    # enlace con una peticion obliga a quitar los enlaces, que era justamente
    # el defecto anterior de la portada.
    import re as _ref
    CARGAS = (
        _ref.compile(r'<(?:link|script|img|iframe|source|video|audio)\b[^>]*'
                     r'\b(?:src|href)="(https?:)?//([^"]+)"', _ref.I),
        _ref.compile(r'@import\s+(?:url\()?["\']?(https?:)?//([^"\')]+)', _ref.I),
        _ref.compile(r'url\(\s*["\']?(https?:)?//([^"\')]+)', _ref.I),
    )
    paginas = ["panel/panel.html", "plataforma/api/panel.html", "consola/consola.html",
               "sitio/tipografias.css",
               "sitio/index.html", "sitio/en/index.html", "sitio/fr/index.html",
               "sitio/pt/index.html", "sitio/it/index.html", "sitio/de/index.html"]
    malas = []
    for rel in paginas:
        f = RAIZ / rel
        _afirma(f.is_file(), f"{rel} no existe y esta en la lista")
        texto = f.read_text(encoding="utf-8")
        for patron in CARGAS:
            for _, donde in patron.findall(texto):
                malas.append(f"{rel} -> {donde[:60]}")
    _afirma(not malas,
            f"hay paginas que CARGAN cosas de un tercero al abrirse: "
            f"{sorted(set(malas))[:5]}. Estas paginas tienen que poder abrirse sin "
            f"conexion, y lo que se traigan solas le dice a un tercero quien las abre")
    reg.append(f"las {len(paginas)} paginas construidas no cargan nada de ningun "
               f"tercero al abrirse")

FASES: dict[str, Callable[[list[str]], None]] = {
    "catalogo": fase_catalogo,
    "consola": fase_consola,
    "panel": fase_panel,
    "portada": fase_portada,
    "suite": fase_suite,
    "articulo50": fase_articulo50,
    "sello": fase_sello,
    "plan": fase_plan,
    "anexos": fase_anexos,
    "formularios": fase_formularios,
    "soa": fase_soa,
    "vigilancia": fase_vigilancia,
    "caducidad": fase_caducidad,
    "sarif": fase_sarif,
    "contrato": fase_contrato,
    "go": fase_go,
    "api": fase_api,
    "paquete": fase_paquete,
    "identidad": fase_identidad,
    "identidad_real": fase_identidad_real,
    "matriz": fase_matriz,
    "instalacion": fase_instalacion,
    "documentacion": fase_documentacion,
    "navegador": fase_navegador,
    "fuentes": fase_fuentes,
}


def correr(nombres: list[str], sin_omitir: bool = False) -> int:
    resultados: list[Resultado] = []
    for nombre in nombres:
        print(f"--- {nombre} " + "-" * max(0, 66 - len(nombre)), flush=True)
        lineas: list[str] = []
        try:
            FASES[nombre](lineas)
            resultados.append(Resultado(nombre, "ok", lineas=lineas))
        except Omitida as e:
            resultados.append(Resultado(nombre, "omitida", str(e)))
            print(f"  OMITIDA: {e}", flush=True)
            continue
        except Exception as e:                      # noqa: BLE001 - se informa entera
            detalle = f"{type(e).__name__}: {e}"
            resultados.append(Resultado(nombre, "fallo", detalle, lineas))
            for linea in lineas:
                print(f"  {linea}", flush=True)
            print(f"  FALLO: {detalle}", flush=True)
            # LA TRAZA DE LO INESPERADO, ENTERA.
            #
            # Un `AssertionError` de esta casa se explica solo: el mensaje dice
            # que se esperaba y que salio. Una excepcion que no escribio nadie
            # -- un `ConnectionResetError`, un `KeyError` -- no dice nada sin su
            # traza, y aqui se imprimia UNA linea con el tipo y el mensaje.
            #
            # Eso paso de verdad: la fase `api` salio roja con
            # `ConnectionResetError` y el rojo no decia en que peticion, asi
            # que no se podia distinguir «el servidor se cayo al arrancar» de
            # «se cayo bajo los topes de concurrencia». Un rojo que no se puede
            # localizar se acaba leyendo como ruido, y un ruido que se ignora
            # es una puerta apagada.
            if not isinstance(e, AssertionError):
                print("".join(f"  {x}" for x in
                              traceback.format_exception(e)), end="", flush=True)
            continue
        for linea in lineas:
            print(f"  {linea}", flush=True)

    ok = [r for r in resultados if r.estado == "ok"]
    fallos = [r for r in resultados if r.estado == "fallo"]
    omitidas = [r for r in resultados if r.estado == "omitida"]
    print("=" * 72)
    print(f"{len(ok)} verdes | {len(fallos)} en rojo | {len(omitidas)} omitidas")
    for r in omitidas:
        print(f"  omitida  {r.nombre}: {r.detalle}")
    for r in fallos:
        print(f"  ROJO     {r.nombre}: {r.detalle.splitlines()[0][:150]}")
    # Una fase omitida no suma al verde, pero tampoco se convierte en rojo: lo
    # que no se pudo medir se dice, y quien lee decide. Lo que no se hace nunca
    # es contarla como aprobada, que es como un verde deja de significar algo.
    #
    # SALVO CON `--sin-omitir`, Y ESE ES EL PUNTO.
    #
    # En la maquina de quien desarrolla, omitir por falta de `docker` o de
    # `node` es razonable. En una maquina de integracion continua, donde TODO
    # esta instalado a proposito, una omision no significa «aqui no se puede»:
    # significa que algo dejo de estar disponible y nadie se entero. Sin esta
    # bandera, la forma mas facil de que una fase deje de medir para siempre es
    # que empiece a omitirse, porque el resumen sigue diciendo «0 en rojo».
    if sin_omitir and omitidas:
        print("y se pidio --sin-omitir: en esta maquina una omision es un fallo")
        return 1
    return 1 if fallos else 0


def main() -> int:
    p = argparse.ArgumentParser(description="La puerta de aceptacion de Actaira.")
    p.add_argument("fases", nargs="*", help="las fases a correr; por omision, todas")
    p.add_argument("--listar", action="store_true", help="los nombres de las fases")
    p.add_argument("--sin-omitir", action="store_true",
                   help="una fase omitida cuenta como fallo. Para la integracion "
                        "continua, donde todo esta instalado y una omision "
                        "significa que algo se rompio, no que no se pueda medir")
    a = p.parse_args()
    if a.listar:
        for nombre in FASES:
            print(nombre)
        return 0
    nombres = a.fases or list(FASES)
    desconocidas = [n for n in nombres if n not in FASES]
    if desconocidas:
        p.error(f"fases desconocidas: {desconocidas}. Las que hay: {list(FASES)}")
    return correr(nombres, sin_omitir=a.sin_omitir)


if __name__ == "__main__":
    raise SystemExit(main())
