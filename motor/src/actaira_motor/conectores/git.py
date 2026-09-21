"""El conector de git: GitHub, GitLab, Bitbucket, Azure DevOps y el de tu casa.

POR QUE UNO Y NO CUATRO
-------------------------
La lista de conectores que pide todo el mundo es «GitHub, GitLab, Bitbucket,
Azure DevOps», y son cuatro productos distintos con cuatro APIs distintas. Pero
para lo que este producto necesita -traer un árbol de ficheros en un commit
concreto- los cuatro hablan el mismo protocolo, que es git sobre HTTPS. Escribir
cuatro integraciones para usar la misma primitiva habría sido cuatro veces el
trabajo, cuatro veces el mantenimiento y cuatro sitios donde meter un `if`.

Lo que SÍ es distinto entre ellos son los eventos, los permisos y los tickets.
Eso vive en otro sitio y no aquí: mezclar «traer el código» con «abrir un pull
request» en un solo conector es lo que hace que cambiar de proveedor de tickets
obligue a tocar el que lee el código.

LAS DOS DECISIONES QUE IMPORTAN
---------------------------------
1. **Se clona superficial y se resuelve a un commit.** La referencia que pide
   el cliente («main») se convierte en la que se publica (el sha), y la
   evidencia queda atada a esa. Sin eso, repetir la observación mañana da otra
   cosa y nadie sabe por qué.

2. **Las credenciales no las gestiona este módulo.** Se usan las que git ya
   tenga configuradas en la máquina que corre el motor: el auxiliar de
   credenciales, la clave del agente, el token del entorno de integración
   continua. Un producto de cumplimiento que se guarda los tokens de sus
   clientes se convierte en el objetivo más valioso de su propia cadena de
   suministro, y la manera de no serlo es no tenerlos.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .contrato import Fuente, LimiteDelConector, redactar

_URL = re.compile(r"^(https://|git@|ssh://|git://)")
LIMITE_SEGUNDOS = 120


class ErrorDelConector(Exception):
    """Falla, y con un mensaje del que ya se han quitado los secretos."""


def _git(*args: str, cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           timeout=LIMITE_SEGUNDOS)
    except FileNotFoundError as e:
        raise ErrorDelConector("no hay `git` en esta maquina: este conector lo necesita") from e
    except subprocess.TimeoutExpired as e:
        raise ErrorDelConector(f"git tardo mas de {LIMITE_SEGUNDOS}s y se corto") from e
    if r.returncode != 0:
        # El mensaje de git puede llevar la URL con usuario y contrasena dentro.
        # Se limpia el mensaje ENTERO, no solo la salida de git: la primera
        # version limpiaba `salida` y metia la URL sin limpiar en el prefijo
        # que ella misma construia, con lo que la credencial salia igual. Lo
        # encontro la prueba, que es para lo que esta.
        salida = (r.stderr or r.stdout).strip()
        raise ErrorDelConector(
            redactar(f"git {' '.join(args[:2])} fallo: {salida}")[:500])
    return r.stdout.strip()


def _borrar_el_git_del_cliente(dot_git: Path) -> None:
    """Borra el `.git` del clon, y REVIENTA si no lo consigue.

    Estaba escrito `shutil.rmtree(..., ignore_errors=True)`, y esa bandera es el
    fallo. En Windows git deja sus objetos en solo lectura, `rmtree` no los
    puede borrar, y `ignore_errors` se traga la excepcion: el historial entero
    del repositorio del cliente se quedaba dentro del arbol materializado y
    nadie se enteraba. El conector cumplia su contrato en Linux y lo incumplia
    en silencio en Windows.

    Un directorio de trabajo que conserva el `.git` de un cliente no es una
    molestia de limpieza: en una plataforma multi cliente es material del
    cliente sobreviviendo a la observacion que lo trajo, y ese es exactamente
    el residuo que un aislamiento tiene que no dejar.

    Asi que se quita el solo lectura y se reintenta, y despues se COMPRUEBA.
    Si sigue ahi se lanza: preferimos que la observacion no ocurra a que ocurra
    dejando detras lo que se prometio borrar.
    """
    import os
    import stat

    if dot_git.exists():
        # Se quita el solo lectura ANTES y a mano, en vez de pasarle a `rmtree`
        # un gestor de errores: el nombre de ese parametro cambio de `onerror`
        # a `onexc` en Python 3.12 y este paquete declara soportar 3.11, asi
        # que usar cualquiera de los dos ata el conector a una version del
        # interprete por una limpieza de ficheros.
        #
        # UN DIRECTORIO NO LLEVA LOS MISMOS BITS QUE UN FICHERO
        # ------------------------------------------------------
        # Aqui habia un solo `chmod` con `S_IWRITE | S_IREAD` -- o sea 0600 --
        # aplicado a `dirs + ficheros`. En Windows eso es inofensivo, porque
        # alli `chmod` solo toca el atributo de solo lectura. En POSIX el bit
        # de ejecucion de un directorio ES el permiso de entrar en el, asi que
        # darle 0600 a `.git/objects` lo cierra: `os.walk` deja de poder
        # descender, `rmtree` deja de poder borrar, el `.git` sobrevive y este
        # metodo lanza SIEMPRE. El conector quedaba roto en Linux y en macOS.
        #
        # Lo que hace esto doblemente feo es que el arreglo de Windows descrito
        # arriba rompio lo que ya funcionaba: el docstring dice que el conector
        # «cumplia su contrato en Linux y lo incumplia en silencio en Windows»,
        # y despues del arreglo no lo cumplia en ninguno de los dos. Un arreglo
        # que no se corre en el sistema que ya funcionaba no es un arreglo.
        try:
            os.chmod(dot_git, stat.S_IRWXU)
        except OSError:
            pass                      # se decide abajo, mirando el disco
        for base, dirs, ficheros in os.walk(dot_git):
            for nombre in dirs:
                try:
                    os.chmod(os.path.join(base, nombre), stat.S_IRWXU)
                except OSError:
                    pass              # se decide abajo, mirando el disco
            for nombre in ficheros:
                try:
                    os.chmod(os.path.join(base, nombre), stat.S_IWRITE | stat.S_IREAD)
                except OSError:
                    pass              # se decide abajo, mirando el disco
        shutil.rmtree(dot_git, ignore_errors=True)
    if dot_git.exists():
        raise ErrorDelConector(
            f"{dot_git}: no se pudo borrar el .git del clon. El arbol materializado "
            f"conservaria el historial del repositorio de origen, asi que la "
            f"materializacion se aborta en vez de dejarlo detras.")


class ConectorGit:
    nombre = "git"
    version = "1.0.0"

    def resuelve(self, ubicacion: str) -> bool:
        return bool(_URL.match(ubicacion)) or ubicacion.endswith(".git")

    def fuente(self, ubicacion: str, referencia: str = "") -> Fuente:
        """Resuelve la referencia SIN traer los ficheros.

        `git ls-remote` pregunta al servidor cual es el commit de una rama o de
        una etiqueta y no descarga nada. Que la resolucion sea barata importa:
        permite comprobar si el sujeto cambio antes de decidir si hace falta
        volver a observar, que es la mitad del argumento de coste de la
        vigilancia continua.
        """
        ref = referencia or "HEAD"
        if re.fullmatch(r"[0-9a-f]{40}", ref):
            # Ya es inmutable: no hay nada que resolver y no se pregunta.
            return Fuente(self.nombre, self.version, ubicacion, ref, ref,
                          {"resuelto_por": "la referencia ya era un commit"})
        salida = _git("ls-remote", ubicacion, ref if ref != "HEAD" else "HEAD")
        primera = salida.splitlines()[0] if salida else ""
        sha = primera.split("\t")[0] if primera else ""
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ErrorDelConector(
                f"no se pudo resolver {ref!r} a un commit en ese repositorio. Sin referencia "
                f"inmutable, la observacion no se podria repetir, asi que no se observa.")
        return Fuente(self.nombre, self.version, ubicacion, ref, sha,
                      {"resuelto_por": "git ls-remote"})

    def materializar(self, fuente: Fuente, destino: Path) -> Path:
        """Clona superficial en el commit resuelto. El destino es del que llama.

        `--depth 1` trae un solo commit: el historial no hace falta para
        observar un estado, y traerlo entero multiplica el tiempo y el disco por
        nada. Lo que se pierde -cuando se introdujo un cambio- no es algo que
        este producto afirme.
        """
        if not fuente.reproducible:
            raise ErrorDelConector(
                "esta fuente no tiene referencia inmutable: materializarla daria un arbol "
                "que manana es otro, y una evidencia que no se puede repetir.")
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        if any(destino.iterdir()):
            raise ErrorDelConector(f"{destino}: no esta vacio. El destino lo gestiona quien "
                                   "llama, y este conector no borra nada de nadie.")
        _git("init", "--quiet", str(destino))
        _git("remote", "add", "origin", fuente.ubicacion, cwd=destino)
        _git("fetch", "--depth", "1", "--quiet", "origin", fuente.referencia_inmutable,
             cwd=destino)
        _git("checkout", "--quiet", "FETCH_HEAD", cwd=destino)
        _borrar_el_git_del_cliente(destino / ".git")
        return destino

    def limites(self) -> tuple[LimiteDelConector, ...]:
        return (
            LimiteDelConector(
                {"es": "los submódulos, que no se clonan: lo que vive en otro repositorio no se "
                       "observa aunque el código lo use",
                 "en": "submodules, which are not cloned: what lives in another repository is "
                       "not observed even if the code uses it"},
                "fuera_del_alcance_de_la_regla"),
            LimiteDelConector(
                {"es": "los ficheros que git no guarda: los de almacenamiento grande sin "
                       "descargar, y todo lo que ignore el .gitignore",
                 "en": "files git does not keep: large-file storage not fetched, and everything "
                       ".gitignore excludes"},
                "fuera_del_alcance_de_la_regla"),
            LimiteDelConector(
                {"es": "las ramas y los repositorios a los que la credencial de esta máquina no "
                       "llega: lo que no se ve no se declara vacío",
                 "en": "branches and repositories this machine's credential cannot reach: what "
                       "is not seen is not declared empty"},
                "no_legible"),
            LimiteDelConector(
                {"es": "el historial: se clona un solo commit, así que cuándo se introdujo un "
                       "cambio no es algo que esta observación pueda decir",
                 "en": "history: a single commit is cloned, so when a change was introduced is "
                       "not something this observation can say"},
                "fuera_del_alcance_de_la_regla"),
        )
