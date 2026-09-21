r"""Las formas de BLANQUEAR un expediente, y la negativa a cada una.

La cadena de sellos del almacen demuestra que nadie edito una linea, le quito
una ni las cambio de orden. Una auditoria externa encontro dos maneras de
saltarsela sin romper una sola firma:

  1. Migrar. `migrar_a` reescribe los sellos, asi que un almacen que entra con
     la cadena ROTA sale con una cadena nueva y perfectamente valida. El
     contenido manipulado se conserva y no queda ni una marca de donde venia.
  2. Reescribir el fichero entero y volver a sellarlo. Eso es una limitacion
     criptografica y no un fallo -- una cadena demuestra consistencia, no
     anclaje -- pero la integracion que se entrega verificaba la cadena y NO
     pasaba nunca la cabeza esperada, asi que el unico ataque que la cadena no
     cubre era justo el que quedaba sin cubrir.

Cada prueba de aqui reproduce una de las dos.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "motor" / "src"))

from actaira_motor.evidencia.registro import Registro                    # noqa: E402
from actaira_motor.vigilancia.almacen import (                           # noqa: E402
    ORIGENES_NO_DEMOSTRABLES, Almacen, AlmacenAlterado)

T = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)


def _almacen_con(tmp: Path, cuantas: int = 3) -> Path:
    ruta = tmp / "ev.jsonl"
    a = Almacen.abrir(str(ruta))
    for i in range(cuantas):
        a.anadir([Registro.nuevo("AIA-009", f"ACT-C-00{i}", f"sha256:{i}", T, {"i": i}, 30)], T)
    return ruta


def _tocar(ruta: Path, linea: int, campo: str, valor) -> None:
    """Edita una linea a mano, como haria quien tenga el fichero."""
    ls = ruta.read_text(encoding="utf-8").splitlines()
    d = json.loads(ls[linea - 1])
    d["registro"][campo] = valor
    ls[linea - 1] = json.dumps(d, ensure_ascii=False, sort_keys=True)
    ruta.write_text("\n".join(ls) + "\n", encoding="utf-8", newline="\n")


# --- 1. la migracion que blanqueaba ---------------------------------------

def test_migrar_un_almacen_con_la_cadena_ROTA_no_lo_convierte_en_uno_valido():
    """EL BLANQUEO, reproducido.

    Antes: se cambiaba `frescura_dias` a 9999, la cadena del origen quedaba
    rota, se migraba, y el destino salia con «0 sin cadena, 3 ya encadenadas»,
    cadena valida, la frescura manipulada intacta y `origen: null`. Es decir:
    la migracion era exactamente la manera comoda de blanquear un fichero
    editado que el docstring de `migrar_a` decia estar evitando.

    Lo que fallaba no era la intencion sino el alcance: se penso en el almacen
    SIN cadena -- el de la version anterior del motor -- y no en el que TIENE
    cadena y no la cumple.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ruta = _almacen_con(tmp)
        _tocar(ruta, 2, "frescura_dias", 9999)
        origen = Almacen.abrir(str(ruta))
        assert origen.primera_rotura() == 2

        with pytest.raises(AlmacenAlterado) as e:
            origen.migrar_a(Almacen.abrir(str(tmp / "nuevo.jsonl")))
        assert "se rompe en la linea 2" in str(e.value)
        assert not (tmp / "nuevo.jsonl").exists(), "escribio algo antes de negarse"


