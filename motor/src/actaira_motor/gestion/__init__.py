"""El sistema de gestión: lo que la ISO/IEC 42001 audita y el código no enseña.

El motor de controles lee bytes. Esto lee el OTRO lado: si el ciclo de mejora
gira, si la revisión por la dirección miró lo que tenía que mirar, y si las no
conformidades se cerraron comprobando que dejaron de producirse o sólo
declarándolo.
"""
from .noconformidad import (EstadoNC, NoConformidad, Transicion, reconstruir)

__all__ = ["EstadoNC", "NoConformidad", "Transicion", "reconstruir"]
