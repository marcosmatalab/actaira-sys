"""El motor generico de controles. Un motor, y los articulos son datos.

POR QUE UN MOTOR Y NO UN CONTROL POR ARTICULO
----------------------------------------------
La fase 2 construyo `art50.py` a mano, y fue lo correcto para el primero: hasta
tener uno entero no se sabe que forma tiene el problema. Escribir asi los
trece articulos de nivel maquina daria trece ficheros con la misma estructura y
trece sitios donde arreglar el mismo defecto. La regla 10 otra vez: la misma
propiedad escrita trece veces no se suma, se anula.

Aqui hay CINCO tipos de comprobacion y ni un articulo nombrado en el codigo.
Anadir el articulo 12 es un fichero JSON y sus dos tests, no un despliegue.

LOS CINCO TIPOS, Y POR QUE SON CINCO Y NO UNO
----------------------------------------------
  llamada              una llamada casa una firma, y el fichero importa el
                       paquete que la regla exige. Es el de la fase 2.
  llamada_sin_pareja   existe la llamada A y NO existe la B en el mismo
                       fichero. Es el que decide el articulo 12: invocas el
                       modelo y no registras nada.
  fichero              existe algun fichero que casa un patron. Sirve para
                       "hay suite de evaluacion", "hay fichero de versiones".
  contenido            un fichero casa una expresion. Sirve para la CI y la
                       configuracion, donde lo que importa es una linea.
  aportado             NO se puede decidir leyendo el repositorio. No falla:
                       produce una PREGUNTA al cliente. Es el puente entre el
                       control tecnico y el formulario, y es lo que permite
                       cubrir el Reglamento entero sin mentir sobre que parte
                       se midio.

`aportado` es el tipo que hace honesto al producto. Sin el, todo lo que no se
puede leer en el codigo tendria que salir NO_CUMPLE o desaparecer del informe,
y las dos cosas son falsas.

POR QUE `llamada_sin_pareja` MIRA EL FICHERO Y NO LA FUNCION
-------------------------------------------------------------
Rechazado el analisis de flujo intraprocedimental: es mas preciso y es
exactamente donde un analizador estatico empieza a equivocarse con decoradores,
contextos y llamadas indirectas. A nivel de fichero el falso negativo es
posible (registras en otro modulo) y el falso positivo casi no, y de los dos
errores el que destruye la confianza es el segundo. El falso negativo se
publica como limite y esta en el backlog como B-004.
"""
from __future__ import annotations

import hashlib

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..evidencia.registro import digest
from ..rutas import nombre_en_el_arbol
from .deteccion import _casa, _importa_paquete, _ruta_punteada
from .modelo import Hallazgo, ResultadoControl

TIPOS = ("llamada", "llamada_sin_pareja", "fichero", "contenido",
         "contenido_prohibido", "aportado")


@dataclass(frozen=True)
class Pregunta:
    """Lo que hay que pedirle al cliente porque el codigo no lo contiene."""

    regla_id: str
    obligacion_id: str
    texto: dict[str, str]
    formato: str
    por_que: dict[str, str]

    def a_json(self) -> dict[str, Any]:
        return {"regla_id": self.regla_id, "obligacion_id": self.obligacion_id,
                "texto": self.texto, "formato": self.formato, "por_que": self.por_que}


# Que campo exige cada tipo. Se valida AL CARGAR y no al evaluar: un paquete
# mal escrito tiene que reventar con su identificador delante, no a mitad de un
# barrido con un KeyError. Regla 11, fallar ruidosamente y nombrar que faltaba.
FUERZA_POR_TIPO = {
    # Lo que el programa HACE, leido del arbol sintactico.
    "llamada": "comportamiento",
    "llamada_sin_pareja": "comportamiento",
    # Lo que el repositorio TIENE. Un nombre de fichero que casa una expresion
    # regular, o una linea de texto dentro de uno. Dice que el artefacto esta;
    # no dice nada de si sirve.
    "fichero": "presencia",
    "contenido": "presencia",
    "contenido_prohibido": "presencia",
    # No se leyo nada: se pregunto.
    "aportado": "aportado",
}
"""Que clase de afirmacion sostiene cada tipo de regla.

El informe decia «comprobada» con la misma cara para las dos cosas: para una
regla que encuentra una llamada al modelo en el arbol sintactico y para una que
encuentra un fichero llamado `dataset-card.md`. La segunda no demuestra que el
origen de los datos sea licito, ni que la representatividad este evaluada, ni
que los sesgos esten dentro de umbrales aprobados -- demuestra que el fichero
esta ahi, que es lo que se miro.

Mirar el fichero sigue valiendo: es la unica forma de saber si el artefacto
existe, y su ausencia es un hallazgo de verdad. Lo que no vale es publicar las
dos con la misma fuerza y dejar que quien lee decida cual era cual, porque
quien lee no tiene con que.
"""

