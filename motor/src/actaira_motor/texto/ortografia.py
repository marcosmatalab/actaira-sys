"""Las tildes del castellano del catalogo, aplicadas una vez y sujetas por una puerta.

POR QUE ESTO ES UN MODULO Y NO UN ARREGLO A MANO
--------------------------------------------------
El catalogo se escribio sin tildes. Es una decision comoda al teclear y es
indefendible en el producto: un sistema que le dice a una empresa espanola
"evaluacion de la conformidad segun el articulo 43" pierde la unica credibilidad
que tiene antes de la segunda linea. Y la consola ya mezclaba las dos cosas,
porque sus propios textos si llevan tilde y los del catalogo no.

Arreglarlo a mano en once ficheros JSON garantiza que se vuelva a romper en el
siguiente anadido. Asi que la correccion es una funcion, se aplica al escribir
el catalogo, y `test_el_castellano_del_catalogo_lleva_tildes` la vuelve a
ejecutar sobre el resultado y exige que no cambie nada. Si alguien anade manana
una obligacion escribiendo "informacion", la puerta lo dice.

LO QUE SE HACE Y LO QUE NO
---------------------------
Se corrige lo que es mecanico y no admite discusion:

  -cion -> -cion con tilde, en SINGULAR. El plural no la lleva (`obligaciones`,
  `decisiones`), y esa asimetria es justo el error que comete un buscar-y-
  reemplazar ingenuo.
  -sion, igual.
  Una lista cerrada de palabras que siempre llevan tilde en cualquier contexto:
  `articulo`, `codigo`, `tecnico`, `publico`, `minimo`, `analisis`, `mas`...

NO se tocan los interrogativos por su cuenta. `que`, `quien`, `cual`, `como`,
`cuanto`, `donde` llevan tilde cuando preguntan y no la llevan cuando relacionan,
y decidir cual es cual con una expresion regular es exactamente la clase de
comprobacion que mira de lado y acierta el ochenta por ciento de las veces. Se
acentuan SOLO dentro de una oracion que termina en interrogacion, y en esas
oraciones se abre ademas el signo de apertura, que el catalogo tampoco tenia.
"""
from __future__ import annotations

import re

