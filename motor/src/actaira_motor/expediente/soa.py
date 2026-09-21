"""La declaracion de aplicabilidad, que es el documento que se pide primero.

QUE ES, Y POR QUE ES LA PIEZA CON MAS APALANCAMIENTO DEL PRODUCTO
------------------------------------------------------------------
La clausula 6.1.3, letra f, de la ISO/IEC 42001 obliga a producir una
declaracion de aplicabilidad que contenga los controles necesarios y que
justifique la inclusion y la exclusion de cada uno. Es el primer folio que pide
un auditor de certificacion y es donde se ve, en una tabla, si la organizacion
ha pensado o ha rellenado.

Hacerla a mano cuesta semanas y envejece en un mes. Aqui sale del motor de
aplicabilidad que ya existe: si el articulo 9 del Reglamento ata a este perfil y
el cruce dice que A.6.1.3 habla de lo mismo, entonces ese control entra, y la
justificacion se escribe sola nombrando el articulo y la regla de aplicabilidad
que lo trajo. Eso es reutilizar el trabajo del Reglamento para la norma, que es
el crossframework de verdad y no una columna en una hoja de calculo.

LA ASIMETRIA DELIBERADA: LA INCLUSION SE DERIVA, LA EXCLUSION NUNCA
--------------------------------------------------------------------
Incluir un control de mas cuesta trabajo. Excluirlo de menos cuesta la
certificacion, y si el control era el que tocaba, cuesta mas que eso. Asi que
este generador incluye por su cuenta y **no excluye jamas**: un control sin
obligacion que lo traiga no sale como excluido, sale como
`pendiente_de_justificar`, con el hueco abierto y el nombre de quien tiene que
cerrarlo.

Es la cuarta negativa aplicada a un documento: nunca actuar sobre lo observado.
Observar que ninguna obligacion del Reglamento trae a A.5.5 no es observar que
A.5.5 no aplique; la norma tiene exigencias propias que el Reglamento no tiene,
y la nota de alcance del cruce lo dice desde la fase 1.

LO QUE SE PUBLICA POR CONTROL
------------------------------
  incluido                 true, o null si nadie lo ha decidido todavia
  procedencia              derivada | aportada | pendiente_de_justificar
  justificacion            por que entra o por que se excluye, con su fuente
  estado_de_implantacion   lo que dijo el barrido y lo que dijo la persona
  evidencia                identificadores de control y de registro, comprobables

No hay columna de porcentaje y no la va a haber. Un recuento de controles
incluidos no es un grado de cumplimiento de la norma.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ..aplicabilidad.tabla import inclusion_en_la_soa
from ..catalogo.cargador import Catalogo

from ..vocabulario import nombres_de

ESQUEMA = "actaira/soa/v1"

# Los nombres de estos estados se cambiaron en la pasada adversarial de la fase
# 6 y el cambio no es cosmetico. Decian "comprobada" y "contestada", que leido
# en una tabla de declaracion de aplicabilidad significa "este control del Anexo
# A esta implantado". El generador no sabe eso: sabe que hay evidencia tecnica
# de una obligacion del Reglamento que el cruce ata a este control, que es
# bastante menos. Heredar la conclusion es justo lo que la nota de alcance del
# cruce lleva prohibiendo desde la fase 1, y la primera version de este modulo
# la infringio en su propia tabla.
ESTADOS = ("con_evidencia_tecnica", "con_hallazgos", "con_respuesta_firmada",
           "sin_evidencia_todavia", "fuera_del_cruce")

_CLAUSULA_FUENTE = {
    "es": "ISO/IEC 42001:2023, cláusula 6.1.3, letra f",
    "en": "ISO/IEC 42001:2023, clause 6.1.3 f)",
}


def _articulos(nums: list[str], idioma: str) -> str:
    """"el articulo 9" o "los articulos 5, 6 y 9", con su verbo concordado.

    Una frase generada que no concuerda delata que la escribio un programa, y
    este documento se lee entero en una auditoria. El coste de concordar son
    seis lineas.
    """
    nums = sorted(set(nums), key=lambda x: (len(x), x))
    if idioma == "en":
        if len(nums) == 1:
            return f"Article {nums[0]} binds"
        return "Articles " + ", ".join(nums[:-1]) + f" and {nums[-1]} bind"
    if len(nums) == 1:
        return f"El articulo {nums[0]} ata"
    return "Los articulos " + ", ".join(nums[:-1]) + f" y {nums[-1]} atan"


def _estado_de_implantacion(cid: str, cat: Catalogo, plan: dict[str, Any] | None,
                            cuestionario: dict[str, Any] | None) -> dict[str, Any]:
    """Lo que se sabe de este control, y de donde se sabe. Nunca un juicio."""
    obligaciones = cat.aiact_de(cid)
    por_obl = {l["obligacion_id"]: l for l in (plan or {}).get("lineas", [])}
    lineas = [por_obl[o] for o in obligaciones if o in por_obl]

    controles, hallazgos = [], 0
    for l in lineas:
        controles += list(l.get("controles_cubiertos", []))
        hallazgos += len(l.get("hallazgos", []))

    respuestas = []
    for q in (cuestionario or {}).get("preguntas", []):
        if cid in [p["id"] for p in q.get("por_que", [])] and q.get("estado") == "contestada":
            respuestas.append({"pregunta": q["id"], "quien": q.get("respondida_por"),
                               "cargo": q.get("cargo"), "registro": q.get("registro_id")})

    if hallazgos:
        estado = "con_hallazgos"
    elif controles:
        estado = "con_evidencia_tecnica"
    elif respuestas:
        estado = "con_respuesta_firmada"
    elif lineas:
        estado = "sin_evidencia_todavia"
    else:
        estado = "fuera_del_cruce"

    return {"estado": estado, "hallazgos": hallazgos,
            "controles_que_lo_comprobaron": sorted(set(controles)),
            "respuestas_que_lo_sostienen": respuestas,
            "obligaciones_cruzadas": list(obligaciones)}


def generar(cat: Catalogo, plan: dict[str, Any] | None, cuestionario: dict[str, Any] | None,
            decisiones: dict[str, dict[str, Any]] | None = None,
            cuando: date | None = None, aprobada_por: dict[str, str] | None = None) -> dict[str, Any]:
    """`decisiones` son las inclusiones y exclusiones que ya firmo una persona."""
    decisiones = decisiones or {}
    cuando = cuando or date.today()
    filas: list[dict[str, Any]] = []

    for cid, ctrl in cat.controles_iso.items():
        fila: dict[str, Any] = {
            "control_id": cid, "titulo": ctrl.titulo, "grupo": ctrl.grupo, "nivel": ctrl.nivel,
        }
        decision = decisiones.get(cid)
        obligaciones = cat.aiact_de(cid)
        estado_de = {l["obligacion_id"]: l["estado"] for l in (plan or {}).get("lineas", [])}
        # La regla vive en `aplicabilidad/tabla.py` y se evalua desde aqui y
        # desde la consola. Una obligacion SIN RESOLVER no "ata a este perfil":
        # nadie ha contestado todavia lo que decide si ata, y meterla en el
        # mismo saco que las resueltas produciria una justificacion plausible y
        # falsa. El control entra igual -- incluir de mas cuesta trabajo -- pero
        # la frase dice la verdad.
        procedencia, sostienen = inclusion_en_la_soa(list(obligaciones), estado_de)
        atan = sostienen if procedencia == "derivada" else []
        dudosas = sostienen if procedencia == "derivada_sin_resolver" else []

        if decision is not None:
            fila["incluido"] = bool(decision["incluido"])
            fila["procedencia"] = "aportada"
            fila["justificacion"] = decision["justificacion"]
            fila["decidido_por"] = {"quien": decision.get("quien"), "cargo": decision.get("cargo"),
                                    "cuando": decision.get("cuando")}
        elif atan:
            fila["incluido"] = True
            fila["procedencia"] = "derivada"
            fila["justificacion"] = {
                i: (f"{_articulos([cat.obligaciones[o].articulo for o in atan], i)} "
                    + ({"es": f"a este perfil, y el cruce del catálogo dice que {cid} habla de lo "
                              f"mismo, así que entra y comparte la evidencia.",
                        "en": f"this profile, and the catalogue crosswalk says {cid} is about the "
                              f"same thing, so it is in and shares the evidence."}[i]))
                for i in ("es", "en")}
            fila["derivada_de"] = list(atan)
        elif dudosas:
            fila["incluido"] = True
            fila["procedencia"] = "derivada_sin_resolver"
            arts = _articulos([cat.obligaciones[o].articulo for o in dudosas], "es")
            arts_en = _articulos([cat.obligaciones[o].articulo for o in dudosas], "en")
            fila["justificacion"] = {
                "es": f"{arts} a este perfil si se contesta lo que falta del alcance, y todavía no se ha "
                      f"contestado. Entra mientras tanto, porque quitarlo seria decidir por omisión; "
                      f"cuando se resuelva el alcance, esta línea se vuelve a generar.",
                "en": f"{arts_en} this profile once the missing scope questions are answered, and they "
                      f"are not answered yet. It is in meanwhile, because dropping it would be deciding "
                      f"by omission; once the scope is resolved this row is generated again."}
            fila["derivada_de"] = list(dudosas)
        else:
            fila["incluido"] = None
            fila["procedencia"] = "pendiente_de_justificar"
            fila["justificacion"] = {
                "es": f"Ninguna obligación del Reglamento que ate a este perfil trae a {cid}. Eso NO "
                      f"significa que no aplique: la norma exige cosas que el Reglamento no exige. "
                      f"Decidalo una persona y escriba por que, que es lo que pide la "
                      f"{_CLAUSULA_FUENTE['es']}.",
                "en": f"No obligation of the Regulation binding this profile brings in {cid}. That does "
                      f"NOT mean it does not apply: the standard requires things the Regulation does "
                      f"not. A person decides and writes why, which is what "
                      f"{_CLAUSULA_FUENTE['en']} asks for."}
        fila["estado_de_implantacion"] = _estado_de_implantacion(cid, cat, plan, cuestionario)
        filas.append(fila)

    recuento = {
        "incluidos": sum(1 for f in filas if f["incluido"] is True),
        "excluidos": sum(1 for f in filas if f["incluido"] is False),
        "pendientes_de_justificar": sum(1 for f in filas if f["incluido"] is None),
        "derivados_del_reglamento": sum(1 for f in filas if f["procedencia"].startswith("derivada")),
    }
    por_estado = {e: sum(1 for f in filas if f["estado_de_implantacion"]["estado"] == e) for e in ESTADOS}

    return {
        "esquema": ESQUEMA,
        "referencia": _CLAUSULA_FUENTE,
        "fecha": cuando.isoformat(),
        "recuento": recuento,
        "por_estado_de_implantacion": por_estado,
        # El vocabulario de los estados que usa este documento. Va dentro
        # porque los estados los inventa el motor y quien lo pinta no tiene por
        # que saberse su idioma.
        "nombres_de_estado": nombres_de(list(recuento) + list(por_estado)),
        "aprobada_por": aprobada_por,
        "nota_de_aprobacion": {
            "es": "La cláusula 6.1.3 exige que la dirección designada apruebe el plan de tratamiento y "
                  "acepte formalmente el riesgo residual. Este documento se genera; no se aprueba solo. "
                  "Sin el campo `aprobada_por` relleno es un borrador, por muy completo que salga.",
            "en": "Clause 6.1.3 requires designated management to approve the treatment plan and formally "
                  "accept the residual risk. This document is generated; it does not approve itself. "
                  "Without `aprobada_por` filled in it is a draft, however complete it looks."},
        "nota_de_no_herencia": {
            "es": "La columna de estado dice que evidencia hay, no que el control este implantado. Que "
                  "una comprobación del Reglamento salga limpia no cierra el control del Anexo A: la "
                  "norma pide además cosas que el artículo no pide. La conclusión la firma una persona, "
                  "control por control.",
            "en": "The status column says what evidence exists, not that the control is implemented. A "
                  "clean check under the Regulation does not close the Annex A control: the standard "
                  "also asks for things the article does not. The conclusion is signed by a person, "
                  "control by control."},
        "nota_de_exclusion": {
            "es": "Este generador incluye por su cuenta y no excluye nunca. Un control que ninguna "
                  "obligación trae sale como pendiente de justificar, no como excluido: incluir de más "
                  "cuesta trabajo y excluir de menos cuesta la certificación.",
            "en": "This generator includes on its own and never excludes. A control that no obligation "
                  "brings in comes out as pending justification, not as excluded: over-including costs "
                  "work and under-excluding costs the certification."},
        "controles": filas,
    }


PALABRAS = {
    "derivada": {"es": "derivada", "en": "derived"},
    "derivada_sin_resolver": {"es": "derivada, alcance sin resolver", "en": "derived, scope unresolved"},
    "aportada": {"es": "aportada", "en": "supplied"},
    "pendiente_de_justificar": {"es": "por justificar", "en": "to be justified"},
    "con_evidencia_tecnica": {"es": "con evidencia técnica", "en": "with technical evidence"},
    "con_hallazgos": {"es": "con hallazgos", "en": "with findings"},
    "con_respuesta_firmada": {"es": "con respuesta firmada", "en": "with a signed answer"},
    "sin_evidencia_todavia": {"es": "sin evidencia todavía", "en": "no evidence yet"},
    "fuera_del_cruce": {"es": "fuera del cruce", "en": "outside the crosswalk"},
    "incluidos": {"es": "incluidos", "en": "included"},
    "excluidos": {"es": "excluidos", "en": "excluded"},
    "pendientes_de_justificar": {"es": "pendientes de justificar", "en": "pending justification"},
    "derivados_del_reglamento": {"es": "derivados del Reglamento", "en": "derived from the Regulation"},
}


def _p(clave: str, idioma: str) -> str:
    """Traduce una clave de estado. Si no la conoce lo dice, no la inventa."""
    return PALABRAS.get(clave, {}).get(idioma, clave)


def _celda(texto: str) -> str:
    """Una barra vertical o un salto de linea en una justificacion escrita por una
    persona parte la tabla en dos y el documento sale ilegible sin avisar."""
    return texto.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def a_markdown(soa: dict[str, Any], idioma: str = "es") -> str:
    """La tabla que se imprime y se lleva a la auditoria.

    Las claves de estado se traducen aqui, con tabla. Es la cuarta vez que una
    cadena de idioma se escapa por el motor (la sexta frase de `reglaDe()` en la
    fase 3, la referencia de `_por_que` y las etiquetas del CLI en la fase 5), y
    la conclusion ya es regla: los estados viajan como claves y solo se
    convierten en palabras en el borde que las imprime.
    """
    cab = {"es": ("Declaracion de aplicabilidad", "Control", "Entra", "Procedencia", "Estado",
                  "Justificacion", "si", "no", "por decidir"),
           "en": ("Statement of Applicability", "Control", "In", "Provenance", "Status",
                  "Justification", "yes", "no", "to decide")}[idioma]
    r, pe = soa["recuento"], soa["por_estado_de_implantacion"]
    lineas = [f"# {cab[0]}", "",
              f"*{soa['referencia'][idioma]}* — {soa['fecha']}", "",
              soa["nota_de_exclusion"][idioma], "",
              soa["nota_de_no_herencia"][idioma], "",
              f"**{r['incluidos']}** {cab[6]} · **{r['excluidos']}** {cab[7]} · "
              f"**{r['pendientes_de_justificar']}** {cab[8]} · "
              f"{r['derivados_del_reglamento']} {_p('derivados_del_reglamento', idioma)}", "",
              "| " + " | ".join(cab[1:6]) + " |",
              "|---|---|---|---|---|"]
    marca = {True: cab[6], False: cab[7], None: cab[8]}
    for f in soa["controles"]:
        just = f["justificacion"][idioma] if isinstance(f["justificacion"], dict) else str(f["justificacion"])
        just = _celda(just)
        lineas.append(f"| `{f['control_id']}` {_celda(f['titulo'][idioma])} | {marca[f['incluido']]} | "
                      f"{_p(f['procedencia'], idioma)} | "
                      f"{_p(f['estado_de_implantacion']['estado'], idioma)} | {just} |")
    if soa.get("aprobada_por"):
        a = soa["aprobada_por"]
        lineas += ["", f"**{'Aprobada por' if idioma == 'es' else 'Approved by'}**: "
                       f"{a.get('quien')} ({a.get('cargo')}), {a.get('cuando')}"]
    else:
        lineas += ["", "> " + soa["nota_de_aprobacion"][idioma]]
    lineas.append("")
    lineas.append("**" + ("Estado de implantación" if idioma == "es" else "Implementation status") +
                  "**: " + ", ".join(f"{_p(k, idioma)}: {v}" for k, v in pe.items() if v))
    return "\n".join(lineas)