def test_si_se_migra_de_todas_formas_cada_linea_dudosa_lo_dice_para_siempre():
    """La salida honesta: conservar el contenido sin heredar su credibilidad.

    Obligar a tirar el fichero seria peor -- es lo unico que queda de lo que
    habia -- asi que se puede migrar diciendolo, y entonces cada linea desde la
    rotura sale marcada. La marca va DENTRO del sello: quitarla rompe la cadena
    nueva.

    Las lineas ANTERIORES a la rotura si estan verificadas y conservan su
    procedencia. Marcarlas todas habria sido perder informacion cierta, que es
    el error contrario y tambien se paga.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ruta = _almacen_con(tmp)
        _tocar(ruta, 2, "frescura_dias", 9999)
        destino = Almacen.abrir(str(tmp / "nuevo.jsonl"))
        dudosas, verificadas = Almacen.abrir(str(ruta)).migrar_a(
            destino, aceptar_cadena_rota=True)

        assert (dudosas, verificadas) == (2, 1)
        assert destino.verificar_cadena() == [], "la cadena nueva tiene que valer"
        origenes = [json.loads(x).get("origen")
                    for x in (tmp / "nuevo.jsonl").read_text(encoding="utf-8").splitlines()]
        assert origenes == [None, "migrada_desde_cadena_rota", "migrada_desde_cadena_rota"]
        assert destino.sin_cadena_demostrable() == 2


def test_la_cuenta_de_lineas_no_demostrables_mira_las_DOS_marcas():
    """Contar solo una habria devuelto el fallo por la ventana de al lado.

    `sin_cadena_demostrable` comparaba con `"migrada_sin_cadena"` y nada mas,
    asi que un almacen migrado desde una cadena rota declaraba CERO lineas no
    demostrables mientras todas sus lineas lo eran.
    """
    assert ORIGENES_NO_DEMOSTRABLES == {"migrada_sin_cadena", "migrada_desde_cadena_rota"}


def test_un_almacen_viejo_SIN_cadena_no_es_lo_mismo_que_uno_roto():
    """Las dos afirmaciones son distintas y por eso son dos banderas.

    «No tenia cadena» es rutina al actualizar el motor. «Tenia cadena y no
    cuadra» es que alguien lo edito. Una sola bandera para las dos convertiria
    la rutina en el permiso para el incidente, y la primera version de
    `primera_rotura` las confundia: decia que un almacen legado estaba roto y
    se negaba a migrar justo los ficheros para los que existe la migracion.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ruta = _almacen_con(tmp, 2)
        ls = [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines()]
        for d in ls:                                  # se le quita la cadena a TODAS
            for campo in ("n", "previo", "sello"):
                d.pop(campo, None)
        ruta.write_text("\n".join(json.dumps(d, ensure_ascii=False, sort_keys=True)
                                  for d in ls) + "\n", encoding="utf-8", newline="\n")

        viejo = Almacen.abrir(str(ruta))
        assert viejo.primera_rotura() is None, "un almacen legado no esta «roto»"
        assert viejo.verificar_cadena(), "pero tampoco verifica, y eso si se dice"

        destino = Almacen.abrir(str(tmp / "nuevo.jsonl"))
        sin_cadena, ya = viejo.migrar_a(destino)      # sin bandera de rotura
        assert (sin_cadena, ya) == (2, 0)
        assert destino.sin_cadena_demostrable() == 2


# --- 2. el anclaje de la cabeza -------------------------------------------

def test_reescribir_el_almacen_entero_da_una_cadena_valida_y_otra_cabeza():
    """El limite que la cadena NO cubre, escrito como prueba y no como parrafo.

    Quien tenga el fichero puede reescribirlo entero y recalcular los sellos.
    El resultado verifica. Lo unico que lo delata es haber anotado FUERA la
    cabeza de antes, y por eso el flujo de integracion continua tiene que
    pasarla: hasta ahora verificaba la cadena y no la pasaba nunca, con lo que
    el unico ataque que la cadena no cubre era el que quedaba sin cubrir.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ruta = _almacen_con(tmp)
        cabeza_buena = Almacen.abrir(str(ruta)).cabeza()

        # Se reescribe entero: dos observaciones en vez de tres, selladas bien.
        ruta.unlink()
        rehecho = Almacen.abrir(str(ruta))
        for i in range(2):
            rehecho.anadir(
                [Registro.nuevo("AIA-009", f"ACT-C-00{i}", f"sha256:{i}", T, {"i": i}, 30)], T)

        assert rehecho.verificar_cadena() == [], "una reescritura completa SI verifica"
        assert rehecho.comprobar_cabeza(cabeza_buena), (
            "y la cabeza anclada es lo unico que lo detecta")
        assert rehecho.comprobar_cabeza(rehecho.cabeza()) is None


def test_el_flujo_de_integracion_continua_exige_la_cabeza_anclada():
    """La plantilla que copia un cliente tiene que USAR el mecanismo que existe.

    `almacen verificar --cabeza-esperada` estaba implementado, probado y
    documentado, y el flujo que se entrega no lo llamaba. Un mecanismo de
    seguridad que existe y que la integracion no usa protege exactamente a
    nadie.
    """
    flujo = (RAIZ / "integraciones" / "github" / "actaira.yml").read_text(encoding="utf-8")
    assert "--cabeza-esperada" in flujo, "el flujo verifica la cadena y no ancla la cabeza"
    assert "upload-artifact" in flujo, "la cabeza tiene que quedar FUERA del repositorio"
    assert "GITHUB_STEP_SUMMARY" in flujo, (
        "y tambien en el registro de la ejecucion, que sobrevive al artefacto")
    # Y se ancla DESPUES de verificar: anclar la cabeza de un almacen roto
    # seria darle un sello de bueno.
    assert flujo.index("El almacén sigue encadenado") < flujo.index("Anclar la cabeza")
