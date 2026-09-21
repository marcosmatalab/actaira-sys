/* El panel conectado. NO calcula nada: pinta lo que el motor devolvio.
 *
 * LA REGLA DE ESTE FICHERO ES LA MISMA QUE LA DE LA API
 * ------------------------------------------------------
 * Traduce presentacion, nunca significado. Cada numero que sale en pantalla
 * es un campo del documento; cada frase que lo explica viaja dentro del
 * documento, en los dos idiomas, escrita por una persona. Aqui no se suma, no
 * se promedia, no se ordena por gravedad y no se pinta ningun semaforo que el
 * motor no haya dicho.
 *
 * El dia que esta pagina calcule algo, habra tres motores en vez de dos, y el
 * tercero sera el mas facil de no auditar porque vive en el navegador de otro.
 *
 * LA CREDENCIAL NO SE GUARDA
 * ---------------------------
 * Ni en localStorage, ni en sessionStorage, ni en una cookie. Vive en una
 * variable y se pierde al recargar. Es incomodo a proposito: un token en el
 * almacenamiento del navegador lo lee cualquier script que acabe en la pagina,
 * y este token vale para leer el expediente entero de un cliente.
 */
"use strict";

const TEXTOS = __TEXTOS__;
// Los roles NO se escriben aqui. Vienen de `panel/roles.json`, que genera
// `herramientas/generar_roles.py` desde el vocabulario del motor. Esta lista
// estaba escrita a mano en este fichero y decia `responsable_del_despliegue`
// y `fabricante_de_productos`, que el motor no conoce: un responsable del
// despliegue de verdad recibia cero obligaciones aplicables. Y le faltaba
// `proveedor_modelo`, asi que un proveedor de modelo de uso general no podia
// decirlo aunque cinco obligaciones del catalogo lo nombren.
const ROLES = __ROLES__;
const T = () => TEXTOS[estado.idioma];

/* Lo que cada categoria de producto ensena. NO cambia lo que el motor dice:
 * cambia que le pides y que ves primero, que es lo unico que una categoria
 * comercial tiene derecho a cambiar. */
/* ESTA TABLA SE QUEDO ATRAS Y ESCONDIO EL PRODUCTO.
 *
 * `RUTAS` paso de cuatro vistas a once y esto no se toco, asi que SIETE de las
 * once no se podian alcanzar desde ninguna categoria: el Anexo IV, la
 * declaracion de aplicabilidad, el cuestionario, el almacen de evidencia, la
 * revision por la direccion, la aplicabilidad y el control del articulo 50.
 * Justo lo que la portada vende.
 *
 * Es el mismo defecto que ya tuvo la API una capa mas abajo -- traducia cinco
 * de diecinueve verbos, y quien abria el panel concluia que el producto hace
 * cinco cosas -- reaparecido una capa mas arriba: se arreglo la API, se
 * amplio `RUTAS`, y la tabla que decide QUE SE VE se quedo como estaba. El
 * arreglo nunca llego a la pantalla.
 *
 * Y lo peor es que el texto de cada categoria ya prometia lo que la categoria
 * no daba: «Pyme: lo que te ata, lo que falta por contestar y el expediente»
 * ensenaba el plan y los vencimientos, ni el cuestionario ni el expediente.
 * El reparto de abajo es el que ese texto ya decia.
 *
 * Hay ahora una puerta -- `test_toda_vista_es_alcanzable` -- que falla si una
 * vista de `RUTAS` no aparece en ninguna categoria: un boton que existe y no
 * se puede pulsar nunca es peor que un boton que no existe, porque nadie lo
 * echa de menos. */
const CATEGORIAS = {
  // El repositorio, la integracion continua y los hallazgos donde ya miras.
  dev:     { pasos: ["p2", "p3", "p5"],
             verbos: ["plan", "comp", "ev", "nc"] },
  // Lo que te ata, lo que falta por contestar y el expediente.
  pyme:    { pasos: ["p1", "p2", "p3"],
             verbos: ["apl", "plan", "preg", "soa", "anx", "venc"] },
  // Varios sistemas, vigilancia continua, no conformidades y remediacion.
  empresa: { pasos: ["p1", "p2", "p3", "p4", "p5"],
             verbos: ["apl", "plan", "comp", "preg", "soa", "anx",
                      "vig", "venc", "nc", "ev", "rev"] },
};

/* Los campos de DOCUMENTO que esta pagina lee, en un solo sitio y con nombre.
 *
 * Existe para poder comprobarlos contra el contrato publicado: si el motor
 * renombra un campo, esta lista y `contrato/*.json` dejan de casar y la puerta
 * lo dice. Sin ella, la pantalla se quedaria en blanco sin que fallara nada,
 * que es el modo de fallo que el contrato existe para evitar y que hasta ahora
 * solo cubria el lado Go.
 *
 * Lo que esta lista NO demuestra, y se dice en vez de disimularlo: que el
 * codigo no lea ademas algun campo que no este aqui. Comprobarlo de verdad
 * pedia analizar JavaScript, y un analizador a medias se relaja hasta que deja
 * de mirar. Lo que si se comprueba es que todo lo de aqui existe en el
 * contrato Y aparece en el codigo, asi que la lista no envejece por los dos
 * lados a la vez.
 */
