"""El empujón como disparador: lo que convierte la vigilancia en barata.

EL ARGUMENTO DE COSTE, QUE ES EL ARGUMENTO ENTERO
---------------------------------------------------
Sondear N repositorios cada minuto son N x 1440 ejecuciones al día. Reaccionar
a un empujón más un vencimiento son del orden de las veces que el cliente
commitea, más una. Dos órdenes de magnitud menos de cómputo para una afirmación
más fuerte, porque la que sale del empujón está atada al commit exacto que lo
provocó.

Pero eso sólo se sostiene si el empujón se traduce bien, y traducirlo bien es
casi todo el trabajo:

  * **Idempotencia.** El mismo evento entregado tres veces -y los proveedores
    reentregan- no puede producir tres observaciones. Aquí no se resuelve con
    una tabla de eventos vistos, que habría sido otro estado que mantener: se
    resuelve porque la decisión depende del SUJETO, y el mismo commit da el
    mismo sujeto. El tercer intento decide lo mismo que el primero.
  * **Un empujón no es un cambio.** Un commit que toca una captura de pantalla
    no cambia el árbol que el motor observa. Volver a observarlo todo en cada
    empujón es sondear con más pasos. Pero la puerta a IGNORAR es estrecha a
    propósito: equivocarse hacia REOBSERVAR cuesta un clon, y equivocarse hacia
    IGNORAR no se nota nunca -el expediente sigue saliendo limpio sobre un
    árbol que ya no existe-. Por eso todo lo que no se puede demostrar acaba en
    REOBSERVAR, y por eso la cadena de inertes tiene tope.
  * **Y lo que se ignora no se disfraza de observado.** Lo que se anota cuando
    un empujón se declara inerte dice, con esas palabras, que el árbol no se ha
    mirado y que lo único que consta es lo que el proveedor declaró. El digest
    del sujeto sobre el que afirma el expediente sigue siendo el de la última
    vez que se miró de verdad.
  * **Y un payload que no se entiende no se ignora en silencio.** Un proveedor
    cambia su formato, los eventos dejan de traducirse, y la vigilancia se para
    sin que nadie se entere: eso es peor que no tener vigilancia, porque el
    cliente cree que la tiene.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

ESQUEMA = "actaira/empujon/v1"
_SHA = re.compile(r"^[0-9a-f]{40}$")


class Decision(str, Enum):
    REOBSERVAR = "reobservar"    # el sujeto puede haber cambiado: hay que mirar
    REVALIDAR = "revalidar"      # el sujeto es el mismo: mueve el reloj, no reobserva
    IGNORAR = "ignorar"          # no afecta a nada que se observe, y se dice por que
    NO_TRADUCIBLE = "no_traducible"  # no se entendio, y NO es lo mismo que ignorar

    @property
    def cuesta_computo(self) -> bool:
        return self is Decision.REOBSERVAR


@dataclass(frozen=True)
class Empujon:
    """Un empujón, traducido a lo único que el motor necesita saber de él.

    Los ficheros vienen en TRES listas y no en una. Añadir o borrar un fichero
    cambia el árbol aunque el motor no abra ese fichero -- el digest del árbol
    resume también los nombres de los que no lee -- mientras que modificar uno
    que no se lee no lo cambia. Fundir las tres listas en «tocados» borraba
    justo la distinción de la que depende el filtro barato.
    """

    id_del_evento: str
    proveedor: str
    ubicacion: str
    referencia: str
    referencia_inmutable: str
    cuando: str
    anadidos: tuple[str, ...] = ()
    modificados: tuple[str, ...] = ()
    eliminados: tuple[str, ...] = ()
    antes: str | None = None
    lista_completa: bool = False
    por_que_no_completa: str = ""

    @property
    def ficheros_tocados(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.anadidos) | set(self.modificados) | set(self.eliminados)))

    def a_json(self) -> dict[str, Any]:
        return {"esquema": ESQUEMA, "id_del_evento": self.id_del_evento,
                "proveedor": self.proveedor, "ubicacion": self.ubicacion,
                "referencia": self.referencia,
                "referencia_inmutable": self.referencia_inmutable,
                "cuando": self.cuando, "ficheros_tocados": list(self.ficheros_tocados),
                "antes": self.antes,
                "anadidos": list(self.anadidos), "modificados": list(self.modificados),
                "eliminados": list(self.eliminados),
                "lista_completa": self.lista_completa,
                "por_que_no_completa": self.por_que_no_completa}


class NoSeEntiende(Exception):
    """El payload no se pudo traducir, y eso NO se resuelve ignorándolo.

    Un proveedor cambia su formato, los eventos dejan de traducirse, y la
    vigilancia se para sin que nadie se entere. El cliente sigue creyendo que
    la tiene, que es peor que no tenerla.
    """


# Cada proveedor con el sitio donde guarda las cosas que hacen falta. Es una
# tabla y no un `if` encadenado porque lo unico que cambia entre proveedores
# son los nombres de los campos: la logica es la misma para todos, y
# escribirla cuatro veces habria dado cuatro sitios donde arreglar un fallo.
#
# `antes` es el commit del que sale el empujon, y sin el la lista de ficheros
# no describe el cambio respecto de lo que se observo, sino respecto de otra
# cosa. `completa` dice si esa lista se puede creer: los cuatro proveedores la
# recortan, y ninguno de los cuatro avisa igual.
PROVEEDORES = {
    "github": {"ubicacion": ("repository", "clone_url"), "ref": ("ref",),
               "sha": ("after",), "senal": ("repository", "full_name"),
               "antes": ("before",), "completa": "github"},
    "gitlab": {"ubicacion": ("project", "git_http_url"), "ref": ("ref",),
               "sha": ("checkout_sha",), "senal": ("object_kind",),
               "antes": ("before",), "completa": "gitlab"},
    "bitbucket": {"ubicacion": ("repository", "links", "html", "href"),
                  "ref": ("push", "changes", 0, "new", "name"),
                  "sha": ("push", "changes", 0, "new", "target", "hash"),
                  "senal": ("push",),
                  "antes": ("push", "changes", 0, "old", "target", "hash"),
                  "completa": "nunca"},
    "azure": {"ubicacion": ("resource", "repository", "remoteUrl"),
              "ref": ("resource", "refUpdates", 0, "name"),
              "sha": ("resource", "refUpdates", 0, "newObjectId"),
              "senal": ("eventType",),
              "antes": ("resource", "refUpdates", 0, "oldObjectId"),
              "completa": "nunca"},
}

# GitHub y GitLab cortan la lista de commits en 20 y no mandan un aviso claro
# de que la cortaron. Se trata el limite como corte: en el borde de 20 commits
# exactos se pierde una optimizacion, y en el otro lado se perderia un cambio.
TOPE_DE_COMMITS = 20

CEROS = "0" * 40


def _completa_github(payload: Any, commits: list) -> tuple[bool, str]:
    """La lista de GitHub se puede creer si no la cortaron y no fue forzado.

    Un empujon forzado reescribe la rama: los commits que trae son los nuevos,
    y los ficheros que el forzado se llevo por delante no aparecen en ninguna
    parte del cuerpo. Creerse esa lista seria no observar un cambio que si
    ocurrio, que es exactamente el error que no se puede cometer.
    """
    if payload.get("forced"):
        return False, "el empujon fue forzado: la lista no describe lo que se perdio"
    if payload.get("created") or payload.get("deleted"):
        return False, "la rama se creo o se borro: no hay un cambio que listar"
    if len(commits) >= TOPE_DE_COMMITS:
        return False, f"{len(commits)} commits: GitHub corta en {TOPE_DE_COMMITS} y no avisa"
    if not commits:
        return False, "el cuerpo no trae ni un commit con ficheros"
    return True, ""


def _completa_gitlab(payload: Any, commits: list) -> tuple[bool, str]:
    total = payload.get("total_commits_count")
    if isinstance(total, int) and total != len(commits):
        return False, f"{len(commits)} commits de {total}: la lista viene recortada"
    if len(commits) >= TOPE_DE_COMMITS:
        return False, f"{len(commits)} commits: GitLab corta en {TOPE_DE_COMMITS}"
    if not commits:
        return False, "el cuerpo no trae ni un commit con ficheros"
    return True, ""


def _completa_nunca(payload: Any, commits: list) -> tuple[bool, str]:
    """Bitbucket y Azure DevOps no mandan los ficheros de cada commit.

    No es una limitacion de este codigo y por eso no se disimula: con estos dos
    proveedores el filtro barato no se puede aplicar, y todo empujon que cambie
    el commit cuesta una observacion.
    """
    return False, "este proveedor no manda que ficheros toco cada commit"


COMPLETITUD = {"github": _completa_github, "gitlab": _completa_gitlab,
               "nunca": _completa_nunca}


def _sacar(d: Any, camino: tuple) -> Any:
    for paso in camino:
        try:
            d = d[paso]
        except (KeyError, IndexError, TypeError):
            return None
    return d


def _ficheros(payload: Any, proveedor: str) -> tuple[tuple[str, ...], ...]:
    """Las tres listas, en el sitio donde cada proveedor las pone.

    Bitbucket y Azure DevOps no las ponen en ninguno: sus cuerpos de empujón
    traen los commits sin los ficheros de cada uno. Devuelven tres listas
    vacías y `completa` dirá que no se pueden creer, que no es lo mismo que
    decir que no se tocó nada.
    """
    if proveedor not in ("github", "gitlab"):
        return (), (), ()
    commits = [c for c in payload.get("commits", []) if isinstance(c, dict)]
    def _de(clave: str) -> tuple[str, ...]:
        return tuple(sorted({f for c in commits for f in c.get(clave, [])
                             if isinstance(f, str)}))
    return _de("added"), _de("modified"), _de("removed")


def traducir(payload: dict[str, Any], id_del_evento: str = "",
             cuando: str | None = None) -> Empujon:
    """Traduce el empujón de cualquiera de los cuatro. Si no lo entiende, revienta.

    El identificador del evento lo pone quien recibe la petición -viene en una
    cabecera, no en el cuerpo- y si no lo hay se usa el commit: dos entregas
    del mismo empujón traen el mismo commit, así que la idempotencia se
    sostiene igual.
    """
    for proveedor, campos in PROVEEDORES.items():
        if _sacar(payload, campos["senal"]) is None:
            continue
        ubicacion = _sacar(payload, campos["ubicacion"])
        sha = _sacar(payload, campos["sha"])
        ref = _sacar(payload, campos["ref"]) or ""
        if not ubicacion or not isinstance(sha, str) or not _SHA.fullmatch(sha):
            continue
        antes = _sacar(payload, campos["antes"])
        if not (isinstance(antes, str) and _SHA.fullmatch(antes)) or antes == CEROS:
            # Cuarenta ceros es «esta rama no existia». No es un commit del que
            # se salga, y tratarlo como tal compararia contra la nada.
            antes = None
        anadidos, modificados, eliminados = _ficheros(payload, proveedor)
        commits = [c for c in payload.get("commits", []) if isinstance(c, dict)]
        completa, por_que = COMPLETITUD[campos["completa"]](payload, commits)
        return Empujon(
            id_del_evento=id_del_evento or sha, proveedor=proveedor,
            ubicacion=str(ubicacion), referencia=str(ref).split("/")[-1],
            referencia_inmutable=sha,
            cuando=cuando or datetime.now().astimezone().isoformat(),
            anadidos=anadidos, modificados=modificados, eliminados=eliminados,
            antes=antes, lista_completa=completa, por_que_no_completa=por_que)
    raise NoSeEntiende(
        "no se reconocio el formato de este empujon. Los que se traducen son "
        + ", ".join(PROVEEDORES) + ". Esto NO se ignora: un proveedor que cambia su "
        "formato para la vigilancia sin que nadie se entere, y el cliente sigue "
        "creyendo que la tiene.")


def lector_del_motor() -> Callable[[str], bool]:
    """La función con la que el motor decide si abre un fichero. UNA definición.

    Se importa aquí dentro y no arriba a propósito: este módulo tiene que poder
    correr en el borde -en la función que recibe el webhook- sin arrastrar el
    motor de reglas, que es la mitad del argumento de coste. Quien quiera el
    filtro barato paga el import; quien sólo quiera traducir, no.
    """
    from ..controles.motor import lee_el_contenido_de
    return lee_el_contenido_de


def _puede_ignorarse(empujon: Empujon, cabeza: str,
                     lee_contenido: Callable[[str], bool] | None) -> tuple[bool, str, str]:
    """Si este empujón NO pudo cambiar el árbol. Seis condiciones, todas duras.

    `cabeza` es el commit desde el que se razona: el último observado, o el
    último demostrado inerte si ya hay cadena.

    La puerta es estrecha a propósito. Equivocarse hacia REOBSERVAR cuesta un
    clon; equivocarse hacia IGNORAR es no mirar un cambio que sí ocurrió, y eso
    no se nota nunca: el expediente sigue saliendo limpio sobre un árbol que ya
    no existe. Por eso cada condición que no se puede demostrar devuelve «no».
    """
    if lee_contenido is None:
        return False, (
            "no se sabe qué ficheros abre el motor, así que no se puede afirmar que este "
            "empujón no le afecta"), (
            "what the engine opens is unknown, so it cannot be claimed that this push does "
            "not affect it")
    if empujon.antes is None:
        return False, (
            "el empujón no dice de qué commit sale: su lista de ficheros no describe el "
            "cambio respecto de lo observado"), (
            "the push does not say which commit it starts from: its file list does not "
            "describe the change relative to what was observed")
    if empujon.antes != cabeza:
        return False, (
            f"el empujón sale de {empujon.antes[:8]} y se venía de {cabeza[:8]}: la lista de "
            f"ficheros describe otro tramo"), (
            f"the push starts from {empujon.antes[:8]} and the subject stood at {cabeza[:8]}: "
            f"the file list describes a different span")
    if not empujon.lista_completa:
        return False, (
            f"la lista de ficheros no se puede creer: {empujon.por_que_no_completa}"), (
            f"the file list cannot be trusted: {empujon.por_que_no_completa}")
    if empujon.anadidos or empujon.eliminados:
        # El digest del arbol resume tambien los NOMBRES de los ficheros que no
        # abre. Un .png nuevo cambia el sujeto aunque nadie lo lea nunca.
        return False, (
            "se añadieron o se borraron ficheros, y el árbol resume también los nombres de "
            "los que no abre"), (
            "files were added or removed, and the tree digest also covers the names of the "
            "files it does not open")
    if not empujon.modificados:
        return False, (
            "el empujón no declara ni un fichero modificado: no hay nada sobre lo que "
            "afirmar que no cambió"), (
            "the push declares no modified file: there is nothing on which to claim that "
            "nothing changed")
    leidos = [f for f in empujon.modificados if lee_contenido(f)]
    if leidos:
        return False, (
            f"toca ficheros que el motor sí abre: {', '.join(leidos[:3])}"), (
            f"it touches files the engine does open: {', '.join(leidos[:3])}")
    return True, (
        "ninguno de los ficheros que modifica lo abre el motor, y no añadió ni borró "
        f"ninguno: {', '.join(empujon.modificados[:3])}"), (
        "none of the files it modifies is opened by the engine, and it added or removed "
        f"none: {', '.join(empujon.modificados[:3])}")


TOPE_DE_CADENA_INERTE = 10
"""Cuántos empujones seguidos se pueden declarar inertes antes de mirar igual.

