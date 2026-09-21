# Backlog

Una linea por hallazgo que la pasada adversarial dejo abierto a proposito.
Regla 2: una pasada por fase, y solo puede producir un arreglo o una linea aqui.

## Abierto

- **B-001. Ligar el artefacto aportado con el punto de generacion que lo produjo.**
  Hoy el control lee los bytes que le entregan y nada los ata al codigo: un
  fichero marcado traido de otro sitio sale CUMPLE. Se ha publicado como
  frontera en `no_cubre`, que es lo honesto, pero la solucion de verdad es
  procedencia en el momento de generar, y eso es una fase con su propia puerta,
  no un arreglo de esta.
- **B-002. La alcanzabilidad se calcula por imports de modulo, no por funciones
  alcanzadas.** Es mas laxo que la version de actaira: esta no detecta una mitad
  muerta dentro de un modulo vivo. Declarado en el docstring de la puerta.
- **B-003. `requiere_import` no ve un SDK envuelto en un modulo propio.** Un
  cliente que haga `from mi_infra.ia import cliente` sale sin detectar. Es el
  precio aceptado de matar los falsos positivos, y esta escrito en el paquete de
  reglas.

## Cerrado en la pasada adversarial de la fase 2

- **D-1. El casador por sufijo daba falsos positivos reales.**
  `correo.messages.create` casaba `messages.create`. Arreglado: cada regla
  declara que paquete tiene que importar el fichero.
- **D-2. El CUMPLE no publicaba que el artefacto no esta ligado al codigo.**
  Arreglado en `no_cubre`.
- **D-3. Un sello firmado con cualquier clave verificaba en silencio.**
  Arreglado: sin `clave_esperada`, `verificar()` devuelve False y dice que la
  firma prueba integridad y no identidad.

## Comprobado y sin defecto

- El arbol de Merkle y sus pruebas de inclusion, en las 136 combinaciones de
  tamano e indice de 1 a 16 hojas. Cero fallos.

## Pasada adversarial de la fase 3

Cuatro ataques, uno entro y fue el serio.

- **D-4. Un README que decia que NO existe satisfacia el control.** Un fichero
  con "NO hay forma de aprobar ni de anular ni kill_switch" satisfizo tres de
  las cinco reglas del artículo 14, y el comentario `# TODO: falta anular` era
  el mismo ataque desde dentro del código. **Arreglado en dos pasos, y el
  segundo es el interesante**: el primer arreglo quitó TODOS los literales de
  texto y se pasó, porque rompió `ACT-12-VERSION`, que busca `model_version`
  donde ese nombre es la clave de un diccionario. En Python una clave de
  diccionario es código, no prosa. La línea no es código contra texto, es
  CÓDIGO contra PROSA: fuera comentarios y docstrings, dentro el resto de
  literales. Una regla que de verdad quiera leer documentación lo declara con
  `ambito: "documentacion"`, y entonces su remediación dice que comprueba que
  algo esté ESCRITO, no que exista.
- **El estado `comprobada` no sobraba.** La pasada preguntó si era inalcanzable,
  porque siete de los ocho paquetes tienen al menos una pregunta al cliente. No
  lo es: el paquete del artículo 72 no tiene ninguna y puede cerrarse solo. Hay
  test que lo fija.
- **Los tres ataques que resistieron**: un patrón que no casa nada no se salta
  en silencio, `llamada_sin_pareja` no dispara si no hay disparo, y las reglas
  de tipo fichero no se enganan con rutas parecidas.

## Abierto, anadido en la fase 3

- **B-004. `llamada_sin_pareja` mira el fichero, no la funcion.** Si registras
  en otro modulo, sale hallazgo donde no lo hay. Se eligio a proposito frente al
  analisis de flujo intraprocedimental: a nivel de fichero el falso negativo es
  posible y el falso positivo casi no, y de los dos el que destruye la confianza
  es el segundo.
- **B-005. Dos defectos seguidos de comprobaciones que miran de lado.** El
  guardia de agregados acuso primero a la nota que prohibe los agregados, y
  despues a `grade` dentro de `degrada`. Los dos eran la regla 12 en directo. Se
  acoto a las lineas y a palabras completas, con su gemelo. Queda la pregunta de
  si hay mas guardias con la misma forma en el arbol, y esa revision es una fase.

## Contraste contra las fuentes (20 sep 2026)

El propietario aporto el Diario Oficial del Reglamento (UE) 2024/1689 en
espanol y la ISO/IEC 42001:2023. El catalogo se contrasto contra ellos.

**Regla de uso de las fuentes, y no es un tecnicismo.** El Reglamento es Derecho
publico de la Union y se cita con precision. La ISO/IEC 42001 es propiedad de
ISO y su texto NO se reproduce: de la norma se usan identificadores y titulos de
control, que son referencias factuales, y todo el analisis de comprobabilidad y
el cruce son trabajo propio. El fichero del catalogo lo declara en su cabecera.

### ISO/IEC 42001, verificada entera

Los 38 controles del Anexo A, sus identificadores y sus titulos coinciden uno a
uno con la Tabla A.1. Cero correcciones.

### Reglamento, tres correcciones reales

- ~~**El Reglamento tiene TRECE anexos, del I al XIII, no catorce.** El catalogo
  listaba un `ANX-XIV` de organismos notificados que no existe. Venia de una
  tabla de trabajo y sobrevivio hasta que se leyo la fuente. Borrado.~~

  **RETIRADA EL 21-09-2026: esta correccion era el error.** El `ANX-XIV` de
  organismos notificados SI existe. Lo inserta el Reglamento (UE) 2026/1744
  (CELEX 32026R1744), publicado el 24 de julio de 2026: la lista de codigos
  AIP, AIB y AIH que delimita el alcance de la designacion en el procedimiento
  de notificacion del articulo 30. Restaurado, con `concreta` vacio porque no
  ata a ningun operador de los que usa este producto.

  Lo que hay que aprender de aqui no es el anexo. La correccion decia haberse
  hecho «contrastada contra el Diario Oficial», y era verdad: contra el texto
  ORIGINAL de 2024, donde efectivamente hay trece anexos. La frase era cierta y
  la conclusion falsa, y nada en ella permitia notarlo, porque no decia contra
  que VERSION se habia contrastado. Una auditoria externa tardo una tarde en
  encontrarlo y esta casa habia tardado meses en no encontrarlo.

  De ahi salen tres cosas que ya estan en el arbol: el bloque `instrumento` del
  catalogo declara ahora `version_consolidada` y lista cada acto modificativo
  con su CELEX, su fecha y -- esto es lo que mas falta hacia -- lo que de ese
  acto NO se ha recogido todavia; `test_ninguna_cita_al_diario_oficial_se_queda_sin_decir_contra_que_version`
  impide volver a publicar una cita a la fuente oficial sin un CELEX o un enlace
  al lado; y `ANEXOS_EN_VIGOR` vive en la puerta y no solo en el catalogo, para
  que el catalogo tenga contra que compararse.
- **El Anexo III tiene ocho ambitos y ahora son un enumerado**, no una cadena
  libre: biometria, infraestructuras criticas, educacion, empleo, servicios
  esenciales, garantia del cumplimiento del Derecho, migracion y fronteras, y
  administracion de justicia y procesos democraticos.
- **Faltaban las exclusiones de ambito del articulo 2**, y la del apartado 12 es
  la que mas duele: un sistema divulgado con licencia libre y de codigo abierto
  queda FUERA del Reglamento salvo que sea de alto riesgo o entre en el articulo
  5 o en el 50. Un motor sin esa regla le dice a un proyecto de codigo abierto
  que le atan veinte obligaciones que no le atan. Cableadas las tres del
  articulo 2: apartados 3, 6 y 12.

## Abierto, anadido en el contraste

## B-006 cerrada

La consola se construye y no se edita. Cinco piezas con un dueno cada una:
`plantilla/pagina.html`, `plantilla/estilo.css`, `plantilla/logica.js`,
`textos.json` y `datos.json`, que sale del motor y nunca se escribe a mano.
`python3 consola/construir.py` las arma y `make consola` lo corre.

Rechazado un empaquetador con npm: anade una cadena de construccion entera y sus
dependencias para ensamblar cuatro ficheros. El coste es que no minifica; a
cambio no necesita nada instalado y produce el mismo byte en cualquier maquina,
y hay test que lo comprueba.

Y al cerrarla aparecio una fuga real que el parcheo a mano escondia:
`reglaDe()` llevaba SEIS frases en castellano incrustadas en la logica, que por
tanto no se traducian. Ahora son plantillas con marcador en `textos.json`, en
los dos idiomas, y hay puerta que impide que vuelva a pasar.

Tercera vez seguida que una comprobacion mira de lado: la primera version de esa
puerta buscaba subcadenas y acusaba a `DATOS.obligaciones`, que es un
identificador. Acotada a los literales. Debajo del falso positivo estaba el
defecto de verdad, que es el argumento para no relajar una puerta ruidosa sino
afinarla.

## Fase 4, la pasada adversarial

El generador del Anexo IV se ataco igual que las fases anteriores: escribiendo
las secciones que un auditor leeria primero y preguntando si lo que dicen es
verdad. Tres defectos, los tres de la misma familia, que es la familia peligrosa
de este repositorio: **una respuesta plausible y falsa vale menos que ninguna
respuesta**, porque una ausencia se ve y una plausibilidad no.

- **D-5. El punto 1.e contestaba con el corredor de la integracion continua.**
  La pregunta del Anexo IV es el hardware en el que se ejecuta EL SISTEMA, y la
  funcion sacaba `runs-on: ubuntu-latest` de `.github/workflows/ci.yml`, que es
  la maquina donde corren las pruebas. Se exige ahora manifiesto de despliegue
  (Dockerfile, compose, Terraform, Kubernetes) y las rutas de CI quedan
  excluidas por nombre; si solo casan ellas, la seccion sale AUSENTE con su
  motivo escrito.
- **D-6. El punto 2.h afirmaba "medidas de ciberseguridad adoptadas"** a partir
  de una expresion regular. Ver `verify_signature` en el codigo no es saber que
  hay una medida adoptada: es ver un patron. La seccion emite ahora una
  advertencia por delante que dice exactamente eso, la lista de patrones
  observados y su recuento, y deja la interpretacion a la persona que firma.
  Regla de la casa: **nunca juzgar, solo citar.**
- **D-7. `a_markdown` cortaba los bloques a 1200 caracteres en silencio.** Un
  expediente que se corta sin avisar es peor que uno incompleto, porque el que
  lo lee no sabe que le falta. Ahora el corte lleva aviso en los dos idiomas con
  el numero de caracteres que faltan y el identificador de la seccion donde
  esta el contenido entero.

Y un cuarto, que aparecio porque el gemelo del D-5 fallaba:

- **`Arbol.leer` no abria los ficheros sin extension.** Un `Dockerfile` no tiene
  sufijo, asi que nunca entraba en el arbol, asi que el arreglo del D-5 no podia
  derivar el punto 1.e de ningun sitio: habria dado AUSENTE siempre, que es
  precisamente el fallo que la regla 11 prohibe (caer al extremo seguro y
  callarse). Lista cerrada de manifiestos sin sufijo en `SIN_EXTENSION`.

  Entran en `texto` y NO en `codigo`, a proposito. `codigo` es lo que barren las
  reglas de control, y un `Dockerfile` lleva comentarios con `#` que ningun
  quitaprosa sabe quitar todavia: meterlo ahi seria reabrir el D-4 (una frase en
  un comentario satisfaciendo una regla) por la puerta de atras.

## B-007. Quitaprosa para los manifiestos

Abierta por el parrafo anterior. Si alguna regla de control necesita mirar
dentro de un `Dockerfile` o de un `.tf` -- y el articulo 15 acabara
necesitandolo -- antes hay que escribirle su quitaprosa de comentarios de
almohadilla, con su gemelo que exija el fallo. Hasta entonces esos ficheros solo
los leen los extractores del Anexo IV, que citan y no juzgan.

## Fase 5, la pasada adversarial

Tres defectos, y el primero es el que habria vendido una mentira.

- **D-8. La resta valia siempre cero.** El cuestionario leia el campo `cubre`
  del plan, que es PROSA para que la lea una persona
  (`"ACT-09-GATE: encontrado en .github/workflows/ci.yml"`), y comparaba la
  frase entera contra un identificador de control. No casaba nunca. El
  sintoma es el peor de todos los posibles aqui: el producto seguia
  funcionando, el cuestionario salia completo, y el unico numero que se
  publica como diferencia frente a un consultor -- cuantas preguntas te ahorra
  el codigo -- era cero siempre, sin avisar.

  El arreglo NO fue parsear el prefijo antes de los dos puntos. Eso habria
  sido inventar en el consumidor un segundo formato de la misma verdad, que es
  la regla 12 en estado puro. `correr_paquete` publica ahora
  `controles_cubiertos` desde el mismo `r["id"]` y en el mismo instante en que
  escribe la prosa, y `ResultadoControl` lleva puerta que revienta si un
  identificador declarado no tiene linea de prosa que lo explique. Las dos
  vistas salen del mismo sitio o se anulan, regla 10.

  Los tests que lo tapaban construian el plan a mano con identificadores
  desnudos. Anadido un test de extremo a extremo contra el repositorio de
  ejemplo, que es donde se vio.

- **D-9. La referencia de cada pregunta era monolingue.** `_por_que` formateaba
  `f"articulo {o.articulo}"` en el motor, asi que `--idioma en` devolvia
  "for: articulo 16, clausula 4.1". Es la fuga exacta de `reglaDe()` en la
  fase 3, por tercera vez: una cadena de idioma formateada dentro del motor no
  se traduce nunca. Tres plantillas en `REFERENCIA`, test que recorre las 52
  preguntas y exige los dos idiomas en todas.

- **D-10. El verbo `contestar` fundia RANCIA con NO_FIABLE.** Imprimia
  "NO ADMITE" para cualquier estado distinto de VALIDA y mostraba `r.motivo`,
  que es None cuando la respuesta simplemente caduco: salia
  `NO ADMITE F-SIS-5: None`. Fundir esos dos estados es literalmente lo que el
  docstring del modulo de evidencia acusa de hacer a las demas herramientas, y
  lo hizo el CLI propio. Piden acciones distintas: una se vuelve a preguntar
  igual, la otra hay que contestarla mejor.

## B-008. El motor del articulo 50 no declara cobertura por regla

