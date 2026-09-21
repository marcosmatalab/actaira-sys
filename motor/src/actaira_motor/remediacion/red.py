r"""A donde se le permite hablar al remediador de red, y por que casi a nadie.

EL PROBLEMA, DICHO SIN ADORNOS
--------------------------------
`RemediadorHttp` manda una peticion a la URL que diga `--destino` y le adjunta
la CREDENCIAL del cliente en una cabecera. Eso, sin mas, es un servicio que
hace peticiones autenticadas a donde le digan, y tiene tres consecuencias que no
son teoricas:

  - `--destino http://...` manda el token en claro por la red.
  - `--destino https://169.254.169.254/...` -- o cualquier direccion interna --
    llega al servicio de metadatos de la nube o a un servicio de la red privada
    del cliente, con la cabecera de autorizacion puesta. Es el SSRF clasico, y
    aqui es peor de lo normal porque la peticion no solo sale: sale firmada.
  - `urlopen` sigue las redirecciones por su cuenta y vuelve a mandar las
    cabeceras. Un destino legitimo que devuelva un 302 a una direccion interna
    consigue lo mismo que el punto anterior sin que nadie escriba esa direccion
    en ningun sitio.

Y una cuarta, mas aburrida y igual de real: `r.read()` sin techo. Un servidor
que conteste sin parar llena la memoria del proceso que corre el barrido.

LO QUE SE HACE, Y LO QUE SE DECIDE NO HACER
---------------------------------------------
Se hacen cuatro cosas: exigir HTTPS, resolver el nombre y rechazar las
direcciones que no son de internet publico, no seguir redirecciones a otro
origen, y poner techo a la respuesta.

Lo que NO se hace es una lista blanca de dominios cerrada de serie. Seria mas
estricto y seria falso: el producto tiene que hablar con el Jira del cliente,
que vive en el dominio del cliente, y una lista que hay que ampliar en cada
instalacion se amplia con un comodin la primera semana. El limite que si se
puede fijar de serie es el que no depende del cliente: que el destino este en
internet publico y no dentro de la maquina o de la red que ejecuta el barrido.

Quien quiera un destino interno -- un Jira en la intranet es un caso legitimo --
lo AFIRMA con `ACTAIRA_DESTINOS_INTERNOS`, nombrando los hosts. Es una
afirmacion de un operador, no una medicion, y por eso hay que escribirla entera:
no se admite un comodin.

SOBRE LA CARRERA ENTRE COMPROBAR Y CONECTAR
---------------------------------------------
Esto resuelve el nombre, comprueba las direcciones y luego deja que `urlopen`
lo resuelva otra vez. Entre las dos resoluciones un DNS hostil puede cambiar la
respuesta: es el DNS rebinding, y esta comprobacion no lo cierra. Cerrarlo de
verdad exige conectar al socket uno mismo y pasarle la direccion ya elegida, lo
que significa reimplementar el cliente HTTP.

Se escribe aqui en vez de dejarlo implicito porque un limite que no se declara
se convierte en una promesa que el producto no hizo pero que alguien leyo. Queda
como deuda conocida; lo que esta cerrado es el caso que de verdad se da, que es
un destino mal puesto o una redireccion, no un atacante con control del DNS del
cliente.
"""
from __future__ import annotations

import ipaddress
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

LIMITE_RESPUESTA = 4 * 1024 * 1024
"""Lo que se lee como maximo de una respuesta, en bytes.

Cuatro megas sobran para un ticket y no dejan que un servidor que contesta sin
parar llene la memoria del proceso que corre el barrido.
"""

VARIABLE_HTTP = "ACTAIRA_PERMITIR_HTTP"
VARIABLE_INTERNOS = "ACTAIRA_DESTINOS_INTERNOS"


class DestinoNoPermitido(Exception):
    """El destino no es un sitio al que este modulo vaya a mandar la credencial."""


def _hosts_afirmados() -> frozenset[str]:
    """Los hosts internos que un operador ha AFIRMADO que son suyos.

    Se separan por comas y se comparan enteros. No se admite comodin a
    proposito: un comodin convierte la afirmacion en un permiso general, y
    entonces lo que queda no es una excepcion sino la ausencia de la regla.
    """
    crudo = os.environ.get(VARIABLE_INTERNOS, "")
    return frozenset(x.strip().lower() for x in crudo.split(",") if x.strip())


