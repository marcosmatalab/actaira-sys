"""Primera negativa, con puerta: ninguna salida publicada contiene un numero plegado."""
import json, re
from datetime import date
from conftest import CATALOGO
from actaira_motor.catalogo.cargador import cargar
from actaira_motor.aplicabilidad.motor import Perfil, resolver, recuento
from actaira_motor.controles.modelo import Pasada, Resultado, ResultadoControl

PROHIBIDAS = ("score", "grade", "rating", "percent", "confidence", "ranking", "puntuacion", "nota_global")


def _salidas():
    cat = cargar(CATALOGO)
    v = resolver(cat, Perfil(roles=frozenset({"proveedor"}), es_alto_riesgo=True, via_anexo="anexo_iii"), date(2026, 9, 20))
    pasada = Pasada([ResultadoControl("C1", "AIA-050", Resultado.SIN_HALLAZGOS, ("png leidos",), ("video",))])
    return [ [x.a_json() for x in v], recuento(v), pasada.a_json() ]


def test_ninguna_salida_nombra_un_agregado():
    texto = json.dumps(_salidas()).lower()
    encontradas = [p for p in PROHIBIDAS if p in texto]
    assert encontradas == [], f"palabras de agregado en la salida: {encontradas}"


def test_ninguna_salida_contiene_un_flotante():
    def buscar(o, ruta="$"):
        if isinstance(o, bool) or o is None: return []
        if isinstance(o, float): return [f"{ruta}={o}"]
        if isinstance(o, dict): return [x for k, v in o.items() for x in buscar(v, f"{ruta}.{k}")]
        if isinstance(o, (list, tuple)): return [x for i, v in enumerate(o) for x in buscar(v, f"{ruta}[{i}]")]
        return []
    assert buscar(_salidas()) == []


def test_el_gemelo_del_guardia_muerde():
    """Regla 9: un test que afirma 'esto no ocurre' tiene que haber visto ocurrirlo."""
    def buscar(o):
        return [o] if isinstance(o, float) and not isinstance(o, bool) else (
            [x for v in o.values() for x in buscar(v)] if isinstance(o, dict) else
            [x for v in o for x in buscar(v)] if isinstance(o, (list, tuple)) else [])
    assert buscar({"cumplimiento": 0.78}) == [0.78]
