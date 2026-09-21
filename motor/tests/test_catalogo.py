"""El catalogo es contenido normativo: si miente, todo lo de arriba miente."""
import dataclasses
import json
import pytest
from pathlib import Path
from conftest import CATALOGO
from actaira_motor.catalogo.cargador import cargar, ErrorDeCatalogo


@pytest.fixture(scope="module")
def cat():
    return cargar(CATALOGO)


def test_el_cruce_no_tiene_pares_rotos(cat):
    assert cat.verificar_cruce() == []


def test_todo_esta_en_los_dos_idiomas(cat):
    for o in cat.obligaciones.values():
        assert o.titulo["es"].strip() and o.titulo["en"].strip(), o.id
    for c in cat.controles_iso.values():
        assert c.titulo["es"].strip() and c.titulo["en"].strip(), c.id


def test_ninguna_obligacion_de_nivel_maquina_se_queda_sin_decir_que_comprueba(cat):
    sin = [o.id for o in cat.por_nivel("maquina") if not o.comprueba]
    assert sin == [], f"nivel maquina sin lista de comprobaciones: {sin}"


def test_toda_obligacion_que_no_es_de_nivel_maquina_dice_por_que_no(cat):
    """La escalera solo vale si cada peldano justifica por que no sube mas."""
    faltan = []
    for o in cat.obligaciones.values():
        if o.nivel == "maquina":
            continue
        b = o.bruto or {}
        if not any(k in b for k in ("por_que_no_mas", "nota_iso", "frontera_dura", "genera", "cruce_tecnico", "parte_tecnica")):
            faltan.append(o.id)
    assert faltan == [], f"sin justificar por que no es comprobable por maquina: {faltan}"


def test_ninguna_fecha_del_catalogo_es_anterior_a_la_entrada_en_vigor(cat):
    from datetime import date
    for o in cat.obligaciones.values():
        assert o.aplica_desde >= date(2024, 8, 1), o.id


def test_el_cargador_falla_ruidosamente_y_nombra_el_campo(tmp_path):
    (tmp_path / "ai-act").mkdir(); (tmp_path / "iso42001").mkdir()
    (tmp_path / "ai-act" / "obligaciones.json").write_text(json.dumps(
        {"obligaciones": [{"id": "X-1", "articulo": "1", "titulo": {"es": "a", "en": "b"},
                           "roles": ["proveedor"], "aplica_desde": "2026-01-01", "alcance": "todo_sistema"}]}))
    (tmp_path / "iso42001" / "anexo-a.json").write_text(json.dumps({"controles": []}))
    (tmp_path / "crosswalk.json").write_text(json.dumps({"pares": []}))
    with pytest.raises(ErrorDeCatalogo) as e:
        cargar(tmp_path)
    assert "nivel" in str(e.value) and "X-1" in str(e.value)


def test_un_catalogo_que_no_esta_no_devuelve_vacio_sino_error(tmp_path):
    """Regla 11: nunca caer al extremo seguro en silencio."""
    with pytest.raises(ErrorDeCatalogo):
        cargar(tmp_path / "no-existe")


def test_el_castellano_del_catalogo_lleva_tildes():
    """La puerta de la fase 7. Vuelve a aplicar la correccion y exige que no cambie.

    El catalogo se escribio sin tildes, que es comodo al teclear e indefendible
    en el producto: un sistema que le dice a una empresa espanola "evaluacion de
    la conformidad segun el articulo 43" pierde su unica credibilidad antes de
    la segunda linea. Se corrigio de una pasada y esto impide que vuelva a
    entrar texto sin tildes con la siguiente obligacion que se anada.
    """
    import json
    from pathlib import Path

    from actaira_motor.texto.ortografia import corregir_es

    raiz = Path(__file__).resolve().parents[2] / "catalogo"
    sucios = [str(r.relative_to(raiz)) for r in sorted(raiz.rglob("*.json"))
              if (d := json.loads(r.read_text(encoding="utf-8"))) != corregir_es(d)]
    assert sucios == [], f"corre `actaira ortografia --arreglar`: {sucios}"