# Siempre con tilde, en cualquier contexto. Lista cerrada y revisada a mano.
SIEMPRE = {
    "articulo": "artículo", "articulos": "artículos",
    "codigo": "código", "codigos": "códigos",
    "tecnica": "técnica", "tecnicas": "técnicas", "tecnico": "técnico", "tecnicos": "técnicos",
    "publicas": "públicas", "publicos": "públicos",   # el singular es ambiguo: "publica la regla"
    "politica": "política", "politicas": "políticas",
    "practica": "práctica", "practicas": "prácticas",
    "biometrica": "biométrica", "biometricas": "biométricas",
    "biometrico": "biométrico", "biometricos": "biométricos",
    "automatica": "automática", "automaticas": "automáticas",
    "automatico": "automático", "automaticos": "automáticos",
    "critica": "crítica", "criticas": "críticas", "critico": "crítico", "criticos": "críticos",
    "juridica": "jurídica", "juridico": "jurídico",
    "sintetica": "sintética", "sinteticas": "sintéticas",
    "sintetico": "sintético", "sinteticos": "sintéticos",
    "estatica": "estática", "estatico": "estático",
    "minimo": "mínimo", "minimos": "mínimos", "minima": "mínima", "minimas": "mínimas",
    "maximo": "máximo", "maxima": "máxima",
    "analisis": "análisis", "parametro": "parámetro", "parametros": "parámetros",
    "periodo": "período", "periodos": "períodos",
    "numero": "número", "numeros": "números",
    "unica": "única", "unicas": "únicas", "unico": "único", "unicos": "únicos",
    "ultima": "última", "ultimas": "últimas", "ultimo": "último", "ultimos": "últimos",
    "limite": "límite", "limites": "límites",
    "deposito": "depósito", "interes": "interés",
    "mas": "más", "ademas": "además", "tambien": "también", "asi": "así", "aqui": "aquí",
    "segun": "según", "despues": "después", "estan": "están", "esta_verbo": "está",
    "sera": "será", "seran": "serán", "habra": "habrá", "podra": "podrá", "debera": "deberá",
        "facil": "fácil", "dificil": "difícil", "util": "útil", "utiles": "útiles",
    "ambito": "ámbito", "ambitos": "ámbitos", "area": "área", "areas": "áreas",
    "regimen": "régimen", "indice": "índice", "criterio": "criterio",
    "metrica": "métrica", "metricas": "métricas", "metodo": "método", "metodos": "métodos",
    "electronica": "electrónica", "electronico": "electrónico",
    "informatica": "informática", "informaticos": "informáticos", "informaticas": "informáticas",
    "categoria": "categoría", "categorias": "categorías",
    "garantia": "garantía", "garantias": "garantías",
    "energia": "energía", "tecnologia": "tecnología", "tecnologias": "tecnologías",
    "metodologia": "metodología", "metodologias": "metodologías",
    "auditoria": "auditoría", "auditorias": "auditorías",
    "dia": "día", "dias": "días", "via": "vía", "vias": "vías",
    "estandar": "estándar", "estandares": "estándares",
    "linea": "línea", "lineas": "líneas",     "caracter": "carácter", "caracteres": "caracteres",
    "practicamente": "prácticamente", "automaticamente": "automáticamente",
    "tecnicamente": "técnicamente", "publicamente": "públicamente",
    "solido": "sólido", "solida": "sólida", "solidez": "solidez",
    "credito": "crédito", "creditos": "créditos",
    "clausula": "cláusula", "clausulas": "cláusulas",
    "climatico": "climático", "climatica": "climática",
    "reviso": "revisó", "aprobo": "aprobó", "decidio": "decidió", "encontro": "encontró",
    "examino": "examinó", "firmo": "firmó", "ocurrio": "ocurrió", "sucedio": "sucedió",
    "salio": "salió", "quedo": "quedó",
    "proposito": "propósito", "traduccion": "traducción",
    "maquina": "máquina", "maquinas": "máquinas",
    "vinculo": "vínculo", "vinculos": "vínculos",
    "fisica": "física", "fisicas": "físicas", "fisico": "físico", "fisicos": "físicos",
    "cientifica": "científica", "cientificas": "científicas",
    "cientifico": "científico", "cientificos": "científicos",
    "ningun": "ningún", "algun": "algún",
    "formula": "fórmula", "formulas": "fórmulas",
    "catalogo": "catálogo", "catalogos": "catálogos",
    "titulo": "título", "titulos": "títulos",
    "escribio": "escribió", "evaluara": "evaluará", "marcara": "marcará",
    "respondera": "responderá", "podras": "podrás", "podran": "podrán",
    "invoco": "invocó", "anulo": "anuló", "busco": "buscó", "funciono": "funcionó",
    "alla": "allá", "aca": "acá", "esten": "estén",     "valoracion": "valoración", "sesion": "sesión",
    "arbol": "árbol", "arboles": "árboles", "leido": "leído", "leida": "leída",
    "leidos": "leídos", "leidas": "leídas", "creido": "creído", "oido": "oído",
    "corrio": "corrió", "detecto": "detectó", "emitio": "emitió", 
    "escribelos": "escríbelos", "escribela": "escríbela", "escribelo": "escríbelo",
    "hipotesis": "hipótesis", "computo": "cómputo", "logica": "lógica", "logicas": "lógicas",
    "sistemico": "sistémico", "sistemica": "sistémica", "sistemicos": "sistémicos",
    "todavia": "todavía", "desempena": "desempeña", "desempeno": "desempeño",
    "inequivoca": "inequívoca", "inequivoco": "inequívoco",
    "provoco": "provocó", "evaluo": "evaluó", "sobrevivio": "sobrevivió",
    "manana": "mañana", "modulo": "módulo", "modulos": "módulos",
    "digitos": "dígitos", "digito": "dígito", "terminos": "términos", "termino": "término",
    "faciles": "fáciles", "asimetrias": "asimetrías", "asimetria": "asimetría",
    "insinua": "insinúa", "insinue": "insinúe", "interactua": "interactúa",
    "habeis": "habéis", "conservais": "conserváis", "comprobais": "comprobáis",
    "declarais": "declaráis", "anadelo": "añádelo",
        "demas": "demás", "explicito": "explícito", "explicita": "explícita",
    "implicito": "implícito", "implicita": "implícita",
    "valido": "válido", "validos": "válidos",
    "digalo": "dígalo", "digame": "dígame", "escribalo": "escríbalo", "hagalo": "hágalo",
    "disparo": "disparó", "senale": "señale", "senala": "señala",
    "anadir": "añadir", "anade": "añade", "anadido": "añadido",
    "basico": "básico", "basica": "básica", "basicos": "básicos", "basicas": "básicas",
    "practico": "práctico", "practicos": "prácticos",
    "generico": "genérico", "generica": "genérica", "genericos": "genéricos",
    "especifico": "específico", "especifica": "específica",
    "especificos": "específicos", "especificas": "específicas",
    "sistematico": "sistemático", "sistematica": "sistemática",
    "estadistico": "estadístico", "estadistica": "estadística",
    "matematico": "matemático", "matematica": "matemática",
    "economico": "económico", "economica": "económica",
    "juridicas": "jurídicas", "juridicos": "jurídicos",
    "organico": "orgánico", "organica": "orgánica",
    "multiple": "múltiple", "multiples": "múltiples",
    "ultimamente": "últimamente", "unicamente": "únicamente",
    "rapido": "rápido", "rapida": "rápida", "proximo": "próximo", "proxima": "próxima",
    "comun": "común", "comunes": "comunes", "asimismo": "asimismo",
    "tramite": "trámite", "tramites": "trámites",
    "credito": "crédito", "debito": "débito", "deficit": "déficit",
    "razon": "razón", "razonable": "razonable",
    "podia": "podía", "habia": "había", "tenia": "tenía", "queria": "quería",
    "hara": "hará", "estara": "estará", "dara": "dará", "ira": "irá",
    "exito": "éxito",     "veridico": "verídico", "aleatorio": "aleatorio",
    "organismo": "organismo",           # sin tilde; esta aqui para que no se le ponga
    "espanola": "española", "espanolas": "españolas", "espanol": "español",
    "ano": "año", "anos": "años", "pequena": "pequeña", "pequenas": "pequeñas",
    "diseno": "diseño", "disenos": "diseños", "tamano": "tamaño",
    "ensenanza": "enseñanza", "companias": "compañías", "compania": "compañía",
}
# Las que no cambian, fuera del mapa efectivo.
SIEMPRE = {k: v for k, v in SIEMPRE.items() if k != v and "_" not in k}

