"""El contrato de conector: traer el código, y no decidir nada sobre él.

POR QUE EL CONTRATO VA ANTES QUE LOS CONECTORES
-------------------------------------------------
La tentación es escribir el de GitHub, que es el que pide el primer cliente, y
sacar el contrato después de él. Eso produce un contrato con forma de GitHub:
`owner/repo`, `pull_request`, `installation_id`. Y entonces el de Azure DevOps
no encaja, el de un Bitbucket autoalojado tampoco, y el «adaptador genérico»
acaba siendo un `if` dentro del de GitHub.

Así que el contrato es esto, y el primer conector que lo implementa es el
LOCAL: un directorio. Si el contrato aguanta un directorio y un repositorio
remoto sin un `if`, aguanta los demás.

LAS CUATRO REGLAS, Y LAS CUATRO SON NEGATIVAS
-----------------------------------------------
  1. **Un conector no decide nada.** Trae ficheros y dice de dónde salieron. No
     evalúa, no clasifica y no puntúa. Toda la doctrina de esta casa vive
     después, en el motor, y un conector que juzgue la mete en un sitio donde
     nadie la audita.
  2. **La referencia se ancla a algo inmutable.** «La rama main» no es una
     referencia: mañana es otra cosa y la evidencia tomada hoy no se puede
     reproducir. El conector resuelve a un identificador que no cambia -un
     commit- y lo publica; si no puede, lo dice y no inventa uno.
  3. **Nada del cliente se queda.** La materialización va a un directorio que
     el que llama controla y borra. El conector no cachea código de cliente en
     ningún sitio suyo, y lo que entra en la evidencia es el DIGEST, nunca los
     ficheros.
  4. **Las credenciales no entran en el expediente.** Ni en la fuente, ni en la
     ejecución, ni en un mensaje de error. Hay una puerta que lo comprueba
     sobre el JSON que se emite, porque el día que un token acabe dentro de un
     expediente firmado, el expediente hay que retirarlo entero.
"""
from .contrato import Conector, Fuente, LimiteDelConector, registro
from .local import ConectorLocal

__all__ = ["Conector", "Fuente", "LimiteDelConector", "registro", "ConectorLocal"]
