# Arquitectura de Actaira

Sistema de compliance as code del Reglamento (UE) 2024/1689 y de la norma
ISO/IEC 42001:2023.

Versión <!--cifra:version-->0.15.0<!--/cifra-->, 21 de septiembre de 2026.

Toda cifra de este documento sale del árbol y **ninguna está escrita a mano**.
Esa frase ya estaba aquí y era falsa: el documento decía <!--historica-->24<!--/historica--> obligaciones
con <!--cifra:obligaciones-->48<!--/cifra--> en el catálogo, <!--historica-->60<!--/historica--> pares del cruce con
<!--cifra:pares-->101<!--/cifra-->, y <!--historica-->205<!--/historica--> pruebas con <!--cifra:pruebas-->561<!--/cifra-->. Lo que hacía daño no era cada número, sino que la frase convertía
una lista de cifras viejas en una lista de cifras *avaladas*: quien lee deja de
comprobarlas porque el documento le ha dicho que ya están comprobadas.

Ahora cada cifra va entre marcadores `<!--cifra:...-->` que rellena
`herramientas/generar_docs.py`, y la puerta de aceptación corre ese generador
en modo comprobación. El documento ya no puede envejecer en silencio.

---

## 1. Qué es, y las cuatro cosas que no es

Actaira lee el código y la configuración de un sistema de IA, resuelve qué
obligaciones le atan por rol y por fecha, corre los controles que se pueden
decidir leyendo bytes, redacta los artefactos documentales que el Reglamento
pide, recoge en formulario lo que no tiene bytes que leer, y emite un
expediente firmado que un tercero verifica sin acceso al sistema.

No es un GRC. No hace matrices de riesgo, políticas, cuestionarios de
proveedores ni formación. Eso vive en el GRC del cliente y Actaira se conecta.

No declara conformidad. La conformidad la declara el proveedor o la certifica
un organismo notificado. Un expediente completo no es un aprobado, y cualquier
texto emitido que insinúe lo contrario es un defecto de producto.

No es una plataforma de observabilidad. No se queda con el tráfico del cliente
para revenderle paneles.

No es un EDR. No bloquea, no aplica cambios, no toca el árbol del usuario.

### Las cuatro negativas, que son invariantes y no aspiraciones

1. **Nunca un número.** Ni puntuación, ni nota, ni porcentaje de cumplimiento,
   ni nivel de confianza. Una severidad es una etiqueta que escribió el autor
   de una regla, viaja junto a su nombre, y no se suma con ninguna otra.
   Puerta: `motor/tests/test_sin_agregados.py`, que recorre la salida buscando
   flotantes y palabras de agregado, con su gemelo que exige el fallo.
2. **Nunca juzgar, solo citar.** Todo hallazgo publica el identificador de la
   regla, su versión, su paquete y su autor.
3. **Nunca inferir lo no observado.** Sin información suficiente,
   `INDETERMINADO`, y nunca plegado a `NO_CUMPLE`.
4. **Nunca actuar sobre lo observado.** Se sugiere la remediación que trae la
   regla, escrita por una persona. No se aplica.

---

## 2. Tres componentes, y la frontera entre ellos

```
  motor/        Python    lee, resuelve, decide, firma, exporta
  plataforma/   Go        entidades, repos, vigilancia, escalado, facturación
  consola/      web       la interfaz, bilingüe
```

**El motor no sabe que existe la plataforma.** No tiene concepto de inquilino,
de suscripción ni de usuario. Esa ignorancia es la propiedad que hay que
conservar: el día que el motor necesite saber qué es un inquilino, la frontera
se ha roto y ya no se puede ejecutar en la máquina del cliente sin cambiarlo.

El contrato entre los dos no hay que inventarlo, ya existe: **JSON canónico**
para la evidencia, **SARIF** para los hallazgos y **in-toto sobre DSSE** para
lo firmado. La plataforma invoca el motor en un contenedor y consume su salida.

### Decisión: dos lenguajes, y por qué no se unifica

Rechazado portar el motor a Go: el ecosistema de análisis estático, lectura de
formatos y evaluación está en Python, y portarlo son meses sin producto nuevo.

Rechazado portar la plataforma a Python: `plazum` ya tiene OIDC, SCIM, control
de acceso, escalado, calendario y pantallas construidos y con más tests que
código (75.187 líneas de producción, 106.553 de tests, medido con
`find . -name '*.go' | xargs wc -l` sobre el clon del 20-09-2026).

El coste aceptado: dos cadenas de construcción y dos conjuntos de dependencias.
Se compensa porque la frontera es un proceso y un JSON, no una biblioteca
compartida, así que ninguno de los dos puede romper al otro en tiempo de
compilación.

---

## 3. La escalera de comprobabilidad