`art50.py` tiene motor propio y su `cubre` nunca lleva prefijo de
identificador, asi que `controles_cubiertos` sale vacio y ninguna pregunta con
`salta_si_cubre: ACT-50-*` llega a saltar. El efecto es preguntar de mas, que
es el lado seguro, pero es una asimetria con el motor generico. Cuando se
toque `art50.py`, que publique cobertura por regla como el otro.

## Fase 6, la pasada adversarial

- **D-11. La declaracion de aplicabilidad heredaba la conclusion, en su propia
  tabla.** La columna de estado decia "comprobada" y "contestada" por control
  del Anexo A. Leido en una declaracion de aplicabilidad eso significa
  implantado, y el generador no sabe eso: sabe que hay evidencia tecnica de una
  obligacion del Reglamento que el cruce ata a ese control, que es bastante
  menos. La `nota_cruce` del plan lleva desde la fase 1 diciendo que la
  conclusion NO se hereda, y el primer documento que se genero la infringio en
  la columna mas visible. Estados renombrados a lo que de verdad dicen
  (`con_evidencia_tecnica`, `con_respuesta_firmada`, `sin_evidencia_todavia`,
  `fuera_del_cruce`) y nota de no herencia impresa en el propio documento, en
  los dos idiomas.
- **D-12. Una barra vertical escrita por una persona partia la tabla.** Las
  justificaciones derivadas no llevan `|` nunca, asi que el defecto solo
  aparecia con una exclusion decidida por un cliente, que es exactamente el
  caso que importa. Celdas escapadas, y el gemelo cuenta las filas.
- **D-13. Una respuesta de lista salia como `['a', 'b']`** dentro de la
  declaracion UE de conformidad. Es cosmetico hasta que uno recuerda que ese
  documento se registra ante una autoridad.

Y una decision de diseno que merece quedar escrita, porque es la que define el
modulo: **la inclusion se deriva y la exclusion no se deriva jamas.** Incluir un
control de mas cuesta trabajo; excluirlo de menos cuesta la certificacion. Un
control que ninguna obligacion trae sale como `pendiente_de_justificar`, con el
hueco abierto. Y la declaracion UE de conformidad se emite con la palabra
BORRADOR en el encabezado mientras no exista la respuesta del punto 8 del Anexo
V, sin bandera ni parametro que la quite por otra via: los puntos 3 y 4 son
afirmaciones del proveedor bajo su exclusiva responsabilidad y ningun programa
puede hacerlas por el.

## Fase 8, la pasada adversarial

- **D-14. El sujeto de una regla de `fichero` era el repositorio entero.**
  `sujeto_de` usaba `arbol.todos`, asi que anadir un apunte, una imagen o un
  fichero de notas superaba la evidencia de que existe un directorio de
  evaluaciones. Es sobreinvalidar, y produce el mismo muro rojo que el digest
  del repositorio entero, solo que mas dificil de explicar: el cliente ve que
  «cambio algo» y no encuentra que. El sujeto correcto es el conjunto de
  nombres QUE CASAN los patrones de la regla, mas un marcador explicito cuando
  no casa ninguno, porque «no existe ninguno» es tambien una observacion y hay
  que poder distinguirla de «no se miro».
- **D-15. Las fechas se comparaban como cadenas.** `max(observado_en,
  revalidado_en)` sobre texto ISO da la respuesta contraria cuando los husos
  difieren: una revalidacion escrita `2027-12-02T08:00:00-02:00` ocurre a las
  10:00 UTC, despues de una observacion de las 09:00 UTC, y ordenada como texto
  parece anterior. Lo que escribe esta casa va normalizado a UTC, asi que el
  defecto solo aparece con un almacen que traiga lineas de otra herramienta, y
  el sintoma seria que la evidencia caduca antes de tiempo sin motivo visible.
  Arregladas las tres comparaciones: el estado, la ultima observacion por
  control y la ultima revalidacion.
- **D-16. Evidencia de algo que ya no ata contaba como valida.** Si el perfil
  cambia -- el sistema deja de ser de alto riesgo, cambia el alcance -- el
  almacen conserva observaciones de controles que ese perfil ya no espera, y
  salian VALIDA. Eso es sostener el expediente de hoy con una observacion sobre
  otra cosa. Estado nuevo `fuera_de_alcance`: se dice, y no cuenta.

Y una quinta reincidencia que ya no es noticia sino regla: la puerta que
comprueba que la vigilancia no emite veredictos se acusaba a si misma, porque
la nota que dice «NO decide si eso bloquea un despliegue» contiene la palabra
«bloquea». Es B-005 otra vez. La leccion ya no es afinar la puerta: es escribir
acotada desde el principio toda puerta que busque palabras.

## B-009. Los articulos 11, 13, 19 y 47 no tienen paquete

`actaira vigilar` los declara en voz alta como «sin paquete todavia» en vez de
callarse, que es lo correcto mientras no existan, pero existen cuatro
obligaciones de nivel comprobable sin una sola regla. Es el siguiente trabajo
de catalogo y no de motor.

## Fase 9: los cuatro articulos que faltaban, y B-009 cerrada

Los articulos 11, 13, 19 y 47 tenian nivel comprobable y ninguna regla. Ahora
tienen 17 reglas entre los cuatro, y `vigilar` ya no declara ninguna obligacion
comprobable sin paquete.

Son de una familia distinta a las ocho anteriores: **se comprueban sobre
documentos, no sobre codigo**, y esa diferencia trajo sus propios defectos.

- **D-17. Una regla que no dispara nunca y parece que funciona.**
  `ACT-47-SIGUE-EN-BORRADOR` se escribio con `contenido` y una expresion
  regular negativa, porque `contenido` solo sabe exigir PRESENCIA. El resultado
  era una regla que casaba casi cualquier linea de cualquier fichero y por
  tanto no acusaba nunca. Es el peor modo de fallo de este motor: la regla
  existe, se ve en el catalogo, corre en cada barrido y no comprueba nada.

  Arreglado con un sexto tipo, `contenido_prohibido`, que es el simetrico
  honesto: hallazgo cuando el patron APARECE. Hacia falta de todos modos para
  las reglas que vendran (indicios del articulo 5, secretos en el repositorio).

- **D-18. Un documento que falta producia tres hallazgos.** La ausencia de la
  declaracion de conformidad acusaba que no existe, que no dice que se expide
  bajo responsabilidad exclusiva, y que sigue en borrador: el mismo defecto
  contado tres veces. Un informe que multiplica un problema por sus
  consecuencias se lee una vez y se ignora a la siguiente, y asi es como se
  pierde una herramienta buena. Campo `solo_si_hay_fichero` en las reglas de
  contenido: la regla no aplica cuando no existe el fichero que mira, y lo dice
  en `no_cubre` en vez de callarse.

- **D-19. `\bretention\b` no casa `retention_days`.** Despues de la palabra
  viene un guion bajo, que es caracter de palabra, asi que la frontera falla.
  Habria dado un hallazgo falso de conservacion de registros a todo cliente que
  use esa clave, que son casi todos. El fallo de frontera de toda la vida, y el
  recordatorio de que una expresion regular sobre configuracion ajena se prueba
  contra la forma real que tiene esa configuracion, no contra la que uno
  imagina.

Y dos preguntas del formulario recuperan su `salta_si_cubre`, que se habia
quitado en la fase 5 porque apuntaba a controles que entonces no existian:
F-PRV-6 (instrucciones de uso) y F-SIS-4 (conservacion). El codigo contesta
ahora ocho preguntas en vez de seis.

## Fase 11: el contrato, y lo que encontró al ponerse delante

El motor es Python y la plataforma es Go. Sin un contrato escrito, esa frontera
se rompe **en silencio**, que es el peor modo de fallo de una arquitectura de
dos procesos: nadie tiene un error que mirar. Seis esquemas JSON y una puerta
que genera cada documento de verdad y lo valida.

La primera ejecución de esa puerta encontró tres cosas, y ninguna rompía nada
todavía.

- **D-20. Seis documentos y dos nombres para la fecha.** El Anexo IV llamaba
  `generado_el` a lo que los otros cinco llaman `fecha`. Una plataforma que
  leyera los seis necesitaría seis nombres para la misma cosa, y el sexto se
  escribiría mal.
- **D-21. `referencia` era una cadena en un documento y un par bilingüe en
  otro.** La versión inglesa del Anexo IV traía su primera línea en castellano.
- **D-22. El castellano que vive en el código no tenía puerta.** La de la fase 7
  cubre el catálogo, y los motivos de ausencia del Anexo IV, las notas de las
  declaraciones y los encabezados de los documentos se escriben en Python. El
  expediente decía «no se encontro ninguna declaracion de dependencias» delante
  de un auditor.

  `texto/codigo.py` lo corrige con una regla precisa: solo el valor `es` de un
  diccionario que también trae `en`, y solo la rama castellana de un
  `... if idioma == "es" else ...`. Un `.py` está lleno de cadenas que NO son
  para el cliente, y acentuarlas rompe el programa.

- **D-23, y esta la cometió el propio arreglo.** La primera versión del
  corrector de código convirtió `_CLAUSULA_FUENTE` en `_Cláusula_FUENTE` dentro
  de una f-string, porque `tokenize` entrega la f-string entera como un solo
  token y el corrector entró en las llaves. El módulo dejó de importar. Una
  herramienta que arregla la ortografía y rompe el programa no la usa nadie dos
  veces: ahora las llaves se saltan y hay gemelo por los dos lados.

## B-010. El esquema fija la forma, no la doctrina

Un esquema JSON no puede decir «aquí no aparece nunca un porcentaje». Esos
invariantes siguen sujetos por pruebas en Python y está escrito en el índice del
contrato, pero conviene recordarlo cada vez que alguien proponga «validamos con
el esquema y ya está».

## Fase 12: la plataforma, y el diccionario vacío

- **D-24. `esperados={}` no es `esperados=None`.** El modo nuevo
  `vigilar --solo-almacen` pasaba un diccionario vacío, y la reconciliación lo
  leía como «se miró y no se esperaba nada»: **toda** la evidencia del almacén
  salía `fuera_de_alcance` y el vencimiento no avisaba nunca. `None` significa
  «en esta pasada no se ha mirado qué se espera», que es la verdad cuando no
  hay repositorio. Es la distinción que más veces se pierde en un tipo
  opcional, y aquí habría apagado el producto de suscripción entero sin que
  fallara nada.
- **D-25. Los motivos de la evidencia salían solo en castellano.** La puerta
  que recorre los documentos buscando prosa suelta lo encontró en dos sitios: el
  `detalle` de cada veredicto de vigilancia, y el `motivo_indeterminado` del
  artículo 50, que el plan copiaba **en las dos claves** de una pregunta. Un
  cliente que pedía el expediente en inglés recibía castellano dentro del campo
  `en`. Los dos son bilingües ahora, y `ResultadoControl` revienta si alguien
  vuelve a poner una cadena suelta.
- **D-26. La regla de los interrogativos acentuaba donde se subordina.**
  «¿qué evidencia tiene DE QUÉ LA tienen?» salió impresa en una pregunta del
  cuestionario. Detrás de una preposición, `que` deja de preguntar si lo que
  sigue es un clítico o un artículo; los demás interrogativos sí preguntan, y
  aplicarles la misma regla dejaba sin tilde «cada CUÁNTO se revisa».

  Lo peor de este defecto es que **la puerta no podía verlo**: `corregir` es
  idempotente, así que sobre un texto que ya lleva tilde no cambia nada y la
  puerta seguía diciendo que todo estaba bien. Hace falta una puerta distinta
  para las tildes de más, y ya existe.

## B-011. Queda castellano suelto en tres campos del plan

`cubre`, `no_cubre` y `regla_aplicabilidad` siguen saliendo solo en castellano.
Están en la lista de deuda de `test_contrato.py` con su motivo escrito, para que
la deuda sea visible y no pueda crecer en silencio: añadir un campo ahí obliga a
explicar por qué.

## Fase 13: la pasada del auditor externo

Una auditoría CISO ajena corrió el árbol de la fase 12 y reprodujo nueve
bloqueos críticos con evidencia ejecutable. Ocho eran reales y los ocho están
arreglados con su pareja en `motor/tests/test_bloqueos_auditoria.py`. El noveno
—que `verificar` saliera con 1— no era un defecto: el mensaje era correcto por
diseño. El defecto real, debajo, era que no había manera de resolverlo, y ese sí
lo era.

Lo que sigue no es la lista de lo que dijo el auditor. Es la lista de lo que la
casa aprendió al reproducirlo, que en cuatro casos fue más grande que el hallazgo.

- **D-27. Un trozo de basura llamado `caBX` valía por un marcado.** La condición
  era «no hay XMP **y además** C2PA está ausente», así que un PNG con cuatro
  letras pegadas al final terminaba el control en el estado que entonces se
  llamaba `cumple`. El error de fondo era tratar `present_unverified` como una
  observación a favor: este arnés **no valida** manifiestos —lo dice su propio
  módulo— y «hay algo que dice llamarse C2PA» es exactamente el patrón que la
  segunda negativa prohíbe convertir en veredicto. Ahora son tres ramas y
  ninguna se funde con otra.
- **D-28. Un estado que se llamaba `cumple`.** Mientras exista un valor que se
  lea como «cumple», alguien lo pondrá en un informe delante de un auditor. Los
  cinco estados dicen ahora lo que se observó —`sin_hallazgos`, `con_hallazgos`,
  `indeterminado`, `no_aplica`, `error`— y ninguno dice lo que eso significa en
  derecho. La propiedad `afirma_cumplimiento` existe, devuelve siempre `False`, y
  existe precisamente para que eso se vea escrito en el código.
- **D-29. El `pipeline` era un parámetro decorativo.** Se aceptaba y no se
  aplicaba: `correr(...)` con cadena y sin cadena devolvían **el mismo JSON**. La
  tercera pregunta del control —¿sobrevive el marcado a la publicación?— no se
  estaba respondiendo, se estaba prometiendo. `tuberia.py` aplica ocho
  transformaciones de verdad, y un paso que no conoce **no se salta en
  silencio**: da `indeterminado` y lo nombra.
- **D-30. Un enlace simbólico leía fuera del repositorio.** `Path.resolve()` se
  llamaba sobre la raíz y no sobre el candidato. Un repositorio hostil —o un
  monorepo mal enlazado— metía en el expediente ficheros que nadie autorizó a
  leer. Ahora se resuelve el candidato, se compara contra la raíz real, y el
  enlace rechazado **aparece en `ilegibles` con su motivo**: no se lee, pero
  tampoco se calla.
