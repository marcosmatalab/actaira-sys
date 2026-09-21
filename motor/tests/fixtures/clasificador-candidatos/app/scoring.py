"""Clasifica candidatos para un puesto. Anexo III punto 4: empleo. Alto riesgo."""
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)
client = OpenAI()
MODEL_SHA = "sha256:9f2c1ab4e8d70bb31c4e7f5a2d6b8c0e1f3a5b7c9d1e3f5a7b9c1d3e5f7a9b1c"

def puntuar(cv, oferta):
    r = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":cv}])
    logger.info("recomendacion", extra={"model_version": MODEL_SHA, "cv_ref": hash(cv), "salida_ref": id(r)})
    return r