const CAMPOS_DEL_DOCUMENTO = [
  "esquema", "recuento", "lineas", "veredictos", "no_conformidades",
  "total_preguntas", "a_reobservar", "nota_de_recuento", "nota_del_cierre",
  "articulo", "obligacion_id", "titulo", "estado", "hallazgos", "preguntas",
  "motivo", "por_que", "remediacion", "localizacion", "regla_id", "texto",
  "situacion", "regla", "id", "descripcion", "origen", "dias_abierta",
  "incoherencias", "vencida", "estancada", "nombres_de_estado",
];

/* Como se lee un estado. El nombre lo publica el MOTOR dentro del documento,
 * porque el vocabulario del producto es suyo: si lo tuviera esta pagina, el
 * dia que el motor anada un estado un cliente ingles veria `sin_cubrir` en
 * crudo, que es el defecto que la fase 20 encontro mirando la pantalla en
 * ingles. Si falta, se ensena el identificador: feo y verdad. */
function nombreDe(clave) {
  const r = estado.documentos[estado.vista];
  const tabla = r && r.documento ? r.documento.nombres_de_estado : null;
  const n = tabla && tabla[clave] ? bil(tabla[clave]) : "";
  return n || String(clave || "").replace(/_/g, " ");
}

const estado = {
  idioma: "es",
  tema: "",
  categoria: "pyme",
  conectado: false,
  servidor: "",
  cliente: "",
  credencial: "",          // en memoria y en ningun otro sitio
  documentos: {},          // verbo -> {codigo, documento, esquema}
  vista: "plan",
  filtro: "todas",
};

/* --- utilidades sin ninguna doctrina dentro ------------------------------ */

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

function vaciar(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }

function el(etiqueta, clase, texto) {
  const n = document.createElement(etiqueta);
  if (clase) n.className = clase;
  if (texto !== undefined && texto !== null) n.textContent = String(texto);
  return n;
}

/* EL IDIOMA DE LA INTERFAZ NO ES EL DEL DOCUMENTO, Y NO PUEDE SERLO.
 *
 * Esta pagina habla seis idiomas. El MOTOR emite sus documentos en dos, `es` y
 * `en`, porque lo que va dentro es contenido normativo -- titulos de
 * obligaciones, motivos, remediaciones, el texto de cada pregunta -- y eso lo
 * escribe una persona, no una maquina. Traducirlo a maquina seria exactamente
 * lo que la segunda negativa de esta casa prohibe.
 *
 * Asi que son dos ajustes distintos. Si se hubieran atado, poner la interfaz
 * en frances habria dejado el contenido EN BLANCO: `bil()` devuelve vacio a
 * proposito cuando falta el idioma pedido, y eso es correcto -- un expediente
 * en un idioma con frases sueltas en otro es el defecto que el motor lleva
 * doce fases evitando -- pero aplicado a un idioma que el motor no emite
 * habria vaciado la pantalla sin decir por que.
 *
 * El documento se pide en el idioma de la interfaz cuando el motor lo emite, y
 * en ingles cuando no. La pantalla lo DICE en vez de disimularlo. */
const IDIOMAS_DEL_MOTOR = ["es", "en"];

function idiomaDelDocumento() {
  return IDIOMAS_DEL_MOTOR.indexOf(estado.idioma) === -1 ? "en" : estado.idioma;
}

function bil(x) {
  if (!x || typeof x !== "object") return "";
  const v = x[idiomaDelDocumento()];
  return typeof v === "string" ? v : "";
}

/* --- el transporte ------------------------------------------------------- */

async function pedir(metodo, camino, cuerpo) {
  const url = estado.servidor.replace(/\/+$/, "") + camino;
  const r = await fetch(url, {
    method: metodo,
    headers: {
      "Authorization": "Bearer " + estado.credencial,
      "Accept-Language": idiomaDelDocumento(),
      ...(cuerpo ? { "Content-Type": "application/json" } : {}),
    },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });
  const texto = await r.text();
  let doc = null;
  try { doc = JSON.parse(texto); } catch (e) { doc = null; }
  return { estado: r.status, doc };
}

function perfilDelFormulario() {
  // VARIOS roles, no uno. Una organizacion es a la vez proveedor de un sistema
  // y responsable del despliegue de otro, y con un solo valor habia que elegir
  // cual declarar y perder las obligaciones del otro. El motor siempre acepto
  // un conjunto; era la pantalla la que obligaba a quedarse con uno.
  const p = { roles: [...$("#rol").selectedOptions].map((o) => o.value) };
  for (const k of ["alto_riesgo", "sector_publico", "modelo_uso_general", "riesgo_sistemico"]) {
    p[k] = $("#" + k).value;
  }
  p.via_anexo = $("#via_anexo").value;
  p.fecha = $("#fecha").value;
  return p;
}