- **D-31. «Solo se añade» era una promesa, no un hecho.** El auditor abrió el
  `.jsonl`, cambió un veredicto y una frescura a mano, y el motor los leyó como
  si nada. Un fichero de texto en el disco del cliente no tiene ninguna
  propiedad que el código no le dé. Ahora cada línea lleva `n`, `previo` y
  `sello`, y el sello cubre la línea entera junto con el de la anterior.

  Dos cosas que se aprendieron reproduciéndolo y que el informe no decía:

  1. **El identificador no bastaba.** `frescura_dias` no entra en el resumen del
     registro —es política, no observación— así que cambiarlo de 30 a 3000
     dejaba el identificador cuadrando perfectamente mientras la evidencia
     pasaba a no caducar nunca. Eso solo lo caza un sello sobre la línea entera.
  2. **La cadena no demuestra inmutabilidad y aquí se dice.** Quien tenga el
     fichero puede reescribirlo entero y recalcular la cadena. Lo que convierte
     esto en una afirmación frente a un tercero es sellar `cabeza()` dentro del
     sello firmado y publicarla. Venderlo como inmutabilidad sería la segunda
     negativa otra vez.
- **D-32. El almacén borraba el juicio del propio motor.** Esto **no** lo
  encontró el auditor; salió al escribir la pareja de D-31. `Registro.a_json()`
  no escribía `estado_declarado`, así que una respuesta que el motor había
  juzgado **no admisible** se guardaba y volvía a leerse como evidencia válida.
  Tampoco escribía `esquema`, con lo que una respuesta de formulario volvía
  diciendo ser una observación de código y su identificador dejaba de cuadrar.
  El motor decidía bien y su propio almacén deshacía la decisión.
- **D-33. `--rol` ampliaba el defecto en vez de sustituirlo.**
  `action="append"` con `default=["proveedor"]` hacía que
  `--rol responsable_despliegue` diera `{proveedor, responsable_despliegue}`. En
  este producto eso no es un parámetro mal leído: es atribuirle a una empresa un
  papel jurídico que no tiene, con las obligaciones que lo acompañan. El defecto
  se aplica ahora en `_roles()`, donde se ve, y no en seis declaraciones de
  argumento repartidas por el fichero.
- **D-34. El formato de salida cambiaba el veredicto.** `plan --json` devolvía 0
  con quince hallazgos delante, porque el `return 0` vivía **dentro** de la rama
  que imprime JSON. En el momento en que alguien encadena el plan con `jq`, eso
  convierte `--json` en una manera de saltarse la puerta sin querer. Los códigos
  de salida están ahora escritos una vez, son cinco, y se corresponden uno a uno
  con los estados del motor.
- **D-35. La separación integridad/identidad no tenía salida.** `verificar` ya
  distinguía las dos —una firma comprobada contra la clave que viaja dentro del
  sello prueba posesión, no identidad— pero el verbo no tenía por dónde pasar la
  clave que uno espera, así que **todo** sello firmado salía con el mismo aviso y
  el aviso dejaba de significar algo. Una separación correcta sin manera de
  resolverla es media separación. Ahora hay `--clave-esperada`.
- **D-36. El circuito no se cerraba.** `contestar` escribía
  `{"sello", "registros"}` y el lector de respuestas solo miraba `respuestas`:
  volver al cuestionario al mes siguiente con la declaración en la mano daba
  **cero** respuestas contestadas, en silencio. Al arreglarlo apareció el defecto
  de debajo, que era peor: los registros se escribían **dos veces** —dentro del
  sello y otra vez al lado— y la raíz Merkle solo cubría la de dentro, que no era
  la que leía la reimportación. Regla 10: dos representaciones de lo mismo con
  una sola comprobada se anulan. Ahora hay una, y es la sellada.
- **D-37. El flujo de integración continua pedía `contents: read` y hacía
  `git push`.** No fallaba en la revisión: fallaba el día que un cliente lo
  copiaba. Está partido en dos tareas —la que mira no puede empujar nada—, la
  versión que instala va clavada, la puerta se enciende con una variable del
  repositorio en vez de descomentando (así sobrevive a que la plantilla cambie),
  y las acciones **no vienen ancladas a digest**: se dice en voz alta y se
  incluye `anclar.sh`, porque publicar un digest inventado sería peor que no
  publicar ninguno.

  Y una consecuencia de D-31 que hubo que resolver ahí: el almacén encadena por
  número de orden, así que dos ejecuciones simultáneas lo romperían. No se
  arregla con `git pull --rebase` —rebasar intercala las líneas y deja dos con el
  mismo número—: si otra ejecución ganó, esta tira lo suyo y **vuelve a
  observar**. Observar otra vez es barato; un expediente roto no.
- **D-38. Una prueba saltada se contaba como una prueba verde.** El auditor contó
  193 pruebas y aquí salían 205: la diferencia entera era `jsonschema`, que él no
  tenía instalado, y con él se saltaban las doce del contrato entre los dos lados
  del producto. La batería decía «verde» y la única señal estaba en una línea de
  resumen que nadie lee. `test_entorno.py` falla ahora, nombra **qué deja de
  comprobarse** con cada ausencia, y se puede renunciar en voz alta con
  `ACTAIRA_SIN_VERIFICAR`, que es una decisión registrada en vez de un silencio.
- **D-39. El corrector de tildes escribía una falta distinta.** `valida` estaba
  en la tabla de siempre-lleva-tilde, y la tabla responde «¿lleva tilde esta
  palabra?» cuando la pregunta es si la lleva **esta aparición**: salió
  «este arnés NO válida manifiestos» dentro de un motivo que lee el cliente.
  Se probó una regla de contexto y acertaba un caso mientras fallaba los dos que
  de verdad salen. Las formas ambiguas ya no las toca la pasada mecánica: se
  escriben a mano, una por una, como las preguntas indirectas. Y una palabra
  entera en mayúsculas —`VALIDA`, `VERSION`— ya no se toca: era corromper un
  identificador mientras se arreglaba una tilde.

### Lo que el auditor dijo y esta casa no va a hacer

El informe propone un grafo de activos, un bus de eventos, un motor CAPA, doce
conectores GRC y un portal de auditor. Su propia conclusión dice que la posición
ganadora **no es otro GRC**, y esas cinco piezas son exactamente las de un GRC.
Se mantiene la malla de evidencia y garantía, y esas piezas entran solo donde
sirven a la evidencia: el grafo como sujetos con digest, los eventos como
empujones que invalidan, la remediación como cambio de código propuesto.

Y el orden no es negociable: **veracidad antes que alcance**. Ampliar el catálogo
a los 113 artículos sobre un motor que emitía falsos «cumple» habría multiplicado
los falsos «cumple» por 113.

## Fase 14: las cinco capas, y el quinto defecto

Una segunda revisión externa aceptó el orden (veracidad antes que cobertura) y
corrigió dos cosas. La primera era un error de planteamiento mío: había dicho
«malla de evidencia **o** GRC», y eso es una falsa elección. La malla necesita
versiones **mínimas** de grafo de activos, cola de eventos y CAPA; lo que no debe
construir es el system of record. La segunda fue de orden: el modelo de
resultados va **antes** que la cobertura, porque si el contrato cambia después
obliga a rehacer agentes, conectores y frontend.

- **D-40. Un enumerado con cuatro naturalezas dentro.** `ERROR` es un hecho de
  ejecución, `NO_APLICA` de aplicabilidad, `CON_HALLAZGOS` y `SIN_HALLAZGOS` son
  observaciones e `INDETERMINADO` es un juicio de suficiencia. Separado en cinco
  capas, con `Resultado` convertido en **proyección** de una sola dirección y una
  puerta en el constructor que impide que la vista derivada discrepe de su fuente.
- **D-41. Un `SIN_HALLAZGOS` con un hallazgo dentro.** Lo encontró la propia
  proyección el día que se encendió, y llevaba ahí desde la fase 2. El artículo
  50 calculaba su resultado final mirando solo los artefactos sin marcar y se
  olvidaba de los hallazgos de generación de texto que ya llevaba en la lista.
  Nada fallaba, el hallazgo viajaba en el JSON, y el informe lo contaba en la
  columna de los limpios. **No lo vio ninguna de las dos auditorías externas.**
- **D-42. Lo observado no se publicaba como dato.** `cubre` era una lista de
  frases en castellano: «3 artefactos leídos byte a byte: a.png, b.png». Sirve
  para el informe y para nada más —no se puede consultar, ni cruzar con un
  requisito, ni comprobar— y además un control que solo registra ausencias
  produce el mismo informe vacío para un repositorio impecable y para uno que no
  se miró. Ahora son `Senal`es con su regla, su versión y su sitio, y la prosa se
  **genera** desde ellas: una fuente, dos vistas.
- **D-43. `que_busca` era una cadena suelta en castellano.** Viaja a la señal y
  de ahí al expediente, así que un informe pedido en inglés traía castellano
  dentro. Las 49 reglas del catálogo son bilingües, y el cargador lo exige **al
  cargar** y no al imprimir: un paquete mal escrito tiene que reventar antes de
  correr, no a mitad del barrido.
- **D-44. Un límite sin motivo es una coletilla.** `no_cubre` era prosa suelta.
  Un `Limite` obliga a decir si no se miró porque la regla no lo alcanza, porque
  el fichero no se pudo leer, porque falta que el cliente aporte algo o porque lo
  cubre otro instrumento: son cuatro acciones distintas para quien lo lee.
- **D-45. Dos números de versión.** `pyproject.toml` decía 0.9.0 y el módulo
  0.1.0, y la plantilla de integración continua clavaba el del módulo: un cliente
  que la copiara habría instalado una versión que el empaquetado decía no ser la
  suya. La versión vive ahora en el paquete y `pyproject` la lee de ahí.
- **D-46. El sujeto del artículo 50 no incluía los artefactos.** Resumir solo el
  repositorio hacía que cambiar la salida no invalidara nada, que es justo el
  fallo que la invalidación por digest existe para evitar. El sujeto es ahora el
  repositorio **más** los artefactos aportados **más** la cadena declarada.

### Lo que esta separación deja preparado

El grafo de activos que pedía la revisión ya existe: es `Sujeto`, con su tipo y
su digest, y las relaciones son el siguiente paso, no una pieza nueva. La cola de
eventos es la invalidación por digest que ya hay. CAPA mínimo es `Falta`, que
obliga a decir **qué hacer** y **a quién le toca**, porque una falta sin acción es
una queja y una lista de quejas acaba en un cajón.

## Fase 15: el Reglamento entero, y lo que aparece al partirlo en deberes

- **D-47. El calendario era uno y son dos.** El Ómnibus digital aplazó las
  Secciones 1 a 3 del Capítulo III con **dos** fechas según por dónde el sistema
  llega a ser de alto riesgo: 2 de diciembre de 2027 por el Anexo III y 2 de
  agosto de 2028 por el Anexo I. Son ocho meses. Publicar una sola obliga a
  elegir, y las dos elecciones mienten a la mitad de los clientes. Ahora la
  fecha **no tiene respuesta** sin saber la vía, y el motor la pide en vez de
  inventarla. A quien dice que NO es de alto riesgo no se le pregunta -sería una
  pregunta sin respuesta- y se toma la temprana.
- **D-48. El aplazamiento no alcanza a lo que el Ómnibus no nombra.** Los
  artículos 43, 47, 49, 72 y 73 estaban puestos en la fecha del aplazamiento y
  no están en las secciones aplazadas. Vuelven al 2 de agosto de 2026, con la
  discrepancia entre fuentes escrita en el catálogo y la regla de decisión dicha
  en voz alta: **mientras no se pueda leer el texto consolidado, se toma la
  fecha temprana**, que es la única que no puede perjudicar al cliente.
- **D-49. El orden de los artículos era un `int()`.** Desde 2026 hay artículos
  «bis» -el 4 bis va entre el 4 y el 5-, y ordenar por entero revienta con el
  primero que aparece mientras ordenar por cadena pone el 10 antes del 2. Una
  definición, en el cargador.
- **D-50. Dos números de versión.** `pyproject.toml` decía 0.9.0 y el módulo
  0.1.0, y la plantilla de integración continua clavaba el del módulo: un cliente
  que la copiara habría instalado una versión que el empaquetado decía no ser la
  suya. La versión vive ahora en el paquete y `pyproject` la lee de ahí.
- **D-51. Las tres barras de la portada estaban escritas a mano.** Se habían
  quedado viejas dos veces: al arreglar la invalidación excesiva (D-14) y al
  añadir el paquete del artículo 5, que sumó un control al denominador sin que
  nadie tocara la página. Las escribe `make portada` desde la misma medición que
  las comprueba.

### Lo que apareció al partir los artículos en deberes

- **D-52. `ACT-50-GEN-TXT` era un falso positivo sistemático.** Emitía un
  hallazgo por **cada** llamada de generación de texto, y **su propia
  remediación explicaba** que el artículo 50(4) sólo obliga a divulgar cuando el
  texto se publica para informar al público sobre asuntos de interés público. O
  sea: el paquete sabía que su hallazgo era más ancho que la norma y lo emitía
  igual. Un producto que marca en rojo a todo el que llama a una API de texto se
  desactiva en una semana, y con él se desactivan los hallazgos de verdad. Ahora
  es una **señal** -un hecho, con su fichero y su línea- y lo que queda abierto
  se pregunta.
- **D-53. `ACT-50-BOT` deducía una ausencia que no se ve.** Marcaba como
  incumplidor a todo punto de entrada de asistente que compartiera fichero con
  una generación de texto. El aviso del artículo 50(1) es una frase en una
  pantalla, no una llamada: deducir que no existe porque no aparece en el árbol
  de sintaxis es inferir lo no observado.
- **D-54. Se pedía un PNG a quien sólo genera texto.** La rama de «no se aportó
  ningún artefacto de imagen legible» se disparaba también sin ningún punto de
  generación de imagen. Una herramienta que pide lo que no hace falta entrena a
  la gente a ignorar lo que pide.
- **D-55. El artículo 50 se daba por suficiente sin leer el texto.** El 50(2)
  alcanza al audio, la imagen, el vídeo **y el texto**, y este arnés sólo lee dos
  contenedores de imagen. Con las imágenes marcadas, la suficiencia salía
  `SUFICIENTE` y cerraba también el marcado del texto, que nadie había mirado.
