<div align="center">

# Actaira

**El Reglamento (UE) 2024/1689 y la ISO/IEC 42001, comprobados leyendo tu repositorio.**
Con procedencia por afirmación, y sin inventarse un porcentaje.

[![Licencia](https://img.shields.io/badge/licencia-Apache--2.0-90099C)](LICENSE)
[![Pruebas](https://img.shields.io/badge/pruebas-en%20motor%2Ftests-90099C)](motor/tests)

</div>

---

## El problema

Una consultora de cumplimiento te entrega un mapa de riesgos, una matriz de
controles y un cuestionario de trescientas preguntas. Todo eso describe lo que
tu organización **dice** que hace. Ninguna de esas tres cosas mira tu código.

El Reglamento no está escrito así. El artículo 12 pide que el sistema
**registre automáticamente** acontecimientos durante su ciclo de vida. El 14
pide que una persona **pueda intervenir** en el sistema. El 15 pide un nivel de
exactitud **mantenido**. Eso son propiedades de un programa, y un programa se
puede leer.

Actaira lee el repositorio, decide lo que se puede decidir leyendo bytes, y
dice en voz alta lo que no puede decidir.

## Las cuatro negativas

No son aspiraciones: son invariantes con puertas que las sujetan, y cada una
tiene su prueba.

| | |
|---|---|
| **Nunca un número** | No existe un «87 % de cumplimiento» y no se va a emitir. Se publican recuentos de obligaciones, nunca proporciones. |
| **Nunca juzgar, solo citar** | Ver `verify_signature` en el código es ver un patrón, no saber que hay una medida adoptada. La interpretación la firma una persona. |
| **Nunca inferir lo no observado** | Un `INDETERMINADO` sin motivo escrito es un `NO_CUMPLE` disfrazado. Si no se pudo mirar, se dice qué y por qué. |
| **Nunca actuar sobre lo observado** | Actaira dice qué hay que volver a mirar. Si eso bloquea un despliegue lo decides tú, en tu fichero de CI, donde la decisión se revisa. |

## Lo que hace, en cuatro comandos

```bash
pip install git+https://github.com/marcosmatalab/actaira-sys

actaira plan .    --rol proveedor --alto-riesgo si     # qué te ata y qué se comprobó
actaira preguntar . --rol proveedor --alto-riesgo si   # lo que hay que preguntarte, y lo que no
actaira anexo .   --rol proveedor --alto-riesgo si     # el Anexo IV, con procedencia por sección
actaira soa .     --rol proveedor --alto-riesgo si     # la declaración de aplicabilidad de la ISO 42001
```

> Se instala desde el repositorio y no desde PyPI porque **todavía no está
> publicado en PyPI**, y decir `pip install actaira-motor` sería mandarte a un
> 404 en la primera orden. Cuando se publique, esa será la línea y esta nota
> desaparece. Hay una puerta que lo comprueba: mientras
> `PUBLICADO_EN_PYPI` sea `False`, ningún documento puede decir lo contrario.

Necesita Python 3.12 o posterior. Nada de esto sube tu código a ningún sitio y
no hace falta cuenta: se puede correr con la red desconectada.

Nada de esto sube tu código a ningún sitio.

### El cuestionario que sobra

Cada pregunta del banco declara a qué sirve **con identificadores de los tres
catálogos a la vez**: obligaciones del Reglamento, cláusulas 4 a 10 de la
norma, y controles del Anexo A. «¿Quién responde de que el sistema de gestión
cumpla, y quién informa de su desempeño a la dirección?» cierra el artículo 16,
el 17, la cláusula 5.3 y el control A.3.2 con una sola respuesta.

Y una pregunta desaparece en cuanto un control lee los bytes que la contestan.
La resta se publica con los identificadores de los controles que la
produjeron, para que se pueda auditar: un número sin la lista detrás es
publicidad.

### La vigilancia que no sondea

A una evidencia la supera **el digest del sujeto sobre el que se tomó**, no el
nombre de ese sujeto. Y el sujeto de un control son exactamente los ficheros
que ese control lee.

> Medido sobre el repositorio de ejemplo: añadir una línea a `datos/README.md`
> supera **uno** de los doce controles con evidencia y deja **once** intactos.
> El superado es el del artículo 10, que es el único que lee esa ficha de datos.

| alternativa | qué pasa |
|---|---|
| digest del repositorio entero | muro rojo en cada errata; se aprende a ignorar en dos semanas |
| el nombre del control | nada se supera nunca; la caducidad es un temporizador |

Consecuencia de coste: sondear N repositorios cada minuto son N × 1440
ejecuciones al día. Reaccionar a un empujón más un vencimiento son del orden de
las veces que commiteas, más una.

## En tu integración continua

Copia [`integraciones/github/actaira.yml`](integraciones/github/actaira.yml) a
`.github/workflows/`. Los hallazgos salen en **SARIF**, o sea en la pestaña
Security y dentro de la revisión del pull request, con la remediación escrita
al lado. El hallazgo llega a quien puede arreglarlo, el día que escribió la
línea.

La puerta que bloquea el despliegue va **comentada** en la plantilla. Hay un
test que comprueba que sigue comentada.

## Lo que NO hace

- No emite un porcentaje de cumplimiento. No existe.
- No dice que cumples. Dice qué se comprobó leyendo bytes, con qué regla, de
  qué versión y de qué autor, y qué queda fuera del alcance de esa comprobación.
- No cierra un control del Anexo A porque una comprobación del Reglamento salga
  limpia: la norma pide cosas que el Reglamento no pide, y el cruce lo dice.
- No firma por ti. La declaración UE de conformidad se emite con la palabra
  **BORRADOR** en el encabezado mientras no exista la firma del punto 8 del
  Anexo V, y no hay bandera que la quite por otra vía: los puntos 3 y 4 son
  afirmaciones del proveedor bajo su exclusiva responsabilidad.

## Cómo está hecho

```
catalogo/     el contenido normativo como DATOS, no como código, para que lo
              revise un jurista y no un programador
motor/        Python. Un motor genérico de controles; los artículos son JSON
consola/      se construye desde el motor con `make consola`, no se edita
integraciones/ SARIF y la plantilla de CI
.github/      la puerta corrida en DOS sistemas. Un defecto que solo se ve en
              uno es invisible mientras las pruebas corran en el otro, y eso
              ya pasó dos veces
docs/         ARQUITECTURA.md (las decisiones y por qué) y BACKLOG.md (los
              defectos encontrados en cada pasada adversarial, con su nombre)
```

`make todo` corre las puertas: el catálogo, el cruce, los formularios, la
ortografía del castellano, la consola y las <!--cifra:pruebas-->562<!--/cifra--> pruebas de Python, más <!--cifra:pruebas_go-->98<!--/cifra--> de Go.

Cada fase cierra con una **pasada adversarial** antes de abrir la siguiente, y
los defectos encontrados se escriben en `docs/BACKLOG.md` con su número y su
lección. <!--cifra:defectos_adversariales-->107<!--/cifra--> hasta hoy. Los más caros no eran fallos: eran respuestas
plausibles y falsas, que es lo peor que puede emitir una herramienta que va a
un auditor.

## Licencia y alcance de los catálogos

Apache-2.0. Ver [LICENSE](LICENSE) y [NOTICE](NOTICE).

El texto de la ISO/IEC 42001:2023 **no se reproduce**: la norma es de pago. Los
catálogos listan identificadores, numeración y títulos, y añaden trabajo propio
—el nivel de comprobabilidad, el cruce entre marcos, las reglas y sus
remediaciones—. El Reglamento (UE) 2024/1689 es público y se cita por
referencia, nunca a granel.

Las reglas y las remediaciones las escribió una persona. Un modelo puede
proponer el borrador de una regla fuera de línea; nunca redacta reglas ni
remediaciones en ejecución.
