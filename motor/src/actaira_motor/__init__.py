"""Actaira, motor de compliance as code del AI Act y la ISO/IEC 42001.

Este paquete es el MOTOR. Lee el codigo y la configuracion de un sistema de IA,
resuelve que obligaciones le atan, corre los controles que se pueden decidir
leyendo bytes, y emite evidencia firmada. No sabe que existe una plataforma, no
tiene concepto de inquilino, de suscripcion ni de usuario, y el dia que lo
tenga la frontera con `plataforma/` se habra roto.

Procedencia del codigo, porque el lector merece saber que no es todo nuevo:

  evidencia/   portado de actaira v2.3.0 `state/evidence.py`, D-223
  controles/   portado de actaira v2.3.0 `controls/model.py`, D-40 y D-41
  aplicabilidad/ portado en concepto de plazum `nucleo/aplicabilidad` (Go)
  catalogo/    nuevo, y es la pieza que faltaba en los dos

Las cuatro negativas de la constitucion de actaira siguen vigentes aqui, y son
invariantes de este paquete, no aspiraciones:

  1. Nunca un numero. Ni score, ni nota, ni porcentaje, ni confianza.
  2. Nunca juzgar, solo citar. Todo hallazgo nombra la regla, su version, su
     paquete y su autor.
  3. Nunca inferir lo no observado. Sin informacion suficiente, INDETERMINADO.
  4. Nunca actuar sobre lo observado. Se sugiere la remediacion; no se aplica.
"""
__version__ = "0.15.0"
