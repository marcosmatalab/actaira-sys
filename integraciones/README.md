# Conectar Actaira a tus repositorios

Tres maneras, de menos a más compromiso.

## 1. A mano, en tu máquina

```bash
pip install actaira-motor
actaira plan .  --rol proveedor --alto-riesgo si
actaira anexo . --rol proveedor --alto-riesgo si            # el Anexo IV
actaira soa .   --rol proveedor --alto-riesgo si            # la declaración de aplicabilidad
```

No sube nada a ningún sitio. Todo lo que ves sale de leer tu repositorio.

## 2. En tu integración continua

Copia [`github/actaira.yml`](github/actaira.yml) a `.github/workflows/`. A
partir de ahí, cada empujón corre los controles, publica los hallazgos en la
pestaña Security con su remediación escrita al lado, y actualiza el almacén de
evidencia, que se versiona con el repositorio.

**La decisión de si un hallazgo bloquea el despliegue es tuya** y se escribe en
ese fichero. Actaira no la toma: dice lo que ve y lo que no ha podido ver.

## 3. Con la plataforma

El mismo motor, con el almacén de evidencia gestionado, el cuestionario
compartido entre las personas que tienen que contestarlo, y los avisos cuando
algo caduca sin que nadie empuje nada. El motor sigue siendo el mismo fichero
que puedes leer.

---

## Lo que NO hace, y conviene saberlo antes

- No emite un porcentaje de cumplimiento. No existe.
- No dice que cumples. Dice qué se comprobó leyendo bytes, con qué regla y de
  qué versión, y qué queda fuera del alcance de esa comprobación.
- No decide por ti si algo bloquea un despliegue.
- No sube tu código a ningún servidor en los modos 1 y 2.

## Por qué la vigilancia no sondea

A una evidencia la supera **el digest del sujeto sobre el que se tomó**, no el
nombre de ese sujeto. Un barrido de un fichero que no cambió no supera nada, y
uno de un fichero que sí cambió supera **solo** la evidencia atada al digest
viejo.

Consecuencia práctica, medida sobre el repositorio de ejemplo: añadir una línea
a `datos/README.md` supera **uno** de los doce controles con evidencia y deja
once intactos. El superado es el del artículo 10, que es el único que lee esa
ficha de datos. La alternativa habitual — el digest del
repositorio entero — pintaría un muro rojo cada vez que alguien corrige una
errata, y un muro rojo se aprende a ignorar en dos semanas.

Consecuencia de coste: sondear N repositorios cada minuto son N × 1440
ejecuciones al día. Reaccionar a un empujón más un vencimiento son del orden de
las veces que commiteas, más una.
