"""La revisión por la dirección de la cláusula 9.3, montada desde la evidencia.

QUE PROBLEMA RESUELVE, Y NO ES EL QUE PARECE
----------------------------------------------
Casi ninguna organización falla la 9.3 por no hacer la revisión: la hace, y el
acta existe. Falla porque el acta no cubre las entradas que la norma enumera, y
eso sólo se ve comparando el acta con la lista, que es lo que hace un auditor y
lo que no hace nadie antes.

Así que esto no redacta el acta. Monta la CARPETA de entrada: cada entrada que
la 9.3.2 exige, con lo que hay en el expediente para sostenerla y su estado de
frescura. Lo que falta sale nombrado. Lo que está caducado sale caducado, que
es distinto de que falte y pide otra cosa.

LO QUE ESTE MODULO SE NIEGA A HACER
-------------------------------------
No emite conclusiones ni decisiones. La salida de la 9.3.3 son decisiones sobre
oportunidades de mejora y cambios en el sistema, y eso lo firma la dirección:
aquí se registra en la capa 5 con quién lo firmó y sobre qué estado del
expediente, y esa atadura es un digest y no una fecha, así que si algo cambia
la decisión queda visiblemente descolgada.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

ESQUEMA = "actaira/revision-por-la-direccion/v1"

# Las entradas de la clausula 9.3.2, con la clausula que produce lo que cada
# una necesita. La lista NO se inventa aqui: sale de la norma, y el mapa a
# clausulas es lo que permite buscar la evidencia en vez de preguntar por ella.
ENTRADAS = (
    ("estado_de_acciones_previas", ("ISO-9.3.3",),
     {"es": "el estado de las acciones decididas en revisiones anteriores",
      "en": "the status of actions from previous management reviews"}),
    ("cambios_en_el_contexto", ("ISO-4.1", "ISO-4.2"),
     {"es": "los cambios en las cuestiones externas e internas pertinentes al sistema",
      "en": "changes in external and internal issues relevant to the management system"}),
    ("cambios_en_las_partes_interesadas", ("ISO-4.2",),
     {"es": "los cambios en las necesidades y expectativas de las partes interesadas",
      "en": "changes in the needs and expectations of interested parties"}),
    ("no_conformidades_y_acciones", ("ISO-10.2",),
     {"es": "las no conformidades y el estado de sus acciones correctivas",
      "en": "nonconformities and the status of their corrective actions"}),
    ("seguimiento_y_medicion", ("ISO-9.1",),
     {"es": "los resultados del seguimiento y la medición",
      "en": "monitoring and measurement results"}),
    ("resultados_de_auditoria", ("ISO-9.2.2",),
     {"es": "los resultados de las auditorías internas",
      "en": "internal audit results"}),
    ("cumplimiento_de_objetivos", ("ISO-6.2",),
     {"es": "el grado en que se han alcanzado los objetivos de IA",
      "en": "the extent to which the AI objectives have been achieved"}),
    ("resultados_de_riesgo", ("ISO-8.2", "ISO-8.3"),
     {"es": "los resultados de la evaluación y del tratamiento de riesgos",
      "en": "the results of risk assessment and risk treatment"}),
    ("evaluaciones_de_impacto", ("ISO-8.4", "ISO-6.1.4"),
     {"es": "los resultados de las evaluaciones de impacto de los sistemas de IA",
      "en": "the results of AI system impact assessments"}),
    ("oportunidades_de_mejora", ("ISO-10.1",),
     {"es": "las oportunidades de mejora continua",
      "en": "opportunities for continual improvement"}),
)


def generar(catalogo, registros, ahora: datetime, *, revalidaciones=None,
            revocadas=frozenset(), no_conformidades=(), idioma: str = "es") -> dict[str, Any]:
    """La carpeta de entrada de la revisión, con su estado entrada por entrada.

    `registros` es la evidencia del almacén. Para cada entrada de la 9.3.2 se
    busca la que salga de las cláusulas que la sostienen, y se clasifica:

      aportada    hay evidencia y cuenta
      caducada    hay evidencia y ya no cuenta, con lo que hay que volver a mirar
      ausente     no hay ninguna, que es otra cosa y pide otra acción

    Fundir `caducada` con `ausente` sería el mismo error que el módulo de
    evidencia persigue desde la fase 8: «nadie ha mirado últimamente» y «nunca
    se miró» no se arreglan igual.
    """
    from ..evidencia.registro import Estado

    revalidaciones = revalidaciones or {}
    por_control: dict[str, list] = {}
    for r in registros:
        por_control.setdefault(r.control_id, []).append(r)

    filas, recuento = [], {"aportada": 0, "caducada": 0, "ausente": 0}
    for clave, clausulas, texto in ENTRADAS:
        apoyos, caducados = [], []
        for cid in clausulas:
            for r in por_control.get(cid, ()):
                estado, motivo = r.estado(ahora, revocadas=revocadas,
                                          visto_de_nuevo=revalidaciones.get(r.id))
                (apoyos if estado.cuenta else caducados).append(
                    {"evidencia": r.id, "estado": estado.value, "motivo": motivo})
        if apoyos:
            situacion = "aportada"
        elif caducados:
            situacion = "caducada"
        else:
            situacion = "ausente"
        recuento[situacion] += 1
        filas.append({"entrada": clave, "clausulas": list(clausulas), "texto": texto,
                      "situacion": situacion, "se_apoya_en": apoyos,
                      "caducado": caducados})

    ncs = [n.a_json() if hasattr(n, "a_json") else n for n in no_conformidades]
    return {
        "esquema": ESQUEMA,
        "fecha": ahora.date().isoformat(),
        "recuento": recuento,
        "nota_de_recuento": {
            "es": "Son entradas de la revisión, nunca un porcentaje de madurez. «Caducada» y «ausente» no se suman: la primera se arregla volviendo a mirar y la segunda construyendo algo que no existe.",
            "en": "These are review inputs, never a maturity percentage. 'Expired' and 'absent' are not added together: the first is fixed by looking again and the second by building something that does not exist."},
        "no_es_un_acta": {
            "es": "Esto es la CARPETA de entrada de la revisión, no el acta. Las decisiones de la cláusula 9.3.3 las toma y las firma la dirección; Actaira registra quién las firmó y sobre qué estado del expediente, y esa atadura es un digest, no una fecha.",
            "en": "This is the review's INPUT folder, not the minutes. The Clause 9.3.3 decisions are taken and signed by top management; Actaira records who signed them and over which state of the file, and that binding is a digest, not a date."},
        "entradas": filas,
        "no_conformidades": ncs,
        "que_falta": [f["texto"][idioma] for f in filas if f["situacion"] != "aportada"],
    }


def a_markdown(doc: dict[str, Any], idioma: str = "es") -> str:
    """El mismo documento, para leerlo. Se deriva, no se escribe aparte."""
    t = {"es": ("Revisión por la dirección", "Entrada", "Situación", "Se apoya en",
                "Qué falta", "No conformidades abiertas"),
         "en": ("Management review", "Input", "Status", "Supported by",
                "What is missing", "Open nonconformities")}[idioma]
    fuera = [f"# {t[0]} — {doc['fecha']}", "", doc["no_es_un_acta"][idioma], "",
             f"| {t[1]} | {t[2]} | {t[3]} |", "|---|---|---|"]
    for f in doc["entradas"]:
        apoyo = str(len(f["se_apoya_en"])) if f["se_apoya_en"] else "—"
        fuera.append(f"| {f['texto'][idioma]} | {f['situacion']} | {apoyo} |")
    if doc["que_falta"]:
        fuera += ["", f"## {t[4]}", ""] + [f"- {x}" for x in doc["que_falta"]]
    if doc["no_conformidades"]:
        fuera += ["", f"## {t[5]}", ""]
        for n in doc["no_conformidades"]:
            fuera.append(f"- **{n['id']}** ({n['estado']}) — {n['descripcion']}")
    return "\n".join(fuera) + "\n"
