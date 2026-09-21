"""Cómo se llama cada estado, en los dos idiomas, en UN solo sitio.

POR QUE ESTO ES DEL MOTOR Y NO DE LA PANTALLA
-----------------------------------------------
Los estados los inventa el motor: `con_hallazgos`, `a_preguntar`, `ejecutada`.
Son identificadores, no prosa, y por eso viajan en el documento sin traducir --
un identificador traducido deja de servir para comparar dos documentos.

Pero alguien tiene que decir cómo se leen. Si ese alguien fuera la pantalla, el
vocabulario del producto viviría en el navegador: el día que el motor añada un
estado, la pantalla enseñaría `sin_cubrir` en crudo a un cliente inglés, que es
exactamente el defecto que ya se corrigió en las señales, en los formularios y
en los paquetes de reglas. Y habría además dos vocabularios en cuanto alguien
hiciera una segunda pantalla.

Así que los nombres los publica el motor, DENTRO del documento y sólo los que
ese documento usa. La pantalla los lee y no sabe nada más; si un día falta uno,
enseña el identificador, que es feo y es verdad.
"""
from __future__ import annotations

from typing import Any

NOMBRES: dict[str, dict[str, str]] = {
    # --- el plan ---------------------------------------------------------
    "comprobada": {"es": "comprobada", "en": "checked"},
    "con_hallazgos": {"es": "con hallazgos", "en": "with findings"},
    "a_preguntar": {"es": "hay que preguntar", "en": "must be asked"},
    "solo_formulario": {"es": "sólo formulario", "en": "form only"},
    "futura": {"es": "te atará", "en": "will bind you"},
    "no_ata": {"es": "no te ata", "en": "does not bind you"},
    "sin_resolver": {"es": "sin resolver", "en": "unresolved"},
    # --- los requisitos atomicos -----------------------------------------
    "comprobado": {"es": "comprobado", "en": "checked"},
    "sin_cubrir": {"es": "sin cubrir", "en": "not covered"},
    "no_exigible": {"es": "no exigible", "en": "not required"},
    "solo_aportado": {"es": "sólo aportado", "en": "supplied only"},
    "no_evaluado": {"es": "no evaluado todavía", "en": "not assessed yet"},
    # --- la aplicabilidad -------------------------------------------------
    "ata": {"es": "te ata hoy", "en": "binds you today"},
    "indeterminada": {"es": "sin resolver", "en": "unresolved"},
    # --- el cuestionario --------------------------------------------------
    "pendiente": {"es": "pendiente", "en": "pending"},
    "contestada": {"es": "contestada", "en": "answered"},
    "la_contesta_el_codigo": {"es": "la contesta el código",
                              "en": "the code answers it"},
    "no_procede": {"es": "no procede", "en": "not applicable"},
    "espera_a": {"es": "espera a otra respuesta", "en": "waits on another answer"},
    # --- la clausula 10.2 -------------------------------------------------
    "abierta": {"es": "abierta", "en": "open"},
    "en_analisis": {"es": "en análisis", "en": "under analysis"},
    "con_accion": {"es": "con acción", "en": "action agreed"},
    "ejecutada": {"es": "ejecutada, no cerrada", "en": "executed, not closed"},
    "verificada": {"es": "verificada", "en": "verified"},
    "vencidas": {"es": "vencidas", "en": "overdue"},
    "estancadas": {"es": "estancadas", "en": "stalled"},
    "incoherentes": {"es": "incoherentes", "en": "incoherent"},
    # --- la declaracion de aplicabilidad (SoA) ----------------------------
    "incluidos": {"es": "incluidos", "en": "included"},
    "excluidos": {"es": "excluidos", "en": "excluded"},
    "derivados_del_reglamento": {"es": "derivados del Reglamento",
                                 "en": "derived from the Regulation"},
    "con_evidencia_tecnica": {"es": "con evidencia técnica",
                              "en": "with technical evidence"},
    "sin_evidencia_todavia": {"es": "sin evidencia todavía", "en": "no evidence yet"},
    "pendientes_de_justificar": {"es": "pendientes de justificar",
                                 "en": "justification pending"},
    # --- el Anexo IV y el Anexo V -----------------------------------------
    "aportada": {"es": "aportada", "en": "supplied"},
    "derivada": {"es": "derivada de lo observado", "en": "derived from what was observed"},
    "ausente": {"es": "ausente", "en": "absent"},
    "caducada": {"es": "caducada", "en": "expired"},
    # --- la evidencia -----------------------------------------------------
    "valida": {"es": "válida", "en": "valid"},
    "rancia": {"es": "rancia", "en": "stale"},
    "superada": {"es": "superada", "en": "superseded"},
    "revocada": {"es": "revocada", "en": "revoked"},
    "no_fiable": {"es": "no fiable", "en": "not trustworthy"},
    # --- la vigilancia ----------------------------------------------------
    "sin_evidencia": {"es": "sin evidencia", "en": "no evidence"},
    "fuera_de_alcance": {"es": "fuera de alcance", "en": "out of scope"},
    "a_reobservar": {"es": "hay que volver a mirar", "en": "must be looked at again"},
    "nada": {"es": "nada que hacer", "en": "nothing to do"},
    # --- los empujones ----------------------------------------------------
    "reobservar": {"es": "volver a observar", "en": "observe again"},
    "revalidar": {"es": "revalidar", "en": "revalidate"},
    "ignorar": {"es": "ignorar", "en": "ignore"},
    "no_traducible": {"es": "no se entiende", "en": "not understood"},
}


def nombres_de(claves) -> dict[str, dict[str, str]]:
    """Los nombres de ESOS estados, y de ninguno más.

    Se publica lo que el documento usa y no la tabla entera: un documento que
    arrastrara los treinta nombres obligaría a quien lo lee a adivinar cuáles
    son suyos, y crecería cada vez que el motor añada un estado a otra cosa.
    """
    return {c: NOMBRES[c] for c in sorted(set(claves)) if c in NOMBRES}


def sin_nombre(claves) -> list[str]:
    """Los estados que se emitirían en crudo. La puerta los usa."""
    return sorted({c for c in claves if c not in NOMBRES})


def con_nombres(documento: dict[str, Any], claves) -> dict[str, Any]:
    """El mismo documento, con el vocabulario de los estados que usa dentro."""
    return {**documento, "nombres_de_estado": nombres_de(claves)}