# LAS FORMAS QUE SON DOS PALABRAS A LA VEZ, Y POR QUE NO SE AUTOMATIZAN
# ----------------------------------------------------------------------
# El mapa de arriba responde «¿lleva tilde esta palabra?», y esa no es la
# pregunta: la pregunta es si la lleva ESTA aparicion. `valida` es «válida» en
# «una firma valida» y es el verbo `validar` en «no valida manifiestos». La
# primera version las tenia en SIEMPRE y escribio, dentro del motivo de un
# INDETERMINADO que lee el cliente, «este arnes NO válida manifiestos»: una
# herramienta que arregla una tilde y escribe una falta distinta no vale mas
# que no tenerla.
#
# Se probo una regla de contexto -- acentuar detras de determinante o copula --
# y acertaba «sigue valida» y fallaba «una firma valida» y «no valida
# manifiestos» a la vez, que son los dos casos que de verdad salen. Acertar el
# ochenta por ciento aqui significa imprimir el veinte restante en un
# expediente, asi que estas formas NO las toca la pasada mecanica: las que son
# adjetivo se escriben a mano en FRASES, abajo, una por una y leyendo su
# contexto. Es el mismo trato que reciben las preguntas indirectas y el verbo
# `estar`, y el coste es exactamente el que se busca: obliga a mirarla.
#
# `valido` (primera persona, «yo valido») no entra porque en este corpus no hay
# primera persona; si alguna vez la hay, su sitio es esta lista.
AMBIGUAS = frozenset({"valida", "validas"})

