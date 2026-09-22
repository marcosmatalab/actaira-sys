"""Evidencia con identidad, con vida y con un motivo por el que dejo de contar.

PORTADO de actaira v2.3.0 `state/evidence.py`, nota de diseno D-223. Se trae
entero porque es el foso: todos los competidores demuestran que el registro no
fue alterado, ninguno que la conclusion siga siendo cierta.

Los cinco estados son los que de verdad ocurren, y separarlos importa porque
piden acciones distintas:

  VALIDA      sigue valiendo para exactamente el sujeto sobre el que se tomo
  RANCIA      mas vieja que la frescura que la politica exige, vuelve a observar
  SUPERADA    una observacion posterior de lo mismo sobre el mismo sujeto
  REVOCADA    la clave, la fuente o la atestacion se retiraron
  NO_FIABLE   integra, y la politica de confianza de aqui no la acepta

RANCIA y SUPERADA son el par que casi todas las herramientas funden, y fundirlo
pierde la diferencia entre "nadie ha mirado ultimamente" y "alguien miro y esta
no es la respuesta actual". REVOCADA y NO_FIABLE son el otro par: la primera es
un hecho sobre el mundo, la segunda una decision tomada aqui.

LA REGLA QUE DA FORMA A LAS TRANSICIONES, Y ES LA QUE CONVIERTE ESTO EN
VIGILANCIA CONTINUA SIN SONDEAR NADA
-----------------------------------------------------------------------
A la evidencia la supera EL DIGEST sobre el que se tomo, nunca el nombre de su
sujeto. Un barrido de un modelo que no cambio no supera nada, y uno de un
modelo que si cambio supera solo la evidencia atada al digest viejo, con lo que
la evidencia sobre un artefacto hermano que nadie toco sigue valida. Esa es la
diferencia entre una invalidacion sobre la que se puede actuar y un muro rojo.

Y de ahi sale el argumento de coste: sondear N repositorios cada minuto son
N x 1440 ejecuciones diarias; reaccionar a un empujon mas un vencimiento son
del orden de las veces que el cliente commitea, mas una. Dos ordenes de
magnitud menos de computo para una afirmacion mas fuerte.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

ESQUEMA = "actaira/evidencia/v1"


class Estado(str, Enum):
    VALIDA = "valida"
    RANCIA = "rancia"
    SUPERADA = "superada"
    REVOCADA = "revocada"
    NO_FIABLE = "no_fiable"

    @property
    def cuenta(self) -> bool:
        """Solo VALIDA. Los otros cuatro no son grados de confianza.

        Una politica que aceptara "rancia" como casi-valida seria una politica
        sin requisito de frescura, que es lo mismo que no tenerla.
        """
        return self is Estado.VALIDA


def canonico(obj: Any) -> bytes:
    """Mismo contenido, mismos bytes. Sin esto ninguna firma del arbol vale nada."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonico(obj)).hexdigest()


