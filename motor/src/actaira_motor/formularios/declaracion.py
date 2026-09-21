"""Lo que contesta una persona, con su nombre encima y con fecha de caducidad.

POR QUE UNA RESPUESTA ES UNA EVIDENCIA Y NO UN CAMPO DE FORMULARIO
------------------------------------------------------------------
La tentacion es guardar las respuestas en una tabla con una columna por
pregunta. Esa tabla no sabe decir tres cosas que un auditor pregunta siempre:
quien contesto, cuando dejo de ser cierto, y si la pregunta que se contesto es
la misma que hay ahora.

Asi que una respuesta se guarda como un `Registro` del modulo de evidencia, sin
inventar un segundo modelo de estados. El mapeo es literal y es lo que hace que
funcione:

  sujeto_digest   la HUELLA DE LA PREGUNTA, no su identificador
  frescura_dias   la vigencia que el catalogo le da a esa pregunta
  control_id      el identificador de la pregunta
  contenido       el valor, quien lo dijo, con que cargo y su justificacion

De ahi salen gratis los cinco estados, y el que de verdad importa aqui es
SUPERADA. Si manana se reformula la pregunta -- se afina, se traduce mejor, se
le anade una opcion -- su huella cambia y TODA respuesta anterior pasa a
superada automaticamente, con el motivo escrito. Ninguna herramienta del mercado
hace esto: todas tratan la respuesta como un dato y la pregunta como una
etiqueta, con lo que una reformulacion deja en el expediente respuestas a una
pregunta que ya no existe, indistinguibles de las buenas.

LA ADMISIBILIDAD SE DECIDE AQUI Y SE DICE EN VOZ ALTA
------------------------------------------------------
Una respuesta de tres palabras a "describa su proceso de evaluacion de riesgos"
no es una respuesta: es un hueco con texto. Pero tampoco se rechaza en
silencio, porque entonces el cliente cree que contesto. Se guarda con estado
NO_FIABLE y con el motivo, y aparece en el plan como lo que es.

Lo que NO se hace aqui, y es deliberado: juzgar el contenido. Que una respuesta
tenga doscientos caracteres se comprueba; que sea verdad, no. La segunda
negativa de la constitucion -- nunca juzgar, solo citar -- se aplica igual a lo
que escribe el cliente que a lo que hay en su repositorio.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
from typing import Any

from ..catalogo.cargador import PreguntaDeFormulario
from ..evidencia.registro import Estado, Registro, digest

ESQUEMA = "actaira/declaracion/v1"


def huella_de_pregunta(p: PreguntaDeFormulario) -> str:
    """La huella cubre lo que cambia el sentido de la pregunta, y nada mas.

    Entra el texto en los dos idiomas, el formato, las opciones y lo que exige,
    porque tocar cualquiera de esas cosas cambia a que se esta contestando.

    NO entra `ayuda`, y la decision costo pensarla: la ayuda explica como
    contestar bien, no que se pregunta. Si entrara, mejorar una redaccion de
    ayuda invalidaria de golpe las respuestas de todos los clientes, que es el
    coste tipico de una invalidacion demasiado ancha: la gente deja de mejorar
    los textos. Tampoco entra `sirve_a`: descubrir que una pregunta tambien
    cierra una clausula no cambia la pregunta.
    """
    return digest({
        "id": p.id,
        "texto": p.texto,
        "formato": p.formato,
        "opciones": [dict(o) for o in p.opciones],
        "exige": p.exige,
    })


def _longitud(valor: Any) -> int:
    if isinstance(valor, str):
        return len(valor.strip())
    if isinstance(valor, (list, tuple)):
        return sum(len(str(v).strip()) for v in valor)
    return len(str(valor).strip())


def admisible(p: PreguntaDeFormulario, valor: Any, justificacion: str | None) -> tuple[bool, list[str]]:
    """Comprueba la FORMA de la respuesta. Nunca su veracidad.

    Devuelve los motivos, no un booleano solo: un cuestionario que dice "esta
    mal" sin decir que falta se contesta dos veces.
    """
    motivos: list[str] = []
    ex = p.exige or {}

    if valor is None or (isinstance(valor, str) and not valor.strip()) or \
       (isinstance(valor, (list, tuple)) and not valor):
        return False, ["sin contestar"]

    if p.formato == "si_no" and not isinstance(valor, bool):
        motivos.append("esta pregunta se contesta si o no")
    if p.formato == "fecha" and not isinstance(valor, str):
        motivos.append("esta pregunta se contesta con una fecha")
    if p.formato in ("lista", "eleccion") and not isinstance(valor, (list, tuple)):
        motivos.append("esta pregunta admite varios valores y se contesta con una lista")

    if p.formato == "eleccion" and isinstance(valor, (list, tuple)):
        validas = {o["valor"] for o in p.opciones}
        for v in valor:
            if v not in validas:
                motivos.append(f"'{v}' no es una de las opciones de esta pregunta")
        excl = ex.get("excluyente")
        if excl and excl in valor and len(valor) > 1:
            motivos.append(f"'{excl}' excluye a las demas y se han marcado {len(valor)}")

    if (m := ex.get("minimo_caracteres")) and _longitud(valor) < m:
        motivos.append(f"la respuesta tiene {_longitud(valor)} caracteres y esta pregunta pide al menos {m}")
    if (m := ex.get("minimo_elementos")) and isinstance(valor, (list, tuple)) and len(valor) < m:
        motivos.append(f"se han dado {len(valor)} elementos y esta pregunta pide al menos {m}")
    if ex.get("exige_justificacion") and not (justificacion or "").strip():
        motivos.append("esta pregunta exige justificar la respuesta, sea cual sea")
    if ex.get("exige_intervalo") and not any(
            u in str(valor).lower() + " " + (justificacion or "").lower()
            for u in ("dia", "semana", "mes", "ano", "año", "trimestr", "day", "week", "month", "year", "quarter")):
        motivos.append("esta pregunta pide un intervalo y la respuesta no nombra ninguna unidad de tiempo")

    return not motivos, motivos


class Confianza(str, Enum):
    """Cuanto se puede decir de QUIEN esta detras de una respuesta.

    POR QUE ESTO NO ERA UN BOOLEANO
    ---------------------------------
    Una declaracion sin firma valida se reimportaba igual con tal de que la raiz
    Merkle cuadrara. Se emitia un aviso por la salida de error -- que en una
    integracion continua no lo lee nadie -- y sus respuestas entraban en el
    expediente exactamente igual que las de una declaracion firmada.

    El problema es que la raiz Merkle demuestra una cosa muy concreta: que el
    contenido es el mismo que cuando se calculo la raiz. No demuestra autoria,
    ni capacidad del firmante, ni representacion, ni no repudio, ni el momento
    de firma. Y sin embargo el documento que sale despues -- la declaracion de
    aplicabilidad, el Anexo V, el cuestionario -- presenta esa respuesta al lado
    de una firmada y verificada, sin distinguirlas.

    Son CUATRO estados y no dos porque hay cuatro cosas distintas que se pueden
    saber, y las decisiones que toma quien lee son distintas con cada una:

      SIN_FIRMA             alguien escribio esto. Integridad ninguna, identidad
                            ninguna. Es un borrador, y vale como borrador.
      FIRMA_ROTA            trae firma y no verifica. Esto NO es un estado de
                            menos confianza: es un rechazo, y quien lo produce
                            no sigue.
      FIRMADA               la firma verifica contra la clave que viaja DENTRO
                            del documento. Demuestra que quien tenga esa clave
                            lo firmo, no quien es. Integridad si, identidad no.
      IDENTIDAD_VERIFICADA  la firma verifica contra una clave que quien lee
                            DIJO esperar. Aqui si hay identidad, y la hay porque
                            alguien la afirmo de antemano, no porque el
                            documento se presentara a si mismo.

    Lo que NO se modela aqui, y se dice para que no se suponga: que el firmante
    tuviera AUTORIDAD para firmar eso, ni que la declaracion este aprobada, ni
    que no haya sido revocada. Eso son hechos sobre la organizacion, no sobre el
    documento, y este modulo no los puede comprobar leyendo bytes. La casilla
    `cargo` de cada respuesta es lo unico que se acerca, y es una afirmacion de
    quien contesta, no una comprobacion.
    """

    SIN_FIRMA = "sin_firma"
    FIRMA_ROTA = "firma_rota"
    FIRMADA = "firmada"
    IDENTIDAD_VERIFICADA = "identidad_verificada"


CONFIANZA_SUFICIENTE_PARA_AUTORIDAD = frozenset({Confianza.IDENTIDAD_VERIFICADA})
"""Los niveles con los que una respuesta puede sostener una afirmacion de autoria.