INTERROGATIVOS = {"que": "qué", "quien": "quién", "quienes": "quiénes", "cual": "cuál",
                  "cuales": "cuáles", "como": "cómo", "cuando": "cuándo", "donde": "dónde",
                  "cuanto": "cuánto", "cuantos": "cuántos", "cuanta": "cuánta",
                  "cuantas": "cuántas", "por que": "por qué"}

_PAL = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


def _misma_caja(original: str, nuevo: str) -> str:
    return nuevo[0].upper() + nuevo[1:] if original[:1].isupper() else nuevo


def _sufijos(p: str) -> str | None:
    """Las dos familias mecanicas: `-ion` en singular y el condicional `-ria`.

    `-ion` cubre `gestion`, `evaluacion`, `revision` y `cuestion` de una vez.
    La primera version solo miraba `-cion` y `-sion`, y por tanto dejaba
    `gestion` sin tilde, que es la palabra que mas sale en un producto sobre
    sistemas de gestion. Buscar el sufijo mas corto habria evitado el agujero.

    El PLURAL no lleva tilde (`obligaciones`, `decisiones`) y por eso la regla
    solo mira el singular: es el error clasico del buscar-y-reemplazar ingenuo.
    """
    b = p.lower()
    if len(b) > 4 and b.endswith("ion"):
        return p[:-3] + "ión"
    if len(b) > 5 and b.endswith("ria") and b not in _RIA_NO:
        return p[:-3] + "ría"
    return None


# Palabras terminadas en -ria que NO son condicionales y no llevan tilde.
_RIA_NO = {"materia", "feria", "seria", "varia", "diaria", "necesaria", "primaria",
           "secundaria", "obligatoria", "contraria", "ordinaria", "extraordinaria",
           "voluntaria", "arbitraria", "provisoria", "trayectoria",
           "historia", "memoria", "maquinaria", "sanitaria", "unitaria"}


# Lo que puede preceder a un interrogativo de verdad: principio de oracion,
# apertura, conjuncion, coma o preposicion. Detras de un verbo o de un
# articulo, la misma palabra relaciona y NO lleva tilde: "que puede hacer
# CUANDO algo va mal" no pregunta cuando, pregunta que.
ANTES_DE_PREGUNTA = {
    ",", "y", "o", "ni", "pero", "cada",
    "a", "ante", "bajo", "con", "contra", "de", "desde", "en", "entre", "hacia",
    "hasta", "para", "por", "segun", "según", "sin", "sobre", "tras", "durante",
}


# Detras de una preposicion, un interrogativo pregunta... salvo cuando le sigue
# un clitico o un articulo: "que evidencia tiene DE QUE la tienen" no pregunta
# de que, subordina. Se acentuo mal en la primera pasada y salio impreso en una
# pregunta del cuestionario.
# SOLO los cliticos de objeto de tercera persona y el articulo. Los reflexivos
# y los personales -- se, me, te, nos, os -- se quitaron despues de que la regla
# quitara la tilde de dos preguntas legitimas seguidas: «¿a qué se comprometió?»
# y «¿de qué se aprueba y qué no?». Las dos veces costo reescribir la frase para
# esquivar al corrector, que es exactamente al reves de para lo que esta.
#
# La diferencia no es caprichosa: con un clitico de objeto y un verbo transitivo
# («de qué LA tienen») la oracion subordina, mientras que con `se` la
# construccion es impersonal o refleja y lee como pregunta indirecta casi
# siempre. Tres casos observados, y los tres caen del mismo lado.
NO_PREGUNTA_DETRAS = {
    # Cliticos y articulos. Estaban desde el principio: «que evidencia tiene DE
    # QUE LA tienen» subordina, y la primera version lo acentuaba.
    "la", "lo", "le", "los", "las", "les", "el",
    # Pronombres indefinidos. «de QUE ALGUIEN se las salta» subordina, y salio
    # impreso como «de qué alguien», que ademas de cambiar el sentido es
    # agramatical: el `que` interrogativo determina un sustantivo o va solo, y
    # no puede preceder a un indefinido.
    "alguien", "nadie", "algo", "nada",
    "alguno", "alguna", "algunos", "algunas",
    "ninguno", "ninguna", "ningunos", "ningunas",
    "uno", "una", "unos", "unas",
    # Pronombres personales, por lo mismo: «de que EL decide» no pregunta.
    "yo", "tu", "usted", "ustedes", "nosotros", "nosotras",
    "vosotros", "vosotras", "ellos", "ellas",
    "me", "te", "se", "nos", "os",
    # Determinantes posesivos y demostrativos. «que SU equipo revise», «que ESTE
    # sistema decida»: los dos subordinan, y ninguno puede seguir a un `que`
    # interrogativo.
    "mi", "mis", "su", "sus", "nuestro", "nuestra", "nuestros", "nuestras",
    "vuestro", "vuestra", "vuestros", "vuestras",
    "este", "esta", "esto", "estos", "estas",
    "ese", "esa", "eso", "esos", "esas",
    "aquel", "aquella", "aquello", "aquellos", "aquellas",
}
"""Lo que, detras de `que`, dice que ese `que` NO pregunta.

La regla es gramatical y no una lista de casos vistos: el `que` interrogativo o
determina un sustantivo -- «que sistema» -- o va solo antes de un verbo --
«que decide». No puede preceder a un clitico, a un articulo, a un pronombre ni
a un determinante, asi que cuando le sigue uno de estos, subordina.

Se amplio dos veces, y las dos por un texto que salio impreso mal: primero con
los cliticos y los articulos, y despues con los indefinidos, cuando una
pregunta del cuestionario salio diciendo «como se enteran de QUE alguien se las
salta» con tilde. Que hiciera falta ampliarla dos veces es la prueba de que
enumerar casos no basta; por eso ahora la lista sigue una regla y se puede
comprobar contra ella."""