const RUTAS = {
  plan: (c) => ["POST", `/v1/clientes/${c}/plan`, perfilDelFormulario()],
  vig:  (c) => ["POST", `/v1/clientes/${c}/vigilar`, perfilDelFormulario()],
  venc: (c) => ["GET", `/v1/clientes/${c}/vencimientos`, null],
  nc:   (c) => ["GET", `/v1/clientes/${c}/noconformidades`, null],
  // Las cinco vistas que faltaban. No son pantallas nuevas que inventen nada:
  // son verbos que el motor ya tenia y que la API no traducia, asi que el panel
  // no podia ensenarlos. Una auditoria externa lo leyo como «no hay explorador
  // de evidencia, no hay vista de procedencia, no hay tablero», y la causa
  // estaba una capa mas abajo de donde se veia.
  ev:   (c) => ["GET", `/v1/clientes/${c}/almacen`, null],
  preg: (c) => ["POST", `/v1/clientes/${c}/preguntar`, perfilDelFormulario()],
  soa:  (c) => ["POST", `/v1/clientes/${c}/soa`, perfilDelFormulario()],
  anx:  (c) => ["POST", `/v1/clientes/${c}/anexo?cual=iv`, perfilDelFormulario()],
  rev:  (c) => ["GET", `/v1/clientes/${c}/revision`, null],
  // La aplicabilidad es la PRIMERA pregunta del producto -- que te ata y que
  // no -- y era la unica de las grandes que no tenia pantalla. Sin ella habia
  // que lanzar un `plan`, que arranca el motor sobre el repositorio entero,
  // para contestar algo que sale del perfil y no lee ni un byte del codigo.
  apl:  (c) => ["POST", `/v1/clientes/${c}/aplicabilidad`, perfilDelFormulario()],
  // Y el control del articulo 50 a solas. Estaba dentro del `plan`, mezclado
  // con todo lo demas: quien queria la respuesta de UN control sobre su codigo
  // tenia que pedir el ciclo entero y buscarla.
  //
  // SIN perfil: este verbo no pregunta a quien ata nada, lee el codigo y dice
  // lo que ve.
  comp: (c) => ["POST", `/v1/clientes/${c}/comprobar`, null],
};

async function traer(verbo) {
  const [metodo, camino, cuerpo] = RUTAS[verbo](estado.cliente);
  // El boton se llama igual que la vista. Habia un mapa que traducia cada
  // nombre al suyo y era la identidad: cuatro entradas que decian `plan: plan`.
  // Con las vistas nuevas habria hecho falta acordarse de anadir cinco mas, y
  // el dia que alguien no lo hiciera el boton no se desactivaria mientras corre
  // -- que es lo unico que ese mapa hacia.
  const boton = $("#pedir-" + verbo);
  if (boton) boton.disabled = true;
  try {
    const r = await pedir(metodo, camino, cuerpo);
    if (r.estado === 401) { fallo(T().credencial_mala); return; }
    if (!r.doc || typeof r.doc !== "object") { fallo(T().error_motor); return; }
    if (r.doc.documento === undefined) { fallo(bil(r.doc.que) || T().error_motor); return; }
    estado.documentos[verbo] = r.doc;
    estado.vista = verbo;
    fallo("");
  } catch (e) {
    fallo(T().no_llega);
  } finally {
    if (boton) boton.disabled = !estado.conectado;
    pintar();
  }
}

/* Que poner cuando no hay nada que ensenar.
 *
 * Decia siempre «conecta un servidor y pide el plan», tambien despues de
 * conectar. Una pantalla que te manda hacer lo que acabas de hacer te dice que
 * no se ha enterado, y lo primero que piensa quien la usa es que no funciona.
 */
function vacio() {
  return estado.conectado ? T().sin_datos_conectado : T().sin_datos;
}

function fallo(texto) {
  const n = $("#conexion-mal");
  n.textContent = texto || "";
  n.classList.toggle("oculto", !texto);
}

/* --- conexion ------------------------------------------------------------ */

async function conectar() {
  estado.servidor = $("#servidor").value.trim();
  estado.cliente = $("#cliente").value.trim();
  estado.credencial = $("#credencial").value;
  $("#conectar").disabled = true;
  $("#conectar").textContent = T().probando;
  try {
    const r = await pedir("GET", "/salud", null);
    if (!r.doc || r.doc.vivo !== true) { fallo(T().no_llega); return; }
    // La salud no pide credencial, asi que no demuestra que la credencial
    // valga. Se prueba con una ruta que SI la pide: decir «conectado» porque
    // el servidor respira seria prometer algo que no se ha comprobado.
    const p = await pedir("GET", `/v1/clientes/${estado.cliente}/noconformidades`, null);
    if (p.estado === 401) { fallo(T().credencial_mala); return; }
    estado.conectado = true;
    estado.documentos.nc = p.doc && p.doc.documento !== undefined ? p.doc : undefined;
    fallo("");
  } catch (e) {
    fallo(T().no_llega);
  } finally {
    $("#conectar").disabled = false;
    pintar();
  }
}