Es la columna vertebral. Decide qué hace el sistema con cada obligación y, más
importante, qué se niega a hacer.

| Nivel | Qué es | Qué puede concluir |
|---|---|---|
| `maquina` | Un control determinista lee bytes y decide | CUMPLE, NO_CUMPLE, INDETERMINADO, NO_APLICA |
| `generable` | El sistema redacta el artefacto que la obligación pide | BORRADOR, INDETERMINADO, NO_APLICA |
| `juzgada` | Si un documento aportado responde es un juicio | INDICIO_A_FAVOR, INDICIO_EN_CONTRA, ABSTENCION |
| `organizativa` | No hay bytes que leer | APORTADO, PENDIENTE, NO_APLICA |

**`generable` nunca concluye CUMPLE.** Un borrador que nadie firmó no es
evidencia. Es la regla que separa esto de un generador de documentos.

Reparto medido hoy, con `python3 -c "..."` sobre `catalogo/`:

- Reglamento: <!--cifra:obligaciones-->48<!--/cifra--> obligaciones, de ellas
  **<!--cifra:obligaciones_maquina-->13<!--/cifra--> de nivel máquina**,
  <!--cifra:obligaciones_generable-->3<!--/cifra--> generables,
  <!--cifra:obligaciones_juzgada-->5<!--/cifra--> juzgadas,
  <!--cifra:obligaciones_organizativa-->27<!--/cifra--> organizativas. Partidas en
  <!--cifra:requisitos-->88<!--/cifra--> requisitos atómicos, de los que quedan
  <!--cifra:huecos-->0<!--/cifra--> sin control ni pregunta que los cubra.
- ISO 42001: <!--cifra:controles_iso-->38<!--/cifra--> controles del Anexo A, de ellos
  **<!--cifra:controles_iso_maquina-->12<!--/cifra--> de nivel máquina**, y
  <!--cifra:clausulas-->32<!--/cifra--> cláusulas de las secciones 4 a 10.
- Cruce entre los dos: **<!--cifra:pares-->101<!--/cifra--> pares**, <!--cifra:pares_rotos-->0<!--/cifra--> rotos.

Cada obligación que no es de nivel máquina **tiene que decir por qué no lo es**,
y hay una puerta que lo exige: `test_toda_obligacion_que_no_es_de_nivel_maquina_dice_por_que_no`.
En su primera ejecución encontró tres sin justificar, que era un fallo real.

---

## 4. El catálogo: contenido normativo como datos, no como código

`catalogo/` tiene tres ficheros y ninguno es Python:

```
catalogo/ai-act/obligaciones.json     <!--cifra:obligaciones-->48<!--/cifra--> obligaciones, ES y EN
catalogo/ai-act/requisitos.json       <!--cifra:requisitos-->88<!--/cifra--> requisitos atómicos
catalogo/iso42001/anexo-a.json        <!--cifra:controles_iso-->38<!--/cifra--> controles, ES y EN
catalogo/iso42001/clausulas.json      <!--cifra:clausulas-->32<!--/cifra--> cláusulas
catalogo/crosswalk.json               <!--cifra:pares-->101<!--/cifra--> pares, fuente única del cruce
catalogo/formularios/                 <!--cifra:preguntas-->90<!--/cifra--> preguntas
catalogo/reglas/                      <!--cifra:paquetes_de_reglas-->17<!--/cifra--> paquetes, <!--cifra:reglas-->68<!--/cifra--> reglas
```

### Decisión: datos y no clases

Rechazado escribir las obligaciones como `@dataclass`. Tres razones, en orden
de peso: quien revisa si el catálogo dice la verdad es un jurista y no un
desarrollador; un fichero de datos se valida contra un esquema en la puerta de
release y el código no; y el Derecho cambia a otro ritmo que el código, así que
mezclarlos obliga a publicar versión del motor para corregir una fecha.

Coste aceptado: el cargador valida a mano lo que un tipo daría gratis. Por eso
falla ruidosamente nombrando el campo y el identificador, nunca devolviendo
lista vacía. Regla 11.

### Decisión: el cruce vive en un solo fichero, y esto se aprendió rompiéndolo

La primera versión declaraba el cruce dos veces, cada catálogo apuntando al
otro. **La primera ejecución del cargador encontró 30 asimetrías.** Cada copia
era coherente consigo misma y el desacuerdo era invisible desde dentro de
cualquiera de las dos.

Rechazada la alternativa de dejar las dos copias y añadir una puerta de
simetría: una puerta que compara dos copias solo dice que difieren, no cuál
tiene razón, y obliga a editar dos ficheros por cada cambio normativo, que es
justo donde se cuela el error que la puerta luego encuentra.