- **D-56. Y el orden de las ramas se tragaba el caso concreto.** Al arreglar
  D-55, la rama nueva quedó **antes** que la del C2PA sin verificar, con lo que
  un artefacto con un trozo `caBX` recibía «no aportaste nada» en vez de «lo que
  aportaste no se puede validar». Lo concreto va antes que lo genérico.
- **D-57. `controles_cubiertos` se mantenía a mano junto a las señales.** Dos
  listas con lo mismo dentro, en el mismo bucle, y el artículo 50 no rellenaba la
  segunda: sus reglas limpias no aparecían como cubiertas y el plan contaba dos
  deberes del artículo 50 como «no evaluados» habiéndose evaluado. Ahora sale de
  las señales (regla 10).
- **D-58. Ocho citas del mapa de cobertura no hablaban de su artículo.** Un
  requisito del artículo 50 citando una pregunta sobre el origen de los datos del
  artículo 10 pasa las dos puertas anteriores -la referencia existe, el requisito
  tiene cobertura- y no cubre nada. Sólo se ve cruzando dos ficheros, así que hay
  una puerta que los cruza. Una cita a otro artículo no está prohibida -la
  reevaluación del 43(4) se dispara con la modificación sustancial, que es lo que
  define el 25- pero tiene que estar **dicha**.
- **D-59. `ACT-55-INCIDENTES` lo satisfacía un documento que se prometía a sí
  mismo.** Aceptaba cualquier markdown que mencionara «incidentes graves». Es el
  D-4 otra vez, y lo cazó la puerta que lo vigila el mismo día que se escribió la
  regla. Ahora mira **dentro** del fichero de seguridad.

## Fase 16: la ISO 42001 como sistema, no como lista

La auditoría lo dijo en una frase: «un AIMS no es una lista de comprobación».
Tenía razón, y lo que faltaba era concreto.

- **D-60. El ciclo no cerraba.** Las 32 cláusulas tenían `depende_de` —de quién
  vienen— y nada que dijera a quién van. Sin eso son 32 casillas marcables en
  cualquier orden: la 10.2 producía un registro de no conformidades que **nadie
  consumía**, y la revisión por la dirección producía un acta que no volvía a
  ningún sitio. Ahora cada cláusula declara `alimenta`, y hay una puerta que
  comprueba que el ciclo cierra de verdad: la 10.2 vuelve a la 6.1.2, la
  revisión vuelve a los objetivos, el seguimiento vuelve a la no conformidad.
- **D-61. Las dos direcciones podían discrepar.** `depende_de` y `alimenta` son
  la misma relación mirada desde los dos lados, y cada copia podía ser coherente
  consigo misma y estar en desacuerdo con la otra. Es exactamente cómo el cruce
  de catálogos acumuló 30 asimetrías en la fase 0, así que lleva su puerta desde
  el primer día (regla 10).
- **D-62. Once cláusulas exigían información documentada sin decir cuál.** El
  sistema pedía guardar registros y no decía de qué, con lo que «falta un
  registro» no se podía detectar. Las 23 que la exigen nombran ahora su salida.
- **D-63. Un sistema de gestión sin reloj.** Una auditoría interna de hace tres
  años no es una auditoría interna, y el catálogo no tenía dónde decirlo. Cada
  cláusula lleva su `periodicidad` —continua, anual o por cambio— y su vigencia,
  y la maquinaria de caducidad que ya existía para la evidencia técnica vale
  igual para los registros de gestión. Eso es lo que separa un sistema
  certificable de una carpeta con documentos correctos y viejos.

### La cláusula 10.2, sin el botón de cerrar

Todas las herramientas de GRC guardan la no conformidad como una fila con un
campo `estado` que alguien cambia. Eso pierde el historial y, peor, convierte
cerrar en **escribir una palabra**: un `estado = "cerrada"` no distingue entre
«comprobamos que la causa dejó de producir el efecto» y «pasó el tiempo y
alguien lo dio por bueno».

Aquí la no conformidad **no se guarda**: se guardan sus transiciones, en el
mismo almacén encadenado que la evidencia técnica, y el estado se calcula al
leer. Es la misma decisión que el módulo de evidencia toma desde la fase 8 y por
la misma razón. Y hay una regla que lo hace útil:

> `EJECUTADA` no es cerrada. Para llegar a `VERIFICADA` hace falta el
> identificador de una evidencia tomada **después** de ejecutar, y el
> constructor lo exige. Sin esa regla, el ciclo de mejora de la 10.2 es un
> formulario.

No hay un segundo mecanismo de almacenamiento para la gestión: la cadena de
sellos, la frescura y la invalidación por digest valen igual para un cambio de
estado que para una lectura de bytes. Dos almacenes habrían sido dos maneras de
perder lo mismo. Y editar una transición a mano rompe la cadena, así que cerrar
una no conformidad tocando el fichero se ve.

### La revisión por la dirección: la carpeta, no el acta

Casi ninguna organización falla la 9.3 por no hacer la revisión: la hace, y el
acta existe. Falla porque el acta **no cubre las entradas que la norma enumera**,
y eso sólo se ve comparando el acta con la lista, que es lo que hace un auditor y
lo que no hace nadie antes. `actaira revision` monta la carpeta de entrada: cada
una de las diez entradas de la 9.3.2, con la evidencia que la sostiene y su
estado. Y distingue **caducada** de **ausente**, porque «nadie ha mirado
últimamente» y «nunca se miró» no se arreglan igual.

No redacta el acta ni concluye nada: las decisiones de la 9.3.3 las firma la
dirección, y se registran en la capa 5 atadas a un digest y no a una fecha.

## Fase 17: los agentes, y lo que el silencio escondía

El Reglamento de 2024 no habla de agentes. Habla de sistemas de IA, y un agente
con herramientas es un sistema de IA: la diferencia no es jurídica, es que su
superficie de riesgo no está donde el catálogo la busca. Un clasificador
arriesga una predicción mala. Un agente con una herramienta que escribe arriesga
una predicción mala **que además actúa**, y eso mueve la mitad del artículo 14
de «que una persona pueda vigilar» a «que una persona pueda parar».

**La decisión que define el módulo es una negativa.** Lo fácil, y lo que hace
todo el mundo, es clasificar las herramientas por su nombre: `get_*` lee,
`delete_*` escribe. Con eso se pinta un panel de riesgo en una tarde y se
equivoca en cuanto alguien llama `obtener_factura` a algo que emite una factura.
Aquí el efecto sólo puede ser **declarado** o **sin declarar**, y el hallazgo no
es «esta herramienta es peligrosa» sino «de once herramientas no consta qué
hacen»: comprobable, accionable y verdad en casi todos los repositorios de
agentes que existen hoy.

- **D-64. Una obligación podía tener un solo analizador.** El artículo 14 se mira
  leyendo el árbol de ficheros —hay ruta de aprobación, hay parada— y leyendo la
  estructura de agentes —cuántas herramientas hay y si consta qué hacen—. Son dos
  sujetos, dos digests y dos invalidaciones: forzarlos al mismo paquete habría
  hecho que un cambio en el arsenal invalidara la evidencia sobre el código. Lo
  que **no** se admite es que dos paquetes definan la misma regla; ahí sí habría
  dos definiciones de lo mismo.
- **D-65. La misma herramienta se contaba dos veces.** Sale donde se define con
  `@tool` y donde se pasa en `tools=[...]`. La segunda es una **referencia**, no
  una declaración, y contarla aparte hacía que una herramienta perfectamente
  declarada apareciera también en la lista de las que no lo están.

### Lo que encontró la adversarial

- **D-66. «No encontré agentes» y «no hay agentes» salían iguales.** Un
  repositorio que declara `crewai` en sus dependencias y registra sus
  herramientas en un bucle no produce ninguna lectura, y salía `NO_APLICABLE`
  **igual que uno sin agentes**. Es el caso peligroso, no el inofensivo. Ahora se
  detectan los marcos declarados, y marco sin inventario legible da
  `INDETERMINADA` con lo que hay que hacer: si las herramientas se registran en
  un bucle, el inventario no existe hasta que alguien lo escriba.
- **D-67. Mover un fichero invalidaba el arsenal.** La localización entraba en el
  digest del sujeto, así que un refactor invalidaba toda la evidencia sobre las
  herramientas sin que las herramientas cambiaran. Lo que identifica a la
  estructura es **qué** puede hacer y si consta, no dónde está escrito; la
  localización sigue viajando como procedencia.
- **D-68. La regla de los interrogativos era demasiado ancha.** Quitó la tilde de
  dos preguntas legítimas seguidas —«¿a qué se comprometió?» y «¿de qué se
  aprueba y qué no?»— y las dos veces costó **reescribir la frase para esquivar
  al corrector**, que es exactamente al revés de para lo que está. Con un clítico
  de objeto y un verbo transitivo la oración subordina; con `se` la construcción
  es impersonal o refleja y lee como pregunta indirecta casi siempre.

### Lo que este control no puede ver, y lo publica

Si una herramienta hace lo que declara; si un límite declarado se respeta en
ejecución; qué pasa cuando el modelo encadena dos herramientas inofensivas para
conseguir una que no lo es; y si un agente hijo hereda los permisos del padre.
Los cuatro se preguntan, y ninguno se deduce.

## Fase 18 — Conectores de código en la nube

Un contrato de conector, dos conectores que lo cumplen —el local y el de git,
que es GitHub, GitLab, Bitbucket y Azure DevOps a la vez porque los cuatro
hablan el mismo protocolo para lo único que aquí hace falta— y el empujón como
disparador. El orden es el del revisor: **contrato estable primero**, conector
de referencia después. Un contrato sacado del primer conector real acaba
teniendo su forma (`owner/repo`, `installation_id`) y entonces el «adaptador
genérico» es un `if` dentro del de GitHub.

**La decisión que define el módulo es la referencia inmutable.** Una fuente que
dice «rama main» describe un sitio, no un contenido: mañana es otro contenido y
la observación de ayer ya no se puede comprobar. El conector local **no puede**
resolverla y lo declara —no inventa una fecha de modificación y la llama
referencia—, y el verbo se niega a observar sin ella salvo que alguien lo diga
en voz alta con `--acepto-que-no-se-puede-repetir`.

### Lo que encontró la adversarial

- **D-69. El filtro barato no existía, y una prueba en verde decía que sí.** El
  test se llamaba «un empujón que no cambia el sujeto no cuesta cómputo», ponía
  `LEEME.md` en la lista de ficheros y pasaba **el mismo digest por los dos
  lados**: salía `REVALIDAR` por la igualdad de digests, y el nombre del test
  atribuía ese verde a un filtro de ficheros que no estaba escrito. Es la regla
  12 en su forma más cara: una comprobación que mira de lado y cuyo verde
  certifica una función que no existe. Ahora el filtro existe, y la puerta a
  `IGNORAR` tiene seis condiciones porque equivocarse hacia `REOBSERVAR` cuesta
  un clon y equivocarse hacia `IGNORAR` **no se nota nunca**.
- **D-70. Dos definiciones de «qué ficheros abre el motor».** El filtro necesita
  contestar por NOMBRE y sin disco —el código no está, ése es el ahorro entero—
  y la lista de sufijos vivía suelta dentro de `Arbol.leer`. Copiarla habría
  sido regla 10 en la dirección peligrosa: el día que alguien añadiera `.tf` al
  motor y no a la copia, un cambio en un fichero de Terraform se ignoraría en
  silencio. Hay una sola definición, `lee_el_contenido_de`, y una prueba que la
  comprueba **contra el árbol de verdad** y no contra la lista.
- **D-71. Un `.png` nuevo se habría colado.** El digest del árbol resume también
  los NOMBRES de los ficheros que el motor no abre, así que añadir o borrar
  cualquier cosa cambia el sujeto aunque nadie la lea. El filtro sólo perdona
  **modificaciones** de ficheros ilegibles. Y hay un gemelo que comprueba esa
  propiedad del digest contra el motor, porque si algún día deja de ser cierta
  el filtro empieza a ignorar empujones que sí cambian el sujeto.
- **D-72. Las listas de ficheros vienen recortadas y ninguno de los cuatro avisa
  igual.** GitHub corta en 20 commits y no manda ningún aviso; GitLab manda
  `total_commits_count`; Bitbucket y Azure DevOps **no mandan los ficheros de
  cada commit**, así que con ellos el filtro no se puede aplicar y se publica en
  vez de fingir una lista vacía. Un empujón forzado se trata como recortado: los
  commits que trae son los nuevos, y lo que el forzado se llevó por delante no
  aparece en ninguna parte del cuerpo.
- **D-73. Se comparaba contra la rama equivocada.** El verbo se quedaba con el
  último registro de la **ubicación** e ignoraba la referencia: un empujón a
  `develop` se comparaba con el commit de `main`, siempre distinto y siempre
  `REOBSERVAR`. No mentía, pero convertía el filtro barato en un adorno, y lo
  hacía en silencio. Y una fuente registrada **sin** referencia inmutable
  contestaba «nunca se observó este sujeto», que era cómodo y era falso: se
  observó, de una manera que no se puede repetir.
- **D-74. Dos de los cuatro valores del enumerado no los devolvía nadie.**
  `IGNORAR` no existía y `NO_TRADUCIBLE` se quedaba en la excepción. Un cuerpo
  que no se entiende ahora sale con la **misma forma** que los demás, porque
  quien recibe webhooks quiere una respuesta y no dos.

### La cadena de inertes, y lo que descansa sobre quién

Sin ella el filtro barato serviría **una sola vez**: el segundo empujón sale del
primero, que ya no es lo último observado, y vuelve a costar un clon. Con ella,
`empujon --registrar` anota que un empujón se demostró inerte y el siguiente
puede salir de ahí. Tres cosas la hacen honesta:

1. **No es una observación, y el registro lo dice con esas palabras.** El árbol
   no se ha mirado. El digest del sujeto sobre el que afirma el expediente sigue
   siendo el de la última vez que se miró de verdad.
2. **Encadena por la cabeza y no por pertenencia.** Dos anotaciones que salen
   del mismo commit son una bifurcación, y el árbol de una rama no dice nada de
   la otra.
3. **Tiene tope.** Cada eslabón descansa en que el proveedor dijo la verdad
   sobre qué ficheros tocó cada commit —una apuesta pequeña y comprobable: se
   clonan los dos commits y se comparan—. Cien eslabones son una afirmación
   sobre un árbol que nadie ha visto desde hace cien empujones. Llegar al tope
   **cuesta** una observación que nadie pidió, y ése es el precio de acotar el
   error.

