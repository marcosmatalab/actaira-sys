"""Un proveedor de identidad DE VERDAD, levantado aqui, para probar contra el.

POR QUE ESTO EXISTE
--------------------
La fase `identidad` prueba el verificador contra un doble: una clave RSA de
ese mismo proceso y unas reclamaciones escritas a mano. Eso demuestra que el
servidor comprueba firmas, reclamaciones y papeles, y no demuestra que hable
con un proveedor concreto. La frase que la fase imprime -- «contra un Entra ID
o un Keycloak de verdad esto NO esta probado» -- era cierta y era un hueco.

El hueco parecia cerrarse solo con credenciales de alguien: una cuenta de
Entra ID, un Keycloak de una empresa. No hace falta. Keycloak es software
libre y esta certificado por la OpenID Foundation, asi que se levanta uno aqui
y se le habla. Lo que un doble no puede dar, y esto si, es DESACUERDO: el
doble emite exactamente lo que quien lo escribio creia que emite un proveedor,
asi que esta de acuerdo con el verificador por construccion. Un Keycloak no
sabe lo que creemos.

Tres cosas aparecieron la primera vez que se corrio esto, y ninguna podia
salir del doble:

  1. `aud` no es una cadena, es una LISTA -- `["actaira", "account"]` --
     porque Keycloak mete siempre su propio `account`.
  2. `roles` no trae solo los nuestros: trae `default-roles-<reino>`,
     `offline_access` y `uma_authorization` al lado. Un verificador que
     tratara un rol desconocido como error habria rechazado a todo el mundo.
  3. `actaira_cliente` NO LLEGABA. Keycloak 26 trae el perfil declarativo con
     `unmanagedAttributePolicy` desactivada y descarta en silencio, con un
     201, cualquier atributo que no este declarado. El testigo salia
     perfectamente firmado y sin la reclamacion que dice de quien es el
     expediente.

LO QUE ESTO SIGUE SIN DEMOSTRAR
--------------------------------
Que hable con Entra ID. Entra emite `iss` con el identificador del inquilino y
una version en la ruta, pone los roles en `roles` o en `wids` segun como este
configurado, y usa `oid` y no `sub` como identificador estable de la persona.
Nada de eso se prueba aqui, y por eso no se dice. Lo que se prueba es que el
verificador aguanta un testigo que NO escribio esta casa.
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

# La imagen va clavada POR DIGEST y no por etiqueta, por lo mismo que la
# plantilla de integracion continua manda anclar las acciones: una etiqueta se
# mueve, y quien controle `latest` decide que corre dentro de esta puerta.
IMAGEN = ("quay.io/keycloak/keycloak@sha256:"
          "82a77884f3af238beab1e7afd63b5f530e1b5c0590bd7aa60b40a40463e29b2c")
VERSION_LEGIBLE = "26.7.4"

CONTENEDOR = "actaira-idp-pruebas"
REINO = "actaira"
CLIENTE_OIDC = "panel"
CLAVE = "clave-de-pruebas"

# Dos personas de dos clientes distintos, para poder probar el aislamiento con
# testigos que NO se han escrito aqui.
PERSONAS = {
    "ana": ("acme", ["lectura"]),
    "beto": ("beta", ["lectura", "observacion"]),
}


class NoSePuede(Exception):
    """No hay con que levantar el proveedor. No es un fallo del producto."""


def _peticion(metodo, url, datos=None, testigo=None, form=False, plazo=30):
    cabeceras = {}
    cuerpo = None
    if datos is not None:
        if form:
            cuerpo = urllib.parse.urlencode(datos).encode()
            cabeceras["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            cuerpo = json.dumps(datos).encode()
            cabeceras["Content-Type"] = "application/json"
    if testigo:
        cabeceras["Authorization"] = "Bearer " + testigo
    pet = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(pet, timeout=plazo) as r:
            crudo = r.read()
            return r.status, (json.loads(crudo) if crudo else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def disponible() -> str | None:
    """El motivo por el que NO se puede correr, o `None` si se puede."""
    if not shutil.which("docker"):
        return "`docker` no esta en el PATH"
    r = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        return "el demonio de docker no responde"
    return None


def _puerto_libre() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _puerto_publicado() -> int:
    """El puerto del contenedor que YA estaba, que no tiene por que ser el mio."""
    r = subprocess.run(["docker", "port", CONTENEDOR, "8080/tcp"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0 or ":" not in r.stdout:
        raise NoSePuede("hay un contenedor corriendo pero no publica el 8080")
    return int(r.stdout.strip().splitlines()[0].rsplit(":", 1)[1])


def levantar() -> tuple[str, bool]:
    """Devuelve `(base, lo_arranque_yo)`.

    Si ya hay uno corriendo se reutiliza y NO se para al salir: pararlo seria
    apagarle a alguien un contenedor que no era suyo.
    """
    motivo = disponible()
    if motivo:
        raise NoSePuede(motivo)

    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", CONTENEDOR],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    mio = not (r.returncode == 0 and r.stdout.strip() == "true")
    if mio:
        subprocess.run(["docker", "rm", "-f", CONTENEDOR],
                       capture_output=True, text=True)
        # EL PUERTO SE PIDE, NO SE CLAVA.
        #
        # Estaba clavado en 18080 y la primera vez que se corrio esto ya habia
        # algo escuchando ahi, asi que la fase se OMITIO por una colision de
        # puertos. Una puerta que se apaga porque otro proceso cogio un numero
        # antes no mide el producto, mide la suerte.
        puerto = _puerto_libre()
        r = subprocess.run(
            ["docker", "run", "-d", "--name", CONTENEDOR, "-p", f"{puerto}:8080",
             "-e", "KC_BOOTSTRAP_ADMIN_USERNAME=admin",
             "-e", "KC_BOOTSTRAP_ADMIN_PASSWORD=admin",
             IMAGEN, "start-dev"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise NoSePuede(f"no arranca el contenedor: {r.stderr.strip()[:300]}")
    else:
        puerto = _puerto_publicado()

    base = f"http://localhost:{puerto}"
    for _ in range(120):
        try:
            with urllib.request.urlopen(base + "/realms/master", timeout=2) as resp:
                if resp.status == 200:
                    return base, mio
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    raise NoSePuede("el proveedor no llego a contestar")


def parar() -> None:
    subprocess.run(["docker", "rm", "-f", CONTENEDOR], capture_output=True, text=True)


def _admin(base: str) -> str:
    _, d = _peticion("POST", f"{base}/realms/master/protocol/openid-connect/token",
                     {"client_id": "admin-cli", "username": "admin",
                      "password": "admin", "grant_type": "password"}, form=True)
    if not isinstance(d, dict):
        raise NoSePuede(f"el proveedor no da testigo de administracion: {d}")
    return d["access_token"]


def configurar(base: str) -> None:
    """Deja el reino como lo tendria un cliente que usara esto de verdad."""
    t = _admin(base)
    A = f"{base}/admin/realms"

    # Repetible: si ya estaba, se rehace. Un montaje que solo vale la primera
    # vez convierte la segunda ejecucion en otra prueba distinta.
    _peticion("DELETE", f"{A}/{REINO}", testigo=t)
    _peticion("POST", A, {"realm": REINO, "enabled": True,
                          "accessTokenLifespan": 300}, testigo=t)

    # Sin esto, `actaira_cliente` no llega: ver la cabecera de este fichero.
    _peticion("PUT", f"{A}/{REINO}/users/profile", {
        "unmanagedAttributePolicy": "ENABLED",
        "attributes": [
            {"name": "username", "permissions": {"view": ["admin", "user"],
                                                 "edit": ["admin", "user"]}},
            {"name": "email", "permissions": {"view": ["admin", "user"],
                                              "edit": ["admin", "user"]}},
        ],
    }, testigo=t)

    for papel in ("lectura", "observacion", "remediacion", "admin"):
        _peticion("POST", f"{A}/{REINO}/roles", {"name": papel}, testigo=t)

    _peticion("POST", f"{A}/{REINO}/clients", {
        "clientId": CLIENTE_OIDC, "enabled": True, "publicClient": True,
        "directAccessGrantsEnabled": True, "standardFlowEnabled": False,
        "protocolMappers": [
            {"name": "aud-actaira", "protocol": "openid-connect",
             "protocolMapper": "oidc-audience-mapper",
             "config": {"included.custom.audience": "actaira",
                        "access.token.claim": "true"}},
            {"name": "roles-planos", "protocol": "openid-connect",
             "protocolMapper": "oidc-usermodel-realm-role-mapper",
             "config": {"claim.name": "roles", "multivalued": "true",
                        "jsonType.label": "String", "access.token.claim": "true"}},
            {"name": "cliente-actaira", "protocol": "openid-connect",
             "protocolMapper": "oidc-usermodel-attribute-mapper",
             "config": {"user.attribute": "actaira_cliente",
                        "claim.name": "actaira_cliente",
                        "jsonType.label": "String", "access.token.claim": "true"}},
        ],
    }, testigo=t)

    _, todos = _peticion("GET", f"{A}/{REINO}/roles", testigo=t)
    for quien, (de_quien, papeles) in PERSONAS.items():
        _peticion("POST", f"{A}/{REINO}/users", {
            "username": quien, "enabled": True,
            # Keycloak 26 exige el perfil completo: sin correo, nombre y
            # apellido la concesion directa responde «Account is not fully set
            # up» y no emite nada.
            "email": f"{quien}@ejemplo.invalid", "emailVerified": True,
            "firstName": quien.capitalize(), "lastName": "Pruebas",
            "requiredActions": [],
            "attributes": {"actaira_cliente": [de_quien]},
            "credentials": [{"type": "password", "value": CLAVE,
                             "temporary": False}],
        }, testigo=t)
        _, lista = _peticion("GET", f"{A}/{REINO}/users?username={quien}", testigo=t)
        uid = lista[0]["id"]
        _peticion("POST", f"{A}/{REINO}/users/{uid}/role-mappings/realm",
                  [r for r in todos if r["name"] in papeles], testigo=t)


def testigo(base: str, quien: str) -> str:
    """Un testigo REAL, pedido como lo pediria una aplicacion."""
    c, d = _peticion("POST",
                     f"{base}/realms/{REINO}/protocol/openid-connect/token",
                     {"client_id": CLIENTE_OIDC, "username": quien,
                      "password": CLAVE, "grant_type": "password"}, form=True)
    if not isinstance(d, dict) or "access_token" not in d:
        raise NoSePuede(f"el proveedor no emitio testigo para {quien}: {c} {d}")
    return d["access_token"]


def reclamaciones(tok: str) -> dict:
    cue = tok.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(cue + "=" * (-len(cue) % 4)))


def cabecera(tok: str) -> dict:
    cab = tok.split(".")[0]
    return json.loads(base64.urlsafe_b64decode(cab + "=" * (-len(cab) % 4)))


def emisor(base: str) -> dict:
    """La configuracion del emisor, construida desde el JWKS PUBLICADO.

    Ninguna clave se escribe a mano: se leen del juego que publica el propio
    proveedor y se convierten a PEM, que es el formato que el servidor
    configura. Se quedan SOLO las de firma: el juego de Keycloak trae tambien
    claves de cifrado, y una clave de cifrado en la lista de las que pueden
    validar una firma es exactamente la confusion de clave que el verificador
    dice impedir.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    url = f"{base}/realms/{REINO}/protocol/openid-connect/certs"
    with urllib.request.urlopen(url, timeout=30) as r:
        juego = json.loads(r.read())

    def num(s: str) -> int:
        return int.from_bytes(
            base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)), "big")

    claves = {}
    for k in juego["keys"]:
        if k.get("use") != "sig" or k.get("kty") != "RSA":
            continue
        pub = rsa.RSAPublicNumbers(num(k["e"]), num(k["n"])).public_key()
        claves[k["kid"]] = pub.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    if not claves:
        raise NoSePuede("el juego de claves publicado no trae ninguna de firma")
    return {"iss": f"{base}/realms/{REINO}", "aud": "actaira", "claves": claves}
