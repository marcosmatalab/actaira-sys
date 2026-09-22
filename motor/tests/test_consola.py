"""La consola se construye, no se edita. B-006.

La pagina se arma de cinco piezas y ninguna es el fichero de 152 KB que sale.
Estos tests sujetan las dos propiedades que hacen que eso valga algo: que la
reconstruccion sea reproducible, y que los dos idiomas cubran las mismas claves.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CONSOLA = RAIZ / "consola"


SEIS = {"es", "en", "fr", "pt", "it", "de"}


def test_los_seis_idiomas_cubren_las_mismas_claves():
    """Una clave que falte en un idioma sale como `undefined` en la pantalla de un cliente.

    Eran dos y son seis. Lo que se exige no es «los que haya»: son LOS SEIS que
    la casa dice hablar, porque perder uno sin darse cuenta es justo el fallo
    que esto vigila.
    """
    t = json.loads((CONSOLA / "textos.json").read_text(encoding="utf-8"))
    assert set(t) == SEIS
    for idioma in sorted(SEIS):
        assert set(t[idioma]) == set(t["es"]), set(t[idioma]) ^ set(t["es"])
        # Las claves de los diccionarios anidados son DATOS con los que la
        # pagina busca: traducirlas dejaria la busqueda sin encontrar nada.
        assert set(t[idioma]["preguntas"]) == set(t["es"]["preguntas"])
        assert set(t[idioma]["roles_n"]) == set(t["es"]["roles_n"])
        assert set(t[idioma]["reglas"]) == set(t["es"]["reglas"])
        assert set(t[idioma]["soa_proc"]) == set(t["es"]["soa_proc"])
        assert len(t[idioma]["pasos"]) == len(t["es"]["pasos"])
        for clave, valor in t[idioma].items():
            if isinstance(valor, str):
                assert valor.strip(), f"{idioma}.{clave} vacio"


def test_la_construccion_es_reproducible():
    """Dos construcciones seguidas dan el mismo byte, o la pagina no es una funcion de sus piezas."""
    # Por RUTA y con nombre propio: la consola y el panel tienen los dos un
    # `construir.py`, y un `import construir` devolvia el que ya estuviera
    # cacheado segun el orden de recogida de pytest.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "actaira_consola_construir", CONSOLA / "construir.py")
    construir = importlib.util.module_from_spec(spec)
    sys.modules["actaira_consola_construir"] = construir
    spec.loader.exec_module(construir)
    a = construir.construir()
    b = construir.construir()
    assert a == b
    assert a == (CONSOLA / "consola.html").read_text(encoding="utf-8"), \
        "consola.html no coincide con lo que construir.py produce: corre `make consola`"


def test_la_pagina_publicada_lleva_los_datos_del_motor():
    """El unico invariante critico: la pagina come lo que emite el motor."""
    html = (CONSOLA / "consola.html").read_text(encoding="utf-8")
    datos = json.loads((CONSOLA / "datos.json").read_text(encoding="utf-8"))
    assert json.dumps(datos, ensure_ascii=False, separators=(",", ":")) in html


def test_ningun_texto_de_la_interfaz_vive_en_el_javascript():
    """Si un texto se cuela en la logica, deja de poder traducirse sin tocar codigo.

    Se mira dentro de los LITERALES y no en el fuente entero. La primera version
    buscaba subcadenas y acuso a `DATOS.obligaciones`, que es un identificador;
    es el mismo error de mirar de lado que ya aparecio dos veces en la fase 3.
    Pero debajo del falso positivo habia una fuga real: `reglaDe()` llevaba seis
    frases en castellano incrustadas, que ahora son plantillas en textos.json.
    """
    import re
    js = (CONSOLA / "plantilla" / "logica.js").read_text(encoding="utf-8")
    cuerpo = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    cuerpo = "\n".join(l for l in cuerpo.splitlines() if not l.strip().startswith("//"))
    literales = re.findall(r'"([^"\n]{4,})"|\'([^\'\n]{4,})\'|`([^`]{4,})`', cuerpo)
    planos = [x for tupla in literales for x in tupla if x]
    # palabras que solo aparecen en prosa de interfaz, nunca en un identificador
    for palabra in ("aplicable", "declarado", "perfil declara", "no cubre", "falta responder", "ningún"):
        culpables = [l for l in planos if palabra.lower() in l.lower()]
        assert not culpables, f"prosa de interfaz en la logica: {culpables[:2]}"


# --- fase 7: las tres vistas ------------------------------------------------

def _js() -> str:
    return (CONSOLA / "plantilla" / "logica.js").read_text(encoding="utf-8")


def test_toda_clave_de_texto_que_usa_la_logica_existe_en_los_seis_idiomas():
    """La puerta contra la fuga de idioma, cuarta reincidencia en este arbol.

    Una clave que la logica lee y `textos.json` no trae sale como `undefined`
    en la pantalla del cliente, y sale en los dos idiomas, asi que la puerta
    anterior -- que los dos idiomas cubran las mismas claves -- no la ve.
    """
    import re
    t = json.loads((CONSOLA / "textos.json").read_text(encoding="utf-8"))
    js = _js()
    usadas = set(re.findall(r"\bt\.([a-z_0-9]+)\b", js))
    usadas |= set(re.findall(r'\bt\["([a-z_0-9]+)"\]', js))
    usadas |= set(re.findall(r'\["[a-z-]+","([a-z_0-9]+)"\]', js.replace(" ", "")))
    # Un CODIGO DE IDIOMA no es una clave de texto. La heuristica de arriba
    # busca pares `["algo","otra"]` y se comia `["es","en"]`, que es la lista
    # de los idiomas en los que el catalogo existe de verdad. Una puerta que
    # denuncia lo que no es un fallo se acaba apagando.
    usadas -= SEIS
    faltan = sorted(k for k in usadas
                    if any(k not in t[i] for i in sorted(SEIS)))
    assert faltan == [], faltan


def test_todo_elemento_que_busca_la_logica_existe_en_la_pagina():
    """Un `getElementById` que devuelve null revienta la pagina entera en la
    primera pintada, y en un fichero de 268 KB eso se depura mal."""
    import re
    js, html = _js(), (CONSOLA / "plantilla" / "pagina.html").read_text(encoding="utf-8")
    pedidos = set(re.findall(r'getElementById\("([a-z0-9-]+)"\)', js))
    # Los que crea la propia logica dentro de una plantilla cuentan igual: el
    # dialogo de detalle pinta su boton de cerrar y luego lo busca. Ponerlos en
    # una lista de excepciones seria apagar la puerta; leerlos del JavaScript es
    # mirar donde de verdad se crean.
    creados = set(re.findall(r'id="([a-z0-9-]+)"', html)) | set(re.findall(r'id="([a-z0-9-]+)"', js))
    assert pedidos - creados == set(), sorted(pedidos - creados)


def test_todo_token_de_color_que_usa_el_css_esta_definido():
    """Una variable CSS sin definir no falla: pinta transparente o negro y nadie
    se entera hasta que un cliente manda una captura."""
    import re
    css = (CONSOLA / "plantilla" / "estilo.css").read_text(encoding="utf-8")
    usados = set(re.findall(r"var\((--[a-z0-9-]+)\)", css))
    definidos = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
    assert usados - definidos == set(), sorted(usados - definidos)


def test_la_consola_no_guarda_nada_en_el_navegador():
    """Las respuestas llevan nombre y cargo dentro. Lo que se guardara aqui se
    quedaria en el disco de quien abriera la pagina despues."""
    js = _js()
    for api in ("localStorage", "sessionStorage", "indexedDB", "document.cookie"):
        assert api not in js, api


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="node no esta instalado")
def test_la_regla_de_la_soa_de_la_consola_reproduce_a_la_del_motor():
    """El patron de la fase 1 aplicado a la fase 6: la regla esta escrita en
    `aplicabilidad/tabla.py` y se ejecuta dos veces, aqui y en el navegador.

    La primera version de este test transcribia a mano la regla del JavaScript
    y la comparaba con Python. Eso no compara nada: las dos copias pasaban en
    sus propios terminos y el JavaScript de verdad podia haber cambiado sin que
    nadie se enterara. Es EXACTAMENTE la forma en la que el cruce de catalogos
    acumulo 30 asimetrias en la fase 0. Ahora se extrae `clasificar` del fichero
    que se publica y se ejecuta en node contra los mismos veredictos.
    """
    from datetime import date
    from itertools import product

    from actaira_motor.aplicabilidad.tabla import evaluar_con_tabla, inclusion_en_la_soa

    tabla = json.loads((CONSOLA / "datos.json").read_text(encoding="utf-8"))
    js = _js()
    trozo = js[js.index("const clasificar = ids =>"):js.index("const arts = ids =>")]

    casos, esperado = [], []
    for valores in product((True, False, None), repeat=4):
        for cuando in (date(2026, 9, 20), date(2027, 12, 2), date(2028, 8, 3)):
            perfil = dict(zip(tabla["campos_decisivos"], valores))
            res = evaluar_con_tabla(tabla, {"proveedor"}, perfil, cuando)
            for c in tabla["controles_iso"]:
                casos.append({"res": res, "ids": c["aiact"]})
                esperado.append(inclusion_en_la_soa(c["aiact"], res)[0])

    guion = ("const casos = " + json.dumps(casos, ensure_ascii=False) + ";\n"
             "const fuera = casos.map(({res, ids}) => {\n" + trozo +
             "  return clasificar(ids)[0];\n});\n"
             "console.log(JSON.stringify(fuera));")
    tmp = RAIZ / "consola" / "__soa.js"
    tmp.write_text(guion, encoding="utf-8")
    try:
        salida = subprocess.run(["node", str(tmp)], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout
    finally:
        tmp.unlink()
    assert json.loads(salida) == esperado
    assert len(esperado) == 3 * 81 * len(tabla["controles_iso"])


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="node no esta instalado")
def test_la_admisibilidad_de_la_consola_coincide_con_la_del_motor():
    """Si discrepan, el cliente contesta en la pantalla algo que el motor rechaza
    despues, que es la peor manera posible de enterarse."""
    from actaira_motor.catalogo.cargador import cargar
    from actaira_motor.formularios.declaracion import admisible as adm_py

    cat = cargar(str(RAIZ / "catalogo"))
    casos = [
        ("F-RSK-1", "corta"), ("F-RSK-1", "x" * 250),
        ("F-CLS-1", ["ninguna"]), ("F-CLS-1", ["ninguna", "subliminal"]),
        ("F-CTX-4", ["a", "b"]), ("F-CTX-4", ["a", "b", "c"]),
        ("F-SOP-3", "x" * 90), ("F-SOP-3", "corto"),
    ]
    js = _js()
    fn = js[js.index("function admisible(q, v){"):js.index("function estadoPregunta(q){")]
    guion = (fn + "\nconst casos = " + json.dumps([
        {"q": {"id": q, "exige": cat.preguntas[q].exige,
               "formato": cat.preguntas[q].formato}, "v": v} for q, v in casos], ensure_ascii=False)
        + "\nconsole.log(JSON.stringify(casos.map(c => admisible(c.q, c.v) === 'ok')));")
    tmp = RAIZ / "consola" / "__adm.js"
    tmp.write_text(guion, encoding="utf-8")
    try:
        salida = subprocess.run(["node", str(tmp)], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout
    finally:
        tmp.unlink()
    en_js = json.loads(salida)
    en_py = [adm_py(cat.preguntas[q], v, None)[0] for q, v in casos]
    assert en_js == en_py, list(zip(casos, en_js, en_py))


def test_la_pagina_declara_utf8_y_su_ventana():
    """Lo encontro una captura de pantalla, no un test, y por eso este existe.

    La pagina no declaraba `charset`. Con el catalogo en ASCII no se notaba;
    en cuanto el castellano llevo tildes, un navegador que abre el fichero por
    `file://` lo leyo como Latin-1 y la tabla entera salio "PolÃtica de IA".
    Una pagina de cumplimiento que muestra mojibake no la lee nadie.
    """
    html = (CONSOLA / "plantilla" / "pagina.html").read_text(encoding="utf-8")
    publicada = (CONSOLA / "consola.html").read_text(encoding="utf-8")
    for pieza in ('<meta charset="utf-8">', 'name="viewport"'):
        assert pieza in html and pieza in publicada, pieza
    # y la declaracion va ANTES de cualquier texto con tilde, o llega tarde
    assert publicada.index('<meta charset="utf-8">') < 1024


def test_la_pagina_publicada_no_tiene_mojibake():
    """El gemelo por el otro lado: que el fichero este de verdad en UTF-8."""
    crudo = (CONSOLA / "consola.html").read_bytes()
    assert "Política".encode("utf-8") in crudo or "política".encode("utf-8") in crudo
    assert "PolÃ­tica".encode("utf-8") not in crudo


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="node no esta instalado")
def test_el_calendario_partido_de_la_consola_reproduce_al_del_motor():
    """La fecha que ve el cliente en la pantalla y la que sale en el expediente.

    El Reglamento (UE) 2026/1744 parte el calendario del Capitulo III en dos
    fechas separadas por ocho meses. Si la pantalla y el motor no aplicaran la
    misma regla, el cliente planificaria contra una fecha y el expediente
    diria otra, y la discrepancia solo se veria el dia de la auditoria.

    No se transcribe la regla: se EXTRAE `desdeDe` del fichero que se publica y
    se corre en node contra los mismos perfiles que evalua Python.
    """
    from datetime import date

    from actaira_motor.aplicabilidad.tabla import evaluar_con_tabla

    tabla = json.loads((CONSOLA / "datos.json").read_text(encoding="utf-8"))
    js = _js()
    trozo = js[js.index("function desdeDe(o){"):js.index("/* LA REGLA GENERICA")]
    assert "aplica_desde_por_via" in trozo, "la consola ya no mira el calendario partido"

    partidas = [o for o in tabla["obligaciones"] if o.get("aplica_desde_por_via")]
    assert partidas, "ninguna obligacion tiene calendario partido: el test no comprueba nada"

    casos, esperado = [], []
    for alto in (True, False, None):
        for via in (None, "anexo_iii", "anexo_i"):
            perfil = {c: None for c in tabla["campos_decisivos"]}
            perfil["es_alto_riesgo"] = alto
            perfil["via_anexo"] = via
            for o in partidas:
                casos.append({"perfil": perfil, "o": o})
                if alto is True:
                    d = None if via is None else o["aplica_desde_por_via"].get(via, o["aplica_desde"])
                else:
                    d = min(o["aplica_desde_por_via"].values())
                esperado.append(d)

    guion = ("const casos = " + json.dumps(casos, ensure_ascii=False) + ";\n"
             "const fuera = casos.map(({perfil, o}) => {\n"
             "  globalThis.perfil = perfil;\n" + trozo +
             "  return desdeDe(o);\n});\n"
             "console.log(JSON.stringify(fuera));")
    tmp = RAIZ / "consola" / "__fechas.js"
    tmp.write_text(guion, encoding="utf-8")
    try:
        salida = subprocess.run(["node", str(tmp)], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout
    finally:
        tmp.unlink()
    assert json.loads(salida) == esperado

    # Y el gemelo: lo mismo, pero contra el evaluador de Python entero, para que
    # esto no se satisfaga con una funcion suelta que nadie llama.
    for cuando in (date(2026, 9, 20), date(2027, 12, 2), date(2028, 8, 2)):
        for alto in (True, False):
            for via in (None, "anexo_iii", "anexo_i"):
                perfil = {c: None for c in tabla["campos_decisivos"]}
                perfil.update({"es_alto_riesgo": alto, "via_anexo": via})
                res = evaluar_con_tabla(tabla, {"proveedor"}, perfil, cuando)
                if alto and via is None:
                    # Solo las que de verdad llegan a la pregunta de la fecha:
                    # una que no ata a este rol sale no_ata antes, y eso es
                    # correcto. Exigirlo de todas comprobaria otra cosa.
                    suyas = [o for o in partidas if "proveedor" in o["roles"]]
                    assert suyas
                    assert all(res[o["id"]] == "indeterminada" for o in suyas), \
                        "de alto riesgo y sin via, la fecha no se puede contestar"