### Lo que este módulo no puede ver, y lo publica

Los submódulos, que no se clonan; lo que git no guarda; las ramas a las que la
credencial de esta máquina no llega; y el historial, porque se clona un solo
commit y cuándo se introdujo un cambio no es algo que esta observación pueda
decir. Los cuatro viajan **con la fuente**, dentro del plan, porque un límite
que no viaja con la observación deja al motor mirando un árbol incompleto
creyendo que está completo: no falla nada y el expediente sale limpio.

## Fase 19 — Remediación delegada

El hallazgo sale al sistema donde el cliente ya trabaja —Jira, Linear, las
incidencias de GitHub, o un fichero para quien no da acceso de escritura a
nadie— y vuelve **con techo**. Es el paso 6 del orden que pidió el revisor, y
es deliberadamente delgado: esto sincroniza controles, evidencias y hallazgos
con el sistema de tickets del cliente; no pretende ser su sistema de registro.

**La regla que define el módulo es una negativa: ningún estado de ningún
tablero cierra una no conformidad.** Da igual que la columna se llame «Done»,
«Closed» o «Verified by QA»: lo que dice es que alguien dio el trabajo por
hecho. `VERIFICADA` dice que se comprobó que la causa dejó de producir el
efecto, y eso exige el identificador de una evidencia tomada DESPUÉS de
ejecutar. La tentación es obvia, y es exactamente por lo que todos los
productos de cumplimiento la aceptan: si el ticket cerrado cerrara la no
conformidad, el panel se pondría verde solo y nadie tendría que volver a mirar.
Ése es el problema, no la solución.

El techo lo impone el **código** y no la tabla, y eso importa: una tabla es un
dato que alguien edita, así que si viviera sólo en sus valores bastaría con
escribir `verificada` en un fichero. La prueba gemela mete una tabla que miente
a propósito y comprueba que el código se niega igual.

### Un remediador y muchos sistemas, porque el que cambia es el perfil

El mismo argumento que el conector de git. Para lo único que aquí hace falta
—crear un elemento de trabajo y leer en qué columna está— Jira, Linear y GitHub
son una petición HTTP con un cuerpo JSON y una respuesta JSON. Que Linear hable
GraphQL no cambia nada: GraphQL es un POST con un cuerpo JSON. Lo que sí es
distinto son los nombres de los campos, y eso es un **dato**: un perfil con
plantillas y rutas. Añadir un sistema es un fichero y sus pruebas.

Las credenciales se leen del entorno con el nombre que el perfil diga y no se
guardan en ninguna parte ni salen en ningún mensaje de error. Un producto de
cumplimiento que se guarda los tokens de sus clientes se convierte en el
objetivo más valioso de su propia cadena de suministro.

### Lo que encontró la adversarial

- **D-75. Se consultaba un sistema al que nadie preguntó.** Con una delegación
  abierta en Jira y un `sincronizar --destino <carpeta>`, el remediador de
  fichero devolvía la delegación intacta —es lo que hace, un fichero no cambia
  solo— y su `estado_externo` se traducía **como si se hubiera preguntado a
  Jira**. El ciclo avanzaba con una respuesta que nadie dio. Ahora el sistema de
  la delegación tiene que casar con el del destino, y si no casa es ilegible y
  se dice.
- **D-76. Una integración rota parecía una pasada limpia.** Un estado que no se
  puede leer salía con el código de «hay hallazgos», que una puerta de
  integración continua trata como trabajo normal. Es «no se pudo decidir», que
  es un código distinto, porque fundirlos deja una integración rota pasando
  desapercibida durante meses.
- **D-77. El ticket fingía ser bilingüe.** El verbo montaba `{"es": x, "en": x}`
  con el mismo castellano en los dos lados: quien lo lee en inglés no sabe que
  está leyendo otro idioma, y eso es peor que no tenerlo. El texto del encargo
  **se busca, no se redacta**: sale del título y la remediación de la regla del
  catálogo, escritos por una persona y en los dos idiomas —segunda negativa de
  la casa, un modelo nunca redacta remediaciones en ejecución—. Cuando la no
  conformidad no viene de una regla, el texto del cliente va **tal cual**, en un
  campo que dice que es suyo, y la procedencia viaja con el encargo.
- **D-78. Una firma que una de sus implementaciones no podía cumplir.** El
  destino iba como argumento de `abrir`, y el remediador de fichero necesitaba
  uno que la firma no traía: su `abrir` reventaba a propósito. El destino es
  estado del remediador, no un argumento de la llamada.

### Las otras dos negativas de este módulo

**No se inventa el autor.** Si el sistema de tickets no dice quién movió el
ticket, aquí no se escribe «sistema»: una transición sin persona no se puede
auditar, y ése es todo el trabajo de la cláusula 10.2. «Quién» y «en calidad de
qué» son además dos preguntas distintas, y casi ningún sistema guarda la
segunda: se pasa con `--cargo` o no se mueve nada.

**Sólo hacia delante.** Un tablero es una herramienta de trabajo y las tarjetas
se arrastran. Si arrastrar una hacia atrás reabriera la no conformidad, el
ciclo de mejora dependería de cómo alguien organiza su semana. Es también lo
que hace idempotente la sincronización: leer el mismo ticket cada hora no llena
el almacén de transiciones idénticas.

### Y una columna que no está en la tabla no se ignora

Un equipo añade «En revisión de seguridad», los tickets se paran ahí y el ciclo
deja de moverse sin que nadie se entere. Es el mismo modo de fallo que un
proveedor de empujones que cambia su formato: el cliente sigue creyendo que
tiene vigilancia. Se dice, con las columnas que sí se conocen al lado.

## Fase 20 — La API y el panel conectado

Paso 7 del revisor. Dos piezas y **una misma negativa las dos veces**: la API
traduce transporte y nunca significado; el panel traduce presentación y nunca
significado. En cuanto cualquiera de las dos pueda producir una conclusión que
la línea de mandatos no produce, hay dos motores —el que se audita y el que
contesta al frontend—, y a partir de ahí un cliente que reproduce el análisis
en su máquina obtiene algo distinto de lo que ve en la pantalla. La única
propiedad que hace verificable a este producto se perdería en la capa más tonta
de todas.

La puerta que lo sujeta corre el mismo repositorio por HTTP y por la línea de
mandatos y compara los dos documentos campo a campo. En su primera pasada
encontró cuatro defectos que llevaban fases escondidos.

### Lo que encontró la puerta de los dos motores

- **D-79. El identificador de una ejecución cambiaba con el reloj.** `cuerpo()`
  dejaba fuera `termino` y su docstring prometía que el reloj no contaba, pero
  `empezo` seguía dentro: doce ejecuciones idénticas daban doce
  identificadores. La prueba que lo cubría variaba **sólo `termino`**, que ya
  estaba fuera, así que su verde no decía nada sobre lo que su nombre prometía
  —regla 12 otra vez—. Y peor: `reproducible_como` tenía su propia definición y
  **discrepaba** con los identificadores, diciendo que sí donde el digest decía
  que no. Regla 10 en su forma peor, que no es que una copia se quede sin
  actualizar, sino que las dos contesten cosas distintas a la misma pregunta.
- **D-80. `make todo` no podía ponerse rojo por el lado Go.** `go test ./... |
  tail -3` hace que make vea el código de salida de `tail`, que es siempre cero.
  Llevaba así desde la fase 7: un test de Go en rojo no rompía nada. Una puerta
  que no puede fallar no es una puerta, y ésta parecía una durante trece fases.
- **D-81. Tres verbos emitían JSON sin `esquema`.** Y `noconformidad listar`
  emitía **una lista suelta**, que no es un documento: no declara versión, no se
  puede extender sin romper a quien la lea por posición, y no tiene sitio donde
  decir que EJECUTADA no es cerrada. La frontera lo rechazaba, que era correcto,
  y nadie lo había notado porque el contrato **sólo se comprobaba sobre los
  documentos que ya tenían esquema**: una puerta que sólo mira donde ya se miró.
  Ahora hay tres esquemas más y una puerta que corre todos los verbos.
- **D-82. Los argumentos del perfil se ordenaban con `sort.Strings` sobre la
  lista plana**, que separa cada bandera de su valor. El orden se quería para
  que dos peticiones iguales dieran la misma ejecución reproducible, no para
  ordenar texto.

### Lo que se decide en la API

El **código de salida no es un estado HTTP**: tres significa «falta contestar o
hay algo que volver a mirar», que es el estado normal de un cliente que empieza.
Devolverlo como 4xx pintaría en rojo a todo el mundo el primer día y haría que
un reintentador repitiera un análisis que salió perfectamente.

**Sin credenciales no se arranca.** No hay modo abierto «para desarrollo»: un
servidor que ejecuta procesos y lee expedientes de varios clientes no puede
tener un estado por defecto permisivo, porque ese estado acaba en producción un
viernes. Un fichero de credenciales que pueda leer alguien más se rechaza al
arrancar, y un token de menos de 24 caracteres también.

**El mismo 401 para «token que no existe» y «token de otro cliente».** Dos
respuestas distintas son un oráculo: con ellas se enumera la lista de clientes
de la plataforma probando nombres, sin tener credencial de ninguno.

**El panel lo sirve el propio servidor.** Así la página y la API comparten
origen: no hace falta CORS, no hay una lista de orígenes que alguien acabará
poniendo en `*`, y no hay un segundo sitio donde desplegar una versión que se
queda vieja. El caso que evita no es teórico —un panel servido aparte más una
API que acepta cualquier origen es una página de otro leyendo el expediente de
un cliente con la credencial que el navegador manda sola—. Una prueba comprueba
que la página incrustada en el binario es la construida, porque si no, compila,
arranca y sirve una pantalla que ya no existe.

### Lo que se decide en el panel

**La credencial no se guarda.** Ni en `localStorage`, ni en `sessionStorage`, ni
en una cookie: vive en una variable y se pierde al recargar. Es incómodo a
propósito, y la página lo dice en la propia pantalla. Un guardia en la
construcción lo impide, y **no se dispara con los comentarios que explican la
prohibición**, que era el primer defecto de ese guardia: quien ve ese rojo quita
la palabra de la lista, y con ella la puerta entera.

**La página no divide.** Una división aquí es casi siempre una proporción
disfrazada. El guardia distingue una división de una expresión regular y de una
URL recorriendo el código carácter a carácter: analizarlo con expresiones
regulares «casi funcionaba», que es la clase de herramienta que se relaja hasta
que deja de mirar. La única aritmética de la página es una suma de recuentos,
escrita con nombre para que se vea.

- **D-83. La pantalla en inglés enseñaba los estados en castellano.**
  `con_hallazgos`, `solo_formulario`, `a_preguntar`: identificadores del motor
  pintados en crudo. Los estados **viajan sin traducir y eso es correcto** —
  traducirlos los inutilizaría para comparar dos documentos—, pero alguien tiene
  que decir cómo se leen, y ese alguien es el motor: si el vocabulario viviera
  en la pantalla, el día que el motor añada un estado un cliente inglés vería la
  clave y nadie se enteraría hasta que lo viera él. Ahora cada documento publica
  los nombres de **los estados que usa**, y hay una puerta que recorre todos los
  verbos y falla si alguno emite un estado sin nombre.
- **D-84. Un `import construir` cogía el módulo del otro.** La consola y el
  panel tienen cada uno su `construir.py`, y meter sus carpetas en `sys.path`
  hacía que el test de reproducibilidad de la consola comprobara el panel según
  el orden en que pytest recogiera los ficheros. Un test cuyo resultado depende
  del orden de recogida no mide lo que dice medir.
- **D-85. El `<pre>` del documento crudo ensanchaba la página entera.** Un
  elemento de rejilla tiene `min-width:auto`, así que la columna crecía más que
  la ventana y aparecía una barra horizontal en todo el panel.

### Las categorías de producto

Equipo técnico, pyme y empresa. Lo que una categoría cambia es **qué se le pide
al motor y qué se ve primero**, que es lo único que una categoría comercial
tiene derecho a cambiar. Ninguna cambia lo que el motor concluye, y una prueba
comprueba que las tres sólo declaran pasos y verbos.

### La pasada adversarial de la fase 20

Probar las rutas **una por una contra el motor instalado de verdad** —que es lo
único que lo habría encontrado, porque las pruebas de la capa HTTP corrían sin
binario— sacó cuatro defectos más.

- **D-86. `noconformidad listar` salía 502.** El primer positional de ese verbo
  es la **acción**, no una ruta, y la plataforma le pasaba el almacén como ruta
  de trabajo: la línea salía `noconformidad <ruta> listar` y el motor la
  rechazaba por argumento inválido. Esta capa lo traducía a «el motor no
  devolvió un documento que esta plataforma entienda», que es verdad y no dice
  nada. Hay ahora un `EjecutarSinRuta` que sigue exigiendo que el verbo corra
  **dentro del espacio del cliente** aunque no le pase ninguna ruta.
- **D-87. La barrera de aislamiento sólo miraba el primer positional.** Un
  `--almacen /etc/algo` habría pasado entero. Ninguna ruta lo hacía, pero una
  barrera que descansa en que quien llama se acuerde no es una barrera: el día
  que se olvide, no falla nada. Ahora se comprueba **toda** ruta absoluta que
  entre en los argumentos.
- **D-88. Nadie cubría las ENTRADAS de la frontera.** El contrato de documentos
  cubre lo que sale; lo que entra no lo cubría nadie, y tres rutas mandaban
  banderas que su verbo no acepta (`noconformidad --idioma`, `vigilar
  --fecha`). Dos se arreglaron dando la bandera al verbo —`aplicabilidad` y
  `noconformidad` imprimían prosa y no tenían `--idioma`, que es el defecto
  bilingüe otra vez— y la tercera traduciendo: `vigilar` mide contra un
  **reloj**, no contra una fecha de evaluación, y darle las dos banderas habría
  sido dos fuentes para lo mismo. La puerta nueva compara lo que la API manda
  con el `--help` de cada verbo.
- **D-89. Dos empujones a la vez se pisaban.** El cuerpo del evento se escribía
  en un fichero de nombre fijo dentro del espacio del cliente, así que dos
  webhooks simultáneos podían hacer que el motor decidiera sobre el cuerpo del
  **otro**. Decidir sobre un evento que no llegó es peor que fallar, porque el
  resultado es plausible y nadie lo mira. Un fichero por petición, y se borra
  al salir: es el cuerpo de un tercero y no tiene por qué quedarse.