@dataclass(frozen=True)
class Registro:
    """Una observacion, atada al digest de su sujeto y no a su nombre."""

    id: str
    obligacion_id: str
    control_id: str
    sujeto_digest: str
    observado_en: str
    contenido: dict[str, Any]
    frescura_dias: int | None = None
    estado_declarado: Estado = Estado.VALIDA
    motivo: str | None = None
    esquema: str = ESQUEMA

    def cuerpo(self) -> dict[str, Any]:
        """Lo que el identificador resume. UNA definicion, y esta es.

        Vive aqui y no en quien calcula el digest porque hay dos sitios que lo
        necesitan -- crear el registro y comprobarlo al leerlo -- y si cada uno
        escribiera su propia version, la comprobacion pasaria a comprobar su
        copia en vez del original. Regla 10: dos comprobaciones sobre la misma
        propiedad comparten su definicion o se anulan.
        """
        return {"esquema": self.esquema, "obligacion_id": self.obligacion_id,
                "control_id": self.control_id, "sujeto_digest": self.sujeto_digest,
                "observado_en": self.observado_en, "contenido": self.contenido}

    def verificar_id(self) -> str | None:
        """El motivo por el que el identificador no resume este contenido, o None.

        Un identificador que no se recalcula es un numero de serie: se queda
        igual mientras alguien edita lo que hay debajo. Recalcularlo al leer
        convierte la edicion a mano en un error visible en vez de en una
        evidencia nueva.
        """
        real = digest(self.cuerpo())
        if real == self.id:
            return None
        return (f"el registro dice llamarse {self.id[:23]}... y su contenido resume "
                f"{real[:23]}...: fue editado despues de observarse")

    @staticmethod
    def nuevo(obligacion_id: str, control_id: str, sujeto_digest: str,
              observado_en: datetime, contenido: dict[str, Any],
              frescura_dias: int | None = None) -> "Registro":
        provisional = Registro(
            id="", obligacion_id=obligacion_id, control_id=control_id,
            sujeto_digest=sujeto_digest,
            observado_en=observado_en.astimezone(timezone.utc).isoformat(),
            contenido=contenido, frescura_dias=frescura_dias,
        )
        return replace(provisional, id=digest(provisional.cuerpo()))

    def estado(self, ahora: datetime, digest_actual_del_sujeto: str | None = None,
               revocadas: frozenset[str] = frozenset(),
               confiables: frozenset[str] | None = None,
               visto_de_nuevo: str | None = None) -> tuple[Estado, dict[str, str]]:
        """El estado AHORA. El tiempo es un argumento, nunca una llamada al reloj.

        El orden de las comprobaciones no es arbitrario y esta puesto de peor a
        menos grave: una evidencia revocada que ademas esta rancia se reporta
        como revocada, porque volver a observarla no arreglaria nada.

        `visto_de_nuevo` es la ultima vez que se volvio a observar EXACTAMENTE
        esto -- mismo control, mismo sujeto, mismo resultado -- y solo mueve el
        reloj de la frescura. Es un hecho distinto de la observacion original y
        por eso no cambia el registro ni su identificador: que el 3 de abril
        siguiera siendo verdad lo que se vio el 1 de enero no reescribe el 1 de
        enero. Sin esto, o el almacen guarda el registro entero en cada pasada
        de integracion continua -- y su tamano mide la frecuencia del cron en
        vez de la actividad del cliente -- o la evidencia caduca aunque alguien
        la este mirando cada dia.
        """
        if self.estado_declarado is not Estado.VALIDA:
            if self.motivo:
                # El motivo declarado lo escribio quien creo el registro -- por
                # ejemplo la admisibilidad de una respuesta -- y llega como una
                # cadena. Se devuelve en las dos claves antes que traducirlo
                # mal: decir en ingles algo que no se dijo es peor que decirlo
                # en castellano.
                return self.estado_declarado, {"es": self.motivo, "en": self.motivo}
            return self.estado_declarado, {
                "es": "estado declarado en el propio registro",
                "en": "state declared in the record itself"}
        if self.id in revocadas:
            return Estado.REVOCADA, {
                "es": "la atestación o la clave detrás de esta evidencia se retiró",
                "en": "the attestation or key behind this evidence was withdrawn"}
        if confiables is not None and self.control_id not in confiables:
            return Estado.NO_FIABLE, {
                "es": f"la política de confianza de este entorno no acepta {self.control_id}",
                "en": f"this environment's trust policy does not accept {self.control_id}"}
        if digest_actual_del_sujeto is not None and digest_actual_del_sujeto != self.sujeto_digest:
            return (Estado.SUPERADA, {
                "es": f"el sujeto cambió: se observó {self.sujeto_digest[:23]}... y ahora es "
                      f"{digest_actual_del_sujeto[:23]}...",
                "en": f"the subject changed: {self.sujeto_digest[:23]}... was observed and it is "
                      f"now {digest_actual_del_sujeto[:23]}..."})
        if self.frescura_dias is not None:
            # max() sobre las FECHAS, no sobre las cadenas: "2027-12-02T10:00+02:00"
            # es anterior a "2027-12-02T09:00+00:00" y ordenarlas como texto da
            # la respuesta contraria. Lo que escribe esta casa va normalizado a
            # UTC, pero un almacen puede traer lineas de otra herramienta.
            desde = max(datetime.fromisoformat(self.observado_en),
                        datetime.fromisoformat(visto_de_nuevo or self.observado_en))
            limite = desde + timedelta(days=self.frescura_dias)
            if ahora.astimezone(timezone.utc) > limite:
                reval = (visto_de_nuevo and datetime.fromisoformat(visto_de_nuevo)
                         > datetime.fromisoformat(self.observado_en))
                cola_es = (f", y la última revalidación es del {desde.date().isoformat()}"
                           if reval else "")
                cola_en = (f", and the last revalidation is from {desde.date().isoformat()}"
                           if reval else "")
                return Estado.RANCIA, {
                    "es": f"observada hace más de {self.frescura_dias} días{cola_es}, "
                          f"vuelve a observar",
                    "en": f"observed more than {self.frescura_dias} days ago{cola_en}, "
                          f"observe it again"}
        return Estado.VALIDA, {
            "es": "sigue valiendo para el sujeto sobre el que se tomó",
            "en": "it still holds for the subject it was taken on"}

    def a_json(self) -> dict[str, Any]:
        """Todo lo que el registro es. Lo que no se escriba aqui, se pierde.

        Antes faltaban tres campos y los tres mentian al releer:

          `esquema`            se escribia siempre el de evidencia, asi que una
                               respuesta de formulario volvia del almacen
                               diciendo ser una observacion de codigo, y su
                               identificador dejaba de cuadrar.
          `estado_declarado`   una respuesta declarada NO ADMISIBLE se guardaba
                               y volvia VALIDA. Es el peor de los tres: el
                               motor juzgaba la respuesta, lo escribia, y el
                               propio almacen lo borraba.
          `motivo`             y sin el, el estado no se podia explicar.
        """
        d = dict(self.cuerpo())
        d.update({"id": self.id, "frescura_dias": self.frescura_dias,
                  "estado_declarado": self.estado_declarado.value})
        if self.motivo is not None:
            d["motivo"] = self.motivo
        return d
