"""El control sobre una estructura de agentes, en las cinco capas.

POR QUE ESTE CONTROL TIENE SU PROPIO MOTOR
--------------------------------------------
El motor genérico barre un árbol de ficheros buscando patrones. Aquí el sujeto
no es el árbol: es la ESTRUCTURA, que se arma leyendo configuraciones de
servidores, decoradores, listas de herramientas y llamadas de delegación, y que
cambia cuando cambia el arsenal aunque no cambie ni una línea de lógica. Eso
importa para la invalidación: añadir una herramienta tiene que invalidar la
evidencia sobre las herramientas, y tocar el README no.

LO QUE ESTE CONTROL AFIRMA, Y LO QUE SE NIEGA A AFIRMAR
--------------------------------------------------------
Afirma: cuántas herramientas hay, cuáles declaran su efecto y cuáles no, si hay
servidores conectados sin inventariar, si hay algún límite declarado y si hay
delegación sin tope.

Se niega a afirmar que una herramienta sea peligrosa. Deducirlo del nombre es
el patrón que la segunda negativa prohíbe, y además falla en cuanto alguien
llama `obtener_factura` a algo que emite una factura. El hallazgo no es «esta
herramienta borra cosas»: es «de once herramientas no consta qué hacen».
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import __version__ as VERSION_MOTOR
from ..agentes import leer
from ..resultado import (Ejecucion, EstadoEjecucion, EstadoSuficiencia, Falta,
                         Observacion, Senal, Suficiencia)
from ..resultado.ejecucion import Sujeto
from ..resultado.observacion import Limite
from .deteccion import Regla, cargar_paquete
from .modelo import Hallazgo, ResultadoControl

CONTROL_ID = "ACT-C-AGENTES"
OBLIGACION = "AIA-014"
REQUISITO = "AIA-R-014-01"


def _hallazgo(r: Regla, donde: str) -> Hallazgo:
    return Hallazgo(regla_id=r.id, regla_version=r.version, autor=r.autor,
                    paquete=r.paquete, severidad=r.severidad, localizacion=donde,
                    remediacion_es=r.remediacion["es"], remediacion_en=r.remediacion["en"])


def correr(repositorio: str | Path, ruta_reglas: str | Path) -> ResultadoControl:
    empezo = Ejecucion.ahora()
    reglas = {r.id: r for r in cargar_paquete(ruta_reglas)}
    a = leer(repositorio)

    def _ejecucion(estado=EstadoEjecucion.COMPLETADA, motivo=None) -> Ejecucion:
        return Ejecucion(
            analizador="actaira/agentes", analizador_version=VERSION_MOTOR,
            paquete="actaira/agentes",
            paquete_version=next(iter(reglas.values())).version,
            sujeto=Sujeto(tipo="estructura-de-agentes", nombre=str(repositorio),
                          digest=a.digest()),
            empezo=empezo, termino=Ejecucion.ahora(), estado=estado, motivo=motivo,
            leidos=tuple(sorted(a.ficheros_leidos)))

    limites_de_siempre = [
        # LO QUE NO SE PUDO LEER, como limite y no como silencio.
        #
        # El lector descartaba en tres `continue` callados un enlace que sale de
        # la raiz, un fichero que no es UTF-8 y un Python que no analiza. Aqui
        # eso importa mas que en ningun otro control: el arsenal de un agente se
        # mide por lo que se encuentra, y «no encontre ninguna herramienta
        # porque no pude leer el fichero donde estan» se parece muchisimo a «no
        # hay herramientas». La primera es un limite y la segunda una
        # conclusion, y publicar la segunda cuando la verdad es la primera es la
        # forma mas silenciosa que tiene este control de mentir.
        *([Limite(
            {"es": (f"{len(a.ilegibles)} ficheros que no se pudieron leer "
                    f"({', '.join(n for n, _ in a.ilegibles[:4])}): lo que no se leyo "
                    f"no produce herramientas, así que su ausencia del arsenal no "
                    f"significa que no las tengan"),
             "en": (f"{len(a.ilegibles)} files that could not be read "
                    f"({', '.join(n for n, _ in a.ilegibles[:4])}): what was not read "
                    f"produces no tools, so their absence from the arsenal does not "
                    f"mean they are not there")},
            "falta_aporte")] if a.ilegibles else []),
        Limite({"es": "si una herramienta hace lo que declara hacer",
                "en": "whether a tool does what it declares"},
               "fuera_del_alcance_de_la_regla"),
        Limite({"es": "si un límite declarado se respeta en ejecución",
                "en": "whether a declared limit is honoured at runtime"},
               "fuera_del_alcance_de_la_regla"),
        Limite({"es": ("qué pasa cuando el modelo encadena dos herramientas inofensivas "
                       "para conseguir una que no lo es"),
                "en": ("what happens when the model chains two harmless tools into one "
                       "that is not")},
               "fuera_del_alcance_de_la_regla"),
        Limite({"es": "si un agente hijo hereda los permisos del padre",
                "en": "whether a child agent inherits the parent's permissions"},
               "fuera_del_alcance_de_la_regla"),
    ]

    if a.indicios_sin_lectura:
        # NI «no aplica» NI un hallazgo: no se pudo decidir, y se dice por que.
        # Un repositorio que declara un marco de agentes y no produce ninguna
        # lectura es el caso peligroso, no el inofensivo: significa que las
        # herramientas se declaran de una forma que este lector no conoce, y
        # eso pide que alguien las declare a mano, no que se le deje pasar.
        ej = _ejecucion()
        obs = Observacion(
            ejecucion_id=ej.id, control_id=CONTROL_ID,
            limites=tuple(limites_de_siempre) + (Limite(
                {"es": (f"el arsenal entero: hay marcos de agentes declarados "
                        f"({', '.join(a.marcos_declarados[:4])}) y no se pudo leer ni una "
                        f"herramienta"),
                 "en": (f"the whole arsenal: agent frameworks are declared "
                        f"({', '.join(a.marcos_declarados[:4])}) and not a single tool could "
                        f"be read")},
                "falta_aporte"),))
        suf = Suficiencia(
            requisito_id=REQUISITO, estado=EstadoSuficiencia.INDETERMINADA,
            politica="actaira/suficiencia/agentes", politica_version="1.0.0",
            falta=(Falta(
                que={"es": (f"este repositorio declara {', '.join(a.marcos_declarados[:4])} y "
                            f"no declara ninguna herramienta de una forma que se pueda leer"),
                     "en": (f"this repository declares {', '.join(a.marcos_declarados[:4])} and "
                            f"declares no tool in a readable form")},
                que_hacer={"es": ("enumera las herramientas del agente y su efecto en una "
                                  "configuración MCP o en una declaración explícita; si se "
                                  "registran en un bucle, el inventario no existe hasta que "
                                  "alguien lo escriba"),
                           "en": ("enumerate the agent's tools and their effect in an MCP "
                                  "configuration or an explicit declaration; if they are "
                                  "registered in a loop, the inventory does not exist until "
                                  "somebody writes it")},
                quien="tecnico"),),
            motivo={
                "es": ("hay marco de agentes y no hay inventario legible: no se puede decir que "
                       "este control no aplica, y tampoco se puede decir que falte algo concreto "
                       "sin saber qué hay"),
                "en": ("there is an agent framework and no readable inventory: this control "
                       "cannot be said not to apply, and nothing concrete can be said to be "
                       "missing without knowing what is there")})
        return ResultadoControl.de(ej, obs, suf, obligacion_id=OBLIGACION)

    if not a.hay_agente:
        # NO es «no hay agentes»: es que no se encontro ninguna de las formas
        # que este lector conoce. La primera seria una conclusion y la segunda
        # es un limite, y el control publica la segunda.
        ej = _ejecucion(EstadoEjecucion.NO_APLICABLE, {
            "es": (f"se leyeron {len(a.ficheros_leidos)} ficheros y no se encontró ninguna de "
                   f"las formas de declarar herramientas que este lector conoce: "
                   f"configuraciones MCP, el decorador de herramienta, listas `tools=[...]` ni "
                   f"llamadas de delegación. Eso no significa que no haya agentes: significa "
                   f"que no se vio ninguno de los que se sabe ver."),
            "en": (f"{len(a.ficheros_leidos)} files were read and none of the tool declaration "
                   f"shapes this reader knows was found: MCP configurations, the tool decorator, "
                   f"`tools=[...]` lists or delegation calls. That does not mean there are no "
                   f"agents: it means none of the ones it knows how to see was seen.")})
        obs = Observacion(ejecucion_id=ej.id, control_id=CONTROL_ID,
                          limites=tuple(limites_de_siempre))
        return ResultadoControl.de(ej, obs, obligacion_id=OBLIGACION)

    hallazgos: list[Hallazgo] = []
    senales: list[Senal] = []
    faltas: list[Falta] = []

    def _senal(rid: str, donde: str) -> None:
        r = reglas[rid]
        senales.append(Senal(regla_id=rid, regla_version=r.version, paquete=r.paquete,
                             que_se_buscaba=r.que_busca, localizacion=donde))

    # 1) el efecto de cada herramienta: declarado o no.
    sin_declarar = a.sin_declarar
    if sin_declarar:
        for h in sin_declarar:
            hallazgos.append(_hallazgo(reglas["ACT-AG-EFECTO-SIN-DECLARAR"],
                                       f"{h.nombre} ({h.localizacion})"))
    declaradas = [h for h in a.herramientas if h.efecto == "declarado"]
    if declaradas:
        _senal("ACT-AG-EFECTO-SIN-DECLARAR",
               f"{len(declaradas)} de {len(a.herramientas)} herramientas declaran su efecto: "
               + ", ".join(h.nombre for h in declaradas[:4]))

    # 2) servidores conectados sin enumerar lo que exponen.
    con_herramientas = {h.nombre.split(".")[0] for h in a.herramientas if h.origen == "mcp"}
    a_ciegas = [s for s in a.servidores_mcp if s not in con_herramientas]
    for s in a_ciegas:
        hallazgos.append(_hallazgo(reglas["ACT-AG-SERVIDOR-SIN-INVENTARIO"], s))
    if a.servidores_mcp and not a_ciegas:
        _senal("ACT-AG-SERVIDOR-SIN-INVENTARIO",
               f"los {len(a.servidores_mcp)} servidores declarados enumeran sus herramientas")

    # 3) limites.
    if not a.limites:
        hallazgos.append(_hallazgo(reglas["ACT-AG-SIN-LIMITES"], "(la estructura entera)"))
    else:
        _senal("ACT-AG-SIN-LIMITES",
               ", ".join(f"{k}: {v[0]}" for k, v in sorted(a.limites.items())))

    # 4) delegacion sin tope. Va contra los limites de PASOS, no contra
    #    cualquiera: un limite de gasto no acota una recursion, solo la encarece.
    if a.delegaciones and not a.limites.get("pasos"):
        for d in a.delegaciones:
            hallazgos.append(_hallazgo(reglas["ACT-AG-DELEGACION-SIN-TOPE"], d.localizacion))
    elif a.delegaciones:
        _senal("ACT-AG-DELEGACION-SIN-TOPE",
               f"{len(a.delegaciones)} delegaciones con tope de pasos declarado")

    # 5) lo que hay que preguntar siempre que haya agente.
    for rid, quien in (("ACT-AG-APROBACION", "responsable"),
                       ("ACT-AG-REGISTRO-DE-LLAMADAS", "tecnico"),
                       ("ACT-AG-CONTENIDO-NO-CONFIABLE", "tecnico")):
        r = reglas[rid]
        faltas.append(Falta(que=r.que_busca, que_hacer=r.remediacion, quien=quien))

    limites = list(limites_de_siempre)
    if a_ciegas:
        limites.append(Limite(
            {"es": (f"las herramientas de {len(a_ciegas)} servidores MCP que no las enumeran: "
                    f"no se inventan"),
             "en": (f"the tools of {len(a_ciegas)} MCP servers that do not enumerate them: "
                    f"they are not invented")},
            "falta_aporte"))

    ej = _ejecucion()
    obs = Observacion(ejecucion_id=ej.id, control_id=CONTROL_ID,
                      hallazgos=tuple(hallazgos), senales=tuple(senales),
                      limites=tuple(limites))
    suf = None
    if not hallazgos:
        suf = Suficiencia(
            requisito_id=REQUISITO, estado=EstadoSuficiencia.INSUFICIENTE,
            politica="actaira/suficiencia/agentes", politica_version="1.0.0",
            se_apoya_en=(obs.id,), falta=tuple(faltas))
    return ResultadoControl.de(ej, obs, suf, obligacion_id=OBLIGACION)


def preguntas_abiertas(ruta_reglas: str | Path) -> list[dict[str, Any]]:
    """Las tres preguntas que este control no puede contestar leyendo bytes."""
    return [{"regla_id": r.id, "texto": r.que_busca, "formato": "texto_largo",
             "remediacion": r.remediacion}
            for r in cargar_paquete(ruta_reglas) if r.id.startswith("ACT-AG-")
            and r.id in ("ACT-AG-APROBACION", "ACT-AG-REGISTRO-DE-LLAMADAS",
                         "ACT-AG-CONTENIDO-NO-CONFIABLE")]