La puerta que queda, `verificar_cruce()`, comprueba que cada par nombre
identificadores que existen en los dos lados. En su primera pasada encontró
cuatro pares huérfanos, y los cuatro eran artículos reales que faltaban.

### Nota de alcance del cruce

Un cruce dice que dos textos hablan de lo mismo, **no** que cumplir uno cumpla
el otro. La evidencia se reutiliza; la conclusión no se hereda. Un certificado
ISO 42001 no descarga el artículo 17 y el sistema no lo dirá nunca.

---

## 5. El ciclo completo, desde cero

Lo que ve una organización que empieza sin nada:

```
  1  PERFIL       responde quién es y qué hace           -> aplicabilidad
  2  DESCUBRE     conecta repos y nubes                  -> inventario de sistemas
  3  RESUELVE     qué le ata hoy, qué le atará y cuándo  -> plan con fechas
  4  COMPRUEBA    corre los controles de nivel máquina   -> veredictos con frontera
  5  REDACTA      genera Anexo IV, instrucciones, DoC    -> borradores con procedencia
  6  APORTA       formularios de lo organizativo          -> firmado por una persona
  7  SELLA        expediente firmado, verificable offline -> evidencia
  8  VIGILA       la evidencia caduca sola                -> avisos citados
```

El paso 1 es el que casi nadie hace bien. El motor, con un perfil vacío,
devuelve **<!--cifra:indeterminadas_perfil_vacio-->48<!--/cifra--> obligaciones indeterminadas de
<!--cifra:obligaciones-->48<!--/cifra-->** y nombra exactamente las preguntas que faltan. Ningún camino lleva de un perfil sin responder a un
resultado limpio: `test_un_perfil_vacio_es_indeterminado_y_nunca_limpio`.

Ejemplo medido, el caso español más común, una pyme que genera imágenes con IA
y no es de alto riesgo: **3 obligaciones la atan hoy**, artículos 4, 5 y 50.
Un proveedor de alto riesgo: 3 hoy, 17 futuras, y **20 el 2 de diciembre de
2027**, que es cuando el aplazamiento del omnibus vence.

### Decisión: el reloj es un argumento, nunca una llamada

`resolver()` recibe `cuando`. No lee `date.today()` por dentro. Un expediente
que no se puede recomputar mañana con el mismo resultado no es evidencia de
nada. Puerta: `test_la_misma_entrada_da_el_mismo_resultado`.

---

## 6. La vigilancia: evidencia que caduca, no sondeo

Vigilancia continua **no** es preguntar cada minuto. Preguntar cada minuto es
caro, ruidoso y no demuestra nada: entre dos sondeos el sistema pudo cambiar y
volver.

El modelo correcto son los cinco estados de la evidencia, portados de
`actaira v2.3.0 state/evidence.py`, nota D-223:

```
  VALID       sigue valiendo para exactamente el sujeto sobre el que se tomó
  STALE       más vieja que la frescura que la política exige, vuelve a observar
  SUPERSEDED  una observación posterior de lo mismo sobre el mismo sujeto
  REVOKED     la clave, la fuente o la atestación se retiraron
  UNTRUSTED   íntegra, y la política de confianza de aquí no la acepta
```

Solo `VALID` cuenta. Los otros cuatro no son grados de confianza, son cuatro
razones distintas por las que la evidencia dejó de responder a la pregunta.

La regla que lo hace útil: **la evidencia la supera el digest sobre el que se
tomó, nunca el nombre de su sujeto.** Un escaneo de un modelo que no cambió no
supera nada, y uno de un modelo que sí cambió supera solo la evidencia atada al
digest viejo. Eso es la diferencia entre una invalidación sobre la que se puede
actuar y un muro rojo.

Coste comparado, que es el argumento comercial además del técnico: sondear cada
minuto N repos son N×1.440 ejecuciones diarias. Reaccionar a un webhook de push
más un vencimiento programado son del orden de las veces que el cliente commitea
más una. Dos órdenes de magnitud menos de cómputo para una afirmación más
fuerte.

**Lo que se le vende al cliente no es "miramos tu repo cada minuto".** Es "tu
conformidad tiene fecha de caducidad y te avisamos el día que vence".

---

## 7. La IA: en los bordes, jamás en el camino de la decisión

Dónde sí:

- Redactar reglas candidatas que después revisa una persona.
- Proponer el mapeo de un requisito nuevo al catálogo, para que alguien lo apruebe.
- Responder preguntas sobre la evidencia ya recogida, citando el registro exacto.
- El nivel `juzgada`: si un documento aportado responde a una obligación. Un
  modelo emite el juicio, **un verificador comprueba cada cita**, y se abstiene
  cuando no puede. La abstención es un resultado legítimo y se cuenta aparte.

Dónde nunca:

- Decidir un control de nivel máquina.
- Escribir una remediación en ejecución. Es un campo de datos de la regla.
- Producir el veredicto de aplicabilidad.

