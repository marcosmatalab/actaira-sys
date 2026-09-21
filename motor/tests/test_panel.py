"""Fase 20: el panel conectado, y las dos negativas que lo definen.

La pagina traduce presentacion, nunca significado. El dia que calcule algo
habra tres motores en vez de dos, y el tercero sera el mas facil de no auditar
porque vive en el navegador de otro.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PANEL = RAIZ / "panel"


def _cargar(nombre: str, ruta: Path):
    """Carga un modulo POR RUTA y con nombre propio.

    La consola y el panel tienen los dos un `construir.py`, y meter sus
    carpetas en `sys.path` hacia que el segundo `import construir` devolviera
    el modulo ya cacheado del primero: el test de la consola comprobaba la
    reproducibilidad del PANEL segun el orden en que pytest recogiera los
    ficheros. Un test cuyo resultado depende del orden de recogida no mide lo
    que dice medir.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo


_construir = _cargar("actaira_panel_construir", PANEL / "construir.py")
PROHIBIDO_EN_LA_LOGICA = _construir.PROHIBIDO_EN_LA_LOGICA
_codigo_sin_prosa = _construir._codigo_sin_prosa
revisar_logica = _construir.revisar_logica
revisar_textos = _construir.revisar_textos

LOGICA = (PANEL / "plantilla" / "logica.js").read_text(encoding="utf-8")
TEXTOS = json.loads((PANEL / "textos.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html():
    ruta = PANEL / "panel.html"
    if not ruta.is_file():
        pytest.skip("corre `make panel` antes")
    return ruta.read_text(encoding="utf-8")


# --- los dos idiomas ------------------------------------------------------

def test_los_seis_idiomas_tienen_las_mismas_claves():
    """Una clave que falte en uno sale como `undefined` en la pantalla de un
    cliente, y eso no lo detecta ningun test de unidad porque el fallo esta en
    el dato y no en el codigo.

    Eran dos y son seis. El numero no se escribe aqui suelto: se exige que
    esten LOS SEIS que la casa dice hablar, porque quitar uno sin darse cuenta
    es exactamente el fallo que esto vigila.
    """
    revisar_textos(TEXTOS)
    assert set(TEXTOS) == {"es", "en", "fr", "pt", "it", "de"}
    assert len(TEXTOS["es"]) >= 60


def test_y_el_guardia_muerde_cuando_falta_una():
    """Regla 9: el gemelo."""
    with pytest.raises(SystemExit, match="faltan"):
        revisar_textos({"es": {"a": "x", "b": "y"}, "en": {"a": "x"}})
    with pytest.raises(SystemExit, match="vacias"):
        revisar_textos({"es": {"a": " "}, "en": {"a": "x"}})


def test_toda_clave_de_texto_se_usa_y_toda_usada_existe():
    """Una clave que nadie pinta es una traduccion que alguien mantiene para
    nada; una que se pinta y no existe sale como `undefined`."""
    codigo = _codigo_sin_prosa(LOGICA)
    usadas = set(re.findall(r"\bt\.([a-z0-9_]+)", codigo))
    usadas |= set(re.findall(r"\bT\(\)\.([a-z0-9_]+)", codigo))
    # Las que se pintan por su clave, desde el mapa de `pintarTextos`, salen de
    # la propia pagina sin adivinar nada.
    mapa = re.search(r"const mapa = \{(.*?)\};", LOGICA, re.S)
    usadas |= set(re.findall(r'"([a-z0-9_]+)"\s*,?\s*$', mapa.group(1), re.M))
    usadas |= set(re.findall(r':\s*"([a-z0-9_]+)"', mapa.group(1)))
    declaradas = set(TEXTOS["es"])
    # Las que se componen (`"cat_" + clave`, `"codigo_" + r.codigo`) se nombran
    # a mano: adivinarlas con una expresion regular seria la misma clase de
    # herramienta que casi funciona.
    compuestas = {f"cat_{c}" for c in ("dev", "pyme", "empresa")}
    compuestas |= {f"cat_{c}_pie" for c in ("dev", "pyme", "empresa")}
    compuestas |= {f"codigo_{n}" for n in (0, 1, 3, 4, 5)}
    compuestas |= {"titulo", "si", "no", "nulo", "todas", "hallazgos", "preguntas",
                   "p1", "p2", "p3", "p4", "p5"}
    compuestas |= {f"rol_{r}" for r in ("proveedor", "responsable_del_despliegue",
                                        "importador", "distribuidor",
                                        "fabricante_de_productos",
                                        "representante_autorizado")}
    huerfanas = declaradas - usadas - compuestas
    assert not huerfanas, f"claves que nadie pinta: {sorted(huerfanas)}"
    inventadas = (set(re.findall(r"\bt\.([a-z0-9_]+)", codigo))
                  | set(re.findall(r"\bT\(\)\.([a-z0-9_]+)", codigo))) - declaradas
    assert not inventadas, f"claves que se pintan y no existen: {sorted(inventadas)}"


# --- la credencial no se guarda -------------------------------------------

def test_la_logica_no_toca_el_almacenamiento_del_navegador():
    """La credencial vale para leer el expediente entero de un cliente. En el
    almacenamiento del navegador la lee cualquier script que acabe en la
    pagina, y ademas sobrevive a cerrar la pestana."""
    revisar_logica(LOGICA)
    codigo = _codigo_sin_prosa(LOGICA)
    for prohibido in PROHIBIDO_EN_LA_LOGICA:
        assert prohibido not in codigo


def test_y_el_guardia_muerde_de_verdad():
    with pytest.raises(SystemExit, match="localStorage"):
        revisar_logica('function f(){ localStorage.setItem("t", x); }')


def test_pero_no_se_dispara_con_un_comentario_que_lo_nombra():
    """El gemelo del gemelo, y es el que importa: la primera version saltaba
    con los comentarios que EXPLICAN por que no se usa. Quien vea ese rojo
    quita la palabra de la lista, y con ella la puerta entera.
    """
    revisar_logica('/* no se usa localStorage aqui */\nfunction f(){ return 1; }')
    revisar_logica('// sessionStorage tampoco\nfunction f(){ return 1; }')


# --- ni una division ------------------------------------------------------

def test_la_pagina_no_divide():
    """Una division aqui es casi siempre una proporcion disfrazada, y la
    primera negativa las prohibe."""
    revisar_logica(LOGICA)


def test_el_guardia_de_divisiones_muerde():
    for malo in ("const x = a / b;", "const p = hechos / total;",
                 "return (a+b) / 2;"):
        with pytest.raises(SystemExit, match="proporcion"):
            revisar_logica("function f(){ " + malo + " }")


def test_y_NO_se_dispara_con_una_expresion_regular_ni_con_una_url():
    """Un guardia que confunda `/\\/+$/` con una division se desactiva el
    primer dia, y con el se desactiva la prohibicion."""
    for bueno in (r'const u = s.replace(/\/+$/, "");',
                  'const t = x.replace(/_/g, " ");',
                  'const u = "https://ejemplo/x";',
                  'const q = `a/b ${x}`;',
                  '// a / b en un comentario'):
        revisar_logica("function f(){ " + bueno + " }")


# --- la pagina no afirma cumplimiento -------------------------------------

def test_la_pagina_no_pinta_ningun_agregado(html):
    """La primera negativa, en la capa donde la gente la lee."""
    sin_prosa = _codigo_sin_prosa(LOGICA)
    for prohibida in ("porcentaje", "percent", "score", "puntuacion", "nota_global",
                      "confidence", "rating", "semaforo"):
        assert not re.search(rf"\b{prohibida}\b", sin_prosa, re.I), prohibida
    # Y en la pantalla lo dice en voz alta, en los dos idiomas.
    assert TEXTOS["es"]["sin_porcentaje"] and TEXTOS["en"]["sin_porcentaje"]
    assert "sin-porcentaje" in html


def test_la_unica_aritmetica_tiene_nombre_y_es_un_recuento():
    """Se escribe con nombre para que se vea. Si algun dia aparece otra, hay
    que poder encontrarla mirando una lista corta."""
    codigo = _codigo_sin_prosa(LOGICA)
    assert "function sumaDe(" in codigo
    operadores = re.findall(r"[^\w\s\"'](\*\*?|%)[^\w\s]", codigo)
    assert not operadores, f"aritmetica suelta: {operadores}"


# --- lo que la pagina lee tiene que existir en el contrato ----------------

def _publicados_por_el_contrato() -> set[str]:
    publicados: set[str] = set()

    def recorrer(x):
        if isinstance(x, dict):
            for clave, valor in x.items():
                if clave == "properties" and isinstance(valor, dict):
                    publicados.update(valor)
                recorrer(valor)
        elif isinstance(x, list):
            for v in x:
                recorrer(v)

    for ruta in sorted((RAIZ / "contrato").glob("*.json")):
        recorrer(json.loads(ruta.read_text(encoding="utf-8")))
    return publicados


def _campos_declarados() -> list[str]:
    bloque = re.search(r"const CAMPOS_DEL_DOCUMENTO = \[(.*?)\];", LOGICA, re.S)
    assert bloque, "la pagina tiene que declarar que campos lee"
    return re.findall(r'"([a-z_]+)"', bloque.group(1))


def test_la_pagina_solo_lee_campos_que_el_contrato_publica():
    """Si lee un campo que el motor no promete, el dia que ese campo cambie de
    nombre la pantalla se queda en blanco sin que falle nada. Es exactamente el
    modo de fallo que el contrato existe para evitar, y hasta ahora solo cubria
    el lado Go.

    La primera version de este test sacaba los campos con una expresion regular
    sobre el codigo y acusaba a `append`, `class` y `first`, que son de la API
    del navegador y no de ningun documento. Un analizador a medias se relaja
    hasta que deja de mirar, asi que la lista se declara en la propia pagina y
    aqui se comprueba contra el contrato.
    """
    publicados = _publicados_por_el_contrato()
    declarados = _campos_declarados()
    assert len(declarados) >= 25
    fuera = [c for c in declarados if c not in publicados]
    assert not fuera, f"campos que la pagina lee y el contrato no promete: {fuera}"


def test_y_la_lista_no_envejece_por_el_otro_lado():
    """El gemelo. Una lista que solo se comprueba contra el contrato se llena
    de campos que ya nadie lee, y entonces deja de decir de que depende la
    pagina, que es lo unico para lo que sirve."""
    codigo = _codigo_sin_prosa(LOGICA)
    bloque = re.search(r"const CAMPOS_DEL_DOCUMENTO = \[(.*?)\];", codigo, re.S)
    resto = codigo.replace(bloque.group(0), "") if bloque else codigo
    huerfanos = [c for c in _campos_declarados() if c not in resto]
    assert not huerfanos, f"campos declarados que la pagina ya no lee: {huerfanos}"


# --- la pagina, ya construida ---------------------------------------------

def test_la_pagina_es_un_solo_fichero_con_su_marca_dentro(html):
    """Un panel que necesita un servidor de estaticos para ensenar su logo no
    se puede abrir desde un correo, y asi es como lo va a abrir la primera
    persona que lo vea."""
    assert html.count("<script") == 1
    assert "data:image/png;base64," in html
    assert re.search(r"src=[\"']https?://", html) is None, "no se trae codigo de fuera"
    assert len(html) < 400_000, "una pagina que tarda en abrirse no es intuitiva"


def test_la_pagina_no_lleva_ninguna_direccion_ni_credencial_dentro(html):
    for filtracion in ("Bearer ey", "actaira.com/clientes", "token="):
        assert filtracion not in html
    assert 'id="credencial" type="password"' in html


def test_las_tres_categorias_de_producto_estan_y_dicen_que_ensenan(html):
    """Marcos lo pidio asi: por categoria de producto, para pymes y empresas.
    Lo que una categoria cambia es QUE se pide y QUE se ve primero, nunca lo
    que el motor concluye."""
    codigo = _codigo_sin_prosa(LOGICA)
    for cat in ("dev", "pyme", "empresa"):
        assert TEXTOS["es"][f"cat_{cat}"] and TEXTOS["en"][f"cat_{cat}_pie"]
    assert re.search(r"CATEGORIAS\s*=", codigo)
    # y ninguna categoria cambia el documento: solo pasos y verbos
    bloque = codigo[codigo.index("CATEGORIAS"):codigo.index("const estado")]
    assert set(re.findall(r"(\w+):\s*\[", bloque)) == {"pasos", "verbos"}


def test_la_construccion_del_panel_es_reproducible():
    """Dos construcciones seguidas dan el mismo byte, o la pagina no es una
    funcion de sus piezas."""
    a = _construir.construir()
    b = _construir.construir()
    assert a == b
    ruta = PANEL / "panel.html"
    if ruta.is_file():
        assert a == ruta.read_text(encoding="utf-8"), \
            "panel.html no coincide con lo que construir.py produce: corre `make panel`"


def test_el_panel_no_afirma_comprobar_una_firma_que_no_comprueba():
    """La entradilla decia «un documento firmado por el motor», y no era verdad.

    El panel no lleva ni una linea de criptografia: no verifica ninguna firma,
    no exige ninguna clave, y la API le entrega JSON llano. El motor SI sabe
    firmar -- `sellar` emite un sello Ed25519 verificable sin red -- y eso es
    justo lo que hacia la frase creible.

    Lo que se rompe con una frase asi no es la pagina: es la unica cosa que
    este producto vende, que es que lo que dice se puede comprobar. Un cliente
    que la lea y luego descubra que ahi no se comprueba nada deja de creerse
    tambien lo que si es cierto.
    """
    import json as _json
    import re as _re

    textos = _json.loads((PANEL / "textos.json").read_text(encoding="utf-8"))
    logica = (PANEL / "plantilla" / "logica.js").read_text(encoding="utf-8")

    hace_criptografia = _re.search(r"crypto\.subtle|Ed25519|verify\(", logica)
    for idioma in ("es", "en"):
        for clave, texto in textos[idioma].items():
            if clave == "origen_nota":
                continue          # esta habla justamente de que NO se comprueba
            if _re.search(r"\bfirmad[oa]\b|\bsigned\b", texto) and not hace_criptografia:
                raise AssertionError(
                    f"{idioma}.{clave} dice que el documento viene firmado y esta pagina "
                    f"no comprueba ninguna firma: {texto[:120]}")

    # Y la otra mitad: el limite tiene que estar DICHO, no solo no mentido.
    for idioma in ("es", "en"):
        assert "origen_nota" in textos[idioma]
        assert textos[idioma]["origen_nota"].strip()


def test_el_panel_puede_ensenar_todo_lo_que_la_api_traduce():
    """Una vista de menos no es una pantalla incompleta: es un motor invisible.

    La API traducia cinco de los diecinueve verbos del motor, asi que el panel
    no podia ensenar la evidencia, ni el cuestionario, ni la declaracion de
    aplicabilidad, ni el expediente, ni la revision por la direccion. Una
    auditoria externa lo leyo como «no hay explorador de evidencia, no hay
    vista de procedencia, no hay tablero»; era cierto, y la causa estaba una
    capa mas abajo de donde se veia.

    Esta puerta ata las dos capas: cada ruta que la API publica tiene que tener
    su vista en el panel, o la pantalla vuelve a quedarse corta en cuanto
    alguien anada una ruta.
    """
    import re as _re

    logica = (PANEL / "plantilla" / "logica.js").read_text(encoding="utf-8")
    pagina = (PANEL / "plantilla" / "pagina.html").read_text(encoding="utf-8")
    textos = _json_del_panel()

    bloque = logica.split("const RUTAS = {", 1)[1].split("\n};", 1)[0]
    vistas = _re.findall(r"^\s*([a-z]+):\s*\(c\)", bloque, _re.M)
    assert len(vistas) >= 9, f"solo hay {len(vistas)} vistas: {vistas}"

    for vista in vistas:
        assert f'id="pedir-{vista}"' in pagina, (
            f"la vista {vista!r} esta en RUTAS y no tiene boton en la pagina")
        assert f'"#pedir-{vista}"' in logica, (
            f"el boton de {vista!r} no esta atado a ninguna clave de texto, asi que "
            f"sale vacio en los dos idiomas")
        clave = _re.search(rf'"#pedir-{vista}":\s*"([a-z0-9_]+)"', logica).group(1)
        for idioma in ("es", "en"):
            assert textos[idioma].get(clave), (
                f"falta el texto {idioma}.{clave} del boton de {vista!r}")


def test_el_texto_se_escribe_al_pintar_y_no_al_arrancar():
    """Lo que se escribe una sola vez se queda en el idioma de esa vez.

    `#servidor-nota` se rellenaba dentro de `arrancar()`, asi que quien
    cambiaba de idioma se quedaba con ese parrafo en castellano dentro de una
    pantalla en aleman. Se veia a simple vista y llevaba ahi desde que la
    pagina tiene dos idiomas.

    Lo que no lo cazaba es que ninguna prueba cambia el idioma y vuelve a
    mirar. Comprobar eso de verdad pide un navegador; lo que SI se puede
    comprobar leyendo es la regla estructural de la que depende: el texto se
    escribe al PINTAR, y `arrancar()` solo engancha. Cualquier `T()` dentro de
    `arrancar()` es texto que no se va a repintar.
    """
    import re as _re

    logica = (PANEL / "plantilla" / "logica.js").read_text(encoding="utf-8")
    cuerpo = logica.split("function arrancar()", 1)[1]
    cuerpo = cuerpo[:cuerpo.index("\n}\n")]
    escritos = [l.strip() for l in cuerpo.splitlines() if _re.search(r"\bT\(\)\.", l)]
    assert not escritos, (
        "`arrancar()` escribe texto que no se repinta al cambiar de idioma: "
        f"{escritos}")


def test_toda_vista_de_rutas_es_alcanzable_desde_alguna_categoria():
    """Un boton que existe y no se puede pulsar nunca es peor que no tenerlo.

    `RUTAS` paso de cuatro vistas a once y `CATEGORIAS` -- la tabla que decide
    cual se ENSENA -- se quedo en cuatro. Siete quedaron inalcanzables desde
    cualquier categoria: el Anexo IV, la declaracion de aplicabilidad, el
    cuestionario, el almacen de evidencia, la revision por la direccion, la
    aplicabilidad y el control del articulo 50. Es decir, justo lo que la
    portada vende.

    Nadie lo echo de menos porque un boton oculto no deja hueco. La puerta que
    ya habia comprobaba que cada vista tuviera boton y texto, y las once lo
    tenian: lo que faltaba era que alguien pudiera llegar a pulsarlo.

    Es el mismo defecto que tuvo la API una capa mas abajo, reaparecido una
    capa mas arriba. Por eso esta puerta mira la CADENA entera y no un eslabon.
    """
    import re as _re

    logica = (PANEL / "plantilla" / "logica.js").read_text(encoding="utf-8")

    rutas = logica.split("const RUTAS = {", 1)[1].split("\n};", 1)[0]
    vistas = set(_re.findall(r"^\s*([a-z]+):\s*\(c\)", rutas, _re.M))

    cats = logica.split("const CATEGORIAS = {", 1)[1].split("\n};", 1)[0]
    alcanzables = set()
    for m in _re.finditer(r"verbos:\s*\[([^\]]*)\]", cats, _re.S):
        alcanzables |= set(_re.findall(r'"([a-z]+)"', m.group(1)))

    huerfanas = sorted(vistas - alcanzables)
    assert not huerfanas, (
        f"estas vistas estan en RUTAS y no las ensena ninguna categoria, asi que "
        f"su boton no se puede pulsar nunca: {huerfanas}")

    inventadas = sorted(alcanzables - vistas)
    assert not inventadas, (
        f"estas categorias ensenan vistas que no existen en RUTAS: {inventadas}")

    # Y que NADIE vuelva a escribir la lista a mano.
    #
    # `pintarBotones` llevaba cuatro pares escritos a mano con once vistas en
    # `RUTAS`: los otros siete se quedaban con el `disabled` del HTML para
    # siempre. La comprobacion de arriba no lo habria cazado, porque las once
    # SI estaban en alguna categoria. Lo que fallaba era el pintado.
    pintar = logica.split("function pintarBotones()", 1)[1].split("\n}", 1)[0]
    assert "Object.keys(RUTAS)" in pintar, (
        "`pintarBotones` no recorre `RUTAS`: si lleva una lista escrita a mano, "
        "la vista que alguien olvide se queda apagada para siempre y no falla nada")


def test_la_pagina_pasa_su_propia_puerta_de_accesibilidad():
    """La puerta corre al CONSTRUIR, y aqui se comprueba que sigue corriendo.

    Vive en `panel/construir.py` porque la accesibilidad no se rompe de golpe:
    se rompe un control cada vez, cuando alguien anade un boton con prisa. Una
    revision manual lo encuentra meses despues, cuando ya hay veinte.
    """
    import importlib.util
    import sys as _sys

    spec = importlib.util.spec_from_file_location(
        "actaira_panel_a11y", PANEL / "construir.py")
    m = importlib.util.module_from_spec(spec)
    _sys.modules["actaira_panel_a11y"] = m
    spec.loader.exec_module(m)

    pagina = m.construir()          # revienta sola si no pasa
    textos = _json_del_panel()

    # Y la puerta MUERDE: con un boton sin nombre, se pone roja.
    import pytest

    roto = pagina.replace('<button class="boton" id="pedir-plan" disabled></button>',
                          '<button class="boton" disabled></button>')
    assert roto != pagina
    with pytest.raises(SystemExit):
        m.revisar_accesibilidad(roto, textos)


def _json_del_panel() -> dict:
    import json as _json

    return _json.loads((PANEL / "textos.json").read_text(encoding="utf-8"))