function desconectar() {
  estado.conectado = false;
  estado.credencial = "";
  estado.documentos = {};
  $("#credencial").value = "";
  pintar();
}

/* --- pintar -------------------------------------------------------------- */

const CLASE_SITUACION = {
  ata: "ata", con_hallazgos: "mal", comprobada: "ata", futura: "futura",
  no_ata: "", a_preguntar: "indet", indeterminada: "indet", sin_resolver: "indet",
  solo_formulario: "", abierta: "indet", en_analisis: "indet", con_accion: "indet",
  ejecutada: "futura", verificada: "ata", vencidas: "mal", estancadas: "mal",
  incoherentes: "mal",
};

function pintarTextos() {
  const t = T();
  document.documentElement.lang = estado.idioma;
  // El aviso de que el documento no viene en el idioma de la pantalla.
  const aviso = $("#idioma-doc");
  if (aviso) {
    const distinto = idiomaDelDocumento() !== estado.idioma;
    aviso.textContent = distinto ? T().doc_en_otro_idioma : "";
    aviso.classList.toggle("oculto", !distinto);
  }
  // LA NOTA DEL SERVIDOR SE REPINTA COMO TODO LO DEMAS.
  //
  // Se escribia UNA sola vez, al arrancar, asi que quien cambiaba de idioma se
  // quedaba con ese parrafo en castellano dentro de una pantalla en aleman. Se
  // ve a simple vista y llevaba ahi desde que la pagina tiene dos idiomas: lo
  // que no lo cazaba era que ninguna prueba cambia el idioma y vuelve a mirar.
  const servido = location.protocol === "http:" || location.protocol === "https:";
  $("#servidor-nota").textContent = servido ? T().servidor_fijado : T().servidor_libre;
  document.title = t.titulo;
  const mapa = {
    "#eyebrow": "eyebrow", "#titular": "titular", "#entradilla": "entradilla",
    "#sin-porcentaje": "sin_porcentaje", "#t-categoria": "categoria",
    "#t-ciclo": "estado_del_ciclo", "#t-conexion": "conexion", "#t-servidor": "servidor",
    "#t-cliente": "cliente", "#t-credencial": "credencial",
    "#credencial-nota": "credencial_nota", "#conectar": "conectar",
    "#desconectar": "desconectar", "#t-perfil": "perfil", "#t-roles": "roles",
    "#origen-nota": "origen_nota",
    "#t-roles-ayuda": "roles_ayuda",
    "#t-alto": "alto_riesgo", "#t-via": "via", "#t-sector": "sector",
    "#t-general": "uso_general", "#t-sistemico": "sistemico", "#t-fecha": "fecha",
    "#pedir-plan": "pedir_plan", "#pedir-vig": "pedir_vigilancia",
    "#pedir-venc": "pedir_venc", "#pedir-nc": "pedir_nc",
    "#pedir-ev": "pedir_ev", "#pedir-preg": "pedir_preg",
    "#pedir-soa": "pedir_soa", "#pedir-anx": "pedir_anx",
    "#pedir-rev": "pedir_rev", "#pedir-apl": "pedir_apl",
    "#pedir-comp": "pedir_comp",
    "#t-vistas": "vistas", "#t-buscar": "buscar",
    "#t-recuento": "recuento", "#t-lineas": "lineas", "#t-documento": "documento",
    "#doc-nota": "doc_nota",
  };
  for (const [sel, clave] of Object.entries(mapa)) {
    const n = $(sel);
    if (n) n.textContent = t[clave];
  }
  $("#enchufe-txt").textContent = estado.conectado ? t.conectado : t.sin_conexion;
  $("#punto").classList.toggle("vivo", estado.conectado);
  $$("#tema button")[0].title = t.tema_claro;
  $$("#tema button")[1].title = t.tema_oscuro;
  // Los roles son valores del motor y sus nombres son de la pantalla: quien
  // elige "deployer" en ingles manda el identificador que el motor entiende.
  // Traducir el valor lo habria roto; no traducir la etiqueta habria dejado
  // media pantalla en castellano. Las dos cosas salen ahora del MISMO sitio.
  const rol = $("#rol");
  const antesRol = [...rol.selectedOptions].map((o) => o.value);
  vaciar(rol);
  for (const r of ROLES.roles) {
    // El vocabulario de roles sale del MOTOR y existe en `es` y `en`, como
    // todo el contenido normativo. Caia a `es` cuando faltaba el idioma, asi
    // que un aleman veia la interfaz en aleman y los roles en castellano.
    // Cae al mismo idioma al que cae el documento, que es la unica caida que
    // esta pantalla explica.
    const o = el("option", null, r.nombre[idiomaDelDocumento()] || r.nombre.en);
    o.value = r.id;
    o.title = r.definicion[idiomaDelDocumento()] || r.definicion.en;
    rol.appendChild(o);
  }
  const elegidos = antesRol.length ? antesRol : ["proveedor"];
  for (const o of rol.options) o.selected = elegidos.includes(o.value);
  for (const s of $$("select[data-tri]")) {
    const antes = s.value;
    vaciar(s);
    for (const [v, k] of [["", "nulo"], ["si", "si"], ["no", "no"]]) {
      const o = el("option", null, t[k]);
      o.value = v;
      s.appendChild(o);
    }
    s.value = antes;
  }
}

