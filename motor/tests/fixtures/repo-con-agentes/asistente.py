"""Un asistente con herramientas, delegacion y un limite declarado."""
from openai import client
from marco import tool, Agent


@tool
def obtener_factura(numero):
    """Suena a lectura y emite una factura. Por eso el nombre no vale."""
    return _emitir(numero)


@tool(requires_approval=True)
def reembolsar(importe, cuenta):
    return _transferir(importe, cuenta)


def responder(mensaje):
    return client.chat.completions.create(
        messages=[{"role": "user", "content": mensaje}],
        tools=[obtener_factura, reembolsar],
        max_steps=8,
    )


def escalar(caso):
    revisor = Agent(nombre="revisor", herramientas=[reembolsar])
    return revisor.run(caso)
