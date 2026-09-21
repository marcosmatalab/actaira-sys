# Cambios

Lo que cambia entre versiones, y sobre todo **qué se rompe**. Una versión que
no dice qué rompe obliga a cada cliente a descubrirlo en producción.

---

## 0.15.0 — 21 de septiembre de 2026

Salida de una auditoría externa que puntuó el producto 4,5 sobre 10 y listó
bloqueantes jurídicos, técnicos y de seguridad. Se cerraron todos los que
marcaba como P0 y P1, y en el camino aparecieron seis defectos que la auditoría
no había visto porque corrió la suite en un solo sistema operativo.

### INCOMPATIBLE: lo que deja de funcionar

Es un salto de versión menor y no de parche porque **hay comportamiento que
cambia**. Cada uno de estos era un fallo hacia el silencio, y cerrarlo
necesariamente hace ruidoso algo que antes no lo era.

- **Un rol desconocido ahora revienta.** `Perfil(roles={"lo_que_sea"})` lanza
  `RolDesconocido` en vez de resolver con cero obligaciones aplicables. Antes,
  un nombre de rol equivocado producía exactamente el mismo documento que un
  rol válido al que de verdad no le ata nada: «no te ata ninguna obligación».
  El panel mandaba `responsable_del_despliegue`, la API lo validaba contra su
  propia lista —que tenía el mismo error— y un responsable del despliegue real
  no recibía ninguna de sus trece obligaciones.
- **La API rechaza los nombres de rol antiguos** (`responsable_del_despliegue`,
  `fabricante_de_productos`) con 400. Los canónicos son los siete del motor, y
  `panel/roles.json` los publica.
- **`migrar_a` se niega si la cadena del origen está rota.** Antes reescribía
  los sellos y el resultado salía con una cadena nueva y perfectamente válida,
  conservando el contenido manipulado y sin una marca de dónde venía. Para
  conservarlo de todas formas hay que pedirlo: `--acepto-una-cadena-rota`, y
  cada línea desde la rotura sale marcada dentro del sello.
- **`verificar` rechaza un sello con campos que la firma no cubre.** Añadirle
  `"estado": "conforme"` a un sello válido lo dejaba verificando.
- **Los esquemas del contrato ganan campos obligatorios**: `plan` trae
  `ilegibles`, `recuento_por_fuerza` y `nota_de_fuerza`; `cuestionario` trae
  `recuento_por_confianza` y `nota_de_confianza`. Un consumidor que valide con
  `required` estricto tiene que actualizarse.
- **El servidor limita la concurrencia** de los verbos del motor y contesta 429
  con `Retry-After` al pasarse. Por omisión, 4 en la máquina y 2 por cliente;
  se ajusta con `--tope-global` y `--tope-por-cliente`.
- **El remediador de red exige HTTPS** y rechaza destinos que no estén en
  internet público. Un Jira en la intranet se declara con
  `ACTAIRA_DESTINOS_INTERNOS`.
- **Los identificadores de no conformidad se validan**: letras, dígitos, punto,
  guion y guion bajo, empezando por letra o dígito, hasta 64.

### Seguridad

- Aislamiento entre clientes: `rutaSegura` resuelve enlaces simbólicos antes de
  decidir. Un directorio de trabajo enlazado fuera de la raíz pasaba la barrera
  y el motor leía la carpeta de otro cliente.
- Escritura arbitraria de ficheros en el remediador: un identificador absoluto
  escribía donde dijera, no un directorio más arriba.
- SSRF con la petición ya firmada: `--destino` llegaba al servicio de metadatos
  de la nube con la credencial del cliente adjunta. Ahora hay HTTPS obligatorio,
  rechazo de direcciones no públicas —incluida la de metadatos mapeada a IPv6—,
  sin seguir redirecciones y con techo de lectura.
- La política de seguridad de contenido del panel deja de llevar
  `'unsafe-inline'`: se calcula de los bytes de la página servida.

### Normativa