Cada eslabón de la cadena descansa en que el proveedor dijo la verdad sobre qué
ficheros tocó cada commit. Un eslabón es una apuesta pequeña y comprobable -se
clonan los dos commits y se comparan-; cien eslabones son una afirmación sobre
un árbol que nadie ha visto desde hace cien empujones. El tope existe para que
el error, si lo hay, esté acotado y salga pronto, y no para ahorrar cómputo:
llegar al tope CUESTA una observación que nadie pidió.
"""


def decidir(empujon: Empujon, identidad_observada: str | None,
            identidad_ahora: str | None,
            lee_contenido: Callable[[str], bool] | None = None,
            inerte: tuple[str, ...] = (),
            tope_inerte: int = TOPE_DE_CADENA_INERTE,
            ) -> tuple[Decision, dict[str, str]]:
    """Qué hacer con este empujón, y por qué. No hace nada: lo dice.

    Se separa de la ejecución a propósito. Que la decisión sea una función pura
    de sus argumentos es lo que permite comprobarla: el mismo empujón entregado
    tres veces pasa por aquí tres veces y sale lo mismo las tres, sin ninguna
    tabla de eventos vistos que mantener.

    `lee_contenido` es lo que el motor abre, y viene de fuera porque tiene UNA
    definición y vive en el motor. Sin él, el filtro barato no se aplica y todo
    cambio de commit cuesta una observación: se pierde una optimización, que es
    el lado por el que hay que equivocarse.

    `inerte` es la cadena de commits por los que el sujeto pasó SIN que nadie
    lo observara, porque se demostró que no podían cambiar el árbol. Existe
    porque sin ella el filtro barato sólo funciona una vez: el segundo empujón
    sale del primero, que ya no es lo último observado, y vuelve a costar un
    clon. Lo que la cadena NO es: una observación. El digest del sujeto sobre
    el que se afirma sigue siendo el de la última vez que se miró de verdad, y
    el expediente lo dice con esas palabras.
    """
    if identidad_ahora is None:
        return Decision.REOBSERVAR, {
            "es": "no se sabe cómo está el sujeto ahora, así que se mira",
            "en": "the subject's current state is unknown, so it is looked at"}
    if identidad_observada is None:
        return Decision.REOBSERVAR, {
            "es": "nunca se observó este sujeto: no hay nada que revalidar",
            "en": "this subject was never observed: there is nothing to revalidate"}
    if identidad_observada == identidad_ahora:
        return Decision.REVALIDAR, {
            "es": (f"el empujón {empujon.referencia_inmutable[:8]} deja el sujeto en el mismo "
                   f"commit que ya se observó: se mueve el reloj de la frescura y no se "
                   f"vuelve a observar"),
            "en": (f"push {empujon.referencia_inmutable[:8]} leaves the subject at the same "
                   f"commit already observed: the freshness clock moves and nothing is "
                   f"observed again")}
    if identidad_ahora in inerte:
        # La reentrega de un empujon que ya se declaro inerte. Sin esta rama
        # caeria en REOBSERVAR -- su `antes` ya no es la cabeza -- y la
        # idempotencia se sostendria para un camino y no para el otro.
        return Decision.REVALIDAR, {
            "es": (f"este commit ya estaba en la cadena de empujones demostrados inertes: "
                   f"es una reentrega, y decide lo mismo que la primera vez"),
            "en": ("this commit was already in the chain of pushes proven inert: it is a "
                   "redelivery, and it decides the same as the first time")}
    cabeza = inerte[-1] if inerte else identidad_observada
    if len(inerte) >= tope_inerte:
        return Decision.REOBSERVAR, {
            "es": (f"van {len(inerte)} empujones seguidos sin mirar el árbol, y el tope es "
                   f"{tope_inerte}: se mira, aunque nada de este empujón lo pida"),
            "en": (f"{len(inerte)} pushes in a row without looking at the tree, and the cap "
                   f"is {tope_inerte}: it is looked at, even though nothing in this push "
                   f"asks for it")}
    puede, es, en = _puede_ignorarse(empujon, cabeza, lee_contenido)
    if puede:
        return Decision.IGNORAR, {
            "es": f"el commit cambió, pero el árbol que observa el motor no pudo cambiar: {es}",
            "en": f"the commit changed, but the tree the engine observes could not have: {en}"}
    return Decision.REOBSERVAR, {
        "es": f"el sujeto pudo cambiar con el empujón {empujon.referencia_inmutable[:8]}: {es}",
        "en": f"the subject may have changed with push {empujon.referencia_inmutable[:8]}: {en}"}