def _sin_tilde(p: str) -> str:
    tabla = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    return p.translate(tabla)


def _acentuar_interrogativos(parte: str) -> str:
    """Acentua los interrogativos de una oracion que termina en interrogacion.

    Dos reglas, y la segunda se anadio porque la primera salio impresa mal:

    1. Un interrogativo pregunta cuando abre la oracion o viene detras de una
       conjuncion, una coma o una preposicion. Detras de un verbo, relaciona:
       "que puede hacer CUANDO algo va mal" no pregunta cuando.
    2. Detras de una PREPOSICION, deja de preguntar si lo que sigue es un
       clitico o un articulo: "que evidencia tiene DE QUE LA tienen" subordina.
       La primera version acentuaba eso y la pregunta salio impresa en el
       cuestionario diciendo "de que la tienen" con tilde.
    """
    piezas = re.split(r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)", parte)
    palabras = [(i, t.lower()) for i, t in enumerate(piezas) if _PAL.fullmatch(t)]

    # SI LA ORACION TRAE UN SIGNO DE APERTURA, LA PREGUNTA EMPIEZA AHI.
    #
    # La regla de abajo trata la primera palabra de la oracion como si abriera
    # la pregunta, porque casi siempre la abre. No la abre cuando la oracion
    # empieza con un preambulo y pregunta despues: «Cuando el sistema decide
    # sobre una persona, ¿como se le informa?». Ahi `cuando` es una conjuncion
    # temporal, y acentuarlo no es una errata: cambia lo que dice la frase, de
    # «siempre que ocurra» a «en que momento». Salio impreso en una pregunta
    # del cuestionario de un cliente.
    #
    # Lo de delante del signo no se toca. Si lleva un interrogativo de verdad,
    # es una pregunta indirecta, y las indirectas ya estan fuera de lo que esta
    # funcion automatiza.
    if "¿" in parte:
        corte = parte.index("¿")
        palabras = [(i, b) for i, b in palabras
                    if len("".join(piezas[:i])) > corte]

    previo = None
    for orden, (i, b) in enumerate(palabras):
        if b in INTERROGATIVOS and (previo is None or previo in ANTES_DE_PREGUNTA):
            siguiente = palabras[orden + 1][1] if orden + 1 < len(palabras) else ""
            # Solo `que`. `cuanto`, `cuando`, `como`, `donde`, `quien` y `cual`
            # detras de una preposicion preguntan casi siempre, y aplicarles
            # esta regla dejaba sin tilde «cada CUANTO se revisa».
            if (b == "que" and previo in ANTES_DE_PREGUNTA and previo != ","
                    and siguiente in NO_PREGUNTA_DETRAS):
                previo = b
                continue
            piezas[i] = _misma_caja(piezas[i], INTERROGATIVOS[b])
        previo = b
        # Una coma o un signo entre dos palabras reabre la posibilidad.
        entre = "".join(piezas[i + 1:palabras[orden + 1][0]]) if orden + 1 < len(palabras) else ""
        if any(c in entre for c in ",;:¿"):
            previo = "," if "¿" not in entre else None
    return "".join(piezas)


