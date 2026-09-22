"""El control del articulo 50: lo que puede afirmar y lo que se niega a afirmar."""
from pathlib import Path
import pytest
from actaira_motor.controles.art50 import Entrada, correr
from actaira_motor.controles.marcado import write_marking, read_facts
from actaira_motor.controles.modelo import Resultado

RAIZ = Path(__file__).resolve().parents[2]
REGLAS = RAIZ / "catalogo" / "reglas" / "art50.json"
FIX = Path(__file__).parent / "fixtures"


def test_un_repo_sin_generacion_no_aplica_y_dice_que_miro():
    r = correr(Entrada(FIX / "repo-limpio"), REGLAS)
    assert r.resultado is Resultado.NO_APLICA
    assert any("ficheros analizados" in c for c in r.cubre), r.cubre
    assert r.no_cubre, "un NO_APLICA tambien tiene frontera"
    # Desde la fase 14, «no aplica» es un hecho de EJECUCION y lleva su motivo:
    # sin el, es indistinguible de haber mirado el marcado y no encontrar nada.
    assert r.ejecucion.estado.value == "no_aplicable"
    assert "No es que se mirara" in r.ejecucion.motivo["es"]


def test_generar_sin_aportar_artefactos_nunca_produce_un_hallazgo_de_marcado():
    """Sin los bytes de salida, el marcado NO se puede decidir. Tercera negativa.

    Hasta la fase 14 esto se comprobaba mirando que el resultado fuera
    INDETERMINADO, y eso escondia una confusion: en este fixture SI hay
    hallazgos reales -- generacion de texto sin divulgacion -- que son otra
    regla y otra pregunta. Fundirlos hacia que un hallazgo de verdad
    desapareciera del informe porque otra cosa no se podia decidir.

    La propiedad que importa es mas fina y es esta: no hay ni un hallazgo de
    marcado ausente, la suficiencia sobre el marcado es INDETERMINADA, y el
    motivo dice en los dos idiomas que falta aportar.
    """
    r = correr(Entrada(FIX / "repo-con-generacion"), REGLAS)
    assert not any(h.regla_id == "ACT-50-MARCA-AUSENTE" for h in r.hallazgos)
    assert r.suficiencia is not None
    assert r.suficiencia.estado.value == "indeterminada"
    assert not r.suficiencia.estado.afirma_cumplimiento
    assert "no se aportó ningún artefacto" in r.motivo_indeterminado["es"]
    assert "servicio.py:6" in r.motivo_indeterminado["es"]
    assert "servicio.py:6" in r.motivo_indeterminado["en"]
    assert r.suficiencia.falta and r.suficiencia.falta[0].que_hacer["en"]


def test_y_los_puntos_de_generacion_salen_como_senales_no_solo_como_prosa():
    """El gemelo: lo que SI se vio tiene que ser un dato consultable."""
    r = correr(Entrada(FIX / "repo-con-generacion"), REGLAS)
    assert r.observacion.senales, "los puntos de generacion son lo observado"
    ids = {s.regla_id for s in r.observacion.senales}
    assert ids & {"ACT-50-GEN-IMG", "ACT-50-GEN-TXT", "ACT-50-BOT"}
    for s in r.observacion.senales:
        assert ":" in s.localizacion, "una senal dice DONDE"
        assert set(s.que_se_buscaba) == {"es", "en"}


def test_una_cadena_que_parece_una_firma_no_dispara(tmp_path):
    """El argumento del AST frente a grep, con su caso."""
    (tmp_path / "x.py").write_text('DOC = "usa client.images.generate y ya"\n')
    r = correr(Entrada(tmp_path), REGLAS)
    assert r.resultado is Resultado.NO_APLICA


def test_un_artefacto_sin_marcar_es_no_cumple_con_su_hallazgo(tmp_path):
    from PIL import Image
    art = tmp_path / "salida.png"
    Image.new("RGB", (24, 24), (3, 3, 3)).save(art)
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,)), REGLAS)
    assert r.resultado is Resultado.CON_HALLAZGOS
    ids = {h.regla_id for h in r.hallazgos}
    assert "ACT-50-MARCA-AUSENTE" in ids