function pintarCategorias() {
  const t = T(), caja = vaciar($("#cats"));
  let i = 1;
  for (const clave of ["dev", "pyme", "empresa"]) {
    const b = el("button", "cat");
    b.setAttribute("aria-pressed", String(estado.categoria === clave));
    b.appendChild(el("p", "n", "0" + i++));
    b.appendChild(el("h3", null, t["cat_" + clave]));
    b.appendChild(el("p", null, t["cat_" + clave + "_pie"]));
    b.onclick = () => { estado.categoria = clave; pintar(); };
    caja.appendChild(b);
  }
}

/* El ciclo lee de los documentos que HAY. Un paso sin documento dice que no se
 * ha pedido, y no un cero: un cero es una afirmacion sobre el mundo y «no lo he
 * mirado» no lo es. Es la misma distincion que el motor hace entre
 * NO_APLICABLE e INDETERMINADA, y fundirla aqui la desharia en la pantalla,
 * que es donde la gente la lee. */
const PASOS = {
  p1: () => sacar("plan", (d) => sumaDe(d.recuento, ["comprobada", "con_hallazgos",
        "a_preguntar", "solo_formulario", "sin_resolver"])),
  p2: () => sacar("plan", (d) => valor(d.recuento, "con_hallazgos")),
  p3: () => sacar("plan", (d) => d.total_preguntas),
  p4: () => sacar("venc", (d) => (d.a_reobservar || []).length),
  p5: () => sacar("nc", (d) => (d.no_conformidades || []).filter((n) => n.estado !== "verificada").length),
};

function valor(o, k) { return o && typeof o[k] === "number" ? o[k] : null; }

/* La UNICA aritmetica de este fichero, y es un recuento de los recuentos que
 * el documento ya trae, no una proporcion. Se escribe aqui, con nombre, para
 * que se vea: si algun dia aparece una division en este fichero, sera facil
 * encontrarla. */
function sumaDe(recuento, claves) {
  if (!recuento) return null;
  let n = 0, hubo = false;
  for (const k of claves) {
    if (typeof recuento[k] === "number") { n += recuento[k]; hubo = true; }
  }
  return hubo ? n : null;
}

function sacar(verbo, fn) {
  const r = estado.documentos[verbo];
  if (!r || !r.documento) return null;
  try { return fn(r.documento); } catch (e) { return null; }
}

function pintarCiclo() {
  const t = T(), caja = vaciar($("#ciclo"));
  let i = 1;
  for (const clave of CATEGORIAS[estado.categoria].pasos) {
    const paso = el("div", "paso");
    paso.appendChild(el("p", "n", "0" + i++));
    paso.appendChild(el("p", "t", t[clave]));
    const v = PASOS[clave]();
    paso.appendChild(v === null || v === undefined
      ? el("p", "v gris", t.sin_recuento)
      : el("p", "v", v));
    caja.appendChild(paso);
  }
}

function pintarBotones() {
  const permitidos = new Set(CATEGORIAS[estado.categoria].verbos);
  // UNA LINEA POR VISTA DE `RUTAS`, NO UNA LISTA ESCRITA A MANO.
  //
  // Aqui habia cuatro pares escritos a mano -- plan, vig, venc y nc -- y
  // `RUTAS` tiene once. Los otros SIETE botones no los tocaba nadie, asi que
  // se quedaban con el `disabled` del HTML PARA SIEMPRE, en cualquier
  // categoria. Existian, se veian si la categoria los dejaba ver, y no se
  // podian pulsar nunca.
  //
  // La leccion ya estaba aprendida VEINTE LINEAS MAS ABAJO, donde los clics se
  // enganchan recorriendo `Object.keys(RUTAS)` con este comentario: «Eran
  // cuatro lineas identicas; con nueve vistas, la novena es la que alguien
  // olvida y el boton no hace nada sin que falle nada». Se arreglo ahi y se
  // dejo intacto aqui, que es como una leccion se queda a medias.
  for (const verbo of Object.keys(RUTAS)) {
    const b = $("#pedir-" + verbo);
    if (!b) continue;
    b.classList.toggle("oculto", !permitidos.has(verbo));
    b.disabled = !estado.conectado;
  }
  $("#desconectar").classList.toggle("oculto", !estado.conectado);
  $("#conectar").textContent = T().conectar;
}

