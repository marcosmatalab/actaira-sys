"""Carga los dos catalogos y resuelve el cruce entre ellos en las dos direcciones.

POR QUE LOS CATALOGOS SON DATOS Y NO CODIGO
-------------------------------------------
La alternativa era escribir las obligaciones como clases de Python, que es mas
comodo para el que programa y peor para todo lo demas. Tres razones, en orden
de peso:

  1. Quien tiene que revisar si el catalogo dice la verdad es un jurista o un
     consultor, no un desarrollador. Un JSON con titulo bilingue lo lee; un
     `@dataclass` con decoradores no.
  2. Un fichero de datos se valida contra un esquema en la puerta de release.
     Codigo no: cualquier comprobacion sobre el es un test que alguien escribe
     o no escribe.
  3. El catalogo cambia cuando cambia el Derecho, que es un ritmo distinto al
     del codigo. Mezclarlos obliga a publicar version del motor para corregir
     una fecha.

El coste aceptado: el cargador tiene que validar a mano lo que un tipo de
Python daria gratis. Por eso `validar()` es explicito y falla ruidosamente
nombrando el campo y el identificador, nunca devolviendo una lista vacia.

EL CRUCE VIVE EN UN SOLO FICHERO, Y ESTO SE APRENDIO ROMPIENDOLO
----------------------------------------------------------------
La primera version declaraba el cruce dos veces, en cada catalogo apuntando al
otro. La primera ejecucion del cargador encontro 30 asimetrias entre las dos
copias, y ese numero es el argumento: cada copia era coherente consigo misma y
el desacuerdo era invisible desde dentro de cualquiera de las dos. Regla 10 de
la constitucion, dos comprobaciones sobre la misma propiedad comparten su
definicion o se anulan.

Ahora el cruce esta en `crosswalk.json` y ninguno de los dos catalogos opina
sobre el otro. La puerta que queda, `verificar_cruce()`, ya no compara copias:
comprueba que cada par nombre identificadores que existen en los dos lados, que
es una pregunta con respuesta unica. Encontro cuatro pares huerfanos en su
primera pasada, y los cuatro eran articulos reales que faltaban en el catalogo.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

NIVELES = ("maquina", "generable", "juzgada", "organizativa")


class ErrorDeCatalogo(Exception):
    """Un catalogo mal formado es un error de carga con mensaje, nunca un traceback."""


@dataclass(frozen=True)
class Obligacion:
    id: str
    articulo: str
    titulo: dict[str, str]
    roles: tuple[str, ...]
    aplica_desde: date
    alcance: str
    nivel: str
    iso42001: tuple[str, ...]
    comprueba: tuple[str, ...] = ()
    vigente_declarado: bool = False
    bruto: dict[str, Any] | None = None
    # EL CALENDARIO PARTIDO DEL REGLAMENTO (UE) 2026/1744
    # -----------------------------------------------------
    # El Omnibus digital sobre IA aplazo las Secciones 1, 2 y 3 del Capitulo III
    # con DOS fechas distintas segun por donde el sistema llega a ser de alto
    # riesgo: 2 de diciembre de 2027 para los del Anexo III (articulo 6.2) y 2
    # de agosto de 2028 para los que son componente de seguridad de un producto
    # regulado (Anexo I, articulo 6.1). Publicar una sola fecha obliga a elegir,
    # y las dos elecciones mienten a la mitad de los clientes: la temprana les
    # mete prisa por nada, la tardia les quita ocho meses de plazo.
    #
    # Cuando esto esta puesto, `aplica_desde` NO se puede contestar sin saber la
    # via, y el motor devuelve INDETERMINADA pidiendola en vez de elegir una.
    aplica_desde_por_via: dict[str, date] | None = None

    def desde(self, via: str | None) -> date | None:
        """La fecha para ESTA via. None cuando hace falta la via y no se dio."""
        if self.aplica_desde_por_via is None:
            return self.aplica_desde
        if via is None:
            return None
        return self.aplica_desde_por_via.get(via, self.aplica_desde)

    def vigente_el(self, cuando: date, via: str | None = None) -> bool:
        d = self.desde(via)
        return d is not None and cuando >= d


@dataclass(frozen=True)
class Requisito:
    """Un DEBER del Reglamento que se puede satisfacer o incumplir por separado.

    No es un apartado del texto. Hay deberes repartidos por varios apartados y
    apartados que dicen tres cosas, asi que partir por apartados habria dado un
    mapa con la forma del documento y no con la forma de lo exigible.

    Existe por una razon concreta: la SUFICIENCIA se decide por requisito. Un
    articulo con seis deberes cerrado entero porque uno esta cubierto es la
    manera mas rapida de emitir un expediente falso, y es lo que podia pasar
    mientras la unidad mas pequena fuera el articulo.
    """

    id: str
    articulo: str
    apartados: tuple[str, ...]
    actores: tuple[str, ...]
    nivel: str
    exige: dict[str, str]
    cubierto_por: tuple[str, ...] = ()
    por_que_no_esta_cubierto: dict[str, str] | None = None

    @property
    def cubierto(self) -> bool:
        return bool(self.cubierto_por)


@dataclass(frozen=True)
class Control42001:
    id: str
    grupo: str
    titulo: dict[str, str]
    nivel: str
    aiact: tuple[str, ...]


@dataclass(frozen=True)
class Clausula:
    """Una clausula de las 4 a la 10 de la norma, que es lo que de verdad se audita.

    El Anexo A no certifica a nadie: entra por la puerta de la 6.1.3, que obliga
    a compararse con el y a justificar inclusiones y exclusiones en una
    declaracion de aplicabilidad. Un producto que solo listara los 38 controles
    dejaria fuera la mitad que un auditor mira.
    """

    id: str
    clausula: str
    titulo: dict[str, str]
    nivel: str
    exige_informacion_documentada: bool
    produce: str | None = None
    depende_de: tuple[str, ...] = ()
    formulario: str = ""
    # EL CICLO, QUE ES LO QUE DISTINGUE UN SISTEMA DE UNA LISTA
    # ----------------------------------------------------------
    # `depende_de` dice de quien viene esta clausula. `alimenta` dice a quien
    # va, y sin el las 32 clausulas son 32 casillas marcables en cualquier
    # orden: la 10.2 producia un registro de no conformidades que nadie
    # consumia. Con las dos, el ciclo se puede recorrer y se puede comprobar
    # que cierra.
    alimenta: tuple[str, ...] = ()
    # Una auditoria interna de hace tres anos no es una auditoria interna. Las
    # clausulas que recurren llevan su vigencia, y la caducidad que ya existe
    # para la evidencia tecnica vale igual para los registros de gestion.
    periodicidad: str = "continua"
    vigencia_dias: int = 365


@dataclass(frozen=True)
class PreguntaDeFormulario:
    """Lo que hay que pedirle a una persona porque el repositorio no lo contiene.

    `sirve_a` es la razon de ser de este producto en una linea: una sola
    pregunta puede cerrar a la vez un articulo del Reglamento, una clausula de
    la norma y un control del Anexo A. El cliente contesta una vez y la
    respuesta se reutiliza en los tres sitios; lo que NO se reutiliza es la
    conclusion, que se firma por separado en cada marco.

    `salta_si_cubre` es la otra mitad: si un control leyo los bytes y ya
    contesto, la pregunta no se hace. Esa resta es la diferencia entre un
    cuestionario de trescientas preguntas y uno de treinta.
    """

    id: str
    paquete: str
    sirve_a: tuple[str, ...]
    destinatario: str
    texto: dict[str, str]
    ayuda: dict[str, str]
    formato: str
    vigencia_dias: int
    exige: dict[str, Any] = field(default_factory=dict)
    opciones: tuple[dict[str, str], ...] = ()
    salta_si_cubre: tuple[str, ...] = ()
    si: dict[str, str] | None = None
    produce: str | None = None


FORMATOS = ("texto_corto", "texto_largo", "si_no", "fecha", "lista", "eleccion", "persona", "artefacto")
DESTINATARIOS = ("direccion", "responsable", "tecnico")


@dataclass
class Catalogo:
    obligaciones: dict[str, Obligacion]
    controles_iso: dict[str, Control42001]
    pares: tuple[tuple[str, str], ...] = ()
    clausulas: dict[str, Clausula] = field(default_factory=dict)
    requisitos: dict[str, Requisito] = field(default_factory=dict)
    preguntas: dict[str, PreguntaDeFormulario] = field(default_factory=dict)
    formularios: dict[str, dict[str, Any]] = field(default_factory=dict)

    def por_nivel(self, nivel: str) -> list[Obligacion]:
        return [o for o in self.obligaciones.values() if o.nivel == nivel]

    def verificar_cruce(self) -> list[str]:
        """Devuelve los pares rotos. Lista vacia solo si de verdad no hay ninguno.

        No devuelve un booleano: una validacion que dice si o no pierde
        exactamente la informacion que hace falta para arreglarla. Y no
        devuelve lista vacia cuando no pudo mirar, que es el modo de fallo que
        la regla 11 persigue: si el fichero de cruce no esta, `cargar()` ya
        reviento antes de llegar aqui.
        """
        problemas: list[str] = []
        for a, c in self.pares:
            if a not in self.obligaciones:
                problemas.append(f"el par ({a}, {c}) nombra {a}, que no existe en el catalogo del Reglamento")
            if c not in self.controles_iso:
                problemas.append(f"el par ({a}, {c}) nombra {c}, que no existe en el Anexo A")
        return problemas

    def sirve_a_existe(self, ident: str) -> bool:
        return (ident in self.obligaciones or ident in self.controles_iso
                or ident in self.clausulas)

    def preguntas_de(self, ident: str) -> tuple[PreguntaDeFormulario, ...]:
        """Las preguntas que sirven a una obligacion, una clausula o un control."""
        return tuple(q for q in self.preguntas.values() if ident in q.sirve_a)

    def verificar_formularios(self, controles_declarados: set[str]) -> list[str]:
        """Las cuatro maneras de que un banco de preguntas mienta, y el hueco.

        Un formulario roto no revienta: contesta de menos, que es el fallo que
        la regla 11 persigue. Las cuatro primeras comprobaciones son de
        integridad referencial; la quinta es la que de verdad importa, porque
        una obligacion organizativa sin ninguna pregunta que la sirva es un
        agujero silencioso: el plan la deja en `solo_formulario` y el
        formulario no la pregunta, asi que nadie la contesta nunca y nadie se
        entera.
        """
        problemas: list[str] = []
        for q in self.preguntas.values():
            for ident in q.sirve_a:
                if not self.sirve_a_existe(ident):
                    problemas.append(f"{q.id}: sirve a '{ident}', que no existe en ningun catalogo")
            for ctrl in q.salta_si_cubre:
                if ctrl not in controles_declarados:
                    problemas.append(f"{q.id}: se salta si se cubre '{ctrl}', que ningun paquete de reglas declara")
            if q.formato not in FORMATOS:
                problemas.append(f"{q.id}: formato '{q.formato}' no esta en {FORMATOS}")
            if q.destinatario not in DESTINATARIOS:
                problemas.append(f"{q.id}: destinatario '{q.destinatario}' no esta en {DESTINATARIOS}")
            if q.formato == "eleccion" and not q.opciones:
                problemas.append(f"{q.id}: es de eleccion y no trae opciones")
            if q.si and q.si.get("pregunta") not in self.preguntas:
                problemas.append(f"{q.id}: depende de '{q.si.get('pregunta')}', que no es una pregunta")

        servidos = {i for q in self.preguntas.values() for i in q.sirve_a}
        for c in self.clausulas.values():
            if c.id not in servidos:
                problemas.append(f"{c.id} ({c.clausula}) no tiene ninguna pregunta que la sirva: "
                                 f"nadie la contestaria nunca")
        for o in self.obligaciones.values():
            if o.nivel in ("organizativa", "juzgada") and o.id not in servidos:
                problemas.append(f"{o.id} (articulo {o.articulo}) es de nivel {o.nivel} y no tiene pregunta: "
                                 f"el plan la dejaria en solo_formulario y el formulario no la pediria")
        return problemas

    def verificar_sistema_de_gestion(self) -> list[str]:
        """Que el SGIA sea un ciclo y no una lista. Devuelve lo que no encaja.

        Cuatro comprobaciones, y la cuarta es la que de verdad importa:

          1. `alimenta` y `depende_de` nombran clausulas que existen;
          2. las dos direcciones son coherentes: si A alimenta a B, B depende
             de A o B es una clausula de entrada declarada. Sin esto, cada
             direccion podria ser coherente consigo misma y estar en
             desacuerdo con la otra -- que es como el cruce de catalogos
             acumulo 30 asimetrias en la fase 0;
          3. toda clausula que exige informacion documentada dice CUAL: si no,
             el sistema pide guardar registros y no dice de que;
          4. y el ciclo CIERRA. Que exista un camino desde la revision por la
             direccion y desde la no conformidad de vuelta a la planificacion
             es lo que convierte 32 casillas en un sistema de gestion.
        """
        problemas: list[str] = []
        ids = set(self.clausulas)
        for c in self.clausulas.values():
            for otro in c.alimenta:
                if otro not in ids:
                    problemas.append(f"{c.id} alimenta a {otro}, que no es una clausula")
            for otro in c.depende_de:
                if otro not in ids:
                    problemas.append(f"{c.id} depende de {otro}, que no es una clausula")
        for c in self.clausulas.values():
            for otro in c.depende_de:
                if otro in ids and c.id not in self.clausulas[otro].alimenta:
                    problemas.append(
                        f"{c.id} dice depender de {otro} y {otro} no dice alimentar a {c.id}: "
                        f"las dos direcciones tienen que decir lo mismo (regla 10)")
        for c in self.clausulas.values():
            if c.exige_informacion_documentada and not c.produce:
                problemas.append(
                    f"{c.id} exige informacion documentada y no dice cual produce: el sistema "
                    f"pide guardar registros sin decir de que")
        for origen, hasta in (("ISO-9.3.3", "ISO-6.2"), ("ISO-10.2", "ISO-6.1.2"),
                              ("ISO-9.1", "ISO-10.2")):
            if not self._alcanza(origen, hasta):
                problemas.append(
                    f"el ciclo no cierra: desde {origen} no se llega a {hasta}, asi que lo que "
                    f"sale del final no vuelve a entrar por el principio")
        return problemas

    def _alcanza(self, origen: str, destino: str) -> bool:
        vistos, pila = set(), [origen]
        while pila:
            actual = pila.pop()
            if actual == destino and actual != origen:
                return True
            if actual in vistos or actual not in self.clausulas:
                continue
            vistos.add(actual)
            pila.extend(self.clausulas[actual].alimenta)
        return destino in self.clausulas[origen].alimenta

    def requisitos_de(self, articulo: str) -> tuple[Requisito, ...]:
        """Los deberes de un articulo, en el orden en que se catalogaron."""
        return tuple(r for r in self.requisitos.values() if r.articulo == articulo)

    def huecos_de_cobertura(self) -> list[Requisito]:
        """Los requisitos que ninguna regla y ninguna pregunta cubren todavia.

        Se publica como metodo y no como un aviso al cargar porque es una cifra
        de PRODUCTO: es lo que hay que bajar, y esconderla dentro de un log la
        convertiria en algo que nadie mira. La puerta que exige un motivo
        escrito para cada uno vive en las pruebas del catalogo.
        """
        return [r for r in self.requisitos.values() if not r.cubierto]

    def iso_de(self, obligacion_id: str) -> tuple[str, ...]:
        return tuple(c for a, c in self.pares if a == obligacion_id)

    def aiact_de(self, control_id: str) -> tuple[str, ...]:
        return tuple(a for a, c in self.pares if c == control_id)


def orden_de_articulo(articulo: str) -> tuple[int, str]:
    """El orden de lectura del Reglamento. UNA definicion, y esta.

    Desde el Reglamento (UE) 2026/1744 hay articulos «bis»: 4 bis va entre el 4
    y el 5, no al final ni en el hueco del 5. Ordenar por `int(articulo)` --que
    es lo que hacia la tabla-- revienta con el primero que aparece, y ordenar
    por cadena pone el 10 antes del 2. El numero manda, y el sufijo desempata.
    """
    numero = "".join(c for c in articulo if c.isdigit())
    sufijo = articulo[len(numero):]
    return (int(numero or 0), sufijo)


def _exigir(dic: dict[str, Any], campo: str, donde: str) -> Any:
    if campo not in dic:
        raise ErrorDeCatalogo(f"{donde}: falta el campo obligatorio '{campo}'")
    return dic[campo]


def controles_declarados(dir_reglas: str | Path) -> set[str]:
    """Los identificadores de control que declaran los paquetes de reglas.

    Vive aqui y no en el Makefile ni en el test porque los tres preguntan lo
    mismo, y tres maneras de contestarlo son tres maneras de discrepar.
    """
    fuera: set[str] = set()
    for ruta in sorted(Path(dir_reglas).glob("*.json")):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        fuera |= {r["id"] for r in datos.get("reglas", [])}
    return fuera


def cargar(raiz: str | Path) -> Catalogo:
    raiz = Path(raiz)
    ruta_aia = raiz / "ai-act" / "obligaciones.json"
    ruta_iso = raiz / "iso42001" / "anexo-a.json"
    ruta_cruce = raiz / "crosswalk.json"
    for r in (ruta_aia, ruta_iso, ruta_cruce):
        if not r.is_file():
            raise ErrorDeCatalogo(f"no encuentro el catalogo en {r}")

    datos_aia = json.loads(ruta_aia.read_text(encoding="utf-8"))
    datos_iso = json.loads(ruta_iso.read_text(encoding="utf-8"))

    # Los requisitos son OPCIONALES al cargar y obligatorios en la puerta: un
    # arbol sin ellos sigue arrancando -- hace falta para poder anadirlos por
    # partes -- y `test_catalogo` se niega a dejar pasar un articulo en alcance
    # sin partir. Reventar aqui habria obligado a escribir los 88 de una vez.
    requisitos: dict[str, Requisito] = {}
    ruta_req = raiz / "ai-act" / "requisitos.json"
    if ruta_req.is_file():
        for bruto in json.loads(ruta_req.read_text(encoding="utf-8"))["requisitos"]:
            rid = _exigir(bruto, "id", str(ruta_req))
            if rid in requisitos:
                raise ErrorDeCatalogo(f"{rid}: identificador de requisito repetido")
            nivel = _exigir(bruto, "nivel", rid)
            if nivel not in NIVELES:
                raise ErrorDeCatalogo(f"{rid}: nivel '{nivel}' no esta en {NIVELES}")
            exige = _exigir(bruto, "exige", rid)
            for idioma in ("es", "en"):
                if not exige.get(idioma, "").strip():
                    raise ErrorDeCatalogo(f"{rid}: falta lo que exige en '{idioma}'")
            cubierto = tuple(bruto.get("cubierto_por", ()))
            if not cubierto and not bruto.get("por_que_no_esta_cubierto"):
                raise ErrorDeCatalogo(
                    f"{rid}: no lo cubre nada y no dice por que. Un mapa de cobertura que "
                    f"solo ensena lo cubierto no es un mapa de cobertura.")
            requisitos[rid] = Requisito(
                id=rid, articulo=_exigir(bruto, "articulo", rid),
                apartados=tuple(_exigir(bruto, "apartados", rid)),
                actores=tuple(_exigir(bruto, "actores", rid)),
                nivel=nivel, exige=exige, cubierto_por=cubierto,
                por_que_no_esta_cubierto=bruto.get("por_que_no_esta_cubierto"))

    obligaciones: dict[str, Obligacion] = {}
    for bruto in _exigir(datos_aia, "obligaciones", str(ruta_aia)):
        oid = _exigir(bruto, "id", str(ruta_aia))
        nivel = _exigir(bruto, "nivel", oid)
        if nivel not in NIVELES:
            raise ErrorDeCatalogo(f"{oid}: nivel '{nivel}' no esta en {NIVELES}")
        titulo = _exigir(bruto, "titulo", oid)
        for idioma in ("es", "en"):
            if idioma not in titulo or not titulo[idioma].strip():
                raise ErrorDeCatalogo(f"{oid}: falta el titulo en '{idioma}'")
        if oid in obligaciones:
            raise ErrorDeCatalogo(f"{oid}: identificador repetido")
        obligaciones[oid] = Obligacion(
            id=oid,
            articulo=_exigir(bruto, "articulo", oid),
            titulo=titulo,
            roles=tuple(_exigir(bruto, "roles", oid)),
            aplica_desde=date.fromisoformat(_exigir(bruto, "aplica_desde", oid)),
            aplica_desde_por_via=(
                {k: date.fromisoformat(v) for k, v in bruto["aplica_desde_por_via"].items()}
                if bruto.get("aplica_desde_por_via") else None),
            alcance=_exigir(bruto, "alcance", oid),
            nivel=nivel,
            iso42001=(),
            comprueba=tuple(bruto.get("comprueba", ())),
            vigente_declarado=bool(bruto.get("vigente", False)),
            bruto=bruto,
        )

    controles: dict[str, Control42001] = {}
    for bruto in _exigir(datos_iso, "controles", str(ruta_iso)):
        cid = _exigir(bruto, "id", str(ruta_iso))
        titulo = _exigir(bruto, "titulo", cid)
        for idioma in ("es", "en"):
            if idioma not in titulo or not titulo[idioma].strip():
                raise ErrorDeCatalogo(f"{cid}: falta el titulo en '{idioma}'")
        controles[cid] = Control42001(
            id=cid,
            grupo=".".join(cid.split(".")[:2]),
            titulo=titulo,
            nivel=_exigir(bruto, "nivel", cid),
            aiact=(),
        )

    clausulas: dict[str, Clausula] = {}
    ruta_cl = raiz / "iso42001" / "clausulas.json"
    if ruta_cl.is_file():
        for bruto in _exigir(json.loads(ruta_cl.read_text(encoding="utf-8")), "clausulas", str(ruta_cl)):
            cid = _exigir(bruto, "id", str(ruta_cl))
            if cid in clausulas:
                raise ErrorDeCatalogo(f"{cid}: clausula repetida")
            nivel = _exigir(bruto, "nivel", cid)
            if nivel not in NIVELES:
                raise ErrorDeCatalogo(f"{cid}: nivel '{nivel}' no esta en {NIVELES}")
            titulo = _exigir(bruto, "titulo", cid)
            for idioma in ("es", "en"):
                if idioma not in titulo or not titulo[idioma].strip():
                    raise ErrorDeCatalogo(f"{cid}: falta el titulo en '{idioma}'")
            clausulas[cid] = Clausula(
                id=cid, clausula=_exigir(bruto, "clausula", cid), titulo=titulo, nivel=nivel,
                exige_informacion_documentada=bool(_exigir(bruto, "exige_informacion_documentada", cid)),
                produce=bruto.get("produce"), depende_de=tuple(bruto.get("depende_de", ())),
                formulario=bruto.get("formulario", ""),
                alimenta=tuple(bruto.get("alimenta", ())),
                periodicidad=bruto.get("periodicidad", "continua"),
                vigencia_dias=int(bruto.get("vigencia_dias", 365)))

    preguntas: dict[str, PreguntaDeFormulario] = {}
    formularios: dict[str, dict[str, Any]] = {}
    dir_form = raiz / "formularios"
    if dir_form.is_dir():
        for ruta in sorted(dir_form.glob("*.json")):
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            paquete = _exigir(datos, "paquete", str(ruta))
            if paquete != ruta.stem:
                raise ErrorDeCatalogo(f"{ruta.name}: declara el paquete '{paquete}' y se llama '{ruta.stem}'")
            formularios[paquete] = {k: v for k, v in datos.items() if k != "preguntas"}
            for bruto in _exigir(datos, "preguntas", str(ruta)):
                qid = _exigir(bruto, "id", str(ruta))
                if qid in preguntas:
                    raise ErrorDeCatalogo(f"{qid}: pregunta repetida, la segunda en {ruta.name}")
                for campo in ("sirve_a", "destinatario", "texto", "ayuda", "formato", "vigencia_dias"):
                    _exigir(bruto, campo, qid)
                for cual in ("texto", "ayuda"):
                    for idioma in ("es", "en"):
                        if not bruto[cual].get(idioma, "").strip():
                            raise ErrorDeCatalogo(f"{qid}: falta '{cual}' en '{idioma}'")
                if not bruto["sirve_a"]:
                    raise ErrorDeCatalogo(f"{qid}: no dice a que sirve, asi que no se puede justificar preguntarla")
                preguntas[qid] = PreguntaDeFormulario(
                    id=qid, paquete=paquete, sirve_a=tuple(bruto["sirve_a"]),
                    destinatario=bruto["destinatario"], texto=bruto["texto"], ayuda=bruto["ayuda"],
                    formato=bruto["formato"], vigencia_dias=int(bruto["vigencia_dias"]),
                    exige=bruto.get("exige", {}), opciones=tuple(bruto.get("opciones", ())),
                    salta_si_cubre=tuple(bruto.get("salta_si_cubre", ())), si=bruto.get("si"),
                    produce=bruto.get("produce"))

    datos_cruce = json.loads(ruta_cruce.read_text(encoding="utf-8"))
    pares = tuple(
        (p["aiact"], p["iso42001"]) for p in _exigir(datos_cruce, "pares", str(ruta_cruce))
    )
    return Catalogo(obligaciones=obligaciones, controles_iso=controles, pares=pares,
                    requisitos=requisitos,
                    clausulas=clausulas, preguntas=preguntas, formularios=formularios)