- **Restaurado el Anexo XIV**, que el catálogo había borrado afirmando que no
  existe. Lo inserta el Reglamento (UE) 2026/1744 (CELEX 32026R1744, DO de
  24-07-2026). La corrección que lo borró decía estar «contrastada contra el
  Diario Oficial», y lo estaba: contra el texto de 2024. Ahora el bloque
  `instrumento` declara `version_consolidada` y, por cada acto modificativo, lo
  que de él se ha recogido **y lo que no**.
- Cobertura completa: los 88 requisitos atómicos del Reglamento y los 38
  controles del Anexo A tienen control o pregunta. Faltaban dos requisitos
  (artículo 9.9 y artículo 26.7/26.11) y diez controles.

### Lo que se dice y antes no se decía

- El plan publica **qué no se pudo leer** (`ilegibles`) y **de qué clase es cada
  comprobación** (`comportamiento` si se leyó lo que el programa hace,
  `presencia` si sólo casó un nombre de fichero).
- El cuestionario publica el **nivel de confianza** de cada respuesta. Una
  declaración sin firma se reimportaba con un aviso por la salida de error —que
  en integración continua no lee nadie— y sus respuestas entraban en el
  expediente indistinguibles de las firmadas.
- El panel deja de afirmar que los números vienen de «un documento firmado por
  el motor»: no verifica ninguna firma, y ahora lo dice.
- `/salud` informa del estado de la vigilancia y de los verbos en curso.

### Arreglado

- **La vigilancia no corría.** `main.go` construía el servidor con el revisor a
  `nil` y el campo no se leía en ningún sitio: el paquete de vencimientos
  compilaba, tenía sus pruebas verdes y el producto no lo invocaba jamás.
- El almacén de evidencia **no tenía candado fuera de POSIX**: dos pasadas de
  integración continua simultáneas dejaban el expediente en `AlmacenAlterado`
  de forma permanente.
- Las rutas del árbol se nombraban con el separador del sistema, así que en
  Windows las reglas del catálogo no casaban y **el producto emitía no
  conformidades falsas**.
- `actaira ortografia --arreglar` acentuaba claves de diccionario dentro de
  f-strings, escribiendo un `KeyError`. Y tres defectos más del mismo corrector.
- La medición de durabilidad del marcado del artículo 50 **daba siempre la
  misma respuesta**, porque simulaba la cadena con una biblioteca que descarta
  metadatos siempre. Ahora mide las dos hipótesis y las distingue.
- `--paso` expone en la línea de mandatos la cadena de publicación, que estaba
  en el contrato desde hacía siete fases y ningún verbo rellenaba.

### Interoperabilidad, consola e identidad

Esto no arregla defectos: **añade** lo que faltaba para que Actaira se enchufe a
un sistema de gestión de otra empresa y para que la pantalla enseñe lo que el
motor ya sabía.

- **Cinco rutas de lectura**: `almacen`, `preguntar`, `soa`, `anexo` y
  `revision`. La API traducía cinco de los diecinueve verbos del motor, así que
  la pantalla no podía enseñar la evidencia, ni el cuestionario, ni la
  declaración de aplicabilidad, ni el expediente. Quien abría el panel veía
  cuatro botones y concluía que el producto hace cuatro cosas.
- **`almacen verificar --json`**: ese verbo sólo sabía imprimir prosa, así que
  el estado de la cadena de evidencia —la única afirmación que este producto
  hace frente a un tercero— no se podía pedir desde ninguna pantalla. Su
  esquema se publica en `contrato/almacen.json`.
- **`contrato/openapi.json`**, generada de las rutas que el enrutador publica de
  verdad y de los esquemas del contrato. Escribirla a mano es la deriva en
  estado puro: nada la compara con nada, y quien la lea escribirá un conector
  contra endpoints que no existen.