## Pasada adversarial externa — la salida por una consola que no es UTF-8

La puerta entera salía verde: veinte fases, quinientas noventa y una pruebas de
Python y ciento trece de Go. Lo que encontró esta pasada no lo podía encontrar
la puerta, porque la puerta se corre a sí misma con el entorno ya arreglado.

- **D-90. Tres verbos reventaban en la consola por defecto de un Windows en
  castellano, y el traceback salía con el código de «hay hallazgos».** Python
  codifica `stdout` con la página de códigos de la consola. En un Windows en
  español esa página es cp850, y cp850 no tiene la raya «—», que está sesenta y
  tres veces en el catálogo y en los documentos que esta casa emite. `soa`,
  `anexo --cual v` y `preguntar --json` salían con un `UnicodeEncodeError` sin
  capturar, sin imprimir nada.

  Lo grave no es el fallo, es el número: un traceback de Python sale con **1**, y
  arriba está escrito que 1 es «apareció algo» y que romperse es 4. Una
  integración continua con `ACTAIRA_BLOQUEA=si` habría parado un despliegue
  citando hallazgos que no existen, y el paso «qué se decidió» habría impreso
  «hay hallazgos» con toda naturalidad. Es exactamente la categoría que este
  producto existe para no cometer: plausible y falso. `main()` ya capturaba
  `BrokenPipeError` con este mismo argumento —que un cliente no debe ver un
  traceback de un producto de cumplimiento— y la lección no se había
  generalizado.

  Arreglado reconfigurando `stdout` y `stderr` a UTF-8 al entrar en `main()`.
  Se descartó quitar la raya del catálogo: arregla los sesenta y tres casos de
  hoy y ninguno de mañana, porque el día que un jurista escriba «—» o «…» en una
  regla nueva el defecto vuelve y no hay puerta que lo detecte. El texto
  normativo se escribe como se escribe el castellano; quien se adapta es el
  canal. Y se descartó `errors="replace"`, que habría dejado un `?` **dentro** de
  un documento que va a un auditor.

  Alcance de lo que estuvo roto: la versión open source instalada con `pip` en
  cualquier Windows en español, y las rutas `/preguntar`, `/soa` y `/anexo` de la
  plataforma si se aloja en Windows, porque `exec.CommandContext` hereda el
  entorno y no fija ninguna codificación. La plantilla de integración continua
  no estuvo expuesta nunca: clava `runs-on: ubuntu-latest`. Por eso no se cazó.

- **D-91. El verde de la suite dependía de quién la lanzara.** `herramientas/
  todo.py` pone `PYTHONUTF8=1` en el entorno de sus subprocesos, y eso hace que
  `locale.getpreferredencoding()` devuelva utf-8 **en el proceso de pytest
  también**. Doce llamadas a `subprocess` de las pruebas pasaban `text=True` sin
  `encoding=`, así que descodificaban con la página de códigos heredada. Con
  `make todo` salían verdes las quinientas noventa y una; con `pytest` a secas
  —que es la vía que `pyproject.toml` declara como criterio de aceptación, «todas
  sus pruebas salgan verdes desde una instalación limpia»— salía una roja.

  Una sola afirmaba hoy sobre texto con tilde; las once restantes eran latentes,
  que es peor, porque el día que una empiece a afirmarlo el fallo aparecerá
  atribuido al cambio que lo destapó y no al que lo dejó ahí. Arreglado en las
  doce. Otras cuatro ya traían `encoding=` en la línea siguiente y no se
  tocaron. La lección es la misma que la de D-90 vista desde el otro lado: un
  criterio de aceptación que sólo se cumple por la vía cómoda no es un criterio.

- **D-92. Una «о» cirílica dentro del módulo que vigila la ortografía del
  castellano.** En un comentario de `texto/ortografia.py`, en la palabra
  «clitico». No cambiaba ningún comportamiento —era un comentario—, pero un
  homóglifo en el fichero que decide cómo se acentúa el castellano de este
  producto es el sitio menos afortunado donde podía estar. Corregido, y el árbol
  no tiene ya ningún carácter del bloque cirílico.

### Lo que esta pasada NO comprobó, dicho para que nadie lo suponga

- El OIDC contra un proveedor de identidad real, y que la suite se corra en
  Linux sola. Los dos se cerraron en la tercera pasada, más abajo.

## Segunda pasada, sobre Linux — lo que Windows no podía ver

Cerrado lo anterior, la misma pasada se repitió dentro de WSL2 con Go 1.26.7,
gcc 13.3 y el motor instalado desde el árbol con `pip`. Eso cerró los dos
huecos declarados arriba —el detector de carreras salió limpio y las dos
pruebas de permisos pasaron— y de paso destapó dos defectos que en Windows no
se podían ver, uno de ellos grave.

- **D-93. El extra `dev` no declaraba `pyyaml`, y la prueba que vigila las
  dependencias te mandaba instalar `dev` para conseguirlo.**
  `test_no_falta_ninguna_dependencia_de_desarrollo` exige `yaml` —lee la
  plantilla de integración continua como estructura y no como texto— y su
  propio mensaje de fallo dice «instálalo con `pip install -e '.[dev]'`». En el
  extra `dev` no estaba. En Windows salía verde porque el intérprete traía
  PyYAML por otra vía; en una instalación limpia, que es el criterio de
  aceptación que este producto se pone a sí mismo, salía roja.

  Es literalmente el defecto que el comentario del propio `pyproject.toml`
  documenta dos párrafos más arriba, sobre `pytest`, `jsonschema` y `pillow`.
  Se arregló para tres dependencias y no se comprobó que la lista estuviera
  completa. Añadido `pyyaml>=6`.

- **D-94. El conector de git quedaba roto en TODO sistema POSIX, y el que lo
  rompió fue el arreglo que lo compuso en Windows.** Antes de materializar el
  árbol, el conector borra el `.git` del clon, y si no puede lo dice y aborta:
  un directorio de trabajo que conserva el historial de un cliente es material
  de ese cliente sobreviviendo a la observación que lo trajo. Para que `rmtree`
  pudiera con los objetos que git deja en sólo lectura en Windows, se añadió un
  `os.chmod(..., S_IWRITE | S_IREAD)` sobre `dirs + ficheros`.

  `S_IWRITE | S_IREAD` es 0600. En Windows eso es inofensivo, porque allí
  `chmod` sólo toca el atributo de sólo lectura. En POSIX el bit de ejecución
  de un directorio **es** el permiso de entrar en él, así que aquello cerraba
  `.git/objects`: `os.walk` dejaba de poder descender, `rmtree` dejaba de poder
  borrar, el `.git` sobrevivía y el método lanzaba **siempre**. El verbo
  `conectar` —traer el código del cliente y observarlo sin dejar copia— no
  funcionaba en Linux ni en macOS, que es donde se aloja una plataforma.

  Lo que lo hace peor es lo que ya estaba escrito en el docstring de ese mismo
  método: «el conector cumplía su contrato en Linux y lo incumplía en silencio
  en Windows». Después del arreglo no lo cumplía en ninguno de los dos, y
  durante meses las cinco pruebas que lo cubren salieron verdes porque sólo se
  corrían en Windows. Un arreglo que no se vuelve a correr en el sistema que ya
  funcionaba no es un arreglo. Ahora los directorios llevan `S_IRWXU` y los
  ficheros 0600, que es la distinción que faltaba.

- **D-95. `quitar_metadatos` iba a reventar en octubre de 2027.**
  `Image.getdata()` está depreciado y desaparece en Pillow 14, y `pyproject`
  declara `pillow>=10` sin techo: el día que esa versión salga, el paso de la
  tubería del artículo 50 que simula la herramienta que borra los metadatos
  habría dejado de existir en cualquier instalación nueva, sin que nadie
  cambiara una línea. Sustituido por `frombytes`/`tobytes`, que es API estable
  y tampoco arrastra metadatos. La suite corre ahora con
  `-W error::DeprecationWarning` limpia.

## Tercera pasada — los dos huecos que parecían no depender de nosotros

Quedaban dos cosas sin comprobar, y las dos parecían necesitar algo de fuera:
credenciales de un proveedor de identidad, y una cuenta de integración continua.
Ninguna de las dos lo necesitaba.

### El proveedor de identidad: `identidad_real`

El hueco estaba mal planteado. No era «nos faltan credenciales de un Entra ID»:
era **«nuestro doble está de acuerdo con nuestro verificador por
construcción»**. Un doble emite exactamente lo que quien lo escribió creía que
emite un proveedor, así que no puede producir la única cosa que hace falta para
probar una integración: desacuerdo.

Keycloak es software libre y está certificado por la OpenID Foundation. Se
levanta uno en un contenedor —clavado por digest, no por etiqueta, por lo mismo
que la plantilla manda anclar las acciones—, se le configura un reino con dos
personas de dos clientes distintos, y se le habla. Las claves se leen de su
**JWKS publicado** y se convierten a PEM; ninguna se escribe a mano. Ocho casos
con testigos que esta casa no firmó.

**Tres diferencias que el doble no podía enseñar, y que el verificador ya
aguantaba:**

- `aud` no es una cadena, es una **lista**: `["actaira", "account"]`, porque
  Keycloak mete siempre su propio `account`. El verificador lee `aud` como
  crudo y comprueba inclusión, así que pasó. Si lo hubiera leído como `string`,
  habría rechazado a todos los usuarios de todos los Keycloak del mundo.
- `roles` no trae solo los nuestros: llegan `default-roles-<reino>`,
  `offline_access` y `uma_authorization` al lado de `lectura`. Un verificador
  que tratara un rol desconocido como error habría rechazado a todo el mundo.
  La fase **afirma que siguen llegando roles ajenos**: el día que dejen de
  llegar, esta prueba ya no comprobaría que se ignoran, y lo dice en vez de
  seguir verde por otro camino.
- `actaira_cliente` **no llegaba**. Keycloak 26 trae el perfil declarativo con
  `unmanagedAttributePolicy` desactivada y descarta en silencio, con un 201,
  cualquier atributo no declarado. El testigo salía perfectamente firmado y sin
  la reclamación que dice de quién es el expediente. No es un defecto del
  producto —el verificador lo rechaza, que es lo correcto— pero es el primer
  sitio donde se va a atascar quien despliegue esto, y ahora está escrito.

**Por qué este cero es un cero de verdad.** La pasada no encontró ningún
defecto del producto, y eso merece justificarse en vez de celebrarse. Tiene
teeth por tres razones comprobables: la puerta se vio **fallar** —con `Puede()`
cortocircuitado, salen en rojo «ana NO observa» y el caso de las cabeceras—; el
proveedor **sí rompió cosas** durante el montaje, tres veces, sólo que del lado
de la configuración; y las tres diferencias de arriba son sitios reales donde
un verificador razonable habría fallado y éste no, porque `aud` se lee como
crudo y los roles desconocidos se ignoran. No es que no se mirara: es que las
decisiones que evitaban esos fallos estaban tomadas de antes.

**Lo que sigue sin probarse, y por qué no se dice de otro modo:** Entra ID.
Emite `iss` con el identificador del inquilino y una versión en la ruta, usa
`oid` y no `sub` como identificador estable de la persona, y coloca los roles
en `roles` o en `wids` según la configuración. Nada de eso se toca aquí. Lo que
se prueba es que el verificador aguanta un testigo que no escribió esta casa.

### La matriz de dos sistemas: `matriz` y `.github/workflows/ci.yml`

B-004 no era un hueco de medida sino de proceso, y un fichero de flujo de
trabajo que nadie ha ejecutado es una promesa, no una comprobación. Así que hay
las dos cosas:

- **El flujo**, con matriz de dos sistemas por dos versiones de Python,
  `fail-fast: false` —si se cancelan, el primer rojo esconde si el otro sistema
  también estaba roto, que es el dato por el que existe la matriz—, la puerta
  con `--sin-omitir` en Linux, y las pruebas de la plataforma bajo `-race`
  fallando si se salta **una sola**.
- **La bandera `--sin-omitir`**, que convierte una omisión en fallo. En la
  máquina de quien desarrolla, omitir por falta de `docker` es razonable; en un
  agente donde todo está instalado a propósito, una omisión significa que algo
  dejó de estar disponible y nadie se enteró. Sin ella, la forma más fácil de
  que una fase deje de medir para siempre es que empiece a omitirse, porque el
  resumen sigue diciendo «0 en rojo».
- **La fase `matriz`**, que afirma sobre el propio flujo: si alguien le quita un
  sistema, afloja el `--sin-omitir` o deja de exigir cero saltadas, se pone
  roja. Y si desde la máquina se alcanza un segundo sistema —WSL— corre allí de
  verdad las tres baterías sensibles al sistema, las mismas que ya cazaron
  D-93 y D-94. Si no se alcanza, se omite con el motivo.

**La demostración que importa.** Deshecho el arreglo de D-94, la suite **en
Windows dice «45 passed»**: el defecto es completamente invisible. La fase
`matriz`, corrida desde esa misma máquina Windows, se pone **roja** y nombra las
tres pruebas que fallan en el otro sistema. Eso es exactamente lo que llevaba
meses sin pasar.

### Y una cifra vieja en el sitio más visible

- **D-96. El README afirmaba 180 pruebas y «Diecinueve» defectos.** Hay 562
  funciones de prueba de Python, 98 de Go y noventa y tantos defectos en este
  fichero. `herramientas/generar_docs.py` existe precisamente para que ninguna
  cifra de la documentación esté escrita a mano, y su propia cabecera cuenta el
  daño: una cifra vieja dentro de un documento que promete procedencia deja de
  ser un número flojo y pasa a ser un número **avalado**, porque quien lee deja
  de comprobarlo. El README era el documento que más gente lee y el único que no
  estaba bajo ese mecanismo. Ahora lo está. La insignia dejó de llevar el número
  —un comentario HTML dentro de una URL de Markdown la rompe, así que un número
  ahí no se puede mantener y por tanto no se pone—, y de paso la regla que
  cuenta los defectos admitía sólo punto detrás del número y se dejaba fuera la
  entrada que empieza «D-23, y esta la cometió el propio arreglo»: publicaba uno
  menos, en un módulo dedicado a que las cifras sean ciertas.

