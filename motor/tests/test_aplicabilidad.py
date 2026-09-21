"""Lo indeterminado nunca se pliega a lo que no ata. Tercera negativa."""
from datetime import date
import pytest
from conftest import CATALOGO
from actaira_motor.catalogo.cargador import cargar
from actaira_motor.aplicabilidad.motor import Perfil, resolver, recuento, Situacion

HOY = date(2026, 9, 20)


@pytest.fixture(scope="module")
def cat():
    return cargar(CATALOGO)


def test_un_perfil_vacio_es_indeterminado_y_nunca_limpio(cat):
    v = resolver(cat, Perfil(), HOY)
    assert all(x.situacion is Situacion.INDETERMINADA for x in v)
    assert recuento(v)["no_ata"] == 0, "un perfil sin responder no puede salir limpio"


def test_el_gemelo_sin_perfilar_no_ata_menos_que_perfilado(cat):
    """El gemelo de la negativa: si esto pasara, la indeterminacion seria un aprobado."""
    sin = resolver(cat, Perfil(roles=frozenset({"proveedor"})), HOY)
    assert recuento(sin)["indeterminada"] > 0


def test_cada_veredicto_cita_la_regla_que_lo_produjo(cat):
    v = resolver(cat, Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii"), HOY)
    for x in v:
        assert x.regla and x.regla.split()[0][:3] in ("ROL", "ALC", "FEC"), x


def test_el_reloj_es_un_argumento_y_cambia_el_resultado(cat):
    p = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii", es_sector_publico=False,
               provee_modelo_uso_general=False, modelo_con_riesgo_sistemico=False)
    antes = recuento(resolver(cat, p, date(2026, 9, 20)))
    despues = recuento(resolver(cat, p, date(2027, 12, 2)))
    assert despues["ata"] > antes["ata"]
    assert despues["futura"] < antes["futura"]


def test_la_misma_entrada_da_el_mismo_resultado(cat):
    p = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=False)
    a = [x.a_json() for x in resolver(cat, p, HOY)]
    b = [x.a_json() for x in resolver(cat, p, HOY)]
    assert a == b


def test_una_pyme_sin_alto_riesgo_que_genera_imagenes_tiene_el_articulo_50(cat):
    p = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=False, es_sector_publico=False,
               provee_modelo_uso_general=False, modelo_con_riesgo_sistemico=False,
               genera_contenido_sintetico=True, interactua_con_personas=True, usa_biometria=False)
    atan = {x.obligacion_id for x in resolver(cat, p, HOY) if x.situacion is Situacion.ATA}
    assert "AIA-050" in atan and "AIA-004" in atan and "AIA-005" in atan


def test_el_codigo_abierto_vacia_el_plan_salvo_articulo_5_y_50(cat):
    """Articulo 2(12), contrastado contra el Diario Oficial el 20-09-2026."""
    p = Perfil(roles=frozenset({"proveedor"}), es_codigo_abierto=True, es_alto_riesgo=False,
               es_sector_publico=False, provee_modelo_uso_general=False,
               modelo_con_riesgo_sistemico=False, fines_militares=False, solo_investigacion=False)
    atan = {v.obligacion_id for v in resolver(cat, p, HOY) if v.situacion is Situacion.ATA}
    assert atan == {"AIA-005", "AIA-050"}, atan


def test_el_codigo_abierto_NO_excluye_si_es_de_alto_riesgo(cat):
    """El gemelo. Si esto pasara, la exclusion se tragaria el alto riesgo entero."""
    p = Perfil(roles=frozenset({"proveedor"}), es_codigo_abierto=True, es_alto_riesgo=True, via_anexo="anexo_iii",
               es_sector_publico=False, provee_modelo_uso_general=False,
               modelo_con_riesgo_sistemico=False, fines_militares=False, solo_investigacion=False)
    atan = {v.obligacion_id for v in resolver(cat, p, date(2027, 12, 2)) if v.situacion is Situacion.ATA}
    assert len(atan) > 10 and "AIA-014" in atan


def test_sin_resolver_el_alto_riesgo_el_codigo_abierto_no_excluye_nada(cat):
    """Tercera negativa: una exclusion que se aplica sobre lo no observado es un aprobado."""
    p = Perfil(roles=frozenset({"proveedor"}), es_codigo_abierto=True, es_alto_riesgo=None)
    situaciones = {v.situacion for v in resolver(cat, p, HOY)}
    assert Situacion.INDETERMINADA in situaciones


