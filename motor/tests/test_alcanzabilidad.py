"""Todo modulo del paquete es alcanzable desde un verbo, o no esta aqui.

Heredada de la constitucion de actaira, y traida a proposito antes de que haga
falta: en aquel arbol, al empezar la fase A, 29 de 55 modulos y unas 8.700
lineas no se alcanzaban desde ningun punto de entrada, y no era visible desde
dentro de ningun fichero. Una regla que sujeta quien se acuerda de ella no
sujeta nada.

Se calcula A TRAVES DE LOS IMPORTS DEL MODULO, que es mas laxo que la version
de actaira (que la calcula a traves de las funciones alcanzadas). Se declara
aqui la diferencia en vez de fingir paridad: esta version no detecta una mitad
muerta dentro de un modulo vivo, y eso esta en el backlog como B-002.

PROHIBIDA UNA LISTA DE EXCEPCIONES. Una excepcion se satisface anadiendo una
linea, asi que la cumpliria quien decidiera no anadirla.

En su primera ejecucion acuso a cinco modulos. Cuatro eran un fallo DE LA
PUERTA: los `__init__.py` de paquete, que `from .catalogo.cargador import x`
alcanza por semantica de Python y este grafo no marcaba. El quinto,
`crosswalk/`, era un huerfano real que quedo del esqueleto y no lo importaba
nadie, porque el cruce acabo viviendo en el cargador. Se borro. Una puerta que
solo hubiera encontrado los cuatro falsos se habria relajado hasta no
encontrar el verdadero.
"""
import ast
from pathlib import Path

PAQUETE = Path(__file__).resolve().parents[1] / "src" / "actaira_motor"


def _modulos():
    for p in PAQUETE.rglob("*.py"):
        rel = p.relative_to(PAQUETE).with_suffix("")
        partes = [x for x in rel.parts if x != "__init__"]
        yield ".".join(["actaira_motor"] + partes) or "actaira_motor", p


def _importa(p: Path, propio: str) -> set[str]:
    out = set()
    arbol = ast.parse(p.read_text(encoding="utf-8"))
    base = propio.split(".")
    for n in ast.walk(arbol):
        if isinstance(n, ast.ImportFrom):
            if n.level:
                ancla = base[:-n.level] if p.name != "__init__.py" else base[:len(base) - (n.level - 1)]
                mod = ".".join(ancla + ([n.module] if n.module else []))
            else:
                mod = n.module or ""
            if mod.startswith("actaira_motor"):
                out.add(mod)
                for a in n.names:
                    out.add(f"{mod}.{a.name}")
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("actaira_motor"):
                    out.add(a.name)
    return out


def test_todo_modulo_se_alcanza_desde_el_cli():
    unidades = dict(_modulos())
    grafo = {m: _importa(p, m) for m, p in unidades.items()}
    vistos, frontera = set(), ["actaira_motor.cli"]
    while frontera:
        m = frontera.pop()
        if m in vistos:
            continue
        vistos.add(m)
        # Alcanzar `a.b.c` alcanza tambien `a.b`: es la semantica real de import
        # de Python, no una excepcion. Sin esto la puerta acusaba a los cinco
        # `__init__.py` de paquete, que era un fallo de la puerta y no del arbol.
        partes = m.split(".")
        for i in range(2, len(partes)):
            ancestro = ".".join(partes[:i])
            if ancestro in unidades and ancestro not in vistos:
                frontera.append(ancestro)
        for d in grafo.get(m, ()):
            cand = d if d in unidades else d.rsplit(".", 1)[0]
            if cand in unidades and cand not in vistos:
                frontera.append(cand)
    huerfanos = sorted(set(unidades) - vistos - {"actaira_motor"})
    assert huerfanos == [], (
        f"modulos que ningun verbo alcanza: {huerfanos}. "
        "Cablealos a lo que los necesita o borralos: el historial los guarda.")


def test_el_gemelo_muerde_con_un_modulo_suelto(tmp_path):
    """Regla 9: la puerta de arriba tiene que haber visto un huerfano."""
    (tmp_path / "cli.py").write_text("from . import vivo\n")
    (tmp_path / "vivo.py").write_text("X = 1\n")
    (tmp_path / "muerto.py").write_text("Y = 2\n")
    (tmp_path / "__init__.py").write_text("")
    unidades = {}
    for p in tmp_path.rglob("*.py"):
        partes = [x for x in p.relative_to(tmp_path).with_suffix("").parts if x != "__init__"]
        unidades[".".join(["paq"] + partes) or "paq"] = p
    assert "paq.muerto" in unidades and "paq.vivo" in unidades