## Cuarta pasada — publicar el repositorio, y lo que eso destapó

El repositorio se subió a GitHub y la matriz de dos sistemas corrió por
primera vez de verdad. **Se pagó sola en su primera ejecución**: cuatro cosas
que no se podían ver desde aquí. Y exponer verbos nuevos a la plataforma
destapó dos defectos del núcleo, uno de ellos de la peor categoría que este
producto reconoce.

### Lo que encontró la matriz el primer día

- **D-97. Python 3.11 no puede con `ortografia --arreglar`.** Corregir la
  prosa que vive dentro de las llaves de una f-string exige que el tokenizador
  vea ahí dentro, y eso es PEP 701, que llegó en 3.12. En 3.11 la f-string
  entera es un único componente y el corrector pasa de largo **sin decir
  nada**: no falla, devuelve el texto sin corregir. `requires-python` decía
  `>=3.11`, es decir, prometía un verbo que allí no hace su trabajo. Subido a
  `>=3.12` con el motivo escrito. Callarlo habría sido peor que no tener el
  verbo.
- **D-98. `gofmt` en rojo sólo en el agente de Windows.** `core.autocrlf` es
  el valor por defecto de ese agente y convierte al **sacar** el árbol,
  después de que la prueba de finales de línea se escribiera. La prueba no
  podía verlo porque mira el árbol, no la copia que git entrega. Añadido
  `.gitattributes` con `eol=lf`.
- **D-99. `build` no estaba en el extra `dev`.** La fase `paquete` se omitía
  en cualquier máquina que no lo trajera puesto. Es la **tercera** vez que ese
  extra se queda corto: ver D-93 con `pyyaml`. La lección ya no es la
  dependencia concreta, es que una lista de dependencias que se amplía cuando
  algo falla siempre va un paso por detrás.
- **D-100. La fase `matriz` se ponía roja donde el producto está bien.** En un
  agente de integración continua no se alcanza un segundo sistema, y eso no es
  un fallo: allí el otro sistema lo corre la propia matriz. La fase levantaba
  `Omitida` y `--sin-omitir` lo convertía en rojo. Una puerta que se pone roja
  donde el producto está bien enseña a apagar la puerta. La fase mide dos
  cosas y ahora dice cuál de las dos no se pudo medir, en vez de tirar las
  dos.

### Los dos del núcleo

- **D-101. Un repositorio que NO EXISTE se leía como un repositorio VACÍO.**
  `rglob` sobre una ruta ausente no falla: devuelve cero entradas. De ahí
  salía el peor documento que este producto puede emitir:

  ```
  actaira comprobar /ruta/mal-escrita   ->   exit 0
  {"resultado": "no_aplica", "inspeccionado": [], "motivo_indeterminado": null}
  ```

  Una afirmación de que el artículo 50 **no te ata**, sin haber mirado nada,
  con el código de salida que significa «se miró y no apareció nada». Y
  `sellar` la convertía en evidencia con su raíz Merkle, lista para un
  auditor. Es la tercera negativa de la casa exactamente del revés, y es
  «tres estados, nunca dos» otra vez: «miré y no hay puntos de generación» y
  «no pude mirar» tienen que ser respuestas distintas.

  Lo llamativo es que el motor genérico **sí** sujetaba la invariante, desde
  el otro lado: `Ejecucion.__post_init__` revienta si una ejecución COMPLETADA
  no leyó ni un fichero. Eso dejaba a `plan` y a `vigilar` soltando un
  `ValueError` crudo con código 1, y al control del artículo 50 —que sale por
  NO_APLICABLE, no por COMPLETADA— sin sujetar en absoluto. Se sujeta ahora en
  `Arbol.leer`, que es donde se entra a mirar, y vale para todos los verbos.

- **D-102. `verificar`, `contestar` y `empujon` soltaban traza cruda con
  código 1.** Cuando el fichero que reciben no existe. Misma forma que D-90:
  una excepción sin capturar disfrazada de veredicto legítimo. Ahora salen 4
  con su motivo. El `except OSError` va **después** del de `BrokenPipeError`
  a propósito: es una subclase, y al revés la tubería cerrada de `| head`
  habría salido 4 en vez de 0.

### La web: seis idiomas, y lo que se quitó

La portada era la única superficie del producto que sólo existía en
castellano, mientras el panel y la consola llevaban dos idiomas desde su
primera versión. Un producto que promete «expediente listo para enseñar, en
español y en inglés» y cuya portada no está en inglés se contradice en la
primera pantalla.

Ahora se construye como las otras dos y salen **seis páginas de verdad** —es,
en, fr, pt, it, de—, cada una con su `lang`, su dirección y un conmutador de
seis enlaces. No es un conmutador de JavaScript a propósito: una página que se
reescribe en el navegador no se puede enviar por correo, se indexa en un solo
idioma, y un lector de pantalla la pronuncia mal hasta que alguien pulsa algo.
Las traducciones están escritas; `INDETERMINADO`, `NO_CUMPLE`, los
identificadores de regla y los nombres de los verbos **no se traducen**, por
lo mismo que decidió D-83.

- **D-103. La portada anunciaba facturación que no existe.** En la tabla de lo
  que está construido, que es justo la tabla que existe para no hacer eso. No
  hay una línea de cobro en la plataforma. Fuera. Y la fila de la Plataforma
  decía «en construcción» con OIDC, RBAC, aislamiento por cliente y topes ya
  construidos y probados contra un Keycloak real.
- **D-104. «Los diez verbos, enteros» cuando son dieciocho, y «Cuatro
  comandos» sobre un bloque que enseña cinco.** El número se quita en vez de
  corregirse: un número a mano envejece igual dentro de una frase que dentro
  de una insignia.
- **D-105. El README, la portada y la plantilla de CI mandaban a un paquete
  que no existe.** Las tres decían `pip install actaira-motor`, y eso no está
  publicado en PyPI: **la primera orden que lee quien llega al repositorio
  fallaba con un 404**. No es un defecto del producto —instala y corre
  perfectamente desde el repositorio— es un defecto de lo que el producto dice
  de sí mismo, en la primera línea, que es donde no hay segunda oportunidad.
  Hay ahora una sola declaración, `PUBLICADO_EN_PYPI`, y una fase que se pone
  roja **en los dos sentidos**: si se manda a PyPI sin estar publicado, y si
  se sigue mandando al repositorio cuando ya lo esté.
- **D-106. Ni la consola ni la portada declaraban `<!doctype html>` ni
  `lang`.** Sin doctype, el navegador renderiza en modo quirks y usa otro
  modelo de caja: la página se mide distinto de como se diseñó y casi cuadra,
  que es por lo que nadie lo nota. Sin `lang`, un lector de pantalla pronuncia
  el castellano con las reglas del inglés. La comprobación existía **dentro
  del constructor del panel**, así que sólo protegía al panel: una puerta que
  no se puede reutilizar acaba protegiendo lo que se acordó de protegerla.
  Ahora vive en `herramientas/paginas.py` y la usan las tres. De paso cazó un
  salto de h2 a h4 en la portada y cinco botones sin nombre accesible en la
  consola —las pestañas y los filtros—, que quien no ve la pantalla oía como
  «botón, botón, botón».
- **D-107. Dos definiciones del mismo número, y discrepaban.**
  `generar_docs.py` contaba las pruebas con `rglob` y `sitio/cifras.py` con
  `glob`: 562 contra 561, las dos publicadas. La que estaba mal era la
  primera, y no por poco: el fichero de más es
  `motor/tests/fixtures/clasificador-candidatos/evals/test_exactitud.py`, que
  no es una prueba del producto sino una que vive dentro del repositorio de
  **ejemplo**, el que el producto analiza como sujeto. La cifra del README
  estaba hinchada con una prueba de mentira. Arreglado llamando a la única que
  hay, no copiando el `glob` bueno: dos definiciones de acuerdo por ahora
  siguen siendo dos definiciones.

### Y dos verbos más en la plataforma

`aplicabilidad` y `comprobar`, que el motor tenía y la API no traducía. La
aplicabilidad es la **primera** pregunta del producto —qué te ata— y era la
única de las grandes sin pantalla: sin ella había que lanzar un `plan`, que
arranca el motor sobre el repositorio entero, para contestar algo que sale del
perfil y no lee ni un byte. Quedan **fuera** a propósito, con su motivo:
`sellar` y `contestar` firman con clave privada, y exponerlos por HTTP pone
esa clave en el servidor; `conectar` clona una URL que manda quien llama, que
es la superficie más grande del producto; `ortografia` y `exportar` son
herramientas del árbol, no del cliente.

## Quinta pasada — recorrer el producto como cliente, con un navegador

Playwright, pantalla por pantalla, parándose en cada acción. Es la primera
pasada que MIRA en vez de leer, y por eso encontró una clase de defecto que
ninguna de las cuatro anteriores podía encontrar: cosas que compilan, pasan
todas las puertas y no funcionan **para una persona**.

### El panel enseñaba cuatro de sus once vistas, y pintaba bien una

- **D-108. Siete vistas de once no se podían pulsar nunca.** `RUTAS` pasó de
  cuatro a once y las **dos** tablas que deciden qué se ve se quedaron en
  cuatro. `CATEGORIAS` no listaba las nuevas, así que ninguna categoría las
  enseñaba; y `pintarBotones` llevaba cuatro pares escritos a mano, así que
  los otros siete botones conservaban el `disabled` del HTML **para siempre**,
  en cualquier categoría. El Anexo IV, la declaración de aplicabilidad, el
  cuestionario, el almacén de evidencia, la revisión por la dirección, la
  aplicabilidad y el control del artículo 50: justo lo que la portada vende.

  Y el texto de cada categoría ya **prometía** lo que la categoría no daba:
  «Pyme: lo que te ata, lo que falta por contestar y el expediente» enseñaba el
  plan y los vencimientos. El reparto nuevo es el que ese texto ya decía.

  La lección estaba aprendida **veinte líneas más abajo**, donde los clics se
  enganchan recorriendo `Object.keys(RUTAS)` con este comentario: «con nueve
  vistas, la novena es la que alguien olvida y el botón no hace nada sin que
  falle nada». Se arregló ahí y se dejó intacto aquí. Es el mismo defecto que
  tuvo la API una capa más abajo —traducía cinco de diecinueve verbos—
  reaparecido una capa más arriba: se arregló la API, se amplió `RUTAS`, y el
  arreglo nunca llegó a la pantalla.

  Nadie lo echó de menos porque **un botón oculto no deja hueco**. La puerta
  que ya había comprobaba que cada vista tuviera botón y texto, y las once lo
  tenían: lo que faltaba era que alguien pudiera llegar a pulsarlo. La puerta
  nueva mira la cadena entera.

- **D-109. `lineasDe` conocía tres formas de documento de las once que el panel
  pide.** Las demás caían a cero filas y lo único que veía quien las pedía era
  el volcado de JSON: el cuestionario son **noventa** preguntas y salía como
  425 KB de JSON; la SoA, treinta y ocho controles; el Anexo IV, veintitrés
  secciones. Adaptadores para las cuatro, más el control del artículo 50.
  Ninguno inventa un dato: si un campo no viene, la fila lo deja vacío.

- **D-110. Ganaba la lista vacía.** `Array.isArray([])` es cierto, así que una
  lista vacía que apareciera antes en la cadena tapaba a una llena de después.
  La revisión por la dirección decía «ninguna línea encaja con este filtro»
  teniendo diez entradas, porque su documento trae `no_conformidades` vacío.

- **D-111. El estado vacío te mandaba hacer lo que acababas de hacer.** «Conecta
  un servidor y pide el plan», también después de conectar. Una pantalla que no
  se entera de lo que acabas de hacer te dice que no funciona.

- **D-112. «1 líneas»,** en un producto que tiene una puerta para las tildes del
  castellano.

### La portada era un documento excelente sin una sola forma de actuar

- **D-113. El bloque de código salía como un párrafo corrido.** `.cod` es un
  `div` con saltos de línea dentro y **sin `white-space:pre`**, y el HTML los
  colapsa. Las cinco órdenes y sus comentarios salían pegados en una línea
  ilegible. Es el único elemento de la página que alguien va a **copiar**, y
  era el que peor estaba. Llevaba así desde siempre.

- **D-114. Ni un enlace externo, ni un botón en las tarjetas, ni un contacto.**
  Se podía leer entera, admirarla, y no hacer nada. Y el argumento entero del
  producto es «el motor es el mismo fichero que puedes leer»: no había dónde
  pulsar para leerlo. Además «Empezar gratis» llevaba a la **tabla de
  precios** —pulsar «gratis» y aterrizar en los precios es una promesa rota en
  el primer clic— y el segundo botón del hero llevaba **también** a `#como`.

### La plataforma en seis idiomas, y la trampa que tenía dentro

La portada ya hablaba seis y el panel y la consola dos. Al ponerlos a seis
apareció lo único interesante de todo esto:

- **D-115. El idioma de la interfaz no es el del contenido, y no puede serlo.**
  El motor emite en dos idiomas y el catálogo está en dos, porque es contenido
  normativo y lo escribe una persona. Atar los dos ajustes habría dejado el
  panel en francés **con el contenido en blanco** —`bil()` devuelve vacío a
  propósito cuando falta el idioma pedido, y eso es correcto— y la consola en
  francés escribiendo **`undefined`** en cada título de la tabla, que es peor
  que vacío: vacío se nota, `undefined` parece un dato. Son dos ajustes, el
  contenido cae al inglés, y la pantalla lo **dice** en los seis idiomas.

- **D-116. Dos fugas de idioma que se veían a simple vista.**
  `#servidor-nota` se escribía una sola vez, dentro de `arrancar()`, así que
  quien cambiaba de idioma se quedaba con ese párrafo en castellano dentro de
  una pantalla en alemán. Y el vocabulario de roles caía a `es`, así que un
  alemán veía la interfaz en alemán y los roles en castellano.

- **D-117. La puerta contra D-116 nació muerta.** Se escribió con un heredoc de
  bash, que convirtió el `\b` de la expresión regular en un **byte de retroceso
  de verdad**: buscaba un carácter de control y no casaba nunca. Pasó verde con
  el fallo delante, y sólo se vio al intentar verla FALLAR contra el código
  roto. Segunda vez que este árbol tropieza con lo mismo, y la razón por la que
  la regla de la casa es «toda puerta nueva hay que verla fallar antes de
  creérsela» y no «toda puerta nueva hay que escribirla».

