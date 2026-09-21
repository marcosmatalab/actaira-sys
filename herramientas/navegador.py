r"""El panel, corrido en un NAVEGADOR de verdad, contra la API de verdad.

POR QUE ESTE FICHERO EXISTE
-----------------------------
La quinta pasada adversarial encontro diez defectos en el panel y la portada, y
el mas grave escondia siete de las once vistas del producto. Ninguna de las
cuatro pasadas anteriores podia encontrarlo, y no por falta de rigor: **el panel
no tenia una sola prueba que ejecutara su JavaScript**. Un `ReferenceError` que
rompia las once vistas paso la reproducibilidad, la accesibilidad, las claves de
texto y el contrato de campos sin que ninguna se inmutara.

Las puertas que salieron de aquella pasada -- `test_toda_vista_es_alcanzable`,
`pintarBotones` recorriendo `RUTAS`, el texto que se pinta y no se escribe al
arrancar -- sujetan la CAUSA, que es lo que se puede leer sin navegador. Este
fichero sujeta el SINTOMA, que es lo unico que de verdad demuestra que la
pantalla funciona: abrirla, pulsar los once botones y mirar lo que sale.

QUE AFIRMA, Y QUE NO
----------------------
Afirma que las once vistas se pueden PULSAR, que pulsarlas pide algo al motor
DE VERDAD -- y no que la pantalla siga llena de lo anterior --, que cada una
trae documento y lo pinta como filas o dice por que no lo pinta, que el idioma
del documento se deriva del de la pantalla, y que la consola del navegador no
escribe ni un error.

No afirma que lo que pone en esas filas sea correcto: eso lo miden las pruebas
del motor, que es donde vive el juicio. Aqui se mide el transporte hasta el ojo.

Y no afirma que toda vista traiga filas. Un documento puede venir legitimamente
vacio -- vencimientos un dia tranquilo no tiene nada que avisar -- y exigirle
filas obligaria a fabricarlas, que es lo contrario de lo que hace esta casa.

CUATRO MODOS, UN SOLO RECORRIDO
---------------------------------
    python herramientas/navegador.py --puerta      afirma, y sale rojo si no
    python herramientas/navegador.py --capturas    las imagenes del README
    python herramientas/navegador.py --gif         el recorrido de 30 s
    python herramientas/navegador.py --latencias   lo que tarda cada verbo

Los cuatro levantan la MISMA pila -- el servidor Go compilado, el motor como
proceso aparte, el cliente de ejemplo -- porque una captura de pantalla hecha
contra datos inventados es publicidad, y este producto tiene una negativa
escrita contra eso.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import todo  # noqa: E402  - la pila se levanta con las MISMAS piezas que la puerta

RAIZ = todo.RAIZ
SALIDA = RAIZ / "docs" / "imagenes"

# Las once vistas, en el orden en que un cliente las recorre: primero que te
# ata, luego que se comprobo leyendo bytes, luego lo que hay que preguntarte, y
# al final el expediente. NO es una lista escrita a mano de las de esta casa:
# `--puerta` la compara con `RUTAS` y falla si sobra o falta alguna.
RECORRIDO = ["apl", "plan", "comp", "preg", "soa", "anx", "ev", "vig", "venc", "nc", "rev"]

# La categoria que ensena las once. Las otras dos ensenan un subconjunto a
# proposito, y eso lo comprueba `test_toda_vista_es_alcanzable`.
CATEGORIA_COMPLETA = "empresa"


def vistas_de_rutas() -> list[str]:
    """Las vistas que el panel declara, leidas del JavaScript que se sirve.

    Se leen del fichero y no se escriben aqui por la misma razon por la que
    `pintarBotones` recorre `RUTAS`: dos listas de vistas en dos sitios acaban
    diciendo cosas distintas, y la que se queda corta esconde producto.
    """
    js = (RAIZ / "panel" / "plantilla" / "logica.js").read_text(encoding="utf-8")
    bloque = js.split("const RUTAS = {", 1)[1].split("\n};", 1)[0]
    return [ln.split(":", 1)[0].strip()
            for ln in bloque.splitlines()
            if ln.strip() and not ln.strip().startswith("//") and ":" in ln
            and ln.strip()[0].isalpha()]


@contextmanager
def pila():
    """Levanta la API de verdad sobre el repositorio de ejemplo, y la para."""
    if not shutil.which("go"):
        raise todo.Omitida("`go` no esta en el PATH")
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "clientes" / "acme").mkdir(parents=True)
        shutil.copytree(todo.FIXTURE, t / "clientes" / "acme" / "trabajo")
        token = "demo-" + secrets.token_urlsafe(24)
        cred = t / "cred.json"
        cred.write_text(json.dumps({token: "acme"}), encoding="utf-8")
        os.chmod(cred, 0o600)
        motor_exe = todo.lanzador_del_motor(t)

        binario = t / ("actaira-api.exe" if os.name == "nt" else "actaira-api")
        r = subprocess.run(["go", "build", "-o", str(binario), "./cmd/actaira-api"],
                           cwd=RAIZ / "plataforma", capture_output=True, text=True)
        if r.returncode != 0:
            raise AssertionError(f"no compila el servidor: {r.stderr[-1500:]}")

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            puerto = s.getsockname()[1]
        base = f"http://127.0.0.1:{puerto}"

        env = dict(os.environ)
        if os.name == "nt":
            env["ACTAIRA_PERMISOS_AFIRMADOS_POR_EL_OPERADOR"] = "1"
        # Se arranca con la MISMA pieza que la puerta -- bitacora a un
        # fichero, nunca a un `PIPE` -- porque dos definiciones de «como se
        # levanta este servidor» acaban diciendo cosas distintas, y la que
        # diverge es la que nadie vuelve a mirar. El porque del fichero esta
        # escrito entero en `todo.arrancar_servidor`.
        proceso, dijo = todo.arrancar_servidor(
            [str(binario), "--clientes", str(t / "clientes"), "--credenciales", str(cred),
             "--motor", str(motor_exe), "--escucha", f"127.0.0.1:{puerto}",
             "--revisar-cada", "0"],
            cwd=RAIZ / "plataforma", env=env, registro=t / "servidor.log")

        try:
            vivo = False
            for _ in range(80):
                if proceso.poll() is not None:
                    raise AssertionError(
                        f"el servidor murio al arrancar:\n{dijo()}")
                try:
                    with urllib.request.urlopen(base + "/salud", timeout=1):
                        vivo = True
                    break
                except (urllib.error.URLError, OSError):
                    time.sleep(0.25)
            if not vivo:
                raise AssertionError("el servidor no respondio a /salud en 20 s")
            yield base, token
        finally:
            todo.parar_servidor(proceso)


class Pagina:
    """El panel abierto, con la consola del navegador vigilada.

    Los errores de consola se GUARDAN, no se imprimen y se olvidan: un
    `ReferenceError` que rompe once vistas no interrumpe la carga de la pagina,
    asi que sin recogerlos el recorrido entero sale verde con la pantalla rota.
    """

    def __init__(self, page, base: str, token: str) -> None:
        self.page = page
        self.base = base
        self.token = token
        self.errores: list[str] = []
        # El idioma en que la pagina PIDE el documento. Se mira en la cabecera
        # que sale por el cable y no en una variable del JavaScript: lo que
        # importa es lo que el motor recibe.
        self.idiomas_pedidos: list[str] = []
        page.on("pageerror", lambda e: self.errores.append(f"pageerror: {e}"))
        page.on("console", lambda m: self.errores.append(f"console.{m.type}: {m.text}")
                if m.type == "error" else None)
        page.on("request", lambda r: self.idiomas_pedidos.append(
            r.headers.get("accept-language", "")) if "/v1/clientes/" in r.url else None)

    def abrir(self) -> float:
        t0 = time.perf_counter()
        self.page.goto(self.base, wait_until="load")
        self.page.wait_for_selector("#conectar", state="visible")
        return (time.perf_counter() - t0) * 1000

    def conectar(self, cliente: str = "acme") -> None:
        self.page.fill("#servidor", self.base)
        self.page.fill("#cliente", cliente)
        self.page.fill("#credencial", self.token)
        self.page.click("#conectar")
        self.page.wait_for_function(
            "() => !document.querySelector('#desconectar').classList.contains('oculto')",
            timeout=30000)

    def perfil(self, rol: str = "proveedor", alto: str = "si",
               via: str = "anexo_iii") -> None:
        """Rellena el perfil como lo rellenaria un cliente de verdad.

        Sin esto, todas las preguntas del formulario se quedan en «sin
        responder» y el plan sale lleno de «no te ata» y «solo formulario»,
        que es una pantalla correcta y una captura inutil: ensena el producto
        contestando a nadie.
        """
        self.page.select_option("#rol", rol)
        self.page.select_option("#alto_riesgo", alto)
        self.page.select_option("#via_anexo", via)

    def arriba(self) -> None:
        """Al principio de la pagina, y esperar a que pare de moverse."""
        self.page.evaluate("() => window.scrollTo(0, 0)")
        self.page.wait_for_timeout(250)

    def mirar_respuesta(self) -> None:
        """Deja la respuesta en pantalla.

        Pulsar un boton de vista arrastra el scroll hasta el boton, que vive al
        final de la columna del formulario. La primera version del recorrido
        grababa treinta segundos del volcado de JSON del pie, que es justo lo
        que el producto NO es.
        """
        # De golpe y no `smooth`: un scroll suave son veinte fotogramas que
        # cambian entero, y en un GIF eso son megabytes por cada vez que se
        # mira la respuesta. Con salto seco el recorrido bajo de 16 a 6 MB.
        y = self.page.locator(".rejilla").bounding_box()["y"]
        self.page.evaluate(f"() => window.scrollTo(0, {y:.0f})")
        self.page.wait_for_timeout(250)

    def recortar(self, selector: str, destino: Path, alto: int = 900) -> None:
        """Una PANTALLA del elemento, no el elemento entero.

        `locator.screenshot()` captura el elemento completo, y la columna de la
        respuesta del cuestionario mide veinte mil pixeles de alto: noventa
        preguntas seguidas. Como imagen de un README eso no se ve, se scrollea.
        Lo que sirve es lo que cabe en una pantalla, encuadrado donde empieza
        la respuesta.
        """
        # `clip` va en coordenadas del DOCUMENTO, y solo las respeta con
        # `full_page`. Sin el, recortar despues de scrollear mezcla las dos
        # referencias y sale el trozo equivocado: la primera version de esto
        # devolvio la cabecera de la pagina con el eje X del panel derecho.
        self.arriba()
        caja = self.page.locator(selector).bounding_box()
        self.page.screenshot(path=str(destino), full_page=True, clip={
            "x": caja["x"], "y": caja["y"], "width": caja["width"],
            "height": min(alto, caja["height"])})

    def categoria(self, cual: str) -> None:
        self.page.click(f"#cats button[data-c='{cual}']")

    def idioma(self, cual: str) -> None:
        self.page.click(f"#idioma button[data-l='{cual}']")

    def tema(self, cual: str) -> None:
        self.page.click(f"#tema button[data-t='{cual}']")

    def pedir(self, verbo: str, plazo: int = 120000) -> dict:
        """Pulsa el boton de una vista y espera a que la pantalla la pinte."""
        boton = self.page.locator(f"#pedir-{verbo}")
        antes = len(self.idiomas_pedidos)
        t0 = time.perf_counter()
        boton.click()
        # El boton se desactiva mientras corre y se vuelve a activar al pintar.
        # Esperar a eso y no a un tiempo fijo es lo que hace que esto mida el
        # producto y no la paciencia de quien lo escribio.
        self.page.wait_for_function(
            f"() => document.querySelector('#pedir-{verbo}').disabled === false",
            timeout=plazo)
        ms = (time.perf_counter() - t0) * 1000
        # QUE EL CLIC HAYA PEDIDO ALGO, Y NO SOLO QUE LA PANTALLA ESTE LLENA.
        #
        # Si un boton no hiciera nada -- que es el defecto que escondio siete
        # vistas, y que ahora seria un enganche perdido en vez de un `disabled`
        # olvidado -- la pantalla seguiria ensenando las filas de la vista
        # ANTERIOR y todas las afirmaciones de abajo pasarian. Un recorrido que
        # mide la pantalla sin mirar el cable puede salir verde con un solo
        # boton funcionando.
        if len(self.idiomas_pedidos) <= antes:
            raise AssertionError(
                f"pulsar la vista {verbo!r} no provoco NI UNA peticion al motor: "
                f"la pantalla que se ve es la de la vista anterior")
        vacios = self.page.locator("#lineas .vacio")
        return {
            "verbo": verbo,
            "ms": round(ms),
            "filas": self.page.locator("#lineas .linea").count(),
            "sello": (self.page.locator("#sello").inner_text() or "").strip(),
            "error": (self.page.locator("#conexion-mal").inner_text() or "").strip(),
            "vacio": (vacios.first.inner_text() or "").strip() if vacios.count() else "",
            "crudo": len(self.page.locator("#crudo").inner_text() or ""),
        }


@contextmanager
def navegador(base: str, token: str, *, video: Path | None = None,
              ancho: int = 1400, alto: int = 900):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise todo.Omitida("`playwright` no esta instalado "
                           "(pip install playwright && playwright install chromium)") from e
    with sync_playwright() as p:
        try:
            navegador_ = p.chromium.launch()
        except Exception as e:                       # noqa: BLE001
            raise todo.Omitida(f"chromium no se puede lanzar aqui: {e}") from e
        contexto = navegador_.new_context(
            viewport={"width": ancho, "height": alto},
            device_scale_factor=2 if video is None else 1,
            record_video_dir=str(video) if video else None,
            record_video_size={"width": ancho, "height": alto} if video else None,
        )
        page = contexto.new_page()
        try:
            yield Pagina(page, base, token), contexto
        finally:
            contexto.close()
            navegador_.close()


def puerta(reg: list[str]) -> None:
    """Las once vistas, pulsadas de verdad. Es la fase `navegador` de la puerta."""
    textos_es = json.loads(
        (RAIZ / "panel" / "textos.json").read_text(encoding="utf-8"))["es"]
    declaradas = set(vistas_de_rutas())
    recorridas = set(RECORRIDO)
    if declaradas != recorridas:
        raise AssertionError(
            f"este recorrido y `RUTAS` no dicen las mismas vistas. "
            f"Sobran aqui: {sorted(recorridas - declaradas)}; "
            f"faltan aqui: {sorted(declaradas - recorridas)}")

    with pila() as (base, token):
        with navegador(base, token) as (pag, _):
            carga = pag.abrir()
            todo._afirma(not pag.errores,
                         f"la consola del navegador escribio errores al cargar: {pag.errores}")
            todo._afirma(carga < 3000, f"la pagina tardo {carga:.0f} ms en cargar")
            reg.append(f"la pagina carga en {carga:.0f} ms, sin errores de consola")

            pag.conectar()
            pag.categoria(CATEGORIA_COMPLETA)

            # Los once botones, VISIBLES y PULSABLES. Es el defecto D-108
            # entero: siete existian, se veian, y conservaban el `disabled` del
            # HTML para siempre.
            for verbo in RECORRIDO:
                b = pag.page.locator(f"#pedir-{verbo}")
                todo._afirma(b.is_visible(),
                             f"el boton de la vista {verbo!r} no se ve en la categoria "
                             f"{CATEGORIA_COMPLETA!r}")
                todo._afirma(b.is_enabled(),
                             f"el boton de la vista {verbo!r} se ve y NO se puede pulsar: "
                             f"es el defecto que escondio siete vistas")
            reg.append(f"las {len(RECORRIDO)} vistas se ven y se pueden pulsar")

            filas_totales = 0
            for r in (pag.pedir(v) for v in RECORRIDO):
                todo._afirma(not r["error"],
                             f"la vista {r['verbo']!r} contesto con error: {r['error']}")
                todo._afirma(r["sello"],
                             f"la vista {r['verbo']!r} no trajo esquema ni codigo: "
                             f"el motor no contesto un documento")
                # Y QUE SE PINTE, O QUE DIGA POR QUE NO.
                #
                # La afirmacion no es «toda vista trae filas»: un documento
                # puede venir legitimamente vacio -- vencimientos un dia
                # tranquilo no tiene nada que avisar -- y exigirle filas
                # obligaria a fabricarlas, que es lo contrario de lo que hace
                # esta casa. Lo que no puede pasar es que la pantalla se quede
                # con el volcado de JSON como unica respuesta, que es lo que
                # hacian ocho de las once vistas: el cuestionario son noventa
                # preguntas y salia como cuatrocientos kilobytes de JSON.
                #
                # Asi que: filas, o una frase que diga que no hay nada. Y nunca
                # la frase de antes de conectar, que aqui significaria que la
                # vista trajo documento y la pantalla no se entero.
                todo._afirma(r["filas"] > 0 or r["vacio"],
                             f"la vista {r['verbo']!r} trajo documento, pinto CERO filas y "
                             f"no dijo por que: solo quedan {r['crudo']} caracteres de "
                             f"JSON crudo")
                if not r["filas"]:
                    todo._afirma(r["vacio"] not in (textos_es["sin_datos"],
                                                    textos_es["sin_datos_conectado"]),
                                 f"la vista {r['verbo']!r} trajo documento y la pantalla "
                                 f"contesta con el texto de antes de pedirla: {r['vacio']!r}")
                if r["verbo"] == "ev":
                    vacio_de_almacen = r
                filas_totales += r["filas"]
                reg.append(f"  {r['verbo']:<5} {r['filas']:>3} filas  {r['ms']:>6} ms"
                           + ("" if r["filas"] else "   (vacio, y lo dice)"))
            reg.append(f"las {len(RECORRIDO)} vistas pintan filas ({filas_totales} en total)")

            # EL ALMACEN, OTRA VEZ, AHORA QUE `vig` LO HA ESCRITO.
            #
            # En el recorrido `ev` va ANTES que `vig`, asi que lo que se ve ahi
            # es el almacen VACIO -- que es el estado normal de un cliente el
            # primer dia y tiene que verse bien. Pero la rama interesante es la
            # otra: cadena, cabeza y recuentos. Pidiendola aqui se recorren las
            # dos, y de paso se comprueba desde la pantalla lo que la fase `api`
            # comprueba desde el cable: que la plataforma ESCRIBE evidencia.
            despues = pag.pedir("ev")
            todo._afirma(despues["filas"] > vacio_de_almacen["filas"],
                         f"despues de vigilar, el almacen ensena las mismas "
                         f"{despues['filas']} filas que cuando estaba vacio: o no se "
                         f"escribio evidencia, o la pantalla no ensena la cadena")
            texto = pag.page.locator("#lineas").inner_text()
            for falta in ("sha256:", textos_es["almacen_observaciones"]):
                todo._afirma(falta in texto,
                             f"el almacen escrito no ensena {falta!r} en pantalla")
            reg.append(f"el almacen: {vacio_de_almacen['filas']} fila vacio y "
                       f"{despues['filas']} con la cadena escrita, con su cabeza")

            # El idioma, que es donde estaba D-115 y D-116. Se recorren los
            # seis y se comprueba que no queda castellano suelto en la pantalla
            # ni `undefined` en ninguna fila.
            # LA REGLA DEL IDIOMA, ESCRITA UNA VEZ Y COMPROBADA AQUI.
            #
            # Pantalla en castellano -> documento en castellano. Pantalla en
            # cualquier otra cosa -> documento en ingles. No son dos ajustes:
            # el del documento se DERIVA del de la pantalla, y por eso no hay
            # ningun sitio donde elegirlo por separado.
            #
            # El motor emite contenido normativo en dos idiomas porque lo
            # escribe una persona. Atar la pantalla a esos dos habria dejado la
            # plataforma en dos idiomas; dejar elegir el del documento aparte
            # habria puesto un ajuste que nadie sabe para que sirve. La derivada
            # da las dos cosas: seis idiomas de pantalla, y el documento en el
            # tuyo cuando existe.
            REGLA = {"es": "es", "en": "en", "fr": "en", "pt": "en", "it": "en", "de": "en"}
            for idioma, esperado in REGLA.items():
                pag.idioma(idioma)
                lang = pag.page.evaluate("() => document.documentElement.lang")
                todo._afirma(lang == idioma, f"se pidio {idioma!r} y el <html> dice {lang!r}")

                pag.idiomas_pedidos.clear()
                pag.pedir("plan")
                pedidos = set(pag.idiomas_pedidos)
                todo._afirma(pedidos == {esperado},
                             f"con la pantalla en {idioma!r} el panel pidio el documento en "
                             f"{pedidos or 'nada'} y la regla dice {esperado!r}")
                texto = pag.page.locator("body").inner_text()
                todo._afirma("undefined" not in texto,
                             f"la pantalla en {idioma!r} escribe `undefined`, que parece un dato")
                aviso = pag.page.locator("#idioma-doc")
                # La regla: el contenido va en el idioma de la pantalla cuando
                # el motor lo emite, y en ingles cuando no. Y la pantalla lo
                # DICE. Sin este aviso, un frances lee un expediente en ingles
                # dentro de una pantalla en frances y no sabe por que.
                debe_avisar = idioma not in ("es", "en")
                todo._afirma(aviso.is_visible() == debe_avisar,
                             f"en {idioma!r} el aviso del idioma del documento "
                             f"{'no sale y deberia' if debe_avisar else 'sale y no deberia'}")
            pag.idioma("es")
            # UN SOLO MANDO DE IDIOMA, Y NO DOS.
            #
            # La garantia no es que hoy la derivada sea correcta: es que no hay
            # donde elegir el idioma del documento por separado. El dia que
            # aparezca un segundo selector, la regla de arriba seguiria pasando
            # y la pantalla podria estar en aleman con el expediente en
            # castellano, que es justo lo que no se quiere.
            mandos = pag.page.evaluate(
                "() => document.querySelectorAll('[data-l]').length")
            botones_idioma = pag.page.evaluate(
                "() => document.querySelectorAll('#idioma [data-l]').length")
            todo._afirma(mandos == botones_idioma == 6,
                         f"hay {mandos} mandos de idioma en la pagina y {botones_idioma} "
                         f"dentro del selector: se esperaban los seis de la interfaz y "
                         f"ninguno mas")
            reg.append("los seis idiomas: un solo mando, la regla es es->es y el resto->en, "
                       "sin `undefined`, y el aviso sale solo donde toca")

            todo._afirma(not pag.errores,
                         f"la consola del navegador escribio errores: {pag.errores}")
            reg.append("cero errores de consola en todo el recorrido")


def milisegundos(duracion: str) -> float:
    """Una duracion de Go -- `1.815s`, `633ms`, `1m2.3s` -- en milisegundos.

    Go escribe `ms` por debajo del segundo y `s` por encima, asi que quitar
    `ms` y llamar a `float` deja en CERO justo las llamadas lentas, que son las
    unicas que importan al medir. Ese cero se restaba del total y aparecia como
    transporte: el resultado decia que el motor no tarda nada y que la culpa es
    de la red, que es lo contrario de lo que pasa.
    """
    import re as _re
    unidades = {"ns": 1e-6, "us": 1e-3, "\u00b5s": 1e-3, "ms": 1.0, "s": 1000.0,
                "m": 60_000.0, "h": 3_600_000.0}
    total, visto = 0.0, False
    for numero, unidad in _re.findall(r"(\d+(?:\.\d+)?)(ns|us|\u00b5s|ms|s|m|h)",
                                      duracion.strip()):
        total += float(numero) * unidades[unidad]
        visto = True
    if not visto:
        raise ValueError(f"no parece una duracion de Go: {duracion!r}")
    return total


def _mediana(xs):
    ys = sorted(xs)
    n = len(ys)
    return ys[n // 2] if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2


# Donde vive cada verbo en la API. Se escribe aqui y no se lee de `RUTAS`
# porque `RUTAS` es JavaScript y esto es Python; lo que SI se comprueba es que
# las claves sean exactamente las del recorrido, para que anadir una vista y no
# medirla no pase en silencio.
CAMINOS = {
    "apl": ("POST", "/aplicabilidad"), "plan": ("POST", "/plan"),
    "comp": ("POST", "/comprobar"), "preg": ("POST", "/preguntar"),
    "soa": ("POST", "/soa"), "anx": ("POST", "/anexo?cual=iv"),
    "ev": ("GET", "/almacen"), "vig": ("POST", "/vigilar"),
    "venc": ("GET", "/vencimientos"), "nc": ("GET", "/noconformidades"),
    "rev": ("GET", "/revision"),
}


def latencias(repeticiones: int = 5) -> int:
    """Lo que tarda cada verbo, separado en las tres cosas que lo componen.

    LAS TRES, Y NO UNA SOLA, PORQUE OPTIMIZAR LA EQUIVOCADA ES LO NORMAL
    ---------------------------------------------------------------------
    Un verbo de este producto es un PROCESO que el servidor arranca, y eso esta
    puesto a proposito: el motor que contesta por HTTP es exactamente el mismo
    binario que corre quien audita en su maquina. El precio de esa frontera es
    arrancar un interprete de Python en cada peticion, y ese precio no se ve si
    solo se mide el total.

      motor       lo que el servidor cronometro alrededor del proceso.
      transporte  lo que anaden el HTTP y el JSON por encima.
      pantalla    desde que se pulsa el boton hasta que hay filas en el DOM.

    Sin esta separacion, el numero gordo se lee como «el motor es lento» y se
    acaba optimizando un analisis que tarda cuatro milisegundos.
    """
    if set(CAMINOS) != set(RECORRIDO):
        raise AssertionError(
            f"hay vistas sin medir o medidas de mas: {set(RECORRIDO) ^ set(CAMINOS)}")

    directas: dict[str, list[float]] = {}
    servidor: dict[str, list[float]] = {}
    with pila() as (base, token):
        perfil = json.dumps({"roles": ["proveedor"], "alto_riesgo": "si",
                             "via_anexo": "anexo_iii", "fecha": "2027-12-02"}).encode()
        for verbo, (metodo, camino) in CAMINOS.items():
            for _ in range(repeticiones):
                cuerpo = perfil if (metodo == "POST" and verbo != "comp") else None
                cabeceras = {"Authorization": "Bearer " + token}
                if cuerpo:
                    cabeceras["Content-Type"] = "application/json"
                pet = urllib.request.Request(base + "/v1/clientes/acme" + camino,
                                             data=cuerpo, headers=cabeceras, method=metodo)
                t0 = time.perf_counter()
                with urllib.request.urlopen(pet, timeout=180) as resp:
                    d = json.loads(resp.read().decode("utf-8"))
                directas.setdefault(verbo, []).append((time.perf_counter() - t0) * 1000)
                # Sin `try`: si la API deja de publicar `duracion`, o la
                # publica en un formato que aqui no se entiende, esto tiene que
                # romperse. Tragarselo devolvia ceros que parecian una medida.
                servidor.setdefault(verbo, []).append(
                    milisegundos(str(d["duracion"])))

        with navegador(base, token) as (pag, _):
            carga = pag.abrir()
            pag.conectar()
            pag.categoria(CATEGORIA_COMPLETA)
            pantalla = {r["verbo"]: r for r in (pag.pedir(v) for v in RECORRIDO)}

    peso = (RAIZ / "panel" / "panel.html").stat().st_size / 1024
    print()
    print(f"carga de la pagina: {carga:.0f} ms "
          f"({peso:.0f} KB, un fichero, cero peticiones de red)")
    print()
    print(f"mediana de {repeticiones} llamadas a cada verbo, en milisegundos")
    print()
    print(f"{'vista':<7}{'motor':>8}{'transporte':>12}{'pantalla':>10}{'filas':>7}")
    print("-" * 44)
    for verbo in RECORRIDO:
        m = _mediana(servidor[verbo])
        d = _mediana(directas[verbo])
        print(f"{verbo:<7}{m:>8.0f}{d - m:>12.0f}{pantalla[verbo]['ms']:>10}"
              f"{pantalla[verbo]['filas']:>7}")
    print("-" * 44)
    tm = sum(_mediana(servidor[v]) for v in RECORRIDO)
    tt = sum(_mediana(directas[v]) for v in RECORRIDO) - tm
    print(f"{'todas':<7}{tm:>8.0f}{tt:>12.0f}"
          f"{sum(pantalla[v]['ms'] for v in RECORRIDO):>10}")
    return 0


# Las piezas de la pantalla, una por una. El manual explica botón por botón y
# sección por sección, así que cada una necesita su recorte: una captura de la
# ventana entera con una flecha encima no sirve para eso, y envejece peor.
#
# La clave es el nombre del fichero; el valor, el selector y el alto máximo.
PIEZAS = {
    "manual-cabecera":   ("header .bar", 200),
    "manual-categorias": (".cats", 320),
    "manual-ciclo":      ("#ciclo", 260),
    "manual-conexion":   ("#tarjeta-conexion", 700),
    "manual-perfil":     ("#tarjeta-perfil", 900),
    "manual-vistas":     ("#tarjeta-perfil .acciones", 460),
    "manual-recuento":   (".rejilla > div:last-child > section:nth-child(1)", 340),
    "manual-lineas":     (".rejilla > div:last-child > section:nth-child(2)", 620),
    "manual-crudo":      (".rejilla > div:last-child > section:nth-child(3)", 460),
}

# Una captura por vista, con el nombre con el que el manual la llama.
POR_VISTA = {
    "apl": "vista-aplicabilidad", "plan": "vista-plan", "comp": "vista-articulo50",
    "preg": "vista-cuestionario", "soa": "vista-soa", "anx": "vista-anexo-iv",
    "ev": "vista-evidencia", "vig": "vista-vigilancia", "venc": "vista-vencimientos",
    "nc": "vista-noconformidades", "rev": "vista-revision",
}

# Y las que el README enseña, que son un subconjunto con otro nombre.
DEL_README = {"plan": "panel-plan", "preg": "panel-cuestionario",
              "soa": "panel-soa", "anx": "panel-anexo-iv"}


def capturas() -> int:
    """Las imagenes del README y del manual, hechas contra la pila de verdad.

    Se encuadra cada PIEZA y no la ventana entera. Una captura de la ventana
    sale con media pagina de formulario y la respuesta cortada por donde se
    quedo el scroll, y un manual que explica un boton necesita ese boton, no la
    pantalla donde esta.
    """
    SALIDA.mkdir(parents=True, exist_ok=True)
    hechas = []
    with pila() as (base, token):
        with navegador(base, token) as (pag, _):
            pag.abrir()

            # La conexion, ANTES de conectar: es la primera pantalla que ve
            # alguien y el manual empieza por ella. Despues de conectar lleva la
            # credencial puesta y el boton de desconectar, que es otra cosa.
            pag.recortar("#tarjeta-conexion", SALIDA / "manual-conexion-vacia.png", 700)
            hechas.append("manual-conexion-vacia")

            pag.conectar()
            pag.categoria(CATEGORIA_COMPLETA)
            pag.perfil()
            pag.pedir("plan")

            for nombre, (selector, alto) in PIEZAS.items():
                pag.recortar(selector, SALIDA / f"{nombre}.png", alto)
                hechas.append(nombre)

            # El aviso de que el documento llega en otro idioma, que solo existe
            # en los cuatro idiomas que el motor no emite.
            pag.idioma("fr")
            pag.pedir("plan")
            pag.recortar(".wrap.hero", SALIDA / "manual-idioma-aviso.png", 460)
            hechas.append("manual-idioma-aviso")
            pag.idioma("es")

            # Una fila con la remediacion DESPLEGADA, que es donde vive lo que
            # hay que hacer y es lo que el manual tiene que ensenar.
            pag.pedir("plan")
            pag.page.locator("#lineas details").first.evaluate(
                "d => { d.open = true; d.scrollIntoView({block: 'center'}); }")
            pag.page.wait_for_timeout(300)
            pag.recortar("#lineas", SALIDA / "manual-fila-abierta.png", 520)
            hechas.append("manual-fila-abierta")

            # El buscador con algo escrito, y la cuenta que sale debajo.
            pag.pedir("preg")
            pag.page.fill("#buscar", "datos")
            pag.page.wait_for_timeout(300)
            pag.recortar(".rejilla > div:last-child > section:nth-child(2)",
                         SALIDA / "manual-buscador.png", 560)
            hechas.append("manual-buscador")
            pag.page.fill("#buscar", "")

            # Una por vista. `vig` va antes que `ev` a proposito: asi el almacen
            # que se retrata es el que YA tiene cadena, y no el del primer dia.
            orden = [v for v in RECORRIDO if v != "ev"] + ["ev"]
            for verbo in orden:
                r = pag.pedir(verbo)
                pag.recortar(".rejilla > div:last-child",
                             SALIDA / f"{POR_VISTA[verbo]}.png", 900)
                hechas.append(f"{POR_VISTA[verbo]} ({r['filas']} filas)")
                if verbo in DEL_README:
                    pag.recortar(".rejilla > div:last-child",
                                 SALIDA / f"{DEL_README[verbo]}.png", 900)

            # La pantalla entera, que es la que ensena el producto de un vistazo.
            pag.pedir("plan")
            pag.arriba()
            pag.page.screenshot(path=str(SALIDA / "panel.png"))
            hechas.append("panel")

            # Y en oscuro, que es la mitad de las capturas que alguien mira en
            # un README y la que suele estar rota.
            pag.tema("dark")
            pag.pedir("plan")
            pag.arriba()
            pag.page.screenshot(path=str(SALIDA / "panel-oscuro.png"))
            hechas.append("panel-oscuro")

        # La portada, que se sirve como fichero y no necesita la API. En los dos
        # idiomas del manual, porque el manual tambien va en los dos.
        #
        # Solo la primera pantalla. La pagina ENTERA pesa 2,3 MB por idioma y
        # ningun documento la ensena: seria un fichero que viaja en cada clon
        # para siempre sin que nadie lo mire. Para mirarla entera esta
        # `--web`, que escribe donde se le diga y no dentro del arbol.
        with navegador(base, token, alto=1000) as (pag, _):
            for idioma, rel in (("es", "index.html"), ("en", "en/index.html")):
                pag.page.goto((RAIZ / "sitio" / rel).as_uri(), wait_until="load")
                pag.page.wait_for_timeout(400)
                sufijo = "" if idioma == "es" else "-en"
                pag.page.screenshot(path=str(SALIDA / f"portada{sufijo}.png"))
                hechas.append(f"portada{sufijo}")

    for x in hechas:
        print(f"  {x}")
    peso = sum(f.stat().st_size for f in SALIDA.glob("*")) / 1e6
    print(f"  {len(list(SALIDA.glob('*')))} ficheros, {peso:.1f} MB en "
          f"{SALIDA.relative_to(RAIZ)}")
    return 0


def web(destino: Path) -> int:
    """La portada ENTERA, en los seis idiomas, fuera del arbol.

    Separado de `--capturas` porque son otra cosa: las del arbol son las que
    los documentos ensenan y tienen que existir siempre; estas son para mirar
    la pagina de arriba abajo o mandarsela a alguien, pesan dos megas cada una
    y no las referencia nadie.
    """
    destino.mkdir(parents=True, exist_ok=True)
    idiomas = {"es": "index.html", "en": "en/index.html", "fr": "fr/index.html",
               "pt": "pt/index.html", "it": "it/index.html", "de": "de/index.html"}
    with navegador("about:blank", "", alto=1000) as (pag, _):
        for idioma, rel in idiomas.items():
            pag.page.goto((RAIZ / "sitio" / rel).as_uri(), wait_until="load")
            pag.page.wait_for_timeout(400)
            entera = destino / f"actaira-portada-{idioma}.png"
            pag.page.screenshot(path=str(entera), full_page=True)
            primera = destino / f"actaira-portada-{idioma}-primera-pantalla.png"
            pag.page.screenshot(path=str(primera))
            print(f"  {entera.name}  {entera.stat().st_size / 1e6:.1f} MB")
            print(f"  {primera.name}  {primera.stat().st_size / 1e6:.1f} MB")
    print(f"  en {destino}")
    return 0


def _tour(pag: Pagina) -> None:
    """El recorrido de 30 segundos. Las esperas son para el ojo, no para el codigo.

    Lo que ensena, en este orden: que te ata (aplicabilidad), que se comprobo
    leyendo bytes (plan), lo que hay que preguntarte (cuestionario), el
    expediente (la declaracion de aplicabilidad y el Anexo IV), el buscador, y
    que la pantalla habla seis idiomas. Es el argumento del producto en el
    orden en que se cuenta.
    """
    pag.abrir()
    pag.page.wait_for_timeout(1100)
    pag.conectar()
    pag.categoria(CATEGORIA_COMPLETA)
    pag.page.wait_for_timeout(900)
    pag.perfil()
    pag.page.wait_for_timeout(700)
    # CUATRO VISTAS Y NO ONCE.
    #
    # Cada `pedir` tarda lo que tarde el motor -- de dos decimas a tres
    # segundos y medio, segun la maquina -- asi que el recorrido dura lo que
    # dure el producto y no lo que diga esta lista. Con seis verbos se iba a
    # cuarenta y ocho segundos y el corte de treinta se comia los idiomas, que
    # es la mitad de lo que hay que ensenar.
    for verbo, espera in [("apl", 1600), ("plan", 2400), ("preg", 2200), ("anx", 1800)]:
        pag.pedir(verbo)
        pag.mirar_respuesta()
        pag.page.wait_for_timeout(espera)
    # El buscador, sobre el documento que mas filas tiene.
    pag.page.fill("#buscar", "conformidad")
    # Filtrar ENCOGE la lista, asi que el scroll se queda por debajo del final
    # y la pantalla acaba ensenando el volcado de JSON del pie. Volver a
    # encuadrar es lo que hace que se vea lo que el filtro dejo.
    pag.mirar_respuesta()
    pag.page.wait_for_timeout(1700)
    pag.page.fill("#buscar", "")
    pag.page.wait_for_timeout(600)
    # Y los idiomas. El aviso de que el documento llega en ingles sale solo en
    # los cuatro que el motor no emite, y eso se ve aqui.
    for idioma in ["en", "fr", "de"]:
        pag.idioma(idioma)
        pag.page.wait_for_timeout(1200)
    pag.idioma("es")
    pag.page.wait_for_timeout(600)
    pag.tema("dark")
    pag.page.wait_for_timeout(2400)


def gif(segundos: int, ancho: int, fps: int) -> int:
    if not shutil.which("ffmpeg"):
        print("hace falta `ffmpeg` para pasar el video a GIF", file=sys.stderr)
        return 1
    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / "panel.gif"
    with tempfile.TemporaryDirectory() as tmp:
        videos = Path(tmp)
        with pila() as (base, token):
            with navegador(base, token, video=videos, ancho=1400, alto=900) as (pag, ctx):
                t0 = time.perf_counter()
                _tour(pag)
                duro = time.perf_counter() - t0
                ruta_video = pag.page.video.path() if pag.page.video else None
            print(f"  recorrido grabado: {duro:.1f} s")
        webm = Path(ruta_video) if ruta_video else next(videos.glob("*.webm"))
        paleta = Path(tmp) / "paleta.png"
        filtro = f"fps={fps},scale={ancho}:-1:flags=lanczos"
        subprocess.run(["ffmpeg", "-y", "-i", str(webm), "-t", str(segundos),
                        # `max_colors` bajo, y no los 256 por omision. Esta
                        # pantalla es interfaz plana: dos grises de fondo, un
                        # morado, seis colores de pastilla y el gris del texto
                        # antialiasado. Medido sobre el mismo video, bajar de
                        # 128 a 64 quita un 30 % del peso sin que se note, y lo
                        # que decide si alguien ve un GIF de README entero no es
                        # su nitidez.
                        "-vf", filtro + ",palettegen=stats_mode=diff:max_colors=64",
                        str(paleta)], check=True, capture_output=True)
        # `dither=none`, y no un patron de Bayer. Esta pantalla es interfaz
        # plana -- fondos lisos, texto negro, seis colores de pastilla -- y
        # difuminar le mete ruido a cada fotograma: el GIF se ve peor Y pesa
        # mas, porque el ruido rompe las zonas planas que el formato comprime.
        # Con `diff` en la paleta y sin difuminado bajo de 10,6 MB a la mitad.
        subprocess.run(["ffmpeg", "-y", "-i", str(webm), "-i", str(paleta), "-t", str(segundos),
                        "-lavfi", filtro + "[x];[x][1:v]paletteuse=dither=none",
                        str(destino)], check=True, capture_output=True)
    peso = destino.stat().st_size / 1e6
    print(f"  {destino.relative_to(RAIZ)}  {peso:.1f} MB  ({segundos} s, {fps} fps, {ancho} px)")
    # EL PRESUPUESTO ES 5 MB, Y LO CARO NO ES ESTE FICHERO: ES LA SERIE.
    #
    # Un README con un GIF que tarda en cargar es un README que nadie ve
    # entero, y eso ya justificaria un limite. Pero el coste que de verdad
    # importa es otro: esto vive en git, y un video grabado nunca sale igual
    # dos veces, asi que CADA regeneracion mete un objeto nuevo en la historia
    # y ninguno se va nunca. A ocho megas por pasada, cinco pasadas son
    # cuarenta megas que todo el mundo se clona para siempre.
    #
    # De ahi las dos decisiones: el fichero pequeno (680 px, 5 fps, 64 colores
    # -- se sigue leyendo el titular, las categorias y el ciclo, que es lo que
    # un GIF de README tiene que ensenar) y regenerarlo SOLO cuando la pantalla
    # cambie de verdad. Las capturas fijas no tienen este problema: un PNG de
    # la misma pantalla sale casi identico y git lo reconoce.
    if peso > 5:
        print(f"  AVISO: {peso:.1f} MB pasa del presupuesto de 5 MB. "
              f"Baja `--fps` o `--ancho`.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="El panel en un navegador de verdad.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--puerta", action="store_true", help="afirma, y sale rojo si no")
    g.add_argument("--capturas", action="store_true", help="las imagenes del README")
    g.add_argument("--gif", action="store_true", help="el recorrido, en GIF")
    g.add_argument("--latencias", action="store_true", help="lo que tarda cada verbo")
    g.add_argument("--web", metavar="CARPETA",
                   help="la portada entera en los seis idiomas, en esa carpeta")
    p.add_argument("--segundos", type=int, default=30)
    p.add_argument("--ancho", type=int, default=680)
    p.add_argument("--fps", type=int, default=5)
    p.add_argument("--repeticiones", type=int, default=5)
    a = p.parse_args()
    try:
        if a.puerta:
            reg: list[str] = []
            puerta(reg)
            for linea in reg:
                print(f"  {linea}")
            return 0
        if a.capturas:
            return capturas()
        if a.web:
            return web(Path(a.web))
        if a.gif:
            return gif(a.segundos, a.ancho, a.fps)
        return latencias(a.repeticiones)
    except todo.Omitida as e:
        print(f"OMITIDA: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
