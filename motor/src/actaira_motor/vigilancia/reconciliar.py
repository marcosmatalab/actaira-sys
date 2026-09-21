"""La vigilancia: que sigue valiendo, que caduco, y que hay que volver a mirar.

LO QUE HACE, Y LO QUE DELIBERADAMENTE NO HACE
-----------------------------------------------
Recibe el almacen de evidencia y una foto de los sujetos de AHORA -- el digest
actual de cada cosa observada -- y responde tres preguntas:

  que sigue VALIDA          nada que hacer
  que caduco (RANCIA)       hay que volver a observarlo, igual que antes
  que cambio (SUPERADA)     hay que volver a observarlo PORQUE cambio

La diferencia entre las dos ultimas es la que casi todas las herramientas
funden, y fundirla pierde exactamente la informacion que hace falta: "nadie ha
mirado ultimamente" pide una repeticion; "alguien cambio el modelo" pide una
revision, y probablemente una conversacion.

Lo que NO hace: decidir. Emite `a_reobservar` con los identificadores y el
motivo de cada uno, y ahi se acaba su trabajo. Cuarta negativa: nunca actuar
sobre lo observado. Quien decide si eso bloquea un despliegue es la puerta de
integracion continua del cliente, con su propio criterio escrito.

EL ARGUMENTO DE COSTE, QUE ES UN ARGUMENTO DE PRODUCTO
--------------------------------------------------------
Sondear N repositorios cada minuto son N x 1440 ejecuciones al dia. Reaccionar
a un empujon mas un vencimiento son del orden de las veces que el cliente
commitea, mas una. Dos ordenes de magnitud menos de computo para una afirmacion
MAS fuerte, porque una evidencia atada a un digest dice sobre que exactamente
sigue valiendo, y un sondeo solo dice que en su momento paso.

`ahorro_de_barridos` publica ese numero en cada reconciliacion: cuantos
controles habria que correr si se corrieran todos, y cuantos hay que correr de
verdad. Con la lista, para que se pueda auditar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..evidencia.registro import Estado
from .almacen import Almacen

ESQUEMA = "actaira/vigilancia/v1"

# Cada cuanto hay que volver a observar, por nivel de comprobabilidad. No es
# una constante universal: es la politica por defecto de esta casa, y el
# cliente la cambia. Se escribe aqui una vez para que la escriba una vez.
FRESCURA_POR_NIVEL = {
    "maquina": 30,        # lo decide el codigo y el codigo cambia todas las semanas
    "generable": 90,      # un documento generado envejece con su fuente
    "juzgada": 180,       # un juicio humano aguanta mas, pero no para siempre
    "organizativa": 365,  # una politica se revisa al ano, y la norma lo pide
}

ACCION = {
    Estado.VALIDA: "nada",
    Estado.RANCIA: "reobservar",
    Estado.SUPERADA: "reobservar",
    Estado.REVOCADA: "reobservar",
    Estado.NO_FIABLE: "corregir",
}

MOTIVOS = {
    "rancia": {"es": "caduco: han pasado más días de los que su frescura permite",
               "en": "expired: more days have passed than its freshness allows"},
    "superada": {"es": "el sujeto cambio: lo que se observo ya no es lo que hay",
                 "en": "the subject changed: what was observed is no longer what is there"},
    "revocada": {"es": "se retiro la atestación o la clave que la sostenia",
                 "en": "the attestation or key behind it was withdrawn"},
    "no_fiable": {"es": "esta integra y la política de confianza de aquí no la acepta",
                  "en": "it is intact and this environment's trust policy does not accept it"},
    "sin_evidencia": {"es": "nunca se observo: no hay nada que caducar",
                      "en": "never observed: there is nothing to expire"},
    "fuera_de_alcance": {
        "es": "hay evidencia de esto y este perfil ya no lo espera: cambio el alcance",
        "en": "there is evidence of this and this profile no longer expects it: the scope changed"},
}


@dataclass
class Veredicto:
    control_id: str
    obligacion_id: str
    estado: str
    accion: str
    motivo: dict[str, str]
    detalle: str | None = None
    observado_en: str | None = None
    revalidado_en: str | None = None
    registro_id: str | None = None

    def a_json(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Reconciliacion:
    fecha: str
    veredictos: list[Veredicto] = field(default_factory=list)

    def a_json(self) -> dict[str, Any]:
        recuento: dict[str, int] = {}
        for v in self.veredictos:
            recuento[v.estado] = recuento.get(v.estado, 0) + 1
        reobservar = [v for v in self.veredictos if v.accion == "reobservar"]
        return {
            "esquema": ESQUEMA,
            "fecha": self.fecha,
            "recuento": recuento,
            "a_reobservar": [v.control_id for v in reobservar],
            "ahorro_de_barridos": {
                "controles_con_evidencia": len(self.veredictos),
                "hay_que_volver_a_correr": len(reobservar),
                "nota": {
                    "es": "Un sondeo correría los controles_con_evidencia enteros en cada pasada. "
                          "Aquí se corren solo los que caducaron o cuyo sujeto cambio, y cada uno "
                          "dice por que. El resto sigue valiendo para el digest sobre el que se tomo.",
                    "en": "Polling would run all controles_con_evidencia on every pass. Here only "
                          "those that expired or whose subject changed are run, and each says why. "
                          "The rest still holds for the digest it was taken on."}},
            "nota_de_no_accion": {
                "es": "Esta salida dice que hay que volver a mirar. NO decide si eso bloquea un "
                      "despliegue: eso lo decide la puerta del cliente, con su criterio escrito.",
                "en": "This output says what must be looked at again. It does NOT decide whether "
                      "that blocks a deployment: the client's own gate decides, by its written criteria."},
            "veredictos": [v.a_json() for v in self.veredictos],
        }


def reconciliar(almacen: Almacen, sujetos_ahora: dict[str, str], ahora: datetime,
                confiables: frozenset[str] | None = None,
                esperados: dict[str, str] | None = None) -> Reconciliacion:
    """`sujetos_ahora` es {control_id: digest de AHORA}. `esperados` es
    {control_id: obligacion_id} de todo lo que DEBERIA tener evidencia.

    Un control esperado del que no hay ninguna observacion sale con estado
    `sin_evidencia` y accion `reobservar`. Omitirlo seria el fallo silencioso de
    manual: el informe saldria limpio porque no se miro, y limpio-por-no-mirar
    es indistinguible de limpio a simple vista.
    """
    revocadas = almacen.revocadas()
    revalidado = almacen.revalidaciones()
    registros = almacen.registros()
    ultima: dict[str, Any] = {}
    for r in registros:
        previo = ultima.get(r.control_id)
        if previo is None or (datetime.fromisoformat(r.observado_en)
                              > datetime.fromisoformat(previo.observado_en)):
            ultima[r.control_id] = r

    rec = Reconciliacion(fecha=ahora.date().isoformat())
    for cid, r in sorted(ultima.items()):
        if esperados is not None and cid not in esperados and cid not in sujetos_ahora:
            # Hay evidencia de un control que este perfil ya no espera: cambio
            # el alcance, o el sistema dejo de ser de alto riesgo. Dejarla
            # contar como VALIDA seria sostener el expediente de hoy con una
            # observacion sobre otra cosa. Se dice, y no se cuenta.
            rec.veredictos.append(Veredicto(
                control_id=cid, obligacion_id=r.obligacion_id, estado="fuera_de_alcance",
                accion="nada", motivo=MOTIVOS["fuera_de_alcance"],
                observado_en=r.observado_en, registro_id=r.id))
            continue
        est, detalle = r.estado(ahora, digest_actual_del_sujeto=sujetos_ahora.get(cid),
                                revocadas=revocadas, confiables=confiables,
                                visto_de_nuevo=revalidado.get(r.id))
        rec.veredictos.append(Veredicto(
            control_id=cid, obligacion_id=r.obligacion_id, estado=est.value,
            accion=ACCION[est], motivo=MOTIVOS.get(est.value, MOTIVOS["sin_evidencia"]),
            detalle=detalle, observado_en=r.observado_en, registro_id=r.id))

    for cid, oid in sorted((esperados or {}).items()):
        if cid in ultima:
            continue
        rec.veredictos.append(Veredicto(
            control_id=cid, obligacion_id=oid, estado="sin_evidencia",
            accion="reobservar", motivo=MOTIVOS["sin_evidencia"]))
    return rec