### Decisión: el verificador de citas no es opcional

Rechazado emitir el juicio del modelo directamente. Un juicio sin verificación
de citas es indistinguible de una alucinación bien escrita, y en un expediente
que va a un auditor eso es el peor defecto posible. El coste es latencia y una
llamada más por juicio; se acepta porque la alternativa destruye el producto.

---

## 8. Multi tenant, datos del cliente y despliegue

**El autoalojado es el plan A para enterprise, no el plan B.** Un responsable de
cumplimiento que pregunte dónde se procesa su repositorio y oiga "en un servidor
nuestro" cierra la conversación. Que se instale en su casa no es una limitación,
es la respuesta que le deja tranquilo.

El SaaS es para pymes y desarrolladores sueltos, y convierte al operador en
encargado del tratamiento: contrato, política de retención, cifrado en reposo y
la pregunta del CISO. Por eso el motor **no guarda el código del cliente**: lee,
emite hallazgos con localización, y descarta. Lo que persiste es la evidencia,
que son digests y veredictos, no fuentes.

Tres modos de despliegue con el mismo motor:

| Modo | Quién lo corre | Qué sale de la máquina del cliente |
|---|---|---|
| CLI local | el desarrollador | nada |
| Acción de CI | el pipeline del cliente | el SARIF, a su propio GitHub |
| SaaS | la plataforma | hallazgos y digests, nunca fuentes |

---

## 9. Qué se reutiliza, medido

| Origen | Qué se trae | Estado |
|---|---|---|
| actaira v2.3.0 `state/` | los cinco estados de la evidencia | portado |
| actaira v2.3.0 `controls/model.py` | el contrato de control, D-40 y D-41 | portado |
| actaira v2.3.0 `connectors/` | 10 conectores de entrada | por portar |
| actaira v2.3.0 `controls/art50.py` | el control del artículo 50 | por portar |
| actaira v3.0.0 `attest/` | Merkle RFC 6962, Ed25519, DSSE, RFC 3161 | por portar |
| actaira v3.0.0 `surface/` | el vertical del artículo 14 | por portar |
| actaira v3.0.0 `trace/` | convenciones GenAI de OpenTelemetry | por portar |
| actaira v3.0.0 `report/sarif.py` y `html.py` | salida SARIF e informe | ya existía |
| plazum `nucleo/aplicabilidad` | el diseño, no el código | portado en concepto |
| plazum `adaptadores/oidc` y `scim` | identidad y aprovisionamiento | la plataforma |
| plazum `superficies/escalado` | los avisos | la plataforma |
| mcp-fanout `capture_addon` y `redact` | captura de egress y redacción | por portar |
| attestor `annexiv/` | generador del Anexo IV | por portar |
| aegis `evals/`, `guardrails/`, `redteam/` | el artículo 15 | por portar |

Medido el 20-09-2026: de `state/` y `connectors/` de la v2.3 importan **20 de
20 módulos** contra el núcleo de la v3 sin tocar el núcleo, y pasan **224 de sus
<!--historica-->259<!--/historica--> tests propios**. Los 35 fallos son todos externos a la capa.

Esas cifras son de la v2.3 y no de este árbol, así que no se regeneran: van
marcadas como históricas a propósito. Una cifra sobre software ajeno que un
generador «actualizara» dejaría de decir lo que midió quien la midió.

---

## 10. Los formularios: la única parte que pregunta, y pregunta lo que falta

Un sistema que sólo lee bytes se queda en la mitad del Reglamento y en mucho
menos de la norma. La otra mitad son cosas que no están en ningún repositorio:
quién aprueba, cada cuánto se revisa, qué se decidió y por qué. Eso hay que
preguntarlo, y ahí es donde casi todo el mercado abre con un cuestionario de
trescientas preguntas porque no ha mirado el código.

Aquí el cuestionario se construye **después** del barrido y **en contra** de
él. Cada pregunta puede declarar `salta_si_cubre`, y desaparece en cuanto un
control leyó los bytes que la contestan. Lo que queda es lo que ningún análisis
estático puede saber. La resta se publica en `ahorro` con los identificadores de
los controles que la produjeron, porque un número sin la lista detrás es
publicidad y con la lista es una afirmación comprobable.

### El cruce se cobra aquí, no en una columna

Una pregunta declara a qué sirve con identificadores de los tres catálogos a la
vez: obligaciones del Reglamento, cláusulas 4 a 10 de la norma y controles del
Anexo A. «¿Quién responde de que el sistema de gestión cumpla, y quién informa
de su desempeño a la dirección?» cierra el artículo 16, el 17, la cláusula 5.3 y
el control A.3.2 con una sola respuesta. El cliente contesta una vez.

