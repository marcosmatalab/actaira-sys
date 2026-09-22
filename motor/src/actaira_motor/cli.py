"""La linea de ordenes. Cada verbo existe porque hay un modulo que lo necesita.

REGLA DE ALCANZABILIDAD, heredada de la constitucion de actaira: todo modulo
del paquete tiene que ser alcanzable desde un verbo. Lo que no lo sea, sale.
`test_alcanzabilidad` es la puerta y corre en `make todo`.

Diez verbos en la fase 8. El noveno, `ortografia`, no es un vertical: es la
herramienta que sujeta una propiedad del catalogo, igual que `exportar` sujeta
la tabla. Un verbo que existe para que una puerta pueda correrse a mano cuenta
como nucleo. El tope es un verbo por vertical construido mas los
del nucleo: subirlo es una decision que se escribe, no un impulso.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .aplicabilidad.motor import Perfil, recuento, resolver
from .aplicabilidad.tabla import exportar
from .catalogo.cargador import cargar
from .controles.art50 import Entrada, correr
from .evidencia.registro import Estado, Registro, digest
from .controles.tuberia import CONOCIDAS
from .controles.motor import Arbol
from .expediente.anexoiv import a_markdown, generar as generar_anexo
from .integraciones.sarif import exportar as exportar_sarif
from .texto.codigo import corregir_fuente
from .texto.ortografia import corregir_es
from .vigilancia.almacen import Almacen, AlmacenAlterado
from .vigilancia.barrido import observar
from .vigilancia.reconciliar import reconciliar
from .expediente.anexov import a_markdown as av_markdown, generar as generar_anexov
from .expediente.soa import a_markdown as soa_markdown, generar as generar_soa
from .formularios.cuestionario import construir as construir_cuestionario, pendientes
from .formularios.declaracion import Confianza, Respuesta, registrar
from .formularios.plan import construir as construir_plan
from .evidencia.sello import sellar, verificar

def _localizar_catalogo() -> Path:
    """Donde esta el catalogo, en los tres sitios donde puede estar.

    Esto existia mal y el sintoma habria sido feo: `RAIZ = parents[3]` funciona
    en el arbol de desarrollo y apunta a `site-packages/catalogo` cuando el
    paquete se instala con pip, que no existe. La plantilla de integracion
    continua dice `pip install actaira-motor`, asi que el primer cliente que la
    copiara se habria encontrado con que el verbo no arranca.

    Orden, de mas explicito a mas implicito:
      1. ACTAIRA_CATALOGO, para apuntar a un catalogo propio o a uno fijado.
      2. el que viaja dentro del paquete, que es el caso de `pip install`.
      3. el de la raiz del repositorio, que es el caso de desarrollo.
    """
    import os

    if (env := os.environ.get("ACTAIRA_CATALOGO")):
        return Path(env)
    empaquetado = Path(__file__).resolve().parent / "_catalogo"
    if (empaquetado / "ai-act" / "obligaciones.json").is_file():
        return empaquetado
    return Path(__file__).resolve().parents[3] / "catalogo"


RAIZ = Path(__file__).resolve().parents[3]
CATALOGO = _localizar_catalogo()
REGLAS_50 = CATALOGO / "reglas" / "art50.json"


# LOS CODIGOS DE SALIDA, ESCRITOS UNA VEZ
# ----------------------------------------
# Un verbo que imprime quince hallazgos y sale con 0 es un verbo que no sirve
# para una integracion continua, que es el unico sitio donde este producto vive
# de verdad. Y si cada verbo elige su numero por su cuenta, `plan` devuelve 1
# donde `anexo` devuelve 3 sobre el mismo hecho. Estan aqui, son cinco, y se
# corresponden uno a uno con los estados del motor.
SALIDA_LIMPIO = 0        # se miro y no aparecio nada
SALIDA_HALLAZGOS = 1     # aparecio algo
SALIDA_PENDIENTE = 3     # no se pudo decidir, o falta que alguien conteste
SALIDA_ERROR = 4         # el analizador se rompio
SALIDA_ALTERADO = 5      # el almacen no es el que esta casa escribio


# LA SALIDA SE ESCRIBE EN UTF-8, DECIDA LO QUE DECIDA LA CONSOLA
# ---------------------------------------------------------------
# Python codifica `stdout` con la pagina de codigos de la consola. En una
# consola de Windows en espanol esa pagina es cp850, y cp850 NO TIENE la raya
# «—», que esta sesenta y tres veces en el catalogo y en los documentos que
# esta casa emite. El resultado era un `UnicodeEncodeError` sin capturar en
# `soa`, en `anexo --cual v` y en `preguntar --json`: el verbo no imprimia
# nada y el proceso salia con 1.
#
# Salir con 1 es lo peor de todo esto. Arriba esta escrito que 1 es «aparecio
# algo» y que romperse es 4, asi que una integracion continua con la puerta
# encendida habria parado un despliegue citando hallazgos que no existen. Es
# la categoria de defecto que este producto existe para no cometer: plausible
# y falso.
#
# POR QUE RECONFIGURAR Y NO QUITAR LA RAYA DEL CATALOGO
# ------------------------------------------------------
# Quitarla arregla los sesenta y tres casos de hoy y ninguno de manana: el dia
# que un jurista escriba «—» o «…» en una regla nueva, el defecto vuelve y no
# hay puerta que lo detenga. El texto normativo se escribe como se escribe el
# castellano; quien se adapta es el canal.
#
# En una consola cp850 antigua algunas tildes se veran mal. Eso es preferible
# a perder el caracter -- `errors="replace"` habria dejado un `?` DENTRO de un
# documento que va a un auditor -- y muy preferible a no imprimir nada.
#
# Se hace en `main()` y no bajo `__main__` a proposito: el punto de entrada
# que instala pip llama a `main()` directamente, que es la misma razon por la
# que el `BrokenPipeError` se captura ahi abajo y no aqui.
def _salida_en_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")   # type: ignore[union-attr]
        except (AttributeError, OSError, ValueError):
            # Un flujo redirigido a algo que no es un fichero de texto no se
            # reconfigura. No es motivo para no correr el verbo.
            pass


def _roles(a: argparse.Namespace) -> frozenset[str]:
    """Los roles pedidos, y `proveedor` SOLO si no se pidio ninguno.

    `action="append"` con `default=["proveedor"]` no sustituye el defecto: lo
    amplia. `--rol responsable_despliegue` daba `{proveedor, responsable_despliegue}`
    y el cliente recibia las obligaciones del proveedor sin haberlas pedido --
    que en este producto no es un parametro mal leido, es atribuirle a una
    empresa un papel juridico que no tiene. El defecto se aplica aqui, donde se
    ve, y no en seis declaraciones de argumento repartidas por el fichero.
    """
    return frozenset(a.rol or ["proveedor"])


def _salida_del_plan(plan: dict) -> int:
    """El codigo de salida de un plan. Una definicion, la usan todos los verbos.

    Y NO depende del formato de salida: `plan --json` devolvia 0 con quince
    hallazgos delante, porque el `return 0` estaba dentro de la rama que
    imprime JSON. Un formato de impresion no puede cambiar un veredicto.
    """
    if any(l["hallazgos"] for l in plan["lineas"]):
        return SALIDA_HALLAZGOS
    r = plan["recuento"]
    if r.get("sin_resolver") or r.get("a_preguntar") or r.get("solo_formulario"):
        return SALIDA_PENDIENTE
    return SALIDA_LIMPIO


def cmd_aplicabilidad(a: argparse.Namespace) -> int:
    cat = cargar(a.catalogo)
    perfil = Perfil(
        roles=_roles(a),
        es_alto_riesgo=a.alto_riesgo,
        es_sector_publico=a.sector_publico,
        provee_modelo_uso_general=a.modelo_uso_general,
        modelo_con_riesgo_sistemico=a.riesgo_sistemico,
        via_anexo=getattr(a, "via_anexo", None),
    )
    v = resolver(cat, perfil, date.fromisoformat(a.fecha))
    if a.json:
        # Con `esquema` dentro, como todo lo que cruza la frontera. Sin el, al
        # otro lado no hay a quien preguntarle que documento acaba de leer, y
        # la plataforma lo rechaza -- que es lo correcto y es como se encontro
        # este hueco: la API no podia servir el primer documento que ve un
        # cliente.
        from .vocabulario import nombres_de
        print(json.dumps({"esquema": "actaira/aplicabilidad/v1", "fecha": a.fecha,
                          "recuento": recuento(v),
                          "nombres_de_estado": nombres_de(
                              [x.situacion.value for x in v] + list(recuento(v))),
                          "veredictos": [x.a_json() for x in v]},
                         ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(recuento(v), ensure_ascii=False))
    for x in sorted(v, key=lambda y: y.situacion.value):
        idioma = getattr(a, "idioma", "es")
        print(f"  {x.situacion.value:<14} {x.obligacion_id}  "
              f"{cat.obligaciones[x.obligacion_id].titulo[idioma]}")
        print(f"                 {x.regla}")
    return 0


def cmd_comprobar(a: argparse.Namespace) -> int:
    res = correr(Entrada(repositorio=Path(a.repo),
                         artefactos=tuple(Path(p) for p in a.artefacto),
                         pipeline=tuple(a.paso)),
                 a.reglas)
    # EL `esquema` SE ANADE AQUI Y NO DENTRO DE `a_json()`.
    #
    # `a_json()` es tambien el CONTENIDO que se sella como evidencia, y el
    # digest de ese contenido es lo que hace que una evidencia vieja se pueda
    # comparar con una nueva. Meterle un campo dentro habria cambiado el digest
    # de todo lo sellado hasta hoy, es decir, habria roto la continuidad del
    # expediente de cualquiera que ya use esto. El documento que se PUBLICA
    # lleva su esquema; lo que se SELLA sigue siendo lo mismo de siempre.
    print(json.dumps({"esquema": "actaira/control/v1", **res.a_json()},
                     ensure_ascii=False, indent=2))
    # Un codigo por estado, y el ERROR se separa del INDETERMINADO a proposito:
    # «no pude decidir» y «me rompi» piden cosas distintas de quien lo recibe.
    return {"sin_hallazgos": 0, "con_hallazgos": 1, "indeterminado": 3,
            "no_aplica": 0, "error": 4}[res.resultado.value]


def cmd_sellar(a: argparse.Namespace) -> int:
    res = correr(Entrada(repositorio=Path(a.repo),
                         artefactos=tuple(Path(p) for p in a.artefacto),
                         pipeline=tuple(a.paso)),
                 a.reglas)
    ahora = datetime.now(timezone.utc) if a.ahora is None else datetime.fromisoformat(a.ahora)
    reg = Registro.nuevo("AIA-050", res.control_id, digest(res.a_json()), ahora,
                         res.a_json(), frescura_dias=a.frescura)
    pem = Path(a.clave).read_bytes() if a.clave else None
    s = sellar([reg], ahora, pem)
    Path(a.salida).write_text(json.dumps(s.a_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"sello escrito en {a.salida}\n  raiz: {s.raiz}\n  firmado: {bool(s.firma)}")
    return 0


def cmd_verificar(a: argparse.Namespace) -> int:
    """Verifica un sello. Sin `--clave-esperada` NO establece identidad, y lo dice.

    La funcion de verificacion ya lo separaba -- integridad no es identidad --
    pero el verbo no tenia por donde pasarle la clave que uno espera, asi que
    en la practica NADIE podia establecer identidad desde la linea de mandatos
    y todo sello firmado salia con el mismo aviso. Una separacion correcta sin
    manera de resolverla es media separacion.
    """
    esperada = a.clave_esperada
    if esperada and Path(esperada).is_file():
        # Se admite el hexadecimal suelto o un fichero que lo contenga: quien
        # opera esto tiene la clave publica en un fichero, no en el portapapeles.
        esperada = Path(esperada).read_text(encoding="utf-8").strip()
    ok, motivos = verificar(json.loads(Path(a.sello).read_text(encoding="utf-8")),
                            clave_esperada=esperada)
    print("VERIFICA" if ok else "NO VERIFICA")
    for m in motivos:
        print("  " + m)
    return 0 if ok else 1


def cmd_plan(a: argparse.Namespace) -> int:
    cat = cargar(a.catalogo)
    perfil = Perfil(
        roles=_roles(a), es_alto_riesgo=_tri(a.alto_riesgo),
        es_sector_publico=_tri(a.sector_publico),
        provee_modelo_uso_general=_tri(a.modelo_uso_general),
        modelo_con_riesgo_sistemico=_tri(a.riesgo_sistemico),
        via_anexo=getattr(a, "via_anexo", None))
    plan = construir_plan(cat, perfil, date.fromisoformat(a.fecha), a.repo,
                          a.reglas, tuple(Path(x) for x in a.artefacto))
    if a.sarif:
        Path(a.sarif).write_text(
            json.dumps(exportar_sarif(plan, idioma=a.idioma), ensure_ascii=False, indent=2),
            encoding="utf-8")
        n = sum(len(l["hallazgos"]) for l in plan["lineas"])
        print(f"SARIF escrito en {a.sarif}: {n} resultados")
    if a.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return _salida_del_plan(plan)
    print(json.dumps(plan["recuento"], ensure_ascii=False), "| preguntas:", plan["total_preguntas"])
    for l in plan["lineas"]:
        if l["estado"] in ("no_ata", "futura"):
            continue
        print(f"  Art.{l['articulo']:<4} {l['estado']:<16} hallazgos={len(l['hallazgos'])} "
              f"preguntas={len(l['preguntas'])}  {l['titulo'][a.idioma][:44]}")
        for h in l["hallazgos"]:
            print(f"      [{h['severidad']}] {h['regla_id']} ({h['paquete']} v{h['regla_version']}, {h['autor']})")
            print(f"        {h['remediacion'][a.idioma][:110]}")
    return _salida_del_plan(plan)


def cmd_anexo(a: argparse.Namespace) -> int:
    if a.cual == "v":
        return _anexo_v(a)
    cat = cargar(a.catalogo)
    perfil = Perfil(
        roles=_roles(a), es_alto_riesgo=_tri(a.alto_riesgo),
        es_sector_publico=_tri(a.sector_publico),
        provee_modelo_uso_general=_tri(a.modelo_uso_general),
        modelo_con_riesgo_sistemico=_tri(a.riesgo_sistemico),
        via_anexo=getattr(a, "via_anexo", None))
    cuando = date.fromisoformat(a.fecha)
    plan = construir_plan(cat, perfil, cuando, a.repo, a.reglas)
    aportes = json.loads(Path(a.aportes).read_text(encoding="utf-8")) if a.aportes else {}
    anexo = generar_anexo(Path(a.catalogo) / "ai-act" / "anexo-iv.json",
                          Arbol.leer(a.repo), plan, aportes, cuando)
    if a.json:
        print(json.dumps(anexo, ensure_ascii=False, indent=2))
    else:
        print(a_markdown(anexo, a.idioma))
    # Un expediente con secciones ausentes NO es un fallo del comando: es el
    # estado real, y el codigo de salida lo distingue para que un flujo de CI
    # pueda decidir. Tres es "incompleto", no "roto".
    return 3 if anexo["recuento"].get("ausente", 0) else 0


def _anexo_v(a: argparse.Namespace) -> int:
    """El Anexo V no sale del repositorio casi nada: sale del cuestionario."""
    cat = cargar(a.catalogo)
    perfil = Perfil(
        roles=_roles(a), es_alto_riesgo=_tri(a.alto_riesgo),
        es_sector_publico=_tri(a.sector_publico),
        provee_modelo_uso_general=_tri(a.modelo_uso_general),
        modelo_con_riesgo_sistemico=_tri(a.riesgo_sistemico),
        via_anexo=getattr(a, "via_anexo", None))
    cuando = date.fromisoformat(a.fecha)
    plan = construir_plan(cat, perfil, cuando, a.repo, a.reglas)
    registros, _ = registrar(cat.preguntas, _respuestas_de(a.respuestas, getattr(a, 'clave_esperada', None)))
    q = construir_cuestionario(cat, plan, registros,
                               datetime.fromisoformat(a.fecha + "T12:00:00+00:00"), cat.formularios)
    doc = generar_anexov(Path(a.catalogo) / "ai-act" / "anexo-v.json", Arbol.leer(a.repo), q, cuando)
    if a.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
    else:
        print(av_markdown(doc, a.idioma))
    # Sin firma es borrador, y eso no es un error del comando: es el estado del
    # documento. Tres, como el Anexo IV incompleto y la SoA sin justificar.
    return 0 if doc["firmado"] else 3


def _respuestas_de(ruta: str | None,
                   clave_esperada: str | None = None) -> list[Respuesta]:
    """Lee respuestas, vengan del fichero que se escribe a mano o de una
    declaracion ya emitida. Una fecha ausente NO se rellena con hoy.

    EL AGUJERO QUE ESTO CIERRA
    ----------------------------
    `contestar` escribe `{"sello": ..., "registros": [...]}` y este lector solo
    miraba la clave `respuestas`. Devolver la declaracion al producto -- que es
    lo primero que hace cualquiera al volver al cuestionario al mes siguiente --
    daba cero respuestas contestadas en vez de nueve, EN SILENCIO, y el cliente
    veia su formulario entero en blanco otra vez. El circuito no se cerraba.

    Rellenar la fecha seria inventar cuando se dijo algo, y de esa fecha cuelga
    la caducidad entera. Sin fecha, el fichero esta mal y se dice.

    Y UNA DECLARACION NO SE CREE SIN COMPROBARLA
    ----------------------------------------------
    Si el fichero trae sello, se verifica la raiz Merkle ANTES de reconstruir
    nada. Sin eso, reimportar seria la manera comoda de blanquear una
    declaracion editada a mano: entra como fichero tocado y sale como evidencia
    recien observada. La identidad de quien firmo es otra pregunta y la
    contesta `verificar --clave-esperada`; aqui se comprueba que el contenido
    es el que se sello.
    """
    if not ruta:
        return []
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if "respuestas" in datos:
        return _respuestas_escritas(ruta, datos["respuestas"])
    if "sello" in datos or "registros" in datos:
        return _respuestas_de_una_declaracion(ruta, datos, clave_esperada)
    raise SystemExit(
        f"{ruta}: no trae ni 'respuestas' (fichero escrito a mano) ni 'registros' "
        f"(declaracion emitida por `actaira contestar`). Claves que trae: "
        f"{', '.join(sorted(datos)) or 'ninguna'}")


def _respuestas_escritas(ruta: str, crudas: list[dict]) -> list[Respuesta]:
    """Un fichero escrito a mano. Confianza: ninguna, y se dice.

    No lleva firma porque no puede llevarla: es un JSON que alguien edito.
    Sale con `SIN_FIRMA` y con eso el expediente lo presentara como lo que
    es -- un borrador -- en vez de al lado de una declaracion firmada y sin
    distinguirlas.
    """
    fuera = []
    for i, r in enumerate(crudas):
        for campo in ("pregunta", "valor", "quien", "cargo", "cuando"):
            if campo not in r:
                raise SystemExit(f"{ruta}: la respuesta {i} no trae '{campo}'")
        fuera.append(Respuesta(r["pregunta"], r["valor"], r["quien"], r["cargo"],
                               datetime.fromisoformat(r["cuando"]), r.get("justificacion"),
                               confianza=Confianza.SIN_FIRMA))
    return fuera


def _respuestas_de_una_declaracion(ruta: str, datos: dict,
                                   clave_esperada: str | None = None) -> list[Respuesta]:
    sello_json = datos.get("sello")
    if sello_json:
        # Los registros se leen de DENTRO del sello, que es lo que la raiz
        # cubre. Un fichero viejo que traiga ademas una copia al lado se
        # rechaza en vez de elegir una: elegir seria decidir en silencio cual
        # de las dos versiones de la verdad vale.
        if "registros" in datos and datos["registros"] != sello_json.get("registros"):
            raise SystemExit(
                f"{ruta}: trae dos listas de registros y no dicen lo mismo. La que "
                f"cuenta es la que esta dentro del sello; la de fuera no la cubre "
                f"la raiz Merkle. Vuelve a emitir la declaracion con `actaira contestar`.")
        datos = {**datos, "registros": sello_json.get("registros", [])}
        _, motivos = verificar(sello_json, clave_esperada=clave_esperada)
        # `verificar` devuelve False cuando no hay firma o no se paso clave
        # esperada, y eso NO invalida el contenido: aqui se comprueba lo que
        # esta funcion necesita, que es la raiz.
        graves = [m for m in motivos if m.startswith("la raiz no reproduce")
                  or m.startswith("la firma no verifica")
                  or m.startswith("esquema desconocido")
                  or m.startswith("la clave que firma no es la esperada")
                  or m.startswith("el sello trae campos")]
        if graves:
            raise SystemExit(f"{ruta}: la declaracion no verifica y no se reimporta.\n  "
                             + "\n  ".join(graves))

        # EL NIVEL DE CONFIANZA SE DECIDE AQUI Y VIAJA CON CADA RESPUESTA.
        #
        # Antes esto era un `print` a la salida de error -- «verifica su
        # contenido pero no su autoria» -- y nada mas. En una integracion
        # continua ese aviso no lo lee nadie, y las respuestas entraban en el
        # expediente indistinguibles de las de una declaracion firmada por
        # alguien con nombre. La raiz Merkle demuestra que el contenido es el
        # mismo que cuando se calculo la raiz; no demuestra autoria, ni
        # capacidad del firmante, ni representacion, ni el momento de firma.
        #
        # Ahora el nivel entra en el CONTENIDO de cada respuesta, que es lo
        # que cubre la raiz y lo que sella la linea del almacen. Un aviso se
        # ignora; un campo dentro del sello llega hasta el documento que lee
        # el auditor y no se puede quitar sin romper la cadena.
        if not sello_json.get("firma"):
            confianza = Confianza.SIN_FIRMA
        elif clave_esperada:
            confianza = Confianza.IDENTIDAD_VERIFICADA
        else:
            confianza = Confianza.FIRMADA
    else:
        # Sin sello no hay ni raiz que comprobar.
        confianza = Confianza.SIN_FIRMA
    fuera = []
    for i, r in enumerate(datos["registros"]):
        c = r.get("contenido", {})
        for campo in ("valor", "quien", "cargo"):
            if campo not in c:
                raise SystemExit(f"{ruta}: el registro {i} ({r.get('control_id')}) no trae "
                                 f"'{campo}' en su contenido: no es una respuesta de formulario")
        fuera.append(Respuesta(r["control_id"], c["valor"], c["quien"], c["cargo"],
                               datetime.fromisoformat(r["observado_en"]),
                               c.get("justificacion"), confianza=confianza))
    return fuera


# Las etiquetas del propio verbo. Si `--idioma en` traduce las preguntas y deja
# "por:" en castellano, la bandera esta a medias, que es peor que no tenerla.
ETIQUETAS = {
    "es": {"por": "por", "ahorro": "el codigo contesta {n} preguntas, porque estos controles leyeron los bytes: {c}",
           "ninguno": "todavia ninguno", "aviso": "AVISO"},
    "en": {"por": "for", "ahorro": "code answers {n} questions, because these controls read the bytes: {c}",
           "ninguno": "none yet", "aviso": "NOTE"},
}


def cmd_preguntar(a: argparse.Namespace) -> int:
    cat = cargar(a.catalogo)
    plan = None
    if a.repo:
        perfil = Perfil(
            roles=_roles(a), es_alto_riesgo=_tri(a.alto_riesgo),
            es_sector_publico=_tri(a.sector_publico),
            provee_modelo_uso_general=_tri(a.modelo_uso_general),
            modelo_con_riesgo_sistemico=_tri(a.riesgo_sistemico),
        via_anexo=getattr(a, "via_anexo", None))
        plan = construir_plan(cat, perfil, date.fromisoformat(a.fecha), a.repo, a.reglas)
    registros, sueltas = registrar(cat.preguntas, _respuestas_de(a.respuestas, getattr(a, 'clave_esperada', None)))
    ahora = datetime.fromisoformat(a.fecha + "T12:00:00+00:00")
    q = construir_cuestionario(cat, plan, registros, ahora, cat.formularios)
    codigo = SALIDA_PENDIENTE if pendientes(q, a.destinatario) else SALIDA_LIMPIO
    if a.json:
        print(json.dumps(q, ensure_ascii=False, indent=2))
        return codigo
    for s in sueltas:
        print(f"  {ETIQUETAS[a.idioma]['aviso']}  {s}")
    print(json.dumps(q["recuento"], ensure_ascii=False))
    ah, et = q["ahorro"], ETIQUETAS[a.idioma]
    print(et["ahorro"].format(n=ah["preguntas_que_contesta_el_codigo"],
                              c=", ".join(ah["porque"]) or et["ninguno"]))
    for p_ in q["paquetes"]:
        falta = [x for x in p_["preguntas"] if x in pendientes(q, a.destinatario)]
        if not falta:
            continue
        print(f"\n--- {p_['titulo'][a.idioma]} ({len(falta)}) ---")
        for x in falta:
            print(f"  [{x['estado']:<10}] {x['id']}  {x['texto'][a.idioma]}")
            print(f"               {et['por']}: "
                  f"{', '.join(y['referencia'][a.idioma] for y in x['por_que'])}")
            if x.get("motivo"):
                print(f"               {x['motivo']}")
    return codigo


def cmd_contestar(a: argparse.Namespace) -> int:
    cat = cargar(a.catalogo)
    registros, sueltas = registrar(cat.preguntas, _respuestas_de(a.respuestas, getattr(a, 'clave_esperada', None)))
    ahora = datetime.now(timezone.utc) if a.ahora is None else datetime.fromisoformat(a.ahora)
    pem = Path(a.clave).read_bytes() if a.clave else None
    s = sellar(registros, ahora, pem)
    # UNA SOLA COPIA DE LOS REGISTROS, Y ES LA SELLADA
    # --------------------------------------------------
    # Antes se escribian dos veces: dentro del sello y otra vez al lado. La
    # raiz Merkle solo cubre la de dentro, asi que editar la de fuera no
    # rompia nada -- y la de fuera era justamente la que leia la reimportacion.
    # Dos representaciones de lo mismo con una sola comprobada: regla 10, se
    # anulan. Ahora hay una, y esa es la que esta bajo la raiz.
    Path(a.salida).write_text(json.dumps(
        {"esquema": "actaira/declaracion-firmada/v1", "sello": s.a_json()},
        ensure_ascii=False, indent=2), encoding="utf-8")
    # Cada estado con su nombre. La primera version imprimia "NO ADMITE" para
    # cualquier cosa que no fuera VALIDA y mostraba `r.motivo`, que es None
    # cuando la respuesta caduco: salia "NO ADMITE F-SIS-5: None". Fundir
    # RANCIA con NO_FIABLE es exactamente lo que el modulo de evidencia
    # advierte que hacen las demas herramientas, y piden acciones distintas:
    # una se vuelve a preguntar igual, la otra hay que contestarla mejor.
    otros = [(r.control_id, *r.estado(ahora)) for r in registros
             if r.estado(ahora)[0] is not Estado.VALIDA]
    print(f"declaracion escrita en {a.salida}\n  respuestas: {len(registros)}"
          f"\n  raiz: {s.raiz}\n  firmada: {bool(s.firma)}")
    for qid, est, motivo in otros:
        print(f"  {est.value.upper():<10} {qid}: {motivo['es']}")
    for x in sueltas:
        print("  AVISO  " + x)
    return 1 if any(e is Estado.NO_FIABLE for _, e, _ in otros) else 0


def cmd_soa(a: argparse.Namespace) -> int:
    cat = cargar(a.catalogo)
    perfil = Perfil(
        roles=_roles(a), es_alto_riesgo=_tri(a.alto_riesgo),
        es_sector_publico=_tri(a.sector_publico),
        provee_modelo_uso_general=_tri(a.modelo_uso_general),
        modelo_con_riesgo_sistemico=_tri(a.riesgo_sistemico),
        via_anexo=getattr(a, "via_anexo", None))
    cuando = date.fromisoformat(a.fecha)
    plan = construir_plan(cat, perfil, cuando, a.repo, a.reglas) if a.repo else None
    registros, _ = registrar(cat.preguntas, _respuestas_de(a.respuestas, getattr(a, 'clave_esperada', None)))
    q = construir_cuestionario(cat, plan, registros,
                               datetime.fromisoformat(a.fecha + "T12:00:00+00:00"), cat.formularios)
    decisiones = json.loads(Path(a.decisiones).read_text(encoding="utf-8")) if a.decisiones else {}
    aprobada = json.loads(a.aprobada) if a.aprobada else None
    soa = generar_soa(cat, plan, q, decisiones, cuando, aprobada)
    if a.json:
        print(json.dumps(soa, ensure_ascii=False, indent=2))
    else:
        print(soa_markdown(soa, a.idioma))
    # Pendientes de justificar no es un fallo: es el estado real de una
    # declaracion que todavia no ha pasado por una persona. Tres es
    # "incompleta", como en el Anexo IV.
    return 3 if soa["recuento"]["pendientes_de_justificar"] else 0


def cmd_vigilar(a: argparse.Namespace) -> int:
    """Que sigue valiendo, que caduco, que cambio, y que hay que volver a mirar.

    Este verbo es el producto de suscripcion. Sin el, todo lo anterior es una
    foto; con el, la foto tiene fecha de caducidad y sabe cuando deja de
    describir lo que hay.
    """
    cat = cargar(a.catalogo)
    if not a.solo_almacen and not a.repo:
        raise SystemExit("vigilar necesita un repositorio, o --solo-almacen para "
                         "preguntar solo que caduco")
    perfil = Perfil(
        roles=_roles(a), es_alto_riesgo=_tri(a.alto_riesgo),
        es_sector_publico=_tri(a.sector_publico),
        provee_modelo_uso_general=_tri(a.modelo_uso_general),
        modelo_con_riesgo_sistemico=_tri(a.riesgo_sistemico),
        via_anexo=getattr(a, "via_anexo", None))
    ahora = datetime.now(timezone.utc) if a.ahora is None else datetime.fromisoformat(a.ahora)
    if a.solo_almacen:
        # Sin repositorio. Es el modo que corre el vencimiento de la plataforma:
        # para saber QUE CADUCO no hace falta el codigo del cliente, hace falta
        # el almacen y el reloj. Correr el barrido entero para eso seria pedirle
        # el repositorio a un cliente que no ha empujado nada, que es justo lo
        # que este diseno evita.
        #
        # `sujetos` vacio NO marca nada como superado: `estado()` solo compara
        # el digest cuando se le da uno. Y `esperados` vacio evita inventar
        # `sin_evidencia` de controles que no se han mirado en esta pasada.
        # `esperados` es None y NO un diccionario vacio, y la diferencia es
        # exactamente el defecto que esto evito: vacio significa "se miro y no
        # se esperaba nada", y con esa lectura TODA la evidencia del almacen
        # salia `fuera_de_alcance`. None significa "en esta pasada no se ha
        # mirado que se espera", que es la verdad cuando no hay repositorio.
        registros, sujetos, esperados, sin_paquete = [], {}, None, []
    else:
        registros, sujetos, esperados, sin_paquete = observar(
            cat, perfil, ahora.date(), a.repo, a.reglas, ahora)

    alm = Almacen.abrir(a.almacen)
    rec = reconciliar(alm, sujetos, ahora, esperados=esperados)
    anadidos, revalidados = alm.anadir(registros, ahora) if a.registrar else (0, 0)
    salida = rec.a_json()
    salida["registradas"] = anadidos
    salida["revalidadas"] = revalidados
    salida["obligaciones_sin_paquete"] = sin_paquete

    if a.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(salida["recuento"], ensure_ascii=False))
        ah = salida["ahorro_de_barridos"]
        print(f"controles con evidencia: {ah['controles_con_evidencia']} | "
              f"hay que volver a correr: {ah['hay_que_volver_a_correr']}")
        for v in salida["veredictos"]:
            if v["accion"] == "nada":
                continue
            print(f"  {v['estado']:<14} {v['control_id']:<10} {v['motivo'][a.idioma]}")
            if v.get("detalle"):
                print(f"                 {v['detalle'][a.idioma][:104]}")
        if anadidos or revalidados:
            print(f"al almacen: {anadidos} observaciones nuevas, "
                  f"{revalidados} revalidadas (mismo sujeto, mismo resultado)")
        if sin_paquete:
            print("obligaciones de nivel comprobable sin paquete todavia: " + ", ".join(sin_paquete))
    # Tres es "hay trabajo que hacer", no "esto ha reventado". La distincion
    # importa porque una puerta de CI trata distinto los dos casos.
    return 3 if salida["a_reobservar"] else 0


CONTROL_FUENTE = "ACT-C-FUENTE"
CONTROL_INERTE = "ACT-C-INERTE"


def _posicion(alm: "Almacen", ubicacion: str, referencia: str) -> tuple[str | None, tuple, str]:
    """Dónde está este sujeto según el almacén: lo observado y la cadena inerte.

    Se busca por UBICACION Y REFERENCIA, no por ubicación sola. La primera
    versión se quedaba con el último registro de la ubicación y comparaba un
    empujón a `develop` contra el commit de `main`: siempre distinto, siempre
    REOBSERVAR. No mentía, pero convertía el filtro barato en un adorno, y lo
    hacía en silencio.
    """
    observada: str | None = None
    otra_rama = False
    esta_rama = False
    inerte: list[str] = []
    for r in alm.registros():
        c = r.contenido if isinstance(r.contenido, dict) else {}
        f = c.get("fuente")
        if not isinstance(f, dict) or f.get("ubicacion") != ubicacion:
            continue
        if r.control_id == CONTROL_FUENTE:
            if (f.get("referencia_pedida") or "") != referencia:
                otra_rama = True
                continue
            esta_rama = True
            observada = f.get("referencia_inmutable")
            inerte = []                 # una observacion nueva cierra la cadena
        elif r.control_id == CONTROL_INERTE and c.get("referencia") == referencia:
            # Encadenar de verdad y no por pertenencia: `desde` tiene que ser
            # la CABEZA, no un eslabon cualquiera. Con pertenencia, dos
            # anotaciones que salen del mismo commit habrian formado una
            # bifurcacion y la cadena habria dicho que se paso por las dos.
            if c.get("desde") == (inerte[-1] if inerte else observada):
                inerte.append(str(c.get("hasta")))
    if observada is not None:
        return observada, tuple(inerte), "observada"
    return None, (), ("sin_referencia" if esta_rama else
                      "otra_rama" if otra_rama else "nunca")


def cmd_empujon(a: argparse.Namespace) -> int:
    """Traduce un empujon y dice QUE HACER con el. No hace nada: lo dice.

    Separar la decision de la ejecucion es lo que permite comprobarla, y es
    tambien lo que permite que esto corra en el borde -- en la funcion que
    recibe el webhook -- sin traer el codigo de nadie. La decision cuesta una
    comparacion de cadenas; reobservar cuesta un clon.
    """
    from .conectores.eventos import (Decision, NoSeEntiende, decidir,
                                     lector_del_motor, traducir)

    crudo = sys.stdin.read() if a.payload == "-" else Path(a.payload).read_text(encoding="utf-8")
    try:
        empujon = traducir(json.loads(crudo), a.id_del_evento or "")
    except json.JSONDecodeError as e:
        aviso = {"es": f"el cuerpo del evento no es JSON: {e}",
                 "en": f"the event body is not JSON: {e}"}
        return _no_traducible(a, aviso)
    except NoSeEntiende as e:
        # NO es ignorar: es un incidente de integracion. Codigo propio para que
        # un cron pueda distinguirlo de «no habia nada que hacer».
        return _no_traducible(a, {"es": str(e), "en": str(e)})

    alm = Almacen.abrir(a.almacen)
    visto, inerte, por_que = ((None, (), "nunca") if not Path(a.almacen).is_file()
                              else _posicion(alm, empujon.ubicacion, empujon.referencia))
    decision, motivo = decidir(
        empujon, visto, empujon.referencia_inmutable,
        lee_contenido=lector_del_motor(), inerte=inerte)
    if visto is None and por_que != "nunca":
        # «Nunca se observo este sujeto» habria sido falso: se observo la
        # ubicacion, pero otra rama, o sin referencia con la que repetirlo.
        motivo = _por_que_no_hay_con_que_comparar(por_que, empujon)

    salida = {"esquema": "actaira/decision-de-empujon/v1",
              "empujon": empujon.a_json(), "decision": decision.value,
              "motivo": motivo, "ultimo_observado": visto,
              "cadena_inerte": list(inerte),
              "cuesta_computo": decision.cuesta_computo}
    if decision is Decision.IGNORAR:
        salida["si_no_se_registra"] = {
            "es": ("este empujón no mueve nada por sí solo: sin `--registrar`, el siguiente "
                   "empujón saldrá de un commit que el almacén no conoce y costará una "
                   "observación"),
            "en": ("this push moves nothing on its own: without `--registrar`, the next push "
                   "will start from a commit the store does not know and will cost an "
                   "observation")}
    if a.registrar and decision is Decision.IGNORAR:
        desde = inerte[-1] if inerte else visto
        reg = Registro.nuevo(
            obligacion_id="AIA-000", control_id=CONTROL_INERTE,
            sujeto_digest=digest({"ubicacion": empujon.ubicacion,
                                  "referencia": empujon.referencia}),
            observado_en=ahora_de(a),
            contenido={"fuente": {"ubicacion": empujon.ubicacion},
                       "referencia": empujon.referencia,
                       "desde": desde, "hasta": empujon.referencia_inmutable,
                       "id_del_evento": empujon.id_del_evento,
                       "modificados": list(empujon.modificados),
                       "por_que": motivo,
                       "no_es_una_observacion": {
                           "es": ("el árbol no se ha mirado: esto anota que el proveedor "
                                  "declaró qué ficheros cambiaron y que ninguno lo abre el "
                                  "motor"),
                           "en": ("the tree has not been looked at: this records that the "
                                  "provider declared which files changed and that the engine "
                                  "opens none of them")}},
            frescura_dias=None)
        alm.anadir([reg], ahora_de(a))
        salida["registrado"] = CONTROL_INERTE
        salida.pop("si_no_se_registra", None)

    if a.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
    else:
        print(f"{empujon.proveedor}: {empujon.ubicacion} {empujon.referencia} "
              f"-> {empujon.referencia_inmutable[:12]}")
        print(f"  {decision.value}: {motivo[a.idioma]}")
        if inerte:
            print(f"  cadena sin observar: {len(inerte)} empujon(es) desde {(visto or '')[:8]}")
        if "si_no_se_registra" in salida:
            print("  " + salida["si_no_se_registra"][a.idioma])
        if "registrado" in salida:
            print(f"  anotado en {a.almacen} (no es una observacion: el arbol no se ha mirado)")
    return SALIDA_PENDIENTE if decision.cuesta_computo else SALIDA_LIMPIO


def _no_traducible(a: argparse.Namespace, motivo: dict[str, str]) -> int:
    """Un cuerpo que no se entiende SALE con la misma forma que los demas.

    Quien recibe webhooks quiere una sola forma de respuesta, y no dos: una
    JSON cuando hay decision y un texto suelto cuando no. Por eso el cuarto
    valor del enumerado existe y se emite, en vez de quedarse de adorno.
    """
    from .conectores.eventos import Decision

    if a.json:
        print(json.dumps({"esquema": "actaira/decision-de-empujon/v1",
                          "decision": Decision.NO_TRADUCIBLE.value, "motivo": motivo,
                          "cuesta_computo": False}, ensure_ascii=False, indent=2))
    print(motivo["es"], file=sys.stderr)
    return SALIDA_ERROR


def _por_que_no_hay_con_que_comparar(por_que: str, empujon: Any) -> dict[str, str]:
    if por_que == "otra_rama":
        return {"es": (f"de esta ubicación sí hay observaciones, pero no de «"
                       f"{empujon.referencia}»: una rama que nunca se miró no se revalida"),
                "en": (f"there are observations for this location, but not for "
                       f"«{empujon.referencia}»: a branch never looked at is not revalidated")}
    return {"es": ("la fuente registrada no tiene referencia inmutable, así que no hay contra "
                   "qué comparar: se observó, pero de una manera que no se puede repetir"),
            "en": ("the registered source has no immutable reference, so there is nothing to "
                   "compare against: it was observed, but in a way that cannot be repeated")}


def ahora_de(a: argparse.Namespace) -> datetime:
    """El reloj, como argumento y nunca como llamada escondida."""
    return (datetime.now(timezone.utc) if getattr(a, "ahora", None) is None
            else datetime.fromisoformat(a.ahora))


def cmd_conectar(a: argparse.Namespace) -> int:
    """Trae el codigo de donde este y corre el plan sobre el, sin dejar copia.

    El destino es TEMPORAL y se borra al terminar. Lo que se queda es el
    expediente, que lleva el digest del sujeto y la fuente con su referencia
    inmutable; el codigo del cliente no se queda en ninguna parte, que es la
    tercera regla del contrato de conector.
    """
    import shutil
    import tempfile

    from .conectores.contrato import elegir, sin_secretos

    try:
        conector = elegir(a.ubicacion)
        fuente = conector.fuente(a.ubicacion, a.referencia or "")
    except (ValueError, Exception) as e:   # ErrorDelConector hereda de Exception
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        print(str(e), file=sys.stderr)
        return SALIDA_ERROR

    filtrados = sin_secretos(json.dumps(fuente.a_json(), ensure_ascii=False))
    if filtrados:
        # No se emite. Un token dentro de un expediente firmado obliga a
        # retirar el expediente entero: no se puede editar sin romper la firma
        # y no se puede dejar.
        print(f"la fuente lleva algo que parece una credencial ({filtrados[0]}): no se emite",
              file=sys.stderr)
        return SALIDA_ERROR

    if not fuente.reproducible and not a.acepto_que_no_se_puede_repetir:
        print("Esta fuente NO tiene referencia inmutable, asi que la observacion no se podra\n"
              "repetir sobre el mismo contenido. Si te vale igual, dilo:\n"
              "  --acepto-que-no-se-puede-repetir")
        return SALIDA_ERROR

    tmp = Path(tempfile.mkdtemp(prefix="actaira-"))
    try:
        raiz = conector.materializar(fuente, tmp / "arbol")
        cat = cargar(a.catalogo)
        perfil = Perfil(
            roles=_roles(a), es_alto_riesgo=_tri(a.alto_riesgo),
            es_sector_publico=_tri(a.sector_publico),
            provee_modelo_uso_general=_tri(a.modelo_uso_general),
            modelo_con_riesgo_sistemico=_tri(a.riesgo_sistemico),
            via_anexo=getattr(a, "via_anexo", None))
        plan = construir_plan(cat, perfil, date.fromisoformat(a.fecha), str(raiz), a.reglas)
        plan["fuente"] = fuente.a_json()
        plan["limites_del_conector"] = [l.a_json() for l in conector.limites()]
        if a.registrar:
            # Se guarda la FUENTE, no el codigo. Es lo que permite que el
            # siguiente empujon se decida comparando dos cadenas en el borde,
            # sin clonar nada: el argumento de coste entero depende de esto.
            alm = Almacen.abrir(a.almacen)
            reg = Registro.nuevo(
                obligacion_id="AIA-000", control_id="ACT-C-FUENTE",
                sujeto_digest=digest(fuente.a_json()), observado_en=ahora_de(a),
                contenido={"fuente": fuente.a_json()}, frescura_dias=None)
            alm.anadir([reg], ahora_de(a))
            print(f"fuente registrada en {a.almacen}")
        if a.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(f"{conector.nombre}: {fuente.ubicacion}")
            print(f"  referencia: {fuente.referencia_pedida} -> "
                  f"{fuente.referencia_inmutable or '(no reproducible)'}")
            print(json.dumps(plan["recuento"], ensure_ascii=False))
            print("  lo que este conector NO trae:")
            for l in conector.limites():
                print(f"    - {l.que[a.idioma]}")
        return _salida_del_plan(plan)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_noconformidad(a: argparse.Namespace) -> int:
    """La clausula 10.2 desde la linea de mandatos, sin boton de cerrar.

    `avanzar --a verificada` EXIGE `--evidencia-de-eficacia`, y el que se
    construye la transicion revienta sin ella. Es la unica manera que conozco
    de que un ciclo de mejora no se convierta en una lista de tareas hechas:
    que cerrar cueste aportar algo que se observo DESPUES.
    """
    from .gestion.noconformidad import (EstadoNC, Transicion, desatendidas,
                                        todas_del_almacen)

    alm = Almacen.abrir(a.almacen)
    ahora = datetime.now(timezone.utc) if a.ahora is None else datetime.fromisoformat(a.ahora)

    if a.accion == "listar":
        ncs = todas_del_almacen(alm) if Path(a.almacen).is_file() else []
        if a.json:
            # Era una lista suelta, que no es un documento: no declaraba
            # version, no se podia extender sin romper a quien la leyera por
            # posicion, y no tenia sitio donde decir que ejecutada no es
            # cerrada. Un array no tiene donde decir quien es.
            cuenta: dict[str, int] = {e.value: 0 for e in EstadoNC}
            for n in ncs:
                cuenta[n.estado.value] += 1
            from .vocabulario import nombres_de
            print(json.dumps({
                "esquema": "actaira/noconformidades/v1",
                "nombres_de_estado": nombres_de(
                    [e.value for e in EstadoNC] + ["vencidas", "estancadas", "incoherentes"]),
                "recuento": {**cuenta,
                             "vencidas": sum(1 for n in ncs if n.vencida(ahora)),
                             "estancadas": sum(1 for n in ncs if n.estancada(ahora)),
                             "incoherentes": sum(1 for n in ncs if n.incoherencias())},
                "no_conformidades": [
                    {**n.a_json(), "vencida": n.vencida(ahora),
                     "estancada": n.estancada(ahora),
                     "dias_abierta": n.dias_abierta(ahora),
                     "incoherencias": n.incoherencias()} for n in ncs],
                "nota_del_cierre": {
                    "es": "solo VERIFICADA está cerrada: EJECUTADA es «lo hicimos», no "
                          "«funcionó», y la cláusula 10.2 pide revisar la eficacia",
                    "en": "only VERIFICADA is closed: EJECUTADA is «we did it», not «it "
                          "worked», and clause 10.2 requires reviewing effectiveness"},
            }, ensure_ascii=False, indent=2))
        else:
            for n in ncs:
                if n.vencida(ahora):
                    marca = " VENCIDA"
                elif n.estancada(ahora):
                    marca = " ESTANCADA"
                else:
                    marca = ""
                print(f"  {n.estado.value:<12} {n.id:<10} {n.dias_abierta(ahora):>4}d"
                      f"{marca}  {n.descripcion[:60]}")
                for mal in n.incoherencias():
                    print(f"      INCOHERENTE  {mal}")
            if not ncs:
                print("no hay ninguna no conformidad en el almacen")
        # Una incoherencia pesa como una vencida: una no conformidad cerrada
        # sin haber ejecutado nada es peor que una abierta y tarde, porque la
        # primera ya no la mira nadie.
        malas = desatendidas(ncs, ahora) or [n for n in ncs if n.incoherencias()]
        return SALIDA_HALLAZGOS if malas else SALIDA_LIMPIO

    try:
        t = Transicion(
            no_conformidad_id=a.id, a=EstadoNC(a.a if a.accion == "avanzar" else "abierta"),
            quien=a.quien, cargo=a.cargo, cuando=ahora.isoformat(), nota=a.nota or "",
            causa_raiz=a.causa_raiz, accion=a.accion_correctiva, responsable=a.responsable,
            compromiso=a.compromiso, evidencia_de_eficacia=a.evidencia_de_eficacia,
            origen=a.origen, descripcion=a.descripcion)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return SALIDA_ERROR
    alm.anadir([t.a_registro()], ahora)
    print(f"{a.id}: {t.a.value}")
    if t.a is EstadoNC.EJECUTADA:
        print("  ejecutada NO es cerrada: la clausula 10.2 pide revisar si la accion funciono,\n"
              "  y eso es una observacion posterior. Cierra con `avanzar --a verificada`.")
    return SALIDA_LIMPIO


CONTROL_DELEGACION = "ACT-R-DELEGACION"


def cmd_remediar(a: argparse.Namespace) -> int:
    """Delega la remediacion donde el cliente trabaja, y la trae de vuelta con techo.

    Dos acciones y una negativa. `abrir` saca el encargo al sistema de tickets;
    `sincronizar` lee lo que ese sistema dice y mueve la no conformidad HASTA
    ejecutada y ni un paso mas. VERIFICADA no sale de aqui nunca: exige una
    evidencia de eficacia tomada DESPUES, y el estado de un tablero no la
    aporta.
    """
    from .gestion.noconformidad import todas_del_almacen
    from .remediacion.contrato import elegir, emitible
    from .remediacion.encargo import de_no_conformidad as encargo_de
    from .remediacion.rest import ErrorDelRemediador
    from .remediacion.traduccion import EstadoQueNoConocemos, leer, mover

    alm = Almacen.abrir(a.almacen)
    ahora = ahora_de(a)
    ncs = {n.id: n for n in (todas_del_almacen(alm) if Path(a.almacen).is_file() else [])}

    try:
        remediador = elegir(a.destino, perfil=getattr(a, "perfil", "") or "")
    except (ValueError, ErrorDelRemediador) as e:
        print(str(e), file=sys.stderr)
        return SALIDA_ERROR

    if a.accion == "abrir":
        nc = ncs.get(a.id)
        if nc is None:
            print(f"no hay ninguna no conformidad {a.id!r} en {a.almacen}", file=sys.stderr)
            return SALIDA_ERROR
        if not (a.responsable and a.compromiso):
            print("abrir un encargo exige --responsable y --compromiso: una accion sin dueno "
                  "y sin fecha es una intencion.", file=sys.stderr)
            return SALIDA_ERROR
        try:
            encargo, procedencia = encargo_de(
                nc, a.reglas, responsable=a.responsable, compromiso=a.compromiso,
                severidad=a.severidad, obligacion=a.obligacion,
                localizaciones=tuple(a.localizacion or ()))

            if getattr(a, "simular", False):
                # SIMULAR: ensena lo que saldria y NO llama a nadie.
                #
                # Una auditoria externa lo pidio como «modo solo lectura y
                # simulacion», y el motivo es concreto: lo que sale de aqui
                # entra en el sistema donde el cliente organiza su trabajo, que
                # lo lee muchisima mas gente que un expediente firmado. Un
                # ticket mal redactado no se borra: se queda, lo lee todo el
                # equipo, y cuesta mas explicarlo que haberlo revisado antes.
                #
                # Y tampoco se ESCRIBE en el almacen. Una simulacion que dejara
                # una linea de evidencia seria una delegacion que no existe
                # dentro de un expediente que dice que si, que es peor que no
                # tener simulacion.
                salida = {
                    "esquema": "actaira/simulacion-de-encargo/v1",
                    "simulado": True,
                    "sistema": remediador.nombre,
                    "version_del_remediador": remediador.version,
                    "destino": remediador.destino,
                    "encargo": encargo.a_json(),
                    "procedencia_del_texto": procedencia,
                    "limites": [l.a_json() for l in remediador.limites()],
                    "nota": {
                        "es": "Nada de esto se ha mandado a ninguna parte y NADA se ha "
                              "escrito en el almacén. Es lo que saldría si quitas "
                              "`--simular`. Los límites de abajo seguirán siendo los "
                              "mismos: delegar no cierra una no conformidad.",
                        "en": "None of this was sent anywhere and NOTHING was written to "
                              "the store. It is what would go out if you drop "
                              "`--simular`. The limits below will be the same: "
                              "delegating does not close a nonconformity."},
                }
                if a.json:
                    print(json.dumps(salida, ensure_ascii=False, indent=2))
                else:
                    print(f"SIMULACION — no se ha mandado nada a {remediador.nombre} "
                          f"({remediador.destino}) y no se ha escrito en el almacen\n")
                    print(f"  titulo: {encargo.titulo[a.idioma]}")
                    print(f"  responsable: {encargo.responsable}")
                    print(f"  fecha comprometida: {encargo.compromiso}")
                    print(f"  severidad: {encargo.severidad}")
                    print(f"  origen: {encargo.obligacion_id} / {encargo.control_id}")
                    print("\n  cuerpo:")
                    for linea in encargo.texto(a.idioma).splitlines():
                        print(f"    {linea}")
                    print(f"\n  {procedencia[a.idioma]}")
                    print("  lo que delegar NO hace:")
                    for l in remediador.limites():
                        print(f"    - {l.que[a.idioma]}")
                # Codigo 3: no es limpio -- no se ha hecho el trabajo -- ni un
                # fallo. Es «falta que alguien decida», que es exactamente lo
                # que una simulacion deja pendiente.
                return SALIDA_PENDIENTE

            delegacion = remediador.abrir(encargo, a.idioma)
        except (ValueError, ErrorDelRemediador) as e:
            print(str(e), file=sys.stderr)
            return SALIDA_ERROR
        reg = Registro.nuevo(
            obligacion_id="ISO-10.2", control_id=CONTROL_DELEGACION,
            sujeto_digest=f"nc:{nc.id}", observado_en=ahora,
            contenido=emitible({"delegacion": delegacion.a_json(),
                                "encargo": encargo.a_json(),
                                "procedencia_del_texto": procedencia,
                                "limites": [l.a_json() for l in remediador.limites()]}),
            frescura_dias=None)
        alm.anadir([reg], ahora)
        if a.json:
            print(json.dumps(delegacion.a_json(), ensure_ascii=False, indent=2))
        else:
            print(f"{delegacion.sistema}: {delegacion.referencia}  {delegacion.url}")
            print(f"  {procedencia[a.idioma]}")
            print("  lo que delegar NO hace:")
            for l in remediador.limites():
                print(f"    - {l.que[a.idioma]}")
        return SALIDA_LIMPIO

    # --- sincronizar ------------------------------------------------------
    delegaciones = _delegaciones_del_almacen(alm)
    if a.id:
        delegaciones = [d for d in delegaciones if d.no_conformidad_id == a.id]
    if not delegaciones:
        print("no hay ninguna delegacion registrada todavia: abre una con "
              "`remediar abrir --id ...`")
        return SALIDA_LIMPIO

    movidas, quietas, ciegas, lecturas = 0, [], [], []
    for d in delegaciones:
        nc = ncs.get(d.no_conformidad_id)
        if nc is None:
            ciegas.append((d, "la no conformidad que delego esto ya no esta en el almacen"))
            continue
        if d.sistema != getattr(remediador, "sistema", remediador.nombre):
            # Encontrado atacando esto: con una delegacion en Jira y un
            # --destino de carpeta, el remediador de fichero devolvia la
            # delegacion intacta y su estado se traducia como si se hubiera
            # preguntado a Jira. Nunca se pregunto a nadie.
            ciegas.append((d, f"esta delegacion es de {d.sistema} y este destino habla "
                              f"{getattr(remediador, 'sistema', remediador.nombre)}: "
                              f"consultarla aqui habria dado un estado que nadie pregunto"))
            continue
        try:
            fresca = remediador.consultar(d)
            lectura = leer(fresca)
        except (ErrorDelRemediador, EstadoQueNoConocemos) as e:
            # Un estado que no se entiende NO es un estado sin cambios: el
            # ciclo se pararia en una columna nueva sin que nadie se enterara.
            ciegas.append((d, str(e)))
            continue
        lecturas.append(lectura)
        t, por_que = mover(nc.estado, lectura, a.cargo or "")
        if t is None:
            quietas.append((d, por_que))
            continue
        emitible(t.a_json())
        alm.anadir([t.a_registro()], ahora)
        movidas += 1
        if not a.json:
            print(f"  {d.referencia:<14} {nc.id:<10} -> {t.a.value}  ({por_que[a.idioma]})")
    if a.json:
        print(json.dumps({"lecturas": [l.a_json() for l in lecturas],
                          "movidas": movidas,
                          "sin_cambios": [{"referencia": d.referencia, "por_que": pq}
                                          for d, pq in quietas],
                          "ilegibles": [{"referencia": d.referencia, "por_que": str(m)}
                                        for d, m in ciegas],
                          "techo": {
                              "es": "ninguna de estas llega a VERIFICADA: cerrar exige una "
                                    "evidencia de eficacia tomada DESPUES de ejecutar",
                              "en": "none of these reaches VERIFICADA: closing requires "
                                    "effectiveness evidence taken AFTER execution"}},
                         ensure_ascii=False, indent=2))
        return SALIDA_PENDIENTE if ciegas else SALIDA_LIMPIO
    for d, por_que in quietas:
        texto = por_que[a.idioma] if isinstance(por_que, dict) else str(por_que)
        print(f"  {d.referencia:<14} {d.no_conformidad_id:<10} sin cambios: {texto}")
    for d, mal in ciegas:
        print(f"  {d.referencia:<14} {d.no_conformidad_id:<10} NO SE PUDO LEER: {mal}",
              file=sys.stderr)
    print(f"{movidas} movidas, {len(quietas)} sin cambios, {len(ciegas)} ilegibles")
    if movidas or quietas:
        print("ninguna de estas llega a VERIFICADA: cerrar exige una evidencia de eficacia\n"
              "tomada DESPUES de ejecutar, y el estado de un tablero no la aporta.")
    # Una delegacion que no se puede leer es «no se pudo decidir», y no «no hay
    # nada»: son dos cosas que una puerta de integracion continua trata
    # distinto, y fundirlas hace que una integracion rota parezca una pasada
    # limpia durante meses.
    return SALIDA_PENDIENTE if ciegas else SALIDA_LIMPIO


def _delegaciones_del_almacen(alm: "Almacen") -> list:
    """La ultima delegacion de cada no conformidad, en orden de llegada."""
    from .remediacion.contrato import Delegacion

    ultimas: dict[str, Delegacion] = {}
    for r in alm.registros():
        if r.control_id != CONTROL_DELEGACION:
            continue
        d = (r.contenido or {}).get("delegacion") or {}
        if not d.get("referencia"):
            continue
        ultimas[d["no_conformidad_id"]] = Delegacion(
            sistema=d["sistema"], referencia=d["referencia"], url=d.get("url", ""),
            no_conformidad_id=d["no_conformidad_id"],
            estado_externo=d.get("estado_externo", ""), actor=d.get("actor", ""),
            cargo_del_actor=d.get("cargo_del_actor", ""), cuando=d.get("cuando", ""),
            detalles=d.get("detalles", {}))
    return list(ultimas.values())


def cmd_revision(a: argparse.Namespace) -> int:
    """La carpeta de entrada de la revision por la direccion, no el acta.

    Sale 3 cuando falta alguna de las entradas que la clausula 9.3.2 enumera,
    porque eso es trabajo y no un fallo del mandato: quien lo corra en un cron
    la vispera del comite quiere saber que le falta, no que reviente.
    """
    from .expediente.revision import a_markdown, generar

    cat = cargar(a.catalogo)
    alm = Almacen.abrir(a.almacen)
    ahora = datetime.now(timezone.utc) if a.ahora is None else datetime.fromisoformat(a.ahora)
    regs = alm.registros() if Path(a.almacen).is_file() else []
    from .gestion.noconformidad import todas_del_almacen
    ncs = todas_del_almacen(alm) if Path(a.almacen).is_file() else []
    doc = generar(cat, regs, ahora, revalidaciones=alm.revalidaciones(),
                  revocadas=alm.revocadas(), no_conformidades=ncs, idioma=a.idioma)
    if a.salida:
        Path(a.salida).write_text(a_markdown(doc, a.idioma), encoding="utf-8")
        print(f"revision escrita en {a.salida}")
    if a.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(doc["recuento"], ensure_ascii=False))
        for f in doc["entradas"]:
            print(f"  {f['situacion']:<10} {f['texto'][a.idioma]}")
    return SALIDA_PENDIENTE if doc["que_falta"] else SALIDA_LIMPIO


def cmd_almacen(a: argparse.Namespace) -> int:
    """Comprueba que el almacen sigue siendo la cadena que esta casa escribio.

    Es un verbo aparte y no un aviso dentro de `vigilar` a proposito: quien
    necesita esto es quien opera la integracion continua justo DESPUES de
    escribir, y quien audita el expediente meses despues. Los dos quieren una
    respuesta y un codigo de salida, no una linea perdida entre cuarenta.
    """
    alm = Almacen.abrir(a.almacen)
    if a.accion == "migrar":
        if not a.destino:
            print("migrar necesita --destino: no se escribe encima de un almacen")
            return SALIDA_ERROR
        if not a.acepto_que_no_se_puede_demostrar:
            print("Un almacen sin cadena de sellos NO se puede declarar intacto: no habia\n"
                  "nada que lo demostrara. Migrarlo lo encadena de aqui en adelante y marca\n"
                  "cada linea vieja como `migrada_sin_cadena`, dentro del sello, para que la\n"
                  "marca no se pueda quitar. Si eso es lo que quieres, dilo:\n"
                  "  actaira almacen migrar --almacen X --destino Y "
                  "--acepto-que-no-se-puede-demostrar")
            return SALIDA_ERROR
        rota = alm.primera_rotura()
        if rota is not None and not a.acepto_una_cadena_rota:
            # Son DOS afirmaciones distintas y por eso son dos banderas.
            #
            # «Este almacen no tenia cadena» es la version anterior del motor y
            # no implica que nadie lo tocara. «Este almacen tenia cadena y no
            # cuadra» es que alguien lo edito, le quito una linea o las cambio
            # de orden. Una sola bandera para las dos convertiria la primera --
            # que es rutina al actualizar -- en el permiso para la segunda.
            print(f"La cadena de {a.almacen} se rompe en la linea {rota}. Migrar reescribe\n"
                  f"los sellos, asi que lo que entra roto saldria con una cadena nueva y\n"
                  f"valida: la rotura desapareceria del expediente en vez de constar en el.\n"
                  f"Si aun asi quieres conservar el contenido, dilo aparte:\n"
                  f"  actaira almacen migrar --almacen X --destino Y \\\n"
                  f"    --acepto-que-no-se-puede-demostrar --acepto-una-cadena-rota\n"
                  f"Cada linea desde la {rota} saldra marcada `migrada_desde_cadena_rota`.")
            for motivo in alm.verificar_cadena():
                print(f"  {motivo}")
            return SALIDA_ALTERADO
        migradas, ya = alm.migrar_a(Almacen.abrir(a.destino),
                                    aceptar_cadena_rota=a.acepto_una_cadena_rota)
        print(f"migradas {migradas} lineas no demostrables y {ya} verificadas -> {a.destino}")
        marca = "migrada_desde_cadena_rota" if rota is not None else "migrada_sin_cadena"
        print(f"  esas {migradas} llevan `{marca}` DENTRO del sello y siempre lo diran")
        if rota is not None:
            print(f"  la cadena de origen se rompia en la linea {rota}: desde ahi van "
                  f"marcadas `migrada_desde_cadena_rota`")
        print(f"  cabeza: {Almacen.abrir(a.destino).cabeza()}")
        return SALIDA_LIMPIO
    if getattr(a, "json", False):
        # EL MISMO VEREDICTO, EN UN DOCUMENTO.
        #
        # Este verbo solo sabia imprimir prosa, y por eso la plataforma no podia
        # consumirlo: la API arrancaba el motor con `--json` y recibia un texto
        # que no es un documento, asi que contestaba «el motor no devolvio un
        # documento que esta plataforma entienda». El estado de la cadena de
        # evidencia -- si verifica, cual es su cabeza, cuantas lineas no se
        # puede demostrar que esten intactas -- es justo lo que una pantalla de
        # procedencia tiene que ensenar, y no habia forma de pedirlo.
        #
        # El documento sale de las MISMAS llamadas que la prosa de abajo. No se
        # recalcula nada aqui: dos caminos que respondan a la misma pregunta
        # acabarian discrepando, y el dia que lo hagan nadie sabria cual creer.
        hay = Path(a.almacen).is_file()
        roturas = alm.verificar_cadena() if hay else []
        doc = {
            "esquema": "actaira/almacen/v1",
            "ruta": str(a.almacen),
            "existe": hay,
            "verifica": hay and not roturas,
            "roturas": roturas,
            "observaciones": len(alm.registros()) if hay and not roturas else 0,
            "cabeza": alm.cabeza() if hay and not roturas else None,
            "sin_cadena_demostrable": (
                alm.sin_cadena_demostrable() if hay and not roturas else 0),
            "cabeza_esperada": a.cabeza_esperada or None,
            "cabeza_es_la_esperada": None,
            "nota_de_la_cabeza": {
                "es": "Que la cadena verifique demuestra que el fichero es consistente "
                      "consigo mismo, y NO que estén todas las líneas: quitarle las "
                      "últimas deja un prefijo que verifica igual. Lo único que detecta "
                      "eso es haber anotado FUERA la cabeza de antes y volver a pasarla.",
                "en": "A chain that verifies proves the file is consistent with itself, "
                      "and NOT that every line is there: dropping the last ones leaves a "
                      "prefix that verifies just the same. The only thing that detects "
                      "that is having recorded the previous head OUTSIDE and passing it "
                      "back."},
        }
        if a.cabeza_esperada and doc["verifica"]:
            mal = alm.comprobar_cabeza(a.cabeza_esperada.strip())
            doc["cabeza_es_la_esperada"] = mal is None
            doc["por_que_no_es_la_esperada"] = mal
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        if not doc["verifica"] and hay:
            return SALIDA_ALTERADO
        if doc["cabeza_es_la_esperada"] is False:
            return SALIDA_ALTERADO
        return SALIDA_LIMPIO

    if not Path(a.almacen).is_file():
        print(f"no hay almacen en {a.almacen}: nada que verificar")
        return SALIDA_LIMPIO
    roturas = alm.verificar_cadena()
    if roturas:
        print("EL ALMACEN NO ES EL QUE SE ESCRIBIO")
        for r in roturas:
            print("  " + r)
        print("\n  Una linea editada a mano no es evidencia nueva: es un incidente.\n"
              "  El expediente anterior a la rotura sigue valiendo; a partir de ahi, no.")
        return SALIDA_ALTERADO
    n = len(alm.registros())
    print(f"cadena intacta: {n} observaciones")
    print(f"cabeza: {alm.cabeza()}")
    if a.cabeza_esperada:
        mal = alm.comprobar_cabeza(a.cabeza_esperada.strip())
        if mal:
            print("\nLA CABEZA NO ES LA ESPERADA\n  " + mal)
            return SALIDA_ALTERADO
        print("  y es la cabeza esperada: tampoco le han quitado lineas del final")
        return SALIDA_LIMPIO
    print("  Esto demuestra que el fichero es consistente consigo mismo, y NO que "
          "esten\n  todas las lineas: quitarle las ultimas deja un prefijo que "
          "verifica igual.\n  Guarda esta cabeza y vuelve a pasarla con "
          "--cabeza-esperada, o publicala\n  dentro de un sello firmado.")
    return SALIDA_LIMPIO


def cmd_ortografia(a: argparse.Namespace) -> int:
    """Comprueba (o arregla) las tildes del castellano del catalogo.

    Sin `--arreglar` no escribe nada y devuelve 1 si algo falta, que es lo que
    corre la puerta. Con `--arreglar` reescribe los ficheros.
    """
    sucios = []
    # Tambien el castellano que vive DENTRO del codigo: los motivos de ausencia
    # del Anexo IV y las notas de las declaraciones se escriben en Python, no
    # en el catalogo, y se quedaron sin tildes hasta que el contrato de la fase
    # 11 los puso delante. La puerta del catalogo no los veia.
    raiz_motor = Path(__file__).resolve().parent
    for ruta in sorted(raiz_motor.rglob("*.py")):
        fuente = ruta.read_text(encoding="utf-8")
        nuevo = corregir_fuente(fuente)
        if nuevo == fuente:
            continue
        sucios.append(str(ruta.relative_to(raiz_motor.parents[2])))
        if a.arreglar:
            ruta.write_text(nuevo, encoding="utf-8")
    for ruta in sorted(Path(a.catalogo).rglob("*.json")):
        antes = json.loads(ruta.read_text(encoding="utf-8"))
        despues = corregir_es(antes)
        if antes == despues:
            continue
        sucios.append(str(ruta.relative_to(Path(a.catalogo).parent)))
        if a.arreglar:
            ruta.write_text(json.dumps(despues, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not sucios:
        print("el castellano del catálogo y del código lleva sus tildes")
        return 0
    print(("arreglados" if a.arreglar else "les faltan tildes") + f": {len(sucios)} ficheros")
    for x in sucios:
        print("  " + x)
    return 0 if a.arreglar else 1


def cmd_exportar(a: argparse.Namespace) -> int:
    Path(a.salida).write_text(
        json.dumps(exportar(cargar(a.catalogo)), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    print(f"tabla escrita en {a.salida}")
    return 0


def _tri(v: str | None) -> bool | None:
    return None if v in (None, "null") else v == "si"


def main(argv: list[str] | None = None) -> int:
    _salida_en_utf8()
    p = argparse.ArgumentParser(prog="actaira", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    a1 = sub.add_parser("aplicabilidad", help="que obligaciones atan a este perfil")
    a1.add_argument("--catalogo", default=str(CATALOGO))
    a1.add_argument("--rol", action="append", default=None,
                    help="repetible; si no se pasa ninguno, se asume proveedor")
    for n in ("alto-riesgo", "sector-publico", "modelo-uso-general", "riesgo-sistemico"):
        a1.add_argument(f"--{n}", choices=["si", "no", "null"], default="null")
    a1.add_argument("--via-anexo", choices=["anexo_iii", "anexo_i"], default=None,
                    help="por donde es de alto riesgo: anexo_iii (sistema autonomo del "
                         "articulo 6.2) o anexo_i (componente de seguridad de un producto "
                         "regulado, articulo 6.1). Decide la fecha: 2-dic-2027 o 2-ago-2028")
    a1.add_argument("--fecha", default=date.today().isoformat())
    a1.add_argument("--idioma", choices=["es", "en"], default="es")
    a1.add_argument("--json", action="store_true")
    a1.set_defaults(fn=lambda a: cmd_aplicabilidad(argparse.Namespace(
        **{**vars(a),
           "alto_riesgo": _tri(a.alto_riesgo), "sector_publico": _tri(a.sector_publico),
           "modelo_uso_general": _tri(a.modelo_uso_general), "riesgo_sistemico": _tri(a.riesgo_sistemico)})))

    a2 = sub.add_parser("comprobar", help="corre el control del articulo 50 sobre un repositorio")
    a2.add_argument("repo")
    # `--json` SE ACEPTA Y NO HACE NADA, y eso se dice.
    #
    # Este verbo no tiene otra salida: su unico formato es el documento. Pero la
    # plataforma le pasa `--json` a TODOS los verbos, porque lo que consume es
    # siempre un documento, y sin esta bandera `comprobar` moria por argumento
    # invalido y la capa de HTTP lo traducia a «el motor no devolvio un
    # documento que esta plataforma entienda» -- que es verdad y no dice nada.
    # Es el mismo defecto que ya tuvieron `noconformidad` y `preguntar`.
    #
    # La alternativa era que la plataforma llevara una lista de los verbos a los
    # que NO hay que pasarsela, y esa lista es exactamente la clase de tabla a
    # mano que se queda corta el dia que alguien anade un verbo.
    a2.add_argument("--json", action="store_true",
                    help="se acepta por uniformidad; este verbo solo habla JSON")
    a2.add_argument("--artefacto", action="append", default=[])
    a2.add_argument("--paso", action="append", default=[],
                    choices=list(CONOCIDAS),
                    help="un paso de tu cadena real de publicacion, en orden. Se puede repetir: `--paso redimensionar_mitad --paso a_jpeg`. El articulo 50(2) pide que la salida generada quede marcada de forma legible por maquina, y un marcado de metadatos lo destruye cualquier recompresion posterior, asi que la pregunta util no es si esta marcado sino si SIGUE marcado despues de tu cadena. Sin ningun paso no se mide esa durabilidad y el informe lo dice en `no_cubre`, en vez de dar por buena una cadena que no se ha visto. Pasos: recomprimir_jpeg_85, recomprimir_jpeg_60, redimensionar_mitad, recortar_10, rotar_90, a_jpeg, a_png, quitar_metadatos")
    a2.add_argument("--reglas", default=str(REGLAS_50))
    a2.set_defaults(fn=cmd_comprobar)

    a3 = sub.add_parser("sellar", help="emite el expediente firmado")
    a3.add_argument("repo")
    a3.add_argument("--artefacto", action="append", default=[])
    a3.add_argument("--paso", action="append", default=[],
                    choices=list(CONOCIDAS),
                    help="un paso de tu cadena real de publicacion, en orden. Se puede repetir: `--paso redimensionar_mitad --paso a_jpeg`. El articulo 50(2) pide que la salida generada quede marcada de forma legible por maquina, y un marcado de metadatos lo destruye cualquier recompresion posterior, asi que la pregunta util no es si esta marcado sino si SIGUE marcado despues de tu cadena. Sin ningun paso no se mide esa durabilidad y el informe lo dice en `no_cubre`, en vez de dar por buena una cadena que no se ha visto. Pasos: recomprimir_jpeg_85, recomprimir_jpeg_60, redimensionar_mitad, recortar_10, rotar_90, a_jpeg, a_png, quitar_metadatos")
    a3.add_argument("--reglas", default=str(REGLAS_50))
    a3.add_argument("--salida", default="sello.json")
    a3.add_argument("--clave")
    a3.add_argument("--frescura", type=int, default=90)
    a3.add_argument("--ahora")
    a3.set_defaults(fn=cmd_sellar)

    a4 = sub.add_parser("verificar", help="verifica un sello sin red")
    a4.add_argument("sello")
    a4.add_argument("--clave-esperada", default=None,
                    help="la clave publica Ed25519 que se espera (hex o fichero). "
                         "Sin ella se comprueba integridad, NO identidad.")
    a4.set_defaults(fn=cmd_verificar)

    a6 = sub.add_parser("plan", help="el ciclo entero: que te ata, que se comprobo y que hay que preguntarte")
    a6.add_argument("repo", nargs="?", default=None)
    a6.add_argument("--catalogo", default=str(CATALOGO))
    a6.add_argument("--reglas", default=str(CATALOGO / "reglas"))
    a6.add_argument("--rol", action="append", default=None,
                       help="repetible; si no se pasa ninguno, se asume proveedor")
    for n in ("alto-riesgo", "sector-publico", "modelo-uso-general", "riesgo-sistemico"):
        a6.add_argument(f"--{n}", choices=["si", "no", "null"], default="null")
    a6.add_argument("--via-anexo", choices=["anexo_iii", "anexo_i"], default=None,
                    help="por donde es de alto riesgo: anexo_iii (sistema autonomo del "
                         "articulo 6.2) o anexo_i (componente de seguridad de un producto "
                         "regulado, articulo 6.1). Decide la fecha: 2-dic-2027 o 2-ago-2028")
    a6.add_argument("--artefacto", action="append", default=[])
    a6.add_argument("--fecha", default=date.today().isoformat())
    a6.add_argument("--idioma", choices=["es", "en"], default="es")
    a6.add_argument("--sarif", help="escribe los hallazgos en SARIF 2.1.0 para la pestana Security")
    a6.add_argument("--json", action="store_true")
    a6.set_defaults(fn=cmd_plan)

    a7 = sub.add_parser("anexo", help="genera el Anexo IV o el Anexo V, con procedencia por seccion")
    a7.add_argument("repo")
    a7.add_argument("--catalogo", default=str(CATALOGO))
    a7.add_argument("--reglas", default=str(CATALOGO / "reglas"))
    a7.add_argument("--rol", action="append", default=None,
                       help="repetible; si no se pasa ninguno, se asume proveedor")
    for n in ("alto-riesgo", "sector-publico", "modelo-uso-general", "riesgo-sistemico"):
        a7.add_argument(f"--{n}", choices=["si", "no", "null"], default="null")
    a7.add_argument("--via-anexo", choices=["anexo_iii", "anexo_i"], default=None,
                    help="por donde es de alto riesgo: anexo_iii (sistema autonomo del "
                         "articulo 6.2) o anexo_i (componente de seguridad de un producto "
                         "regulado, articulo 6.1). Decide la fecha: 2-dic-2027 o 2-ago-2028")
    a7.add_argument("--cual", choices=["iv", "v"], default="iv",
                    help="iv, la documentacion tecnica; v, la declaracion UE de conformidad")
    a7.add_argument("--aportes", help="JSON con las secciones que escribio una persona")
    a7.add_argument("--respuestas", help="JSON con lo que contesto una persona (lo usa el Anexo V)")
    a7.add_argument("--clave-esperada", default=None,
                     help="la clave publica que esperas que haya firmado la "
                          "declaracion de --respuestas. Sin ella, una declaracion "
                          "firmada demuestra que quien tenga ESA clave la firmo, no "
                          "quien es, y cada respuesta entra en el expediente marcada "
                          "`firmada` en vez de `identidad_verificada`. Una sin firma "
                          "entra marcada `sin_firma`, que es lo que es.")
    a7.add_argument("--fecha", default=date.today().isoformat())
    a7.add_argument("--idioma", choices=["es", "en"], default="es")
    a7.add_argument("--json", action="store_true")
    a7.set_defaults(fn=cmd_anexo)

    a8 = sub.add_parser("preguntar", help="que le queda por contestar a una persona, y que ya contesto el codigo")
    a8.add_argument("repo", nargs="?", default=None)
    a8.add_argument("--catalogo", default=str(CATALOGO))
    a8.add_argument("--reglas", default=str(CATALOGO / "reglas"))
    a8.add_argument("--rol", action="append", default=None,
                       help="repetible; si no se pasa ninguno, se asume proveedor")
    for n in ("alto-riesgo", "sector-publico", "modelo-uso-general", "riesgo-sistemico"):
        a8.add_argument(f"--{n}", choices=["si", "no", "null"], default="null")
    a8.add_argument("--via-anexo", choices=["anexo_iii", "anexo_i"], default=None,
                    help="por donde es de alto riesgo: anexo_iii (sistema autonomo del "
                         "articulo 6.2) o anexo_i (componente de seguridad de un producto "
                         "regulado, articulo 6.1). Decide la fecha: 2-dic-2027 o 2-ago-2028")
    a8.add_argument("--respuestas", help="JSON con lo que ya se contesto")
    a8.add_argument("--clave-esperada", default=None,
                     help="la clave publica que esperas que haya firmado la "
                          "declaracion de --respuestas. Sin ella, una declaracion "
                          "firmada demuestra que quien tenga ESA clave la firmo, no "
                          "quien es, y cada respuesta entra en el expediente marcada "
                          "`firmada` en vez de `identidad_verificada`. Una sin firma "
                          "entra marcada `sin_firma`, que es lo que es.")
    a8.add_argument("--destinatario", choices=["direccion", "responsable", "tecnico"])
    a8.add_argument("--fecha", default=date.today().isoformat())
    a8.add_argument("--idioma", choices=["es", "en"], default="es")
    a8.add_argument("--json", action="store_true")
    a8.set_defaults(fn=cmd_preguntar)

    a9 = sub.add_parser("contestar", help="sella las respuestas de una persona como evidencia firmada")
    a9.add_argument("respuestas")
    a9.add_argument("--catalogo", default=str(CATALOGO))
    a9.add_argument("--salida", default="declaracion.json")
    a9.add_argument("--clave")
    a9.add_argument("--ahora")
    a9.set_defaults(fn=cmd_contestar)

    a10 = sub.add_parser("soa", help="la declaracion de aplicabilidad de la ISO 42001, derivada del Reglamento")
    a10.add_argument("repo", nargs="?", default=None)
    a10.add_argument("--catalogo", default=str(CATALOGO))
    a10.add_argument("--reglas", default=str(CATALOGO / "reglas"))
    a10.add_argument("--rol", action="append", default=None,
                       help="repetible; si no se pasa ninguno, se asume proveedor")
    for n in ("alto-riesgo", "sector-publico", "modelo-uso-general", "riesgo-sistemico"):
        a10.add_argument(f"--{n}", choices=["si", "no", "null"], default="null")
    a10.add_argument("--via-anexo", choices=["anexo_iii", "anexo_i"], default=None,
                    help="por donde es de alto riesgo: anexo_iii (sistema autonomo del "
                         "articulo 6.2) o anexo_i (componente de seguridad de un producto "
                         "regulado, articulo 6.1). Decide la fecha: 2-dic-2027 o 2-ago-2028")
    a10.add_argument("--respuestas", help="JSON con lo que ya contesto una persona")
    a10.add_argument("--clave-esperada", default=None,
                     help="la clave publica que esperas que haya firmado la "
                          "declaracion de --respuestas. Sin ella, una declaracion "
                          "firmada demuestra que quien tenga ESA clave la firmo, no "
                          "quien es, y cada respuesta entra en el expediente marcada "
                          "`firmada` en vez de `identidad_verificada`. Una sin firma "
                          "entra marcada `sin_firma`, que es lo que es.")
    a10.add_argument("--decisiones", help="JSON con las inclusiones y exclusiones ya firmadas")
    a10.add_argument("--aprobada", help='JSON en linea: {"quien":..,"cargo":..,"cuando":..}')
    a10.add_argument("--fecha", default=date.today().isoformat())
    a10.add_argument("--idioma", choices=["es", "en"], default="es")
    a10.add_argument("--json", action="store_true")
    a10.set_defaults(fn=cmd_soa)

    a12 = sub.add_parser("vigilar", help="que sigue valiendo, que caduco y que hay que volver a mirar")
    a12.add_argument("repo", nargs="?", default=None)
    a12.add_argument("--solo-almacen", action="store_true", dest="solo_almacen",
                     help="no barre el repositorio: solo dice que caduco, que es lo que "
                          "necesita el vencimiento de la plataforma")
    a12.add_argument("--almacen", default="estado/evidencia.jsonl")
    a12.add_argument("--catalogo", default=str(CATALOGO))
    a12.add_argument("--reglas", default=str(CATALOGO / "reglas"))
    a12.add_argument("--rol", action="append", default=None,
                       help="repetible; si no se pasa ninguno, se asume proveedor")
    for n in ("alto-riesgo", "sector-publico", "modelo-uso-general", "riesgo-sistemico"):
        a12.add_argument(f"--{n}", choices=["si", "no", "null"], default="null")
    a12.add_argument("--via-anexo", choices=["anexo_iii", "anexo_i"], default=None,
                    help="por donde es de alto riesgo: anexo_iii (sistema autonomo del "
                         "articulo 6.2) o anexo_i (componente de seguridad de un producto "
                         "regulado, articulo 6.1). Decide la fecha: 2-dic-2027 o 2-ago-2028")
    a12.add_argument("--registrar", action="store_true",
                     help="anade al almacen lo observado en esta pasada")
    a12.add_argument("--ahora")
    a12.add_argument("--idioma", choices=["es", "en"], default="es")
    a12.add_argument("--json", action="store_true")
    a12.set_defaults(fn=cmd_vigilar)

    a11 = sub.add_parser("ortografia", help="comprueba las tildes del castellano del catalogo")
    a11.add_argument("--catalogo", default=str(CATALOGO))
    a11.add_argument("--arreglar", action="store_true")
    a11.set_defaults(fn=cmd_ortografia)

    a17 = sub.add_parser("empujon", help="traduce un webhook y dice si hay que volver a observar")
    a17.add_argument("payload", nargs="?", default="-", help="fichero JSON, o - para la entrada")
    a17.add_argument("--id-del-evento", default=None)
    a17.add_argument("--almacen", default=".actaira/evidencia.jsonl")
    a17.add_argument("--idioma", choices=["es", "en"], default="es")
    a17.add_argument("--json", action="store_true")
    a17.add_argument("--registrar", action="store_true",
                     help="anota en el almacen que este empujon se demostro inerte, para "
                          "que el siguiente pueda salir de el sin costar una observacion. "
                          "NO es una observacion: el arbol no se mira.")
    a17.add_argument("--ahora", default=None,
                     help="el reloj, como argumento (ISO 8601). Por defecto, el de la maquina.")
    a17.set_defaults(fn=cmd_empujon)

    a16 = sub.add_parser("conectar", help="trae el codigo de donde este y corre el plan, sin dejar copia")
    a16.add_argument("ubicacion", help="una ruta local o una URL de git")
    a16.add_argument("--referencia", default=None, help="rama, etiqueta o commit")
    a16.add_argument("--catalogo", default=str(CATALOGO))
    a16.add_argument("--reglas", default=str(CATALOGO / "reglas"))
    a16.add_argument("--rol", action="append", default=None)
    for n in ("alto-riesgo", "sector-publico", "modelo-uso-general", "riesgo-sistemico"):
        a16.add_argument(f"--{n}", choices=["si", "no", "null"], default="null")
    a16.add_argument("--via-anexo", choices=["anexo_iii", "anexo_i"], default=None)
    a16.add_argument("--fecha", default=date.today().isoformat())
    a16.add_argument("--idioma", choices=["es", "en"], default="es")
    a16.add_argument("--almacen", default=".actaira/evidencia.jsonl")
    a16.add_argument("--registrar", action="store_true",
                     help="guarda la fuente en el almacen para que el siguiente empujon se "
                          "pueda decidir sin clonar nada")
    a16.add_argument("--ahora")
    a16.add_argument("--acepto-que-no-se-puede-repetir", action="store_true",
                     help="seguir aunque la fuente no tenga referencia inmutable")
    a16.add_argument("--json", action="store_true")
    a16.set_defaults(fn=cmd_conectar)

    a15 = sub.add_parser("noconformidad", help="la clausula 10.2: abrir, avanzar y listar")
    a15.add_argument("accion", choices=["abrir", "avanzar", "listar"])
    a15.add_argument("--id", default=None)
    a15.add_argument("--almacen", default=".actaira/evidencia.jsonl")
    a15.add_argument("--a", choices=[e.value for e in __import__(
        "actaira_motor.gestion.noconformidad", fromlist=["EstadoNC"]).EstadoNC], default=None)
    a15.add_argument("--quien", default="")
    a15.add_argument("--cargo", default="")
    a15.add_argument("--origen", default=None)
    a15.add_argument("--descripcion", default=None)
    a15.add_argument("--nota", default=None)
    a15.add_argument("--causa-raiz", default=None)
    a15.add_argument("--accion-correctiva", default=None)
    a15.add_argument("--responsable", default=None)
    a15.add_argument("--compromiso", default=None, help="fecha comprometida, AAAA-MM-DD")
    a15.add_argument("--evidencia-de-eficacia", default=None,
                     help="identificador de una evidencia observada DESPUES de ejecutar. "
                          "Sin ella no se puede verificar, y verificar es lo unico que cierra.")
    a15.add_argument("--ahora")
    a15.add_argument("--json", action="store_true")
    a15.add_argument("--idioma", choices=["es", "en"], default="es")
    a15.set_defaults(fn=cmd_noconformidad)

    a18 = sub.add_parser("remediar", help="delega la remediacion en el sistema de tickets "
                                          "del cliente, y la trae de vuelta con techo")
    a18.add_argument("accion", choices=["abrir", "sincronizar"])
    a18.add_argument("--destino", required=True,
                     help="una carpeta, o la URL del sistema de tickets")
    a18.add_argument("--perfil", default="",
                     help="jira, linear, github, o la ruta de uno tuyo. Solo para destinos "
                          "de red.")
    a18.add_argument("--id", default="", help="la no conformidad")
    a18.add_argument("--responsable", default="")
    a18.add_argument("--compromiso", default="", help="la fecha a la que faltar (ISO 8601)")
    a18.add_argument("--severidad", default="media")
    a18.add_argument("--simular", action="store_true",
                     help="ensena lo que saldria al sistema de tickets y NO lo manda, "
                          "ni escribe en el almacen. Lo que sale de aqui entra donde el "
                          "cliente organiza su trabajo, que lo lee mucha mas gente que "
                          "un expediente firmado: un ticket mal redactado no se borra.")

    a18.add_argument("--obligacion", default="")
    a18.add_argument("--localizacion", action="append",
                     help="una ruta del repositorio que sale al ticket. Por defecto NO sale "
                          "ninguna: un ticket lo lee mucha mas gente que un expediente.")
    a18.add_argument("--cargo", default="",
                     help="en calidad de que mueve el ticket quien lo mueve, cuando el otro "
                          "sistema no lo guarda")
    a18.add_argument("--almacen", default=".actaira/evidencia.jsonl")
    a18.add_argument("--reglas", default=str(RAIZ / "catalogo" / "reglas"),
                     help="de donde sale el texto bilingue del encargo cuando la no "
                          "conformidad viene de una regla del catalogo")
    a18.add_argument("--ahora", default=None)
    a18.add_argument("--idioma", choices=["es", "en"], default="es")
    a18.add_argument("--json", action="store_true")
    a18.set_defaults(fn=cmd_remediar)

    a14 = sub.add_parser("revision", help="la carpeta de entrada de la revision por la direccion (ISO 9.3)")
    a14.add_argument("--catalogo", default=str(CATALOGO))
    a14.add_argument("--almacen", default=".actaira/evidencia.jsonl")
    a14.add_argument("--salida", default=None, help="escribe el documento en markdown")
    a14.add_argument("--ahora")
    a14.add_argument("--idioma", choices=["es", "en"], default="es")
    a14.add_argument("--json", action="store_true")
    a14.set_defaults(fn=cmd_revision)

    a13 = sub.add_parser("almacen", help="comprueba la cadena de sellos del almacen de evidencia")
    a13.add_argument("accion", choices=["verificar", "migrar"], nargs="?", default="verificar")
    a13.add_argument("--destino", default=None, help="solo para migrar: el almacen nuevo")
    a13.add_argument("--acepto-que-no-se-puede-demostrar", action="store_true",
                     help="solo para migrar: reconoce que lo anterior a la migracion no "
                          "se puede declarar intacto")
    a13.add_argument("--acepto-una-cadena-rota", action="store_true",
                     help="solo para migrar: reconoce que el almacen de origen TENIA "
                          "cadena y no cuadra, es decir, que alguien lo edito. Es una "
                          "bandera aparte de la anterior a proposito: «no tenia cadena» "
                          "es rutina al actualizar el motor, «tenia cadena y no cuadra» "
                          "es un incidente, y una sola bandera para las dos convertiria "
                          "la rutina en el permiso para el incidente.")
    a13.add_argument("--almacen", default=".actaira/evidencia.jsonl")
    a13.add_argument("--json", action="store_true",
                     help="el mismo veredicto como documento. Sin esto el verbo solo "
                          "imprime prosa, y la plataforma no lo podia consumir: el "
                          "estado de la cadena de evidencia no se podia ensenar en "
                          "ninguna pantalla.")
    a13.add_argument("--cabeza-esperada", default=None,
                     help="el sello de la ultima linea que viste. Es lo unico que "
                          "detecta que le hayan quitado lineas del final.")
    a13.set_defaults(fn=cmd_almacen)

    a5 = sub.add_parser("exportar", help="emite la tabla de decision que consume la consola")
    a5.add_argument("--catalogo", default=str(CATALOGO))
    a5.add_argument("--salida", default="consola/datos.json")
    a5.set_defaults(fn=cmd_exportar)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except AlmacenAlterado as e:
        # No es un error de operacion, es un incidente, y por eso no comparte
        # codigo de salida con «el fichero no existe». Un cron que los funda
        # trata una manipulacion como un fallo transitorio y la reintenta.
        print(f"EL ALMACEN NO ES EL QUE SE ESCRIBIO\n  {e}", file=sys.stderr)
        return SALIDA_ALTERADO
    except BrokenPipeError:
        # `actaira plan . | head -3` cierra la tuberia y Python lo convierte en
        # un traceback que asusta. Se captura AQUI y no en `__main__`, porque
        # el punto de entrada que instala pip llama a `main()` directamente y
        # se saltaba el except: el primer cliente que hiciera `| head` habria
        # visto un traceback de un producto de cumplimiento.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    except OSError as e:
        # UN FICHERO QUE NO ESTA NO ES UN HALLAZGO.
        #
        # `verificar`, `contestar` y `empujon` reciben una ruta y la abren. Si
        # no existe, Python lanzaba un `FileNotFoundError` que nadie capturaba,
        # el cliente veia una traza cruda y el proceso salia con 1 -- que
        # arriba esta escrito que significa «aparecio algo».
        #
        # Es la misma forma del defecto que ya se arreglo con la salida en una
        # consola que no es UTF-8: una excepcion sin capturar se disfraza de
        # veredicto legitimo, y una integracion continua con la puerta
        # encendida para un despliegue citando hallazgos que no existen.
        #
        # Va DESPUES de `BrokenPipeError` a proposito, que es una subclase de
        # `OSError`: al reves, la tuberia cerrada de `| head` entraria por aqui
        # y saldria 4 en vez de 0.
        print(f"NO SE PUDO LEER LO QUE SE PIDIO MIRAR\n  {e}", file=sys.stderr)
        return SALIDA_ERROR


if __name__ == "__main__":
    sys.exit(main())
