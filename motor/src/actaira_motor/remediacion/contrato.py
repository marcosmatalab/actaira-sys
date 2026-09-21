"""Lo que sale de aquí hacia el sistema de tickets de otro, y lo que vuelve.

POR QUE ESTO NO ES EL MISMO CONECTOR QUE TRAE EL CODIGO
---------------------------------------------------------
Mezclar «traer el código» con «abrir un ticket» en un solo conector es lo que
hace que cambiar de proveedor de tickets obligue a tocar el que lee el código.
Son dos ciclos de vida distintos -uno se usa en cada observación, el otro
cuando hay un hallazgo que alguien tiene que arreglar- y dos superficies de
permiso distintas: leer un repositorio y escribir en el sistema donde el
cliente organiza su trabajo no se piden juntos.

LAS TRES NEGATIVAS DE ESTE MODULO
-----------------------------------
1. **Un remediador no verifica.** Puede abrir un ticket, leer su estado y
   decirlo. No puede concluir que la no conformidad quedó resuelta: eso es una
   observación posterior y vive en el motor. La cláusula 10.2 pide revisar la
   EFICACIA, y el estado de un ticket no la revisa.

2. **Un remediador no inventa autores.** Una transición sin persona no se puede
   auditar. Si el sistema de tickets no dice quién movió el ticket, aquí no se
   escribe «sistema»: se dice que falta el autor y no se mueve nada.

3. **Lo que sale, sale al sistema de otro.** El encargo lleva el texto de la
   regla y de su remediación, que son nuestros. Las rutas de fichero del
   cliente sólo salen si alguien lo pide expresamente, porque un ticket es
   legible por mucha más gente que un expediente firmado.
"""
from __future__ import annotations

import re as _re

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..conectores.contrato import redactar, sin_secretos   # UNA definicion de secreto
from ..gestion.noconformidad import EstadoNC

ESQUEMA_ENCARGO = "actaira/encargo/v1"
ESQUEMA_DELEGACION = "actaira/delegacion/v1"

TECHO = EstadoNC.EJECUTADA
"""Hasta dónde puede llegar una no conformidad movida desde fuera.

Es la regla entera de este módulo. Un ticket cerrado dice que alguien dio el
trabajo por hecho; `VERIFICADA` dice que se comprobó que la causa dejó de
producir el efecto, y eso exige el identificador de una evidencia tomada
DESPUÉS. Dejar que un estado externo llegara a `VERIFICADA` convertiría la
mejora continua de la 10.2 en el botón «cerrar» de un tablero ajeno, que es
exactamente lo que el módulo de gestión existe para no ser.
"""


_IDENTIFICADOR = _re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
"""Lo que puede ser un identificador de no conformidad.

Letras, digitos, punto, guion y guion bajo; hasta 64; y empezando por letra o
digito. Es deliberadamente estrecho: un identificador viaja a un nombre de
fichero, a una URL y a un ticket de un sistema ajeno, y lo que es inofensivo en
uno de los tres no lo es en los otros dos. Empezar por letra o digito descarta
`.`, `..` y los nombres ocultos de un tiron.

NO se sanea, se RECHAZA. Sanear -- quitar las barras, colapsar los puntos --
produce un identificador distinto del que pidio quien llama, y entonces el
encargo que se abre no es el que se pidio y nadie se entera. Entre escribir en
el sitio equivocado y no escribir, no escribir.
"""


def _exigir_identificador_manejable(valor: str, campo: str) -> None:
    if not _IDENTIFICADOR.fullmatch(str(valor or "")):
        raise ValueError(
            f"{campo}={valor!r} no sirve como identificador: acaba siendo un nombre de "
            f"fichero y un trozo de URL. Se admiten letras, digitos, punto, guion y guion "
            f"bajo, empezando por letra o digito, hasta 64 caracteres. No se sanea el "
            f"valor a proposito: un identificador saneado ya no es el que se pidio.")