def test_la_correccion_de_tildes_no_toca_el_ingles():
    """El gemelo, y encontro algo: `corregir` aplicada a ingles lo destroza.

    "information" sale "informatión". Por eso la que se expone al catalogo es
    `corregir_es`, que decide a que campos se aplica, y esa decision vive en un
    solo sitio en vez de repetirse en el CLI y en esta puerta.
    """
    from actaira_motor.texto.ortografia import corregir, corregir_es
    ing = {"titulo": {"es": "La evaluacion de la organizacion",
                      "en": "The evaluation of the organization"}}
    assert corregir_es(ing)["titulo"]["en"] == "The evaluation of the organization"
    assert corregir_es(ing)["titulo"]["es"] == "La evaluación de la organización"
    # y el paso mecanico por si solo no acentua un plural
    assert corregir("las obligaciones y sus decisiones") == "las obligaciones y sus decisiones"
    assert corregir("la obligacion y su decision") == "la obligación y su decisión"


def test_la_correccion_es_idempotente():
    """Aplicarla dos veces da lo mismo, o la puerta no podria compararse con ella."""
    from actaira_motor.texto.ortografia import corregir
    t = "El sistema de gestion: que separa un riesgo aceptable de otro? La evaluacion."
    assert corregir(corregir(t)) == corregir(t)


def test_el_catalogo_se_encuentra_en_los_tres_sitios(monkeypatch, tmp_path):
    """La resolucion del catalogo, que estaba mal y el sintoma habria sido feo.

    `RAIZ = parents[3]` funciona en el arbol de desarrollo y apunta a
    `site-packages/catalogo` cuando el paquete se instala con pip, que no
    existe. La plantilla de integracion continua dice `pip install
    actaira-motor`, asi que el primer cliente que la copiara se habria
    encontrado con que el verbo no arranca.
    """
    from actaira_motor.cli import _localizar_catalogo

    monkeypatch.setenv("ACTAIRA_CATALOGO", str(tmp_path / "mio"))
    assert _localizar_catalogo() == tmp_path / "mio"

    monkeypatch.delenv("ACTAIRA_CATALOGO")
    # sin variable y sin copia empaquetada, el arbol de desarrollo
    resuelto = _localizar_catalogo()
    assert (resuelto / "ai-act" / "obligaciones.json").is_file()