# Lo que no se automatiza: las preguntas indirectas y el verbo `estar`.
#
# `quien`, `que`, `como`, `cuando`, `donde` llevan tilde cuando preguntan, y una
# pregunta indirecta no termina en interrogacion: "si no dice QUIEN responde de
# QUE" las lleva las dos y la oracion acaba en punto. Decidirlo con una regla
# seria acertar el ochenta por ciento, y el veinte restante saldria impreso en
# un expediente. Lo mismo con `esta` (demostrativo) frente a `esta` (verbo).
#
# Asi que se corrigen a mano, una por una, en una tabla de frases exactas. Son
# pocas porque el corpus es acotado, se revisaron leyendo el contexto de cada
# una, y `test_el_castellano_del_catalogo_lleva_tildes` vuelve a aplicarlas y
# exige que el catalogo ya no cambie. Anadir texto nuevo con una pregunta
# indirecta obliga a anadir su linea aqui, que es exactamente el coste que se
# quiere: obliga a mirarla.
FRASES = {
    # el verbo `estar`
    "en el que esta previsto": "en el que está previsto",
    "si el uso esta aqui": "si el uso está aqui",
    "que su uso este permitido": "que su uso esté permitido",
    "Esta en vigor desde": "Está en vigor desde",
    "la esta haciendo usted": "la está haciendo usted",
    "que el texto este y que": "que el texto esté y que",
    "y en que estado esta?": "y en que estado está?",
    "desde que fecha esta emitida": "desde que fecha está emitida",
    "Esta el sistema registrado": "Está el sistema registrado",
    "el incumplimiento esta en la politica": "el incumplimiento está en la politica",
    "que esta atado a una alerta": "que está atado a una alerta",
    "quien esta al otro lado y que hace": "quién está al otro lado y qué hace",
    "de que esta hablando con una maquina": "de que está hablando con una maquina",
    "porque eso no esta en el codigo": "porque eso no está en el codigo",
    "se esta portando mal": "se está portando mal",
    "La trampa esta en la segunda mitad": "La trampa está en la segunda mitad",
    "cuando algo esta en el limite": "cuando algo está en el limite",
    "que el proceso este escrito": "que el proceso esté escrito",
    "mientras no este, el documento": "mientras no esté, el documento",
    "El modelo no esta fijado": "El modelo no está fijado",
    # preguntas indirectas
    "pregunta a quien afecta el sistema y como,": "pregunta a quién afecta el sistema y cómo,",
    "no cual tiene razon": "no cuál tiene razon",
    "conviene decir cual y hasta donde": "conviene decir cuál y hasta dónde",
    "le dice cuales faltan": "le dice cuáles faltan",
    "si no dice quien responde de que": "si no dice quién responde de qué",
    "de donde vino cada conjunto y quien le dijo": "de dónde vino cada conjunto y quién le dijo",
    "si dice que busco y como;": "si dice qué buscó y cómo;",
    "se consume decidiendo quien decide": "se consume decidiendo quién decide",
    "siempre es quien mira el numero": "siempre es quién mira el numero",
    "responsables y como se garantiza": "responsables y cómo se garantiza",
    "decir cuales de esos requisitos": "decir cuáles de esos requisitos",
    "de gestion y cuales no.": "de gestion y cuáles no.",
    "que se hara, con que recursos, quien responde, cuando estara y como se evaluara":
        "qué se hará, con qué recursos, quién responde, cuándo estará y cómo se evaluará",
    "anonimato, quien lo recibe y en cuanto tiempo":
        "anonimato, quién lo recibe y en cuánto tiempo",
    "decir quien los propone, quien los aprueba y donde se registran":
        "decir quién los propone, quién los aprueba y dónde se registran",
    "organizacion cual es la politica": "organizacion cuál es la politica",
    "declarar cuales, por que y con que garantias":
        "declarar cuáles, por qué y con qué garantias",
    "del modelo, y quien invoco": "del modelo, y quién invocó",
    "registra que se anulo, quien y por que": "registra que se anuló, quién y por qué",
    "decir como se forma y como se comprueba": "decir cómo se forma y cómo se comprueba",
    "quien firma la notificacion y a que autoridad":
        "quién firma la notificacion y a qué autoridad",
    "No se registra quien reviso": "No se registra quién revisó",
    "Quien pasa a ser proveedor": "Quién pasa a ser proveedor",
    "Si aun no existe": "Si aún no existe",
    "riesgos: quien lo ejecuta, cada cuanto, y como asegura":
        "riesgos: quién lo ejecuta, cada cuánto, y cómo asegura",
    "Cada seccion publica de donde sale": "Cada seccion publica de dónde sale",
    "que es donde se cuela el error": "que es donde se cuela el error",
    "no tiene de donde salir": "no tiene de dónde salir",
    "seria exactamente el producto": "sería exactamente el producto",
    "El contenido entero esta en el": "El contenido entero está en el",
    "proteccion frente a perdida de integridad": "proteccion frente a pérdida de integridad",
    "quien lo acepto y en que fecha": "quién lo aceptó y en qué fecha",
    "espacios de acceso publico": "espacios de acceso público",
    "para informar al publico": "para informar al público",
    "mas alla de sus usuarios": "mas allá de sus usuarios",
    # `valida` y `validas` cuando son adjetivo (ver AMBIGUAS, arriba)
    "una firma valida": "una firma válida",
    "sigue siendo valida": "sigue siendo válida",
    "evidencia valida": "evidencia válida",
    "sigue valida": "sigue válida",
    "no es valida": "no es válida",
    "marca de tiempo valida": "marca de tiempo válida",
}