function pintarRecuento() {
  const caja = vaciar($("#recuento"));
  const r = estado.documentos[estado.vista];
  const sello = $("#sello");
  if (!r || !r.documento) {
    sello.textContent = "";
    caja.appendChild(el("p", "vacio", vacio()));
    return;
  }
  const t = T();
  sello.textContent = `${r.documento.esquema} · ${t.codigo} ${r.codigo}` +
    (t["codigo_" + r.codigo] ? ` — ${t["codigo_" + r.codigo]}` : "");
  const rec = r.documento.recuento || {};
  for (const [clave, n] of Object.entries(rec)) {
    if (typeof n !== "number") continue;
    const p = el("span", "pastilla " + (CLASE_SITUACION[clave] || ""));
    p.appendChild(el("b", null, n));
    p.appendChild(el("span", null, nombreDe(clave)));
    caja.appendChild(p);
  }
  if (r.documento.nota_de_recuento) {
    caja.appendChild(el("p", "sub", bil(r.documento.nota_de_recuento)));
  }
  if (r.documento.nota_del_cierre) {
    caja.appendChild(el("p", "sub", bil(r.documento.nota_del_cierre)));
  }
  // La nota del cierre la escribe el motor; esta la escribe la pagina y dice
  // lo mismo, porque es la frase que alguien va a buscar en la pantalla
  // cuando vea un ticket cerrado y la no conformidad abierta.
  if (estado.vista === "nc") caja.appendChild(el("p", "sub", t.ejecutada_no_es_cerrada));
  if (estado.vista === "venc" && !(r.documento.a_reobservar || []).length) {
    caja.appendChild(el("p", "sub", t.nada_que_avisar));
  }
}

const FILTROS = ["todas", "hallazgos", "preguntas"];

function pintarFiltro() {
  const t = T(), caja = vaciar($("#filtro"));
  for (const f of FILTROS) {
    const b = el("button", null, t[f]);
    b.setAttribute("aria-pressed", String(estado.filtro === f));
    b.onclick = () => { estado.filtro = f; pintar(); };
    caja.appendChild(b);
  }
}

/* De un documento del motor a las filas de la pantalla.
 *
 * ESTO CONOCIA TRES FORMAS Y EL PANEL PIDE ONCE DOCUMENTOS.
 *
 * Las ocho restantes caian aqui, devolvian cero filas, y lo unico que veia
 * quien las pedia era el volcado de JSON de abajo. El cuestionario son
 * NOVENTA preguntas y salia como cuatrocientos kilobytes de JSON; la
 * declaracion de aplicabilidad, treinta y ocho controles; el Anexo IV,
 * veintitres secciones. Es decir: justo lo que la portada vende, servido
 * crudo.
 *
 * El volcado se queda -- es honesto y dice «si algo de la pantalla no esta
 * aqui dentro, es un defecto de esta pagina» -- pero deja de ser lo unico.
 *
 * Cada adaptador traduce a la MISMA fila que ya usa el plan: clave, titulo,
 * marca y motivo. No inventa ningun dato: si un campo no viene, la fila lo
 * deja vacio en vez de rellenarlo. */
function lineasDe(doc) {
  // GANA LA PRIMERA LISTA CON ALGO DENTRO, NO LA PRIMERA QUE EXISTA.
  //
  // `Array.isArray([])` es cierto, asi que una lista VACIA que aparezca antes
  // en esta cadena tapaba a una llena que viniera despues. Paso de verdad: el
  // documento de la revision por la direccion trae `no_conformidades` vacio y
  // `entradas` con diez, y la pantalla salia con «ninguna linea encaja con
  // este filtro» teniendo diez cosas que ensenar.
  //
  // El orden se queda como desempate para cuando TODAS estan vacias: asi un
  // documento sin datos sigue diciendo que forma tiene.
  const formas = [
    [doc.lineas, deLineaDePlan],
    [doc.no_conformidades, deNoConformidad],
    [doc.veredictos, deVeredicto],
    [doc.preguntas, dePregunta],
    [doc.controles, deControlIso],
    [doc.secciones, deSeccionDeAnexo],
    [doc.entradas, deEntradaDeRevision],
  ];
  for (const [lista, comoFila] of formas) {
    if (Array.isArray(lista) && lista.length) return lista.map(comoFila);
  }
  if (Array.isArray(doc.inspeccionado) && doc.inspeccionado.length) return lineasDeControl(doc);
  return [];
}

