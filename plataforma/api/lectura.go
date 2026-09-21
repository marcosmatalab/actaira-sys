package api

import (
	"net/http"
	"os"

	"actaira.com/plataforma/cliente"
)

// Los verbos de LECTURA que la consola necesita y la API no exponia.
//
// QUE FALTABA, Y POR QUE SE NOTABA EN LA PANTALLA
// -------------------------------------------------
// El motor tiene diecinueve verbos y esta API exponia cinco. La consecuencia no
// era una limitacion abstracta de la interfaz: era que la pantalla NO PODIA
// ensenar lo que el producto sabe. No habia forma de ver el almacen de
// evidencia ni su cadena, ni el cuestionario con lo que le queda por contestar
// a cada persona, ni la declaracion de aplicabilidad, ni el expediente.
//
// Y esa carencia se leia al reves. Quien abria el panel veia cuatro botones y
// concluia que el producto hace cuatro cosas, cuando lo que pasaba es que la
// API traducia cuatro. Una auditoria externa lo describio como «no hay
// explorador de evidencia, no hay vista de procedencia, no hay tablero»; es
// cierto, y la causa estaba una capa mas abajo de donde se veia.
//
// LA REGLA QUE SE MANTIENE
// -------------------------
// `Rutas` dice, y sigue diciendo: los verbos que EXISTEN y ni uno mas. Cada uno
// de estos es una traduccion 1:1 de un verbo de la linea de mandatos, sin
// logica propia y sin componer nada. Anadir aqui un verbo que el motor no
// tenga, o juntar dos en una respuesta «comoda», seria empezar el segundo motor
// por el sitio mas facil de no notar: el dia que los dos discrepen, el
// expediente que ve el cliente por la pantalla dejaria de ser el que emite el
// motor, y eso es justo lo que este producto vende que no pasa.

// almacen: el estado de la cadena de evidencia.
//
// Es la vista de procedencia que faltaba. Dice si el almacen verifica, cual es
// su cabeza -- lo unico que hay que anclar fuera para detectar una reescritura
// completa -- y cuantas lineas no se puede demostrar que esten intactas.
func (s *Servidor) almacen(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	// Sin ruta de trabajo: el primer positional de este verbo es la accion, y
	// para comprobar una cadena no hace falta el codigo del cliente.
	// SIN `--idioma`: este verbo no lo tiene.
	//
	// Es el tercer manejador de esta tanda que le pasaba al motor una bandera
	// que el verbo no acepta. Los tres compilaban, los tres devolvian 502 y los
	// tres decian «el motor no devolvio un documento que esta plataforma
	// entienda», que es verdad y no sirve para nada. Lo unico que los encontro
	// fue llamar a las rutas contra el motor de verdad.
	//
	// El veredicto de este verbo no lleva prosa traducible: dice si la cadena
	// verifica, cual es la cabeza y cuantas lineas no son demostrables. La unica
	// nota que si esta en los dos idiomas va DENTRO del documento.
	s.correrSinRuta(w, r, c, "almacen", "verificar", "--almacen", c.Almacen())
}

// preguntar: lo que le queda por contestar a una persona, y lo que ya contesto
// el codigo.
//
// Es la bandeja de trabajo. El cuestionario ya restaba lo que los controles
// cubren desde hace siete fases y no habia forma de verlo sin la linea de
// mandatos.
func (s *Servidor) preguntar(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	// NI `--almacen` NI NADA QUE EL VERBO NO TENGA.
	//
	// La primera version le pasaba `--almacen`, que `preguntar` no acepta: la
	// linea de mandatos fallaba por argumento invalido y esta capa lo traducia
	// a «el motor no devolvio un documento que entienda», que es verdad y no
	// dice nada. Es EXACTAMENTE el mismo fallo que ya tenia `noconformidad`, y
	// lo encontro lo mismo que a aquel: probar las rutas contra el motor de
	// verdad en vez de contra un doble. Compilar no es funcionar.
	_, args, ok := s.leerPerfil(w, r)
	if !ok {
		return
	}
	args = append(args, "--idioma", idiomaDe(r))
	args = conRespuestas(args, c)
	s.correr(w, r, c, "preguntar", c.Trabajo(), args...)
}

// soa: la declaracion de aplicabilidad de la ISO 42001, derivada del Reglamento.
//
// Es la vista de auditor: que controles del Anexo A entran, por que obligacion
// entran, y con que evidencia.
func (s *Servidor) soa(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	_, args, ok := s.leerPerfil(w, r)
	if !ok {
		return
	}
	args = append(args, "--idioma", idiomaDe(r))
	args = conRespuestas(args, c)
	s.correr(w, r, c, "soa", c.Trabajo(), args...)
}

// anexo: el expediente tecnico del Anexo IV, o la declaracion UE del Anexo V.
//
// `--cual` viene de la peticion y se valida contra una lista cerrada: es lo
// unico de estos manejadores que toma un parametro del que llama, y un valor
// libre ahi acabaria siendo un argumento de la linea de mandatos.
func (s *Servidor) anexo(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	cual := r.URL.Query().Get("cual")
	if cual == "" {
		cual = "iv"
	}
	if cual != "iv" && cual != "v" {
		fallar(w, http.StatusBadRequest,
			"el anexo es `iv` o `v`, y nada mas",
			"the annex is `iv` or `v`, and nothing else")
		return
	}
	_, args, ok := s.leerPerfil(w, r)
	if !ok {
		return
	}
	args = append(args, "--cual", cual, "--idioma", idiomaDe(r))
	args = conRespuestas(args, c)
	s.correr(w, r, c, "anexo", c.Trabajo(), args...)
}

// revision: la carpeta de entrada de la revision por la direccion (ISO 9.3).
func (s *Servidor) revision(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	s.correrSinRuta(w, r, c, "revision",
		"--almacen", c.Almacen(), "--idioma", idiomaDe(r))
}

// conRespuestas anade `--respuestas` SOLO si el cliente tiene ese fichero.
//
// Pasarlo siempre haria que el motor reventara con «no existe» en cuanto un
// cliente todavia no ha contestado nada, que es el estado de TODOS los clientes
// el primer dia. Y no pasarlo nunca dejaria el cuestionario y la declaracion
// sin lo ya contestado, es decir, ensenando trabajo que ya esta hecho.
func conRespuestas(args []string, c *cliente.Cliente) []string {
	if existe(c.Respuestas()) {
		return append(args, "--respuestas", c.Respuestas())
	}
	return args
}

// existe dice si hay un fichero ahi. Un directorio no cuenta: `--respuestas`
// espera un JSON, y pasarle una carpeta produce un error del motor que esta
// capa traduciria a «el motor no devolvio un documento que entienda», que es
// verdad y no dice nada.
func existe(ruta string) bool {
	info, err := os.Stat(ruta)
	return err == nil && !info.IsDir()
}
