"""El conector local: un directorio. Es el que valida el contrato.

Se escribe ANTES que el de git y no después, y por un motivo: si el contrato
aguanta un directorio y un repositorio remoto sin un `if`, aguanta los demás.
Un contrato sacado del primer conector real acaba teniendo su forma, y luego
el segundo no encaja.

Y tiene una propiedad que lo hace útil más allá de las pruebas: un cliente que
no quiere dar acceso a su repositorio puede correr el motor sobre un directorio
suyo y entregar sólo el expediente. El producto no exige acceso al código; lo
ofrece.
"""
from __future__ import annotations

from pathlib import Path

from .contrato import Fuente, LimiteDelConector


class ConectorLocal:
    nombre = "local"
    version = "1.0.0"

    def resuelve(self, ubicacion: str) -> bool:
        return Path(ubicacion).is_dir()

    def fuente(self, ubicacion: str, referencia: str = "") -> Fuente:
        """Un directorio no tiene referencia inmutable, y eso se dice.

        La tentacion es poner la fecha de modificacion o un hash del contenido y
        llamarlo referencia. No lo es: una referencia inmutable identifica un
        contenido ANTES de leerlo, y sirve para que otro lo traiga igual. Un
        directorio local no le sirve a nadie mas, asi que `reproducible` es
        False y el motor lo sabe.
        """
        raiz = Path(ubicacion)
        if not raiz.is_dir():
            raise ValueError(f"{ubicacion}: no es un directorio")
        return Fuente(conector=self.nombre, conector_version=self.version,
                      ubicacion=str(raiz.resolve()), referencia_pedida=referencia or "",
                      referencia_inmutable=None,
                      detalles={"nota": "un directorio local no tiene referencia inmutable"})

    def materializar(self, fuente: Fuente, destino: Path) -> Path:
        """No copia nada: el directorio YA esta materializado.

        Copiarlo habria sido la opcion comoda y habria dejado una segunda copia
        del codigo del cliente en un sitio que el no eligio, que es justo lo que
        la tercera regla del contrato prohibe.
        """
        return Path(fuente.ubicacion)

    def limites(self) -> tuple[LimiteDelConector, ...]:
        return (
            LimiteDelConector(
                {"es": "no hay referencia inmutable: esta observación no se puede repetir "
                       "sobre el mismo contenido desde otro sitio",
                 "en": "there is no immutable reference: this observation cannot be repeated "
                       "over the same content from elsewhere"},
                "fuera_del_alcance_de_la_regla"),
            LimiteDelConector(
                {"es": "lo que haya fuera del directorio, incluidos los enlaces que salgan de él",
                 "en": "anything outside the directory, including links that leave it"},
                "fuera_del_alcance_de_la_regla"),
        )