EXIGE = {
    "llamada": ("firmas",),
    "llamada_sin_pareja": ("firmas", "pareja"),
    "fichero": ("patrones",),
    "contenido": ("patrones",),
    "contenido_prohibido": ("patrones",),
    "aportado": ("pregunta",),
}


@dataclass
class Paquete:
    obligacion: str
    nombre: str
    version: str
    autor: str
    reglas: list[dict[str, Any]]
    motor: str = "generico"

    @staticmethod
    def cargar(ruta: str | Path) -> "Paquete":
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        motor = d.get("motor", "generico")
        if motor == "generico":
            for r in d["reglas"]:
                tipo = r.get("tipo", "llamada")
                if tipo not in TIPOS:
                    raise ValueError(f"{r['id']}: tipo '{tipo}' no esta en {TIPOS}")
                faltan = [c for c in EXIGE[tipo] if c not in r]
                if faltan:
                    raise ValueError(
                        f"{r['id']}: de tipo '{tipo}' y le faltan los campos {faltan}. "
                        f"Un tipo que no trae lo que necesita reventaria a mitad del barrido.")
                # `que_busca` viaja a la senal, y la senal se imprime en el
                # expediente. Era una cadena suelta en castellano, asi que un
                # informe pedido en ingles traia castellano dentro. Se exige
                # aqui, al cargar, y no al imprimir: un paquete mal escrito
                # tiene que reventar antes de correr, no a mitad del barrido.
                q = r.get("que_busca")
                if not isinstance(q, dict) or set(q) != {"es", "en"}:
                    raise ValueError(
                        f"{r['id']}: `que_busca` va en los dos idiomas ({{es, en}}) porque "
                        f"acaba impreso en el expediente del cliente. Trae: {q!r}")
        return Paquete(d["obligacion"], d["paquete"], d["version"], d["autor"],
                       d["reglas"], motor)


EXT_CODIGO = {".py", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".json"}
EXT_PROSA = {".md", ".txt", ".rst"}

SIN_EXTENSION = {"dockerfile", "containerfile", "makefile", "procfile", "justfile", "vagrantfile"}
"""Ficheros de despliegue que no tienen sufijo y que hay que leer igual.

Los extractores del Anexo IV preguntan por el hardware en el que se ejecuta el
sistema, y esa respuesta vive en un `Dockerfile` que no se llama `algo.docker`.
Sin esta lista `Arbol.leer` no lo abria nunca y la seccion 1.e salia AUSENTE
aunque el manifiesto estuviera delante.

Entran en `texto` y NO entran en `codigo`, y la distincion importa: `codigo` es
lo que barren las reglas de control, y un `Dockerfile` lleva comentarios con `#`
que ningun quitaprosa de los que hay sabe quitar todavia. Meterlos en `codigo`
seria reabrir el D-4 (un comentario que satisface una regla) por la puerta de
atras. Si algun dia una regla necesita mirar dentro de un manifiesto, primero
hay que escribirle su quitaprosa; queda anotado como B-007.
"""


EXT_LEIDAS = {".py", ".yml", ".yaml", ".toml", ".cfg", ".json", ".md", ".txt", ".ini"}
"""Los sufijos cuyo CONTENIDO entra en el arbol, y por tanto en su digest.

Estaba escrito como un conjunto suelto dentro de `Arbol.leer`. Se saca aqui
porque el filtro de empujones necesita la misma lista para poder decir «este
empujon no pudo cambiar el sujeto», y dos listas habrian sido dos definiciones
de la misma propiedad: el dia que alguien anada `.tf` aqui y no alli, un cambio
en un fichero de Terraform se ignoraria en silencio. Regla 10, y en la
direccion peligrosa.
"""


def _es_de_despliegue(p: Path) -> bool:
    return p.suffix == "" and p.name.lower().split(".")[0] in SIN_EXTENSION


