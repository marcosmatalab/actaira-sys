"""El plan completo: que te ata, que se comprobo, y que hay que preguntarte.

ESTE MODULO ES EL PRODUCTO
--------------------------
Todo lo anterior son piezas. Esto las junta en la unica salida que le importa a
quien empieza de cero: una lista de obligaciones con su estado real, donde
"estado real" significa una de estas cinco cosas y nunca un porcentaje.

  COMPROBADA      un control leyo bytes y decidio
  CON_HALLAZGOS   un control leyo bytes y encontro lo que busca
  A_PREGUNTAR     el codigo no lo contiene, hay que pedirselo al cliente
  SOLO_FORMULARIO no hay bytes que leer: es organizativa de principio a fin
  FUTURA          le atara, con su fecha

POR QUE NO HAY UN ESTADO "CUMPLE" A NIVEL DE OBLIGACION
--------------------------------------------------------
Porque una obligacion la cumple una organizacion, no un control. El articulo 14
tiene cuatro comprobaciones de codigo y una pregunta sobre si la supervision es
efectiva; aunque las cuatro salgan limpias, decir "cumple el articulo 14" seria
exactamente la afirmacion que este producto existe para no hacer. Lo que se
publica es qué se comprobó y qué no, y la conclusión la firma una persona.

EL CRUCE CON LA ISO 42001 NO ES UNA COLUMNA DECORATIVA
--------------------------------------------------------
Cada obligacion arrastra los controles del Anexo A que hablan de lo mismo, y la
evidencia se reutiliza entre los dos marcos. Lo que NO se hereda es la
conclusion: que una comprobacion del articulo 12 salga limpia no cierra A.6.2.8,
porque la norma pide ademas cosas que el articulo no pide. Se dice en el plan,
en la linea `nota_cruce`, para que nadie venda una certificacion con esto.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ..aplicabilidad.motor import Perfil, Situacion, resolver
from ..catalogo.cargador import Catalogo
from ..controles.modelo import Resultado
from ..controles.motor import Arbol, Paquete, Pregunta, correr_paquete
from ..resultado.observacion import FUERZAS
from ..vocabulario import nombres_de

ESTADOS = ("comprobada", "con_hallazgos", "a_preguntar", "solo_formulario", "futura", "no_ata", "sin_resolver")


@dataclass
class LineaDelPlan:
    obligacion_id: str
    articulo: str
    titulo: dict[str, str]
    nivel: str
    estado: str
    regla_aplicabilidad: str
    fuerza_maxima: str | None = None
    fuerzas: dict[str, int] = field(default_factory=dict)
    hallazgos: list[dict[str, Any]] = field(default_factory=list)
    preguntas: list[dict[str, Any]] = field(default_factory=list)
    cubre: list[str] = field(default_factory=list)
    controles_cubiertos: list[str] = field(default_factory=list)
    no_cubre: list[str] = field(default_factory=list)
    iso42001: list[str] = field(default_factory=list)
    desde: str | None = None
    # LA PROCEDENCIA, POR REFERENCIA Y NO POR COPIA
    # -----------------------------------------------
    # El plan no lleva las capas enteras dentro: llevaria las listas de
    # ficheros leidos de cada control y dejaria de caber en una pantalla. Lleva
    # sus identificadores, que es lo que permite pedir la ejecucion y la
    # observacion completas y comprobar que el plan sale de ellas. Copiarlas
    # habria creado una segunda copia de lo mismo que nadie compara (regla 10).
    ejecucion_id: str | None = None
    observacion_id: str | None = None
    suficiencia: dict[str, Any] | None = None
    # De que analizadores y de que sujetos salio esta linea. Con dos motores
    # sobre la misma obligacion, un hallazgo tiene que poder decir de cual vino.
    procedencia: list[dict[str, Any]] = field(default_factory=list)
    # LOS DEBERES DEL ARTICULO, UNO A UNO
    # -------------------------------------
    # Un articulo con seis deberes que se cierra entero porque uno esta
    # cubierto es la manera mas rapida de emitir un expediente falso. La linea
    # del plan lleva ahora sus requisitos con el estado de cada uno, asi que
    # «el articulo 9 esta comprobado» deja de poder decirse: se dice cuantos de
    # sus cinco deberes lo estan, y que pasa con los otros.
    requisitos: list[dict[str, Any]] = field(default_factory=list)

    def a_json(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


ESTADOS_DE_REQUISITO = ("comprobado", "con_hallazgos", "a_preguntar", "sin_cubrir",
                        "no_evaluado")


def _sin_repetir(limites):
    """Los limites sin duplicados. No se puede usar `set`: llevan un dict dentro."""
    vistos, fuera = set(), []
    for l in limites:
        clave = (l.por_que, l.que["es"])
        if clave not in vistos:
            vistos.add(clave)
            fuera.append(l)
    return tuple(fuera)


def _correr_uno(ruta: Path, arbol, repositorio, artefactos, preguntas_fuera: list):
    """Corre UN paquete con el motor que el paquete declara."""
    pk = Paquete.cargar(ruta)
    if pk.motor == "agentes":
        # La estructura de agentes es OTRO sujeto: no el arbol de ficheros sino
        # el arsenal, que cambia cuando se anade una herramienta aunque no
        # cambie una linea de logica.
        from ..controles.agentes import correr as correr_ag
        return correr_ag(repositorio, ruta)
    if pk.motor == "art50":
        # Motor propio: necesita los bytes de la salida y no solo el arbol. Sin
        # artefactos aportados da INDETERMINADO con su motivo, que es lo correcto.
        from ..controles.art50 import Entrada, correr as correr50
        return correr50(Entrada(Path(repositorio), artefactos=artefactos), ruta)
    res, preg = correr_paquete(arbol, pk)
    preguntas_fuera.extend(preg)
    return res


def _juntar(resultados: list):
    """Un solo resultado a partir de varios analizadores sobre la misma obligacion.

    Se junta lo OBSERVADO -- hallazgos, senales y limites -- y se recalcula la
    proyeccion, en vez de elegir uno de los resultados o quedarse con el peor.
    Elegir habria perdido lo que vio el otro; quedarse con el peor habria
    escondido lo bueno que vio el primero.

    La ejecucion que se publica como principal es la del primer analizador, y
    la lista completa viaja en `procedencia`: un hallazgo tiene que poder
    decir de que analizador y de que sujeto salio.
    """
    if len(resultados) == 1:
        return resultados[0]
    from ..controles.modelo import ResultadoControl
    from ..resultado.observacion import Observacion

    base = resultados[0]
    obs = Observacion(
        ejecucion_id=base.ejecucion.id, control_id=base.observacion.control_id,
        hallazgos=tuple(h for r in resultados for h in r.observacion.hallazgos),
        senales=tuple(s for r in resultados for s in r.observacion.senales),
        limites=_sin_repetir([l for r in resultados for l in r.observacion.limites]))
    suf = next((r.suficiencia for r in resultados if r.suficiencia is not None), None)
    return ResultadoControl.de(base.ejecucion, obs, suf,
                               obligacion_id=base.obligacion_id)


def _estado_de_los_requisitos(catalogo, linea) -> list[dict[str, Any]]:
    """El estado de cada deber del articulo, derivado de lo que paso en la linea.

    No se recalcula nada: se mira lo que la linea ya sabe -- que controles
    salieron limpios, que hallazgos hay y que preguntas quedan -- y se reparte
    entre los deberes segun que los cubre. Recalcularlo seria una segunda
    fuente de verdad sobre lo mismo (regla 10).

    `no_evaluado` no es un fallo ni un hueco: es que el control que cubre ese
    deber no llego a correr en esta pasada, normalmente porque no se paso
    repositorio. Fundirlo con `sin_cubrir` diria que falta construir algo que
    ya esta construido.
    """
    limpios = set(linea.controles_cubiertos)
    con_hallazgo = {h["regla_id"] for h in linea.hallazgos}
    pendientes = {p.get("regla_id") for p in linea.preguntas}
    fuera = []
    for req in catalogo.requisitos_de(linea.articulo):
        if not req.cubierto:
            estado = "sin_cubrir"
        elif any(c in con_hallazgo for c in req.cubierto_por):
            estado = "con_hallazgos"
        elif any(c in pendientes for c in req.cubierto_por):
            estado = "a_preguntar"
        elif any(c in limpios for c in req.cubierto_por):
            estado = "comprobado"
        elif any(c.startswith("F-") for c in req.cubierto_por):
            estado = "a_preguntar"
        else:
            estado = "no_evaluado"
        fila = {"id": req.id, "apartados": list(req.apartados), "nivel": req.nivel,
                "actores": list(req.actores), "exige": req.exige,
                "cubierto_por": list(req.cubierto_por), "estado": estado}
        if req.por_que_no_esta_cubierto:
            fila["por_que_no_esta_cubierto"] = req.por_que_no_esta_cubierto
        fuera.append(fila)
    return fuera


def indexar_paquetes(directorio: Path) -> dict[str, list[Path]]:
    """Indexa por el campo `obligacion` que declara cada paquete, no por su nombre.

    La primera version derivaba el nombre del fichero del identificador
    (`AIA-009` -> `art009.json`) y por tanto no encontraba `art09.json`. El
    sintoma fue peor que el fallo: el plan no reventaba, sino que devolvia
    `a_preguntar` para TODO, que es una respuesta plausible y falsa. Un nombre de
    fichero que decide comportamiento es una segunda fuente de verdad sobre a que
    obligacion sirve un paquete, y la regla 10 dice que dos fuentes no se suman,
    se anulan. Ahora el nombre es libre y solo manda el contenido.

    UN paquete por obligacion era la regla, y se cambio con un motivo concreto:
    una misma obligacion puede comprobarse con DOS analizadores distintos. El
    articulo 14 se mira leyendo el arbol de ficheros -si hay una ruta de
    aprobacion, si hay una parada- y se mira leyendo la estructura de agentes
    -cuantas herramientas hay y si consta lo que hacen-. Son dos sujetos, dos
    digests y dos invalidaciones: forzarlos al mismo paquete habria obligado a
    que un cambio en el arsenal invalidara la evidencia sobre el codigo.

    Lo que NO se admite es que dos paquetes repitan un identificador de regla:
    ahi si habria dos definiciones de lo mismo.
    """
    indice: dict[str, list[Path]] = {}
    reglas_vistas: dict[str, Path] = {}
    for ruta in sorted(directorio.glob("*.json")):
        try:
            d = json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"{ruta}: paquete de reglas ilegible: {e}") from e
        obl = d.get("obligacion")
        if not obl:
            raise ValueError(f"{ruta}: el paquete no declara a que obligacion sirve")
        for r in d.get("reglas", ()):
            rid = r.get("id")
            if rid in reglas_vistas:
                raise ValueError(
                    f"la regla {rid} esta en {reglas_vistas[rid].name} y en {ruta.name}: "
                    f"dos definiciones de la misma regla se anulan")
            reglas_vistas[rid] = ruta
        indice.setdefault(obl, []).append(ruta)
    return indice


def construir(catalogo: Catalogo, perfil: Perfil, cuando: date,
              repositorio: str | Path | None, reglas: str | Path,
              artefactos: tuple[Path, ...] = ()) -> dict[str, Any]:
    reglas = Path(reglas)
    indice = indexar_paquetes(reglas)
    arbol = Arbol.leer(repositorio) if repositorio else None
    lineas: list[LineaDelPlan] = []

    for v in resolver(catalogo, perfil, cuando):
        obl = catalogo.obligaciones[v.obligacion_id]
        linea = LineaDelPlan(
            obligacion_id=obl.id, articulo=obl.articulo, titulo=obl.titulo, nivel=obl.nivel,
            estado="", regla_aplicabilidad=v.regla,
            iso42001=list(catalogo.iso_de(obl.id)),
            desde=obl.aplica_desde.isoformat(),
        )
        if v.situacion is Situacion.NO_ATA:
            linea.estado = "no_ata"
        elif v.situacion is Situacion.INDETERMINADA:
            linea.estado = "sin_resolver"
            linea.preguntas = [{"regla_id": "ALC", "texto": {
                "es": f"Falta responder: {', '.join(v.falta_responder)}",
                "en": f"Unanswered: {', '.join(v.falta_responder)}"}, "formato": "si_no"}]
        elif v.situacion is Situacion.FUTURA:
            linea.estado = "futura"
        else:
            rutas = indice.get(obl.id)
            if not rutas or arbol is None:
                linea.estado = "solo_formulario" if obl.nivel == "organizativa" else "a_preguntar"
                if not rutas and obl.nivel != "organizativa":
                    linea.preguntas = [{"regla_id": "SIN-PAQUETE", "texto": {
                        "es": "Esta obligación es de nivel comprobable y todavía no tiene paquete de reglas construido.",
                        "en": "This obligation is at a checkable tier and has no rule pack built yet."},
                        "formato": "aviso"}]
            else:
                # VARIOS paquetes por obligacion: el articulo 14 se mira en el
                # arbol de ficheros y en la estructura de agentes, que son dos
                # sujetos con dos digests. Se corren todos y se junta lo que
                # sale; cada uno publica SU procedencia, asi que el plan no
                # pierde de que analizador vino cada hallazgo.
                resultados, preguntas_todas = [], []
                for ruta in rutas:
                    resultados.append(_correr_uno(ruta, arbol, repositorio, artefactos,
                                                  preguntas_todas))
                res, preg = _juntar(resultados), preguntas_todas
                linea.ejecucion_id = res.ejecucion.id if res.ejecucion else None
                linea.observacion_id = res.observacion.id if res.observacion else None
                linea.procedencia = [
                    {"analizador": x.ejecucion.analizador, "ejecucion": x.ejecucion.id,
                     "observacion": x.observacion.id,
                     "sujeto": x.ejecucion.sujeto.a_json()}
                    for x in resultados if x.ejecucion and x.observacion]
                if res.suficiencia is not None:
                    linea.suficiencia = res.suficiencia.a_json()
                # LA FUERZA DE LO QUE RESPALDA ESTA LINEA.
                #
                # `comprobada` se imprimia igual cuando la respaldaba una regla
                # que habia encontrado una LLAMADA en el arbol sintactico --
                # una afirmacion sobre lo que el programa hace -- que cuando la
                # respaldaba un nombre de fichero que casa una expresion
                # regular. Encontrar `dataset-card.md` no demuestra que el
                # origen de los datos sea licito ni que los sesgos esten
                # medidos; demuestra que el fichero esta.
                #
                # Se publica la mas fuerte de las senales y el desglose entero:
                # la mas fuerte para poder ordenar, y el desglose para que no se
                # pueda leer «comportamiento» sobre una obligacion en la que
                # ocho de nueve senales eran de presencia.
                fuerzas = [s.fuerza for x in resultados
                           for s in (x.observacion.senales if x.observacion else ())]
                linea.fuerzas = {f: fuerzas.count(f) for f in FUERZAS if f in fuerzas}
                linea.fuerza_maxima = next((f for f in FUERZAS if f in fuerzas), None)
                linea.hallazgos = [h.a_json() for h in res.hallazgos]
                linea.preguntas = [p.a_json() for p in preg]
                linea.cubre = list(res.cubre)
                linea.controles_cubiertos = list(res.controles_cubiertos)
                linea.no_cubre = list(res.no_cubre)
                if res.resultado is Resultado.CON_HALLAZGOS:
                    linea.estado = "con_hallazgos"
                elif res.resultado is Resultado.SIN_HALLAZGOS:
                    linea.estado = "a_preguntar" if preg else "comprobada"
                elif res.resultado is Resultado.INDETERMINADO:
                    linea.estado = "a_preguntar"
                    linea.preguntas = linea.preguntas + [{
                        "regla_id": res.control_id,
                        "texto": res.motivo_indeterminado or {"es": "", "en": ""},
                        "formato": "aporte_de_artefacto"}]
                else:
                    linea.estado = "a_preguntar"
        lineas.append(linea)

    for linea in lineas:
        linea.requisitos = _estado_de_los_requisitos(catalogo, linea)

    recuento = {e: sum(1 for l in lineas if l.estado == e) for e in ESTADOS}
    recuento_requisitos = {e: 0 for e in ESTADOS_DE_REQUISITO}
    for l in lineas:
        for r in l.requisitos:
            recuento_requisitos[r["estado"]] += 1
    return {
        "esquema": "actaira/plan/v1",
        "fecha": cuando.isoformat(),
        # LO QUE NO SE PUDO LEER, que hasta ahora se perdia aqui.
        #
        # `Arbol.leer` anota cada fichero que no pudo abrir: un enlace que sale
        # de la raiz, una codificacion que no es UTF-8, un Python que no
        # analiza. El plan los tiraba. La consecuencia era que un repositorio
        # con la mitad del arbol ilegible producia exactamente el mismo
        # documento que uno leido entero, y el SARIF de salida declaraba
        # `executionSuccessful: true` sin matices.
        #
        # Una observacion parcial presentada como completa es la forma mas
        # barata de fabricar un falso limpio: lo que no se leyo no tiene
        # hallazgos, y sin esta lista nada distingue «no hay nada» de «no mire».
        # Va en el plan, no en un registro aparte, porque tiene que viajar con
        # el documento a todos los sitios a los que el documento viaja.
        "ilegibles": [{"fichero": n, "por_que": m} for n, m in (arbol.ilegibles if arbol else [])],
        "nota_de_ilegibles": {
            "es": "Ficheros que el motor no pudo leer. Lo que no se leyó no produce hallazgos, "
                  "así que su ausencia en el resto del documento no significa que esté bien: "
                  "significa que no se miró.",
            "en": "Files the engine could not read. What was not read produces no findings, so "
                  "its absence from the rest of the document does not mean it is fine: it means "
                  "it was not looked at."},
        "recuento": recuento,
        "recuento_de_requisitos": recuento_requisitos,
        "nota_de_requisitos": {
            "es": "Son los deberes concretos del Reglamento, no los artículos. Un artículo puede estar «comprobado» en uno de sus cinco deberes y no en los otros cuatro, y esa es justo la diferencia que un recuento por artículos esconde.",
            "en": "These are the Regulation's concrete duties, not its articles. An article can be 'checked' on one of its five duties and not on the other four, and that is exactly the difference an article-level count hides."},
        "nota_de_recuento": {
            "es": "Son recuentos de obligaciones, nunca proporciones. No existe un porcentaje de cumplimiento y no se va a emitir.",
            "en": "These are counts of obligations, never proportions. There is no compliance percentage and none will be emitted."},
        "nota_cruce": {
            "es": "Los controles de la ISO 42001 que aparecen en cada línea hablan de lo mismo que la obligación y comparten su evidencia. La conclusión NO se hereda: una comprobación limpia del Reglamento no cierra el control de la norma.",
            "en": "The ISO 42001 controls on each line are about the same thing as the obligation and share its evidence. The conclusion is NOT inherited: a clean check under the Regulation does not close the standard's control."},
        "total_preguntas": sum(len(l.preguntas) for l in lineas),
        # Cuantas obligaciones estan respaldadas por cada clase de senal.
        "recuento_por_fuerza": {
            f: sum(1 for l in lineas if l.fuerza_maxima == f) for f in FUERZAS},
        "nota_de_fuerza": {
            "es": "No todas las comprobaciones pesan lo mismo, y el informe las imprimía "
                  "igual. `comportamiento` es lo que el programa HACE, leído del árbol "
                  "sintáctico: una llamada al modelo, un registro que falta junto a esa "
                  "llamada. `presencia` es que un fichero o una línea de texto casan un "
                  "patrón: dice que el artefacto está, y no dice nada de si sirve. Encontrar "
                  "`dataset-card.md` no demuestra que el origen de los datos sea lícito, ni "
                  "que la representatividad esté evaluada, ni que los sesgos estén dentro de "
                  "umbrales aprobados. Mirar el fichero sigue valiendo -- su ausencia es un "
                  "hallazgo de verdad --; lo que no vale es publicar las dos con la misma cara.",
            "en": "Not all checks weigh the same, and the report printed them alike. "
                  "`comportamiento` is what the program DOES, read from the syntax tree: a "
                  "call to the model, a log missing next to that call. `presencia` is a file "
                  "or a line of text matching a pattern: it says the artefact is there, and "
                  "says nothing about whether it serves. Finding `dataset-card.md` does not "
                  "prove the data provenance is lawful, nor that representativeness was "
                  "assessed, nor that bias is within approved thresholds. Looking at the file "
                  "still counts -- its absence is a real finding -- what does not count is "
                  "publishing both with the same face."},
        # El vocabulario de los estados que ESTE documento usa. Los estados son
        # identificadores y viajan sin traducir -- traducirlos los inutilizaria
        # para comparar dos documentos --, pero alguien tiene que decir como se
        # leen, y ese alguien es el motor: si fuera la pantalla, el dia que el
        # motor anada un estado un cliente ingles veria `sin_cubrir` en crudo.
        "nombres_de_estado": nombres_de(
            list(recuento) + list(recuento_requisitos)),
        "lineas": [l.a_json() for l in lineas],
    }