def test_un_artefacto_marcado_no_produce_hallazgo_de_marcado_y_publica_su_frontera(tmp_path):
    """El marcado leido byte a byte se registra como SENAL, no como silencio.

    Esta prueba decia `resultado is SIN_HALLAZGOS` y ESO ERA EL DEFECTO: el
    fixture tiene ademas una llamada de generacion de texto que produce su
    propio hallazgo, y el control lo llevaba en la lista mientras devolvia
    SIN_HALLAZGOS. La propiedad que de verdad importa aqui es que no hay
    hallazgo de MARCADO y que el marcado observado aparece como senal.
    """
    from PIL import Image
    art = tmp_path / "salida.png"
    Image.new("RGB", (24, 24), (3, 3, 3)).save(art)
    write_marking(art)
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,)), REGLAS)
    assert not any(h.regla_id == "ACT-50-MARCA-AUSENTE" for h in r.hallazgos)
    assert any(s.localizacion == "salida.png" for s in r.observacion.senales)
    assert r.observacion.id in r.suficiencia.se_apoya_en, \
        "el marcado leido byte a byte cuenta como apoyo"
    assert not r.suficiencia.estado.afirma_cumplimiento
    # No sale «suficiente» porque este fixture ademas genera texto, y el
    # articulo 50 tiene mas deberes que el marcado de las imagenes. Que las
    # imagenes esten bien no cierra el articulo, y eso es la mejora.
    assert all("texto" in f.que["es"] or "asistente" in f.que["es"]
               for f in r.suficiencia.falta), [f.que["es"][:60] for f in r.suficiencia.falta]
    assert any("video" in n for n in r.no_cubre), "un resultado limpio dice que NO cubre"


def test_todo_hallazgo_nombra_su_regla_su_version_su_paquete_y_su_autor(tmp_path):
    from PIL import Image
    art = tmp_path / "s.png"; Image.new("RGB", (8, 8), (1, 1, 1)).save(art)
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,)), REGLAS)
    assert r.hallazgos
    for h in r.hallazgos:
        assert h.regla_id and h.regla_version and h.paquete and h.autor
        assert h.remediacion_es and h.remediacion_en


def test_un_fichero_ilegible_se_declara_y_no_se_salta_en_silencio(tmp_path):
    (tmp_path / "roto.py").write_text("def (:\n")
    (tmp_path / "bien.py").write_text("import openai\nopenai.images.generate(x=1)\n")
    from actaira_motor.controles.deteccion import barrer, cargar_paquete
    b = barrer(tmp_path, cargar_paquete(REGLAS))
    assert len(b.ficheros_ilegibles) == 1 and "roto.py" in b.ficheros_ilegibles[0][0]


def test_una_firma_sin_el_import_del_proveedor_no_dispara(tmp_path):
    """D-1 de la pasada adversarial: `correo.messages.create` no es Anthropic."""
    (tmp_path / "correo.py").write_text(
        "import smtplib\nclass C:\n    messages = None\n"
        "correo = C()\ncorreo.messages.create(asunto='hola')\n")
    r = correr(Entrada(tmp_path), REGLAS)
    assert r.resultado is Resultado.NO_APLICA


def test_la_misma_llamada_con_el_import_si_dispara(tmp_path):
    """El gemelo de la anterior: si no, la regla no probaria nada."""
    (tmp_path / "bot.py").write_text(
        "import anthropic\nclient = anthropic.Anthropic()\n"
        "client.messages.create(model='x', messages=[])\n")
    r = correr(Entrada(tmp_path), REGLAS)
    assert r.resultado is not Resultado.NO_APLICA


# --- la pasada adversarial de la fase 15: el falso positivo sistematico ----

def test_generar_texto_no_es_por_si_mismo_un_hallazgo(tmp_path):
    """El articulo 50(4) no prohibe generar texto: obliga a divulgarlo CUANDO
    se publica para informar al publico sobre asuntos de interes publico.

    La version anterior emitia un hallazgo por cada llamada de generacion de
    texto, y su propia remediacion explicaba el matiz -- o sea que el paquete
    sabia que su hallazgo era mas ancho que la norma y lo emitia igual. Un
    producto que marca en rojo a todo el que llama a una API de texto se
    desactiva en una semana, y con el se desactivan los hallazgos de verdad.
    """
    (tmp_path / "redaccion.py").write_text(
        "from openai import client\n"
        "def resumir(t):\n"
        "    return client.chat.completions.create(messages=[{'role':'user','content':t}])\n",
        encoding="utf-8")
    r = correr(Entrada(tmp_path), REGLAS)
    assert not any(h.regla_id == "ACT-50-GEN-TXT" for h in r.hallazgos)
    assert any(s.regla_id == "ACT-50-GEN-TXT" for s in r.observacion.senales), \
        "pero SI se ha visto, y se dice donde"


def test_a_un_repositorio_que_solo_genera_texto_no_se_le_pide_un_png(tmp_path):
    """Una herramienta que pide lo que no hace falta entrena a ignorarla.

    La rama de «no se aporto ningun artefacto de imagen legible» se disparaba
    tambien cuando NO habia ningun punto de generacion de imagen: el informe
    pedia un PNG a un repositorio que solo genera texto.
    """
    (tmp_path / "redaccion.py").write_text(
        "from openai import client\n"
        "x = client.chat.completions.create(messages=[])\n", encoding="utf-8")
    r = correr(Entrada(tmp_path), REGLAS)
    textos = " ".join(f.que["es"] for f in (r.suficiencia.falta if r.suficiencia else ()))
    assert "PNG" not in textos and "imagen legible" not in textos, textos