def lee_el_contenido_de(ruta: str) -> bool:
    """Si el arbol abriria ese fichero, dicho sobre una RUTA y no sobre un Path.

    El filtro de empujones solo tiene nombres: el codigo no esta -- ese es el
    argumento de coste entero -- asi que la pregunta hay que poder hacerla sin
    disco. Una sola definicion, dos sitios que la usan.
    """
    p = Path(ruta)
    return p.suffix in EXT_LEIDAS or _es_de_despliegue(p)


def _codigo_sin_prosa(fuente: str) -> str:
    """El codigo sin sus comentarios ni sus docstrings, y CON el resto de literales.

    La pasada adversarial de la fase 3 empujo esta funcion dos veces, y la
    segunda correccion es la interesante.

    Primero: un README que decia "NO hay forma de aprobar ni de anular ni
    kill_switch" SATISFIZO tres de las cinco reglas del articulo 14, y el
    comentario `# TODO: falta anular` era el mismo ataque desde dentro del
    codigo. Una herramienta de cumplimiento a la que se engana escribiendo la
    palabra en una frase negativa no vale nada.

    El primer arreglo quito tambien TODOS los literales de texto, y se paso:
    rompio `ACT-12-VERSION`, que busca `model_version` en un registro donde ese
    nombre es la clave de un diccionario. En Python una clave de diccionario es
    codigo, no prosa. La linea correcta no es codigo contra texto, es CODIGO
    contra PROSA: fuera comentarios y docstrings, dentro el resto de literales.

    Un docstring se reconoce por su posicion (primera sentencia de modulo,
    clase o funcion), asi que se usa `ast` para localizarlos y `tokenize` para
    los comentarios. Con expresiones regulares las dos cosas fallan en silencio
    con una comilla triple anidada.
    """
    import io
    import tokenize

    try:
        arbol = ast.parse(fuente)
    except SyntaxError:
        return fuente
    docstrings = set()
    for n in ast.walk(arbol):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            cuerpo = getattr(n, "body", [])
            if cuerpo and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant) \
               and isinstance(cuerpo[0].value.value, str):
                docstrings.add((cuerpo[0].lineno, cuerpo[0].col_offset))
    try:
        piezas = []
        for tok in tokenize.generate_tokens(io.StringIO(fuente).readline):
            if tok.type == tokenize.COMMENT:
                continue
            if tok.type == tokenize.STRING and tok.start in docstrings:
                continue
            piezas.append(tok.string)
        return " ".join(piezas)
    except (tokenize.TokenError, IndentationError):
        return fuente


