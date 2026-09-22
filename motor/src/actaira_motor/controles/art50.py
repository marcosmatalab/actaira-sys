"""El control del articulo 50, de punta a punta.

Es el unico articulo del Reglamento con la fecha ya vencida (2 de agosto de
2026) y es de codigo, asi que es el primero que se construye entero.

LAS TRES PREGUNTAS QUE RESPONDE, Y LA CUARTA QUE SE NIEGA A RESPONDER
----------------------------------------------------------------------
  1. Genera este repositorio contenido sintetico, y donde        -> AST
  2. Sale marcado lo que genera                                  -> bytes
  3. Sobrevive el marcado al pipeline de publicacion             -> medicion
  4. Cumple la organizacion el articulo 50                       -> NO

La cuarta no la responde ningun control. `cubre` y `no_cubre` llevan esa
frontera dentro del resultado y no en una nota al pie.

EL ORDEN IMPORTA, Y ES LA PARTE QUE SE HIZO MAL EN LA VERSION ANTERIOR
-----------------------------------------------------------------------
El AST solo puede decir DONDE se genera. No puede decir si la salida sale
marcada, porque eso depende de bytes que el codigo fuente no contiene. La
tentacion es mirar si en el mismo fichero aparece una llamada de marcado y
concluir que si: eso es una heuristica presentada como hecho, que es el modo de
fallo que la tercera negativa persigue.

Asi que: sin artefactos aportados, el veredicto es INDETERMINADO con su motivo
escrito, y el informe dice exactamente que hace falta para resolverlo. Con
artefactos, CUMPLE o NO_CUMPLE, y la frontera dice que ficheros se leyeron.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .deteccion import Barrido, Regla, barrer, cargar_paquete
from .motor import Arbol
from .marcado import read_facts
from .tuberia import aplicar as aplicar_tuberia
from .modelo import Hallazgo, Resultado, ResultadoControl
from .. import __version__ as VERSION_MOTOR
from ..resultado import (Ejecucion, EstadoEjecucion, EstadoSuficiencia, Falta,
                         Observacion, Senal, Suficiencia)
from ..resultado.ejecucion import Sujeto
from ..resultado.observacion import Limite

CONTROL_ID = "ACT-C-50"
# El REQUISITO, no la obligacion. El articulo 50 tiene cinco deberes distintos
# -- informar de que se habla con una IA, marcar las salidas sinteticas,
# informar en reconocimiento de emociones, divulgar ultrafalsificaciones y
# hacerlo de forma accesible -- y este control solo puede decir algo del
# segundo. Cerrar el articulo entero por el seria exactamente el fallo que los
# requisitos atomicos existen para impedir.
REQUISITO = "AIA-R-050-02"
OBLIGACION = "AIA-050"
SUFIJOS_IMAGEN = {".png", ".jpg", ".jpeg"}
CONOCIDAS_TXT = ("recomprimir_jpeg_85", "recomprimir_jpeg_60", "redimensionar_mitad",
                 "recortar_10", "rotar_90", "a_jpeg", "a_png", "quitar_metadatos")


def _hallazgo(regla: Regla, localizacion: str) -> Hallazgo:
    return Hallazgo(
        regla_id=regla.id, regla_version=regla.version, autor=regla.autor,
        paquete=regla.paquete, severidad=regla.severidad, localizacion=localizacion,
        remediacion_es=regla.remediacion["es"], remediacion_en=regla.remediacion["en"],
    )


@dataclass
class Entrada:
    """Lo que el control recibe. `artefactos` vacio no es un fallo, es un limite."""

    repositorio: Path
    artefactos: tuple[Path, ...] = ()
    pipeline: tuple[str, ...] = ()


def _sujeto(entrada: Entrada) -> Sujeto:
    """El sujeto de esta ejecucion: el repositorio Y los artefactos aportados.

    Los artefactos entran en el digest porque son parte de lo observado: la
    misma base de codigo con otro PNG aportado es otro sujeto, y una evidencia
    tomada sobre el PNG viejo no puede seguir valiendo para el nuevo. Resumir
    solo el repositorio habria hecho que cambiar la salida no invalidara nada,
    que es justo el fallo que la invalidacion por digest existe para evitar.
    """
    from ..evidencia.registro import digest as _d
    import hashlib
    arts = []
    for a in sorted(entrada.artefactos, key=lambda x: x.name):
        try:
            arts.append([a.name, hashlib.sha256(a.read_bytes()).hexdigest()])
        except OSError as e:
            arts.append([a.name, f"ilegible: {type(e).__name__}"])
    return Sujeto(tipo="repositorio+artefactos", nombre=str(entrada.repositorio),
                  digest=_d({"repositorio": Arbol.leer(entrada.repositorio).digest(),
                             "artefactos": arts,
                             "cadena": list(entrada.pipeline)}))


def _senal(regla: Regla, que: dict[str, str], loc: str) -> Senal:
    return Senal(regla_id=regla.id, regla_version=regla.version, paquete=regla.paquete,
                 que_se_buscaba=que, localizacion=loc)


def _limites_de_siempre() -> list[Limite]:
    """Lo que este control NO cubre, pase lo que pase. Viaja con el resultado."""
    return [
        Limite({"es": "video, audio y texto, que este control no lee",
                "en": "video, audio and text, which this control does not read"},
               "fuera_del_alcance_de_la_regla"),
        Limite({"es": "contenido generado fuera de este repositorio",
                "en": "content generated outside this repository"},
               "fuera_del_alcance_de_la_regla"),
        Limite({"es": "el artículo 50(4), divulgación de ultrafalsificaciones",
                "en": "Article 50(4), disclosure of deepfakes"},
               "otro_instrumento"),
        Limite({"es": ("que los artefactos aportados salgan de los puntos de generación "
                       "detectados: se leen los bytes que se entregan, y nada los liga al código"),
                "en": ("that the supplied artefacts come from the detected generation points: "
                       "the delivered bytes are read, and nothing ties them to the code")},
               "fuera_del_alcance_de_la_regla"),
    ]


def correr(entrada: Entrada, ruta_reglas: str | Path) -> ResultadoControl:
    empezo = Ejecucion.ahora()
    reglas = {r.id: r for r in cargar_paquete(ruta_reglas)}
    barrido = barrer(entrada.repositorio, list(reglas.values()))
    por_regla = barrido.por_regla

    genera_imagen = por_regla.get("ACT-50-GEN-IMG", [])
    genera_texto = por_regla.get("ACT-50-GEN-TXT", [])
    bots = por_regla.get("ACT-50-BOT", [])

    # AQUI SE COMPONIA UNA LISTA DE `fichero:linea (llamada)` Y NO SE USABA.
    #
    # No es una lista que se dejara de publicar: el campo `inspeccionado` del
    # documento lo llena `controles/modelo.py` con los ficheros LEIDOS, que es
    # lo que la pantalla pinta. Esto era otra cosa con el mismo nombre, y la
    # unica manera de saber si el documento perdio algo era mirar las dos. Se
    # quita para que quede una sola: lo que se inspecciono son los ficheros que
    # se abrieron, y las apariciones concretas viajan como senales con su
    # fichero y su linea.

    def _ejecucion(estado=EstadoEjecucion.COMPLETADA, motivo=None):
        return Ejecucion(
            analizador="actaira/art50", analizador_version=VERSION_MOTOR,
            paquete="actaira/art50", paquete_version=next(iter(reglas.values())).version,
            sujeto=_sujeto(entrada), empezo=empezo, termino=Ejecucion.ahora(),
            estado=estado, motivo=motivo,
            leidos=tuple(sorted(Arbol.leer(entrada.repositorio).texto))
                   + tuple(a.name for a in entrada.artefactos))

    if not (genera_imagen or genera_texto or bots):
        ej = _ejecucion(EstadoEjecucion.NO_APLICABLE, {
            "es": (f"se leyeron {barrido.ficheros_leidos} ficheros Python y no hay ningún punto "
                   f"de generación de contenido sintético: el artículo 50 no tiene sobre que "
                   f"morder aquí. No es que se mirara el marcado y saliera bien."),
            "en": (f"{barrido.ficheros_leidos} Python files were read and there is no synthetic "
                   f"content generation point: Article 50 has nothing to bite on here. It is not "
                   f"that the marking was looked at and came out fine.")})
        obs = Observacion(ejecucion_id=ej.id, control_id=CONTROL_ID,
                          limites=tuple(_limites_de_siempre()) + (
                              Limite({"es": "código en otros lenguajes y llamadas construidas en ejecución",
                                      "en": "code in other languages and calls built at runtime"},
                                     "fuera_del_alcance_de_la_regla"),))
        return ResultadoControl.de(ej, obs, obligacion_id=OBLIGACION)

    # GENERAR NO ES INCUMPLIR, Y ESTO ERA UN FALSO POSITIVO SISTEMATICO
    # -------------------------------------------------------------------
    # La version anterior emitia un hallazgo por CADA llamada de generacion de
    # texto y por cada punto de entrada de asistente que compartiera fichero
    # con una. Las dos cosas estaban mal por el mismo motivo:
    #
    #   * el articulo 50(4) solo obliga a divulgar el texto generado cuando se
    #     publica para informar al publico sobre asuntos de interes publico, y
    #     eso NO se lee en una llamada a una API. La propia remediacion de la
    #     regla lo decia, lo que significa que el paquete sabia que su hallazgo
    #     era mas ancho que la norma y lo emitia igual;
    #   * y la divulgacion del 50(1) es una frase en una pantalla, no una
    #     llamada: deducir que no existe porque no se ve en el AST es inferir
    #     lo no observado, que es la tercera negativa.
    #
    # Asi que los puntos de generacion y los asistentes pasan a ser SENALES
    # -- hechos, con su fichero y su linea -- y lo que queda abierto se
    # pregunta. Los hallazgos del articulo 50 son ahora solo los dos que se
    # miden sobre bytes: el marcado ausente y el marcado que la cadena borra.
    hallazgos: list[Hallazgo] = []
    preguntas_abiertas: list[Falta] = []
    if genera_texto:
        preguntas_abiertas.append(Falta(
            que={"es": (f"hay {len(genera_texto)} puntos de generación de texto y no consta si "
                        f"lo que producen se publica para informar al público sobre asuntos de "
                        f"interés público, que es cuando el artículo 50(4) obliga a divulgarlo"),
                 "en": (f"there are {len(genera_texto)} text generation points and it is not "
                        f"recorded whether what they produce is published to inform the public on "
                        f"matters of public interest, which is when Article 50(4) requires "
                        f"disclosure")},
            que_hacer={"es": ("di si ese texto se publica con esa finalidad; si se publica, "
                              "divulga que está generado artificialmente, salvo que haya revisión "
                              "editorial con responsabilidad humana"),
                       "en": ("say whether that text is published for that purpose; if it is, "
                              "disclose that it is artificially generated, unless there is "
                              "editorial review with human responsibility")},
            quien="responsable"))
    if bots:
        preguntas_abiertas.append(Falta(
            que={"es": (f"hay {len(bots)} puntos de entrada de asistente conversacional y este "
                        f"motor no puede leer si la persona recibe el aviso de que habla con una "
                        f"máquina: ese aviso es una frase en una pantalla, no una llamada"),
                 "en": (f"there are {len(bots)} conversational assistant entry points and this "
                        f"engine cannot read whether the person gets the notice that they are "
                        f"talking to a machine: that notice is a sentence on a screen, not a call")},
            que_hacer={"es": "aporta dónde consta ese aviso y en qué momento de la conversación aparece",
                       "en": "supply where that notice is recorded and at which point in the conversation it appears"},
            quien="responsable"))

    def _senales_de_generacion() -> list[Senal]:
        """Lo que SI se vio: los puntos de generacion, con su regla y su sitio.

        Antes esto no se publicaba como dato en ninguna parte: los puntos de
        generacion solo aparecian dentro de la prosa de un motivo. Un control
        que solo sabe registrar lo que falta produce el mismo informe vacio
        para un repositorio impecable y para uno que no se miro.
        """
        fuera = []
        for clave, aps in (("ACT-50-GEN-IMG", genera_imagen), ("ACT-50-GEN-TXT", genera_texto),
                           ("ACT-50-BOT", bots)):
            for a in aps:
                fuera.append(_senal(reglas[clave], reglas[clave].que_busca,
                                    f"{a.fichero}:{a.linea} ({a.llamada})"))
        return fuera

    def _no_decidible(motivo: dict[str, str], faltan: list[Falta],
                      limites_extra: list[Limite]) -> ResultadoControl:
        faltan = faltan + preguntas_abiertas
        """Una suficiencia INDETERMINADA, que es lo que estas ramas siempre fueron.

        «No puedo decidir si esto basta para el articulo 50» no es una
        observacion: es un juicio sobre si lo observado alcanza para el
        requisito. Vivia dentro del control, escrito a mano, y por eso el
        criterio no se podia cambiar sin tocar el codigo del analizador.
        """
        ej = _ejecucion()
        obs = Observacion(ejecucion_id=ej.id, control_id=CONTROL_ID,
                          hallazgos=tuple(hallazgos), senales=tuple(_senales_de_generacion()),
                          limites=tuple(_limites_de_siempre()) + tuple(limites_extra))
        suf = Suficiencia(requisito_id=REQUISITO, estado=EstadoSuficiencia.INDETERMINADA,
                          politica="actaira/suficiencia/art50", politica_version="1.0.0",
                          falta=tuple(faltan), motivo=motivo)
        return ResultadoControl.de(ej, obs, suf, obligacion_id=OBLIGACION)

    # Sin artefactos no se puede afirmar nada sobre el marcado. Tercera negativa.
    if genera_imagen and not entrada.artefactos:
        sitios = ", ".join(f"{a.fichero}:{a.linea}" for a in genera_imagen[:4])
        return _no_decidible(
            motivo={
                "es": (f"se detectaron {len(genera_imagen)} puntos de generación de imagen "
                       f"({sitios}) y no se aportó ningún artefacto generado. El código fuente "
                       f"no contiene los bytes de salida, así que el marcado no se puede leer. "
                       f"Aporta al menos un fichero producido por cada punto."),
                "en": (f"{len(genera_imagen)} image generation points were found ({sitios}) and "
                       f"no generated artefact was supplied. Source code does not contain the "
                       f"output bytes, so the marking cannot be read. Supply at least one file "
                       f"produced by each point."),
            },
            faltan=[Falta(
                que={"es": "no se ha aportado ningún artefacto generado",
                     "en": "no generated artefact has been supplied"},
                que_hacer={"es": "aporta al menos un fichero producido por cada punto de generación",
                           "en": "supply at least one file produced by each generation point"},
                quien="tecnico")],
            limites_extra=[
                Limite({"es": "el marcado de la salida", "en": "the marking of the output"},
                       "falta_aporte"),
                Limite({"es": "la durabilidad del marcado en la cadena de publicación",
                        "en": "the durability of the marking in the publication pipeline"},
                       "falta_aporte")])

    # LA CONDICION QUE ESTABA MAL, Y POR QUE ESTABA MAL
    # --------------------------------------------------
    # Decia: hallazgo solo si NO hay marcado XMP Y ADEMAS c2pa es "absent".
    # O sea: un PNG con un trozo de basura llamado `caBX` bastaba para NO
    # producir hallazgo, y el control terminaba en el estado que entonces se
    # llamaba `cumple`. Una auditoria externa lo reprodujo en una tarde.
    #
    # El error de fondo es tratar `present_unverified` como si fuera una
    # observacion a favor. No lo es: este arnes NO valida manifiestos C2PA
    # -- lo dice su propio modulo de marcado -- y «hay algo que dice llamarse
    # C2PA» es exactamente el tipo de patron que la segunda negativa prohibe
    # convertir en veredicto.
    #
    # La politica correcta tiene CUATRO ramas y ninguna las funde:
    #   XMP con un codigo del IPTC     -> marcado legible por maquina, OBSERVADO
    #   XMP con un valor que no lo es  -> hallazgo PROPIO, y no el de ausencia
    #   solo C2PA sin verificar        -> INDETERMINADO, con su motivo escrito
    #   nada de lo anterior            -> hallazgo de ausencia
    #
    # Eran tres, y la que faltaba es la segunda. `has_marking` era
    # `digital_source_type is not None`, asi que CUALQUIER valor contaba:
    # `DigitalSourceType="potato"` se publicaba como marcado legible por
    # maquina. Una auditoria externa lo probo con esa palabra exacta.
    #
    # Y no basta con mandarlo a la rama de ausencia. Un fichero con un valor
    # inventado no es un fichero sin marcar: alguien ESTA escribiendo ese campo,
    # casi siempre mal, y decirle «no marcas tus imagenes» a quien lleva meses
    # marcandolas con el valor equivocado no le dice donde mirar. Son dos
    # remediaciones distintas porque son dos problemas distintos.
    leidos, sin_marcar, ilegibles, sin_verificar, marcados_ok = [], [], [], [], []
    for art in entrada.artefactos:
        if art.suffix.lower() not in SUFIJOS_IMAGEN:
            continue
        f = read_facts(art)
        leidos.append(art.name)
        if f.marking == "present":
            marcados_ok.append(art.name)
            continue
        if f.marking == "unrecognised":
            ilegibles.append(art.name)
            hallazgos.append(_hallazgo(
                reglas["ACT-50-MARCA-ILEGIBLE"],
                f"{art.name} (DigitalSourceType={f.digital_source_type!r})"))
            continue
        if f.c2pa == "present_unverified":
            sin_verificar.append(art.name)
            continue
        sin_marcar.append(art.name)
        hallazgos.append(_hallazgo(reglas["ACT-50-MARCA-AUSENTE"], art.name))

    # Solo si hay algo que marcar. Sin ningun punto de generacion de imagen, la
    # ausencia de artefactos de imagen no es una falta: es que no habia nada
    # que aportar. La version anterior pedia «aporta un PNG» a un repositorio
    # que solo genera texto, y una herramienta que pide lo que no hace falta
    # entrena a la gente a ignorar lo que pide.
    if genera_imagen and not leidos:
        return _no_decidible(
            motivo={"es": "no se aportó ningún artefacto PNG o JPEG legible",
                    "en": "no readable PNG or JPEG artefact was supplied"},
            faltan=[Falta(
                que={"es": "no hay ningún artefacto de imagen legible entre los aportados",
                     "en": "there is no readable image artefact among those supplied"},
                que_hacer={"es": "aporta un PNG o un JPEG producido por el sistema",
                           "en": "supply a PNG or JPEG produced by the system"},
                quien="tecnico")],
            limites_extra=[Limite({"es": "el marcado de la salida",
                                   "en": "the marking of the output"}, "falta_aporte")])

    cubre: tuple[str, ...] = (f"{len(leidos)} artefactos leidos byte a byte: {', '.join(leidos)}",
             f"{barrido.ficheros_leidos} ficheros Python analizados")
    no_cubre = ("que los artefactos aportados salgan de los puntos de generacion "
                "detectados: se leen los bytes que se entregan, y nada los liga al codigo",
                "video, audio y texto, que este control no lee",
                "contenido generado fuera de este repositorio",
                *(("la durabilidad del marcado: no se declaro ninguna cadena de publicacion",)
                  if not entrada.pipeline else ()),
                "el articulo 50(4), divulgacion de ultrafalsificaciones")
    if barrido.ficheros_ilegibles:
        no_cubre = no_cubre + (f"{len(barrido.ficheros_ilegibles)} ficheros que no se pudieron analizar",)

    # LA TERCERA PREGUNTA, QUE ANTES SE ACEPTABA Y SE IGNORABA
    # ---------------------------------------------------------
    # `pipeline` llevaba desde la fase 2 en el contrato y no lo leia nadie.
    # Ahora se aplica de verdad: se pasa cada artefacto MARCADO por la cadena
    # que el cliente declara y se vuelve a leer al final. Si el marcado no
    # sobrevive, el hallazgo dice en que paso se perdio, porque asi el cliente
    # cambia un paso y no su cadena entera.
    perdidos: list[str] = []
    if entrada.pipeline:
        import tempfile
        marcados = [a for a in entrada.artefactos
                    if a.suffix.lower() in SUFIJOS_IMAGEN and read_facts(a).has_marking]
        with tempfile.TemporaryDirectory() as tmp:
            for art in marcados:
                pasos, desconocidos = aplicar_tuberia(art, entrada.pipeline, Path(tmp) / art.stem)
                if desconocidos:
                    return _no_decidible(
                        motivo={
                            "es": (f"la cadena declara pasos que este motor no sabe aplicar "
                                   f"({', '.join(desconocidos)}). No se salta ninguno y se mide el "
                                   f"resto: medir una cadena que no es la suya daria un número "
                                   f"más bonito sobre otra cosa. Los pasos conocidos son "
                                   f"{', '.join(CONOCIDAS_TXT)}."),
                            "en": (f"the pipeline declares steps this engine cannot apply "
                                   f"({', '.join(desconocidos)}). None is skipped and the rest is "
                                   f"not measured: measuring a pipeline that is not yours would "
                                   f"give a prettier number about something else. Known steps are "
                                   f"{', '.join(CONOCIDAS_TXT)}.")},
                        faltan=[Falta(
                            que={"es": f"la cadena declara pasos desconocidos: {', '.join(desconocidos)}",
                                 "en": f"the pipeline declares unknown steps: {', '.join(desconocidos)}"},
                            que_hacer={"es": ("usa solo pasos que este motor sepa aplicar, o aporta "
                                              "el artefacto ya pasado por tu cadena"),
                                       "en": ("use only steps this engine can apply, or supply the "
                                              "artefact already run through your pipeline")},
                            quien="tecnico")],
                        limites_extra=[Limite(
                            {"es": "la durabilidad del marcado en la cadena declarada",
                             "en": "the durability of the marking in the declared pipeline"},
                            "falta_aporte")])
                if pasos and not pasos[0].aplicado:
                    return _no_decidible(
                        motivo={
                            "es": f"no se pudo medir la cadena: {pasos[0].motivo}",
                            "en": f"the pipeline could not be measured: {pasos[0].motivo}"},
                        faltan=[Falta(
                            que={"es": f"la cadena no se pudo aplicar: {pasos[0].motivo}",
                                 "en": f"the pipeline could not be applied: {pasos[0].motivo}"},
                            que_hacer={"es": "instala Pillow o aporta el artefacto ya procesado",
                                       "en": "install Pillow or supply the already processed artefact"},
                            quien="tecnico")],
                        limites_extra=[Limite(
                            {"es": "la durabilidad del marcado en la cadena declarada",
                             "en": "the durability of the marking in the declared pipeline"},
                            "falta_aporte")])
                # `pasos` viene de la hipotesis PESIMISTA -- herramientas que
                # reescriben los pixeles y descartan los metadatos -- y aqui se
                # aplica ademas la OPTIMISTA, que arrastra el XMP paso a paso.
                #
                # Hasta ahora solo se aplicaba la pesimista, y como Pillow
                # descarta los metadatos al guardar SIEMPRE, el resultado no
                # dependia de la cadena: rotar noventa grados salia igual de
                # destructivo que quitar los metadatos a proposito. Una medicion
                # cuya respuesta no cambia con la entrada no esta midiendo la
                # entrada; estaba midiendo Pillow.
                #
                # La pregunta de la que de verdad depende -- si las herramientas
                # CONCRETAS del cliente conservan los metadatos -- no se puede
                # contestar leyendo bytes: `convert` los conserva y `convert
                # -strip` no, y los dos se declaran aqui con el mismo nombre de
                # paso. Asi que no se elige una hipotesis y se presenta como la
                # verdad: se miden las dos y se dice cual es cual.
                buenos, _ = aplicar_tuberia(art, entrada.pipeline,
                                            Path(tmp) / (art.stem + "-conserva"),
                                            conservar_metadatos=True)
                murio_siempre = next(
                    (x for x in pasos if not read_facts(x.salida).has_marking), None)
                murio_conservando = next(
                    (x for x in buenos if not read_facts(x.salida).has_marking), None)

                if murio_conservando is not None:
                    # No sobrevive ni en el mejor caso: la cadena lo destruye,
                    # hagan lo que hagan las herramientas.
                    perdidos.append(
                        f"{art.name} pierde el marcado en el paso {murio_conservando.nombre}")
                    hallazgos.append(_hallazgo(reglas["ACT-50-PIPE-BORRA"],
                                               f"{art.name} -> {murio_conservando.nombre}"))
                elif murio_siempre is not None:
                    # Sobrevive si las herramientas conservan y no si no. El
                    # hallazgo no es sobre la cadena: es sobre depender de eso.
                    hallazgos.append(_hallazgo(
                        reglas["ACT-50-PIPE-FRAGIL"],
                        f"{art.name} -> {murio_siempre.nombre}"))

        cubre = cubre + (
            f"{len(marcados)} artefactos marcados pasados por {len(entrada.pipeline)} pasos "
            f"de la cadena declarada, en las dos hipotesis: herramientas que conservan los "
            f"metadatos y herramientas que no",)
        no_cubre = no_cubre + (
            "cual de las dos hipotesis es la tuya: que `convert` conserve el XMP o que lo "
            "tire con `-strip` no se distingue por el nombre del paso, y este motor no "
            "ejecuta tus herramientas",)

    # LA FRONTERA SE PUBLICA SIEMPRE, HAYA HALLAZGOS O NO
    # -----------------------------------------------------
    # La primera version solo hablaba de los artefactos indecidibles cuando NO
    # habia ningun hallazgo. Con dos artefactos sin marcar y uno con un trozo
    # C2PA sin verificar, el informe salia con dos hallazgos y ni una palabra
    # del tercero: quien lo leyera entenderia que el resto esta bien. Callar lo
    # que no se pudo decidir porque hay otra cosa que contar es inferir lo no
    # observado por omision, que es la tercera negativa por la puerta de atras.
    if sin_verificar:
        no_cubre = no_cubre + (
            f"la validez de los manifiestos C2PA, que este arnes no comprueba: "
            f"{len(sin_verificar)} artefactos ({', '.join(sin_verificar[:4])}) quedan sin decidir",)

    # EL CIERRE, YA SOBRE LAS CINCO CAPAS
    # -------------------------------------
    # Lo que se vio son senales y hallazgos. Si eso ALCANZA para el articulo 50
    # lo decide una suficiencia, citada por su identificador y su version, y no
    # una rama escrita a mano dentro del analizador. La diferencia se nota el
    # dia que alguien quiere cambiar el criterio: hoy se cambia la politica y se
    # ve en el diff; antes se cambiaba el control y el diff mezclaba «cambie lo
    # que miro» con «cambie lo que me parece suficiente».
    senales = _senales_de_generacion()
    for nombre in marcados_ok:
        senales.append(_senal(reglas["ACT-50-MARCA-AUSENTE"],
                              {"es": "marcado XMP con digitalSourceType, leído byte a byte",
                               "en": "XMP marking with digitalSourceType, read byte by byte"},
                              nombre))

    limites = _limites_de_siempre()
    if barrido.ficheros_ilegibles:
        limites.append(Limite(
            {"es": f"{len(barrido.ficheros_ilegibles)} ficheros que no se pudieron analizar",
             "en": f"{len(barrido.ficheros_ilegibles)} files that could not be analysed"},
            "no_legible"))
    if not entrada.pipeline:
        limites.append(Limite(
            {"es": "la durabilidad del marcado: no se declaró ninguna cadena de publicación",
             "en": "the durability of the marking: no publication pipeline was declared"},
            "falta_aporte"))
    if sin_verificar:
        limites.append(Limite(
            {"es": (f"la validez de los manifiestos C2PA, que este arnés no comprueba: "
                    f"{len(sin_verificar)} artefactos ({', '.join(sin_verificar[:4])}) "
                    f"quedan sin decidir"),
             "en": (f"the validity of C2PA manifests, which this harness does not check: "
                    f"{len(sin_verificar)} artefacts ({', '.join(sin_verificar[:4])}) "
                    f"remain undecided")},
            "falta_aporte"))

    ej = _ejecucion()
    obs = Observacion(ejecucion_id=ej.id, control_id=CONTROL_ID,
                      hallazgos=tuple(hallazgos), senales=tuple(senales),
                      limites=tuple(limites))

    if hallazgos:
        # `if hallazgos:` y no `if sin_marcar or perdidos:`.
        #
        # La regla es «hay hallazgos, la suficiencia no anade nada», y estaba
        # escrita enumerando los cubos que producian hallazgos EN AQUEL
        # MOMENTO. En cuanto se anadio un hallazgo nuevo -- el de la cadena que
        # solo sobrevive si las herramientas conservan metadatos -- la
        # enumeracion se quedo corta y el control empezo a emitir un veredicto
        # de suficiencia teniendo hallazgos delante. Lo cazo la puerta que fija
        # el invariante, no la que anadio el hallazgo.
        #
        # Una condicion que enumera los casos en vez de preguntar por la
        # propiedad se queda corta siempre que alguien anade un caso, y el que
        # lo anade no tiene motivo para acordarse de esta linea.
        suf = None
    elif sin_verificar:
        suf = Suficiencia(
            requisito_id=REQUISITO, estado=EstadoSuficiencia.INDETERMINADA,
            politica="actaira/suficiencia/art50", politica_version="1.0.0",
            falta=(Falta(
                que={"es": f"{len(sin_verificar)} artefactos llevan algo que dice ser un "
                           f"manifiesto C2PA y este arnés NO comprueba manifiestos",
                     "en": f"{len(sin_verificar)} artefacts carry something claiming to be a "
                           f"C2PA manifest and this harness does NOT check manifests"},
                que_hacer={"es": ("añade el paquete XMP con digitalSourceType, que se lee sin "
                                  "confiar en nadie, o valida los manifiestos con c2patool y "
                                  "aporta su salida"),
                           "en": ("add the XMP packet with digitalSourceType, readable without "
                                  "trusting anyone, or validate the manifests with c2patool and "
                                  "supply its output")},
                quien="tecnico"),),
            motivo={
                "es": (f"{len(sin_verificar)} artefactos ({', '.join(sin_verificar[:4])}) llevan algo "
                       f"que dice ser un manifiesto C2PA y este arnés NO comprueba manifiestos: hacen "
                       f"falta la cadena de confianza y el validador oficial. Sin eso, «hay un trozo "
                       f"llamado C2PA» no es marcado observado."),
                "en": (f"{len(sin_verificar)} artefacts ({', '.join(sin_verificar[:4])}) carry "
                       f"something claiming to be a C2PA manifest and this harness does NOT check "
                       f"manifests: that needs the trust chain and the official validator. Without "
                       f"it, 'there is a chunk called C2PA' is not observed marking.")})
    elif not marcados_ok:
        # Va DESPUES de `sin_verificar` a proposito: un artefacto con un trozo
        # C2PA sin verificar tampoco esta marcado, y si esta rama fuera antes se
        # tragaria ese caso y el cliente recibiria «no aportaste nada» en vez de
        # «lo que aportaste no se puede validar». Lo concreto antes que lo generico.
        # Ningun artefacto de imagen que juzgar. Eso NO es suficiente: el
        # articulo 50(2) habla de audio, imagen, video Y TEXTO, y de los cuatro
        # este arnes solo sabe leer dos contenedores de imagen. Decir
        # SUFICIENTE aqui seria cerrar el marcado del texto sin haberlo mirado,
        # que es la tercera negativa. Se dice que no se puede decidir, con lo
        # que falta para decidirlo.
        suf = Suficiencia(
            requisito_id=REQUISITO, estado=EstadoSuficiencia.INDETERMINADA,
            politica="actaira/suficiencia/art50", politica_version="1.0.0",
            falta=tuple(preguntas_abiertas) + (Falta(
                que={"es": "no se aportó ningún artefacto de imagen sobre el que leer el marcado",
                     "en": "no image artefact was supplied on which to read the marking"},
                que_hacer={"es": "aporta un PNG o un JPEG producido por el sistema",
                           "en": "supply a PNG or JPEG produced by the system"},
                quien="tecnico"),) if genera_imagen else tuple(preguntas_abiertas),
            motivo={
                "es": ("el artículo 50(2) alcanza al audio, la imagen, el vídeo y el texto, y este "
                       "arnés solo sabe leer el marcado de PNG y JPEG. Lo que no se ha podido leer "
                       "no se da por bueno."),
                "en": ("Article 50(2) reaches audio, image, video and text, and this harness only "
                       "knows how to read PNG and JPEG marking. What could not be read is not "
                       "taken as fine.")})
    else:
        # SUFICIENTE no es «cumple»: dice que la evidencia que el requisito pide
        # esta y se leyo. La conclusion juridica la firma una persona, capa 5.
        # Hay marcado leido byte a byte. Si ademas queda algo por contestar --
        # el texto que se publica, el aviso del asistente -- eso NO desaparece
        # porque las imagenes esten bien: se dice y baja a insuficiente.
        if preguntas_abiertas:
            suf = Suficiencia(
                requisito_id=REQUISITO, estado=EstadoSuficiencia.INSUFICIENTE,
                politica="actaira/suficiencia/art50", politica_version="1.0.0",
                se_apoya_en=(obs.id,), falta=tuple(preguntas_abiertas))
        else:
            suf = Suficiencia(
                requisito_id=REQUISITO, estado=EstadoSuficiencia.SUFICIENTE,
                politica="actaira/suficiencia/art50", politica_version="1.0.0",
                se_apoya_en=(obs.id,))

    return ResultadoControl.de(ej, obs, suf, obligacion_id=OBLIGACION)