def test_y_lo_que_queda_abierto_se_pregunta(tmp_path):
    """El gemelo: «no es un hallazgo» no puede significar «no pasa nada».

    Si generar texto dejara de producir hallazgo y no preguntara nada, el
    articulo 50(4) desapareceria del expediente y el arreglo habria sido
    cambiar un falso positivo por un falso silencio.
    """
    (tmp_path / "redaccion.py").write_text(
        "from openai import client\n"
        "x = client.chat.completions.create(messages=[])\n", encoding="utf-8")
    r = correr(Entrada(tmp_path), REGLAS)
    assert r.suficiencia is not None
    textos = " ".join(f.que["es"] for f in r.suficiencia.falta)
    assert "interés público" in textos, textos
    assert all(f.que_hacer["en"] for f in r.suficiencia.falta)


def test_un_asistente_tampoco_se_da_por_incumplidor_sin_mirar(tmp_path):
    """El aviso del 50(1) es una frase en una pantalla, no una llamada.

    Deducir que no existe porque no se ve en el arbol de sintaxis es inferir
    lo no observado. Se pregunta.
    """
    (tmp_path / "bot.py").write_text(
        "from fastapi import FastAPI\n"
        "from openai import client\n"
        "app = FastAPI()\n"
        "@app.post('/chat')\n"
        "async def responder(m):\n"
        "    return client.chat.completions.create(messages=[m])\n", encoding="utf-8")
    r = correr(Entrada(tmp_path), REGLAS)
    assert not any(h.regla_id == "ACT-50-BOT" for h in r.hallazgos)
    textos = " ".join(f.que["es"] for f in (r.suficiencia.falta if r.suficiencia else ()))
    assert "máquina" in textos or "asistente" in textos, textos


def test_pero_el_marcado_ausente_sigue_siendo_un_hallazgo(tmp_path):
    """La otra mitad: los dos hallazgos que SI se miden sobre bytes se quedan.

    Si al quitar los falsos positivos se hubieran ido tambien los verdaderos,
    el articulo 50 habria dejado de decir nada.
    """
    from PIL import Image
    art = tmp_path / "salida.png"
    Image.new("RGB", (16, 16), (1, 1, 1)).save(art)
    r = correr(Entrada(FIX / "repo-con-generacion", artefactos=(art,)), REGLAS)
    assert any(h.regla_id == "ACT-50-MARCA-AUSENTE" for h in r.hallazgos)


def test_el_xmp_en_un_trozo_tEXt_o_zTXt_TAMBIEN_se_lee(tmp_path):
    """Una rama que nunca se ejecutaba, y que ademas no hacia nada.

    Estaba escrita asi:

        elif ctype in (b"tEXt", b"zTXt") and b"xmp" in ctype.lower():
            pass

    Comprobaba `xmp` dentro del NOMBRE del trozo -- `tEXt` no lo contiene --
    en vez de dentro de la palabra clave, y aunque hubiera casado no hacia
    nada. Asi que un fichero cuyo XMP vive en un `tEXt` se leia como NO
    MARCADO.

    El sitio estandar del XMP en PNG es `iTXt`, y es donde este arnes escribe,
    pero hay herramientas que lo ponen en `tEXt`. Leer solo donde uno escribe
    convierte «no mire ahi» en «no esta», que es el fallo que este modulo
    entero existe para no cometer. Lo encontro una barrida adversarial buscando
    `pass` en ramas de decision.
    """
    import struct
    import zlib

    pytest.importorskip("PIL")
    from PIL import Image

    from actaira_motor.controles.marcado import (
        PNG_XMP_KEYWORD, TRAINED_ALGORITHMIC_MEDIA, xmp_packet)

    base = tmp_path / "base.png"
    Image.new("RGB", (16, 16), (7, 7, 7)).save(base)
    paquete = xmp_packet(TRAINED_ALGORITHMIC_MEDIA)

    def con_trozo(destino, ctype, datos):
        crudo = base.read_bytes()
        i = crudo.index(b"IDAT") - 4
        trozo = (struct.pack(">I", len(datos)) + ctype + datos
                 + struct.pack(">I", zlib.crc32(ctype + datos) & 0xFFFFFFFF))
        destino.write_bytes(crudo[:i] + trozo + crudo[i:])

    tEXt = tmp_path / "text.png"
    con_trozo(tEXt, b"tEXt", PNG_XMP_KEYWORD + b"\x00" + paquete)
    assert read_facts(tEXt).marking == "present", "XMP en tEXt se leyo como ausente"
    assert read_facts(tEXt).says_synthetic

    zTXt = tmp_path / "ztxt.png"
    con_trozo(zTXt, b"zTXt",
              PNG_XMP_KEYWORD + b"\x00" + b"\x00" + zlib.compress(paquete))
    assert read_facts(zTXt).marking == "present", "XMP en zTXt se leyo como ausente"

    # Y la otra mitad: sin marcar sigue saliendo ausente.
    assert read_facts(base).marking == "absent"
