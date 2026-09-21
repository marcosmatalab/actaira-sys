"""La tabla que come la consola reproduce al motor. Si no, se anulan (regla 10)."""
import itertools
from datetime import date
import pytest
from conftest import CATALOGO
from actaira_motor.catalogo.cargador import cargar
from actaira_motor.aplicabilidad.motor import Perfil, resolver
from actaira_motor.aplicabilidad.tabla import exportar, evaluar_con_tabla, CAMPOS_DECISIVOS

CONJUNTOS_DE_ROL = [
    {"proveedor"}, {"responsable_despliegue"}, {"importador"}, {"distribuidor"},
    {"proveedor", "responsable_despliegue"},
]
FECHAS = [date(2026, 9, 20), date(2027, 12, 2), date(2028, 8, 2)]


@pytest.fixture(scope="module")
def cat():
    return cargar(CATALOGO)


# Las exclusiones del articulo 2 no se barren en producto cartesiano completo:
# 3^7 son 2.187 estados por conjunto de rol y la puerta tardaria mas de lo que
# nadie espera de `make todo`. Se barren los cuatro estados que cambian la
# respuesta, que son todas sin responder y cada una a si por separado, y eso
# esta escrito aqui en vez de que parezca un descuido.
ESTADOS_DE_EXCLUSION = [
    {"fines_militares": None, "solo_investigacion": None, "es_codigo_abierto": None},
    {"fines_militares": True, "solo_investigacion": False, "es_codigo_abierto": False},
    {"fines_militares": False, "solo_investigacion": True, "es_codigo_abierto": False},
    {"fines_militares": False, "solo_investigacion": False, "es_codigo_abierto": True},
]


def _combinaciones():
    for roles in CONJUNTOS_DE_ROL:
        for valores in itertools.product([True, False, None], repeat=len(CAMPOS_DECISIVOS)):
            for exc in ESTADOS_DE_EXCLUSION:
                yield roles, {**dict(zip(CAMPOS_DECISIVOS, valores)), **exc}


def test_la_tabla_reproduce_al_motor(cat):
    tabla = exportar(cat)
    comparadas = 0
    for roles, campos in _combinaciones():
        for cuando in FECHAS:
            # La via del Anexo entra en el barrido: desde el Reglamento (UE)
            # 2026/1744 decide ocho meses de plazo, asi que una tabla que la
            # ignorara reproduciria al motor solo por casualidad.
            for via in (None, "anexo_iii", "anexo_i"):
                campos_v = {**campos, "via_anexo": via}
                por_tabla = evaluar_con_tabla(tabla, set(roles), campos_v, cuando)
                por_motor = {v.obligacion_id: v.situacion.value
                             for v in resolver(cat, Perfil(roles=frozenset(roles), **campos_v), cuando)}
                assert por_tabla == por_motor, \
                    f"discrepan en roles={roles} campos={campos_v} fecha={cuando}"
                comparadas += 1
    assert comparadas == (len(CONJUNTOS_DE_ROL) * 3 ** len(CAMPOS_DECISIVOS)
                          * len(ESTADOS_DE_EXCLUSION) * len(FECHAS) * 3)


def test_el_gemelo_muerde_si_la_tabla_se_desvia(cat):
    """Regla 9: la puerta anterior tiene que haber visto fallar para valer algo."""
    tabla = exportar(cat)
    tabla["alcances"]["alto_riesgo"] = []            # se rompe a proposito
    roles, campos = {"proveedor"}, {c: None for c in CAMPOS_DECISIVOS}
    por_tabla = evaluar_con_tabla(tabla, roles, campos, date(2026, 9, 20))
    por_motor = {v.obligacion_id: v.situacion.value
                 for v in resolver(cat, Perfil(roles=frozenset(roles), **campos), date(2026, 9, 20))}
    assert por_tabla != por_motor


def test_la_exportacion_lleva_los_dos_idiomas(cat):
    t = exportar(cat)
    for o in t["obligaciones"]:
        assert o["titulo"]["es"] and o["titulo"]["en"]
    for c in t["controles_iso"]:
        assert c["titulo"]["es"] and c["titulo"]["en"]
