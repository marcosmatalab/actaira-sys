"""El almacen de evidencia: se anade, no se edita, y el estado no se guarda.

DOS DECISIONES, Y LAS DOS SON EL PRODUCTO
------------------------------------------
1. **Solo se anade.** Un fichero de lineas JSON al que se agrega y del que no
   se borra. Un expediente que se puede reescribir vale lo mismo que ninguno:
   la pregunta que hace un auditor no es "que dice tu sistema hoy", es "que
   decia el 3 de abril y quien lo cambio". Revocar una evidencia es anadir una
   linea de revocacion, no quitar la vieja.

2. **El estado NO se almacena.** En el fichero solo hay observaciones con su
   fecha, su sujeto y su frescura. Que una evidencia este VALIDA, RANCIA o
   SUPERADA se calcula en el momento de leer, con el reloj que se pase como
   argumento. Guardar el estado obligaria a recorrer el almacen entero cada vez
   que pasa un minuto, y ademas crearia una segunda fuente de verdad sobre lo
   mismo que ya dice la fecha: regla 10.

3. **Cada linea sella a la anterior.** Solo-anadir es una promesa sobre como
   escribe esta casa, no un hecho sobre el fichero: el fichero es de texto y lo
   tiene el cliente. Una auditoria externa lo demostro en una tarde -- abrio el
   `.jsonl`, cambio un veredicto y una frescura a mano, y el almacen los leyo
   como si nada. Asi que cada linea lleva `n`, `previo` y `sello`, y el sello
   cubre la linea entera junto con el sello de la anterior: tocar un byte de
   cualquier linea, quitar una, meter una o cambiarlas de orden rompe la cadena
   desde ese punto hasta el final, y `verificar_cadena` dice en cual se rompio.

   LO QUE LA CADENA NO DEMUESTRA, Y SE DICE AQUI PARA NO VENDERLO
   ---------------------------------------------------------------
   Quien tenga el fichero puede reescribirlo ENTERO y recalcular la cadena. Una
   cadena interna demuestra consistencia, no anclaje. Lo que convierte esto en
   una afirmacion frente a un tercero es sellar la cabeza (`cabeza()`) dentro
   del sello firmado y publicarla: a partir de ahi, reescribir el almacen exige
   ademas falsificar una firma Ed25519 sobre una raiz que ya salio de aqui.
   Vender la cadena sola como inmutabilidad seria la segunda negativa otra vez.

POR QUE ESTO ES EL FOSO, EN UNA FRASE
---------------------------------------
Todos los competidores demuestran que el registro no fue alterado. Ninguno
demuestra que la conclusion siga siendo cierta. La diferencia esta en el
`sujeto_digest`: a una evidencia la supera el digest sobre el que se tomo, no
el nombre de su sujeto, asi que un barrido de un modelo que no cambio no supera
nada, y uno de un modelo que si cambio supera SOLO la evidencia atada al digest
viejo. Eso convierte la vigilancia continua en reaccionar a un empujon mas un
vencimiento, en vez de sondear N repositorios cada minuto.
"""
from __future__ import annotations

import time
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from ..evidencia.registro import ESQUEMA, Estado, Registro, digest

ESQUEMA_ALMACEN = "actaira/almacen/v2"
GENESIS = "sha256:" + __import__("hashlib").sha256(b"actaira/almacen/genesis").hexdigest()


class AlmacenAlterado(Exception):
    """El fichero no es el que esta casa escribio, y se dice donde se rompio.

    Es una excepcion propia y no un `ValueError` porque quien la recoge tiene
    que hacer algo distinto: un almacen ilegible es un error de operacion, un
    almacen alterado es un incidente. El CLI les da codigos de salida distintos
    por eso mismo.
    """


# Los dos mecanismos de candado, resueltos UNA vez al importar y no en cada
# escritura. `fcntl` en POSIX, `msvcrt` en Windows; si no hubiera ninguno, el
# camino de escritura se niega a correr en vez de escribir sin candado.
try:                                      # POSIX
    from fcntl import LOCK_EX as _LOCK_EX
    from fcntl import flock as _flock
except ImportError:                       # pragma: no cover - solo fuera de POSIX
    _flock = None
    _LOCK_EX = 0