Lo que **no** se reutiliza es la conclusión. Que una respuesta valga para los dos
marcos no significa que cerrar uno cierre el otro, y el plan lo dice en su
`nota_cruce` para que nadie venda una certificación con esto.

### Una respuesta es evidencia, con las mismas reglas que un barrido

No hay un segundo modelo de estados para las respuestas. Una respuesta se
guarda como un `Registro` del módulo de evidencia, y el mapeo es literal:

| campo del registro | qué guarda en una respuesta |
|---|---|
| `sujeto_digest` | la **huella de la pregunta**, no su identificador |
| `frescura_dias`  | la vigencia que el catálogo da a esa pregunta |
| `control_id`     | el identificador de la pregunta |
| `contenido`      | el valor, quién lo dijo, con qué cargo y su justificación |

De ahí salen gratis los cinco estados, y el que importa es SUPERADA. **Si mañana
se reformula una pregunta, su huella cambia y toda respuesta anterior pasa a
superada automáticamente, con el motivo escrito.** Ninguna herramienta del
mercado hace esto: todas tratan la respuesta como un dato y la pregunta como una
etiqueta, con lo que una reformulación deja en el expediente respuestas a una
pregunta que ya no existe, indistinguibles de las buenas.

La huella cubre el texto en los dos idiomas, el formato, las opciones y lo que
exige. **No** cubre la ayuda, y la decisión costó pensarla: si entrara, mejorar
una redacción de ayuda invalidaría de golpe las respuestas de todos los
clientes, y entonces nadie mejoraría nunca una redacción. Hay test gemelo para
las dos mitades.

### La admisibilidad se comprueba; la veracidad, jamás

Una respuesta de tres palabras a «describa su proceso de evaluación de riesgos»
se guarda con estado NO_FIABLE y con el motivo escrito, no se rechaza en
silencio ni se acepta. Lo que se comprueba es la forma: longitud mínima, número
de elementos, opción excluyente, justificación obligatoria, mención de un
intervalo. Que lo que dice sea verdad no lo decide un programa. Segunda
negativa, y se aplica igual a lo que escribe el cliente que a lo que hay en su
repositorio.

---

## 11. La vigilancia cableada, que es el producto de suscripción

Las fases 1 a 7 producen una foto. Ésta le pone fecha de caducidad y, sobre
todo, le enseña a saber **cuándo deja de describir lo que hay**.

### El almacén se añade, y el estado no se guarda

Un fichero de líneas JSON al que solo se agrega. Revocar una evidencia es
añadir una línea de revocación, no quitar la vieja: la pregunta de un auditor
no es «qué dice tu sistema hoy» sino «qué decía el 3 de abril y quién lo
cambió».

Y el estado —VÁLIDA, RANCIA, SUPERADA, REVOCADA, NO_FIABLE— **no se almacena**:
se calcula al leer, con el reloj que se pase como argumento. Guardarlo obligaría
a recorrer el almacén entero cada minuto y crearía una segunda fuente de verdad
sobre lo que ya dice la fecha.

### El sujeto de un control es lo que ese control mira

Aquí está el foso entero. A una evidencia la supera el **digest del sujeto**
sobre el que se tomó, y el sujeto de un paquete de reglas son exactamente los
ficheros que sus reglas leen: una regla de `llamada` mira el código Python
acotado por sus imports, una de `contenido` mira el texto acotado por `solo_en`,
una de `fichero` mira la lista de nombres.

Medido sobre el repositorio de ejemplo: **añadir una línea a `datos/README.md`
supera uno de los doce controles con evidencia y deja once intactos**. El
superado es el del artículo 10, que es el único que lee esa ficha; los otros
once no la leen.

La primera versión de esta medida decía cinco de ocho, y era peor por una razón
que conviene dejar escrita: el sujeto de una regla de `fichero` incluía
entonces la lista completa del repositorio, así que cuatro paquetes se
invalidaban por un fichero que en realidad no leen. Afinar el sujeto (D-14)
bajó el número y mejoró la afirmación. Las dos alternativas son peores y las dos son lo que hace el mercado:

| alternativa | qué pasa |
|---|---|
| digest del repositorio entero | muro rojo en cada errata; se aprende a ignorar en dos semanas |
| el nombre del control | nada se supera nunca; la caducidad es un temporizador |

### La revalidación, que es un hecho distinto de la observación

Volver a observar lo mismo —mismo control, mismo sujeto, mismo resultado— no
reescribe el registro: añade una línea de revalidación con su fecha, y esa fecha
mueve el reloj de la frescura. Sin esto, o el almacén guarda el registro entero
en cada pasada de CI (y su tamaño mide la frecuencia del cron en vez de la
actividad del cliente), o la evidencia caduca aunque alguien la esté mirando
todos los días.

### Y no decide

