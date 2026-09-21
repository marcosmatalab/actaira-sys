"""El remediador que no habla con nadie: escribe el encargo y se calla.

POR QUE ES EL PRIMERO QUE IMPLEMENTA EL CONTRATO
--------------------------------------------------
Por lo mismo que el conector local fue el primero del otro contrato: si el
contrato aguanta un directorio y un sistema de tickets de verdad sin un `if`,
aguanta los demás. Un contrato sacado del primer sistema real acaba teniendo
su forma -`issueType`, `fields.customfield_10007`- y entonces Linear no encaja.

Y además sirve de verdad. Hay clientes que no dan acceso de escritura a su
sistema de tickets a ninguna herramienta, y con razón: lo que se les puede
ofrecer es el encargo escrito, listo para pegar, con la referencia de la no
conformidad dentro para que la vuelta se pueda atar a mano.
"""
from __future__ import annotations

import json
from pathlib import Path

from .contrato import Delegacion, Encargo, LimiteDelRemediador


def _exigir_dentro(carpeta: Path, *nombres: str) -> None:
    """Comprueba que lo que se va a escribir cae DENTRO de la carpeta de encargos.

    `Encargo` ya rechaza un identificador que no sirva como nombre de fichero, y
    esta comprobacion es la segunda barrera. No es desconfianza del codigo de al
    lado: es que quien escribe en el disco es el unico que puede saber donde
    acaba escribiendo de verdad.

    La diferencia importa porque las dos fallan por motivos distintos: la del
    contrato mira el TEXTO del identificador, y esta mira la RUTA ya resuelta.
    Asi que esta caza lo que el texto no ve -- un enlace COLGANDO de la carpeta,
    puesto entre la validacion y la escritura -- aunque el identificador fuera
    impecable.

    LO QUE ESTA BARRERA NO HACE, Y NO PUEDE HACER
    -----------------------------------------------
    No comprueba que la CARPETA de destino sea legitima. Si `--destino` apunta a
    un enlace que sale al espacio de otro cliente, `carpeta.resolve()` sigue ese
    enlace y el encargo se escribe ahi sin que esto proteste: la base contra la
    que compara es la carpeta ya seguida, asi que la comprobacion se anula a si
    misma exactamente igual que le pasaba a `Arbol._dentro`.

    Y esta bien que no lo haga, porque no puede: aqui no se sabe donde empieza
    el espacio de un cliente. Quien lo sabe es la capa que reparte las carpetas,
    y es `rutaSegura` del lado Go -- que ya resuelve enlaces -- la que tiene que
    no entregar nunca una carpeta que salga fuera. Se escribe aqui para que
    nadie lea esta funcion y crea que el aislamiento entre clientes esta
    resuelto en este fichero.

    Que escribia esto antes de existir: con `../../../escape` el encargo salia
    tres directorios por encima del destino, y con una ruta absoluta el operador
    `/` de `pathlib` descartaba la carpeta entera. Escritura arbitraria de
    ficheros desde un campo que rellena quien abre la no conformidad.
    """
    base = carpeta.resolve()
    for nombre in nombres:
        destino = (carpeta / nombre).resolve()
        if destino.parent != base:
            raise ValueError(
                f"el encargo saldria en {destino}, que no esta en {base}. No se escribe: "
                f"un fichero fuera de la carpeta de encargos es, en una plataforma con "
                f"varios clientes, un fichero en el espacio de otro.")


class RemediadorFichero:
    nombre = "fichero"
    version = "1.0.0"

    def __init__(self, destino: str) -> None:
        self.destino = destino

    @staticmethod
    def resuelve(destino: str) -> bool:
        if "://" in destino:
            return False
        p = Path(destino)
        return p.is_dir() or p.parent.is_dir()

    @classmethod
    def desde(cls, destino: str, **ajustes: object) -> "RemediadorFichero":
        return cls(destino)

    def abrir(self, encargo: Encargo, idioma: str = "es") -> Delegacion:
        """Escribe el encargo y devuelve una delegación que declara su límite.

        `estado_externo` es «escrito» y no «abierto»: lo único que consta es
        que el fichero existe. Que alguien lo lea, lo pegue en su tablero y
        haga algo es precisamente lo que este remediador no puede saber.
        """
        carpeta = Path(self.destino)
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = f"{encargo.no_conformidad_id}.md"
        _exigir_dentro(carpeta, nombre, f"{encargo.no_conformidad_id}.json")
        cuerpo = (f"# {encargo.titulo[idioma]}\n\n{encargo.texto(idioma)}\n\n"
                  f"{'responsable' if idioma == 'es' else 'owner'}: {encargo.responsable}\n"
                  f"{'fecha comprometida' if idioma == 'es' else 'committed date'}: "
                  f"{encargo.compromiso}\n")
        (carpeta / nombre).write_text(cuerpo, encoding="utf-8")
        (carpeta / f"{encargo.no_conformidad_id}.json").write_text(
            json.dumps(encargo.a_json(), ensure_ascii=False, indent=2), encoding="utf-8")
        return Delegacion(
            sistema=self.nombre, referencia=nombre, url=str((carpeta / nombre).resolve()),
            no_conformidad_id=encargo.no_conformidad_id, estado_externo="escrito",
            detalles={"nota": "esto es un fichero, no un ticket: nadie lo ha aceptado"})

    def consultar(self, delegacion: Delegacion) -> Delegacion:
        """No hay nada que consultar: un fichero no cambia de estado solo."""
        return delegacion

    def limites(self) -> tuple[LimiteDelRemediador, ...]:
        return (
            LimiteDelRemediador(
                {"es": "no hay nadie al otro lado: que el encargo esté escrito no significa "
                       "que alguien lo haya aceptado, ni que vaya a hacerlo",
                 "en": "there is nobody on the other side: the request being written does not "
                       "mean anyone accepted it, or will act on it"},
                "falta_aporte"),
            LimiteDelRemediador(
                {"es": "el estado no vuelve: un fichero no se mueve solo, así que el ciclo "
                       "tiene que avanzarlo una persona con el verbo `noconformidad`",
                 "en": "state does not come back: a file does not move on its own, so a "
                       "person has to advance the cycle with the `noconformidad` verb"},
                "otro_instrumento"),
        )