- **Webhooks firmados** con HMAC-SHA256 y comparación en tiempo constante. La
  credencial demuestra que quien llama puede tocar este cliente; la firma
  demuestra que el cuerpo viene del proveedor y llegó intacto. Sin secreto
  configurado el evento se atiende y la respuesta lleva `firma_verificada:
  false`; con secreto configurado, un evento sin firma se **rechaza**.
- **`remediar abrir --simular`**: enseña lo que saldría al sistema de tickets y
  no llama a nadie ni escribe en el almacén. Lo que sale de ahí entra donde el
  cliente organiza su trabajo, y un ticket mal redactado no se borra.
- **`docs/CONECTORES.md`**: la guía para escribir un conector, con puerta que
  extrae los métodos de los protocolos reales y exige que los documente.
- **La consola**, con nueve vistas, buscador con anuncio para lectores de
  pantalla, foco de teclado visible y una **puerta de accesibilidad en el
  build**: botón sin nombre, campo sin etiqueta, `lang` ausente, foco invisible,
  dos `h1` y salto de encabezado. Dice además lo que NO comprueba —contraste
  real, orden de tabulación percibido, si los textos se entienden— para que
  nadie lea la lista como completa.
- **OIDC y papeles.** Con `--emisor`, el cliente y los roles salen del testigo
  firmado y de ningún otro sitio. Tres papeles —`lectura`, `observacion`,
  `remediacion`— más `admin`. Un verbo sin permiso declarado no pasa. Sin
  `--emisor` se siguen usando las credenciales estáticas, que no tienen papeles
  y no caducan, y el arranque lo dice con todas las letras.

### Lo que NO está probado, dicho aquí

- **No hay conector de ServiceNow, OneTrust ni Archer.** Escribir uno sin una
  instalación real contra la que probarlo produciría código que compila, tiene
  sus pruebas en verde y nadie ha visto funcionar contra lo que dice integrar.
  Lo que sí hay es el contrato que cumplen los tres conectores que vienen
  —GitHub, Jira y Linear—, probado con ellos.
- **El verificador de identidad está probado contra un doble local**, no contra
  un Entra ID ni un Keycloak. Lo que se demuestra es que el servidor verifica
  firmas, reclamaciones y papeles; no que hable con un proveedor concreto. La
  fase de aceptación lo imprime en cada ejecución.
- **El juego de claves no se descarga de `/.well-known`**, se configura en un
  fichero. Arrancar significaría aceptar sin revisión cualquier clave que
  devuelva un servidor, y esas claves deciden de quién es cada expediente.

### De la pasada adversarial final

Una barrida buscando `except` que se tragan y siguen, `pass` en ramas de
decisión y comparaciones con un solo literal encontró tres cosas más:

- **El lector de agentes descartaba ficheros en silencio** en tres `continue`:
  un enlace que sale de la raíz, un fichero que no es UTF-8, un Python que no
  analiza. Es el mismo fallo que el plan tenía al descartar sus `ilegibles`,
  asomando por otra ventana, y aquí es peor de notar: «no encontré ninguna
  herramienta porque no pude leer el fichero donde están» se parece muchísimo a
  «no hay herramientas». Ahora se anotan y salen como límite del control.
- **Un paquete de reglas ilegible se saltaba**. De ahí sale el texto que se le
  manda a una persona en un ticket, y es un fichero del árbol: que no cargue es
  un defecto de esta casa, no una condición del entorno. Ahora revienta con su
  nombre delante.
- **Una rama de lectura de PNG que nunca se ejecutaba**: comprobaba `xmp` dentro
  del nombre del trozo (`tEXt`) en vez de dentro de la palabra clave, y aunque
  hubiera casado no hacía nada. Un fichero cuyo XMP vive en un `tEXt` se leía
  como NO MARCADO. Leer sólo donde uno escribe convierte «no miré ahí» en «no
  está».

### Cómo se comprueba

`python herramientas/todo.py` corre las dieciocho fases de aceptación. La puerta
ya no es el `Makefile`: la mayoría de sus objetivos terminaban en `; true`,
`|| true` o `| head` y **no podían ponerse rojos**.
