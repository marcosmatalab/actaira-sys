"""Genera el Anexo IV desde el repositorio, y dice de donde sale cada seccion.

LA REGLA QUE HACE QUE ESTO NO SEA UN GENERADOR DE WORD
-------------------------------------------------------
Cada seccion publica su PROCEDENCIA, y solo hay tres valores:

  DERIVADA   se saco del arbol del cliente, y se dice de que ficheros
  APORTADA   la escribio una persona, y se dice quien y cuando
  AUSENTE    nadie la ha rellenado todavia, y se dice que falta

Nunca en blanco, y nunca inventada. Un expediente cuyas secciones no dicen su
origen es indistinguible de uno redactado por un modelo, y ante un auditor eso
vale cero. De ahi sale la unica afirmacion fuerte de este modulo: **nada de lo
que escribe aqui lo redacta un modelo de lenguaje**. Lo derivado sale de leer el
arbol y lo aportado sale de una persona; no hay tercera via.

POR QUE UNA SECCION DERIVADA PUEDE ADEMAS ADMITIR APORTE HUMANO
----------------------------------------------------------------
Seis de las catorce derivadas llevan `tambien_humana`. El punto 1.a es el
ejemplo: la version del sistema sale del arbol, pero la finalidad prevista no
esta en ningun fichero y no va a estarlo nunca. Fundirlas en una sola
procedencia obligaria a elegir entre publicar media seccion como derivada, que
seria mentir sobre su alcance, o marcarla entera como humana, que tiraria a la
basura lo que si se puede extraer. Asi que la seccion lleva las dos partes y
cada una dice lo suyo.

POR QUE EL EXTRACTOR PUEDE DEVOLVER NADA Y ESO NO ES UN FALLO
---------------------------------------------------------------
Un extractor que no encuentra lo que busca devuelve `AUSENTE` con el motivo
escrito, no una cadena vacia ni un texto de relleno. Regla 11: nunca caer al
extremo seguro en silencio. Un Anexo IV con seis secciones ausentes y dichas es
mas util que uno completo a base de parrafos genericos, porque el primero dice
en que trabajar y el segundo esconde el trabajo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ..controles.motor import Arbol

from ..vocabulario import nombres_de

ESQUEMA = "actaira/anexo-iv/v1"

# El texto corta a esta longitud por seccion, y lo DICE. El JSON nunca corta:
# es el documento de verdad y el markdown es su lectura comoda.
LIMITE_BLOQUE = 1200
AVISO_CORTE = {
    "es": "> **Cortado**: faltan {sobran} caracteres de esta sección. El contenido entero está en el "
          "JSON del expediente, sección `{id}`. Este texto es una lectura comoda, no el documento.",
    "en": "> **Truncated**: {sobran} characters of this section are missing. The full content is in the "
          "file's JSON, section `{id}`. This text is a convenient reading, not the document.",
}


@dataclass
class Seccion:
    id: str
    punto: str
    titulo: dict[str, str]
    procedencia: str                      # derivada | aportada | ausente
    contenido: dict[str, Any] = field(default_factory=dict)
    de_donde: list[str] = field(default_factory=list)
    motivo_ausencia: dict[str, str] | None = None
    aporte_humano: dict[str, Any] | None = None

    def a_json(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


# ---------------------------------------------------------------- extractores
# Cada uno devuelve (contenido, de_donde) o (None, motivo). Ninguno inventa.

def _version_y_proveedor(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    fuentes, datos = [], {}
    for nombre in ("pyproject.toml", "setup.cfg", "package.json"):
        if nombre in arbol.texto:
            fuentes.append(nombre)
            t = arbol.texto[nombre]
            m = re.search(r'^\s*version\s*[=:]\s*["\']([^"\']+)["\']', t, re.M)
            if m:
                datos["version"] = m.group(1)
            m = re.search(r'^\s*name\s*[=:]\s*["\']([^"\']+)["\']', t, re.M)
            if m:
                datos["nombre"] = m.group(1)
    if not datos:
        return None, {"es": "no hay pyproject.toml, setup.cfg ni package.json con nombre y versión",
                      "en": "no pyproject.toml, setup.cfg or package.json with a name and version"}
    return datos, fuentes


def _dependencias(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    fuentes, deps = [], []
    for nombre, t in arbol.texto.items():
        base = Path(nombre).name
        if base == "requirements.txt":
            fuentes.append(nombre)
            deps += [l.strip() for l in t.splitlines() if l.strip() and not l.startswith("#")]
        elif base == "pyproject.toml":
            fuentes.append(nombre)
            bloque = re.search(r"dependencies\s*=\s*\[(.*?)\]", t, re.S)
            if bloque:
                deps += re.findall(r'["\']([^"\']+)["\']', bloque.group(1))
    if not deps:
        return None, {"es": "no se encontró ninguna declaración de dependencias",
                      "en": "no dependency declaration was found"}
    fijadas = [d for d in deps if re.search(r"[=~]=|@sha256:", d)]
    return {"total": len(deps), "fijadas": len(fijadas), "lista": sorted(set(deps))[:60]}, fuentes


def _computo(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    """El hardware en el que se ejecuta EL SISTEMA, que no es el corredor de la CI.

    D-5 de la pasada adversarial de la fase 4: esta funcion contestaba al punto
    1.e con `runs-on` sacado de `.github/workflows/ci.yml`, que es la maquina
    donde corren las pruebas y no donde se ejecuta el sistema. Era plausible y
    era falso, que es la peor combinacion posible en un expediente que va a un
    auditor. Los ficheros de integracion continua quedan excluidos por ruta, y
    si solo casan ellos la seccion sale AUSENTE con su motivo.
    """
    pistas, fuentes = [], []
    for nombre, texto in arbol.texto.items():
        if re.search(r"(?i)(^|/)\.github/|(^|/)\.gitlab-ci|(^|/)\.circleci/", nombre):
            continue
        base = Path(nombre).name.lower()
        es_despliegue = (base.startswith("dockerfile") or base.startswith("docker-compose")
                         or nombre.endswith((".tf", ".tfvars"))
                         or re.search(r"(?i)(deploy|k8s|kubernetes|helm|infra)", nombre))
        if not es_despliegue:
            continue
        hallado = re.findall(r"(?i)\b(gpu|cuda|nvidia|memory|cpus?|instance_type|machine_type|node_type)\b[^\n]{0,60}", texto)
        if hallado:
            fuentes.append(nombre)
            pistas += [h if isinstance(h, str) else h[0] for h in hallado[:6]]
    if not pistas:
        return None, {"es": "no hay manifiestos de despliegue (Dockerfile, compose, Terraform o Kubernetes) que declaren "
                            "recursos de cómputo. Los ficheros de integración continua se excluyen a propósito: dicen "
                            "donde corren las pruebas, no donde se ejecuta el sistema",
                      "en": "no deployment manifest (Dockerfile, compose, Terraform or Kubernetes) declaring compute "
                            "resources. Continuous integration files are excluded on purpose: they say where the tests "
                            "run, not where the system runs"}
    return {"pistas": sorted(set(pistas))[:20]}, fuentes


def _terceros(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    firmas = ("from_pretrained", "hf_hub_download", "snapshot_download", "load_model")
    sitios = []
    for rel, (_paquetes, llamadas) in arbol.ficheros.items():
        for c in llamadas:
            if any(c.endswith(f) for f in firmas):
                sitios.append(f"{rel} ({c})")
    if not sitios:
        return None, {"es": "no se detectó carga de modelos preentrenados de terceros en el código leído",
                      "en": "no loading of third-party pre-trained models was detected in the code read"}
    return {"sitios": sitios}, sorted({s.split(" ")[0] for s in sitios})


def _arquitectura(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    if not arbol.ficheros:
        return None, {"es": "no se leyo ningún módulo Python", "en": "no Python module was read"}
    paquetes: dict[str, int] = {}
    for rel in arbol.ficheros:
        raiz = rel.split("/")[0] if "/" in rel else "(raiz)"
        paquetes[raiz] = paquetes.get(raiz, 0) + 1
    entradas = [r for r in arbol.ficheros if Path(r).name in ("main.py", "app.py", "cli.py", "__main__.py")]
    return ({"modulos": len(arbol.ficheros), "paquetes": dict(sorted(paquetes.items())),
             "puntos_de_entrada": entradas or ["(ninguno reconocido por nombre)"]},
            sorted(arbol.ficheros)[:40])


def _datos(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    fichas = [f for f in arbol.todos
              if re.search(r"(?i)(datasheet|data.?card|ficha.?datos|dataset)", f)]
    if not fichas:
        return None, {"es": "no hay ninguna ficha técnica de conjunto de datos en el árbol. El punto 2.d la exige expresamente en esa forma",
                      "en": "there is no dataset datasheet in the tree. Point 2(d) expressly requires that form"}
    return {"fichas": fichas}, fichas


def _instrucciones(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    docs = [f for f in arbol.todos if re.search(r"(?i)(instruc|manual|user.?guide|uso)\w*\.(md|rst|txt|pdf)$", f)]
    if not docs:
        return None, {"es": "no se encontró un documento de instrucciones de uso",
                      "en": "no instructions-for-use document was found"}
    return {"documentos": docs}, docs


def _ciberseguridad(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    señales = []
    for nombre, t in arbol.codigo.items():
        for pat, etiqueta in ((r"(?i)injection|jailbreak|redteam", "pruebas de manipulacion de entrada"),
                              (r"(?i)rate.?limit", "limitacion de peticiones"),
                              (r"(?i)sha256:|digest", "fijacion de artefactos por digest"),
                              (r"(?i)secrets?\.|keyring|vault", "gestion de secretos")):
            if re.search(pat, t):
                señales.append({"patron_observado": etiqueta, "fichero": nombre})
    if not señales:
        return None, {"es": "no se observo en el código ningún patron asociado a medidas de ciberseguridad. El punto 2.h "
                            "no admite quedar en blanco y hay que aportarlo",
                      "en": "no pattern associated with cybersecurity measures was observed in the code. Point 2(h) "
                            "cannot be left blank and must be supplied"}
    vistos, unicos = set(), []
    for s in señales:
        clave = (s["patron_observado"], s["fichero"])
        if clave not in vistos:
            vistos.add(clave); unicos.append(s)
    return ({"advertencia": {
                 "es": "Esto son PATRONES OBSERVADOS en el código, no medidas de ciberseguridad adoptadas. Que aparezca "
                       "`sha256:` no prueba que los artefactos estén fijados, solo que alguien escribió esa cadena. La "
                       "segunda negativa prohibe que Actaira interprete: la interpretación la firma una persona en el "
                       "aporte de esta misma sección.",
                 "en": "These are PATTERNS OBSERVED in the code, not cybersecurity measures adopted. That `sha256:` "
                       "appears does not prove artefacts are pinned, only that somebody wrote that string. The second "
                       "negative forbids Actaira from interpreting: a person signs the interpretation in this section's "
                       "own supplied text."},
             "patrones": unicos[:20], "total_observados": len(unicos)},
            sorted({s["fichero"] for s in unicos})[:20])


def _cambios(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    cl = [f for f in arbol.todos if re.search(r"(?i)^(changelog|historial|cambios)", Path(f).name)]
    if not cl:
        return None, {"es": "no hay CHANGELOG ni equivalente. El punto 6 pide los cambios pertinentes del ciclo de vida",
                      "en": "there is no CHANGELOG or equivalent. Point 6 asks for relevant lifecycle changes"}
    t = arbol.texto.get(cl[0], "")
    versiones = re.findall(r"^#{1,3}\s*\[?v?(\d+\.\d+\.\d+)", t, re.M)
    return {"fichero": cl[0], "versiones": versiones[:20]}, cl


def _control(arbol: Arbol, ctx: dict) -> tuple[dict | None, Any]:
    """Toma la seccion de la linea del plan que ya corrio el control."""
    linea = ctx.get("plan_por_obligacion", {}).get(ctx["obligacion"])
    if linea is None:
        return None, {"es": f"la obligación {ctx['obligacion']} no ata a este perfil o no se corrió su control",
                      "en": f"obligation {ctx['obligacion']} does not bind this profile or its control was not run"}
    return ({"estado": linea["estado"], "cubre": linea["cubre"], "no_cubre": linea["no_cubre"],
             "hallazgos": [{"regla": h["regla_id"], "severidad": h["severidad"],
                            "localizacion": h["localizacion"]} for h in linea["hallazgos"]],
             "preguntas_abiertas": len(linea["preguntas"])},
            [f"control de {ctx['obligacion']}"])


EXTRACTORES = {
    "version_y_proveedor": _version_y_proveedor, "dependencias": _dependencias,
    "computo": _computo, "terceros": _terceros, "arquitectura": _arquitectura,
    "datos": _datos, "instrucciones": _instrucciones, "ciberseguridad": _ciberseguridad,
    "cambios": _cambios, "control": _control,
}


def generar(catalogo_anexo: str | Path, arbol: Arbol | None, plan: dict | None,
            aportes: dict[str, dict] | None = None, cuando: date | None = None) -> dict[str, Any]:
    """Arma el Anexo IV. `aportes` son las secciones que ya escribio una persona."""
    spec = json.loads(Path(catalogo_anexo).read_text(encoding="utf-8"))
    aportes = aportes or {}
    por_obl = {l["obligacion_id"]: l for l in (plan or {}).get("lineas", [])}
    secciones: list[Seccion] = []

    for s in spec["secciones"]:
        sec = Seccion(id=s["id"], punto=s["punto"], titulo=s["titulo"], procedencia="ausente")
        aporte = aportes.get(s["id"])
        if aporte:
            sec.aporte_humano = {"texto": aporte["texto"], "firmado_por": aporte["firmado_por"],
                                 "fecha": aporte["fecha"]}

        if s["origen"] == "derivada" and arbol is not None:
            ctx = {"plan_por_obligacion": por_obl, "obligacion": s.get("obligacion")}
            contenido, extra = EXTRACTORES[s["extractor"]](arbol, ctx)
            if contenido is not None:
                sec.procedencia = "derivada"
                sec.contenido = contenido
                sec.de_donde = list(extra)
            else:
                sec.motivo_ausencia = extra

        if sec.procedencia == "ausente" and sec.aporte_humano:
            sec.procedencia = "aportada"
        elif sec.procedencia == "derivada" and sec.aporte_humano:
            sec.procedencia = "derivada+aportada"
        elif sec.procedencia == "ausente" and sec.motivo_ausencia is None:
            sec.motivo_ausencia = {
                "es": "sección que solo puede escribir una persona, y todavía no se ha aportado",
                "en": "section that only a person can write, and it has not been supplied yet"}
        secciones.append(sec)

    recuento: dict[str, int] = {}
    for s in secciones:
        recuento[s.procedencia] = recuento.get(s.procedencia, 0) + 1

    return {
        "esquema": ESQUEMA,
        "referencia": spec["referencia"],
        "fecha": (cuando or date.today()).isoformat(),
        "nota_de_procedencia": spec["nota_de_procedencia"],
        "recuento": recuento,
        # Como se lee cada procedencia, publicado por el motor: la pantalla que
        # ensene un Anexo no tiene por que saberse el vocabulario del motor.
        "nombres_de_estado": nombres_de(list(recuento)),
        "total_secciones": len(secciones),
        "secciones": [s.a_json() for s in secciones],
    }


def a_markdown(anexo: dict[str, Any], idioma: str = "es") -> str:
    """El expediente en texto. Toda seccion imprime su procedencia, sin excepcion."""
    ETIQ = {"es": {"derivada": "DERIVADA del codigo", "aportada": "APORTADA por una persona",
                   "derivada+aportada": "DERIVADA del codigo y COMPLETADA por una persona",
                   "ausente": "AUSENTE"},
            "en": {"derivada": "DERIVED from code", "aportada": "SUPPLIED by a person",
                   "derivada+aportada": "DERIVED from code and COMPLETED by a person",
                   "ausente": "MISSING"}}[idioma]
    out = [f"# {anexo['referencia'][idioma]}", "",
           f"{anexo['nota_de_procedencia'][idioma]}", "",
           f"Generado el {anexo['fecha']}. Secciones: {anexo['total_secciones']}. "
           + ", ".join(f"{v} {ETIQ[k].lower()}" for k, v in sorted(anexo["recuento"].items())), ""]
    for s in anexo["secciones"]:
        out.append(f"## {s['punto']}. {s['titulo'][idioma]}")
        out.append(f"*{ETIQ[s['procedencia']]}*")
        if s["de_donde"]:
            out.append(f"Fuentes: {', '.join(f'`{x}`' for x in s['de_donde'][:8])}")
        if s["contenido"]:
            # D-7: truncar en silencio dentro de un expediente es perder contenido
            # sin que nadie lo sepa. Si se corta, se dice cuanto y donde esta lo
            # entero. Regla 11: nunca caer al extremo seguro sin ruido.
            cuerpo = json.dumps(s["contenido"], ensure_ascii=False, indent=2)
            out.append("```json")
            if len(cuerpo) > LIMITE_BLOQUE:
                out.append(cuerpo[:LIMITE_BLOQUE])
                out.append("```")
                sobran = len(cuerpo) - LIMITE_BLOQUE
                out.append(AVISO_CORTE[idioma].format(sobran=sobran, id=s["id"]))
            else:
                out.append(cuerpo)
                out.append("```")
        if s["aporte_humano"]:
            out.append(f"> {s['aporte_humano']['texto']}")
            out.append(f"> Firmado por {s['aporte_humano']['firmado_por']} el {s['aporte_humano']['fecha']}.")
        if s["motivo_ausencia"] and s["procedencia"] == "ausente":
            out.append(f"**Falta**: {s['motivo_ausencia'][idioma]}")
        out.append("")
    return "\n".join(out)
