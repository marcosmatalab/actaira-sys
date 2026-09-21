# La puerta de aceptacion de Actaira, como atajo.
#
# POR QUE ESTE FICHERO SE QUEDO EN CUATRO LINEAS
# -----------------------------------------------
# Aqui vivian trece objetivos con la puerta de aceptacion entera escrita en
# bash: `python3`, rutas bajo `/tmp`, `rm -rf`, `sleep`, `curl`, `mktemp` y
# sustitucion de procesos. Tenia dos problemas.
#
# El primero es que no corria fuera de un Linux con GNU make. Un criterio de
# aceptacion que solo se puede comprobar en una de las maquinas donde corre el
# producto no es un criterio, es una costumbre; y el propio producto se vende
# como algo que se comporta igual en todas partes.
#
# El segundo es peor: la mayoria de esos objetivos NO PODIAN PONERSE ROJOS.
# `fase2` acababa en `|| true`; de `fase3` a `fase8`, en `; true` o en `| head`,
# que se come el codigo de salida. Este mismo fichero documentaba ese defecto
# -- sobre tres lineas del objetivo `contrato`, donde se arreglo -- y lo dejaba
# intacto en el resto. Una puerta que no puede ponerse roja no es una puerta.
#
# Asi que la puerta vive en `herramientas/todo.py`, donde cada fase AFIRMA algo
# y falla si no se cumple, y donde lo que no se puede medir aqui se declara
# OMITIDO con su motivo en vez de contarse como aprobado. Esto de aqui es un
# atajo para los dedos, y nada mas: si algun dia vuelve a haber logica en el
# Makefile, habra dos definiciones de cuando el producto esta bien.

PY ?= python

.PHONY: todo
todo:
	@$(PY) herramientas/todo.py

.PHONY: listar
listar:
	@$(PY) herramientas/todo.py --listar

# Cualquier fase suelta: `make fase F=api`, `make fase F="catalogo suite"`.
.PHONY: fase
fase:
	@$(PY) herramientas/todo.py $(F)

.PHONY: test
test:
	@$(PY) herramientas/todo.py suite

.PHONY: marca
marca:
	@$(PY) consola/marca/incrustar.py

.PHONY: consola panel portada
consola:
	@$(PY) -c "import json,sys;sys.path.insert(0,'motor/src');\
from pathlib import Path;\
from actaira_motor.catalogo.cargador import cargar;\
from actaira_motor.aplicabilidad.tabla import exportar;\
Path('consola/datos.json').write_text(json.dumps(exportar(cargar('catalogo')),ensure_ascii=False,separators=(',',':')),encoding='utf-8')"
	@$(PY) consola/construir.py

panel:
	@$(PY) panel/construir.py
	@$(PY) -c "import shutil;shutil.copyfile('panel/panel.html','plataforma/api/panel.html')"
	@echo "  panel copiado al servidor, que lo sirve desde su propio origen"

portada:
	@$(PY) sitio/construir.py
