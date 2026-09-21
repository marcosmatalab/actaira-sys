"""Exporta el motor como TABLA de datos, para que la consola no lo reimplemente.

EL PROBLEMA QUE RESUELVE
------------------------
La consola corre en un navegador y el motor es Python. La salida perezosa es
reescribir las reglas de aplicabilidad en JavaScript, y entonces hay dos
definiciones de la misma propiedad. Regla 10 de la constitucion: dos
comprobaciones sobre la misma propiedad comparten su definicion o SE ANULAN.
Cada una pasaria en sus terminos y el desacuerdo quedaria invisible entre las
dos, que es exactamente lo que le paso al cruce de catalogos en la fase 0.

LO QUE SE HACE EN SU LUGAR
--------------------------
`exportar()` emite el espacio de decision como datos: por cada alcance, que
campos del perfil necesita y que exige de ellos. La consola evalua una regla
GENERICA de quince lineas sobre esa tabla; no conoce ni un solo alcance por su
nombre. Anadir un alcance nuevo al catalogo no toca el JavaScript.

Y la puerta que lo sujeta, sin la cual esto seria una promesa:
`test_la_tabla_reproduce_al_motor` recorre las 405 combinaciones de perfil que
la consola puede producir y exige que la evaluacion por tabla y `resolver()`
den el MISMO veredicto en las 405. Si alguien toca una y no la otra, revienta.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ..catalogo.cargador import orden_de_articulo, Catalogo
from .motor import SOBREVIVEN_AL_CODIGO_ABIERTO

# Que necesita cada alcance del perfil. Es la unica definicion, y sale de aqui
# tanto para Python como para la consola.
ALCANCES: dict[str, tuple[str, ...]] = {
    "todo_sistema": (),
    "alto_riesgo": ("es_alto_riesgo",),
    "alto_riesgo_sector_publico": ("es_alto_riesgo", "es_sector_publico"),
    "modelo_uso_general": ("provee_modelo_uso_general",),
    "modelo_riesgo_sistemico": ("modelo_con_riesgo_sistemico",),
}

EXCLUSIONES = ("fines_militares", "solo_investigacion", "es_codigo_abierto")

CAMPOS_DECISIVOS = (
    "es_alto_riesgo",
    "es_sector_publico",
    "provee_modelo_uso_general",
    "modelo_con_riesgo_sistemico",
)


def exportar(catalogo: Catalogo) -> dict[str, Any]:
    """El catalogo y el espacio de decision, en la forma que consume la consola."""
    return {
        "generado_por": "actaira_motor.aplicabilidad.tabla.exportar",
        "alcances": {k: list(v) for k, v in ALCANCES.items()},
        "campos_decisivos": list(CAMPOS_DECISIVOS),
        "exclusiones": list(EXCLUSIONES),
        "sobreviven_al_codigo_abierto": list(SOBREVIVEN_AL_CODIGO_ABIERTO),
        "obligaciones": [
            {
                "id": o.id,
                "articulo": o.articulo,
                "titulo": o.titulo,
                "roles": list(o.roles),
                "alcance": o.alcance,
                "aplica_desde": o.aplica_desde.isoformat(),
                # El calendario partido del Reglamento (UE) 2026/1744 viaja a la
                # consola como dato. Si no viajara, la tabla diria una fecha y el
                # motor otra, que es exactamente la discrepancia que esta tabla
                # existe para hacer imposible.
                "aplica_desde_por_via": (
                    {k: v.isoformat() for k, v in o.aplica_desde_por_via.items()}
                    if o.aplica_desde_por_via else None),
                "nivel": o.nivel,
                "comprueba": list(o.comprueba),
                "iso42001": list(catalogo.iso_de(o.id)),
            }
            for o in sorted(catalogo.obligaciones.values(), key=lambda x: orden_de_articulo(x.articulo))
        ],
        "controles_iso": [
            {
                "id": c.id,
                "grupo": c.grupo,
                "titulo": c.titulo,
                "nivel": c.nivel,
                "aiact": list(catalogo.aiact_de(c.id)),
            }
            for c in sorted(catalogo.controles_iso.values(), key=lambda x: x.id)
        ],
        # Desde la fase 7 la consola tambien muestra la declaracion de
        # aplicabilidad y el cuestionario, asi que necesita las clausulas y el
        # banco de preguntas. `por_que` va PRE-RENDERIZADO en los dos idiomas a
        # proposito: es la unica manera de que la consola cite el articulo y la
        # clausula sin reimplementar `_por_que`, que es de donde salio la fuga
        # de idioma de la fase 5.
        "regla_soa": REGLA_SOA,
        "clausulas": [
            {"id": c.id, "clausula": c.clausula, "titulo": c.titulo, "nivel": c.nivel,
             "exige_informacion_documentada": c.exige_informacion_documentada,
             "produce": c.produce, "formulario": c.formulario}
            for c in sorted(catalogo.clausulas.values(),
                            key=lambda x: [int(n) for n in x.clausula.split(".")])
        ],
        "formularios": [
            {"paquete": k, "titulo": v.get("titulo", {}), "nota": v.get("nota"),
             "destinatario_principal": v.get("destinatario_principal", "")}
            for k, v in sorted(catalogo.formularios.items())
        ],
        "preguntas": [
            {"id": q.id, "paquete": q.paquete, "destinatario": q.destinatario,
             "texto": q.texto, "ayuda": q.ayuda, "formato": q.formato,
             "vigencia_dias": q.vigencia_dias, "exige": q.exige,
             "opciones": [dict(o) for o in q.opciones], "sirve_a": list(q.sirve_a),
             "salta_si_cubre": list(q.salta_si_cubre), "si": q.si, "produce": q.produce,
             "por_que": _por_que_exportado(catalogo, q)}
            for q in sorted(catalogo.preguntas.values(), key=lambda x: (x.paquete, x.id))
        ],
    }


def _por_que_exportado(catalogo: Catalogo, q: Any) -> list[dict[str, Any]]:
    """Reusa el que ya existe. Escribir aqui una segunda version seria el defecto."""
    from ..formularios.cuestionario import _por_que
    return _por_que(catalogo, q)


def evaluar_con_tabla(tabla: dict[str, Any], roles: set[str], perfil: dict[str, bool | None], cuando: date) -> dict[str, str]:
    """La MISMA regla generica que corre la consola, escrita una vez y aqui.

    Quince lineas y ni un alcance nombrado. Si esto y `resolver()` discrepan,
    la puerta lo dice.
    """
    salida: dict[str, str] = {}
    for o in tabla["obligaciones"]:
        if perfil.get("fines_militares") is True or perfil.get("solo_investigacion") is True:
            salida[o["id"]] = "no_ata"; continue
        if perfil.get("es_codigo_abierto") is True and o["id"] not in tabla["sobreviven_al_codigo_abierto"] \
           and perfil.get("es_alto_riesgo") is False:
            salida[o["id"]] = "no_ata"; continue
        if not roles:
            salida[o["id"]] = "indeterminada"; continue
        if not (roles & set(o["roles"])):
            salida[o["id"]] = "no_ata"; continue
        campos = tabla["alcances"][o["alcance"]]
        valores = [perfil.get(c) for c in campos]
        if any(v is None for v in valores):
            salida[o["id"]] = "indeterminada"; continue
        if not all(valores):
            salida[o["id"]] = "no_ata"; continue
        # La fecha, con el calendario partido. La via solo se le pide a quien
        # ha dicho que SI es de alto riesgo: al que ha dicho que no, preguntarle
        # por cual de las dos maneras de serlo le aplica no tiene respuesta.
        por_via = o.get("aplica_desde_por_via")
        if por_via and perfil.get("es_alto_riesgo") is True:
            via = perfil.get("via_anexo")
            if via is None:
                salida[o["id"]] = "indeterminada"; continue
            desde = por_via.get(via, o["aplica_desde"])
        elif por_via:
            desde = min(por_via.values())
        else:
            desde = o["aplica_desde"]
        salida[o["id"]] = "ata" if cuando >= date.fromisoformat(desde) else "futura"
    return salida


# La regla de inclusion de la declaracion de aplicabilidad, escrita UNA vez.
#
# La consola la evalua en JavaScript y `expediente/soa.py` la evalua en Python.
# Son dos ejecuciones de la misma frase, no dos frases: la frase esta aqui, y
# `test_la_soa_reproduce_a_la_tabla` recorre las combinaciones de perfil que la
# consola puede producir y exige el mismo veredicto en todas. Es el mismo
# patron que sujeta la tabla de aplicabilidad desde la fase 1, y por la misma
# razon: sin la puerta, esto seria una promesa.
REGLA_SOA = {
    "es": "Un control del Anexo A entra en la declaración de aplicabilidad si alguna obligación del "
          "Reglamento que el cruce ata a ese control ata a este perfil. Si la única que lo trae esta "
          "sin resolver, entra igual y se dice. Si ninguna lo trae, NO se excluye: queda pendiente de "
          "que lo justifique una persona.",
    "en": "An Annex A control is in the statement of applicability if some obligation of the Regulation "
          "that the crosswalk ties to it binds this profile. If the only one bringing it in is "
          "unresolved, it is still in and that is said. If none brings it in, it is NOT excluded: it "
          "stays pending a person's justification.",
}


def inclusion_en_la_soa(obligaciones_cruzadas: list[str],
                        estado_por_obligacion: dict[str, str]) -> tuple[str, list[str]]:
    """(procedencia, obligaciones que la sostienen). Cuatro lineas, sin nombres propios.

    `estado_por_obligacion` admite tanto los estados del plan (`no_ata`,
    `sin_resolver`, ...) como los veredictos de la tabla (`no_ata`,
    `indeterminada`, `ata`, `futura`), porque los dos consumidores traen uno de
    los dos y la distincion que importa aqui es la misma en ambos.
    """
    sin_resolver = {"sin_resolver", "indeterminada"}
    fuera = {"no_ata", None}
    atan = [o for o in obligaciones_cruzadas
            if estado_por_obligacion.get(o) not in (fuera | sin_resolver)]
    if atan:
        return "derivada", atan
    dudosas = [o for o in obligaciones_cruzadas if estado_por_obligacion.get(o) in sin_resolver]
    if dudosas:
        return "derivada_sin_resolver", dudosas
    return "pendiente_de_justificar", []
