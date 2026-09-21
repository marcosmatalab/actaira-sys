"""Las cinco capas que hasta la fase 14 vivian dentro de un solo enumerado.

EL PROBLEMA, EN UNA LINEA DE CODIGO
-------------------------------------
    Resultado.SIN_HALLAZGOS | CON_HALLAZGOS | INDETERMINADO | NO_APLICA | ERROR

Esos cinco valores no son cinco grados de lo mismo. Son cuatro afirmaciones de
naturaleza distinta metidas en un tipo:

    ERROR            es un hecho sobre la EJECUCION: el analizador se rompio
    NO_APLICA        es un hecho sobre la APLICABILIDAD: no le tocaba mirar
    CON_HALLAZGOS    es una OBSERVACION: aparecio lo que se buscaba
    SIN_HALLAZGOS    es una OBSERVACION: se busco y no aparecio
    INDETERMINADO    es una SUFICIENCIA: lo observado no alcanza para decidir

Mientras vivan juntos, cualquier codigo nuevo puede confundir «se ejecuto» con
«es suficiente» sin que nada falle, y eso es exactamente lo que pasa cuando la
herramienta crece: un conector, un agente o una pantalla leen el enumerado y
deciden lo que les conviene. Separarlo ahora cuesta un dia; separarlo despues
de construir los conectores, los agentes y el frontend cuesta rehacerlos.

LAS CINCO CAPAS, Y QUE PREGUNTA CONTESTA CADA UNA
---------------------------------------------------
    1. Ejecucion    corrio? sobre que? con que version? que leyo y que no pudo
    2. Observacion  que se vio. Hechos. NINGUN veredicto.
    3. Evidencia    esa observacion, guardada, con su frescura y su estado
    4. Suficiencia  para ESTE requisito, alcanza lo que hay? que falta?
    5. Decision     la conclusion juridica. Actaira la REGISTRA y no la emite.

La frontera entre la 2 y la 4 es la que sostiene la segunda negativa. Un
control puede decir «no aparecio ningun marcado en estos tres ficheros». Solo
una politica de suficiencia, citada por su identificador, puede decir «para el
articulo 50 eso no alcanza». Y ni una ni otra pueden decir «esta empresa
incumple»: eso lo firma una persona, en la capa 5, y aqui solo se guarda quien
lo firmo y sobre que.

POR QUE LA 4 NO SE LLAMA «CUMPLIMIENTO»
-----------------------------------------
Porque SUFICIENTE significa «la evidencia que este requisito pide esta, esta
fresca y es valida», que es una afirmacion sobre el expediente. Cumplir es una
afirmacion sobre la conducta de una organizacion frente a una norma, y no se
sigue de la primera: un expediente completo de una practica mal hecha es un
expediente completo. Llamarlo cumplimiento seria volver a meter el veredicto
en el tipo de datos, que es el defecto que esta separacion arregla.
"""
from .ejecucion import Ejecucion, EstadoEjecucion
from .observacion import Observacion, Senal
from .suficiencia import EstadoSuficiencia, Falta, Suficiencia
from .decision import Decision

__all__ = ["Ejecucion", "EstadoEjecucion", "Observacion", "Senal",
           "Suficiencia", "EstadoSuficiencia", "Falta", "Decision"]