`actaira vigilar` sale con 3 cuando hay algo que volver a observar y con 0
cuando no. **Tres es «hay trabajo», no «esto ha reventado»**, y la diferencia
importa porque una puerta de integración continua trata los dos casos distinto.
Si eso bloquea un despliegue lo decide el cliente, en su propio fichero de CI,
donde la decisión se revisa. La plantilla de `integraciones/github/` ofrece esa
puerta **comentada**, y hay test que comprueba que sigue comentada.

---

## 12. El contrato, que es lo único que sujeta una frontera entre dos lenguajes

El motor es Python y la plataforma es Go. Sin un contrato escrito, esa frontera
se rompe **en silencio**: el motor renombra un campo, la plataforma lo lee como
vacío, y el cliente ve un expediente incompleto sin que falle nada en ninguno de
los dos lados. Es el peor modo de fallo de una arquitectura de dos procesos,
porque nadie tiene un error que mirar.

Seis esquemas JSON en `contrato/`, uno por documento, y una puerta que **genera
cada documento de verdad** —no un ejemplo guardado, que envejecería— y lo valida.
La primera ejecución de esa puerta encontró dos derivas que nadie había visto:

- el Anexo IV llamaba `generado_el` a lo que los otros cinco documentos llaman
  `fecha`, así que una plataforma que leyera los seis necesitaría seis nombres
  distintos para la misma cosa;
- su `referencia` era una cadena en castellano mientras la del Anexo V era
  bilingüe, así que la versión inglesa del documento traía una línea en español.

Ninguna de las dos rompía nada hoy. Las dos habrían roto algo el día que la
plataforma leyera el sexto documento.

### Y una tercera, que era de producto

Al poner los documentos delante, el Anexo IV decía «no se encontro ninguna
declaracion de dependencias». La puerta de ortografía de la fase 7 cubría el
catálogo, y ese texto no está en el catálogo: se escribe en Python, en los
motivos de ausencia y en las notas de las declaraciones.

`texto/codigo.py` lo corrige con una regla precisa —solo el valor `es` de un
diccionario que también tiene `en`, y solo la rama castellana de un
`... if idioma == "es" else ...`— porque un `.py` está lleno de cadenas que no
son para el cliente: identificadores, expresiones regulares, claves. Acentuarlas
rompería el programa, y de hecho lo rompió: la primera versión convirtió
`_CLAUSULA_FUENTE` en `_Cláusula_FUENTE` dentro de una f-string, porque
`tokenize` entrega la f-string entera como un solo token. Una herramienta que
arregla la ortografía y rompe el programa no la usa nadie dos veces.

### El lado Go no sabe qué es una obligación

`plataforma/motor` invoca un verbo, respeta un plazo, comprueba que la ruta de
trabajo cuelga de la raíz del cliente, y lee un documento que declara su
versión. No reimplementa ninguna regla y no conoce ningún artículo.

Lo que sí hace, y es la parte que se equivoca todo el mundo: **no interpreta el
código de salida 3 como un fallo**. Tres significa «falta contestar, falta
firmar, o hay algo que volver a observar», que es el estado normal de un cliente
que empieza. Una plataforma que lo pinte en rojo enseña a sus usuarios a ignorar
el rojo, y entonces el rojo de verdad tampoco se ve.

---

## 13. La plataforma: aislamiento, y el único trabajo que hace la suscripción

Dos paquetes en Go, los dos cortos a propósito. Todo lo que sabe de cumplimiento
vive en el motor.

### `cliente`: rechaza, no limpia

Un identificador de cliente se valida contra una expresión cerrada y se
**rechaza** si no encaja. No se sanea, no se recorta, no se normaliza. La razón
es que limpiar deja la puerta abierta al siguiente que olvide limpiar, y
rechazar no. `..`, una barra, un nombre vacío o mayúsculas no se corrigen: se
niegan.

La pertenencia de una ruta se comprueba con las rutas **ya resueltas**, y el
test la prueba por los dos extremos: que rechaza la carpeta ajena y que **no
rechaza la propia**. Una barrera que lo rechaza todo pasa el primer test y no
sirve para nada.

### `vencimientos`: darse cuenta sin que nadie empuje nada

Es el único trabajo que la suscripción hace de verdad. Y tiene dos decisiones
que lo definen:

**No barre el repositorio.** Para saber qué caducó hacen falta el almacén de
evidencia y un reloj, no el código del cliente. El motor tiene un modo para eso
—`vigilar --solo-almacen`— y este paquete lo usa. Pedirle el repositorio a quien
no ha empujado nada sería trabajo inútil y obligaría a tener una copia fresca de
su código permanentemente, que es justo lo que un cliente con secretos en el
repositorio no quiere.