Uno solo, y a proposito. `FIRMADA` demuestra integridad y se parece bastante a
identidad, que es justo lo que la hace peligrosa: la clave viaja dentro del
documento, asi que cualquiera que firme con la suya produce un documento que
«verifica».
"""


@dataclass(frozen=True)
class Respuesta:
    """Una respuesta con su persona detras. `cargo` no es decorativo.

    Las clausulas 5.3 y 6.1.3 de la norma y los articulos 17 y 47 del
    Reglamento piden que ciertas cosas las apruebe quien tiene autoridad para
    aprobarlas. Guardar solo el nombre deja al auditor la pregunta de si esa
    persona podia; guardar el cargo la contesta en el mismo renglon.
    """

    pregunta_id: str
    valor: Any
    quien: str
    cargo: str
    cuando: datetime
    justificacion: str | None = None
    confianza: Confianza = Confianza.SIN_FIRMA
    """De donde salio esta respuesta y cuanto se puede decir de quien la firma.

    Por omision `SIN_FIRMA`: una `Respuesta` construida a mano en codigo o
    leida de un fichero escrito a mano es, literalmente, algo que alguien
    escribio. El valor por omision tiene que ser el que menos afirma, porque es
    el que se queda cuando alguien anade un camino de carga nuevo y se olvida.
    """

    def a_registro(self, p: PreguntaDeFormulario) -> Registro:
        if p.id != self.pregunta_id:
            raise ValueError(f"la respuesta es a {self.pregunta_id} y la pregunta es {p.id}")
        ok, motivos = admisible(p, self.valor, self.justificacion)
        cuerpo = {
            "esquema": ESQUEMA, "obligacion_id": "+".join(p.sirve_a), "control_id": p.id,
            "sujeto_digest": huella_de_pregunta(p),
            "observado_en": self.cuando.astimezone(timezone.utc).isoformat(),
            "contenido": self.contenido(),
        }
        return Registro(
            id=digest(cuerpo),
            obligacion_id=cuerpo["obligacion_id"],
            control_id=p.id,
            sujeto_digest=cuerpo["sujeto_digest"],
            observado_en=cuerpo["observado_en"],
            contenido=cuerpo["contenido"],
            frescura_dias=p.vigencia_dias,
            estado_declarado=Estado.VALIDA if ok else Estado.NO_FIABLE,
            motivo=None if ok else "; ".join(motivos),
            esquema=ESQUEMA,
        )

    def contenido(self) -> dict[str, Any]:
        """Lo que se guarda de la respuesta, y por tanto lo que entra en el sello.

        `confianza` va AQUI dentro y no en un campo de al lado. El contenido es
        lo que cubre la raiz Merkle del sello y lo que entra en el sello de la
        linea del almacen, asi que meterla aqui la hace inseparable de la
        respuesta: no se puede subir el nivel de confianza de una respuesta ya
        guardada sin romper la cadena. Fuera habria sido una anotacion que
        cualquiera reescribe.
        """
        return {"valor": self.valor, "quien": self.quien, "cargo": self.cargo,
                "justificacion": self.justificacion,
                "confianza": Confianza(self.confianza).value}


def registrar(preguntas: dict[str, PreguntaDeFormulario],
              respuestas: list[Respuesta]) -> tuple[list[Registro], list[str]]:
    """Convierte respuestas en evidencia. Las que no casan con ninguna pregunta se dicen.

    Una respuesta a una pregunta que ya no esta en el catalogo no se tira en
    silencio: se devuelve en la segunda lista. Tirarla callando seria la forma
    mas barata de que un expediente perdiera una firma sin que nadie lo notara.
    """
    registros, sueltas = [], []
    for r in respuestas:
        p = preguntas.get(r.pregunta_id)
        if p is None:
            sueltas.append(f"{r.pregunta_id}: respondida por {r.quien} y ya no existe en el catalogo")
            continue
        registros.append(r.a_registro(p))
    return registros, sueltas
