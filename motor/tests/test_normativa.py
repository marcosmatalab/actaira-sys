r"""Las puertas sobre la BASE NORMATIVA del catalogo, y sobre como se cita.

POR QUE ESTE FICHERO
---------------------
El catalogo borro el Anexo XIV del Reglamento y dejo escrito, en el propio
fichero, que «el Reglamento tiene TRECE anexos, del I al XIII», que el ANX-XIV
«no existe» y que todo eso estaba «contrastado contra el Diario Oficial».

Las tres frases eran falsas a la vez y por el mismo motivo: la comprobacion se
hizo contra el texto ORIGINAL del Reglamento (UE) 2024/1689 -- donde hay trece
anexos -- y no contra el texto en vigor. El Reglamento (UE) 2026/1744, publicado
el 24 de julio de 2026, inserta un Anexo XIV con los codigos AIP, AIB y AIH del
procedimiento de notificacion del articulo 30.

Lo grave no es el anexo. Es que una afirmacion normativa se publico con una
procedencia que no se puede comprobar: «contrastado contra el Diario Oficial» no
dice contra QUE VERSION, y sin esa palabra la frase no se puede ni verificar ni
desmentir. Estas puertas fijan las dos cosas -- el dato y la forma de citarlo --
porque arreglar solo el dato deja intacto el mecanismo que lo produjo.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "motor" / "src"))

CATALOGO = RAIZ / "catalogo"
OBLIGACIONES = json.loads((CATALOGO / "ai-act" / "obligaciones.json").read_text(encoding="utf-8"))

ANEXOS_EN_VIGOR = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                   "XI", "XII", "XIII", "XIV"]
"""Los anexos del Reglamento en su version consolidada con el 2026/1744.