@dataclass(frozen=True)
class Encargo:
    """Lo que se le pide a alguien que arregle, dicho para que se pueda hacer.

    Lleva responsable y fecha comprometida porque una acción sin dueño y sin
    fecha es una intención, y porque son los dos campos que la transición a
    CON_ACCION exige: si el encargo no los trae, el ticket que abra no podrá
    mover la no conformidad ni un paso.
    """

    no_conformidad_id: str
    titulo: dict[str, str]
    cuerpo: dict[str, str]
    obligacion_id: str
    control_id: str
    severidad: str
    responsable: str
    compromiso: str                       # ISO 8601, la fecha a la que faltar
    localizaciones: tuple[str, ...] = ()  # vacio salvo que alguien lo pida
    etiquetas: tuple[str, ...] = ()
    texto_del_cliente: str = ""
    """Lo que el cliente escribio, TAL CUAL, y en su idioma.

    Va en un campo propio y no mezclado con `cuerpo` porque son dos cosas con
    dos procedencias: `cuerpo` es el texto del catalogo, escrito por una
    persona y contrastable; esto es lo que escribio quien abrio la no
    conformidad. Fundirlos habria hecho imposible saber cual de los dos se
    esta leyendo, y traducir el segundo habria sido inventar.
    """

    def __post_init__(self) -> None:
        # El identificador ACABA SIENDO UN NOMBRE DE FICHERO, asi que se valida
        # como tal antes que nada.
        #
        # `RemediadorFichero` hacia `carpeta / f"{encargo.no_conformidad_id}.md"`
        # con el identificador tal cual. Con `../../../escape` el encargo se
        # escribia tres directorios por encima del destino, y con una ruta
        # ABSOLUTA -- `C:/Windows/Temp/lo-que-sea` o `/etc/cron.d/lo-que-sea` --
        # el operador `/` de `pathlib` descarta la carpeta entera y escribe
        # donde diga el identificador. No era un escape de un directorio: era
        # escritura de ficheros en cualquier sitio donde alcance el proceso.
        #
        # Se valida AQUI y no en el remediador por dos razones. La primera es
        # que hay mas de un remediador y el mismo identificador viaja a todos:
        # los de REST lo meten en una URL, donde una barra tambien cambia a que
        # recurso se llama. La segunda es la de siempre: una comprobacion que
        # vive en el consumidor hay que acordarse de repetirla en el siguiente,
        # y el siguiente es justo el que no la tendra.
        #
        # El remediador de ficheros COMPRUEBA ADEMAS que lo que va a escribir
        # cae dentro de su carpeta. No es redundancia por desconfianza del
        # codigo de al lado: es que quien escribe en el disco es el unico que
        # puede comprobar donde acaba escribiendo de verdad.
        _exigir_identificador_manejable(self.no_conformidad_id, "no_conformidad_id")

        for campo in ("no_conformidad_id", "obligacion_id", "control_id",
                      "responsable", "compromiso"):
            if not str(getattr(self, campo)).strip():
                raise ValueError(
                    f"un encargo sin '{campo}' no puede mover nada: la transicion a "
                    "CON_ACCION exige accion, responsable y fecha comprometida.")
        if not isinstance(self.titulo, dict) or not (self.titulo.get("es")
                                                     and self.titulo.get("en")):
            raise ValueError(
                "'titulo' va en los dos idiomas: un ticket en castellano dentro de un "
                "expediente pedido en ingles es el mismo defecto que ya se corrigio en las "
                "senales.")
        if not isinstance(self.cuerpo, dict) or set(self.cuerpo) != {"es", "en"}:
            raise ValueError(
                "'cuerpo' lleva las dos claves aunque esten vacias: vacio significa «no hay "
                "texto de catalogo detras de esto», y esa es una informacion, no un hueco.")
        if not (self.cuerpo["es"] or self.cuerpo["en"] or self.texto_del_cliente.strip()):
            raise ValueError(
                "un encargo sin texto no dice que hay que hacer: o trae la remediacion del "
                "catalogo, o trae lo que escribio el cliente.")

    def texto(self, idioma: str = "es") -> str:
        """El cuerpo del ticket, ya montado, y SIN secretos.

        La puerta de secretos se aplica aqui y no al revisar, por la misma
        razon que en el conector de codigo: lo que sale de aqui entra en un
        sistema que no controlamos, y de ahi no se puede retirar.
        """
        partes = [self.cuerpo[idioma]]
        if self.texto_del_cliente.strip():
            partes += ["", ("lo que escribió quien la abrió, sin traducir"
                            if idioma == "es" else
                            "what whoever opened it wrote, untranslated") + ":",
                       self.texto_del_cliente]
        partes += [""] + [
                  f"{'obligación' if idioma == 'es' else 'obligation'}: {self.obligacion_id}",
                  f"{'control' if idioma == 'es' else 'control'}: {self.control_id}",
                  f"{'no conformidad' if idioma == 'es' else 'nonconformity'}: "
                  f"{self.no_conformidad_id}"]
        if self.localizaciones:
            partes += ["", ("dónde se vio" if idioma == "es" else "where it was seen") + ":"]
            partes += [f"  - {l}" for l in self.localizaciones]
        return redactar("\n".join(partes))

    def a_json(self) -> dict[str, Any]:
        return {"esquema": ESQUEMA_ENCARGO, "no_conformidad_id": self.no_conformidad_id,
                "titulo": self.titulo, "cuerpo": self.cuerpo,
                "obligacion_id": self.obligacion_id, "control_id": self.control_id,
                "severidad": self.severidad, "responsable": self.responsable,
                "compromiso": self.compromiso,
                "localizaciones": list(self.localizaciones),
                "etiquetas": list(self.etiquetas),
                "texto_del_cliente": self.texto_del_cliente}


