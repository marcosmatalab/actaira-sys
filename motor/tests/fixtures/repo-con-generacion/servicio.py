"""Fixture: un servicio que genera imagenes y texto, como cualquiera del mundo real."""
from openai import OpenAI
client = OpenAI()

def portada(prompt):
    r = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1024")
    return r.data[0].b64_json

def responder(mensaje):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": mensaje}])

# una cadena que se PARECE a una firma pero no es una llamada
DOCUMENTACION = "usa client.images.generate para crear la portada"
