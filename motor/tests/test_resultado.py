"""Fase 14: las cinco capas, y que ninguna pueda hacer el trabajo de otra.

La primera auditoria encontro un falso «cumple». La segunda pregunto algo mas
incomodo: si el modelo de datos permite que vuelva a pasar. Permitia. Un solo
enumerado contenia un hecho de ejecucion (ERROR), uno de aplicabilidad
(NO_APLICA), dos observaciones y un juicio de suficiencia (INDETERMINADO), y
cualquier codigo que comparara ese enumerado podia tratarlos como grados de lo
mismo.

Estas pruebas sujetan la separacion. No comprueban que el motor acierte:
comprueban que no PUEDA confundir una capa con otra.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from actaira_motor.controles.modelo import (Hallazgo, Resultado, ResultadoControl,
                                            proyectar)
from actaira_motor.controles.motor import Arbol, Paquete, correr_paquete
from actaira_motor.resultado import (Decision, Ejecucion, EstadoEjecucion,
                                     EstadoSuficiencia, Falta, Observacion,
                                     Senal, Suficiencia)
from actaira_motor.resultado.decision import digest_de_suficiencias
from actaira_motor.resultado.ejecucion import Sujeto
from actaira_motor.resultado.observacion import Limite

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "motor" / "tests" / "fixtures" / "clasificador-candidatos"


def _ejecucion(**kw):
    base = dict(analizador="prueba", analizador_version="1.0.0", paquete="p",
                paquete_version="1.0.0",
                sujeto=Sujeto("repositorio", "/tmp/x", "sha256:aaa"),
                empezo="2027-12-02T10:00:00+00:00", termino="2027-12-02T10:00:01+00:00",
                estado=EstadoEjecucion.COMPLETADA, leidos=("a.py",))
    base.update(kw)
    return Ejecucion(**base)


def _observacion(**kw):
    base = dict(ejecucion_id="sha256:bbb", control_id="ACT-C-009",
                limites=(Limite({"es": "nada mas", "en": "nothing else"},
                                "fuera_del_alcance_de_la_regla"),))
    base.update(kw)
    return Observacion(**base)


# --- capa 1: la ejecucion --------------------------------------------------

def test_una_ejecucion_rota_no_puede_callarse_por_que():
    with pytest.raises(ValueError, match="sin motivo"):
        _ejecucion(estado=EstadoEjecucion.FALLIDA)


def test_y_una_completada_que_no_leyo_nada_no_es_una_completada():
    """El gemelo: «corrio bien y no vio nada» es indistinguible de no correr."""
    with pytest.raises(ValueError, match="no miro nada"):
        _ejecucion(leidos=(), ilegibles=())


def test_solo_una_ejecucion_completada_produce_observacion():
    assert EstadoEjecucion.COMPLETADA.hay_observacion
    assert not EstadoEjecucion.FALLIDA.hay_observacion
    assert not EstadoEjecucion.NO_APLICABLE.hay_observacion


def test_el_identificador_de_una_ejecucion_no_cambia_con_el_reloj():
    """Si cambiara, la reproducibilidad no se podria comprobar nunca.

    La version anterior de este test variaba SOLO `termino`, que ya estaba
    fuera del cuerpo, y por eso pasaba mientras el identificador cambiaba con
    `empezo` en cada pasada. El nombre prometia la propiedad general y la
    prueba medía un caso que no la tocaba: regla 12. Aqui se varian los DOS
    relojes, que es lo que el nombre dice.
    """
    a = _ejecucion(empezo="2027-12-02T10:00:00+00:00",
                   termino="2027-12-02T10:00:01+00:00")
    b = _ejecucion(empezo="2027-12-02T23:00:00+00:00",
                   termino="2027-12-02T23:59:59+00:00")
    assert a.id == b.id
    assert a.reproducible_como(b)


def test_y_el_identificador_y_la_reproducibilidad_no_pueden_discrepar():
    """Regla 10: dos definiciones de la misma propiedad, o comparten origen o
    se anulan. Discrepaban -- `reproducible_como` decia que si y los
    identificadores decian que no -- y eso es peor que olvidarse de
    actualizar una, porque las dos contestaban a la misma pregunta.
    """
    casos = [
        (_ejecucion(), _ejecucion()),
        (_ejecucion(empezo="2027-01-01T00:00:00+00:00"), _ejecucion()),
        (_ejecucion(), _ejecucion(analizador_version="2.0.0")),
        (_ejecucion(), _ejecucion(sujeto=Sujeto("repositorio", "/tmp/x", "sha256:otro"))),
        (_ejecucion(), _ejecucion(leidos=("otro.py",))),
    ]
    for a, b in casos:
        assert (a.id == b.id) == a.reproducible_como(b), (a.id, b.id)


def test_pero_si_cambia_con_el_sujeto():
    """El gemelo: dos arboles distintos no pueden dar la misma ejecucion."""
    a = _ejecucion()
    b = _ejecucion(sujeto=Sujeto("repositorio", "/tmp/x", "sha256:ccc"))
    assert a.id != b.id and not a.reproducible_como(b)


def test_y_cambia_con_la_version_del_analizador():
    """Tambien: la misma observacion con otro motor no es la misma evidencia."""
    assert _ejecucion().id != _ejecucion(analizador_version="2.0.0").id


# --- capa 2: la observacion ------------------------------------------------

def test_una_observacion_no_tiene_donde_escribir_un_veredicto():
    campos = set(Observacion.__dataclass_fields__)
    assert campos == {"ejecucion_id", "control_id", "hallazgos", "senales", "limites"}, campos
    assert "resultado" not in campos and "estado" not in campos


def test_una_observacion_sin_limites_afirma_haberlo_mirado_todo():
    with pytest.raises(ValueError, match="mirado todo"):
        Observacion(ejecucion_id="sha256:b", control_id="ACT-C-009")


def test_un_limite_sin_motivo_conocido_no_se_traga():
    with pytest.raises(ValueError, match="motivo de limite"):
        Limite({"es": "x", "en": "x"}, "porque si")


def test_la_prosa_del_informe_sale_de_las_senales_y_no_al_reves():
    """Regla 10: una fuente, dos vistas. Antes eran dos textos escritos a mano."""
    s = Senal("ACT-09-UMBRAL", "1.0.0", "actaira/art09",
              {"es": "un fichero de criterios", "en": "a criteria file"}, "riesgos.md")
    o = _observacion(senales=(s,))
    mirado_es, fuera_es = o.frases("es")
    mirado_en, fuera_en = o.frases("en")
    assert mirado_es == ("ACT-09-UMBRAL: un fichero de criterios -> riesgos.md",)
    assert mirado_en == ("ACT-09-UMBRAL: a criteria file -> riesgos.md",)
    assert fuera_es == ("nada mas",) and fuera_en == ("nothing else",)


def test_una_senal_en_un_solo_idioma_no_entra():
    with pytest.raises(ValueError, match="dos idiomas"):
        Senal("R", "1.0.0", "p", {"es": "solo castellano"}, "x.py")


# --- la proyeccion: el enumerado de siempre, derivado ----------------------

def test_la_proyeccion_distingue_roto_de_limpio():
    roto = _ejecucion(estado=EstadoEjecucion.FALLIDA,
                      motivo={"es": "se rompio", "en": "it broke"})
    limpio = _ejecucion()
    o = _observacion()
    assert proyectar(roto, o) is Resultado.ERROR
    assert proyectar(limpio, o) is Resultado.SIN_HALLAZGOS


def test_y_distingue_no_le_tocaba_mirar_de_miro_y_no_habia_nada():
    no_tocaba = _ejecucion(estado=EstadoEjecucion.NO_APLICABLE,
                           motivo={"es": "ninguna regla aplicaba", "en": "no rule applied"})
    assert proyectar(no_tocaba, _observacion()) is Resultado.NO_APLICA
    assert proyectar(_ejecucion(), _observacion()) is Resultado.SIN_HALLAZGOS


def test_una_vista_derivada_no_puede_discrepar_de_su_fuente():
    """El corazon de la regla 10 puesto en el constructor.

    Si alguien construye el resultado a mano con un valor que las capas no
    proyectan, revienta. Sin esto, la proyeccion seria una sugerencia.
    """
    with pytest.raises(ValueError, match="proyectan"):
        ResultadoControl(
            control_id="ACT-C-009", obligacion_id="AIA-009",
            resultado=Resultado.SIN_HALLAZGOS,
            cubre=("algo",), no_cubre=("algo",),
            ejecucion=_ejecucion(estado=EstadoEjecucion.FALLIDA,
                                 motivo={"es": "roto", "en": "broken"}),
            observacion=_observacion())


def test_el_gemelo_cuando_coinciden_se_construye_sin_quejarse():
    r = ResultadoControl.de(_ejecucion(), _observacion(), obligacion_id="AIA-009")
    assert r.resultado is Resultado.SIN_HALLAZGOS
    assert r.ejecucion is not None and r.observacion is not None


# --- capa 4: la suficiencia ------------------------------------------------

def test_ningun_estado_de_suficiencia_afirma_cumplimiento():
    for e in EstadoSuficiencia:
        assert not e.afirma_cumplimiento


def test_suficiente_sin_apoyarse_en_nada_es_un_expediente_vacio():
    with pytest.raises(ValueError, match="expediente vacio"):
        Suficiencia("AIA-R-009-01", EstadoSuficiencia.SUFICIENTE, "pol", "1.0.0")


def test_insuficiente_sin_decir_que_falta_es_un_no_cumple_disfrazado():
    with pytest.raises(ValueError, match="disfrazado"):
        Suficiencia("AIA-R-009-01", EstadoSuficiencia.INSUFICIENTE, "pol", "1.0.0")


def test_el_gemelo_una_suficiencia_bien_formada_se_construye():
    s = Suficiencia("AIA-R-009-01", EstadoSuficiencia.SUFICIENTE, "pol", "1.0.0",
                    se_apoya_en=("sha256:ev1",))
    assert s.id.startswith("sha256:")
    mala = Suficiencia("AIA-R-009-02", EstadoSuficiencia.INSUFICIENTE, "pol", "1.0.0",
                       falta=(Falta({"es": "falta la ficha", "en": "the card is missing"},
                                    {"es": "escribela", "en": "write it"}, "tecnico"),))
    assert mala.falta[0].quien == "tecnico"


def test_una_falta_sin_que_hacer_no_es_una_falta_sino_una_queja():
    with pytest.raises(ValueError, match="dos idiomas"):
        Falta({"es": "falta algo", "en": "something missing"}, {"es": "solo castellano"}, "tecnico")


def test_suficiente_y_con_faltas_a_la_vez_no_se_puede_escribir():
    with pytest.raises(ValueError, match="suficiente y con faltas"):
        Suficiencia("R", EstadoSuficiencia.SUFICIENTE, "pol", "1.0.0",
                    se_apoya_en=("sha256:ev",),
                    falta=(Falta({"es": "x", "en": "x"}, {"es": "y", "en": "y"}, "tecnico"),))


# --- capa 5: la decision ---------------------------------------------------

def test_no_existe_manera_de_construir_una_decision_sin_una_persona():
    """La cuarta negativa convertida en tipo de datos."""
    for campo in ("quien", "cargo", "conclusion"):
        kw = dict(sobre="sha256:s", requisitos=("R",), quien="Marta Iglesias",
                  cargo="responsable de IA", cuando="2027-12-02T10:00:00+00:00",
                  conclusion="lo doy por bueno")
        kw[campo] = "   "
        with pytest.raises(ValueError, match="no es una decision de nadie"):
            Decision(**kw)


def test_una_decision_se_ata_al_expediente_y_no_a_la_fecha():
    """Si cambia una suficiencia, la decision queda atada a un estado viejo.

    Visible, sin que nadie tenga que acordarse. Una decision atada a una fecha
    no tiene esa propiedad: «firmado el 3 de abril» no dice sobre que.
    """
    a = Suficiencia("R1", EstadoSuficiencia.SUFICIENTE, "pol", "1.0.0",
                    se_apoya_en=("sha256:ev1",))
    antes = digest_de_suficiencias([a])
    d = Decision(sobre=antes, requisitos=("R1",), quien="Marta Iglesias",
                 cargo="responsable de IA", cuando="2027-12-02T10:00:00+00:00",
                 conclusion="lo doy por bueno")
    b = Suficiencia("R1", EstadoSuficiencia.INSUFICIENTE, "pol", "1.0.0",
                    falta=(Falta({"es": "caduco", "en": "expired"},
                                 {"es": "vuelve a observar", "en": "observe again"}, "tecnico"),))
    assert d.sobre != digest_de_suficiencias([b]), "la decision tiene que quedar descolgada"


def test_el_gemelo_si_nada_cambia_la_decision_sigue_atada():
    a = Suficiencia("R1", EstadoSuficiencia.SUFICIENTE, "pol", "1.0.0",
                    se_apoya_en=("sha256:ev1",))
    otra_igual = Suficiencia("R1", EstadoSuficiencia.SUFICIENTE, "pol", "1.0.0",
                             se_apoya_en=("sha256:ev1",))
    assert digest_de_suficiencias([a]) == digest_de_suficiencias([otra_igual])


# --- el motor generico, ya migrado ----------------------------------------

@pytest.fixture(scope="module")
def corrida():
    arbol = Arbol.leer(FIX)
    pk = Paquete.cargar(RAIZ / "catalogo" / "reglas" / "art12.json")
    res, _ = correr_paquete(arbol, pk)
    return res


def test_el_motor_generico_publica_sus_tres_capas(corrida):
    assert corrida.ejecucion is not None
    assert corrida.observacion is not None
    assert corrida.ejecucion.sujeto.digest.startswith("sha256:")
    assert corrida.observacion.ejecucion_id == corrida.ejecucion.id


def test_las_senales_son_datos_y_no_frases(corrida):
    """Lo encontrado se puede consultar y cruzar, no solo imprimir."""
    assert corrida.observacion.senales, "si no hay ninguna senal, esta prueba no comprueba nada"
    for s in corrida.observacion.senales:
        assert s.regla_id.startswith("ACT-")
        assert s.regla_version and s.paquete
        assert set(s.que_se_buscaba) == {"es", "en"}
    for l in corrida.observacion.limites:
        assert l.por_que in Limite.MOTIVOS


def test_dos_pasadas_sobre_el_mismo_arbol_dan_la_misma_observacion():
    """Reproducibilidad comprobada, no prometida."""
    pk = Paquete.cargar(RAIZ / "catalogo" / "reglas" / "art12.json")
    a, _ = correr_paquete(Arbol.leer(FIX), pk)
    b, _ = correr_paquete(Arbol.leer(FIX), pk)
    assert a.ejecucion.reproducible_como(b.ejecucion)
    assert a.observacion.id == b.observacion.id


def test_y_el_gemelo_tocar_un_fichero_cambia_el_sujeto(tmp_path):
    import shutil
    copia = tmp_path / "repo"
    shutil.copytree(FIX, copia)
    pk = Paquete.cargar(RAIZ / "catalogo" / "reglas" / "art12.json")
    antes, _ = correr_paquete(Arbol.leer(copia), pk)
    (copia / "nuevo.py").write_text("x = 1\n", encoding="utf-8")
    despues, _ = correr_paquete(Arbol.leer(copia), pk)
    assert antes.ejecucion.sujeto.digest != despues.ejecucion.sujeto.digest
    assert not antes.ejecucion.reproducible_como(despues.ejecucion)


def test_un_paquete_que_no_aplica_lo_dice_en_la_ejecucion_y_no_en_el_resultado(tmp_path):
    """«No le tocaba mirar» es un hecho de ejecucion, no una observacion limpia."""
    import json
    (tmp_path / "x.py").write_text("y = 1\n", encoding="utf-8")
    pq = tmp_path / "paquete.json"
    pq.write_text(json.dumps({
        "obligacion": "AIA-012", "paquete": "prueba/no-aplica", "version": "1.0.0",
        "autor": "prueba", "reglas": [{
            "id": "ACT-X-PAREJA", "version": "1.0.0", "tipo": "llamada_sin_pareja",
            "severidad": "alta",
            "que_busca": {"es": "una invocacion sin registro", "en": "a call with no logging"},
            "firmas": ["cliente.modelo.invocar"], "pareja": ["registro.escribir"],
            "titulo": {"es": "t", "en": "t"}, "remediacion": {"es": "r", "en": "r"}}]},
        ensure_ascii=False), encoding="utf-8")
    pk = Paquete.cargar(pq)
    res, _ = correr_paquete(Arbol.leer(tmp_path), pk)
    assert res.resultado is Resultado.NO_APLICA
    assert res.ejecucion.estado is EstadoEjecucion.NO_APLICABLE
    assert "no es que se mirara" in res.ejecucion.motivo["es"]
    assert res.ejecucion.motivo["en"]


def test_el_gemelo_cuando_si_aplica_la_ejecucion_sale_completada(tmp_path):
    """Si no, «no aplica» se arreglaria devolviendolo siempre."""
    import json
    (tmp_path / "x.py").write_text(
        "from cliente import modelo\nmodelo.invocar('hola')\n", encoding="utf-8")
    pq = tmp_path / "paquete.json"
    pq.write_text(json.dumps({
        "obligacion": "AIA-012", "paquete": "prueba/si-aplica", "version": "1.0.0",
        "autor": "prueba", "reglas": [{
            "id": "ACT-X-PAREJA", "version": "1.0.0", "tipo": "llamada_sin_pareja",
            "severidad": "alta",
            "que_busca": {"es": "una invocacion sin registro", "en": "a call with no logging"},
            "firmas": ["modelo.invocar"], "requiere_import": ["cliente"],
            "pareja": ["registro.escribir"],
            "titulo": {"es": "t", "en": "t"}, "remediacion": {"es": "r", "en": "r"}}]},
        ensure_ascii=False), encoding="utf-8")
    res, _ = correr_paquete(Arbol.leer(tmp_path), Paquete.cargar(pq))
    assert res.ejecucion.estado is EstadoEjecucion.COMPLETADA
    assert res.resultado is Resultado.CON_HALLAZGOS


# --- el defecto que encontro la propia separacion --------------------------

def test_un_resultado_limpio_con_hallazgos_dentro_no_se_puede_construir():
    """El quinto defecto, y no lo vio ninguna de las dos auditorias.

    El articulo 50 calculaba su resultado final mirando solo los artefactos sin
    marcar y se olvidaba de los hallazgos de generacion de texto que ya llevaba
    en la lista: devolvia SIN_HALLAZGOS con un hallazgo dentro. Nada fallaba, el
    hallazgo viajaba en el JSON, y el informe lo contaba en la columna de los
    limpios. Lo vio la proyeccion de la fase 14, que es para lo que se hizo.
    """
    h = Hallazgo("ACT-50-GEN-TXT", "1.0.0", "Actaira", "actaira/art50", "media",
                 "servicio.py:10", "r", "r")
    with pytest.raises(ValueError, match="hallazgos dentro"):
        ResultadoControl(control_id="ACT-C-50", obligacion_id="AIA-050",
                         resultado=Resultado.SIN_HALLAZGOS,
                         cubre=("algo",), no_cubre=("algo",), hallazgos=(h,))


def test_el_gemelo_con_hallazgos_y_hallazgos_dentro_si():
    h = Hallazgo("ACT-50-GEN-TXT", "1.0.0", "Actaira", "actaira/art50", "media",
                 "servicio.py:10", "r", "r")
    r = ResultadoControl(control_id="ACT-C-50", obligacion_id="AIA-050",
                         resultado=Resultado.CON_HALLAZGOS,
                         cubre=("algo",), no_cubre=("algo",), hallazgos=(h,))
    assert r.hallazgos == (h,)


def test_el_articulo_50_tambien_pasa_por_las_cinco_capas(tmp_path):
    """El ultimo control que construia su resultado a mano, ya no lo hace."""
    from actaira_motor.controles.art50 import Entrada, correr
    reglas = RAIZ / "catalogo" / "reglas" / "art50.json"
    r = correr(Entrada(RAIZ / "motor" / "tests" / "fixtures" / "repo-con-generacion"), reglas)
    assert r.ejecucion is not None and r.observacion is not None
    assert r.ejecucion.analizador == "actaira/art50"
    assert r.ejecucion.sujeto.tipo == "repositorio+artefactos"
    assert r.observacion.ejecucion_id == r.ejecucion.id
    assert r.suficiencia is not None and r.suficiencia.politica.startswith("actaira/suficiencia")


def test_y_no_queda_ningun_control_que_construya_su_resultado_a_mano():
    """La puerta que impide volver atras sin querer.

    Mientras exista un camino que arme un `ResultadoControl` sin capas, ese
    camino puede volver a fundir ejecucion, observacion y suficiencia, que es
    el defecto que esta fase arregla. Se comprueba leyendo el codigo con `ast`,
    no corriendolo: una rama que no se ejecuta en las pruebas tambien cuenta.
    """
    import ast
    sospechosos = []
    for f in sorted((RAIZ / "motor" / "src" / "actaira_motor" / "controles").glob("*.py")):
        if f.name == "modelo.py":
            continue                      # es donde vive el constructor
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id == "ResultadoControl":
                sospechosos.append(f"{f.name}:{n.lineno}")
    assert sospechosos == [], (
        "estos sitios construyen un ResultadoControl sin pasar por las capas: " +
        ", ".join(sospechosos))


# --- la pasada adversarial de la fase 14 -----------------------------------

def test_adv_una_suficiencia_no_se_puede_apoyar_en_evidencia_rancia():
    """`se_apoya_en` era una lista de identificadores y nadie miraba su estado.

    El tipo decia «esta, esta fresca y es valida» y solo comprobaba que la
    lista no estuviera vacia: la parte cara de la afirmacion quedaba a cargo de
    quien llamara, que es justo donde se pierde.
    """
    from datetime import datetime, timedelta, timezone

    from actaira_motor.evidencia.registro import Registro
    from actaira_motor.resultado.suficiencia import desde_evidencia

    T0 = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)
    r = Registro.nuevo("AIA-009", "ACT-C-009", "sha256:aaa", T0, {"x": 1}, frescura_dias=30)

    fresca = desde_evidencia("AIA-R-009-01", [r], T0 + timedelta(days=5),
                             politica="pol", politica_version="1.0.0")
    assert fresca.estado is EstadoSuficiencia.SUFICIENTE
    assert fresca.se_apoya_en == (r.id,)

    vieja = desde_evidencia("AIA-R-009-01", [r], T0 + timedelta(days=400),
                            politica="pol", politica_version="1.0.0")
    assert vieja.estado is EstadoSuficiencia.INSUFICIENTE
    assert "rancia" in vieja.falta[0].que["es"]
    assert vieja.falta[0].que_hacer["es"] == "vuelve a observar"


def test_adv_ni_en_evidencia_revocada():
    from datetime import datetime, timezone

    from actaira_motor.evidencia.registro import Registro
    from actaira_motor.resultado.suficiencia import desde_evidencia

    T0 = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)
    r = Registro.nuevo("AIA-009", "ACT-C-009", "sha256:aaa", T0, {"x": 1}, frescura_dias=30)
    s = desde_evidencia("AIA-R-009-01", [r], T0, politica="pol", politica_version="1.0.0",
                        revocadas=frozenset({r.id}))
    assert s.estado is EstadoSuficiencia.INSUFICIENTE
    assert "revocada" in s.falta[0].que["es"]


def test_adv_sin_evidencia_ninguna_no_es_lo_mismo_que_con_evidencia_caducada():
    """Dos faltas distintas piden dos acciones distintas."""
    from datetime import datetime, timedelta, timezone

    from actaira_motor.evidencia.registro import Registro
    from actaira_motor.resultado.suficiencia import desde_evidencia

    T0 = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)
    vacia = desde_evidencia("R", [], T0, politica="pol", politica_version="1.0.0")
    assert "no hay ninguna evidencia" in vacia.falta[0].que["es"]

    r = Registro.nuevo("AIA-009", "ACT-C-009", "sha256:aaa", T0, {"x": 1}, frescura_dias=1)
    caducada = desde_evidencia("R", [r], T0 + timedelta(days=9),
                               politica="pol", politica_version="1.0.0")
    assert "no hay ninguna evidencia" not in caducada.falta[0].que["es"]
    assert vacia.falta[0].que_hacer != caducada.falta[0].que_hacer


def test_adv_lo_que_cuenta_no_borra_lo_que_cayo():
    """Que una parte valga no puede esconder que otra caduco."""
    from datetime import datetime, timedelta, timezone

    from actaira_motor.evidencia.registro import Registro
    from actaira_motor.resultado.suficiencia import desde_evidencia

    T0 = datetime(2027, 12, 2, 10, 0, tzinfo=timezone.utc)
    viva = Registro.nuevo("AIA-009", "ACT-C-009", "sha256:aaa", T0, {"x": 1}, frescura_dias=365)
    muerta = Registro.nuevo("AIA-009", "ACT-C-009", "sha256:bbb", T0, {"y": 2}, frescura_dias=1)
    s = desde_evidencia("R", [viva, muerta], T0 + timedelta(days=9),
                        politica="pol", politica_version="1.0.0")
    assert s.estado is EstadoSuficiencia.INSUFICIENTE
    assert s.se_apoya_en == (viva.id,), "lo que cuenta se publica igual"
    assert len(s.falta) == 1


def test_adv_una_decision_sabe_decir_si_sigue_hablando_del_expediente_de_hoy():
    a = Suficiencia("R1", EstadoSuficiencia.SUFICIENTE, "pol", "1.0.0",
                    se_apoya_en=("sha256:ev1",))
    d = Decision(sobre=digest_de_suficiencias([a]), requisitos=("R1",),
                 quien="Marta Iglesias", cargo="responsable de IA",
                 cuando="2027-12-02T10:00:00+00:00", conclusion="lo doy por bueno")
    assert d.sigue_atada([a])
    b = Suficiencia("R1", EstadoSuficiencia.INSUFICIENTE, "pol", "1.0.0",
                    falta=(Falta({"es": "caduco", "en": "expired"},
                                 {"es": "vuelve a observar", "en": "observe again"}, "tecnico"),))
    assert not d.sigue_atada([b])


def test_adv_el_arbol_ENTERO_pasa_por_las_capas_no_solo_los_controles():
    """La puerta anterior solo miraba `controles/`. Un expediente, un formulario
    o un conector nuevo podian construir el resultado a mano igual."""
    import ast
    base = RAIZ / "motor" / "src" / "actaira_motor"
    sospechosos = []
    for f in sorted(base.rglob("*.py")):
        if f.name == "modelo.py":
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id == "ResultadoControl":
                sospechosos.append(f"{f.relative_to(base)}:{n.lineno}")
    assert sospechosos == [], (
        "construyen un ResultadoControl sin pasar por las capas: " + ", ".join(sospechosos))


def test_la_suficiencia_del_articulo_50_es_de_UN_requisito_no_del_articulo():
    """El articulo 50 tiene cinco deberes y este control solo mira uno.

    Cerrar el articulo entero por el marcado seria el fallo que los requisitos
    atomicos existen para impedir: un articulo con cinco deberes dado por bueno
    porque uno esta cubierto.
    """
    from actaira_motor.catalogo.cargador import cargar
    from actaira_motor.controles.art50 import Entrada, correr

    cat = cargar(str(RAIZ / "catalogo"))
    deberes = cat.requisitos_de("50")
    assert len(deberes) >= 4, "el articulo 50 no esta partido en sus deberes"

    reglas = RAIZ / "catalogo" / "reglas" / "art50.json"
    r = correr(Entrada(RAIZ / "motor" / "tests" / "fixtures" / "repo-con-generacion"), reglas)
    assert r.suficiencia.requisito_id in {d.id for d in deberes}
    assert r.suficiencia.requisito_id != "AIA-050", "eso es la obligacion, no el requisito"

    # Y el requisito al que apunta es el del marcado, no otro cualquiera.
    suyo = next(d for d in deberes if d.id == r.suficiencia.requisito_id)
    assert "marca" in suyo.exige["es"].lower() or "mark" in suyo.exige["en"].lower()
