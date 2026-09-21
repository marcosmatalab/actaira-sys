"""Pantalla en la que una persona aprueba o rechaza la recomendacion."""
def aprobar(recomendacion, revisor):
    return {"decision": "aprobada", "revisado_por": revisor}

def rechazar(recomendacion, revisor, motivo):
    return {"decision": "rechazada", "revisado_por": revisor, "motivo": motivo}