@dataclass(frozen=True)
class Delegacion:
    """El ticket que alguien abrió por esto, y lo último que se supo de él.

    `estado_externo` es la cadena CRUDA del sistema de tickets, sin traducir.
    Guardar ya traducido habría perdido lo único con lo que se puede discutir
    una traducción equivocada: lo que el otro sistema dijo de verdad.
    """

    sistema: str
    referencia: str                  # la clave del ticket: ACT-123, ENG-45
    url: str
    no_conformidad_id: str
    estado_externo: str = ""
    actor: str = ""                  # quien lo movio, segun el otro sistema
    cargo_del_actor: str = ""
    cuando: str = ""
    detalles: dict[str, str] = field(default_factory=dict)

    def a_json(self) -> dict[str, Any]:
        return {"esquema": ESQUEMA_DELEGACION, "sistema": self.sistema,
                "referencia": self.referencia, "url": self.url,
                "no_conformidad_id": self.no_conformidad_id,
                "estado_externo": self.estado_externo, "actor": self.actor,
                "cargo_del_actor": self.cargo_del_actor,
                "cuando": self.cuando, "detalles": self.detalles}


@dataclass(frozen=True)
class LimiteDelRemediador:
    """Lo que este remediador NO puede hacer, dicho por él mismo."""

    que: dict[str, str]
    por_que: str

    def a_json(self) -> dict[str, Any]:
        return {"que": self.que, "por_que": self.por_que}


@runtime_checkable
class Remediador(Protocol):
    """Abrir un encargo, leer su estado y decir qué no puede hacer. Nada más.

    El DESTINO -la carpeta, el proyecto de Jira, el equipo de Linear- es estado
    del remediador y no un argumento de `abrir`. La primera version lo pasaba
    en cada llamada y obligaba al de fichero a tener un `abrir` que reventaba,
    porque necesitaba un dato que la firma no traia: una firma que una de sus
    implementaciones no puede cumplir es una firma equivocada.
    """

    nombre: str
    version: str
    destino: str

    def abrir(self, encargo: "Encargo", idioma: str = "es") -> "Delegacion":
        """Abre el ticket y devuelve su referencia. No decide nada."""

    def consultar(self, delegacion: "Delegacion") -> "Delegacion":
        """Lo último que dice el otro sistema. Crudo, sin traducir."""

    def limites(self) -> tuple[LimiteDelRemediador, ...]:
        """Lo que este remediador NO alcanza, para que viaje con la delegacion."""


def _tipos() -> list[Any]:
    from .fichero import RemediadorFichero
    from .rest import RemediadorHttp
    # El de FICHERO va el ultimo por la misma razon que el conector local:
    # resuelve casi cualquier ruta, y si fuera el primero se tragaria un
    # destino de red que casualmente existiera como directorio.
    return [RemediadorHttp, RemediadorFichero]


def nombres() -> list[str]:
    return [t.nombre for t in _tipos()]


def elegir(destino: str, **ajustes: Any) -> Remediador:
    """El remediador YA configurado para ese destino.

    Devuelve una instancia atada al destino y no un tipo suelto: un remediador
    sin destino es un objeto que no puede hacer lo unico que se le pide.
    """
    for tipo in _tipos():
        if tipo.resuelve(destino):
            return tipo.desde(destino, **ajustes)
    raise ValueError(
        f"ningun remediador sabe hablar con {destino!r}. Los que hay: "
        + ", ".join(nombres()))


def emitible(d: dict[str, Any]) -> dict[str, Any]:
    """El mismo diccionario, y revienta si lleva un secreto dentro.

    Se llama ANTES de escribir una delegacion en el almacen encadenado. Un
    token dentro de un expediente firmado obliga a retirar el expediente
    entero: no se puede editar sin romper la firma y no se puede dejar.
    """
    import json

    encontrados = sin_secretos(json.dumps(d, ensure_ascii=False))
    if encontrados:
        raise ValueError(
            f"esto lleva algo que parece una credencial ({encontrados[0]}) y no se emite: "
            "dentro de un expediente firmado no se puede editar sin romper la firma.")
    return d