### Lo que esta pasada dice del resto

Ninguna de las cuatro pasadas anteriores podía encontrar esto, y no por falta
de rigor: **el panel no tiene una sola prueba que ejecute su JavaScript**. Un
`ReferenceError` que rompía las once vistas —`total is not defined`, y lo
introduje yo arreglando D-112— pasó la reproducibilidad, la accesibilidad, las
claves de texto y el contrato de campos sin que ninguna se inmutara. Lo cazó
el navegador a los treinta segundos.

Las puertas nuevas de esta pasada son estructurales porque es lo que se puede
leer sin navegador: que toda vista sea alcanzable, que `pintarBotones` recorra
`RUTAS`, que el texto se escriba al pintar y no al arrancar. Sujetan la causa,
no el síntoma. Lo que sigue sin sujetarse —y se dice— es el síntoma: nadie
corre esta página en un navegador salvo a mano.


## Sexta pasada — poner el navegador dentro de la puerta

La quinta pasada encontró diez defectos recorriendo el producto a mano y cerró
diciendo lo que faltaba: *«lo que sigue sin sujetarse es el síntoma: nadie corre
esta página en un navegador salvo a mano»*. Esta pasada lo sujeta —
`herramientas/navegador.py` y la fase `navegador`, que abre el panel en
Chromium, pulsa las once vistas contra la API de verdad y mira lo que sale.

Encontró cinco defectos **la primera vez que corrió**, y el más caro no estaba
en el producto.

### Lo que la puerta nueva cazó en su primera ejecución

- **D-118. La vista del almacén de evidencia no podía pintar una fila nunca.**
  La pasada anterior arregló `lineasDe`, que conocía tres formas de documento
  de once, y dio las once por buenas. Pero las que arregló tenían todas una
  LISTA que recorrer. El almacén no la tiene: su documento es un **estado** —
  existe o no, la cadena cuadra o no, cuál es la cabeza, cuántas líneas no se
  puede demostrar que estén intactas—, así que la cadena de formas acababa
  devolviendo cero filas y la pantalla dejaba el volcado de JSON como única
  respuesta.

  Y es la vista que sostiene la única afirmación que este producto hace frente a
  un tercero: que la evidencia es la que esta casa escribió. Arreglar ocho de
  once y contar once es la misma aritmética que dejó `CATEGORIAS` con cuatro
  cuando `RUTAS` tenía once. El navegador la cazó a los treinta segundos.

- **D-119. «Ninguna línea encaja con este filtro», con el filtro en «todas».**
  Un documento que no trae nada y un filtro que lo esconde todo se decían con la
  misma frase. El caso normal es vencimientos un día tranquilo: el recuento dice
  «nada que avisar hoy» y justo debajo salía «ninguna línea encaja con este
  filtro» sin que nadie hubiera tocado el filtro. Quien lo lee busca el filtro
  que no puso.

- **D-120. Los botones de categoría no eran direccionables.** Los de idioma y
  los de tema llevan `data-l` y `data-t`; estos no llevaban nada, así que la
  única forma de pulsar una categoría desde fuera era contar posiciones. Una
  prueba que cuenta posiciones se rompe el día que se reordenan, que es el día
  en que deja de mirar.

### El caro, y no estaba en el producto

- **D-121. El arnés estrangulaba al servidor por su propia bitácora.**
  Las tres fases que levantan la API lo hacían con `stdout=subprocess.PIPE` y
  nadie leyendo. El buffer del sistema operativo son unos pocos kilobytes: al
  llenarse, el servidor **se bloquea escribiendo su siguiente línea de
  bitácora**. No se muere, no cierra el puerto y no dice nada; simplemente deja
  de contestar.

  Se vio midiendo latencias: veinticinco llamadas seguidas iban bien y a partir
  de ahí **todas** se quedaban colgadas, incluidas las baratas que no arrancan
  ningún proceso. Parecía el limitador de concurrencia —que es lo que uno mira
  primero, y el código del limitador es correcto— y era el medidor ahogando al
  medido.

  Es también la causa del rojo intermitente que la fase `api` llevaba dando:
  `ConnectionResetError` bajo la ráfaga de concurrencia, sin nada roto en el
  producto. **Un rojo intermitente es peor que un rojo**: el rojo se arregla, y
  el intermitente se vuelve a correr hasta que sale verde.

  Arreglado en un solo sitio —`arrancar_servidor` y `parar_servidor`— que usan
  las cuatro fases que levantan un servidor, porque dos definiciones de «cómo se
  levanta esto» acaban diciendo cosas distintas.

- **D-122. La puerta imprimía una línea por excepción inesperada, sin traza.**
  Un `AssertionError` de esta casa se explica solo: el mensaje dice qué se
  esperaba y qué salió. Un `ConnectionResetError` no dice nada sin su traza, y
  el runner imprimía el tipo y el mensaje y tiraba el resto. El rojo de D-121
  decía *qué* reventó y no *dónde*, así que no se podía distinguir «el servidor
  se cayó al arrancar» de «se cayó bajo los topes». Un rojo que no se puede
  localizar se acaba leyendo como ruido, y un ruido que se ignora es una puerta
  apagada.

- **D-123. El medidor de latencias contaba como CERO justo lo lento.**
  `duracion` es una duración de Go, y Go escribe `633ms` por debajo del segundo
  y `1.815s` por encima. El parseo quitaba `"ms"` y llamaba a `float`, así que
  toda llamada de más de un segundo salía a 0 ms de motor — y ese cero se
  restaba del total y aparecía como **transporte**. La primera tabla que salió
  decía que el motor no tarda nada y que la culpa era de la red, que es
  exactamente lo contrario de lo que pasa.

### Lo que la medición dijo, ya bien

| | |
|---|---|
| cargar el panel | ~200 ms, un fichero, cero peticiones |
| transporte de un verbo | ~4 ms de mediana |
| el análisis en sí | 9–28 ms |
| arrancar el intérprete que lo corre | 440–1 750 ms |

El último renglón es el 97 %, y no es un defecto: es la frontera de la
arquitectura —un proceso por verbo para que el binario que contesta por HTTP sea
el mismo que corre quien audita—. Cargar el catálogo entero cuesta 4 ms. No hay
nada que optimizar en el motor; lo que se optimizaría es el intérprete. Se
publica en el README con el comando que lo reproduce, porque una cifra de
rendimiento sin la forma de repetirla es publicidad.

## Cerrado en la sexta pasada, segunda vuelta

- **D-124. El almacen de evidencia del servidor lo leian tres rutas y no lo
  escribia ninguna.** Se reporto abierto (B-004) porque tenia dos arreglos
  opuestos: o sobraba la frase del permiso, o faltaba el cableado. Se decidio
  lo segundo, y la razon es que el almacen del servidor **no tiene otro
  escritor**: `c.Almacen()` era una ruta que nadie escribia nunca.

  `rbac.go` le pedia a `vigilar` papel de observacion diciendo que «arranca un
  proceso que lee el repositorio entero **y escribe evidencia en el
  expediente**». Lo segundo no era verdad: la ruta no pasaba `--registrar`, asi
  que el motor observaba y tiraba lo observado. A traves de la plataforma el
  expediente estaba SIEMPRE vacio, y con el la vigilancia, los vencimientos y la
  revision por la direccion. Tres pantallas correctas encima de un fichero que
  no existe.

  Arreglado en la ruta que lee el repositorio, y **solo** en esa: la de
  `vencimientos` invoca el mismo verbo con `--solo-almacen`, no mira el codigo
  y no tiene nada que observar. Escribir desde ahi seria registrar una
  observacion que nadie hizo.

  Medido: de `existe: false` a **14 observaciones**, cadena que verifica y
  cabeza sellada; la segunda llamada registra **0** y revalida **14**, que es lo
  que debe hacer — la revalidacion mueve el reloj de la frescura sin inflar el
  fichero. `revision` paso de 0 a 10 entradas y `vencimientos` de 0 a 14
  veredictos.

  Y de paso se corrigio la frase del permiso, que agrupaba tres verbos
  diciendo que los tres escriben evidencia: `plan` y `comprobar` no escriben
  ninguna. Su papel se justifica por la maquina que cuestan, que es cierto. Un
  comentario que avala un control es peor que ninguno cuando es falso, porque
  quien lo lee deja de comprobarlo.

- **D-125. Una fila sin estado pintaba una insignia vacia.** La insignia se
  pintaba siempre, asi que las dos filas que son un recuento a secas en la
  vista del almacen salian con una pastilla gris vacia al final, que parece un
  estado que no se pudo leer. Enseñar un hueco donde no hay dato invita a
  buscarle un significado.

### Lo que la puerta nueva de esta vuelta habria cazado

Ninguna prueba veia D-124 porque **todas eran ciertas por separado**: el verbo
registra cuando se le pide, la ruta contesta 200, el documento valida contra su
esquema, el papel es el correcto. Lo que fallaba era el CABLEADO, que es lo
mismo que le paso al revisor de vencimientos cuando se construia con `nil`.

Por eso la puerta nueva vive en la fase `api`, contra el servidor levantado, y
afirma el ciclo entero: almacen vacio -> vigilar -> almacen con cadena que
verifica -> vigilar otra vez -> revalida sin duplicar -> y las dos rutas que
leen ese almacen ven lo escrito. Se vio fallar quitando el `--registrar`.

Y dos puertas mas de documentacion, que son baratas y cubren el defecto que peor
envejece: que las imagenes que los documentos ensenan existan, lleven texto
alternativo y esten todas citadas — con el reves incluido, una captura que ya no
ensena nadie es un fichero que viaja en cada clon para siempre — y que los
enlaces internos lleven a algun sitio. La primera version del manual tenia cinco
capturas huerfanas y la puerta las canto el dia que nacio.

Y una tercera, que sale de mirar lo que el manual pide que la gente TECLEE:
`fase_instalacion` comprobaba la primera orden --la de instalar, que mando a un
404 durante meses-- y ninguna de las demas. El manual manda teclear treinta y
dos. Una bandera renombrada en el motor dejaria el manual mandando teclear algo
que contesta «unrecognized arguments», igual de creible y sin que nada se ponga
rojo. Ahora se le pregunta al CLI de verdad con `--help`, verbo por verbo. Se
vio fallar cambiando `--cual` por `--que-anexo` en una linea del manual.


## Las dos que se reportaron sabidas, decididas

Las dos salieron de mirar el resultado, no de una prueba en rojo. Ninguna era un
fallo; las dos eran decisiones aplazadas, que es la forma educada de no tomarlas.

- **D-126. El GIF pesaba 8,2 MB, y lo caro no era ese fichero: era la serie.**
  Un video grabado nunca sale igual dos veces, asi que CADA regeneracion mete un
  objeto nuevo en la historia de git y ninguno se va nunca. A ocho megas por
  pasada, cinco pasadas son cuarenta megas que todo el mundo se clona para
  siempre. El coste que se veia --lo que tarda en cargar un README-- era el
  pequeno.

  Se midio en vez de estimarlo: se grabo el recorrido UNA vez y se probaron
  cinco codificaciones sobre el mismo video. Dos cosas que no se esperaban:

  - El **webm sale a 3,1 MB**, menos que casi todos los GIF. Se descarto de
    todos modos porque un `<video>` con ruta relativa no se ve seguro en GitHub,
    y un heroe roto es peor que uno pesado. Un GIF se ve en todas partes.
  - Grabar una ventana MAS PEQUENA para escalar menos **sube** el peso: 1120x740
    escalado a 820 px pesa mas que 1400x900 escalado a 760. Lo que cuesta es la
    densidad de lo que cambia, no el factor de escala. La intuicion iba al
    reves.

  Queda en **680 px, 5 fps, 64 colores: 3,1 MB**, un 62 % menos. Se miro un
  fotograma antes de decidir: el titular, las categorias y el ciclo se siguen
  leyendo, que es lo que un GIF de README tiene que ensenar; la letra pequena
  no, y nadie la lee ahi. El presupuesto del comando baja de 10 MB a 5, y el
  ancho del `<img>` del README baja a 680 para no escalar hacia arriba una
  imagen de 680.

- **D-127. La documentacion inglesa mandaba teclear castellano sin traducirlo.**
  `actaira preguntar . --alto-riesgo si` en un manual en ingles. Estaba dicho y
  justificado, y seguia sin poder leerse.

  **No se anaden alias ingleses**, y esa es la parte con criterio. El motor
  emite ESE MISMO vocabulario dentro de los documentos que produce, asi que dos
  pasadas de lo mismo se comparan linea a linea; un segundo juego de nombres
  serian DOS nombres para un verbo, que es el fallo con el que este arbol ha
  tropezado cuatro veces --los roles, la lista blanca de banderas, la tabla de
  vistas y las cifras publicadas--. Y `--alto-riesgo si` lleva el valor `si`:
  aliasarlo tambien seria aliasar el vocabulario que viaja dentro del documento.

  Se comprobo antes de decidir que el caso malo no es silencioso:
  `--alto-riesgo yes` sale con codigo 2 y `invalid choice: 'yes' (choose from
  si, no, null)`. No hay respuesta equivocada callada, solo friccion.

  Asi que se paga la friccion donde se paga: un **glosario** de los 16 verbos,
  las 17 banderas y los 3 valores, antes del primer comando del manual ingles, y
  una nota en el README ingles que enlaza a el. Con su puerta, porque un
  glosario es justo la clase de lista que se queda corta: el dia que el manual
  nombre un verbo nuevo sin glosarlo, la puerta lo dice. Vista fallar quitando
  `--registrar` del glosario y dejandolo citado en el resto del manual.

  Y el glosario **nacio corto**, que es la parte que hay que contar. Decia «here
  is the whole first one» y listaba DIECISEIS verbos de los dieciocho que el
  motor tiene: faltaban `contestar` y `conectar`. La primera version de su
  puerta tampoco lo veia, porque comprobaba solo los verbos que la
  documentacion CITA -- y un verbo que no se cita tampoco se echa de menos, que
  es literalmente el mismo razonamiento por el que siete vistas del panel
  estuvieron inalcanzables sin que nadie las echara en falta.

  Ahora la puerta compara el glosario con `actaira --help`, que es la unica
  lista que no puede mentir sobre si misma. Vista fallar quitando `exportar`.

  Tercera vez en esta pasada que un heredoc de bash se come una barra
  invertida al escribir codigo (D-117 fue la primera). Se dejo de usar heredocs
  para eso.