def test_el_pyproject_lleva_el_catalogo_dentro_de_la_rueda():
    """El gemelo del anterior: si el catalogo no viajara, la resolucion daria
    igual. Se comprueba la declaracion, no la rueda, porque construirla en cada
    pasada de tests cuesta diez segundos; `make paquete` la construye de verdad
    y corre el verbo contra ella."""
    from pathlib import Path as P
    t = (P(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    assert '"catalogo" = "actaira_motor/_catalogo"' in t
    assert 'actaira = "actaira_motor.cli:main"' in t
    assert 'license = "Apache-2.0"' in t


def test_una_tuberia_cerrada_no_produce_un_traceback():
    """El punto de entrada que instala pip llama a `main()` directamente, asi
    que el `except` que vivia en `__main__` no lo cubria: el primer cliente que
    hiciera `actaira plan . | head -3` habria visto un traceback de un producto
    de cumplimiento."""
    import inspect
    from actaira_motor import cli
    fuente = inspect.getsource(cli.main)
    assert "BrokenPipeError" in fuente, "la captura tiene que estar dentro de main()"


def test_el_castellano_que_vive_en_el_codigo_tambien_lleva_tildes():
    """La puerta del catalogo no veia esto, y el contrato de la fase 11 lo destapo.

    No todo el castellano que ve un cliente sale del catalogo: los motivos de
    ausencia del Anexo IV, las notas de las declaraciones y los encabezados de
    los documentos se escriben en Python. El expediente decia «no se encontro
    ninguna declaracion de dependencias» delante de un auditor.
    """
    from pathlib import Path as P

    from actaira_motor.texto.codigo import sucios

    raiz = P(__file__).resolve().parents[1] / "src"
    assert sucios(raiz) == [], "corre `actaira ortografia --arreglar`"


def test_el_corrector_de_codigo_no_entra_en_las_llaves_de_una_fstring():
    """Costo un identificador: `tokenize` entrega una f-string entera como un
    solo token, asi que corregirla acentuaba tambien lo de dentro de las llaves
    y `_CLAUSULA_FUENTE` se convirtio en `_Cláusula_FUENTE`. Una herramienta que
    arregla la ortografia y rompe el programa no la usa nadie dos veces."""
    from actaira_motor.texto.codigo import _corregir_fuera_de_llaves as f

    dentro = '''f"{_CLAUSULA_FUENTE['es']}: la evaluacion de la organizacion"'''
    assert f(dentro) == '''f"{_CLAUSULA_FUENTE['es']}: la evaluación de la organización"'''
    assert f('"{{literal}} la version"') == '"{{literal}} la versión"'


def test_el_corrector_de_codigo_no_toca_lo_que_no_es_para_una_persona():
    """El gemelo: un `.py` esta lleno de cadenas que NO son para el cliente.
    Identificadores, expresiones regulares y claves de diccionario se quedan
    como estan, o el programa deja de funcionar."""
    from actaira_motor.texto.codigo import corregir_fuente

    fuente = ('PATRON = "(?i)documentacion"\n'
              'CLAVES = {"obligacion": 1, "version": 2}\n'
              'def f():\n    """Un docstring con evaluacion y organizacion."""\n')
    assert corregir_fuente(fuente) == fuente


def test_no_hay_interrogativos_acentuados_donde_subordinan():
    """La puerta de las tildes no ve esto, y por eso hace falta esta.

    `corregir` es idempotente: sobre un texto que YA lleva tilde no cambia
    nada, asi que una tilde puesta de mas en una pasada anterior se queda para
    siempre y la puerta sigue diciendo que todo esta bien. La primera version
    de la regla acentuaba «que evidencia tiene DE QUÉ LA tienen», que subordina
    y no pregunta, y salio impresa en una pregunta del cuestionario.

    La lista de cliticos se estrecho en la fase 17, y no por gusto: la version
    ancha quito la tilde de dos preguntas legitimas seguidas -- «¿a qué se
    comprometió?» y «¿de qué se aprueba y qué no?» -- y las dos veces costo
    reescribir la frase para esquivar al corrector, que es exactamente al reves
    de para lo que esta. Con un clitico de objeto y un verbo transitivo la
    oracion subordina; con `se` la construccion es impersonal o refleja y lee
    como pregunta indirecta casi siempre.
    """
    import json
    import re
    from pathlib import Path as P

    raiz = P(__file__).resolve().parents[2]
    malo = re.compile(r"\b(de|a|en|con|por|para|sin|sobre) qué (la|lo|le|los|las|les)\b")
    culpables = []
    for ruta in sorted((raiz / "catalogo").rglob("*.json")):
        for m in malo.finditer(ruta.read_text(encoding="utf-8")):
            culpables.append(f"{ruta.name}: {m.group(0)}")
    assert culpables == [], culpables


# --- la cobertura del Reglamento, comprobada articulo a articulo -----------

def test_estan_los_113_articulos_y_ninguno_se_repite():
    """La cobertura deja de ser una afirmacion comercial y pasa a ser una lista.

    Un catalogo que solo lista los articulos que sabe comprobar no puede
    contestar «y el articulo 46?». Estan los 113 del texto de 2024, cada uno
    diciendo a quien ata y, si no ata a un cliente, por que. Esa es la
    diferencia entre decir que se cubre el Reglamento entero y poder recorrerlo
    delante de alguien.
    """
    d = json.loads((Path(CATALOGO) / "ai-act" / "articulos.json").read_text(encoding="utf-8"))
    originales = sorted(int(a["articulo"]) for a in d["articulos"] if not a.get("anadido_por"))
    assert originales == list(range(1, 114)), sorted(set(range(1, 114)) - set(originales))
    ids = [a["articulo"] for a in d["articulos"]]
    assert len(ids) == len(set(ids)), "hay un articulo repetido"


def test_los_articulos_que_no_estaban_en_2024_lo_dicen():
    """Un articulo anadido por una modificacion posterior no puede parecer que
    estaba en el texto original: quien cite el Reglamento de 2024 buscando el
    4 bis no lo encontrara, y tiene que saber por que."""
    d = json.loads((Path(CATALOGO) / "ai-act" / "articulos.json").read_text(encoding="utf-8"))
    anadidos = [a for a in d["articulos"] if a.get("anadido_por")]
    assert anadidos, "el Reglamento (UE) 2026/1744 anadio articulos y no estan"
    for a in anadidos:
        assert a["anadido_por"].startswith("Reglamento (UE)"), a["articulo"]
        assert not a["articulo"].isdigit(), \
            f"{a['articulo']}: un articulo bis se numera como bis, no como uno mas"


def test_todo_articulo_que_no_ata_a_un_cliente_dice_por_que():
    d = json.loads((Path(CATALOGO) / "ai-act" / "articulos.json").read_text(encoding="utf-8"))
    for a in d["articulos"]:
        if a["en_alcance_del_producto"]:
            continue
        por_que = a.get("por_que_no_ata_a_un_cliente")
        assert por_que and por_que.get("es") and por_que.get("en"), a["articulo"]


def test_todo_articulo_que_ata_a_un_operador_tiene_su_obligacion():
    """El agujero que esto cierra es el que encontro la auditoria externa.

    Se puede catalogar un articulo, marcarlo «ata a un operador» y no
    construirle nada. Entonces la lista esta completa y el producto no, que es
    la peor combinacion posible: parece cubierto y no se pregunta nunca.
    """
    d = json.loads((Path(CATALOGO) / "ai-act" / "articulos.json").read_text(encoding="utf-8"))
    o = json.loads((Path(CATALOGO) / "ai-act" / "obligaciones.json").read_text(encoding="utf-8"))
    con_obligacion = {x["articulo"] for x in o["obligaciones"]}
    faltan = [a["articulo"] for a in d["articulos"]
              if a["vincula"] in ("operador", "derecho") and a["articulo"] not in con_obligacion]
    assert faltan == [], f"atan a un operador y no tienen obligacion construida: {faltan}"


def test_y_ninguna_obligacion_nombra_un_articulo_que_no_existe():
    """El gemelo: la integridad referencial en la otra direccion."""
    d = json.loads((Path(CATALOGO) / "ai-act" / "articulos.json").read_text(encoding="utf-8"))
    o = json.loads((Path(CATALOGO) / "ai-act" / "obligaciones.json").read_text(encoding="utf-8"))
    conocidos = {a["articulo"] for a in d["articulos"]}
    huerfanas = [x["id"] for x in o["obligaciones"] if x["articulo"] not in conocidos]
    assert huerfanas == []


def test_el_indice_de_articulos_dice_de_donde_sale_cada_cosa():
    """Incluida la parte que NO se extrajo de un documento en esta maquina."""
    d = json.loads((Path(CATALOGO) / "ai-act" / "articulos.json").read_text(encoding="utf-8"))
    p = d["procedencia"]
    assert "Diario Oficial" in p["es"] and "Official Journal" in p["en"]
    assert "NO se extrajeron" in p["es"], "la deuda de los titulos en ingles tiene que estar dicha"


# --- los requisitos atomicos, y el mapa de cobertura -----------------------

def _requisitos():
    return json.loads((Path(CATALOGO) / "ai-act" / "requisitos.json").read_text(encoding="utf-8"))


def test_todo_articulo_en_alcance_tiene_al_menos_un_requisito():
    """Sin esto, «cobertura total» significa lo que cada uno quiera.

    Un articulo puede estar catalogado, tener obligacion y no haberse partido
    en deberes: entonces la suficiencia se decide por articulo, y un articulo
    con seis deberes se cierra entero porque uno esta cubierto. Es la manera
    mas rapida de emitir un expediente falso.
    """
    arts = json.loads((Path(CATALOGO) / "ai-act" / "articulos.json").read_text(encoding="utf-8"))
    con_requisito = {r["articulo"] for r in _requisitos()["requisitos"]}
    faltan = [a["articulo"] for a in arts["articulos"]
              if a["en_alcance_del_producto"] and a["articulo"] not in con_requisito]
    assert faltan == [], f"en alcance y sin partir en requisitos: {faltan}"


def test_todo_requisito_nombra_un_articulo_que_existe():
    arts = {a["articulo"] for a in json.loads(
        (Path(CATALOGO) / "ai-act" / "articulos.json").read_text(encoding="utf-8"))["articulos"]}
    huerfanos = [r["id"] for r in _requisitos()["requisitos"] if r["articulo"] not in arts]
    assert huerfanos == []


def test_lo_que_dice_cubrir_un_requisito_existe_de_verdad():
    """Integridad referencial del mapa de cobertura.

    Un mapa que apunta a una regla que nadie escribio es peor que no tener
    mapa: enseña una cobertura que no hay, y nadie la busca porque el mapa
    dice que esta.
    """
    import glob
    conocidos = set()
    for f in glob.glob(str(Path(CATALOGO) / "formularios" / "*.json")):
        conocidos |= {q["id"] for q in json.load(open(f, encoding="utf-8"))["preguntas"]}
    for f in glob.glob(str(Path(CATALOGO) / "reglas" / "*.json")):
        conocidos |= {r["id"] for r in json.load(open(f, encoding="utf-8"))["reglas"]}
    rotos = [(r["id"], c) for r in _requisitos()["requisitos"]
             for c in r["cubierto_por"] if c not in conocidos]
    assert rotos == [], rotos


def test_un_requisito_sin_cubrir_tiene_que_decir_por_que():
    """La puerta que convierte un hueco en algo que se ve.

    Un mapa de cobertura que solo enseña lo cubierto no es un mapa de
    cobertura. Lo que no esta cubierto lleva su motivo escrito, o no entra.
    """
    for r in _requisitos()["requisitos"]:
        if r["cubierto_por"]:
            continue
        por_que = r.get("por_que_no_esta_cubierto")
        assert por_que and por_que.get("es") and por_que.get("en"), r["id"]
        assert len(por_que["es"]) > 60, f"{r['id']}: el motivo tiene que explicar, no despachar"


def test_y_los_huecos_son_pocos_y_conocidos():
    """El gemelo: «di por que» se satisface tambien dejandolo todo sin cubrir.

    Este numero es el que tiene que bajar. Si sube, la puerta de arriba seguiria
    verde -- cada hueco con su motivo -- y la cobertura habria empeorado en
    silencio, que es exactamente el modo de fallo que la regla 9 persigue.
    """
    rs = _requisitos()["requisitos"]
    sin = [r["id"] for r in rs if not r["cubierto_por"]]
    assert len(sin) <= 4, sin
    assert len(sin) / len(rs) < 0.1, f"{len(sin)} de {len(rs)} requisitos sin cubrir"


def test_cada_requisito_dice_a_quien_ata_y_en_que_nivel():
    from actaira_motor.catalogo.cargador import NIVELES
    roles = {"proveedor", "responsable_despliegue", "importador", "distribuidor",
             "representante_autorizado", "fabricante_producto", "proveedor_modelo"}
    for r in _requisitos()["requisitos"]:
        assert r["actores"], r["id"]
        assert set(r["actores"]) <= roles, (r["id"], set(r["actores"]) - roles)
        assert r["nivel"] in NIVELES, (r["id"], r["nivel"])
        assert r["apartados"], f"{r['id']}: un requisito dice de que apartados sale"
        assert r["exige"]["es"] and r["exige"]["en"], r["id"]


def test_lo_que_cubre_un_requisito_habla_de_su_articulo():
    """La pasada adversarial de la fase 15 encontro ocho citas que no.

    Un requisito del articulo 50 citando una pregunta sobre el origen de los
    datos del articulo 10 pasa las dos puertas anteriores -- la referencia
    existe y el requisito tiene cobertura -- y no cubre nada. Es el tipo de
    error que solo se ve cruzando dos ficheros, y por eso hay que cruzarlos.

    Una cita a otro articulo NO esta prohibida: la reevaluacion del 43(4) se
    dispara con la modificacion sustancial, que es lo que define el 25, y
    escribir una regla gemela habria creado dos definiciones de lo mismo. Pero
    tiene que estar DICHA.
    """
    import glob

    reglas, preguntas = {}, {}
    for f in glob.glob(str(Path(CATALOGO) / "reglas" / "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for r in d["reglas"]:
            reglas[r["id"]] = d["obligacion"]
    for f in glob.glob(str(Path(CATALOGO) / "formularios" / "*.json")):
        for q in json.load(open(f, encoding="utf-8"))["preguntas"]:
            preguntas[q["id"]] = set(q["sirve_a"])
    obl = {o["articulo"]: o["id"] for o in json.loads(
        (Path(CATALOGO) / "ai-act" / "obligaciones.json").read_text(encoding="utf-8"))["obligaciones"]}

    cruzadas = []
    for r in _requisitos()["requisitos"]:
        mia = obl.get(r["articulo"])
        for c in r["cubierto_por"]:
            fuera = (c in reglas and reglas[c] != mia) or \
                    (c in preguntas and mia and mia not in preguntas[c])
            if fuera and not r.get("nota_de_cobertura"):
                cruzadas.append((r["id"], c))
    assert cruzadas == [], f"citan algo de otro articulo y no dicen por que: {cruzadas}"


def test_el_gemelo_una_cita_cruzada_con_su_nota_si_pasa():
    """Si no, la puerta de arriba se cumple prohibiendo el cruce, y entonces
    habria que duplicar la definicion de «modificacion sustancial»."""
    con_nota = [r for r in _requisitos()["requisitos"] if r.get("nota_de_cobertura")]
    assert con_nota, "ninguna cita cruzada: esta prueba no comprueba nada"
    for r in con_nota:
        assert r["nota_de_cobertura"]["es"] and r["nota_de_cobertura"]["en"]
        assert len(r["nota_de_cobertura"]["es"]) > 80


# --- el SGIA como sistema, no como lista ----------------------------------

def test_el_sistema_de_gestion_es_un_ciclo_que_cierra(cat):
    """Un sistema de gestión es un CICLO: lo que produce una cláusula lo
    consume otra, y lo que sale del final vuelve a entrar por el principio.

    Sin eso, las 32 cláusulas son 32 casillas marcables en cualquier orden y
    ninguna obliga a la siguiente: la 10.2 producía un registro de no
    conformidades que nadie consumía.
    """
    assert cat.verificar_sistema_de_gestion() == []


def test_el_gemelo_la_puerta_del_ciclo_muerde(cat):
    """Regla 9: una puerta que nunca ha visto fallar no vale nada."""
    import copy

    roto = copy.deepcopy(cat)
    roto.clausulas["ISO-10.2"] = dataclasses.replace(roto.clausulas["ISO-10.2"], alimenta=())
    problemas = roto.verificar_sistema_de_gestion()
    assert problemas, "romper el retorno de la 10.2 tiene que verse"
    assert any("el ciclo no cierra" in p for p in problemas), problemas


def test_y_muerde_tambien_si_las_dos_direcciones_discrepan(cat):
    """Cada dirección puede ser coherente consigo misma y estar en desacuerdo
    con la otra. Es como el cruce de catálogos acumuló 30 asimetrías."""
    import copy

    roto = copy.deepcopy(cat)
    roto.clausulas["ISO-6.1.1"] = dataclasses.replace(
        roto.clausulas["ISO-6.1.1"], alimenta=("ISO-9.1",))
    problemas = roto.verificar_sistema_de_gestion()
    assert any("tienen que decir lo mismo" in p for p in problemas), problemas


def test_toda_clausula_que_pide_registros_dice_de_que(cat):
    """Un sistema que pide guardar información documentada sin decir cuál
    produce una carpeta con documentos y ninguna manera de saber si falta uno."""
    mudas = [c.id for c in cat.clausulas.values()
             if c.exige_informacion_documentada and not c.produce]
    assert mudas == [], mudas


def test_las_clausulas_que_recurren_llevan_su_vigencia(cat):
    """Una auditoría interna de hace tres años no es una auditoría interna.

    La maquinaria de caducidad que ya existe para la evidencia técnica vale
    igual para los registros de gestión, y esto es lo que la conecta.
    """
    for cid in ("ISO-9.2.2", "ISO-9.3.3", "ISO-9.1", "ISO-10.2"):
        c = cat.clausulas[cid]
        assert c.periodicidad in ("continua", "anual", "por_cambio"), cid
        assert 0 < c.vigencia_dias <= 365, (cid, c.vigencia_dias)
    # Y las que se rehacen por cambio no fingen una fecha fija.
    assert cat.clausulas["ISO-6.1.4"].periodicidad == "por_cambio"
