# El contrato entre el motor y la plataforma

El motor es Python y la plataforma es Go. La frontera entre los dos es **un
proceso y un JSON**, no una biblioteca compartida, y esa decisión está en
[`docs/ARQUITECTURA.md`](../docs/ARQUITECTURA.md) con sus dos alternativas
rechazadas.

Este documento es el contrato. Lo que no está aquí, la plataforma no puede
suponerlo.

## 1. La invocación

```
actaira <verbo> <ruta-de-trabajo> [opciones] --json
```

- La plataforma invoca el binario. **No importa el paquete de Python**: si lo
  importara, una excepción del motor tumbaría el servicio, y una dependencia
  del motor entraría en el espacio de direcciones de la plataforma.
- `--json` siempre. La salida de texto es para una persona en un terminal y
  puede cambiar sin avisar; el JSON no.
- La ruta de trabajo va **resuelta** y comprobada contra la raíz del cliente
  antes de invocar. Comparar cadenas sin resolver deja pasar un `../`.

## 2. Los códigos de salida, y el que importa

| código | significa | qué hace la plataforma |
|---|---|---|
| `0` | lo que se pidió está completo | guardar y mostrar |
| `1` | hay hallazgos, o una respuesta no admite | guardar y mostrar; **no es un fallo del motor** |
| `3` | está incompleto o hay trabajo que hacer | guardar y mostrar; **no es un fallo del motor** |
| otro | el motor reventó de verdad | registrar, avisar, no guardar |

**El 3 es el que se equivoca todo el mundo.** Significa «falta contestar, falta
firmar, o hay algo que volver a observar», que es el estado normal de un cliente
que empieza. Una plataforma que lo pinte en rojo enseña a sus usuarios a ignorar
el rojo, y entonces el rojo de verdad tampoco se ve.

## 3. El documento

Todo documento trae un campo `esquema` con la forma `actaira/<nombre>/v1`. La
plataforma **comprueba ese campo antes de leer nada más**: sin él no puede saber
si entiende lo que acaba de recibir.

Los esquemas viven en [`contrato/`](../contrato/) y hay una puerta que valida
contra ellos cada documento que el motor emite en sus pruebas.

| verbo | esquema | qué contiene |
|---|---|---|
| `plan` | `actaira/plan/v1` | qué ata, qué se comprobó, qué hay que preguntar |
| `preguntar` | `actaira/cuestionario/v1` | las preguntas y la resta que hace el código |
| `soa` | `actaira/soa/v1` | la declaración de aplicabilidad |
| `vigilar` | `actaira/vigilancia/v1` | qué caducó, qué cambió, qué reobservar |
| `anexo` | `actaira/anexo-iv/v1` | la documentación técnica |
| `anexo --cual v` | `actaira/anexo-v/v1` | la declaración UE de conformidad |

## 4. Lo que la plataforma NO puede hacer con el documento

- **No lo transforma antes de guardarlo.** Lo que sale del motor es lo que se
  guarda y lo que se enseña. Una plataforma que reescribe el expediente deja de
  poder demostrar que el expediente es el que emitió el motor.
- **No añade un resumen numérico.** Si el motor no emite un porcentaje, la
  plataforma tampoco. La primera negativa no es del motor: es del producto.
- **No decide por el cliente.** `a_reobservar` dice qué mirar. Si eso bloquea un
  despliegue lo decide el fichero de CI del cliente.
- **No rellena un campo ausente.** Una sección `ausente` trae su
  `motivo_ausencia`; enseñarla vacía o esconderla la convierte en lo que el
  Anexo IV prohíbe.

## 5. El aislamiento

Una ruta de trabajo tiene que colgar de la raíz de clientes, comprobado con
rutas ya resueltas. Es la única barrera de este lado y por eso se prueba por los
dos extremos: que rechaza lo ajeno, y que **no rechaza lo propio** — una barrera
que lo rechaza todo pasa el primer test y no sirve para nada.

## 6. El plazo

Todo verbo corre con un plazo. Un barrido sobre un repositorio enorme se mata y
se informa; no se deja colgado ocupando un trabajador.

## 7. Lo que el esquema no puede decir

Un esquema JSON fija la forma, no la doctrina. Que no aparezca nunca un
porcentaje, que un `INDETERMINADO` traiga su motivo, o que la declaración de
aplicabilidad no excluya sola son invariantes que se sujetan con pruebas en
Python. **El contrato dice qué campos hay; las cuatro negativas dicen qué puede
haber dentro.**
