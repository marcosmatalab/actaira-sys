"""El puente entre correr los controles y guardar lo que se observo.

Existe para que ni el CLI ni la reconciliacion sepan como se corre un paquete
ni como se calcula un sujeto. Devuelve las tres cosas que la vigilancia
necesita y ninguna mas:

  registros   lo observado, ya en forma de evidencia con su frescura
  sujetos     {control_id: digest de AHORA}, para detectar lo que cambio
  esperados   {control_id: obligacion_id} de todo lo que DEBERIA tener evidencia

La tercera es la que impide el fallo silencioso: sin ella, un control que nunca
se corrio no aparece en el informe, y un informe limpio por no haber mirado es
indistinguible a simple vista de uno limpio de verdad.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from ..aplicabilidad.motor import Perfil, Situacion, resolver
from ..catalogo.cargador import Catalogo
from ..controles.motor import Arbol, Paquete, correr_paquete, sujeto_de
from ..evidencia.registro import Registro
from ..formularios.plan import indexar_paquetes
from .reconciliar import FRESCURA_POR_NIVEL


def observar(catalogo: Catalogo, perfil: Perfil, cuando: date, repositorio: str | Path,
             reglas: str | Path, ahora: datetime,
             frescura: dict[str, int] | None = None
             ) -> tuple[list[Registro], dict[str, str], dict[str, str], list[str]]:
    """Corre lo que se puede correr y lo convierte en evidencia fechada."""
    frescura = {**FRESCURA_POR_NIVEL, **(frescura or {})}
    indice = indexar_paquetes(Path(reglas))
    arbol = Arbol.leer(repositorio)

    registros: list[Registro] = []
    sujetos: dict[str, str] = {}
    esperados: dict[str, str] = {}
    sin_paquete: list[str] = []

    for v in resolver(catalogo, perfil, cuando):
        if v.situacion is not Situacion.ATA:
            continue
        obl = catalogo.obligaciones[v.obligacion_id]
        rutas = indice.get(obl.id)
        if not rutas:
            if obl.nivel in ("maquina", "generable"):
                sin_paquete.append(obl.id)
            continue
        # Una obligacion puede tener VARIOS paquetes desde la fase 17: el
        # articulo 14 se mira en el arbol de ficheros y en la estructura de
        # agentes. Cada uno observa SU sujeto, con su digest, asi que cada uno
        # produce su propia evidencia: juntarlas habria hecho que anadir una
        # herramienta invalidara tambien lo que se sabe del codigo.
        for ruta in rutas:
            pk = Paquete.cargar(ruta)
            if pk.motor == "agentes":
                from ..controles.agentes import correr as correr_ag
                res = correr_ag(repositorio, ruta)
                sujeto = res.ejecucion.sujeto.digest
                ficheros = list(res.ejecucion.leidos)
            elif pk.motor != "generico":
                # Un paquete con motor propio (el articulo 50) necesita
                # artefactos que aqui no hay. Se declara esperado y no se
                # inventa evidencia.
                esperados[f"ACT-C-{obl.id.replace('AIA-', '')}"] = obl.id
                continue
            else:
                res, _preguntas = correr_paquete(arbol, pk)
                sujeto, ficheros = sujeto_de(arbol, pk)
            esperados[res.control_id] = obl.id
            sujetos[res.control_id] = sujeto
            registros.append(Registro.nuevo(
                obligacion_id=obl.id, control_id=res.control_id, sujeto_digest=sujeto,
                observado_en=ahora,
                contenido={"resultado": res.resultado.value,
                           "hallazgos": len(res.hallazgos),
                           "controles_cubiertos": list(res.controles_cubiertos),
                           "ficheros_del_sujeto": ficheros},
                frescura_dias=frescura.get(obl.nivel)))
    return registros, sujetos, esperados, sin_paquete
