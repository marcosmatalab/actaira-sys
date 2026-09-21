"""Remediación delegada: el hallazgo sale al sistema donde el cliente trabaja.

Y vuelve con un techo. Ningún estado de ningún tablero cierra una no
conformidad, porque cerrar es comprobar que la causa dejó de producir el
efecto y eso es una observación posterior, no una columna.
"""
from .contrato import Delegacion, Encargo, Remediador, elegir, nombres

__all__ = ["Delegacion", "Encargo", "Remediador", "elegir", "nombres"]