@dataclass
class Arbol:
    """El repositorio leido una sola vez. Leerlo por regla seria O(reglas x ficheros)."""

    raiz: Path
    ficheros: dict[str, tuple[set[str], list[str]]] = field(default_factory=dict)
    texto: dict[str, str] = field(default_factory=dict)
    codigo: dict[str, str] = field(default_factory=dict)
    ilegibles: list[tuple[str, str]] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)

    def digest(self) -> str:
        """Lo que identifica a ESTE arbol. Es el sujeto de toda ejecucion.

        Resume el contenido, no los nombres: dos repositorios con los mismos
        ficheros renombrados NO son el mismo sujeto, y el mismo repositorio
        clonado en otra ruta SI lo es. De aqui cuelga la invalidacion
        selectiva entera -- a una evidencia la supera el digest sobre el que se
        tomo -- asi que resumirlo por la ruta habria hecho caducar todo cada
        vez que alguien clona en otro sitio.

        Los ilegibles entran en el resumen. Un arbol donde un fichero dejo de
        leerse ES otro arbol: si no entraran, una evidencia tomada cuando el
        fichero se leia seguiria valiendo cuando ya no se lee.
        """
        from ..evidencia.registro import digest as _d
        import hashlib
        cuerpo = {
            "ficheros": {n: hashlib.sha256(t.encode("utf-8")).hexdigest()
                         for n, t in sorted(self.texto.items())},
            "otros": sorted(set(self.todos) - set(self.texto)),
            "ilegibles": sorted([list(x) for x in self.ilegibles]),
        }
        return _d(cuerpo)

    @staticmethod
    def _dentro(raiz_real: Path, candidato: Path) -> bool:
        """Que el fichero este de verdad DENTRO de la raiz, ya resuelto.

        Un enlace simbolico dentro del repositorio apuntaba fuera y se leia sin
        mas: una auditoria externa lo reprodujo leyendo un fichero del sistema
        desde un repositorio de cliente. En una plataforma multi cliente eso es
        leer el repositorio de otro.

        Se resuelve la ruta y se compara con la raiz resuelta. Comparar cadenas
        sin resolver es lo que hacia la version anterior y es justo lo que un
        enlace simbolico esta disenado para saltarse.
        """
        try:
            real = candidato.resolve(strict=True)
        except (OSError, RuntimeError):
            return False                      # enlace roto o ciclo
        return real == raiz_real or raiz_real in real.parents

    @staticmethod
    def leer(raiz: str | Path) -> "Arbol":
        raiz = Path(raiz)
        # UNA RUTA QUE NO ESTA NO ES UN REPOSITORIO VACIO.
        #
        # `rglob` sobre una ruta que no existe no falla: devuelve cero
        # entradas. Asi que un arbol inexistente se leia como un arbol vacio, y
        # de ahi salia el peor documento que este producto puede emitir:
        #
        #   actaira comprobar /ruta/mal-escrita   ->   exit 0
        #   {"resultado": "no_aplica", "inspeccionado": [],
        #    "motivo_indeterminado": null}
        #
        # Es decir, una afirmacion de que el articulo 50 NO TE ATA, sin haber
        # mirado nada, con el codigo de salida que significa «se miro y no
        # aparecio nada». Y `sellar` la convertia en evidencia con su raiz
        # Merkle, lista para un auditor.
        #
        # Es la tercera negativa de la casa al reves: «nunca inferir lo no
        # observado». Y es «tres estados, nunca dos» otra vez -- «mire y no hay
        # puntos de generacion» y «no pude mirar» tienen que ser respuestas
        # distintas, porque significan cosas distintas.
        #
        # El motor generico SI sujetaba la invariante, pero desde el otro lado:
        # `Ejecucion.__post_init__` revienta si una ejecucion COMPLETADA no
        # leyo ni un fichero. Eso dejaba a `plan` y a `vigilar` soltando un
        # `ValueError` crudo con codigo 1, y al control del articulo 50 --que
        # sale por NO_APLICABLE, no por COMPLETADA-- sin sujetar en absoluto.
        # Se sujeta aqui porque aqui es donde se entra a mirar, y asi vale para
        # todos los verbos que leen un arbol.
        if not raiz.is_dir():
            que = "no existe" if not raiz.exists() else "no es un directorio"
            raise FileNotFoundError(
                f"{raiz}: {que}. No se puede observar lo que no se puede abrir, "
                f"y un arbol que no se pudo leer NO es un arbol vacio: decir "
                f"«no aplica» sobre el habria sido inventar el resultado.")
        raiz_real = raiz.resolve()
        a = Arbol(raiz)
        for p in sorted(raiz.rglob("*")):
            if not p.is_file() or any(x in {".git", "__pycache__", ".venv", "node_modules"} for x in p.parts):
                continue
            if not Arbol._dentro(raiz_real, p):
                a.ilegibles.append((nombre_en_el_arbol(raiz, p),
                                    "enlace que sale de la raiz del repositorio: no se lee, y se dice"))
                continue
            rel = nombre_en_el_arbol(raiz, p)
            a.todos.append(rel)
            if lee_el_contenido_de(rel):
                try:
                    a.texto[rel] = p.read_text(encoding="utf-8")
                except UnicodeDecodeError as e:
                    a.ilegibles.append((rel, f"UnicodeDecodeError: {e}")); continue
            if p.suffix in EXT_CODIGO and p.suffix != ".py":
                a.codigo[rel] = a.texto[rel]
            if p.suffix == ".py":
                a.codigo[rel] = _codigo_sin_prosa(a.texto[rel])
                try:
                    arbol = ast.parse(a.texto[rel])
                except SyntaxError as e:
                    a.ilegibles.append((rel, f"SyntaxError: {e}")); continue
                llamadas = [_ruta_punteada(n.func) for n in ast.walk(arbol) if isinstance(n, ast.Call)]
                a.ficheros[rel] = (_importa_paquete(arbol), [c for c in llamadas if c])
        return a


def _sitios(arbol: Arbol, firmas: list[str], imports: list[str]) -> list[str]:
    out = []
    for rel, (paquetes, llamadas) in arbol.ficheros.items():
        if imports and not (paquetes & set(imports)):
            continue
        if any(_casa(c, f) for c in llamadas for f in firmas):
            out.append(rel)
    return out


