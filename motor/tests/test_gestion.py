"""Fase 16: la clausula 10.2 sin el boton de cerrar.

Todas las herramientas de GRC guardan la no conformidad como una fila con un
campo `estado` que alguien cambia. Eso pierde el historial y, peor, convierte
cerrar en escribir una palabra: un `estado = "cerrada"` no distingue entre
«comprobamos que la causa dejo de producir el efecto» y «paso el tiempo y
alguien lo dio por bueno».

Estas pruebas sujetan la diferencia.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from actaira_motor.gestion import EstadoNC, Transicion, reconstruir
from actaira_motor.gestion.noconformidad import desde_el_almacen, vencidas
from actaira_motor.vigilancia.almacen import Almacen

T0 = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)


def _t(a, cuando=T0, **kw):
    base = dict(no_conformidad_id="NC-1", a=a, quien="Marta Iglesias",
                cargo="responsable de IA", cuando=cuando.isoformat())
    if a is EstadoNC.ABIERTA:
        base.update(origen="auditoria interna 2027",
                    descripcion="el registro del modelo no lleva la version")
    base.update(kw)
    return Transicion(**base)


def _nc(*transiciones):
    return reconstruir("NC-1", "auditoria interna 2027",
                       "el registro del modelo no lleva la version", list(transiciones))


# --- lo que no se puede escribir ------------------------------------------

def test_ejecutada_no_es_cerrada():
    """La clausula 10.2 pide revisar la EFICACIA de la accion correctiva.

    Haber hecho la accion no es haber cerrado, y fundir los dos convierte la
    mejora continua en una lista de tareas hechas.
    """
    assert not EstadoNC.EJECUTADA.cerrada
    assert EstadoNC.VERIFICADA.cerrada
    for e in EstadoNC:
        assert not e.afirma_cumplimiento


def test_no_se_puede_verificar_sin_evidencia_de_eficacia():
    with pytest.raises(ValueError, match="evidencia de eficacia"):
        _t(EstadoNC.VERIFICADA)


def test_ni_comprometerse_a_una_accion_sin_dueno_y_sin_fecha():
    """Una accion sin dueno y sin fecha es una intencion."""
    with pytest.raises(ValueError, match="accion, responsable y fecha"):
        _t(EstadoNC.CON_ACCION, accion="mejorar el registro")
    with pytest.raises(ValueError, match="accion, responsable y fecha"):
        _t(EstadoNC.CON_ACCION, accion="mejorar", responsable="Luis")


def test_abrir_una_no_conformidad_sin_decir_de_donde_sale_no_se_puede():
    """Sin origen y sin descripcion, lo que hay es un identificador."""
    with pytest.raises(ValueError, match="de donde salio"):
        Transicion(no_conformidad_id="NC-9", a=EstadoNC.ABIERTA, quien="M",
                   cargo="c", cuando=T0.isoformat())


def test_ni_mover_una_no_conformidad_sin_decir_quien():
    with pytest.raises(ValueError, match="no se puede auditar"):
        Transicion(no_conformidad_id="NC-1", a=EstadoNC.EN_ANALISIS, quien="  ",
                   cargo="x", cuando=T0.isoformat())


def test_el_gemelo_una_verificacion_bien_formada_si_se_escribe():
    """Si no, «exige evidencia» se cumpliria tambien no dejando verificar nunca."""
    t = _t(EstadoNC.VERIFICADA, evidencia_de_eficacia="sha256:ev-posterior")
    assert t.a is EstadoNC.VERIFICADA
    assert t.evidencia_de_eficacia == "sha256:ev-posterior"


# --- el estado se calcula, no se guarda -----------------------------------

def test_el_estado_sale_de_las_transiciones_en_orden_de_fecha():
    """Y no en orden de llegada: el almacen admite que dos pasadas escriban en
    cualquier orden, y reconstruir por llegada haria que el estado dependiera
    de cual gano la carrera."""
    nc = _nc(
        _t(EstadoNC.CON_ACCION, cuando=T0 + timedelta(days=2), accion="anadir la version",
           responsable="Luis Serra", compromiso="2028-01-15"),
        _t(EstadoNC.ABIERTA),
        _t(EstadoNC.EN_ANALISIS, cuando=T0 + timedelta(days=1),
           causa_raiz="el formateador de registro no recibia el modelo"),
    )
    assert nc.estado is EstadoNC.CON_ACCION
    assert nc.abierta_en == T0.isoformat()
    assert nc.causa_raiz.startswith("el formateador")
    assert [t.a for t in nc.transiciones] == [EstadoNC.ABIERTA, EstadoNC.EN_ANALISIS,
                                              EstadoNC.CON_ACCION]


def test_una_transicion_vieja_que_llega_tarde_no_reabre_lo_cerrado():
    """Lo contrario seria que una escritura tardia reabriera algo cerrado sin
    que nadie lo decidiera."""
    nc = _nc(
        _t(EstadoNC.ABIERTA),
        _t(EstadoNC.EN_ANALISIS, cuando=T0 + timedelta(days=1), causa_raiz="x"),
        _t(EstadoNC.CON_ACCION, cuando=T0 + timedelta(days=2), accion="a",
           responsable="r", compromiso="2028-01-15"),
        _t(EstadoNC.EJECUTADA, cuando=T0 + timedelta(days=3)),
        _t(EstadoNC.VERIFICADA, cuando=T0 + timedelta(days=30),
           evidencia_de_eficacia="sha256:ev"),
        _t(EstadoNC.EN_ANALISIS, cuando=T0 + timedelta(days=40), causa_raiz="llega tarde"),
    )
    assert nc.estado is EstadoNC.VERIFICADA


def test_una_no_conformidad_sin_transiciones_no_existe():
    with pytest.raises(ValueError, match="sin ninguna transicion"):
        reconstruir("NC-9", "x", "y", [])


# --- lo vencido, que es lo que encuentra un auditor -----------------------

def test_ejecutada_y_sin_verificar_pasada_la_fecha_esta_vencida():
    """La que lleva cuatro meses «ejecutada» sin que nadie comprobara nada es
    justo la que un auditor encuentra."""
    nc = _nc(
        _t(EstadoNC.ABIERTA),
        _t(EstadoNC.CON_ACCION, cuando=T0 + timedelta(days=1), accion="a",
           responsable="r", compromiso="2027-12-20"),
        _t(EstadoNC.EJECUTADA, cuando=T0 + timedelta(days=5)),
    )
    assert nc.estado is EstadoNC.EJECUTADA
    assert nc.vencida(datetime(2028, 4, 1, tzinfo=timezone.utc))
    assert vencidas([nc], datetime(2028, 4, 1, tzinfo=timezone.utc)) == [nc]


def test_el_gemelo_verificada_ya_no_vence():
    nc = _nc(
        _t(EstadoNC.ABIERTA),
        _t(EstadoNC.CON_ACCION, cuando=T0 + timedelta(days=1), accion="a",
           responsable="r", compromiso="2027-12-20"),
        _t(EstadoNC.VERIFICADA, cuando=T0 + timedelta(days=10),
           evidencia_de_eficacia="sha256:ev"),
    )
    assert not nc.vencida(datetime(2028, 4, 1, tzinfo=timezone.utc))
    assert nc.dias_abierta(datetime(2028, 4, 1, tzinfo=timezone.utc)) == 10


# --- y va al MISMO almacen que la evidencia tecnica -----------------------

def test_las_transiciones_viven_en_el_almacen_encadenado(tmp_path):
    """No hay un segundo mecanismo de almacenamiento para la gestion.

    La cadena de sellos, la frescura y la invalidacion por digest valen igual
    para un cambio de estado de una no conformidad que para una lectura de
    bytes. Dos almacenes habrian sido dos maneras de perder lo mismo.
    """
    ruta = tmp_path / "ev.jsonl"
    alm = Almacen.abrir(ruta)
    ts = [_t(EstadoNC.ABIERTA),
          _t(EstadoNC.EN_ANALISIS, cuando=T0 + timedelta(days=1), causa_raiz="c"),
          _t(EstadoNC.CON_ACCION, cuando=T0 + timedelta(days=2), accion="a",
             responsable="r", compromiso="2028-01-15")]
    alm.anadir([t.a_registro() for t in ts], T0)

    assert Almacen.abrir(ruta).verificar_cadena() == []
    nc = desde_el_almacen(Almacen.abrir(ruta), "NC-1")
    assert nc.origen == "auditoria interna 2027", "el origen sale de su propia apertura"
    assert nc.estado is EstadoNC.CON_ACCION
    assert nc.responsable == "r"


def test_y_editar_una_transicion_a_mano_rompe_la_cadena(tmp_path):
    """El gemelo que importa: cerrar una no conformidad editando el fichero."""
    import json as _json

    ruta = tmp_path / "ev.jsonl"
    Almacen.abrir(ruta).anadir([_t(EstadoNC.ABIERTA).a_registro()], T0)
    lineas = [_json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]
    lineas[0]["registro"]["contenido"]["a"] = "verificada"
    ruta.write_text("".join(_json.dumps(l, ensure_ascii=False, sort_keys=True) + "\n"
                            for l in lineas), encoding="utf-8")
    assert Almacen.abrir(ruta).verificar_cadena(), "editar el estado tiene que verse"


# --- la revision por la direccion: la carpeta, no el acta ------------------

def _cat():
    from actaira_motor.catalogo.cargador import cargar
    return cargar("catalogo")


def _registro(control, cuando=T0, frescura=365, contenido=None):
    from actaira_motor.evidencia.registro import Registro
    return Registro.nuevo("ISO", control, f"c:{control}", cuando,
                          contenido or {"x": control}, frescura)


def test_la_revision_dice_que_entrada_de_la_norma_falta():
    """Casi nadie falla la 9.3 por no hacer la revision: falla porque el acta
    no cubre las entradas que la norma enumera, y eso solo se ve comparando."""
    from actaira_motor.expediente.revision import ENTRADAS, generar

    doc = generar(_cat(), [], T0)
    assert doc["recuento"]["ausente"] == len(ENTRADAS)
    assert doc["recuento"]["aportada"] == 0
    assert len(doc["que_falta"]) == len(ENTRADAS)
    assert all(f["situacion"] == "ausente" for f in doc["entradas"])


def test_y_la_que_esta_aportada_dice_en_que_se_apoya():
    from actaira_motor.expediente.revision import generar

    regs = [_registro("ISO-9.1"), _registro("ISO-10.2"), _registro("ISO-6.2")]
    doc = generar(_cat(), regs, T0 + timedelta(days=5))
    aportadas = {f["entrada"] for f in doc["entradas"] if f["situacion"] == "aportada"}
    assert {"seguimiento_y_medicion", "no_conformidades_y_acciones",
            "cumplimiento_de_objetivos"} <= aportadas
    for f in doc["entradas"]:
        if f["situacion"] == "aportada":
            assert f["se_apoya_en"] and f["se_apoya_en"][0]["evidencia"].startswith("sha256:")


def test_caducada_no_es_lo_mismo_que_ausente():
    """«Nadie ha mirado ultimamente» y «nunca se miro» no se arreglan igual.

    Fundirlas seria el mismo error que el modulo de evidencia persigue desde la
    fase 8, cometido en la capa de gestion.
    """
    from actaira_motor.expediente.revision import generar

    regs = [_registro("ISO-9.1", frescura=30)]
    doc = generar(_cat(), regs, T0 + timedelta(days=400))
    fila = next(f for f in doc["entradas"] if f["entrada"] == "seguimiento_y_medicion")
    assert fila["situacion"] == "caducada"
    assert fila["caducado"] and fila["caducado"][0]["estado"] == "rancia"
    assert doc["recuento"]["caducada"] >= 1
    otra = next(f for f in doc["entradas"] if f["entrada"] == "resultados_de_auditoria")
    assert otra["situacion"] == "ausente"


def test_la_revision_no_concluye_nada():
    """La salida de la 9.3.3 la firma la direccion. Aqui no hay veredicto."""
    from actaira_motor.expediente.revision import generar

    doc = generar(_cat(), [_registro("ISO-9.1")], T0)
    plano = str(doc).lower()
    assert "cumple" not in plano
    assert "%" not in str(doc["recuento"])
    assert doc["no_es_un_acta"]["es"] and doc["no_es_un_acta"]["en"]


def test_la_revision_se_lee_en_los_dos_idiomas():
    from actaira_motor.expediente.revision import a_markdown, generar

    doc = generar(_cat(), [_registro("ISO-9.2.2")], T0)
    es, en = a_markdown(doc, "es"), a_markdown(doc, "en")
    assert "Revisión por la dirección" in es and "Management review" in en
    assert es != en
    assert "auditorías internas" in es and "internal audit results" in en


def test_las_no_conformidades_abiertas_entran_en_la_carpeta():
    """Es una de las entradas que la norma enumera, y la que mas se olvida."""
    from actaira_motor.expediente.revision import a_markdown, generar

    nc = _nc(_t(EstadoNC.ABIERTA),
             _t(EstadoNC.CON_ACCION, cuando=T0 + timedelta(days=1), accion="a",
                responsable="r", compromiso="2028-01-15"))
    doc = generar(_cat(), [], T0, no_conformidades=[nc])
    assert doc["no_conformidades"][0]["estado"] == "con_accion"
    assert "NC-1" in a_markdown(doc, "es")


# --- la clausula 10.2 desde la linea de mandatos ---------------------------

import os
import subprocess
import sys
from pathlib import Path as _P

RAIZ = _P(__file__).resolve().parents[2]
ENT = {**os.environ, "PYTHONPATH": str(RAIZ / "motor" / "src"), "PYTHONIOENCODING": "utf-8"}


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "actaira_motor.cli", *args],
                          cwd=RAIZ, env=ENT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_el_verbo_se_niega_a_cerrar_sin_evidencia_de_eficacia(tmp_path):
    """Es la unica manera que conozco de que un ciclo de mejora no se convierta
    en una lista de tareas hechas: que cerrar cueste aportar algo posterior."""
    alm = str(tmp_path / "ev.jsonl")
    assert _cli("noconformidad", "abrir", "--id", "NC-1", "--almacen", alm,
                "--quien", "Marta", "--cargo", "resp", "--origen", "auditoria",
                "--descripcion", "el registro no lleva la version").returncode == 0

    sin = _cli("noconformidad", "avanzar", "--id", "NC-1", "--a", "verificada",
               "--almacen", alm, "--quien", "Marta", "--cargo", "resp")
    assert sin.returncode == 4
    assert "evidencia de eficacia" in sin.stderr

    con = _cli("noconformidad", "avanzar", "--id", "NC-1", "--a", "verificada",
               "--almacen", alm, "--quien", "Marta", "--cargo", "resp",
               "--evidencia-de-eficacia", "sha256:ev")
    assert con.returncode == 0, con.stderr


def test_listar_saca_con_uno_cuando_hay_alguna_vencida(tmp_path):
    """Un cron que lista no conformidades quiere enterarse de las vencidas por
    el codigo de salida, no leyendo la tabla."""
    alm = str(tmp_path / "ev.jsonl")
    _cli("noconformidad", "abrir", "--id", "NC-2", "--almacen", alm,
         "--quien", "M", "--cargo", "r", "--origen", "auditoria",
         "--descripcion", "x", "--ahora", "2027-01-02T10:00:00+00:00")
    _cli("noconformidad", "avanzar", "--id", "NC-2", "--a", "con_accion", "--almacen", alm,
         "--quien", "M", "--cargo", "r", "--accion-correctiva", "a", "--responsable", "r",
         "--compromiso", "2027-02-01", "--ahora", "2027-01-03T10:00:00+00:00")

    tarde = _cli("noconformidad", "listar", "--almacen", alm, "--ahora", "2028-01-01T10:00:00+00:00")
    assert tarde.returncode == 1 and "VENCIDA" in tarde.stdout

    pronto = _cli("noconformidad", "listar", "--almacen", alm, "--ahora", "2027-01-10T10:00:00+00:00")
    assert pronto.returncode == 0 and "VENCIDA" not in pronto.stdout


def test_la_revision_lee_las_no_conformidades_del_mismo_almacen(tmp_path):
    """El ciclo cierra tambien en el producto, no solo en el catalogo: lo que
    la 10.2 produce lo consume la 9.3.2 sin que nadie lo copie a mano."""
    alm = str(tmp_path / "ev.jsonl")
    _cli("noconformidad", "abrir", "--id", "NC-3", "--almacen", alm,
         "--quien", "M", "--cargo", "r", "--origen", "reclamacion",
         "--descripcion", "una persona pidio explicaciones y no habia ruta")
    r = _cli("revision", "--almacen", alm, "--json")
    doc = __import__("json").loads(r.stdout)
    assert doc["no_conformidades"] and doc["no_conformidades"][0]["id"] == "NC-3"
    fila = next(f for f in doc["entradas"] if f["entrada"] == "no_conformidades_y_acciones")
    assert fila["situacion"] == "aportada", "la apertura de la NC es evidencia de la 10.2"


# --- la pasada adversarial de la fase 16 ----------------------------------

def test_adv_verificar_sin_haber_ejecutado_nada_se_ve():
    """El constructor solo mira UNA transicion. Esto mira la historia entera."""
    nc = _nc(_t(EstadoNC.ABIERTA),
             _t(EstadoNC.EN_ANALISIS, cuando=T0 + timedelta(days=1), causa_raiz="c"),
             _t(EstadoNC.CON_ACCION, cuando=T0 + timedelta(days=2), accion="a",
                responsable="r", compromiso="2028-01-15"),
             _t(EstadoNC.VERIFICADA, cuando=T0 + timedelta(days=3),
                evidencia_de_eficacia="sha256:ev"))
    problemas = nc.incoherencias()
    assert any("sin que conste ninguna ejecucion" in p for p in problemas), problemas


def test_adv_verificar_sin_causa_raiz_es_cerrar_el_sintoma():
    """La clausula 10.2 pide corregir Y eliminar la causa."""
    nc = _nc(_t(EstadoNC.ABIERTA),
             _t(EstadoNC.EJECUTADA, cuando=T0 + timedelta(days=1)),
             _t(EstadoNC.VERIFICADA, cuando=T0 + timedelta(days=2),
                evidencia_de_eficacia="sha256:ev"))
    assert any("sin causa raiz" in p for p in nc.incoherencias())


def test_adv_una_verificacion_anterior_a_la_ejecucion_se_ve():
    """Eso no es revisar si funciono: es haber mirado antes de hacerlo."""
    nc = _nc(_t(EstadoNC.ABIERTA),
             _t(EstadoNC.EN_ANALISIS, cuando=T0 + timedelta(days=1), causa_raiz="c"),
             _t(EstadoNC.CON_ACCION, cuando=T0 + timedelta(days=2), accion="a",
                responsable="r", compromiso="2028-01-15"),
             _t(EstadoNC.VERIFICADA, cuando=T0 + timedelta(days=3),
                evidencia_de_eficacia="sha256:ev"),
             _t(EstadoNC.EJECUTADA, cuando=T0 + timedelta(days=9)))
    assert any("anterior a la ejecucion" in p for p in nc.incoherencias())


def test_adv_el_gemelo_una_historia_coherente_no_se_queja():
    """Si no, «detecta incoherencias» se cumpliria quejandose siempre."""
    nc = _nc(_t(EstadoNC.ABIERTA),
             _t(EstadoNC.EN_ANALISIS, cuando=T0 + timedelta(days=1), causa_raiz="c"),
             _t(EstadoNC.CON_ACCION, cuando=T0 + timedelta(days=2), accion="a",
                responsable="r", compromiso="2028-01-15"),
             _t(EstadoNC.EJECUTADA, cuando=T0 + timedelta(days=5)),
             _t(EstadoNC.VERIFICADA, cuando=T0 + timedelta(days=40),
                evidencia_de_eficacia="sha256:ev"))
    assert nc.incoherencias() == []
    assert nc.estado.cerrada


def test_adv_no_comprometerse_a_nada_no_puede_salir_gratis():
    """`vencida` no ve una no conformidad sin fecha comprometida: sin fecha no
    hay nada que pasar. Era el agujero mas comodo de todos, porque premiaba no
    comprometerse."""
    from actaira_motor.gestion.noconformidad import desatendidas

    nc = _nc(_t(EstadoNC.ABIERTA))
    dentro_de_un_ano = T0 + timedelta(days=365)
    assert not nc.vencida(dentro_de_un_ano), "sin compromiso no hay fecha que pasar"
    assert nc.estancada(dentro_de_un_ano)
    assert desatendidas([nc], dentro_de_un_ano) == [nc]


def test_adv_y_el_gemelo_recien_abierta_no_esta_estancada():
    nc = _nc(_t(EstadoNC.ABIERTA))
    assert not nc.estancada(T0 + timedelta(days=5))
    assert not nc.estancada(T0 + timedelta(days=89))
    assert nc.estancada(T0 + timedelta(days=91))
