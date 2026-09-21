r"""Las puertas que impiden que la documentacion envejezca en silencio.

POR QUE ESTE FICHERO
---------------------
`docs/ARQUITECTURA.md` empezaba diciendo, con estas palabras: «Toda cifra de
este documento sale de un comando que se cita al lado. Ninguna esta escrita a
mano».

No era verdad, y no lo era por mucho: decia 24 obligaciones con 48 en el
catalogo, 60 pares del cruce con 101, 56 preguntas con 90 y 205 pruebas con mas
de quinientas. Su propio sello de version decia 0.1.0 con el paquete en 0.14.

Lo que hace dano ahi no es cada numero. Es que esa frase convierte una lista de
cifras viejas en una lista de cifras AVALADAS: quien lee deja de comprobarlas
porque el documento le ha dicho que ya estan comprobadas. Una promesa de
procedencia sin nada que la sostenga es peor que no darla, y es el mismo defecto
que el catalogo tenia al citar el Diario Oficial sin decir contra que version.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "motor" / "src"))

from actaira_motor import __version__  # noqa: E402

ARQUITECTURA = RAIZ / "docs" / "ARQUITECTURA.md"


def test_ninguna_cifra_de_la_arquitectura_se_ha_quedado_vieja():
    """Corre el generador en modo comprobacion. Si hay deriva, sale roja.

    La alternativa -- comprobar aqui cada cifra a mano -- habria creado una
    SEGUNDA definicion de las mismas cantidades, y el dia que discreparan no se
    sabria cual de las dos esta mal. Se llama al mismo generador que las
    escribe, que es la unica forma de que no puedan discrepar.
    """
    r = subprocess.run(
        [sys.executable, str(RAIZ / "herramientas" / "generar_docs.py"), "--comprobar"],
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr


def test_la_arquitectura_no_afirma_cifras_sin_marcador():
    """La frase de la cabecera tiene que seguir siendo verdad.

    Se comprueba que las cantidades que el documento afirma sobre el arbol
    estan DENTRO de un marcador. Un numero suelto al lado de la palabra
    «obligaciones» es exactamente lo que llevaba ahi dos versiones sin que
    nadie lo notara.
    """
    texto = ARQUITECTURA.read_text(encoding="utf-8")
    # Se quitan los tramos generados Y los declarados historicos.
    #
    # `<!--historica-->` existe para dos cosas que un generador NO debe tocar:
    # una cifra sobre otro arbol -- las pruebas de la v2.3 -- y una cita del
    # error pasado, cuando el texto explica que el documento DECIA 24 y son 48.
    # Regenerar cualquiera de las dos las estropearia: la primera dejaria de
    # decir lo que midio quien la midio, y la segunda convertiria la correccion
    # en una frase sin sentido que se corrige a si misma.
    #
    # Es el mismo escape que hizo falta en el catalogo para poder contar que el
    # campo `por_que_estan_los_113` seguia diciendo 113 con 115 dentro.
    sin_marcadores = re.sub(r"<!--cifra:[a-z0-9_]+-->.*?<!--/cifra-->", "", texto, flags=re.S)
    sin_marcadores = re.sub(r"<!--historica-->.*?<!--/historica-->", "", sin_marcadores,
                            flags=re.S)

    sueltas = []
    for m in re.finditer(
            r"\b(\d{2,4})\s+(obligaciones|requisitos|controles|clausulas|cláusulas|"
            r"preguntas|pares|pruebas|tests|reglas)\b", sin_marcadores):
        sueltas.append(m.group(0))
    assert not sueltas, (
        f"cifras escritas a mano sobre el arbol: {sueltas}. Ponlas entre "
        f"`<!--cifra:...-->` y anadelas a `herramientas/generar_docs.py`, o la "
        f"frase de la cabecera vuelve a ser falsa")


def test_la_version_es_la_misma_en_todas_partes():
    """Dos numeros de version es el defecto D-45 de este mismo arbol, otra vez.

    Ya paso: `pyproject.toml` decia 0.9.0, el modulo 0.1.0, y la plantilla de
    integracion continua clavaba el del modulo, asi que un cliente que la
    copiara instalaba una version que el otro fichero decia no ser la suya. Se
    arreglo haciendo que `pyproject` lea la del modulo, y quedo un tercer sitio
    sin atar: la version CLAVADA en la plantilla, que es la que de verdad se
    instala en la maquina del cliente.
    """
    flujo = (RAIZ / "integraciones" / "github" / "actaira.yml").read_text(encoding="utf-8")
    clavadas = set(re.findall(r'ACTAIRA_VERSION:\s*"([^"]+)"', flujo))
    assert clavadas, "la plantilla ya no clava la version: una etiqueta movil no se audita"
    # UNA ETIQUETA DE GIT LLEVA `v` DELANTE Y EL PAQUETE NO.
    #
    # Mientras no haya paquete en PyPI, la plantilla instala desde el
    # repositorio y clava una ETIQUETA, que por costumbre se llama `v0.15.0`.
    # El paquete se llama `0.15.0`. Son la misma version en dos convenciones, y
    # compararlas en crudo ponia esto rojo por una letra. Se quita la `v` del
    # principio y se comparan los numeros; lo que NO se hace es aflojar la
    # comparacion a «que se parezcan».
    numeros = {v[1:] if v.startswith("v") else v for v in clavadas}
    assert numeros == {__version__}, (
        f"la plantilla instala {sorted(clavadas)} y el paquete es {__version__}: "
        f"un cliente que la copie correria otra version de la que dice este arbol")

    sello = re.search(r"<!--cifra:version-->([^<]+)<!--/cifra-->",
                      ARQUITECTURA.read_text(encoding="utf-8"))
    assert sello and sello.group(1) == __version__


def test_lo_que_se_rompe_en_esta_version_esta_escrito():
    """Una version que no dice que rompe obliga a descubrirlo en produccion.

    Esta version cambia comportamiento a proposito -- un rol desconocido
    revienta, la migracion se niega ante una cadena rota, el sello rechaza
    campos sin firmar -- y cada uno de esos cambios hace ruidoso algo que antes
    fallaba en silencio. Publicarlos sin decirlo convierte un arreglo en una
    sorpresa.
    """
    cambios = RAIZ / "docs" / "CAMBIOS.md"
    assert cambios.is_file(), "no hay registro de cambios"
    texto = cambios.read_text(encoding="utf-8")
    assert __version__ in texto, f"el registro de cambios no menciona la {__version__}"
    assert "INCOMPATIBLE" in texto, (
        "el registro no separa lo que ROMPE de lo que anade, y es lo unico que "
        "alguien necesita leer antes de actualizar")


def test_la_guia_de_conectores_describe_el_protocolo_QUE_HAY():
    """Una guia de integracion que describe otra interfaz es peor que ninguna.

    Quien la siga escribira un conector contra metodos que no existen, y lo
    descubrira cuando ya lo tenga escrito. Asi que los nombres que la guia
    promete se comprueban contra los protocolos de verdad, leidos del codigo.
    """
    import ast as _ast

    guia = (RAIZ / "docs" / "CONECTORES.md").read_text(encoding="utf-8")

    def metodos_de(ruta: Path, clase: str) -> set[str]:
        arbol = _ast.parse(ruta.read_text(encoding="utf-8"))
        for n in _ast.walk(arbol):
            if isinstance(n, _ast.ClassDef) and n.name == clase:
                return {x.name for x in n.body
                        if isinstance(x, (_ast.FunctionDef, _ast.AsyncFunctionDef))
                        and not x.name.startswith("_")}
        raise AssertionError(f"no hay clase {clase} en {ruta.name}")

    fuente = RAIZ / "motor" / "src" / "actaira_motor"
    for ruta, clase in ((fuente / "conectores" / "contrato.py", "Conector"),
                        (fuente / "remediacion" / "contrato.py", "Remediador")):
        for metodo in metodos_de(ruta, clase):
            assert f"def {metodo}(" in guia, (
                f"`{clase}.{metodo}` existe y la guia no lo documenta: quien la siga "
                f"escribira un conector al que le falta un metodo")


def test_la_guia_de_conectores_dice_lo_que_NO_trae():
    """El hueco de ServiceNow y compania, dicho en vez de dejado.

    Escribir uno sin una instalacion real contra la que probarlo produciria
    codigo que compila, tiene sus pruebas en verde y nadie ha visto funcionar
    contra lo que dice integrar. Decirlo cuesta un parrafo; no decirlo hace que
    alguien lo busque en el arbol y concluya que el producto esta a medias sin
    saber por que.
    """
    guia = (RAIZ / "docs" / "CONECTORES.md").read_text(encoding="utf-8")
    assert "ServiceNow" in guia
    assert "--simular" in guia, "la guia no menciona el modo que evita mandar un ticket malo"
    # Y el reparto de responsabilidad con el GRC del cliente, que es lo que
    # impide que esto se convierta en un GRC por acumulacion de conectores.
    assert "aceptación formal del riesgo" in guia or "aceptacion formal del riesgo" in guia


def test_los_perfiles_de_remediacion_que_vienen_de_serie_cargan():
    """La guia dice «copia uno de estos». Tienen que cargar.

    Un perfil roto en el arbol convierte la primera instruccion de la guia en
    un callejon sin salida, y quien lo sufra no sabra si se equivoco el o el
    producto.
    """
    import sys as _sys

    _sys.path.insert(0, str(RAIZ / "motor" / "src"))
    from actaira_motor.remediacion.rest import cargar_perfil

    carpeta = (RAIZ / "motor" / "src" / "actaira_motor" / "remediacion" / "perfiles")
    perfiles = sorted(carpeta.glob("*.json"))
    assert perfiles, "la guia manda copiar un perfil y no hay ninguno"
    for p in perfiles:
        d = cargar_perfil(str(p))
        assert d["credencial"]["variable"].startswith("ACTAIRA_") or \
               d["credencial"]["variable"].isupper(), (
            f"{p.name}: la credencial tiene que leerse del ENTORNO, nunca del perfil")
        assert "{credencial}" in str(d["credencial"]["cabeceras"]), (
            f"{p.name}: el perfil no dice donde va la credencial")