def sujeto_de(arbol: Arbol, paquete: Paquete) -> tuple[str, list[str]]:
    """El SUJETO de un paquete: exactamente los ficheros que sus reglas miran.

    De aqui cuelga la vigilancia entera, asi que la definicion importa mas que
    la implementacion. Dos alternativas malas y por que se descartaron:

    - El digest del repositorio entero. Cualquier cambio en cualquier fichero
      superaria TODA la evidencia, y el cliente veria un muro rojo cada vez que
      alguien corrige una errata en el README. Un muro rojo no es una senal:
      se aprende a ignorarlo en dos semanas.
    - El nombre del control. Entonces nada se supera nunca y la caducidad es
      solo un temporizador, que es lo que hace todo el mercado.

    Lo correcto es lo que la regla mira. Una regla de tipo `llamada` mira el
    codigo Python (acotado por sus imports si los declara); una de `fichero`
    mira la lista de nombres del arbol; una de `contenido` mira el texto o el
    codigo, acotado por `solo_en`. Se junta lo que miran todas las reglas del
    paquete y se digiere el mapa fichero -> digest de su contenido.

    Consecuencia buscada: tocar un README no supera un control del articulo 14
    que solo lee codigo, y cambiar el modelo si supera el control que lo mira.
    """
    mirados: set[str] = set()
    for r in paquete.reglas:
        tipo = r.get("tipo", "llamada")
        if tipo == "aportado":
            continue
        if tipo in ("llamada", "llamada_sin_pareja"):
            imports = set(r.get("requiere_import", []))
            for rel, (paquetes, _llamadas) in arbol.ficheros.items():
                if not imports or (paquetes & imports):
                    mirados.add(rel)
        elif tipo == "fichero":
            # Los nombres que CASAN sus patrones, no la lista entera del
            # repositorio. La primera version usaba `arbol.todos` y por tanto
            # cualquier fichero nuevo -- un apunte, una imagen -- superaba la
            # evidencia de que existe un directorio de evaluaciones. Eso es
            # sobreinvalidar, que produce el mismo muro rojo que el digest del
            # repositorio entero, solo que mas dificil de explicar.
            #
            # El conjunto de nombres que casan SI es el sujeto correcto: si
            # aparece uno nuevo que casa, cambia; si desaparecen todos, cambia;
            # si se anade algo que no casa, no cambia, y no deberia.
            mirados |= {f for f in arbol.todos
                        if any(re.search(p, f) for p in r["patrones"])}
            if not any(re.search(p, f) for p in r["patrones"] for f in arbol.todos):
                # Que NO exista ninguno es tambien una observacion, y hay que
                # poder distinguirla de "no se miro": se marca con un nombre
                # imposible en vez de dejar el sujeto vacio.
                mirados.add(f"(ninguno casa {r['id']})")
        elif tipo in ("contenido", "contenido_prohibido"):
            fuente = arbol.texto if r.get("ambito") == "documentacion" else arbol.codigo
            for rel in fuente:
                if not r.get("solo_en") or re.search(r["solo_en"], rel):
                    mirados.add(rel)

    contenidos = {}
    for rel in sorted(mirados):
        if rel.startswith("(ninguno casa "):
            contenidos[rel] = "(ausente)"
            continue
        crudo = arbol.texto.get(rel)
        if crudo is None:
            ruta = arbol.raiz / rel
            try:
                crudo = hashlib.sha256(ruta.read_bytes()).hexdigest()
            except OSError:
                crudo = "(ilegible)"
        else:
            crudo = hashlib.sha256(crudo.encode("utf-8")).hexdigest()
        contenidos[rel] = crudo
    return digest({"paquete": paquete.nombre, "version": paquete.version,
                   "ficheros": contenidos}), sorted(mirados)


