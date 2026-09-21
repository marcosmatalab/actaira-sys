"""Las estructuras de agentes como sujeto de control.

El Reglamento de 2024 no habla de agentes. Habla de sistemas de IA, y un agente
con herramientas es un sistema de IA: la diferencia no es juridica, es que su
superficie de riesgo no esta donde el catalogo la busca. Un clasificador
arriesga una prediccion mala. Un agente con una herramienta que escribe arriesga
una prediccion mala QUE ADEMAS ACTUA, y eso mueve la mitad del articulo 14 de
«que una persona pueda vigilar» a «que una persona pueda parar».
"""
from .lectura import Agente, Delegacion, Herramienta, leer

__all__ = ["Agente", "Delegacion", "Herramienta", "leer"]
