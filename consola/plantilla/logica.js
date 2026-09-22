const DATOS = __DATOS__;
const T = __TEXTOS__;
/* «HOY» ES HOY, Y NO EL DIA EN QUE SE CONSTRUYO ESTA PAGINA.
 *
 * Aqui habia una fecha escrita, y el boton de la barra lateral -- el que dice
 * «Hoy», «Today», «Heute» -- la llevaba tambien escrita en su `data-f`. Asi que
 * la pantalla que contesta «que te ata HOY» contestaba con el calendario del
 * dia en que alguien corrio `make consola`, y se iba separando de la realidad
 * un dia por cada dia. No es cosmetico: la regla de aplicabilidad compara la
 * fecha con la de entrada en vigor de cada obligacion, asi que una obligacion
 * que ya ata sale como «futura» hasta que alguien vuelva a construir la pagina.
 *
 * Se lee del reloj del navegador y NO se inyecta al construir, que era la otra
 * salida: inyectarla haria que dos maquinas sanas produjeran dos ficheros
 * distintos el mismo dia siguiente, y la reproducibilidad de esta pagina es una
 * puerta de la suite.
 *
 * Y se compone con el calendario LOCAL en vez de recortar un `toISOString`, que
 * es UTC: en Espana, entre medianoche y las dos de la manana, «hoy» habria sido
 * ayer. */
const HOY = (d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
                  + `-${String(d.getDate()).padStart(2, "0")}`)(new Date());
let idioma = "es", fecha = HOY, abierta = null, vista = "aplica", filtro = "todos";

/* EL IDIOMA DE LA INTERFAZ NO ES EL DEL CATALOGO, Y NO PUEDE SERLO.
 *
 * Esta pagina habla seis idiomas. El CATALOGO -- los titulos de las
 * obligaciones, los de los controles del Anexo A, el texto de cada pregunta y
 * su ayuda -- esta en dos, `es` y `en`, porque es contenido normativo y lo
 * escribe una persona. Traducirlo a maquina seria exactamente lo que la
 * segunda negativa de esta casa prohibe, y ademas es texto que va a un
 * auditor.
 *
 * Si se hubieran atado, poner la interfaz en frances habria escrito
 * `undefined` en cada titulo de la tabla: `titulo["fr"]` no existe. Peor que
 * vacio, porque vacio se nota y `undefined` parece un dato.
 *
 * Asi que el catalogo se lee en el idioma de la interfaz cuando existe, y en
 * ingles cuando no. Y la pagina lo DICE. */
const IDIOMAS_DEL_CATALOGO = ["es", "en"];
const idiomaCat = () =>
  IDIOMAS_DEL_CATALOGO.indexOf(idioma) === -1 ? "en" : idioma;
/* Las respuestas viven SOLO en memoria. Nada de almacenamiento del navegador:
   son declaraciones con nombre y cargo dentro, y lo que aqui se guardara se
   quedaria en el disco de quien abriera la pagina despues. Salen por descarga,
   que es una decision explicita de la persona. */
let respuestas = {}, firmante = {nombre: "", cargo: ""};
let roles = new Set(["proveedor"]);
let perfil = Object.fromEntries([...DATOS.campos_decisivos, ...DATOS.exclusiones].map(c => [c, null]));
/* Por donde el sistema es de alto riesgo. No es un campo de tres estados como
   los demas: es una eleccion entre dos vias, y desde el Reglamento (UE)
   2026/1744 decide OCHO MESES de plazo. Vive aparte a proposito, para que se
   vea que no es una pregunta mas del cuestionario de alcance. */
perfil.via_anexo = null;

/* La fecha de una obligacion, con el calendario partido. Escrita una vez aqui
   y una vez en `tabla.py`, y `test_la_tabla_reproduce_al_motor` compara las dos
   en 2.430 combinaciones: si discrepan, la pantalla diria una fecha y el
   expediente otra. La via SOLO se le pide a quien ha dicho que si es de alto
   riesgo: al que ha dicho que no, preguntarle por cual de las dos maneras de
   serlo le aplica no tiene respuesta. */