try:                                      # Windows
    import msvcrt as _msvcrt
except ImportError:                       # pragma: no cover - solo en Windows
    _msvcrt = None

_ESPERA_MAXIMA = 30.0
"""Lo que se espera por el candado antes de rendirse, en segundos.

Treinta segundos aguantan una cola de varias pasadas de integracion continua y
siguen siendo menos que el plazo de cualquiera de ellas. Rendirse no pierde la
observacion: el barrido siguiente la vuelve a tomar.
"""


class SinBloqueoExclusivo(Exception):
    """No se puede tomar el candado, asi que NO se escribe.

    Es una excepcion propia porque quien la recoge tiene que distinguirla de un
    almacen alterado: aqui no ha pasado nada malo todavia, y precisamente por
    eso no se sigue.
    """


def _tomar(fd: int) -> None:
    """Toma el candado exclusivo sobre un descriptor, en los dos sistemas."""
    if _flock is not None:
        _flock(fd, _LOCK_EX)
        return
    if _msvcrt is not None:
        espera, esperado = 0.01, 0.0
        while True:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if esperado >= _ESPERA_MAXIMA:
                    raise SinBloqueoExclusivo(
                        f"no se pudo tomar el candado del almacen en {_ESPERA_MAXIMA:.0f} s. "
                        f"No se escribe: una escritura sin candado bifurcaria la cadena y "
                        f"dejaria el almacen alterado de forma permanente.") from None
                time.sleep(espera)
                esperado += espera
                espera = min(espera * 2, 0.25)
    raise SinBloqueoExclusivo(
        "este sistema no ofrece ni `fcntl.flock` ni `msvcrt.locking`, asi que no hay forma "
        "de serializar dos escritores. No se escribe: la cadena de evidencia se encadena "
        "hacia atras y una bifurcacion no se puede recoser.")


def _soltar(fd: int) -> None:
    if _flock is None and _msvcrt is not None:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
        except OSError:
            pass                      # lo suelta el cierre del descriptor


@contextmanager
def _bloqueado(ruta: Path):
    """El candado del almacen, sobre un fichero APARTE y no sobre los datos.

    TRES COSAS QUE ESTABAN MAL, Y LA TERCERA LA ENCONTRO EL ARREGLO DE LA SEGUNDA
    -----------------------------------------------------------------------------
    1. Fuera de POSIX no habia candado ninguno: `_bloquear` era una funcion
       vacia con un docstring que decia que la bifurcacion «se detecta
       despues». Detectarla despues no sirve. La cadena se encadena hacia
       atras, asi que una bifurcacion no se recose: el almacen queda
       `AlmacenAlterado` para siempre, y en la semantica de este modulo eso no
       es un error de operacion sino un INCIDENTE. Dos pasadas de integracion
       continua a la vez -- la forma normal de usar esto -- convertian el
       expediente de un cliente en un incidente permanente.

    2. Windows SI tiene candado: `msvcrt.locking`. Ponerlo lo hizo peor de una
       manera instructiva: el candado de Windows es OBLIGATORIO, no consultivo.
       Bloquear el byte cero del `.jsonl` bloqueaba tambien a los LECTORES, y
       `_crudas` -- que abre el fichero por su cuenta para verificar la cadena
       antes de escribir -- empezo a recibir `PermissionError`. El arreglo
       convirtio un fallo intermitente en uno seguro, que es la unica cosa
       buena que se puede decir de el.

    3. La forma correcta es no candar los datos. Se canda un fichero aparte,
       `<almacen>.lock`, que nadie lee y nadie escribe: existe solo para ser el
       objeto del candado. Con eso los dos sistemas se comportan igual -- el
       consultivo de POSIX y el obligatorio de Windows -- y los lectores no se
       enteran de que hay nadie escribiendo, que es justo lo que se queria.

    El fichero de candado NO se borra al soltar. Borrarlo abriria una carrera
    clasica: un proceso lo borra mientras otro acaba de abrirlo, y los dos
    acaban candando ficheros distintos con el mismo nombre. Queda ahi, vacio, y
    cuesta cero.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    candado = ruta.with_name(ruta.name + ".lock")
    fd = os.open(str(candado), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _tomar(fd)
        try:
            yield
        finally:
            _soltar(fd)
    finally:
        os.close(fd)


ORIGENES_NO_DEMOSTRABLES = frozenset({
    "migrada_sin_cadena",          # la escribio una version del motor sin cadena
    "migrada_desde_cadena_rota",   # venia de un almacen que encadenaba y no cuadraba
})
"""Las marcas que dicen «de esta linea no se puede demostrar que este intacta».