Del I al XIII vienen del acto base. El XIV lo inserta el acto modificativo. La
lista se escribe aqui, en la puerta, y no solo en el catalogo, para que el
catalogo tenga contra que comprobarse: una lista que solo existe en el sitio que
se quiere comprobar no comprueba nada.
"""


def test_el_catalogo_trae_los_catorce_anexos_de_la_version_que_declara():
    ids = [a["id"] for a in OBLIGACIONES["anexos"]]
    assert ids == [f"ANX-{n}" for n in ANEXOS_EN_VIGOR], (
        "la lista de anexos no es la del Reglamento en vigor. Si de verdad cambio, "
        "cambia tambien ANEXOS_EN_VIGOR y di con que CELEX lo comprobaste")


def test_el_anexo_xiv_dice_quien_lo_introdujo_y_que_no_ata_a_ningun_operador():
    """Restaurarlo sin decir de donde sale seria repetir el fallo al reves.

    El Anexo XIV no obliga a un proveedor ni a un responsable del despliegue:
    es el vocabulario con el que un organismo de evaluacion de la conformidad
    pide su designacion (articulo 29) y con el que se le notifica (articulo 30).
    Por eso su `concreta` esta VACIO, y ese vacio es informacion: dice que el
    anexo existe y que no le toca a nadie de los que usan este producto, que no
    es lo mismo que no estar.
    """
    xiv = next(a for a in OBLIGACIONES["anexos"] if a["id"] == "ANX-XIV")
    assert xiv.get("introducido_por") == "32026R1744"
    assert xiv["concreta"] == [], "el Anexo XIV no concreta ninguna obligacion de operador"
    for idioma in ("es", "en"):
        assert "30" in xiv["nota"][idioma], "tiene que decir a que articulo sirve"


def test_todo_anexo_introducido_por_un_acto_posterior_lo_nombra_con_un_celex_listado():
    """Un anexo no puede venir de un acto que el instrumento no declara conocer."""
    conocidos = {m["celex"] for m in OBLIGACIONES["instrumento"]["modificado_por"]}
    for a in OBLIGACIONES["anexos"]:
        origen = a.get("introducido_por")
        if origen:
            assert origen in conocidos, (
                f"{a['id']} dice venir de {origen}, que no esta en `modificado_por`")


def test_el_instrumento_declara_hasta_donde_ha_leido():
    """`version_consolidada` es el campo cuya ausencia dejo pasar el fallo.

    Sin el, un catalogo leido contra el texto original y otro leido contra el
    texto en vigor se parecen exactamente igual desde fuera.
    """
    inst = OBLIGACIONES["instrumento"]
    assert inst["celex"] == "32024R1689"
    partes = inst["version_consolidada"].split("+")
    assert partes[0] == inst["celex"], "la version consolidada empieza por el acto base"
    declarados = [m["celex"] for m in inst["modificado_por"]]
    assert partes[1:] == declarados, (
        "`version_consolidada` y `modificado_por` no dicen lo mismo, y son la misma "
        "afirmacion escrita dos veces")
    for m in inst["modificado_por"]:
        for campo in ("celex", "url", "publicado", "en_vigor",
                      "recogido_en_este_catalogo", "no_recogido_todavia"):
            assert m.get(campo), f"{m.get('celex')} no trae `{campo}`"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", m["publicado"])
        assert "eur-lex.europa.eu" in m["url"]


def _textos(obj, ruta="") -> list[tuple[str, str]]:
    if isinstance(obj, dict):
        return [x for k, v in obj.items() for x in _textos(v, f"{ruta}.{k}")]
    if isinstance(obj, list):
        return [x for i, v in enumerate(obj) for x in _textos(v, f"{ruta}[{i}]")]
    return [(ruta, obj)] if isinstance(obj, str) else []


def test_ninguna_cita_al_diario_oficial_se_queda_sin_decir_contra_que_version():
    """La puerta que impide repetir el MECANISMO, no solo el dato.

    «Contrastada contra el Diario Oficial» era una procedencia que suena
    verificable y no lo es: el Diario Oficial publica el acto base y cada acto
    modificativo, asi que la frase es cierta de cualquier version y por tanto no
    distingue ninguna. Una cita a la fuente oficial tiene que traer al lado un
    CELEX o un enlace: algo que alguien pueda abrir y contradecir.
    """
    sin_ancla = []
    for fichero in sorted(CATALOGO.rglob("*.json")):
        d = json.loads(fichero.read_text(encoding="utf-8"))
        for ruta, texto in _textos(d):
            if not re.search(r"Diario Oficial|Official Journal", texto):
                continue
            if not re.search(r"3\d{4}[A-Z]\d{4}|eur-lex\.europa\.eu|\b\d{4}/\d{3,4}\b", texto):
                sin_ancla.append(f"{fichero.name}{ruta}")
    assert not sin_ancla, (
        f"citan el Diario Oficial sin decir contra que acto: {sin_ancla}. "
        f"Pon el CELEX o el enlace, o no es una procedencia")


def test_el_corrector_de_tildes_no_toca_lo_que_va_entre_acentos_graves():
    """En esta casa los acentos graves marcan un identificador, no prosa.

    El corrector convertia `version_consolidada` en algo con tilde, es decir,
    renombraba un campo que si existe a uno que no. Es el mismo error que ya
    estaba cazado para las palabras en mayusculas -- lo dice su propio
    comentario, «corromper un identificador mientras se arregla una tilde» --
    aplicado al otro marcador que usa el arbol.
    """
    from actaira_motor.texto.ortografia import corregir

    salida = corregir("`version_consolidada` y una version suelta")
    assert "`version_consolidada`" in salida, "renombro un identificador"
    assert "versión suelta" in salida, "y de paso dejo de corregir la prosa"


def test_el_corrector_de_tildes_no_reescribe_la_maquetacion():
    """Corregir de mas es corromper, aunque el cambio parezca inofensivo.

    Rejuntaba las oraciones con `" ".join(...)`, asi que cualquier blanco que
    siguiera a un punto se convertia en un espacio: una nota del catalogo no
    podia tener dos parrafos sin que la puerta se pusiera roja.
    """
    from actaira_motor.texto.ortografia import corregir

    texto = "Primer parrafo con una obligacion.\n\n   Segundo parrafo."
    salida = corregir(texto)
    assert salida.count("\n\n") == 1, "se comio el salto de parrafo"
    assert "   Segundo" in salida, "se comio la sangria"
    assert "obligación" in salida, "y ademas dejo de corregir"


ARTICULOS = json.loads((CATALOGO / "ai-act" / "articulos.json").read_text(encoding="utf-8"))


def test_la_cifra_de_articulos_no_se_queda_vieja():
    """Una cifra escrita en prosa que nadie vuelve a mirar es una cifra falsa.

    El campo se llamaba `por_que_estan_los_113` y decia «Estan los 113» con 115
    articulos dentro: el Reglamento (UE) 2026/1744 inserto el 4 bis y el 60 bis.
    Una cifra metida en el NOMBRE de un campo es peor todavia, porque
    actualizarla obliga a renombrar el campo, y entonces no se actualiza nunca.

    La primera version de esta puerta escaneaba todos los numeros de la nota y
    exigia que fueran el total o sus partes. Se cazo a si misma: marco el «60»
    de «articulo 60 bis». Una puerta que no distingue una cifra AFIRMADA de una
    cifra MENCIONADA acaba desactivada, asi que ahora la cifra vive en una
    estructura -- `recuento` -- y aqui se compara esa estructura con la lista de
    verdad. La prosa solo tiene que citar el total.
    """
    arts = ARTICULOS["articulos"]
    anadidos = [a["articulo"] for a in arts if not str(a["articulo"]).isdigit()]
    r = ARTICULOS["recuento"]

    assert "por_que_estan_los_113" not in ARTICULOS, (
        "el nombre del campo volvio a llevar una cifra dentro")
    assert r["total"] == len(arts)
    assert r["articulos_insertados"] == anadidos
    assert r["insertados_por_actos_modificativos"] == len(anadidos)
    assert r["del_acto_base"] + r["insertados_por_actos_modificativos"] == r["total"]

    nota = ARTICULOS["por_que_estan_todos"]
    for idioma in ("es", "en"):
        assert str(r["total"]) in nota[idioma], (
            f"la nota en {idioma} no cita el total, que es {r['total']}")


def test_la_procedencia_de_los_articulos_nombra_todos_los_actos_de_los_que_vienen():
    """Nombraba solo el acto de 2024 con articulos de 2026 dentro.

    No era falso en lo que decia: era falso en lo que dejaba de decir, que es
    como una procedencia se estropea sin que nadie la toque. Si hay un articulo
    que no es un numero -- «4a», «60a» -- es que vino de un acto modificativo, y
    ese acto tiene que estar citado.
    """
    anadidos = [a["articulo"] for a in ARTICULOS["articulos"]
                if not str(a["articulo"]).isdigit()]
    if not anadidos:
        return
    for idioma in ("es", "en"):
        texto = ARTICULOS["procedencia"][idioma]
        assert "32024R1689" in texto, "falta el CELEX del acto base"
        assert "32026R1744" in texto, (
            "hay articulos insertados por un acto modificativo y la procedencia no lo cita")


# --- roles ----------------------------------------------------------------

def test_un_rol_desconocido_revienta_en_vez_de_decir_que_no_te_ata_nada():
    """El fallo mas peligroso que tenia el producto, fijado.

    `Perfil(roles={"rol_inventado_zzz"})` resolvia sin protestar y salia con
    cero obligaciones aplicables y cuarenta y ocho no aplicables: exactamente
    el mismo documento que un rol valido al que de verdad no le ata nada. El
    motor trataba «no se quien eres» como «no te toca nada», que ademas se
    parece a una buena noticia y por eso nadie lo cuestiona.

    Se prueban los dos nombres que mandaba el panel de verdad, no solo uno
    inventado: eran nombres PLAUSIBLES, y por eso pasaron meses.
    """
    import pytest

    from actaira_motor.aplicabilidad.motor import Perfil
    from actaira_motor.roles import RolDesconocido

    for malo in ("responsable_del_despliegue", "fabricante_de_productos",
                 "rol_inventado_zzz"):
        with pytest.raises(RolDesconocido) as e:
            Perfil(roles=frozenset({malo}))
        assert malo in str(e.value), "el error no dice cual era"
        assert "proveedor" in str(e.value), "ni cuales son los validos"


def test_un_perfil_sin_roles_sigue_valiendo_porque_es_otra_cosa():
    """Arreglarlo rechazando tambien el vacio seria romper la tercera negativa.

    Sin roles es «todavia no me lo han preguntado», y `resolver` ya lo
    convierte en INDETERMINADA con la regla ROL-000. Confundir eso con un rol
    invalido seria el mismo error que se acaba de arreglar, en la otra
    direccion.
    """
    from datetime import date

    from actaira_motor.aplicabilidad.motor import Perfil, Situacion, resolver
    from actaira_motor.catalogo.cargador import cargar

    v = list(resolver(cargar(str(CATALOGO)), Perfil(), date(2027, 12, 2)))
    assert v and all(x.situacion is Situacion.INDETERMINADA for x in v)


def test_una_organizacion_puede_declarar_varios_roles_a_la_vez():
    """Lo normal es serlo de varias cosas, y la pantalla obligaba a elegir una.

    El motor siempre acepto un conjunto; el panel mandaba `[valor unico]`. Con
    eso, quien es proveedor de un sistema y responsable del despliegue de otro
    tenia que quedarse con uno y perder las obligaciones del otro.
    """
    from datetime import date

    from actaira_motor.aplicabilidad.motor import Perfil, Situacion, resolver
    from actaira_motor.catalogo.cargador import cargar

    cat = cargar(str(CATALOGO))
    def ata(*roles):
        p = Perfil(roles=frozenset(roles), es_alto_riesgo=True, via_anexo="anexo_iii")
        return {v.obligacion_id for v in resolver(cat, p, date(2027, 12, 2))
                if v.situacion is Situacion.ATA}

    solo_prov, solo_resp = ata("proveedor"), ata("responsable_despliegue")
    los_dos = ata("proveedor", "responsable_despliegue")
    assert solo_prov and solo_resp
    assert los_dos == solo_prov | solo_resp, "declarar dos roles no es la union de los dos"
    assert len(los_dos) > len(solo_prov), "anadir un rol no anadio ninguna obligacion"


def test_los_cuatro_vocabularios_de_roles_dicen_lo_mismo():
    """Habia cuatro listas escritas a mano y dos estaban mal.

    Ahora hay una fuente y derivados generados, asi que lo que hay que
    comprobar es que los derivados no se hayan quedado atras. La puerta corre
    el generador en modo comprobacion: si alguien edito el Go o el JSON del
    panel a mano, sale roja con el nombre del fichero.
    """
    import subprocess
    import sys as _sys

    r = subprocess.run([_sys.executable, str(RAIZ / "herramientas" / "generar_roles.py"),
                        "--comprobar"], cwd=RAIZ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr


def test_todo_rol_que_usa_el_catalogo_esta_declarado_en_el_vocabulario():
    """`proveedor_modelo` lo usaban cinco obligaciones y no estaba declarado.

    Un rol usado y no declarado no se puede ofrecer en ninguna pantalla, asi
    que un proveedor de modelo de uso general no tenia forma de decir que lo
    es, y no recibia ninguna de sus obligaciones.
    """
    from actaira_motor.roles import ACTORES_ESPECIALES, CANONICOS

    # Una OBLIGACION ata a roles canonicos y a nada mas: si llevara `todos`, el
    # motor no podria decidir a quien ata.
    de_obligaciones = {r for o in OBLIGACIONES["obligaciones"] for r in o.get("roles", [])}
    assert de_obligaciones <= CANONICOS, (
        f"roles usados por obligaciones y no declarados: {sorted(de_obligaciones - CANONICOS)}")

    # Un ARTICULO admite ademas el cuantificador `todos` -- ambito, definiciones,
    # entrada en vigor -- que no es un rol y no se ofrece en ninguna pantalla.
    de_articulos = {r for a in ARTICULOS["articulos"] for r in a.get("actores", [])}
    permitidos = CANONICOS | ACTORES_ESPECIALES
    assert de_articulos <= permitidos, (
        f"actores usados por articulos y no declarados: {sorted(de_articulos - permitidos)}")
    assert set(OBLIGACIONES["roles"]) == CANONICOS, (
        "la lista declarada en el catalogo y el vocabulario del motor no coinciden")


def test_no_queda_ningun_requisito_del_reglamento_sin_cubrir():
    """Los dos huecos que la auditoria conto, cerrados, y la puerta que lo fija.

    Eran `AIA-R-009-05` (menores y colectivos vulnerables, articulo 9.9) y
    `AIA-R-026-04` (informar a los trabajadores y a las personas, articulo 26.7
    y 26.11). Los dos estaban catalogados con su `por_que_no_esta_cubierto`
    escrito, que es honesto y no es lo mismo que cubrirlos.

    El segundo reservaba que la pregunta la escribiera alguien de Derecho
    laboral. Esa reserva era buena para no improvisar la NORMA -- que varia por
    Estado miembro -- y mala para no hacer la PREGUNTA: lo que no varia es que
    el articulo obliga a informar y que quien despliega sabe si lo hizo, cuando
    y por que cauce. Se pregunta eso, se pide el Estado miembro, y se dice
    expresamente que la suficiencia del cauce la juzga quien conozca esa
    legislacion.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ / "motor" / "src"))
    from actaira_motor.catalogo.cargador import cargar

    c = cargar(str(CATALOGO))
    huecos = [r.id for r in c.huecos_de_cobertura()]
    assert huecos == [], f"requisitos sin control ni pregunta: {huecos}"


