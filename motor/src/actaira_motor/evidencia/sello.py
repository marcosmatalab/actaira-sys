"""El expediente sellado, y su verificacion sin red ni confianza en quien lo emitio.

PORTADO en diseno de actaira v3.0.0 `attest/`: arbol de Merkle RFC 6962 con
separacion de dominio, y firma Ed25519 sobre la raiz.

POR QUE MERKLE Y NO UN HASH DE TODO JUNTO
------------------------------------------
Un hash del expediente entero demuestra que nada cambio, y obliga a entregar el
expediente entero para demostrar una sola cosa. Con Merkle, un tercero puede
verificar UNA evidencia concreta con su prueba de inclusion, sin ver las demas.
Para un auditor que pregunta por el articulo 50 y no tiene por que ver el resto
del expediente del cliente, esa diferencia lo es todo.

LA SEPARACION DE DOMINIO NO ES DECORACION
------------------------------------------
Las hojas se hashean con prefijo 0x00 y los nodos internos con 0x01, que es el
RFC 6962. Sin eso, un atacante puede presentar un nodo interno como si fuera
una hoja y viceversa. La version 2.3.0 de actaira tenia una colision real por
concatenar con `|` sin prefijos de longitud, se arreglo en la 3.0.0 y el test
que la fija reintroduce el hash viejo a proposito para comprobar que muerde.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registro import Registro, canonico

ESQUEMA_SELLO = "actaira/sello/v1"


def _hoja(b: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + b).digest()


def _nodo(izq: bytes, der: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + izq + der).digest()


def raiz_merkle(hojas: list[bytes]) -> bytes:
    if not hojas:
        return hashlib.sha256(b"").digest()
    nivel = [_hoja(h) for h in hojas]
    while len(nivel) > 1:
        siguiente = []
        for i in range(0, len(nivel) - 1, 2):
            siguiente.append(_nodo(nivel[i], nivel[i + 1]))
        if len(nivel) % 2:
            siguiente.append(nivel[-1])
        nivel = siguiente
    return nivel[0]


def prueba_de_inclusion(hojas: list[bytes], indice: int) -> list[tuple[str, str]]:
    nivel = [_hoja(h) for h in hojas]
    camino: list[tuple[str, str]] = []
    i = indice
    while len(nivel) > 1:
        siguiente = []
        for j in range(0, len(nivel) - 1, 2):
            if j == i - (i % 2):
                camino.append(("der", nivel[j + 1].hex()) if i % 2 == 0 else ("izq", nivel[j].hex()))
            siguiente.append(_nodo(nivel[j], nivel[j + 1]))
        if len(nivel) % 2:
            siguiente.append(nivel[-1])
            if i == len(nivel) - 1:
                i = len(siguiente) - 1
                nivel = siguiente
                continue
        i //= 2
        nivel = siguiente
    return camino


def verificar_inclusion(hoja: bytes, camino: list[tuple[str, str]], raiz: bytes) -> bool:
    actual = _hoja(hoja)
    for lado, hermano in camino:
        h = bytes.fromhex(hermano)
        actual = _nodo(h, actual) if lado == "izq" else _nodo(actual, h)
    return actual == raiz


@dataclass
class Sello:
    emitido_en: str
    raiz: str
    registros: list[dict[str, Any]]
    firma: str | None = None
    clave_publica: str | None = None

    def a_json(self) -> dict[str, Any]:
        return {
            "esquema": ESQUEMA_SELLO, "emitido_en": self.emitido_en, "raiz": self.raiz,
            "registros": self.registros, "firma": self.firma, "clave_publica": self.clave_publica,
        }


def sellar(registros: list[Registro], cuando: datetime, clave_privada_pem: bytes | None = None) -> Sello:
    hojas = [canonico(r.a_json()) for r in registros]
    raiz = raiz_merkle(hojas)
    sello = Sello(
        emitido_en=cuando.astimezone(timezone.utc).isoformat(),
        raiz="sha256:" + raiz.hex(),
        registros=[r.a_json() for r in registros],
    )
    if clave_privada_pem:
        from cryptography.hazmat.primitives import serialization
        k = serialization.load_pem_private_key(clave_privada_pem, password=None)
        # Se firma sobre el JSON canonico de la cabecera, no sobre la raiz suelta:
        # una firma sobre 32 bytes pelados no ata la fecha ni el esquema, y esa
        # fue una de las dos deudas criptograficas que arrastraba la 2.3.0.
        cabecera = {"esquema": ESQUEMA_SELLO, "emitido_en": sello.emitido_en, "raiz": sello.raiz}
        sello.firma = k.sign(b"actaira/sello/v1\x00" + canonico(cabecera)).hex()
        sello.clave_publica = k.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw).hex()
    return sello


def verificar(sello_json: dict[str, Any], clave_esperada: str | None = None) -> tuple[bool, list[str]]:
    """Verifica sin red y sin confiar en quien lo emitio. Devuelve (ok, motivos).

    Nunca devuelve True con una lista de avisos: si algo no se pudo comprobar,
    eso es un motivo y el resultado es False. Regla 11, no caer al extremo
    seguro.

    `clave_esperada` no es opcional por comodidad, y la pasada adversarial de
    la fase 2 es la razon: sin ella, un sello firmado por CUALQUIER clave
    verificaba y la funcion no decia nada, porque la firma se comprueba contra
    la clave publica que viaja DENTRO del propio sello. Eso demuestra que quien
    tuviera esa clave lo firmo, no QUIEN es. Integridad no es identidad, es la
    separacion D-170 de actaira, y ahora se publica como motivo en vez de
    quedar implicita.
    """
    motivos: list[str] = []
    if sello_json.get("esquema") != ESQUEMA_SELLO:
        return False, [f"esquema desconocido: {sello_json.get('esquema')!r}"]

    # LO QUE LA FIRMA NO CUBRE NO PUEDE VIAJAR DENTRO DE UN SELLO.
    #
    # La firma cubre la cabecera -- esquema, fecha y raiz -- y la raiz cubre los
    # registros. Todo lo demas que aparezca en este documento esta SIN FIRMAR, y
    # hasta ahora se aceptaba en silencio: anadirle a un sello valido un campo
    # `"estado": "conforme"` o `"vigencia": "2030-01-01"` lo dejaba verificando,
    # porque ninguno de los dos entra en lo que se comprueba.
    #
    # Eso no es un defecto teorico. Un sello es lo que un cliente le ensena a un
    # auditor, y lo que un consumidor de aguas abajo lee para decidir. Un campo
    # inventado dentro de un documento que la herramienta acaba de declarar
    # VERIFICADO hereda toda la autoridad del sello sin haber pasado por la
    # firma. Es la forma mas barata de blanquear una afirmacion: no hay que
    # romper Ed25519, basta con escribir al lado.
    #
    # Asi que se rechaza. No se avisa: se rechaza. Un verificador que devuelve
    # cierto sobre un documento que contiene cosas que no ha mirado esta
    # afirmando de mas, y afirmar de mas es lo que este modulo existe para no
    # hacer. Si manana el esquema gana un campo, se anade aqui y el sello sube
    # de version; que es exactamente la friccion que debe tener.
    CONOCIDOS = {"esquema", "emitido_en", "raiz", "registros", "firma", "clave_publica"}
    sobrantes = sorted(set(sello_json) - CONOCIDOS)
    if sobrantes:
        motivos.append(
            f"el sello trae campos que la firma no cubre: {sobrantes}. Lo que no esta "
            f"firmado no puede viajar dentro de un documento sellado, porque heredaria "
            f"su autoridad sin haber pasado por la firma")

    hojas = [canonico(r) for r in sello_json["registros"]]
    raiz = "sha256:" + raiz_merkle(hojas).hex()
    if raiz != sello_json["raiz"]:
        motivos.append(f"la raiz no reproduce: el sello dice {sello_json['raiz'][:24]}... y los registros dan {raiz[:24]}...")
    if sello_json.get("firma"):
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(sello_json["clave_publica"]))
            cabecera = {"esquema": ESQUEMA_SELLO, "emitido_en": sello_json["emitido_en"], "raiz": sello_json["raiz"]}
            pk.verify(bytes.fromhex(sello_json["firma"]), b"actaira/sello/v1\x00" + canonico(cabecera))
        except Exception as e:
            motivos.append(f"la firma no verifica: {type(e).__name__}")
        if clave_esperada is None:
            motivos.append(
                "la firma verifica contra la clave que viaja dentro del sello: "
                "eso prueba que quien tenga esa clave lo firmo, no quien es. "
                "Pasa `clave_esperada` con la clave publica que esperas para "
                "establecer identidad.")
        elif clave_esperada != sello_json.get("clave_publica"):
            motivos.append(
                f"la clave que firma no es la esperada: se esperaba "
                f"{clave_esperada[:16]}... y firma {str(sello_json.get('clave_publica'))[:16]}...")
    else:
        motivos.append("el sello no lleva firma: integridad si, identidad no")
    return (not motivos), motivos