function dePregunta(p) {
  // `por_que` es la LISTA de obligaciones a las que sirve la pregunta. Es el
  // dato que hace que este cuestionario no sea otro cuestionario de
  // trescientas preguntas: cada una dice a que ata.
  const ata = (p.por_que || []).map((x) => x.id).filter(Boolean);
  return {
    clave: p.id || "",
    titulo: bil(p.texto) || p.id || "",
    marca: p.estado,
    hallazgos: [],
    preguntas: bil(p.ayuda) ? [{ texto: bil(p.ayuda) }] : [],
    motivo: [p.destinatario, ata.join(" · ")].filter(Boolean).join("  —  "),
  };
}

function deControlIso(c) {
  const e = c.estado_de_implantacion || {};
  return {
    clave: c.control_id || "",
    titulo: bil(c.titulo) || c.control_id || "",
    // `incluido` es un booleano, y la marca del resto de la pantalla es un
    // nombre. Se traduce aqui y no en la hoja de estilo.
    marca: c.incluido === false ? "no_ata" : (e.estado || c.procedencia),
    hallazgos: [],
    preguntas: [],
    motivo: bil(c.justificacion) || "",
  };
}

function deSeccionDeAnexo(s) {
  return {
    clave: s.punto ? s.punto : (s.id || ""),
    titulo: bil(s.titulo) || s.id || "",
    marca: s.procedencia,
    hallazgos: [],
    preguntas: [],
    // Si falta, el motivo de que falte. Es la tercera negativa de la casa
    // puesta en una fila: lo que no se pudo sacar dice por que.
    motivo: bil(s.motivo_ausencia) || (s.de_donde || []).join(", "),
  };
}

function deEntradaDeRevision(e) {
  return {
    clave: (e.clausulas || []).join(" ") || e.entrada || "",
    titulo: bil(e.texto) || e.entrada || "",
    marca: e.situacion,
    hallazgos: [],
    preguntas: [],
    motivo: (e.se_apoya_en || []).join(", "),
  };
}

function lineasDeControl(doc) {
  // El control del articulo 50 no trae una lista de obligaciones: trae lo que
  // MIRO. Enseñarlo es la procedencia, que es media promesa del producto.
  return (doc.inspeccionado || []).map((x) => ({
    clave: doc.control_id || "",
    titulo: String(x),
    marca: doc.resultado,
    hallazgos: [],
    preguntas: [],
    motivo: bil(doc.motivo_indeterminado) || "",
  }));
}

function deLineaDePlan(l) {
  return {
    clave: l.articulo ? "art. " + l.articulo : l.obligacion_id,
    titulo: bil(l.titulo) || l.obligacion_id,
    marca: l.estado,
    hallazgos: (l.hallazgos || []).map((h) => ({
      texto: bil(h.remediacion), donde: h.localizacion, regla: h.regla_id })),
    preguntas: (l.preguntas || []).map((p) => ({ texto: bil(p.texto) || bil(p) })),
    motivo: bil(l.motivo) || bil(l.por_que) || "",
  };
}

function deVeredicto(v) {
  return { clave: v.obligacion_id, titulo: v.regla || v.obligacion_id,
           marca: v.situacion, hallazgos: [], preguntas: [], motivo: "" };
}

function deNoConformidad(n) {
  const t = T(), avisos = [];
  if (n.vencida) avisos.push(t.nc_vencida);
  if (n.estancada) avisos.push(t.nc_estancada);
  if ((n.incoherencias || []).length) avisos.push(t.nc_incoherente);
  return {
    clave: n.id,
    titulo: n.descripcion,
    marca: n.estado,
    hallazgos: (n.incoherencias || []).map((x) => ({ texto: x })),
    preguntas: [],
    motivo: [n.origen, `${n.dias_abierta} ${t.dias}`, ...avisos].filter(Boolean).join(" · "),
  };
}

function filtrarPorTexto() {
  // Filtra lo YA PINTADO y no vuelve a pedir nada.
  //
  // Es deliberado: el documento que se esta mirando es el que emitio el motor,
  // y buscar dentro de el no puede cambiar lo que dice. Si el buscador pidiera
  // otra vez con un criterio, la pantalla estaria componiendo una pregunta que
  // el motor no hizo, y lo que se vería dejaría de ser el documento que hay.
  const q = ($("#buscar").value || "").trim().toLowerCase();
  const filas = [...$("#lineas").children];
  let visibles = 0;
  for (const fila of filas) {
    const casa = !q || (fila.textContent || "").toLowerCase().includes(q);
    fila.hidden = !casa;
    if (casa) visibles++;
  }
  const t = T();
  const cuenta = $("#buscar-cuenta");
  if (!filas.length) { cuenta.textContent = ""; return; }
  // Singular y plural. Decia «1 lineas» en un producto que tiene una puerta
  // para las tildes del castellano.
  const plantilla = !q ? (filas.length === 1 ? t.buscar_una : t.buscar_todas)
    : visibles ? t.buscar_algunas : t.buscar_nada;
  cuenta.textContent = plantilla
    .replace("{n}", String(visibles))
    .replace("{total}", String(filas.length))
    .replace("{q}", q);
}

