"""Lee la estructura de agentes de un repositorio: herramientas, delegación y límites.

LA DECISION QUE DEFINE ESTE MODULO, Y ES UNA NEGATIVA
-------------------------------------------------------
Lo fácil, y lo que hace todo el mundo, es clasificar las herramientas por su
nombre: `get_*` lee, `delete_*` escribe, `send_*` envía. Con eso se pinta un
panel de riesgo en una tarde y se equivoca en cuanto alguien llama
`obtener_factura` a algo que emite una factura. Nombrar no es declarar, y
deducir el efecto de una herramienta de su nombre es exactamente el patrón que
la segunda negativa prohíbe convertir en veredicto.

Así que el efecto de una herramienta aquí sólo puede ser:

    declarado     el código lo dice: una anotación MCP, un campo explícito
    sin_declarar  no lo dice, y ESO es el hallazgo

El hallazgo no es «esta herramienta es peligrosa». Es «tienes catorce
herramientas y de once no consta qué hacen cuando se las llama», que es una
afirmación comprobable, accionable y que además es verdad en casi todos los
repositorios de agentes que existen hoy.

QUE SE LEE, Y DE DONDE
------------------------
  * configuraciones MCP (`mcp.json`, `.mcp.json`, `claude_desktop_config.json`
    y equivalentes): servidores, y las anotaciones de cada herramienta si están;
  * declaraciones de herramientas en Python: el decorador `@tool`, las listas
    `tools=[...]` que se pasan a un cliente, y los `Tool(...)` explícitos;
  * delegación: un agente que crea o invoca a otro;
  * límites: gasto, número de pasos, tiempo.

Lo que NO se lee, y se dice: si la herramienta hace lo que dice, si el límite
se respeta en ejecución, y qué pasa cuando el modelo encadena dos herramientas
inofensivas para conseguir una que no lo es.
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..rutas import nombre_en_el_arbol

# Los nombres de fichero que llevan configuracion de servidores MCP. Es una
# lista cerrada a proposito: adivinar por contenido daria falsos positivos en
# cualquier JSON con una clave parecida.
CONFIGS_MCP = ("mcp.json", ".mcp.json", "claude_desktop_config.json",
               "mcp_servers.json", ".cursor/mcp.json")

# Las anotaciones que SI declaran el efecto. Vienen del esquema de MCP, donde
# son opcionales; que sean opcionales es justamente el problema que esto mide.
ANOTACIONES = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint",
               "efecto", "effect", "side_effects", "requires_approval",
               "requiere_aprobacion")

DECORADORES_HERRAMIENTA = ("tool", "function_tool", "register_tool", "ai_function")

# INDICIOS de que aqui hay agentes aunque no se haya podido leer ninguno.
#
# Es la mitad que faltaba. «No encontre ninguna estructura de agentes» y «no
# hay agentes» no son lo mismo, y el control ya lo decia; pero decirlo sin mas
# deja el caso peligroso en silencio: un repositorio que declara `crewai` en
# sus dependencias y define sus herramientas en un bucle no produce ninguna
# lectura, y sale NO_APLICABLE como el que no tiene agentes. Esto los separa:
# si hay marco de agentes declarado y no se leyo ni una herramienta, eso no es
# «no aplica», es «no lo se ver», y las dos piden cosas distintas.
MARCOS_DE_AGENTES = ("mcp", "modelcontextprotocol", "langchain", "langgraph", "crewai",
                     "autogen", "llama-index", "llama_index", "semantic-kernel",
                     "semantic_kernel", "smolagents", "openai-agents", "agents-sdk",
                     "pydantic-ai", "pydantic_ai", "haystack-ai")
FICHEROS_DE_DEPENDENCIAS = ("pyproject.toml", "requirements.txt", "package.json",
                            "Pipfile", "poetry.lock", "requirements-dev.txt")
LLAMADAS_DELEGACION = ("Agent", "create_agent", "spawn", "subagent", "Task",
                       "run_agent", "delegate", "crew", "Crew")
LIMITES = {
    "gasto": ("max_cost", "budget", "spend_limit", "coste_maximo", "presupuesto",
              "max_spend", "cost_limit"),
    "pasos": ("max_steps", "max_iterations", "max_turns", "pasos_maximos",
              "recursion_limit", "max_depth"),
    "tiempo": ("timeout", "deadline", "max_duration", "tiempo_maximo"),
}


@dataclass(frozen=True)
class Herramienta:
    """Una herramienta que un agente puede llamar, y lo que consta de ella."""

    nombre: str
    origen: str            # "mcp" | "decorador" | "lista" | "clase"
    localizacion: str
    efecto: str            # "declarado" | "sin_declarar"
    anotaciones: tuple[str, ...] = ()

    def a_json(self) -> dict[str, Any]:
        return {"nombre": self.nombre, "origen": self.origen,
                "localizacion": self.localizacion, "efecto": self.efecto,
                "anotaciones": list(self.anotaciones)}


@dataclass(frozen=True)
class Delegacion:
    """Un agente que crea o invoca a otro. La herencia de permisos NO se lee."""

    desde: str
    localizacion: str
    llamada: str

    def a_json(self) -> dict[str, Any]:
        return {"desde": self.desde, "localizacion": self.localizacion,
                "llamada": self.llamada}


@dataclass
class Agente:
    """La estructura de agentes de un repositorio, tal y como consta en el."""

    raiz: str
    herramientas: list[Herramienta] = field(default_factory=list)
    delegaciones: list[Delegacion] = field(default_factory=list)
    limites: dict[str, list[str]] = field(default_factory=dict)
    servidores_mcp: list[str] = field(default_factory=list)
    ficheros_leidos: list[str] = field(default_factory=list)
    marcos_declarados: list[str] = field(default_factory=list)
    ilegibles: list[tuple[str, str]] = field(default_factory=list)
    """Los ficheros que este lector NO pudo abrir, con el motivo.

    Estaban cayendo en tres `continue` silenciosos: un enlace que sale de la
    raiz, un fichero que no es UTF-8, un Python que no analiza. El lector
    seguia y publicaba su resultado como si hubiera mirado el arbol entero.

    Es exactamente el mismo fallo que el plan tenia al descartar sus
    `ilegibles`, asomando por la otra ventana, y con la misma consecuencia: lo
    que no se leyo no produce hallazgos, asi que un repositorio con media rama
    ilegible da el mismo documento que uno leido entero. Aqui es peor de notar,
    porque `hay_agente` es False cuando no se encontro nada -- y no encontrar
    nada porque no se pudo leer se parece muchisimo a no encontrar nada porque
    no hay.
    """

    @property
    def hay_agente(self) -> bool:
        """Si este repositorio tiene estructura de agentes que mirar.

        Una lista vacia NO significa «no hay agentes»: significa que no se
        encontro ninguna de las formas que este lector conoce. La diferencia
        importa porque la primera es una conclusion y la segunda es un limite,
        y el control publica la segunda.
        """
        return bool(self.herramientas or self.delegaciones or self.servidores_mcp)

    @property
    def indicios_sin_lectura(self) -> bool:
        """Hay marco de agentes declarado y no se leyo ni una herramienta.

        Es el caso que de verdad importa: un repositorio que declara `crewai` y
        registra sus herramientas en un bucle no produce ninguna lectura, y sin
        esto saldria igual que uno que no tiene agentes. «No lo se ver» y «no
        hay» piden cosas distintas: la primera pide que alguien lo declare a
        mano, la segunda no pide nada.
        """
        return bool(self.marcos_declarados) and not self.hay_agente

    @property
    def sin_declarar(self) -> list[Herramienta]:
        return [h for h in self.herramientas if h.efecto == "sin_declarar"]

    def digest(self) -> str:
        """Lo que identifica a ESTA estructura. Cambia si cambia el arsenal.

        Que el sujeto sea la estructura y no el repositorio es lo que hace util
        la invalidacion: anadir una herramienta invalida la evidencia sobre las
        herramientas, y tocar el README no.
        """
        from ..evidencia.registro import digest as _d
        # La localizacion NO entra: mover una herramienta de fichero no cambia
        # lo que el agente puede hacer, y si entrara, un refactor invalidaria
        # toda la evidencia sobre el arsenal sin que el arsenal cambiara. Lo
        # que identifica a la estructura es QUE puede hacer y si consta, no
        # donde esta escrito; la localizacion sigue viajando como procedencia.
        return _d({
            "herramientas": sorted(
                [{"nombre": h.nombre, "efecto": h.efecto,
                  "anotaciones": list(h.anotaciones)} for h in self.herramientas],
                key=lambda x: x["nombre"]),
            "delegaciones": sorted({d.llamada for d in self.delegaciones}),
            "limites": sorted(self.limites),
            "servidores_mcp": sorted(self.servidores_mcp),
            "marcos": sorted(self.marcos_declarados),
        })

    def a_json(self) -> dict[str, Any]:
        return {"raiz": self.raiz,
                "herramientas": [h.a_json() for h in self.herramientas],
                "delegaciones": [d.a_json() for d in self.delegaciones],
                "limites": self.limites,
                "servidores_mcp": self.servidores_mcp,
                "marcos_declarados": self.marcos_declarados,
                "ficheros_leidos": sorted(self.ficheros_leidos),
                "digest": self.digest()}


def _anotaciones_de(d: dict[str, Any]) -> tuple[str, ...]:
    presentes = [k for k in ANOTACIONES if k in d]
    anid = d.get("annotations") or d.get("anotaciones")
    if isinstance(anid, dict):
        presentes += [k for k in ANOTACIONES if k in anid]
    return tuple(sorted(set(presentes)))


def _leer_mcp(ruta: Path, rel: str, a: Agente) -> None:
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return
    a.ficheros_leidos.append(rel)
    servidores = d.get("mcpServers") or d.get("servers") or {}
    if isinstance(servidores, dict):
        for nombre, cfg in servidores.items():
            a.servidores_mcp.append(nombre)
            herramientas = (cfg or {}).get("tools") if isinstance(cfg, dict) else None
            if not isinstance(herramientas, list):
                continue
            for h in herramientas:
                if not isinstance(h, dict) or "name" not in h:
                    continue
                anots = _anotaciones_de(h)
                a.herramientas.append(Herramienta(
                    nombre=f"{nombre}.{h['name']}", origen="mcp",
                    localizacion=rel, efecto="declarado" if anots else "sin_declarar",
                    anotaciones=anots))
    # Un servidor MCP declarado sin lista de herramientas es un arsenal
    # desconocido entero: se registra como servidor y no como herramienta,
    # porque inventarse sus herramientas seria inventarse el sujeto.


def _nombre_de(nodo: ast.AST) -> str:
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        return f"{_nombre_de(nodo.value)}.{nodo.attr}"
    if isinstance(nodo, ast.Call):
        return _nombre_de(nodo.func)
    return ""


def _leer_python(fuente: str, rel: str, a: Agente) -> None:
    try:
        arbol = ast.parse(fuente)
    except SyntaxError:
        return
    a.ficheros_leidos.append(rel)
    for n in ast.walk(arbol):
        # 1) el decorador @tool sobre una funcion
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in n.decorator_list:
                corto = _nombre_de(deco).split(".")[-1]
                if corto in DECORADORES_HERRAMIENTA:
                    claves = ()
                    if isinstance(deco, ast.Call):
                        claves = tuple(sorted(
                            k.arg for k in deco.keywords if k.arg in ANOTACIONES))
                    a.herramientas.append(Herramienta(
                        nombre=n.name, origen="decorador",
                        localizacion=f"{rel}:{n.lineno}",
                        efecto="declarado" if claves else "sin_declarar",
                        anotaciones=claves))
        if not isinstance(n, ast.Call):
            continue
        llamado = _nombre_de(n.func)
        corto = llamado.split(".")[-1]
        # 2) delegacion: un agente que crea o invoca a otro
        if corto in LLAMADAS_DELEGACION:
            a.delegaciones.append(Delegacion(
                desde=rel, localizacion=f"{rel}:{n.lineno}", llamada=llamado))
        # 3) limites declarados como argumento
        for clase, nombres in LIMITES.items():
            for k in n.keywords:
                if k.arg in nombres:
                    a.limites.setdefault(clase, []).append(f"{rel}:{n.lineno} ({k.arg})")
        # 4) tools=[...] pasado a un cliente
        for k in n.keywords:
            if k.arg not in ("tools", "herramientas") or not isinstance(k.value, ast.List):
                continue
            for elem in k.value.elts:
                nombre, anots = None, ()
                if isinstance(elem, ast.Dict):
                    for clave, valor in zip(elem.keys, elem.values):
                        if isinstance(clave, ast.Constant) and clave.value == "name" \
                                and isinstance(valor, ast.Constant):
                            nombre = valor.value
                    anots = tuple(sorted(
                        c.value for c in elem.keys
                        if isinstance(c, ast.Constant) and c.value in ANOTACIONES))
                elif isinstance(elem, ast.Name):
                    nombre = elem.id
                elif isinstance(elem, ast.Call):
                    nombre = _nombre_de(elem)
                if nombre:
                    a.herramientas.append(Herramienta(
                        nombre=str(nombre), origen="lista",
                        localizacion=f"{rel}:{n.lineno}",
                        efecto="declarado" if anots else "sin_declarar",
                        anotaciones=anots))


def _agrupar(crudas: list[Herramienta]) -> list[Herramienta]:
    """Una herramienta por NOMBRE, y declarada si alguna aparicion la declara.

    La misma herramienta sale dos veces: una donde se define con `@tool` y otra
    donde se pasa en `tools=[...]`. La segunda es una REFERENCIA, no una
    declaracion, y contarla aparte hacia que una herramienta perfectamente
    declarada apareciera tambien en la lista de las que no lo estan. La
    pregunta que este modulo contesta es «¿consta en algun sitio lo que hace
    esta herramienta?», y esa pregunta se contesta una vez por herramienta.
    """
    por_nombre: dict[str, list[Herramienta]] = {}
    for h in crudas:
        por_nombre.setdefault(h.nombre, []).append(h)
    fuera = []
    for nombre, grupo in sorted(por_nombre.items()):
        declarada = next((h for h in grupo if h.efecto == "declarado"), None)
        sitios = ", ".join(sorted({h.localizacion for h in grupo}))
        base = declarada or sorted(grupo, key=lambda h: h.localizacion)[0]
        fuera.append(Herramienta(
            nombre=nombre, origen=base.origen, localizacion=sitios,
            efecto="declarado" if declarada else "sin_declarar",
            anotaciones=base.anotaciones))
    return fuera


def leer(raiz: str | Path) -> Agente:
    """Lee la estructura de agentes de un repositorio. Una pasada, un objeto."""
    raiz = Path(raiz)
    raiz_real = raiz.resolve()
    a = Agente(raiz=str(raiz))
    for p in sorted(raiz.rglob("*")):
        if not p.is_file() or any(x in {".git", "__pycache__", ".venv", "node_modules"}
                                  for x in p.parts):
            continue
        rel = nombre_en_el_arbol(raiz, p)
        try:
            if p.resolve(strict=True) != raiz_real and raiz_real not in p.resolve().parents:
                a.ilegibles.append(
                    (rel, "enlace que sale de la raiz del repositorio: no se lee, y se dice"))
                continue
        except (OSError, RuntimeError) as e:
            a.ilegibles.append((rel, f"{type(e).__name__}: {e}"))
            continue
        if p.name in FICHEROS_DE_DEPENDENCIAS:
            try:
                texto = p.read_text(encoding="utf-8").lower()
            except (UnicodeDecodeError, OSError) as e:
                a.ilegibles.append((rel, f"{type(e).__name__}: {e}"))
                continue
            a.ficheros_leidos.append(rel)
            a.marcos_declarados += [m for m in MARCOS_DE_AGENTES if m in texto]
        if p.name in CONFIGS_MCP or rel in CONFIGS_MCP:
            _leer_mcp(p, rel, a)
        elif p.suffix == ".py":
            try:
                _leer_python(p.read_text(encoding="utf-8"), rel, a)
            except (UnicodeDecodeError, OSError, SyntaxError) as e:
                a.ilegibles.append((rel, f"{type(e).__name__}: {e}"))
                continue
    a.herramientas = _agrupar(a.herramientas)
    a.delegaciones = sorted(set(a.delegaciones), key=lambda d: d.localizacion)
    a.servidores_mcp = sorted(set(a.servidores_mcp))
    a.marcos_declarados = sorted(set(a.marcos_declarados))
    return a