def _es_publica(ip: ipaddress._BaseAddress) -> bool:
    """Si la direccion esta en internet publico.

    Se usan las propiedades de `ipaddress` y no una lista de rangos escrita a
    mano: la lista se queda corta -- la de casi todo el mundo se olvida de
    `::ffff:169.254.169.254`, que es la direccion de metadatos en IPv6 mapeada,
    y de `0.0.0.0/8` -- y ademas hay que mantenerla.
    """
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified)


def comprobar(url: str) -> None:
    """Deja pasar la URL, o lanza `DestinoNoPermitido` diciendo por que.

    Se llama antes de CADA peticion, no solo con el destino inicial: una
    redireccion produce otra URL y esa tambien tiene que pasar por aqui.
    """
    partes = urllib.parse.urlsplit(url)
    esquema = (partes.scheme or "").lower()
    host = (partes.hostname or "").lower()

    if not host:
        raise DestinoNoPermitido(f"{url!r} no trae host")

    if esquema not in ("http", "https"):
        raise DestinoNoPermitido(
            f"esquema {esquema!r}: este remediador habla HTTPS y nada mas. Un `file://` o un "
            f"`gopher://` en un destino es siempre un intento de leer algo que no es un ticket")

    if esquema == "http" and os.environ.get(VARIABLE_HTTP) != "1":
        raise DestinoNoPermitido(
            f"{url!r} va sin cifrar y a esta peticion se le adjunta la credencial del "
            f"cliente. Usa https. Para un servidor de pruebas en tu maquina, arranca con "
            f"{VARIABLE_HTTP}=1 y sabe lo que estas afirmando.")

    if host in _hosts_afirmados():
        return                              # el operador dijo que ese es suyo

    try:
        infos = socket.getaddrinfo(host, partes.port or (443 if esquema == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except OSError as e:
        raise DestinoNoPermitido(
            f"no se pudo resolver {host!r}: {e}. No se manda la credencial a un nombre que "
            f"no se ha podido comprobar.") from None

    direcciones = {ipaddress.ip_address(info[4][0]) for info in infos}
    privadas = sorted(str(ip) for ip in direcciones if not _es_publica(ip))
    if privadas:
        raise DestinoNoPermitido(
            f"{host!r} resuelve a {privadas}, que no esta en internet publico. A esta "
            f"peticion se le adjunta la credencial del cliente, asi que un destino dentro "
            f"de la maquina o de la red que corre el barrido llegaria al servicio de "
            f"metadatos de la nube o a un servicio interno, autenticado. Si ese host es "
            f"tuyo de verdad, nombralo en {VARIABLE_INTERNOS} (separado por comas, sin "
            f"comodines).")


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
    """Corta toda redireccion. No la sigue y no la esconde.

    `urlopen` las sigue por su cuenta y vuelve a mandar las cabeceras, asi que
    un destino legitimo que conteste 302 a una direccion interna consigue lo
    mismo que escribir esa direccion en `--destino`, sin que aparezca en ningun
    sitio que alguien pueda revisar.

    Se podria seguir la redireccion pasando la nueva URL por `comprobar` otra
    vez. No se hace: un sistema de tickets que contesta con una redireccion a
    una peticion de API es un sistema mal configurado o uno que no es el que se
    cree, y las dos cosas se arreglan mirandolas, no siguiendolas.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DestinoNoPermitido(
            f"{req.full_url} contesto {code} redirigiendo a {newurl}. No se sigue: la "
            f"peticion lleva la credencial del cliente y una redireccion la mandaria a un "
            f"sitio que no aparece en ninguna configuracion revisable.")


_ABRIDOR = urllib.request.build_opener(_SinRedirecciones())


def pedir(peticion: urllib.request.Request, plazo: int) -> str:
    """Hace la peticion con las cuatro defensas puestas y devuelve el cuerpo.

    Lee un byte de mas a proposito: asi se puede distinguir «la respuesta cabia
    justo» de «la respuesta se corto», y lo segundo se dice en vez de devolver
    medio documento como si fuera entero.
    """
    comprobar(peticion.full_url)
    with _ABRIDOR.open(peticion, timeout=plazo) as r:
        crudo = r.read(LIMITE_RESPUESTA + 1)
    if len(crudo) > LIMITE_RESPUESTA:
        raise DestinoNoPermitido(
            f"la respuesta pasa de {LIMITE_RESPUESTA} bytes y se corta. No se devuelve lo "
            f"leido: medio documento JSON se parece bastante a uno entero y se acabaria "
            f"tratando como tal.")
    return crudo.decode("utf-8", "replace")