function pintarLineas() {
  const t = T(), caja = vaciar($("#lineas"));
  const r = estado.documentos[estado.vista];
  if (!r || !r.documento) { caja.appendChild(el("p", "vacio", vacio())); return; }
  let lineas = lineasDe(r.documento);
  if (estado.filtro === "hallazgos") lineas = lineas.filter((l) => l.hallazgos.length);
  if (estado.filtro === "preguntas") lineas = lineas.filter((l) => l.preguntas.length);
  if (!lineas.length) { caja.appendChild(el("p", "vacio", t.sin_lineas)); return; }
  for (const l of lineas) {
    const fila = el("div", "linea");
    fila.appendChild(el("p", "art", l.clave));
    const medio = el("div");
    medio.appendChild(el("h3", null, l.titulo));
    if (l.motivo) medio.appendChild(el("p", "sub", l.motivo));
    for (const [cual, etiqueta] of [["hallazgos", t.remediacion], ["preguntas", t.preguntas]]) {
      if (!l[cual].length) continue;
      const d = el("details", "detalle");
      d.appendChild(el("summary", null, `${etiqueta} (${l[cual].length})`));
      const ul = el("ul");
      for (const x of l[cual]) {
        const li = el("li", null, x.texto);
        if (x.donde) li.appendChild(el("span", "mono", `  ${t.donde}: ${x.donde}`));
        if (x.regla) li.appendChild(el("span", "mono", `  ${t.regla}: ${x.regla}`));
        ul.appendChild(li);
      }
      d.appendChild(ul);
      medio.appendChild(d);
    }
    fila.appendChild(medio);
    fila.appendChild(el("span", "marca " + (CLASE_SITUACION[l.marca] || ""),
                        nombreDe(l.marca)));
    caja.appendChild(fila);
  }
}

function pintarCrudo() {
  const r = estado.documentos[estado.vista];
  $("#crudo").textContent = r ? JSON.stringify(r, null, 2) : "";
  $("#pie-esquema").textContent =
    r && r.documento ? `${T().esquema}: ${r.documento.esquema}` : "";
}

function pintar() {
  pintarTextos();
  pintarCategorias();
  pintarCiclo();
  pintarBotones();
  pintarRecuento();
  pintarFiltro();
  pintarLineas();
  // El filtro se vuelve a aplicar despues de pintar: si no, cambiar de vista
  // con texto en el buscador ensena la lista entera y la cuenta dice otra cosa.
  filtrarPorTexto();
  pintarCrudo();
}

/* --- arranque ------------------------------------------------------------ */

function arrancar() {
  for (const b of $$("#idioma button")) {
    b.onclick = () => {
      estado.idioma = b.dataset.l;
      for (const o of $$("#idioma button")) o.setAttribute("aria-pressed", String(o === b));
      pintar();
    };
  }
  for (const b of $$("#tema button")) {
    b.onclick = () => {
      estado.tema = estado.tema === b.dataset.t ? "" : b.dataset.t;
      document.documentElement.dataset.tema = estado.tema;
      for (const o of $$("#tema button")) {
        o.setAttribute("aria-pressed", String(o.dataset.t === estado.tema));
      }
    };
  }
  $("#conectar").onclick = conectar;
  $("#desconectar").onclick = desconectar;
  $("#enchufe").onclick = () => $("#servidor").focus();
  // Un enganche por cada vista de `RUTAS`, y no una linea por vista escrita a
  // mano. Eran cuatro lineas identicas; con nueve vistas, la novena es la que
  // alguien olvida y el boton no hace nada sin que falle nada.
  for (const vista of Object.keys(RUTAS)) {
    const b = $("#pedir-" + vista);
    if (b) b.onclick = () => traer(vista);
  }
  $("#buscar").oninput = filtrarPorTexto;
  // El servidor se rellena con el ORIGEN DE ESTA PAGINA cuando la sirve uno.
  //
  // La politica de seguridad de contenido que manda el servidor lleva
  // `connect-src 'self'`, que es lo que impide que un script colado en la
  // pagina se mande el expediente del cliente a otro sitio. Es el control
  // correcto y se queda. Lo que estaba mal era la pantalla: ofrecia un campo
  // de texto libre para escribir cualquier servidor mientras el navegador solo
  // dejaba hablar con este, asi que escribir otro daba un error de red sin
  // explicacion y el usuario concluia que el producto no funciona.
  //
  // Abierta como fichero local no hay politica ninguna, y ahi el campo si vale
  // para cualquier servidor. Por eso se rellena solo cuando hay origen.
  if (location.protocol === "http:" || location.protocol === "https:") {
    if (!$("#servidor").value) $("#servidor").value = location.origin;
  }
  $("#fecha").value = new Date().toISOString().slice(0, 10);
  $("#alto_riesgo").value = "";
  pintar();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", arrancar);
} else {
  arrancar();
}