def test_el_corrector_no_convierte_una_conjuncion_en_un_interrogativo():
    """Acentuar `cuando` no es una errata: cambia lo que dice la frase.

    «Cuando el sistema decide sobre una persona, ¿como se le informa?» salia
    como «¿Cuando el sistema decide...», que pregunta EN QUE MOMENTO en vez de
    decir SIEMPRE QUE OCURRA. Y de paso le ponia un segundo signo de apertura a
    una oracion que ya abria la pregunta por la mitad, que es castellano
    correcto.

    La regla que faltaba: si la oracion trae un signo de apertura, la pregunta
    empieza ahi y lo de delante es preambulo.
    """
    from actaira_motor.texto.ortografia import corregir

    salida = corregir("Cuando el sistema decide sobre una persona, \u00bfcomo se le informa?")
    assert salida.startswith("Cuando el sistema"), salida
    assert salida.count("\u00bf") == 1, salida
    assert "\u00bfc\u00f3mo" in salida, "y el interrogativo de dentro SI se acentua"


def test_una_senal_de_presencia_no_se_publica_como_si_fuera_de_comportamiento():
    """No todas las comprobaciones pesan lo mismo, y el informe las imprimia igual.

    La auditoria externa lo puso asi: encontrar `dataset-card.md` no demuestra
    que el origen de los datos sea licito, ni que la representatividad este
    evaluada, ni que los sesgos esten dentro de umbrales aprobados. Es exacto.

    El arreglo no es dejar de mirar el fichero -- su ausencia es un hallazgo de
    verdad -- sino dejar de presentar las dos cosas con la misma cara. Una
    regla que casa una LLAMADA en el arbol sintactico afirma algo sobre lo que
    el programa HACE; una que casa un nombre de fichero afirma que el artefacto
    esta. Ahora cada senal dice cual de las dos es, y el plan lo publica.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ / "motor" / "src"))
    from actaira_motor.controles.motor import FUERZA_POR_TIPO, TIPOS
    from actaira_motor.resultado.observacion import FUERZAS

    # Todo tipo de regla declara su fuerza: si manana se anade uno y nadie lo
    # clasifica, esto se pone rojo en vez de dejarlo caer en la mas fuerte.
    assert set(FUERZA_POR_TIPO) == set(TIPOS), (
        f"tipos sin fuerza declarada: {set(TIPOS) - set(FUERZA_POR_TIPO)}")
    assert set(FUERZA_POR_TIPO.values()) <= set(FUERZAS)
    assert FUERZA_POR_TIPO["fichero"] == "presencia"
    assert FUERZA_POR_TIPO["contenido"] == "presencia"
    assert FUERZA_POR_TIPO["llamada"] == "comportamiento"


def test_el_plan_publica_de_que_clase_es_cada_comprobacion():
    from datetime import date
    import sys as _sys

    _sys.path.insert(0, str(RAIZ / "motor" / "src"))
    from actaira_motor.aplicabilidad.motor import Perfil
    from actaira_motor.catalogo.cargador import cargar
    from actaira_motor.formularios.plan import construir
    from actaira_motor.resultado.observacion import FUERZAS

    plan = construir(
        cargar(str(CATALOGO)),
        Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii"),
        date(2027, 12, 2),
        str(RAIZ / "motor" / "tests" / "fixtures" / "clasificador-candidatos"),
        str(CATALOGO / "reglas"))

    assert set(plan["recuento_por_fuerza"]) == set(FUERZAS)
    assert plan["recuento_por_fuerza"]["presencia"] > 0, (
        "si ninguna sale como presencia, la clasificacion no se esta aplicando")
    assert plan["recuento_por_fuerza"]["comportamiento"] > 0, (
        "y si ninguna sale como comportamiento, se clasifico todo con la mas debil")
    for linea in plan["lineas"]:
        if linea["fuerzas"]:
            # La maxima es la mas fuerte de las que hay, y el desglose las trae
            # todas: publicar solo la maxima dejaria leer «comportamiento» sobre
            # una obligacion con ocho senales de presencia y una de llamada.
            assert linea["fuerza_maxima"] == next(f for f in FUERZAS if f in linea["fuerzas"])
    for idioma in ("es", "en"):
        assert plan["nota_de_fuerza"][idioma].strip()


# --- ISO/IEC 42001 --------------------------------------------------------

def test_los_38_controles_del_anexo_a_tienen_pregunta():
    """Diez no la tenian, y una auditoria externa los conto uno a uno.

    Eran A.4.3, A.4.4, A.4.5, A.5.3, A.6.1.3, A.6.2.3, A.6.2.8, A.7.2, A.9.2 y
    A.9.4: los recursos (datos, herramientas y computo), la documentacion de la
    evaluacion de impacto, los procesos de diseno responsable y su
    documentacion, el registro de acontecimientos, los datos de desarrollo, el
    uso responsable y el uso previsto.

    Un control del Anexo A sin pregunta no es un control que falle: es uno del
    que no se puede decir nada, y la declaracion de aplicabilidad lo arrastra
    como si estuviera.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ / "motor" / "src"))
    from actaira_motor.catalogo.cargador import cargar

    c = cargar(str(CATALOGO))
    sin = sorted(cid for cid in c.controles_iso
                 if not any(cid in q.sirve_a for q in c.preguntas.values()))
    assert sin == [], f"controles del Anexo A sin ninguna pregunta que los toque: {sin}"


def test_el_corrector_no_acentua_un_que_que_subordina():
    """«Se enteran de QUE alguien se las salta» no pregunta, y salio con tilde.

    Ademas de cambiar el sentido es agramatical: el `que` interrogativo
    determina un sustantivo o va solo antes de un verbo, y no puede preceder a
    un pronombre indefinido. La lista que lo impide se amplio dos veces --
    primero cliticos y articulos, luego indefinidos -- y por eso ahora sigue una
    regla gramatical en vez de enumerar los casos que alguien vio fallar.
    """
    from actaira_motor.texto.ortografia import corregir

    assert "de que alguien" in corregir(
        "\u00bfComo se enteran de que alguien se las salta?")
    assert "de que la tienen" in corregir("\u00bfQue evidencia tiene de que la tienen?")
    assert "que su equipo" in corregir("\u00bfComo saben que su equipo lo revisa?")
    # Y la otra mitad: los que SI preguntan siguen acentuandose.
    assert "\u00bfDe qu\u00e9 sirve" in corregir("\u00bfDe que sirve un control que nadie mira?")
    assert "\u00bfQu\u00e9 sistema" in corregir("\u00bfQue sistema usan?")
