"""El cuestionario: lo que hay que preguntar, que es mucho menos de lo que parece.

LA RESTA ES EL PRODUCTO
-----------------------
Un consultor abre con un cuestionario de trescientas preguntas porque no ha
mirado el repositorio. Aqui el cuestionario se construye DESPUES del barrido y
en contra de el: toda pregunta que trae `salta_si_cubre` desaparece en cuanto un
control leyo los bytes que la contestan. Lo que queda es lo que ningun analisis
estatico puede saber, que es casi siempre lo mismo -- quien responde, cada
cuanto se revisa, que se decidio y por que -- y es la parte que de verdad hay
que preguntarle a una persona.

Esa resta se publica en `ahorro`, con los identificadores de los controles que
la produjeron, para que se pueda auditar. Un numero que dice "te ahorramos 40
preguntas" sin decir cuales es publicidad; con la lista de controles detras es
una afirmacion comprobable.

LAS CONDICIONES NO ESCONDEN PREGUNTAS, LAS APLAZAN
---------------------------------------------------
Una pregunta con `si` que todavia no se puede evaluar no se calla: sale con
estado `espera_a` y nombra de que depende. La diferencia con esconderla importa
porque el cliente ve el tamano real de lo que le queda, y porque un cuestionario
que encoge segun se contesta produce la sensacion de que alguien esta moviendo
la porteria.

POR QUE `por_que` SE DERIVA Y NO SE ESCRIBE
--------------------------------------------
Cada pregunta dice a que sirve con identificadores, y el texto de por que se le
pregunta se saca del catalogo en el momento de construir. Escribirlo a mano en
el formulario seria una segunda fuente de verdad sobre lo que exige el articulo,
y la regla 10 dice que dos fuentes sobre la misma propiedad no se suman: se
anulan. Si manana cambia el titulo de una clausula, cambia aqui solo.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..catalogo.cargador import Catalogo, PreguntaDeFormulario
from ..evidencia.registro import Estado, Registro
from .declaracion import huella_de_pregunta

from ..vocabulario import nombres_de

ESQUEMA = "actaira/cuestionario/v1"

ESTADOS = ("pendiente", "contestada", "rancia", "superada", "no_fiable",
           "no_procede", "espera_a", "la_contesta_el_codigo")

_POR_ESTADO = {
    Estado.VALIDA: "contestada", Estado.RANCIA: "rancia", Estado.SUPERADA: "superada",
    Estado.REVOCADA: "superada", Estado.NO_FIABLE: "no_fiable",
}


def _ultima(registros: list[Registro], pregunta_id: str) -> Registro | None:
    candidatas = [r for r in registros if r.control_id == pregunta_id]
    return max(candidatas, key=lambda r: r.observado_en) if candidatas else None


def _valor_de(reg: Registro | None) -> Any:
    return None if reg is None else reg.contenido.get("valor")


def _condicion(q: PreguntaDeFormulario, registros: list[Registro]) -> tuple[str, str | None]:
    """Evalua `si`. Devuelve (veredicto, de_quien_depende).

    Veredictos: 'procede', 'no_procede', 'espera'. Nunca revienta por una
    dependencia que no existe, porque esa la caza la puerta del catalogo al
    cargar y aqui ya no puede pasar.
    """
    if not q.si:
        return "procede", None
    origen = q.si.get("pregunta")
    reg = _ultima(registros, origen) if origen else None
    if reg is None:
        return "espera", origen
    valor = _valor_de(reg)
    lista = valor if isinstance(valor, (list, tuple)) else [valor]
    if "vale" in q.si:
        return ("procede" if q.si["vale"] in lista else "no_procede"), origen
    if "distinto_de" in q.si:
        return ("procede" if any(v != q.si["distinto_de"] for v in lista) else "no_procede"), origen
    if "contiene" in q.si:
        return ("procede" if q.si["contiene"] in lista else "no_procede"), origen
    return "procede", origen


REFERENCIA = {
    "articulo": {"es": "artículo {x}", "en": "Article {x}"},
    "clausula": {"es": "cláusula {x}", "en": "clause {x}"},
    "anexo_a": {"es": "Anexo A, {x}", "en": "Annex A, {x}"},
}


def _ref(plantilla: str, x: str) -> dict[str, str]:
    return {i: REFERENCIA[plantilla][i].format(x=x) for i in ("es", "en")}


def _por_que(cat: Catalogo, q: PreguntaDeFormulario) -> list[dict[str, Any]]:
    """La referencia va en los dos idiomas, y esto se aprendio rompiendolo.

    En la fase 3 la consola llevaba seis frases en castellano incrustadas en la
    logica, que por tanto no se traducian nunca. La primera version de esta
    funcion repitio el error exacto: escribia `f"articulo {o.articulo}"` y la
    salida en ingles decia "por: articulo 16, clausula 4.1". Una cadena de
    idioma formateada en el motor es una fuga, siempre. Las tres plantillas
    estan arriba y son datos.
    """
    fuera = []
    for ident in q.sirve_a:
        if ident in cat.obligaciones:
            o = cat.obligaciones[ident]
            fuera.append({"id": ident, "marco": "ai-act",
                          "referencia": _ref("articulo", o.articulo), "titulo": o.titulo})
        elif ident in cat.clausulas:
            c = cat.clausulas[ident]
            fuera.append({"id": ident, "marco": "iso42001",
                          "referencia": _ref("clausula", c.clausula), "titulo": c.titulo})
        elif ident in cat.controles_iso:
            c = cat.controles_iso[ident]
            fuera.append({"id": ident, "marco": "iso42001",
                          "referencia": _ref("anexo_a", ident), "titulo": c.titulo})
    return fuera


def construir(cat: Catalogo, plan: dict[str, Any] | None, registros: list[Registro],
              ahora: datetime, paquetes: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """El cuestionario en el momento `ahora`. El reloj es un argumento, siempre."""
    # `controles_cubiertos` y no `cubre`: el segundo es prosa para leer
    # ("ACT-09-GATE: encontrado en .github/workflows/ci.yml") y parsear un
    # prefijo de una frase seria inventar aqui un segundo formato de la misma
    # verdad. El motor publica los dos en el mismo instante y desde el mismo
    # `r["id"]`, y `ResultadoControl` tiene puerta para que no puedan divergir.
    cubiertos: dict[str, str] = {}
    for linea in (plan or {}).get("lineas", []):
        for ctrl in linea.get("controles_cubiertos", []):
            cubiertos[ctrl] = linea["obligacion_id"]

    salidas: list[dict[str, Any]] = []
    ahorro: list[dict[str, str]] = []

    for q in cat.preguntas.values():
        entrada: dict[str, Any] = {
            "id": q.id, "paquete": q.paquete, "destinatario": q.destinatario,
            "texto": q.texto, "ayuda": q.ayuda, "formato": q.formato,
            "vigencia_dias": q.vigencia_dias, "por_que": _por_que(cat, q),
            "huella": huella_de_pregunta(q),
        }
        if q.opciones:
            entrada["opciones"] = [dict(o) for o in q.opciones]
        if q.exige:
            entrada["exige"] = q.exige
        if q.produce:
            entrada["produce"] = q.produce

        cubre = [c for c in q.salta_si_cubre if c in cubiertos]
        veredicto, depende = _condicion(q, registros)
        reg = _ultima(registros, q.id)

        if cubre and reg is None:
            entrada["estado"] = "la_contesta_el_codigo"
            entrada["cubierta_por"] = [{"control_id": c, "obligacion_id": cubiertos[c]} for c in cubre]
            ahorro += entrada["cubierta_por"]
        elif veredicto == "no_procede":
            entrada["estado"] = "no_procede"
            entrada["depende_de"] = depende
        elif veredicto == "espera" and reg is None:
            entrada["estado"] = "espera_a"
            entrada["depende_de"] = depende
        elif reg is None:
            entrada["estado"] = "pendiente"
        else:
            est, motivo = reg.estado(ahora, digest_actual_del_sujeto=huella_de_pregunta(q))
            entrada["estado"] = _POR_ESTADO[est]
            entrada["motivo"] = motivo
            entrada["respondida_por"] = reg.contenido.get("quien")
            entrada["cargo"] = reg.contenido.get("cargo")
            # QUE SE PUEDE DECIR DE QUIEN HAY DETRAS, al lado de su nombre.
            #
            # `respondida_por` y `cargo` los escribio quien contesto: son una
            # AFIRMACION suya, no una comprobacion. Publicarlos sin decir si
            # la declaracion que los trajo estaba firmada, y contra que clave,
            # hace que un nombre tecleado en un JSON a mano se lea igual que
            # uno que viene de una firma Ed25519 verificada contra la clave
            # que el lector dijo esperar.
            #
            # Por omision `sin_firma`, y no vacio: un registro escrito antes
            # de que este campo existiera no lleva confianza dentro, y lo
            # honesto ahi es lo que menos afirma. Dejarlo vacio habria hecho
            # que la pantalla se lo saltara, que es como se pierde un aviso.
            entrada["confianza"] = reg.contenido.get("confianza", "sin_firma")
            entrada["cuando"] = reg.observado_en
            entrada["registro_id"] = reg.id
            # El valor SOLO se publica cuando la respuesta cuenta. Publicarlo
            # tambien en rancia o en no_fiable seria poner al alcance de los
            # generadores de documentos un contenido que el estado dice que no
            # vale, y tarde o temprano alguno lo usaria sin mirar el estado.
            # Que la puerta este en el emisor y no en cada consumidor es la
            # diferencia entre una regla y una convencion.
            if est is Estado.VALIDA:
                entrada["valor"] = reg.contenido.get("valor")
                entrada["justificacion"] = reg.contenido.get("justificacion")
        salidas.append(entrada)

    # El desglose por CONFIANZA, junto al de estados y nunca fundido con el.
    #
    # `contestada: 40` no dice lo mismo si las cuarenta vienen de una
    # declaracion firmada y verificada que si vienen de un JSON escrito a
    # mano. Antes no habia forma de distinguirlo: una declaracion sin firma
    # valida se reimportaba con un aviso por la salida de error -- que en una
    # integracion continua no lo lee nadie -- y sus respuestas entraban en el
    # expediente indistinguibles de las demas.
    #
    # Va como un recuento aparte y NO restando del de estados a proposito.
    # Una respuesta sin firma sigue siendo una respuesta y sigue contando
    # como contestada: lo que no puede es sostener una afirmacion sobre
    # QUIEN la dio. Fundir las dos cosas en un numero obligaria a elegir cual
    # de las dos verdades se publica.
    por_confianza: dict[str, int] = {}
    for e in salidas:
        if "confianza" in e:
            por_confianza[e["confianza"]] = por_confianza.get(e["confianza"], 0) + 1

    paquetes = paquetes or {}
    por_paquete: dict[str, dict[str, Any]] = {}
    for e in salidas:
        p = por_paquete.setdefault(e["paquete"], {
            "paquete": e["paquete"],
            "titulo": paquetes.get(e["paquete"], {}).get("titulo", {"es": e["paquete"], "en": e["paquete"]}),
            "nota": paquetes.get(e["paquete"], {}).get("nota"),
            "preguntas": [],
        })
        p["preguntas"].append(e)

    recuento = {est: sum(1 for e in salidas if e["estado"] == est) for est in ESTADOS}
    return {
        "esquema": ESQUEMA,
        "fecha": ahora.date().isoformat(),
        "recuento": recuento,
        "recuento_por_confianza": por_confianza,
        "nota_de_confianza": {
            "es": "`sin_firma` es una respuesta que alguien escribió: no demuestra "
                  "autoría. `firmada` demuestra que quien tenga esa clave la firmó, no "
                  "quién es, porque la clave viaja dentro del propio documento. "
                  "`identidad_verificada` es la única que ata la respuesta a una clave "
                  "que el lector dijo esperar de antemano, y se consigue pasando "
                  "`--clave-esperada`. Lo que ninguna de las cuatro demuestra es que "
                  "quien firmó tuviera AUTORIDAD para firmar eso: eso es un hecho sobre "
                  "la organización y no sobre el documento.",
            "en": "`sin_firma` is an answer somebody wrote: it proves no authorship. "
                  "`firmada` proves whoever holds that key signed it, not who they are, "
                  "because the key travels inside the document itself. "
                  "`identidad_verificada` is the only one tying the answer to a key the "
                  "reader said in advance to expect, and it is obtained by passing "
                  "`--clave-esperada`. What none of the four proves is that the signer "
                  "had the AUTHORITY to sign that: this is a fact about the "
                  "organisation, not about the document."},
        # El vocabulario de los estados que este documento usa, para que quien
        # lo pinte no tenga que inventarse como se leen. Va aqui y no en la
        # pantalla porque los estados los inventa el motor.
        "nombres_de_estado": nombres_de(list(recuento)),
        "nota_de_recuento": {
            "es": "Son recuentos de preguntas, nunca un porcentaje de avance. Contestar veinte de treinta no es estar al 66 por ciento de cumplir nada.",
            "en": "These are counts of questions, never a progress percentage. Answering twenty of thirty is not being 66 per cent of the way to complying with anything."},
        "ahorro": {
            "preguntas_que_contesta_el_codigo": recuento["la_contesta_el_codigo"],
            "porque": sorted({a["control_id"] for a in ahorro}),
            "nota": {
                "es": "Estas preguntas no se hacen porque un control leyo los bytes que las contestan. Los identificadores de esos controles están aquí para que la resta se pueda auditar.",
                "en": "These questions are not asked because a control read the bytes that answer them. The identifiers of those controls are here so the subtraction can be audited."}},
        "preguntas": salidas,
        "paquetes": [por_paquete[k] for k in sorted(por_paquete)],
    }


def pendientes(cuestionario: dict[str, Any], destinatario: str | None = None) -> list[dict[str, Any]]:
    """Lo que hay que preguntar HOY, opcionalmente a un destinatario concreto.

    `rancia` y `superada` entran: una respuesta que caduco o que se dio a otra
    version de la pregunta hay que volver a pedirla. `no_fiable` tambien, porque
    la respuesta esta pero no admite. `espera_a` no entra, que para eso espera.
    """
    quiero = {"pendiente", "rancia", "superada", "no_fiable"}
    return [q for q in cuestionario["preguntas"]
            if q["estado"] in quiero and (destinatario is None or q["destinatario"] == destinatario)]