**No calcula la caducidad.** Sería una tarde de trabajo y dos definiciones de la
misma propiedad. La frescura, la revalidación y los cinco estados viven en el
motor, con sus pruebas; aquí se lee la respuesta.

Y un detalle que parece menor y no lo es: **un aviso vacío no se envía**. Un
aviso que llega cuando no hay nada que hacer enseña a la gente a archivarlo sin
leerlo, y entonces el que importa tampoco se lee.

### El trampa del diccionario vacío

`esperados={}` y `esperados=None` no significan lo mismo, y confundirlos rompió
el modo nuevo en su primera ejecución. Vacío es «se miró y no se esperaba nada»,
y con esa lectura **toda** la evidencia del almacén salía `fuera_de_alcance`.
`None` es «en esta pasada no se ha mirado qué se espera», que es la verdad
cuando no hay repositorio. Tiene su test con ese nombre.

---

## 14. Las cinco capas del resultado, y por qué estaban fundidas

Hasta la fase 14 un control devolvía un enumerado de cinco valores:

    SIN_HALLAZGOS | CON_HALLAZGOS | INDETERMINADO | NO_APLICA | ERROR

Esos cinco valores **no son cinco grados de lo mismo**. Son cuatro afirmaciones
de naturaleza distinta metidas en un tipo:

| valor | qué es de verdad |
|---|---|
| `ERROR` | un hecho sobre la **ejecución**: el analizador se rompió |
| `NO_APLICA` | un hecho sobre la **aplicabilidad**: no le tocaba mirar |
| `CON_HALLAZGOS` | una **observación**: apareció lo que se buscaba |
| `SIN_HALLAZGOS` | una **observación**: se buscó y no apareció |
| `INDETERMINADO` | una **suficiencia**: lo observado no alcanza para decidir |

Mientras vivieran juntos, cualquier `if resultado is not CON_HALLAZGOS` trataba
un analizador roto igual que un repositorio limpio, y cualquier pantalla, agente
o conector nuevo podía volver a fundir «se ejecutó» con «es suficiente» sin que
nada fallara. Separarlo antes de construir la cobertura cuesta un día; hacerlo
después de construir los agentes, los conectores y el frontend obliga a
rehacerlos, que es exactamente por lo que va antes que ampliar el catálogo.

### Las cinco capas

    1. Ejecución    ¿corrió? ¿sobre qué? ¿con qué versión? qué leyó y qué no pudo
    2. Observación  qué se vio. Hechos. NINGÚN veredicto.
    3. Evidencia    esa observación, guardada, con su frescura y su estado
    4. Suficiencia  para ESTE requisito, ¿alcanza lo que hay? ¿qué falta?
    5. Decisión     la conclusión jurídica. Actaira la REGISTRA y no la emite.

La frontera entre la 2 y la 4 es la que sostiene la segunda negativa. Un control
puede decir «en estos tres ficheros no aparece ningún marcado». Solo una
política de suficiencia, **citada por su identificador y su versión**, puede
decir «para el artículo 50 eso no alcanza». Y ni una ni otra pueden decir «esta
empresa incumple»: eso lo firma una persona, en la capa 5, y aquí solo se guarda
quién lo firmó y **sobre qué estado del expediente**.

### Tres decisiones de diseño que no son obvias

**`suficiente` no es `cumple`.** Dice que la evidencia que el requisito pide
está, está fresca y es válida: una afirmación sobre el **expediente**. Cumplir es
una afirmación sobre la conducta de una organización frente a una norma, y no se
sigue de la primera: un expediente completo de una práctica mal hecha sigue
siendo un expediente completo. Por eso `EstadoSuficiencia.afirma_cumplimiento`
existe y devuelve `False` para los cuatro estados, igual que `Resultado`: si
algún día alguien quiere que devuelva `True`, tiene que cambiar dos líneas en
dos módulos y explicar las dos.

**La identidad de una observación es su contenido, no su ejecución.** Dos pasadas
que ven exactamente lo mismo sobre el mismo sujeto han visto *lo mismo*: son una
observación observada dos veces, no dos observaciones. Si la identidad arrastrara
el identificador de la ejecución —que lleva el reloj dentro— cada pasada del cron
escribiría un registro nuevo, el almacén mediría la frecuencia del cron en vez de
la actividad del cliente, y la reproducibilidad del motor no se podría comprobar.
La ejecución sigue viajando como **procedencia**. Procedencia e identidad son
cosas distintas y fundirlas cuesta exactamente eso.

**Una decisión se ata a un digest, no a una fecha.** `Decision.sobre` es el
digest del conjunto de suficiencias sobre el que se decidió. Si mañana cambia
una sola, el digest cambia y la decisión queda visiblemente atada a un estado que
ya no es el actual, sin que nadie tenga que acordarse. «Firmado el 3 de abril» no
dice sobre qué se firmó, y es la forma más común de que una aprobación sobreviva
a los hechos que la justificaban.