_ENTRE_GRAVES = re.compile("`[^`" + chr(10) + "]*`")
_MARCA = ""
"""Un caracter de uso privado con el que se tapa un identificador mientras se
corrige la prosa de alrededor.

No es letra, asi que `_PAL` no lo puede tomar por una palabra; no es puntuacion
de fin de oracion, asi que no parte una frase; y no aparece en ningun texto del
catalogo, cosa que la puerta de ortografia comprueba al volver a correr la
correccion sobre su propio resultado y exigir que no cambie nada."""


def corregir(texto: str) -> str:
    """Devuelve el texto con las tildes que faltan. Idempotente por construccion.

    LO QUE VA ENTRE ACENTOS GRAVES NO SE TOCA
    -------------------------------------------
    En la prosa de este arbol, los acentos graves marcan un identificador: el
    nombre de un campo, de un verbo o de un fichero. Este corrector no los
    miraba, asi que `version_consolidada` salia `versión_consolidada` y
    `no_recogido_todavia` salia `no_recogido_todavía`. El campo documentado
    dejaba de existir con ese nombre, y la nota que lo explica pasaba a nombrar
    algo que no esta en el JSON.

    Es el mismo error que ya estaba cazado para las palabras en mayusculas, y
    que el propio comentario de `por_palabra` describe: «corromper un
    identificador mientras se arregla una tilde». Faltaba aplicarlo al otro
    marcador de identificador que usa esta casa. Y es el mismo error, otra vez,
    que cometia el corrector de fuentes Python dentro de las llaves de una
    f-string: la prosa no se decide por el aspecto de una palabra sino por la
    marca que dice que ahi hay codigo.

    Los tramos se apartan ANTES de nada y se devuelven al final, para que las
    tres pasadas -- frases, mecanica e interrogativos -- vean un texto continuo:
    partirlo aqui dejaria una oracion con un identificador dentro fuera del
    alcance del signo de apertura.
    """
    guardados: list[str] = []

    def _apartar(m: re.Match) -> str:
        guardados.append(m.group(0))
        return _MARCA * (len(guardados) - 1) + ""

    texto = _ENTRE_GRAVES.sub(_apartar, texto)
    texto = _corregir_prosa(texto)
    for i, crudo in reversed(list(enumerate(guardados))):
        texto = texto.replace(_MARCA * i + "", crudo)
    return texto