def correr_paquete(arbol: Arbol, paquete: Paquete, idioma_error: str = "es"
                   ) -> tuple[ResultadoControl, list[Pregunta]]:
    """Corre un paquete y devuelve la PROYECCION de las cinco capas.

    Desde la fase 14 esto ya no construye un `ResultadoControl` a mano: arma
    una `Ejecucion` (que corrio, sobre que sujeto, con que version, que leyo),
    una `Observacion` (hallazgos, senales y limites, sin veredicto) y una
    `Suficiencia` cuando hay algo que el cliente tiene que aportar. El
    enumerado de siempre sale de proyectarlas, y `ResultadoControl` revienta si
    lo que trae no coincide con lo que las capas proyectan.

    Lo que se gana, y no es cosmetico: las SENALES. Antes lo encontrado se
    escribia como una frase en castellano dentro de `cubre` -- inconsultable,
    incruzable e incomprobable -- y ahora es un dato con su regla, su version y
    su sitio, del que la frase se genera. Una sola fuente y dos vistas.
    """
    from ..resultado import Ejecucion, EstadoEjecucion, Observacion, Senal
    from ..resultado.ejecucion import Sujeto
    from ..resultado.observacion import Limite
    from ..resultado.suficiencia import Falta
    from .. import __version__ as VERSION_MOTOR

    empezo = Ejecucion.ahora()
    hallazgos: list[Hallazgo] = []
    preguntas: list[Pregunta] = []
    senales: list[Senal] = []
    limites: list[Limite] = []
    faltas: list[Falta] = []
    aplicables = 0

    def _senal(r: dict, loc: str) -> None:
        senales.append(Senal(regla_id=r["id"], regla_version=r["version"],
                             paquete=paquete.nombre, que_se_buscaba=r["que_busca"],
                             localizacion=loc,
                             fuerza=FUERZA_POR_TIPO[r.get("tipo", "llamada")]))

    def _limite(texto: dict, por_que: str) -> None:
        limites.append(Limite(que=texto, por_que=por_que))

    for r in paquete.reglas:
        tipo = r.get("tipo", "llamada")
        # `_h` captura `r`, la variable del bucle, y eso es justo lo que la regla
        # B023 avisa. Aqui NO es un defecto: esta funcion se llama DENTRO de la
        # misma vuelta que la define, nunca se guarda para despues, asi que `r`
        # vale lo que tiene que valer. Se silencia nombrando la regla y no
        # apagandola en `pyproject.toml`: donde si se guarde una clausura para
        # mas tarde, la regla tiene que seguir cantando.
        def _h(loc: str) -> Hallazgo:
            return Hallazgo(regla_id=r["id"], regla_version=r["version"], autor=paquete.autor,  # noqa: B023
                            paquete=paquete.nombre, severidad=r["severidad"], localizacion=loc,  # noqa: B023
                            remediacion_es=r["remediacion"]["es"],  # noqa: B023
                            remediacion_en=r["remediacion"]["en"])  # noqa: B023

        if tipo == "aportado":
            preguntas.append(Pregunta(r["id"], paquete.obligacion, r["pregunta"],
                                      r.get("formato", "texto"), r["remediacion"]))
            _limite({"es": f"{r['id']}: {r['que_busca']['es']}",
                     "en": f"{r['id']}: {r['que_busca']['en']}"}, "falta_aporte")
            faltas.append(Falta(
                que={"es": f"no se ha aportado {r['que_busca']['es']}",
                     "en": f"{r['que_busca']['en']} has not been supplied"},
                que_hacer=r["remediacion"], quien="responsable"))
            continue

        if tipo == "llamada":
            sitios = _sitios(arbol, r["firmas"], r.get("requiere_import", []))
            aplicables += 1
            if sitios:
                for x in sitios: hallazgos.append(_h(x))
            else:
                _senal(r, f"ninguna aparicion en {len(arbol.ficheros)} ficheros Python")

        elif tipo == "llamada_sin_pareja":
            disparo = _sitios(arbol, r["firmas"], r.get("requiere_import", []))
            if not disparo:
                continue                      # la regla no aplica a este arbol
            aplicables += 1
            pareja = set(_sitios(arbol, r["pareja"], []))
            faltan = [s for s in disparo if s not in pareja]
            if faltan:
                for x in faltan: hallazgos.append(_h(x))
            else:
                _senal(r, f"los {len(disparo)} sitios tienen su pareja en el mismo fichero")

        elif tipo == "fichero":
            aplicables += 1
            casan = [f for f in arbol.todos if any(re.search(p, f) for p in r["patrones"])]
            if casan:
                _senal(r, f"{len(casan)} ficheros casan ({casan[0]})")
            else:
                hallazgos.append(_h("(el repositorio entero)"))

        elif tipo in ("contenido", "contenido_prohibido"):
            # `solo_si_hay_fichero`: la regla no aplica cuando no existe el
            # fichero que mira. Sin esto, la ausencia de la declaracion de
            # conformidad producia TRES hallazgos -- no existe, no dice que se
            # expide bajo responsabilidad exclusiva, no esta firmada -- que son
            # el mismo defecto contado tres veces. Un informe que multiplica un
            # problema por sus consecuencias se lee una vez y se ignora la
            # siguiente, que es como se pierde una herramienta buena.
            if r.get("solo_si_hay_fichero") and r.get("solo_en"):
                fuente0 = arbol.texto if r.get("ambito") == "documentacion" else arbol.codigo
                if not any(re.search(r["solo_en"], f) for f in fuente0):
                    _limite({"es": f"{r['id']}: {r['que_busca']['es']} (no hay fichero que mirar)",
                             "en": f"{r['id']}: {r['que_busca']['en']} (no file to look at)"},
                            "fuera_del_alcance_de_la_regla")
                    continue
            aplicables += 1
            # Por defecto una regla de contenido mira CODIGO, no prosa, y el
            # codigo va sin comentarios ni literales. Una regla que de verdad
            # quiera leer documentacion lo declara con `ambito: "documentacion"`,
            # y entonces su remediacion tiene que decir que lo que comprueba es
            # que algo este ESCRITO, no que exista.
            fuente = arbol.texto if r.get("ambito") == "documentacion" else arbol.codigo
            casan = [f for f, t in fuente.items()
                     if (not r.get("solo_en") or re.search(r["solo_en"], f))
                     and any(re.search(p, t, re.M) for p in r["patrones"])]
            if tipo == "contenido_prohibido":
                if casan:
                    for c in casan:
                        hallazgos.append(_h(c))
                else:
                    _senal(r, f"ninguna aparicion en {len(fuente)} ficheros")
            elif casan:
                _senal(r, casan[0])
            else:
                hallazgos.append(_h(r.get("solo_en", "(el repositorio entero)")))

    _limite({"es": "código en lenguajes que este motor no lee",
             "en": "code in languages this engine does not read"},
            "fuera_del_alcance_de_la_regla")
    _limite({"es": "llamadas construidas en ejecución o por getattr",
             "en": "calls built at runtime or through getattr"},
            "fuera_del_alcance_de_la_regla")
    if arbol.ilegibles:
        _limite({"es": f"{len(arbol.ilegibles)} ficheros que no se pudieron analizar",
                 "en": f"{len(arbol.ilegibles)} files that could not be analysed"},
                "no_legible")

    # NO_APLICABLE es un hecho de EJECUCION y no un resultado de la observacion:
    # ninguna regla del paquete tenia nada que mirar en este arbol. Antes era un
    # valor del mismo enumerado que «se miro y no aparecio nada», y las dos
    # cosas se contaban juntas.
    if aplicables == 0:
        estado = EstadoEjecucion.NO_APLICABLE
        motivo_ejec = {
            "es": (f"ninguna de las {len(paquete.reglas)} reglas de {paquete.nombre} tenía nada "
                   f"que mirar en este árbol: no es que se mirara y saliera limpio"),
            "en": (f"none of the {len(paquete.reglas)} rules in {paquete.nombre} had anything "
                   f"to look at in this tree: it is not that it was looked at and came out clean")}
    else:
        estado, motivo_ejec = EstadoEjecucion.COMPLETADA, None

    ejecucion = Ejecucion(
        analizador="actaira/motor-generico", analizador_version=VERSION_MOTOR,
        paquete=paquete.nombre, paquete_version=paquete.version,
        sujeto=Sujeto(tipo="repositorio", nombre=str(arbol.raiz), digest=arbol.digest()),
        empezo=empezo, termino=Ejecucion.ahora(), estado=estado, motivo=motivo_ejec,
        # Lo LEIDO, no lo parseado. `ficheros` son los .py que se pudieron
        # analizar como codigo; `texto` es todo lo que se abrio de verdad,
        # incluida la documentacion que miran las reglas de ambito documental.
        # Publicar solo los .py hacia que un paquete que solo mira prosa
        # declarara no haber leido nada.
        leidos=tuple(sorted(arbol.texto)),
        ilegibles=tuple((n, m) for n, m in arbol.ilegibles))

    observacion = Observacion(
        ejecucion_id=ejecucion.id,
        control_id=f"ACT-C-{paquete.obligacion.replace('AIA-', '')}",
        hallazgos=tuple(hallazgos), senales=tuple(senales), limites=tuple(limites))

    return ResultadoControl.de(
        ejecucion, observacion, obligacion_id=paquete.obligacion,
        idioma_frases=idioma_error), preguntas