def test_los_fines_militares_lo_excluyen_todo(cat):
    p = Perfil(roles=frozenset({"proveedor"}), fines_militares=True, es_alto_riesgo=True, via_anexo="anexo_iii")
    assert all(v.situacion is Situacion.NO_ATA for v in resolver(cat, p, HOY))


def test_las_exclusiones_sin_responder_se_publican(cat):
    from actaira_motor.aplicabilidad.motor import exclusiones_sin_responder
    assert set(exclusiones_sin_responder(Perfil())) == {
        "fines_militares", "solo_investigacion", "es_codigo_abierto"}


# --- el calendario partido del Reglamento (UE) 2026/1744 -------------------

def test_de_alto_riesgo_y_sin_decir_la_via_la_fecha_no_se_contesta(cat):
    """Ocho meses de diferencia no se eligen por el cliente.

    El Omnibus digital aplazo las Secciones 1 a 3 del Capitulo III con dos
    fechas: 2 de diciembre de 2027 por el Anexo III y 2 de agosto de 2028 por
    el Anexo I. Publicar una sola obliga a elegir, y las dos elecciones mienten
    a la mitad de los clientes: la temprana les mete prisa por nada, la tardia
    les quita ocho meses de plazo.
    """
    p = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True)
    v = {x.obligacion_id: x for x in resolver(cat, p, date(2027, 12, 15))}
    sin_via = [x for x in v.values() if "FEC-030" in x.regla]
    assert sin_via, "ninguna obligacion pide la via: el calendario partido no esta puesto"
    for x in sin_via:
        assert x.situacion is Situacion.INDETERMINADA
        assert "via_anexo" in x.falta_responder


def test_y_diciendola_salen_dos_planes_distintos(cat):
    """El gemelo: si las dos vias dieran lo mismo, el dato seria decorativo."""
    cuando = date(2027, 12, 15)
    iii = resolver(cat, Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True,
                               via_anexo="anexo_iii"), cuando)
    uno = resolver(cat, Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True,
                               via_anexo="anexo_i"), cuando)
    atan_iii = {x.obligacion_id for x in iii if x.situacion is Situacion.ATA}
    atan_i = {x.obligacion_id for x in uno if x.situacion is Situacion.ATA}
    assert atan_i < atan_iii, "el Anexo I tiene ocho meses mas y eso se tiene que ver"
    assert len(atan_iii - atan_i) >= 10


def test_a_quien_dice_que_no_es_de_alto_riesgo_no_se_le_pregunta_la_via(cat):
    """Preguntar por cual de las dos maneras de ser de alto riesgo le aplica a
    quien ha dicho que no lo es es una pregunta sin respuesta.

    Se toma la fecha TEMPRANA, que es la unica que no le puede quitar plazo.
    """
    p = Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=False,
               es_sector_publico=False, provee_modelo_uso_general=False,
               modelo_con_riesgo_sistemico=False)
    v = resolver(cat, p, date(2026, 9, 20))
    assert not any("FEC-030" in x.regla for x in v)
    assert not any("via_anexo" in x.falta_responder for x in v)


def test_el_aplazamiento_no_alcanza_a_lo_que_el_omnibus_no_nombra(cat):
    """Las Secciones 4 y 5 del Capitulo III y el Capitulo IX mantienen su fecha.

    Algunos analisis secundarios dicen que la evaluacion de la conformidad y el
    registro tambien se aplazan. Mientras no se pueda leer el texto consolidado,
    esta casa toma la fecha TEMPRANA: si la tardia fuera la correcta, el cliente
    habra ido con adelanto; al reves, se habria quedado sin plazo.
    """
    for art in ("43", "47", "49", "72", "73"):
        o = next(x for x in cat.obligaciones.values() if x.articulo == art)
        assert o.aplica_desde == date(2026, 8, 2), art
        assert o.aplica_desde_por_via is None, art
        assert o.bruto and o.bruto.get("nota_de_fecha", {}).get("en"), \
            f"{art}: una fecha que no es la obvia tiene que decir por que"