### La proyección, y por qué tiene una puerta

`Resultado` no desaparece: el SARIF, el expediente y la consola lo consumen. Pasa
a ser una **proyección** de las capas, en una dirección y una sola, con una única
definición en `proyectar()`. Y `ResultadoControl` comprueba en su constructor que
el valor que trae coincide con lo que las capas proyectan: una vista derivada que
puede discrepar de su fuente es peor que no tenerla.

Esa puerta encontró un defecto el día que se encendió. El artículo 50 calculaba
su resultado final mirando solo los artefactos sin marcar y se olvidaba de los
hallazgos de generación de texto que ya llevaba en la lista: **devolvía
`SIN_HALLAZGOS` con un hallazgo dentro**. Nada fallaba, el hallazgo viajaba en el
JSON, y el informe lo contaba en la columna de los limpios. No lo vio la
auditoría externa ni la revisión posterior; lo vio la proyección.

### Lo que cruza la frontera

El plan no lleva las capas enteras dentro —llevaría la lista de ficheros leídos
de cada control y dejaría de caber en una pantalla—: lleva `ejecucion_id`,
`observacion_id` y la suficiencia. Los documentos completos tienen su esquema en
`contrato/capas.json`, y allí están escritos los mismos invariantes que en
Python, porque al otro lado de la frontera no hay constructor, solo JSON: una
observación sin límites no la puede fabricar ni el motor ni la plataforma.

## 15. Estado real hoy, y lo que falta

Construido y verde en este árbol (`python herramientas/todo.py`:
**<!--cifra:pruebas-->561<!--/cifra--> pruebas de Python** y **<!--cifra:pruebas_go-->98<!--/cifra--> de Go**).

La puerta de aceptación ya no es el `Makefile`. Lo era, y la mayoría de sus
objetivos **no podían ponerse rojos**: terminaban en `; true`, `|| true` o
`| head`, que se come el código de salida. El propio `Makefile` documentaba ese
defecto sobre tres líneas de un objetivo y lo dejaba intacto en el resto. Ahora
vive en `herramientas/todo.py`, cada fase afirma algo concreto, y lo que no se
puede medir en la máquina se declara OMITIDO con su motivo en vez de contarse
como aprobado.

| fase | qué quedó construido | verbo |
|---|---|---|
| 1 | catálogo bilingüe de las dos normas con su cruce, cargador con puertas, motor de aplicabilidad con las cuatro situaciones | `aplicabilidad` |
| 2 | el artículo 50 con motor propio, marcado de artefactos, sello Merkle y firma Ed25519 verificable sin red | `comprobar`, `sellar`, `verificar` |
| 3 | el motor genérico de controles, nueve paquetes de reglas y el plan completo con sus siete estados | `plan` |
| 4 | el Anexo IV generado desde el repositorio, con procedencia por sección | `anexo` |
| 5 | las <!--cifra:clausulas-->32<!--/cifra--> cláusulas de la norma, el banco de <!--cifra:preguntas-->90<!--/cifra--> preguntas crossframework, el cuestionario que resta lo que el código contesta y la declaración firmada que caduca | `preguntar`, `contestar` |
| 6 | la declaración de aplicabilidad derivada del Reglamento y la declaración UE de conformidad del artículo 47 | `soa`, `anexo --cual v` |
| 7 | la consola en tres vistas, bilingüe y construida desde el motor; el castellano con sus tildes | `exportar`, `ortografia` |
| 8 | el almacén de evidencia que solo se añade, la invalidación selectiva por digest de sujeto, la revalidación, y SARIF para la pestaña Security | `vigilar`, `plan --sarif` |
| 9 | los artículos 11, 13, 19 y 47, y el sexto tipo de regla (`contenido_prohibido`) | `plan` |
| 10 | el paquete instalable con el catálogo dentro, la licencia y el README | `pip install git+https://github.com/marcosmatalab/actaira-sys` |
| 11 | los seis esquemas del contrato, la ortografía del castellano que vive en el código, y el lado Go de la frontera | `make contrato` |
| 12 | el aislamiento por cliente, el vencimiento que se da cuenta sin que nadie empuje, y los motivos bilingües | `vigilar --solo-almacen` |

No construido todavía: la identidad de la organización y el aprovisionamiento
(OIDC y SCIM, que en plazum ya existen y hay que cablear), la facturación, el
receptor HTTP de empujones, y los conectores de entrada hacia las suites de GRC
que ya usan los clientes grandes.

Cada fase cierra con su pasada adversarial antes de abrir la siguiente, regla 1
y regla 4. Este documento se actualiza al cerrar cada fase: si dice construido,
hay un comando.