def _corregir_prosa(texto: str) -> str:
    def por_palabra(m: re.Match) -> str:
        p = m.group(0)
        b = p.lower()
        # Una palabra entera en mayusculas es una sigla, un identificador o el
        # nombre de un estado -- VALIDA, RANCIA, SUPERADA -- y este corrector no
        # sabe cual de las tres. Antes no miraba: «VALIDA» salia «Válida» y
        # «VERSION» salia «VERSión», que es corromper un identificador mientras
        # se arregla una tilde. Lo que de verdad necesite acentuarse en
        # mayusculas se escribe a mano en FRASES, que corre antes que esto.
        if len(p) > 1 and p.isupper():
            return p
        if b in AMBIGUAS:
            return p                      # su tilde, si la lleva, viene de FRASES
        if b in SIEMPRE:
            return _misma_caja(p, SIEMPRE[b])
        s = _sufijos(p)
        return s if s else p

    # 0) las frases revisadas a mano, ANTES de lo mecanico: sus reemplazos estan
    #    escritos sin las tildes que pone el paso siguiente, para que las dos
    #    pasadas compongan en vez de pisarse.
    for antes, despues in FRASES.items():
        texto = texto.replace(antes, despues)

    # 1) lo mecanico, en todo el texto
    texto = _PAL.sub(por_palabra, texto)

    # 2) los interrogativos, SOLO dentro de una oracion que pregunta, y de paso
    #    el signo de apertura que el catalogo nunca tuvo.
    #
    #    El separador se CAPTURA y se vuelve a poner tal cual. Antes se partia
    #    con `re.split(r"(?<=[.?!])\s+")` y se rejuntaba con `" ".join(...)`,
    #    que convierte en un espacio cualquier blanco que siga a un punto: un
    #    salto de parrafo, una sangria, una linea en blanco entre dos bloques.
    #    Es decir, una funcion que se llama «corregir las tildes» reescribia
    #    ademas la maquetacion de un texto para personas, y por eso una nota del
    #    catalogo no podia tener dos parrafos: la puerta la dejaba en rojo hasta
    #    que se aplanaba. Corregir de mas es corromper, aunque el cambio parezca
    #    inofensivo.
    partes = re.split(r"((?<=[.?!])\s+)", texto)
    fuera = []
    for i, parte in enumerate(partes):
        if i % 2:
            fuera.append(parte)           # es el separador: va intacto
            continue
        if parte.rstrip().endswith("?"):
            parte = _acentuar_interrogativos(parte)
            # `not in`, y no `startswith`. Una oracion puede abrir la pregunta
            # por la MITAD -- «Antes de ponerlo en servicio, ¿como informaron a
            # los trabajadores?» -- y eso es castellano correcto: lo de delante
            # es el preambulo y la pregunta empieza en el signo. Mirando solo el
            # principio, esta rama anadia un SEGUNDO signo de apertura y dejaba
            # «¿Antes de ponerlo en servicio, ¿como...?».
            if "¿" not in parte:
                blanco = parte[:len(parte) - len(parte.lstrip())]
                parte = blanco + "¿" + parte.lstrip()
        fuera.append(parte)
    return "".join(fuera)


def corregir_es(obj):
    """Recorre una estructura del catalogo y corrige SOLO los campos `es`.

    Vive aqui y no en quien la llama porque `corregir` aplicada a un texto en
    ingles lo destroza -- "information" sale "informatión" -- y el que decide
    a que campos se aplica es el unico sitio donde esa decision esta a salvo.
    El verbo del CLI y la puerta de los tests la usan a los dos, asi que no hay
    dos maneras de recorrer lo mismo.
    """
    if isinstance(obj, dict):
        return {k: (corregir(v) if k == "es" and isinstance(v, str)
                    else (v if k == "en" else corregir_es(v)))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [corregir_es(x) for x in obj]
    return obj