Viven en un conjunto y no sueltas en un `==` porque hay mas de un consumidor --
`sin_cadena_demostrable`, el verbo `almacen`, el expediente -- y el dia que se
anada una tercera procedencia hay que anadirla en un sitio. La segunda entro
despues de la primera y hubo que perseguir los `== "migrada_sin_cadena"` que
habia repartidos; esto es para que no haya una tercera persecucion.

La marca va DENTRO del sello de su linea, asi que quitarla rompe la cadena. Una
marca de «no demostrable» que se pudiera borrar no serviria de nada.
"""


def _sello_de(cuerpo: dict[str, Any]) -> str:
    """El sello de una linea: su contenido entero menos el propio sello."""
    return digest({k: v for k, v in cuerpo.items() if k != "sello"})


@dataclass
class Linea:
    """Una linea del almacen. O es una observacion, o es una revocacion."""

    tipo: str                    # "observacion" | "revalidacion" | "revocacion"
    cuando: str
    registro: dict[str, Any] | None = None
    registro_id: str | None = None
    motivo: str | None = None
    quien: str | None = None
    n: int = 0
    previo: str = GENESIS
    sello: str = ""
    origen: str | None = None    # None, o uno de ORIGENES_NO_DEMOSTRABLES

    def cuerpo(self) -> dict[str, Any]:
        d: dict[str, Any] = {"esquema": ESQUEMA_ALMACEN, "tipo": self.tipo,
                             "cuando": self.cuando, "n": self.n, "previo": self.previo}
        if self.registro is not None:
            d["registro"] = self.registro
        for campo in ("registro_id", "motivo", "quien", "origen"):
            if getattr(self, campo) is not None:
                d[campo] = getattr(self, campo)
        return d

    def a_json(self) -> dict[str, Any]:
        d = self.cuerpo()
        d["sello"] = self.sello or _sello_de(d)
        return d


@dataclass
class Almacen:
    ruta: Path

    @staticmethod
    def abrir(ruta: str | Path) -> "Almacen":
        return Almacen(Path(ruta))

    def _crudas(self) -> Iterator[tuple[int, dict[str, Any]]]:
        """Las lineas tal cual, sin comprobar nada. Solo la usa la verificacion."""
        if not self.ruta.is_file():
            return
        for n, cruda in enumerate(self.ruta.read_text(encoding="utf-8").splitlines(), 1):
            if not cruda.strip():
                continue
            try:
                yield n, json.loads(cruda)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"{self.ruta}:{n}: linea ilegible en el almacen de evidencia ({e}). "
                    "No se salta en silencio: un almacen con un hueco no es un almacen.") from e

    def _lineas(self) -> Iterator[Linea]:
        """Las lineas COMPROBADAS. Leer y verificar son la misma operacion.

        Deliberadamente no hay una manera de leer el almacen saltandose la
        cadena: si existiera, seria la que acabaria llamando el codigo con
        prisa, y la comprobacion se convertiria en un adorno. Quien quiera el
        diagnostico sin la excepcion tiene `verificar_cadena`, que devuelve la
        lista de roturas en vez de levantarlas.
        """
        esperado = GENESIS
        for n, d in self._crudas():
            fallo = self._rotura(n, d, esperado)
            if fallo:
                raise AlmacenAlterado(fallo)
            esperado = d["sello"]
            yield Linea(tipo=d.get("tipo", "observacion"), cuando=d["cuando"],
                        registro=d.get("registro"), registro_id=d.get("registro_id"),
                        motivo=d.get("motivo"), quien=d.get("quien"),
                        n=d["n"], previo=d["previo"], sello=d["sello"],
                        origen=d.get("origen"))

    def _rotura(self, n: int, d: dict[str, Any], previo_esperado: str) -> str | None:
        """El motivo por el que esta linea no encaja, o None si encaja."""
        if "sello" not in d or "previo" not in d or "n" not in d:
            return (f"{self.ruta}:{n}: linea sin cadena de sellos. La escribio una version "
                    f"anterior del motor, que no podia demostrar que no habia sido alterada. "
                    f"No se acepta en silencio: vuelve a observar sobre un almacen nuevo.")
        if d["n"] != n:
            return (f"{self.ruta}:{n}: la linea dice ser la numero {d['n']}. Falta una linea, "
                    f"sobra una o estan cambiadas de orden.")
        if d["previo"] != previo_esperado:
            return (f"{self.ruta}:{n}: encadena con {d['previo'][:23]}... y la linea anterior "
                    f"termina en {previo_esperado[:23]}.... La cadena se rompe aqui.")
        if _sello_de(d) != d["sello"]:
            return (f"{self.ruta}:{n}: el contenido de la linea no coincide con su sello. "
                    f"Alguien la edito despues de escribirla.")
        return None

    def primera_rotura(self) -> int | None:
        """El numero de la primera linea que no encaja, o None si la cadena entera vale.

        `verificar_cadena` devuelve el motivo escrito para una persona; esto
        devuelve el sitio, que es lo que necesita `migrar_a` para saber hasta
        donde puede seguir fiandose.

        Y hay una diferencia deliberada entre las dos: un almacen en el que
        NINGUNA linea encadena no tiene rotura. Es el fichero de la version
        anterior del motor, que es exactamente para lo que existe `migrar_a`;
        `verificar_cadena` si lo llama rotura porque quien pregunta ahi quiere
        saber si puede fiarse, y la respuesta es que no. Aqui la pregunta es
        otra: si alguien lo TOCO. No tener cadena no es haber sido tocado.
        """
        crudas = list(self._crudas())
        if not any("sello" in d for _, d in crudas):
            # NINGUNA linea encadena: es un almacen de la version anterior del
            # motor, no uno manipulado. `_rotura` dice «linea sin cadena de
            # sellos» para cada una, y devolver eso aqui haria que `migrar_a`
            # -- que existe justo para estos ficheros -- se negara a migrarlos.
            #
            # La distincion es la que da sentido a las dos banderas del verbo:
            # «no tenia cadena» es rutina al actualizar y «tenia cadena y no
            # cuadra» es un incidente. Fundirlas en una sola respuesta era el
            # error de la primera version de esta funcion, y habria convertido
            # la rutina en el permiso para el incidente.
            return None
        esperado = GENESIS
        for n, d in crudas:
            if self._rotura(n, d, esperado):
                return n
            esperado = d["sello"]
        return None

    def verificar_cadena(self) -> list[str]:
        """Las roturas, de la primera a la ultima. Lista vacia es cadena intacta.

        Para de mirar en la primera: a partir de una rotura todo lo que sigue
        encadena con un sello que ya no vale, asi que enumerar las demas seria
        contar N veces el mismo incidente -- el modo de fallo de las
        herramientas que devuelven doscientos hallazgos de una sola causa.
        """
        esperado, fuera = GENESIS, []
        for n, d in self._crudas():
            fallo = self._rotura(n, d, esperado)
            if fallo:
                fuera.append(fallo)
                break
            esperado = d["sello"]
        return fuera

    def comprobar_cabeza(self, esperada: str) -> str | None:
        """El motivo por el que la cabeza no es la esperada, o None.

        LO QUE LA CADENA SOLA NO PUEDE VER, Y ES ESTO
        -----------------------------------------------
        Quitar las ultimas lineas de un almacen deja un prefijo perfectamente
        valido: la cadena verifica y nadie se entera de que faltan seis meses
        de observaciones. Ningun mecanismo interno puede detectarlo, porque el
        fichero truncado es indistinguible de un fichero que aun no ha crecido.

        Lo unico que lo detecta es haber anotado FUERA la cabeza de antes. Por
        eso `almacen verificar --cabeza-esperada` existe y por eso la cabeza se
        publica dentro del sello firmado: no es un adorno del verbo, es la
        mitad del mecanismo que la cadena no puede aportar.
        """
        real = self.cabeza()
        if real == esperada:
            return None
        n = sum(1 for _ in self._crudas())
        return (f"la cabeza es {real[:23]}... y se esperaba {esperada[:23]}.... "
                f"El almacen tiene {n} lineas. Si la cadena verifica y la cabeza no es "
                f"la esperada, es que le quitaron lineas del final o lo reescribieron entero.")

    def migrar_a(self, destino: "Almacen", *,
                 aceptar_cadena_rota: bool = False) -> tuple[int, int]:
        """Encadena un almacen escrito por la version anterior, EN OTRO FICHERO.

        LO QUE ESTA FUNCION NO HACE, Y ES LO IMPORTANTE
        ------------------------------------------------
        No demuestra que el almacen viejo estuviera intacto. No puede: no habia
        cadena. Encadenar y callar convertiria la migracion en la manera comoda
        de blanquear un fichero editado -- entra sin cadena, sale con cadena y
        con pinta de expediente impecable.

        Asi que cada linea migrada sale marcada `origen: migrada_sin_cadena`, y
        esa marca va DENTRO del sello: no se puede quitar sin romper la cadena.
        A partir de ahi el expediente dice la verdad completa -- «de aqui hacia
        atras no se puede demostrar, de aqui hacia delante si» -- que es una
        afirmacion util, y «todo verificado» habria sido una mentira.

        Y escribe en otro fichero, nunca encima: el original se conserva porque
        es lo unico que queda de lo que habia antes de tocar nada.
        """
        if destino.ruta.exists() and destino.ruta.stat().st_size:
            raise AlmacenAlterado(
                f"{destino.ruta}: ya existe y no esta vacio. La migracion no escribe "
                f"encima de un almacen: elige un destino nuevo.")

        # SE COMPRUEBA EL ORIGEN ANTES DE COPIAR NADA.
        #
        # Esta funcion leia con `_crudas` -- que no verifica -- y decidia linea
        # por linea: si traia `sello`, la daba por buena y la copiaba con su
        # `origen` original. Con eso, un almacen cuya cadena estaba ROTA entraba
        # roto y salia con una cadena nueva perfectamente valida, conservando el
        # contenido manipulado y sin una sola marca que dijera de donde venia.
        #
        # Reproducido: se cambia `frescura_dias` de la primera linea a 9999, la
        # cadena del origen queda rota, se migra, y el destino sale con
        # «0 sin cadena, 3 ya encadenadas», cadena valida, la frescura
        # manipulada intacta y `origen: null`. La migracion era exactamente la
        # manera comoda de blanquear un fichero editado que el docstring de esta
        # funcion decia estar evitando.
        #
        # Lo que fallaba no era la intencion sino el alcance: se penso en el
        # almacen SIN cadena -- el de la version anterior del motor -- y no en
        # el que TIENE cadena y no la cumple. Son dos cosas distintas y solo una
        # estaba cubierta.
        rotura = self.primera_rotura()
        if rotura is not None and not aceptar_cadena_rota:
            raise AlmacenAlterado(
                f"{self.ruta}: la cadena se rompe en la linea {rotura} y no se migra. "
                f"Migrar reescribe los sellos, asi que lo que entra roto saldria con una "
                f"cadena nueva y valida: la rotura desapareceria del expediente en vez de "
                f"constar en el. Si necesitas conservar el contenido de todas formas, migra "
                f"con `aceptar_cadena_rota=True`: cada linea desde la {rotura} sale marcada "
                f"`migrada_desde_cadena_rota`, esa marca va DENTRO del sello y no se puede "
                f"quitar sin romper la cadena nueva.\n  "
                + "\n  ".join(self.verificar_cadena()))

        migradas = ya = rotas = 0
        plantillas = []
        for n, d in self._crudas():
            l = Linea(tipo=d.get("tipo", "observacion"), cuando=d["cuando"],
                      registro=d.get("registro"), registro_id=d.get("registro_id"),
                      motivo=d.get("motivo"), quien=d.get("quien"))
            if rotura is not None and n >= rotura:
                # Desde la rotura hacia delante no hay nada demostrable: ni el
                # contenido, ni el orden, ni que no falte una linea. Se marcan
                # TODAS, tengan sello o no, porque tener sello es justo lo que
                # dejo de significar algo en cuanto la cadena no cuadra.
                l.origen = "migrada_desde_cadena_rota"; rotas += 1
            elif "sello" in d:
                l.origen = d.get("origen"); ya += 1
            else:
                l.origen = "migrada_sin_cadena"; migradas += 1
            plantillas.append(l)
        destino.ruta.parent.mkdir(parents=True, exist_ok=True)
        with _bloqueado(destino.ruta), destino.ruta.open("a+", encoding="utf-8") as f:
            destino._escribir(f, plantillas)
        return migradas + rotas, ya

    def sin_cadena_demostrable(self) -> int:
        """Cuantas lineas NO se puede demostrar que esten intactas.

        Cuenta las DOS marcas, y la segunda se anadio despues justamente por
        esto: `migrada_sin_cadena` es una linea que escribio una version del
        motor que no encadenaba, y `migrada_desde_cadena_rota` es una que venia
        de un almacen que si encadenaba y no cuadraba. Son procedencias
        distintas y la consecuencia es la misma -- no se puede demostrar que sea
        la que se escribio -- asi que contar solo una habria hecho que un
        almacen migrado desde una cadena rota declarara CERO lineas no
        demostrables. Es el mismo fallo que se acaba de cerrar en `migrar_a`,
        asomando por la ventana de al lado.
        """
        return sum(1 for l in self._lineas() if l.origen in ORIGENES_NO_DEMOSTRABLES)

    def cabeza(self) -> str:
        """El sello de la ultima linea: lo unico que hace falta anclar fuera.

        Publicar este valor dentro de un sello firmado convierte la cadena en
        una afirmacion frente a un tercero. Sin anclarlo, la cadena solo dice
        que el fichero es consistente consigo mismo.
        """
        ultimo = GENESIS
        for _, d in self._crudas():
            ultimo = d.get("sello", ultimo)
        return ultimo

    def anadir(self, registros: list[Registro], cuando: datetime) -> tuple[int, int]:
        """Agrega lo observado. Devuelve (nuevas, revalidadas).

        Una observacion que dice LO MISMO que otra ya guardada -- mismo
        control, mismo sujeto y mismo contenido -- no se escribe entera otra
        vez: se anade una linea de revalidacion, que es un identificador y una
        fecha. La diferencia importa por dos motivos y los dos son de producto.

        Uno: sin ella, cada pasada de integracion continua escribe el registro
        completo, y a los seis meses el tamano del almacen mide la frecuencia
        del cron del cliente en vez de su actividad.

        Dos: la revalidacion SI mueve el reloj de la frescura, porque alguien
        volvio a mirar de verdad. Tratarla como un duplicado a descartar haria
        caducar evidencia que se esta comprobando cada dia, que es el fallo
        contrario y peor.
        """
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with _bloqueado(self.ruta), self.ruta.open("a+", encoding="utf-8") as f:
            # Se relee YA bloqueado: si se leyera antes, dos pasadas de
            # integracion continua simultaneas escribirian la misma linea dos
            # veces o encadenarian las dos con el mismo `previo`.
            previos = {l.registro["id"]: l.registro for l in self._lineas()
                       if l.tipo == "observacion" and l.registro}
            por_contenido = {(d["control_id"], d["sujeto_digest"],
                              json.dumps(d.get("contenido", {}), sort_keys=True)): d["id"]
                             for d in previos.values()}
            nuevas, revalidadas = [], []
            for r in registros:
                clave = (r.control_id, r.sujeto_digest,
                         json.dumps(r.contenido, sort_keys=True))
                if clave in por_contenido:
                    revalidadas.append(por_contenido[clave])
                else:
                    nuevas.append(r)
            if not nuevas and not revalidadas:
                return 0, 0
            marca = cuando.astimezone(timezone.utc).isoformat()
            self._escribir(f, [Linea("observacion", marca, registro=r.a_json()) for r in nuevas]
                           + [Linea("revalidacion", marca, registro_id=rid) for rid in revalidadas])
        return len(nuevas), len(revalidadas)

    def _cola(self) -> tuple[int, str]:
        """(numero de la ultima linea, su sello). El almacen vacio es (0, GENESIS)."""
        n, sello = 0, GENESIS
        for _, d in self._crudas():
            n, sello = d.get("n", n + 1), d.get("sello", sello)
        return n, sello

    def _escribir(self, f, lineas: list[Linea]) -> None:
        """Encadena y escribe. El fichero llega ya abierto y bloqueado.

        Comprueba la cadena ANTES de anadir nada. `anadir` ya la leia entera
        para no duplicar, pero `revocar` no, y por ahi se podia extender la
        cadena de un almacen ya manipulado: la rotura quedaba enterrada bajo
        lineas nuevas y perfectamente selladas. Ningun camino de escritura
        puede saltarse esto, y por eso esta aqui y no en cada verbo.
        """
        roturas = self.verificar_cadena()
        if roturas:
            raise AlmacenAlterado(
                "no se anade a un almacen que no verifica: lo nuevo quedaria "
                "encima de una rotura y la taparia.\n  " + "\n  ".join(roturas))
        n, previo = self._cola()
        for l in lineas:
            n += 1
            l.n, l.previo = n, previo
            l.sello = _sello_de(l.cuerpo())
            f.write(json.dumps(l.a_json(), ensure_ascii=False, sort_keys=True) + "\n")
            previo = l.sello

    def revocar(self, registro_id: str, motivo: str, quien: str, cuando: datetime) -> None:
        """Revoca anadiendo, nunca borrando. La vieja sigue ahi y se ve revocada."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        linea = Linea("revocacion", cuando.astimezone(timezone.utc).isoformat(),
                      registro_id=registro_id, motivo=motivo, quien=quien)
        with _bloqueado(self.ruta), self.ruta.open("a+", encoding="utf-8") as f:
            self._escribir(f, [linea])

    def registros(self) -> list[Registro]:
        fuera = []
        for l in self._lineas():
            if l.tipo != "observacion" or not l.registro:
                continue
            d = l.registro
            if d.get("esquema") not in (ESQUEMA, "actaira/declaracion/v1"):
                raise ValueError(f"{self.ruta}: registro con esquema desconocido {d.get('esquema')!r}")
            r = Registro(
                id=d["id"], obligacion_id=d["obligacion_id"], control_id=d["control_id"],
                sujeto_digest=d["sujeto_digest"], observado_en=d["observado_en"],
                contenido=d.get("contenido", {}), frescura_dias=d.get("frescura_dias"),
                estado_declarado=Estado(d["estado_declarado"]) if d.get("estado_declarado")
                else Estado.VALIDA,
                motivo=d.get("motivo"), esquema=d.get("esquema", ESQUEMA))
            # La cadena de sellos demuestra que la LINEA es la que se escribio.
            # Esto demuestra que el REGISTRO resume lo que dice resumir, que es
            # otra propiedad y hace falta porque un almacen puede traer lineas
            # de otra herramienta. Las dos usan la misma definicion de cuerpo.
            mal = r.verificar_id()
            if mal:
                raise AlmacenAlterado(f"{self.ruta}: {mal}")
            fuera.append(r)
        return fuera

    def revalidaciones(self) -> dict[str, str]:
        """{id del registro: la ultima vez que se volvio a ver lo mismo}."""
        fuera: dict[str, str] = {}
        for l in self._lineas():
            if l.tipo == "revalidacion" and l.registro_id:
                previo = fuera.get(l.registro_id)
                if previo is None or datetime.fromisoformat(l.cuando) > datetime.fromisoformat(previo):
                    fuera[l.registro_id] = l.cuando
        return fuera

    def revocadas(self) -> frozenset[str]:
        return frozenset(l.registro_id for l in self._lineas()
                         if l.tipo == "revocacion" and l.registro_id)

    def resumen(self) -> dict[str, Any]:
        regs = self.registros()
        return {"observaciones": len(regs), "revalidaciones": len(self.revalidaciones()),
                "revocaciones": len(self.revocadas()),
                "controles": len({r.control_id for r in regs}),
                "sujetos": len({r.sujeto_digest for r in regs})}
