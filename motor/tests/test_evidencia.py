"""Los cinco estados y el sello. El foso, y lo que lo sujeta."""
from datetime import datetime, timedelta, timezone
from actaira_motor.evidencia.registro import Registro, Estado, canonico
from actaira_motor.evidencia.sello import (sellar, verificar, raiz_merkle,
                                           prueba_de_inclusion, verificar_inclusion)

AHORA = datetime(2026, 9, 20, tzinfo=timezone.utc)
SUJ = "sha256:" + "a" * 64


def _reg(**kw):
    return Registro.nuevo("AIA-050", "ACT-C-50", SUJ, AHORA, {"x": 1}, **kw)


def test_solo_valida_cuenta():
    assert Estado.VALIDA.cuenta
    assert not any(e.cuenta for e in Estado if e is not Estado.VALIDA)


def test_la_supera_el_digest_y_no_el_nombre():
    r = _reg()
    assert r.estado(AHORA, digest_actual_del_sujeto=SUJ)[0] is Estado.VALIDA
    assert r.estado(AHORA, digest_actual_del_sujeto="sha256:" + "b" * 64)[0] is Estado.SUPERADA


def test_rancia_y_superada_no_se_funden():
    r = _reg(frescura_dias=30)
    assert r.estado(AHORA + timedelta(days=40))[0] is Estado.RANCIA
    assert r.estado(AHORA, digest_actual_del_sujeto="sha256:" + "c" * 64)[0] is Estado.SUPERADA


def test_revocada_gana_a_rancia_porque_reobservar_no_arreglaria_nada():
    r = _reg(frescura_dias=1)
    e, _ = r.estado(AHORA + timedelta(days=9), revocadas=frozenset({r.id}))
    assert e is Estado.REVOCADA


def test_todo_estado_distinto_de_valida_trae_motivo_escrito():
    r = _reg(frescura_dias=1)
    for kw in ({"digest_actual_del_sujeto": "sha256:" + "d" * 64},
               {"revocadas": frozenset({r.id})},
               {"confiables": frozenset({"OTRO"})}):
        e, m = r.estado(AHORA + timedelta(days=9), **kw)
        assert e is not Estado.VALIDA
        # Y el motivo va en los dos idiomas, desde la fase 12. Antes era una
        # cadena en castellano que acababa impresa tal cual en el `detalle` de
        # un documento pedido en ingles.
        assert set(m) == {"es", "en"} and m["es"].strip() and m["en"].strip()


def test_el_sello_firmado_verifica_sin_red_contra_la_clave_esperada():
    """Cambiado por D-3: sin clave esperada no basta, y eso es lo correcto."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                          serialization.NoEncryption())
    s = sellar([_reg(), _reg(frescura_dias=5)], AHORA, pem).a_json()
    ok, motivos = verificar(s, clave_esperada=s["clave_publica"])
    assert ok and motivos == []


def test_un_sello_manipulado_no_verifica():
    s = sellar([_reg(), _reg(frescura_dias=5)], AHORA).a_json()
    s["registros"][0]["contenido"] = {"x": 999}
    ok, motivos = verificar(s)
    assert not ok and "la raiz no reproduce" in motivos[0]


def test_un_sello_sin_firma_no_pasa_como_valido():
    """Integridad no es identidad. Regla 11: no caer al extremo seguro."""
    ok, motivos = verificar(sellar([_reg()], AHORA).a_json())
    assert not ok and "identidad no" in motivos[0]


def test_la_separacion_de_dominio_muerde():
    """El gemelo: sin prefijos de dominio, hoja y nodo colisionan."""
    import hashlib
    a, b = b"uno", b"dos"
    con = raiz_merkle([a, b])
    sin = hashlib.sha256(hashlib.sha256(a).digest() + hashlib.sha256(b).digest()).digest()
    assert con != sin


def test_se_prueba_una_evidencia_sin_ensenar_las_demas():
    regs = [_reg() for _ in range(7)]
    hojas = [canonico(r.a_json()) for r in regs]
    raiz = raiz_merkle(hojas)
    for i in (0, 3, 6):
        assert verificar_inclusion(hojas[i], prueba_de_inclusion(hojas, i), raiz)
    assert not verificar_inclusion(b"inventada", prueba_de_inclusion(hojas, 3), raiz)


def test_una_firma_con_clave_cualquiera_no_establece_identidad():
    """D-3 de la pasada adversarial: verificaba en silencio."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                          serialization.NoEncryption())
    s = sellar([_reg()], AHORA, pem).a_json()
    ok, motivos = verificar(s)
    assert not ok and "no quien es" in motivos[0]
    ok2, motivos2 = verificar(s, clave_esperada=s["clave_publica"])
    assert ok2 and motivos2 == []
    ok3, motivos3 = verificar(s, clave_esperada="00" * 32)
    assert not ok3 and "no es la esperada" in motivos3[0]