function desdeDe(o){
  const porVia = o.aplica_desde_por_via;
  if (!porVia) return o.aplica_desde;
  if (perfil.es_alto_riesgo === true){
    if (perfil.via_anexo === null) return null;
    return porVia[perfil.via_anexo] || o.aplica_desde;
  }
  return Object.values(porVia).sort()[0];
}

/* LA REGLA GENERICA. No nombra ni un alcance: los lee de la tabla que emite el
   motor. `motor/tests/test_tabla.py` comprueba que esto y `resolver()` de
   Python coinciden en las 810 combinaciones que esta pantalla puede producir. */
function resolver(){
  const hoy = fecha, out = {};
  for (const o of DATOS.obligaciones){
    /* Exclusiones de ambito del articulo 2, antes que todo lo demas. La misma
       definicion que `_excluido` en Python, y `test_la_tabla_reproduce_al_motor`
       compara las dos en 3.240 combinaciones. */
    if (perfil.fines_militares === true || perfil.solo_investigacion === true){ out[o.id] = "no_ata"; continue; }
    if (perfil.es_codigo_abierto === true && !DATOS.sobreviven_al_codigo_abierto.includes(o.id)
        && perfil.es_alto_riesgo === false){ out[o.id] = "no_ata"; continue; }
    if (roles.size === 0){ out[o.id] = "indeterminada"; continue; }
    if (![...roles].some(r => o.roles.includes(r))){ out[o.id] = "no_ata"; continue; }
    const campos = DATOS.alcances[o.alcance] || [];
    const valores = campos.map(c => perfil[c]);
    if (valores.some(v => v === null)){ out[o.id] = "indeterminada"; continue; }
    if (!valores.every(Boolean)){ out[o.id] = "no_ata"; continue; }
    const desde = desdeDe(o);
    if (desde === null){ out[o.id] = "indeterminada"; continue; }
    out[o.id] = hoy >= desde ? "ata" : "futura";
  }
  return out;
}
function reglaDe(o, s){
  const t = T[idioma], campos = DATOS.alcances[o.alcance] || [];
  if (perfil.fines_militares === true) return t.reglas.exc_militar;
  if (perfil.solo_investigacion === true) return t.reglas.exc_investigacion;
  if (perfil.es_codigo_abierto === true && !DATOS.sobreviven_al_codigo_abierto.includes(o.id)
      && perfil.es_alto_riesgo === false) return t.reglas.exc_abierto;
  if (s === "no_ata" && ![...roles].some(r => o.roles.includes(r)))
    return t.reglas.rol.replace("{ata}", o.roles.join(", ")).replace("{perfil}", [...roles].join(", "));
  if (s === "indeterminada"){
    const faltan = campos.filter(c => perfil[c] === null);
    if (faltan.length) return t.reglas.alcance_sin_resolver.replace("{campos}", faltan.join(", "));
    if (desdeDe(o) === null) return t.reglas.sin_via;
    return t.reglas.sin_rol;
  }
  if (s === "no_ata") return t.reglas.fuera_de_alcance.replace("{alcance}", o.alcance);
  return (s === "ata" ? t.reglas.vigente : t.reglas.futura)
    .replace("{desde}", desdeDe(o) || o.aplica_desde).replace("{fecha}", fecha);
}
function faltantes(){
  const necesarios = new Set();
  for (const o of DATOS.obligaciones){
    if (roles.size && ![...roles].some(r => o.roles.includes(r))) continue;
    for (const c of (DATOS.alcances[o.alcance] || [])) if (perfil[c] === null) necesarios.add(c);
  }
  return [...necesarios];
}
const esc = s => String(s).replace(/[&<>"]/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));

function pintar(){
  const t = T[idioma];
  document.getElementById("titular").textContent = t.titular;
  document.getElementById("entradilla").textContent = t.entradilla;
  document.getElementById("lb-perfil").textContent = t.perfil;
  document.getElementById("lb-roles").textContent = t.roles;
  document.getElementById("lb-fecha").textContent = t.fecha;
  document.getElementById("lb-fecha-corta").textContent = fecha;
  document.getElementById("cat-t").textContent = t.cat_t;
  document.getElementById("cat-p").textContent = t.cat_p;
  document.getElementById("th-id").textContent = t.th_id;
  document.getElementById("th-tit").textContent = t.th_tit;
  document.getElementById("th-niv").textContent = t.th_niv;
  document.getElementById("th-cruce").textContent = t.th_cruce;
  document.getElementById("pie").textContent = t.pie;
  const bf = document.querySelectorAll("#fecha button");
  bf[0].textContent = t.hoy; bf[1].textContent = t.dic27;
  // El boton «Hoy» apunta a hoy. Su `data-f` venia escrito en la plantilla con
  // la fecha de construccion, asi que pulsarlo te llevaba a un dia del pasado.
  bf[0].dataset.f = HOY;
  document.querySelectorAll("#vistas button").forEach(b => {
    b.textContent = t["v_" + b.dataset.v];
  });

  document.getElementById("ciclo").innerHTML = t.pasos.map((p,i)=>
    `<div class="paso" data-estado="${i===0?"ahora":(i<0?"hecho":"")}"><div class="n">0${i+1}</div><div class="t">${esc(p)}</div></div>`).join("");

  document.getElementById("roles").innerHTML = Object.keys(t.roles_n).map(r =>
    `<button class="rol" data-r="${r}" aria-pressed="${roles.has(r)}">${esc(t.roles_n[r])}</button>`).join("");

  const tri = c => `
    <div class="campo"><span class="pregunta">${esc(t.preguntas[c])}</span>
      <div class="tri" data-c="${c}">
        <button data-v="true"  aria-pressed="${perfil[c]===true}">${esc(t.si)}</button>
        <button data-v="false" aria-pressed="${perfil[c]===false}">${esc(t.no)}</button>
        <button data-v="null"  aria-pressed="${perfil[c]===null}">${esc(t.nulo)}</button>
      </div></div>`;
  document.getElementById("exclusiones").innerHTML =
    `<p class="eyebrow" style="margin-bottom:10px">${esc(t.exc_t)}</p>` + DATOS.exclusiones.map(tri).join("");
  document.getElementById("preguntas").innerHTML = DATOS.campos_decisivos.map(c => `
    <div class="campo"><span class="pregunta">${esc(t.preguntas[c])}</span>
      <div class="tri" data-c="${c}">
        <button data-v="true"  aria-pressed="${perfil[c]===true}">${esc(t.si)}</button>
        <button data-v="false" aria-pressed="${perfil[c]===false}">${esc(t.no)}</button>
        <button data-v="null"  aria-pressed="${perfil[c]===null}">${esc(t.nulo)}</button>
      </div></div>`).join("");

  const res = resolver();
  const cuenta = {ata:0,futura:0,no_ata:0,indeterminada:0};
  for (const k in res) cuenta[res[k]]++;
  document.getElementById("recuento").innerHTML = ["ata","indeterminada","futura","no_ata"].map(s =>
    `<div class="cifra" data-s="${s}"><b>${cuenta[s]}</b><span>${esc(t[s])}</span></div>`).join("");

  const f = faltantes();
  document.getElementById("aviso").innerHTML = (roles.size === 0)
    ? `<div class="aviso"><h3>${esc(t.faltan_t)}</h3><p>${esc(t.sin_rol)}</p></div>`
    : (f.length ? `<div class="aviso"><h3>${esc(t.faltan_t)}</h3><p>${esc(t.faltan_p)}</p><ul>${
        f.map(c=>`<li>${esc(t.preguntas[c])}</li>`).join("")}</ul></div>` : "");

  const orden = {ata:0, indeterminada:1, futura:2, no_ata:3};
  const obls = [...DATOS.obligaciones].sort((a,b)=>
    (orden[res[a.id]] - orden[res[b.id]]) || (parseInt(a.articulo) - parseInt(b.articulo)));
  document.getElementById("lista").innerHTML = obls.map(o => `
    <button class="fila" data-id="${o.id}">
      <span class="art">Art. ${esc(o.articulo)}</span>
      <span><span class="tit">${esc(o.titulo[idiomaCat()])}</span>
        <span class="meta">${esc(t.niveles[o.nivel])}${o.iso42001.length?" · "+o.iso42001.join(" "):""}</span></span>
      <span class="pill" data-s="${res[o.id]}">${esc(t[res[o.id]])}</span>
    </button>`).join("");

  document.getElementById("tbody-iso").innerHTML = DATOS.controles_iso.map(c => `
    <tr><td class="mono">${esc(c.id)}</td><td>${esc(c.titulo[idiomaCat()])}</td>
    <td><span class="pill nivel">${esc(t.niveles[c.nivel])}</span></td>
    <td class="mono">${c.aiact.map(a=>"Art. "+a.replace("AIA-","").replace(/^0+/,"")).join(", ")||"—"}</td></tr>`).join("");

  if (abierta) pintarDetalle(abierta, res);
  pintarCuestionario();
  pintarSoa(res);
  /* Y LA VISTA QUE HAY ABIERTA SE QUEDA ABIERTA.

     Cada sitio que repinta llevaba pegada una llamada que forzaba la primera
     pantalla, asi que responder una pregunta, cambiar de idioma, mover la
     fecha o tocar un rol te echaba del cuestionario o de la declaracion de
     aplicabilidad. No se veia porque los ids repetidos hacian que la
     conmutacion no conmutara nada: arreglado aquello, el salto quedo a la
     vista. Se sincroniza aqui, UNA vez, en vez de en cinco sitios. */
  cambiarVista(vista);
}

/* --- la vista del cuestionario ---------------------------------------- */

function admisible(q, v){
  /* La MISMA forma que `declaracion.admisible` en Python, y por la misma razon
     que la regla de aplicabilidad: si las dos discrepan, el cliente contesta
     aqui algo que el motor rechaza luego, que es la peor manera de enterarse.
     `test_la_consola_admite_lo_mismo_que_el_motor` compara las dos. */
  const ex = q.exige || {};
  if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) return "vacia";
  const largo = Array.isArray(v) ? v.reduce((a,x)=>a+String(x).trim().length,0) : String(v).trim().length;
  if (ex.minimo_caracteres && largo < ex.minimo_caracteres) return "corta";
  if (ex.minimo_elementos && Array.isArray(v) && v.length < ex.minimo_elementos) return "corta";
  if (ex.excluyente && Array.isArray(v) && v.includes(ex.excluyente) && v.length > 1) return "corta";
  return "ok";
}

function estadoPregunta(q){
  if (q.si){
    const otra = respuestas[q.si.pregunta];
    if (otra === undefined) return "espera";
    const lista = Array.isArray(otra) ? otra : [otra];
    if ("vale" in q.si && !lista.includes(q.si.vale)) return "no_procede";
    if ("contiene" in q.si && !lista.includes(q.si.contiene)) return "no_procede";
    if ("distinto_de" in q.si && !lista.some(x => x !== q.si.distinto_de)) return "no_procede";
  }
  const v = respuestas[q.id];
  if (v === undefined) return q.salta_si_cubre.length ? "salta" : "pendiente";
  return admisible(q, v) === "ok" ? "contestada" : "corta";
}

function pintarCuestionario(){
  const t = T[idioma];
  for (const [id, k] of [["q-t","q_t"],["q-p","q_p"],["q-descarga-p","q_descarga_p"],
                         ["lb-q-nombre","q_nombre"],["lb-q-cargo","q_cargo"]])
    document.getElementById(id).textContent = t[k];
  document.getElementById("q-descargar").textContent = t.q_descargar;
  document.getElementById("q-nombre").placeholder = t.q_nombre;
  document.getElementById("q-cargo").placeholder = t.q_cargo;

  const dests = ["todos", ...Object.keys(t.q_dest_n)];
  document.getElementById("q-filtro").innerHTML = dests.map(d =>
    `<button data-q="${d}" aria-pressed="${filtro===d}">${esc(d==="todos"?t.q_todos:t.q_dest_n[d])}</button>`
  ).join("");

  const estados = DATOS.preguntas.map(estadoPregunta);
  const cuenta = {contestada:0, pendiente:0, espera:0, salta:0, corta:0, no_procede:0};
  estados.forEach(e => cuenta[e]++);
  document.getElementById("q-recuento").innerHTML = [
    ["contestada", t.q_contestadas], ["pendiente", t.q_pendientes],
    ["espera", t.q_espera], ["salta", t.q_ahorro_t]
  ].map(([k, lb]) => `<div class="cifra" data-s="${k==="contestada"?"ata":k==="salta"?"futura":"indeterminada"}">
      <b>${cuenta[k]}</b><span>${esc(lb)}</span></div>`).join("");

  const vis = DATOS.preguntas.filter((q,i) =>
    (filtro === "todos" || q.destinatario === filtro) && estados[i] !== "no_procede");
  document.getElementById("q-lista").innerHTML = vis.map(q => {
    const e = estadoPregunta(q), v = respuestas[q.id];
    const refs = q.por_que.map(r =>
      `<span class="ref" data-m="${r.marco}">${esc(r.referencia[idiomaCat()])}</span>`).join("");
    let campo;
    if (q.formato === "si_no" || q.formato === "eleccion"){
      const ops = q.formato === "si_no"
        ? [{valor:"true", es:t.si, en:t.si}, {valor:"false", es:t.no, en:t.no}]
        : q.opciones;
      const multi = q.formato === "eleccion";
      campo = `<div class="opciones">` + ops.map(o => {
        const marcado = multi ? (Array.isArray(v) && v.includes(o.valor)) : String(v) === o.valor;
        return `<label><input type="${multi?"checkbox":"radio"}" name="n-${q.id}"
          data-q="${q.id}" data-o="${esc(o.valor)}" ${marcado?"checked":""}>
          <span>${esc(o[idiomaCat()] !== undefined ? o[idiomaCat()] : o.valor)}</span></label>`;
      }).join("") + `</div>`;
    } else if (q.formato === "texto_largo" || q.formato === "lista" || q.formato === "persona"){
      campo = `<textarea rows="3" data-q="${q.id}">${esc(v === undefined ? "" : (Array.isArray(v)?v.join("\n"):v))}</textarea>`;
    } else {
      campo = `<input type="text" data-q="${q.id}" value="${esc(v === undefined ? "" : v)}">`;
    }
    const falta = e === "corta" && (q.exige||{}).minimo_caracteres
      ? `<span class="mal">${esc(t.q_corta)}: ${(q.exige.minimo_caracteres)}</span>` : "";
    return `<div class="q" data-e="${e}">
      <span class="qid">${esc(q.id)} · ${esc(t.q_dest_n[q.destinatario])}</span>
      <h4>${esc(q.texto[idiomaCat()])}</h4>
      <div class="porque">${refs}</div>
      <p class="ayuda">${esc(q.ayuda[idiomaCat()])}</p>
      ${campo}
      <div class="pie2">
        <span>${esc(t.q_vigencia)} ${q.vigencia_dias} ${esc(t.q_dias)}</span>
        ${q.salta_si_cubre.length?`<span>${esc(t.q_salta)}: ${q.salta_si_cubre.join(", ")}</span>`:""}
        ${e==="espera"?`<span>${esc(t.q_espera)}: ${esc(q.si.pregunta)}</span>`:""}
        ${falta}
      </div></div>`;
  }).join("");

  const listo = firmante.nombre.trim() && firmante.cargo.trim() && Object.keys(respuestas).length;
  const bd = document.getElementById("q-descargar");
  bd.disabled = !listo;
  bd.title = listo ? "" : t.q_sin_firma;
}

/* La descarga tiene DOS caminos y los dos hacen falta.

   La pagina se entrega de dos maneras: como fichero que se abre con el
   navegador (lo que produce `make consola`) y publicada como artefacto en
   claude.ai. En el artefacto, un enlace `blob:` con `download` no baja nada:
   el visor no le da permiso de descarga a la pagina, y el boton pareceria
   funcionar y no haria NADA, que es el peor fallo de los dos posibles.

   Asi que si el visor ofrece `claude.use("downloads")`, se usa; si no lo
   ofrece -- porque la pagina es un fichero local -- se cae al enlace, que ahi
   si funciona. La rama que no existe nunca se ejecuta. */
async function descargarRespuestas(){
  const ahora = new Date().toISOString().replace(/\.\d+Z$/, "+00:00");
  const salida = {respuestas: Object.keys(respuestas).map(id => ({
    pregunta: id, valor: respuestas[id],
    quien: firmante.nombre.trim(), cargo: firmante.cargo.trim(), cuando: ahora
  }))};
  const texto = JSON.stringify(salida, null, 2);
  let guardado = null;
  try {
    guardado = (typeof claude !== "undefined" && claude.use)
      ? await claude.use("downloads") : null;
  } catch (e) { guardado = null; }
  if (guardado){
    try { await guardado.save({filename: "respuestas.json", data: texto}); }
    catch (e) { /* el visor dijo que no, o no se puede: no se insiste */ }
    return;
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([texto], {type:"application/json"}));
  a.download = "respuestas.json"; a.click(); URL.revokeObjectURL(a.href);
}

/* --- la declaracion de aplicabilidad ----------------------------------- */

function pintarSoa(res){
  const t = T[idioma];
  for (const [id, k] of [["soa-t","soa_t"],["soa-p","soa_p"],["cl-t","cl_t"],["cl-p","cl_p"],
                         ["soa-th-ctrl","soa_th_ctrl"],["soa-th-entra","soa_th_entra"],
                         ["soa-th-proc","soa_th_proc"],["soa-th-just","soa_th_just"],
                         ["cl-th-id","cl_th_id"],["cl-th-tit","cl_th_tit"],
                         ["cl-th-doc","cl_th_doc"],["cl-th-prod","cl_th_prod"]])
    document.getElementById(id).textContent = t[k];
  document.getElementById("soa-notas").innerHTML =
    `<p>${esc(t.soa_nota)}</p><p>${esc(t.soa_herencia)}</p>`;

  /* La MISMA regla que `inclusion_en_la_soa` en Python, que es donde esta
     escrita. `test_la_soa_reproduce_a_la_tabla` compara las dos en todas las
     combinaciones de perfil que esta pantalla puede producir. */
  const clasificar = ids => {
    const dentro = ids.filter(o => res[o] === "ata" || res[o] === "futura");
    if (dentro.length) return ["derivada", dentro];
    const dudosas = ids.filter(o => res[o] === "indeterminada");
    if (dudosas.length) return ["derivada_sin_resolver", dudosas];
    return ["pendiente_de_justificar", []];
  };
  const arts = ids => ids.map(o =>
    (idioma === "es" ? "art. " : "Art. ") +
    (DATOS.obligaciones.find(x => x.id === o) || {articulo:o}).articulo).join(", ");

  const filas = DATOS.controles_iso.map(c => {
    const [proc, sostienen] = clasificar(c.aiact);
    const just = proc === "derivada" ? t.soa_just_der.replace("{arts}", arts(sostienen))
              : proc === "derivada_sin_resolver" ? t.soa_just_dud.replace("{arts}", arts(sostienen))
              : t.soa_just_pen;
    return {c, proc, just};
  });
  const n = p => filas.filter(f => f.proc === p).length;
  document.getElementById("soa-recuento").innerHTML = [
    ["ata", n("derivada"), t.soa_incluidos],
    ["indeterminada", n("derivada_sin_resolver"), t.soa_dudosos],
    ["no_ata", n("pendiente_de_justificar"), t.soa_pendientes]
  ].map(([s, v, lb]) => `<div class="cifra" data-s="${s}"><b>${v}</b><span>${esc(lb)}</span></div>`).join("");

  document.getElementById("tbody-soa").innerHTML = filas.map(({c, proc, just}) => `
    <tr><td class="mono">${esc(c.id)}<br><span class="just">${esc(c.titulo[idiomaCat()])}</span></td>
      <td><span class="pill" data-s="${proc==="pendiente_de_justificar"?"indeterminada":"ata"}">${
        esc(proc==="pendiente_de_justificar"?t.soa_pordecidir:t.soa_si)}</span></td>
      <td>${esc(t.soa_proc[proc])}</td>
      <td class="just">${esc(just)}</td></tr>`).join("");

  document.getElementById("tbody-cl").innerHTML = DATOS.clausulas.map(c => `
    <tr><td class="mono">${esc(c.clausula)}</td><td>${esc(c.titulo[idiomaCat()])}</td>
      <td>${c.exige_informacion_documentada ? esc(t.cl_si) : esc(t.cl_no)}</td>
      <td class="mono">${c.produce ? esc(c.produce) : esc(t.cl_no)}</td></tr>`).join("");
}

/* Los PANELES se llaman `p-...` y las PESTANAS `v-...`, y no es cosmetica.
   Los dos llevaban el mismo id, asi que `getElementById("v-"+x)` devolvia el
   primero del documento -- el boton -- y esta funcion escondia las pestanas en
   vez de los paneles: al cargar quedaba una sola pestana visible y las otras
   dos vistas no se podian alcanzar nunca. Ver el comentario de `pagina.html`. */
function cambiarVista(v){
  vista = v;
  for (const x of ["aplica", "pregunta", "soa"])
    document.getElementById("p-" + x).classList.toggle("oculto", x !== v);
  document.querySelectorAll("#vistas button").forEach(b =>
    b.setAttribute("aria-selected", b.dataset.v === v));
}

function pintarDetalle(id, res){
  const t = T[idioma], o = DATOS.obligaciones.find(x => x.id === id);
  if (!o){ document.getElementById("detalle").innerHTML = ""; return; }
  const s = (res || resolver())[id];
  document.getElementById("detalle").innerHTML = `
    <div class="detalle" role="dialog" aria-label="${esc(o.titulo[idiomaCat()])}">
      <button class="cerrar" id="cerrar">${esc(t.cerrar)}</button>
      <p class="eyebrow">Art. ${esc(o.articulo)} · ${esc(o.id)}</p>
      <h3>${esc(o.titulo[idiomaCat()])}</h3>
      <span class="pill" data-s="${s}">${esc(t[s])}</span>
      <div class="regla">${esc(reglaDe(o, s))}</div>
      <dl>
        <dt>${esc(t.det_nivel)}</dt><dd>${esc(t.niveles[o.nivel])}</dd>
        <dt>${esc(t.det_desde)}</dt><dd>${esc(desdeDe(o) || o.aplica_desde)}</dd>
        <dt>${esc(t.det_roles)}</dt><dd>${o.roles.map(r=>esc(t.roles_n[r]||r)).join(", ")}</dd>
        ${o.comprueba.length ? `<dt>${esc(t.det_comprueba)}</dt><dd>${o.comprueba.map(c=>`<code>${esc(c)}</code>`).join(" ")}</dd>` : ""}
        ${o.iso42001.length ? `<dt>${esc(t.det_iso)}</dt><dd>${o.iso42001.map(i=>esc(i)+" "+esc((DATOS.controles_iso.find(c=>c.id===i)||{titulo:{}}).titulo[idiomaCat()]||"")).join("<br>")}</dd>` : ""}
      </dl></div>`;
  document.getElementById("cerrar").onclick = () => { abierta = null; document.getElementById("detalle").innerHTML = ""; };
}

document.addEventListener("input", e => {
  const el = e.target;
  if (el.id === "q-nombre"){ firmante.nombre = el.value; pintarBoton(); return; }
  if (el.id === "q-cargo"){ firmante.cargo = el.value; pintarBoton(); return; }
  if (!el.dataset.q) return;
  const q = DATOS.preguntas.find(x => x.id === el.dataset.q);
  if (!q) return;
  if (el.tagName === "TEXTAREA"){
    const v = el.value;
    if (v.trim() === "") delete respuestas[q.id];
    else respuestas[q.id] = (q.formato === "lista" || q.formato === "persona")
      ? v.split("\n").map(x => x.trim()).filter(Boolean) : v;
  } else if (el.type === "text"){
    if (el.value.trim() === "") delete respuestas[q.id]; else respuestas[q.id] = el.value;
  }
  pintarBoton();
});

/* Solo el boton, no la lista entera: repintar mientras alguien escribe le
   quitaria el foco al campo en cada tecla. */
function pintarBoton(){
  const b = document.getElementById("q-descargar");
  b.disabled = !(firmante.nombre.trim() && firmante.cargo.trim() && Object.keys(respuestas).length);
}

document.addEventListener("change", e => {
  const el = e.target;
  if (!el.dataset.q || !el.dataset.o) return;
  const q = DATOS.preguntas.find(x => x.id === el.dataset.q);
  if (!q) return;
  if (el.type === "radio"){
    respuestas[q.id] = q.formato === "si_no" ? el.dataset.o === "true" : el.dataset.o;
  } else {
    const previo = Array.isArray(respuestas[q.id]) ? respuestas[q.id] : [];
    respuestas[q.id] = el.checked ? [...previo, el.dataset.o] : previo.filter(x => x !== el.dataset.o);
    if (!respuestas[q.id].length) delete respuestas[q.id];
  }
  pintar();
});

document.addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.id === "q-descargar"){ descargarRespuestas(); return; }
  if (b.dataset.v && b.parentElement.id === "vistas"){ cambiarVista(b.dataset.v); return; }
  if (b.dataset.q !== undefined && b.parentElement.id === "q-filtro"){
    filtro = b.dataset.q; pintarCuestionario(); return; }
  if (b.dataset.l){ idioma = b.dataset.l; document.querySelectorAll("#idioma button").forEach(x=>x.setAttribute("aria-pressed", x.dataset.l===idioma)); pintar(); }
  else if (b.dataset.t){ document.documentElement.dataset.theme = b.dataset.t; document.querySelectorAll("#tema button").forEach(x=>x.setAttribute("aria-pressed", x.dataset.t===b.dataset.t)); }
  else if (b.dataset.f){ fecha = b.dataset.f; document.querySelectorAll("#fecha button").forEach(x=>x.setAttribute("aria-pressed", x.dataset.f===fecha)); pintar(); }
  else if (b.dataset.r){ roles.has(b.dataset.r) ? roles.delete(b.dataset.r) : roles.add(b.dataset.r); pintar(); }
  else if (b.dataset.v !== undefined && b.parentElement.dataset.c){
    const c = b.parentElement.dataset.c;
    perfil[c] = b.dataset.v === "null" ? null : b.dataset.v === "true";
    pintar();
  }
  else if (b.classList.contains("fila")){ abierta = b.dataset.id; pintarDetalle(abierta); }
});
pintar();
