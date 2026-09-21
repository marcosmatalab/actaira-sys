// Package api es el transporte, y nada mas.
//
// # LA REGLA DE ESTE PAQUETE ES UNA NEGATIVA
//
// La API traduce transporte, nunca significado. Ninguna ruta calcula un
// veredicto, ninguna resume, ninguna decide que un documento «esta bien». Lo
// que sale por HTTP es el documento que emitio el motor, con su campo `esquema`
// dentro y sin una coma de diferencia.
//
// La razon no es purismo. En cuanto la API pueda producir una conclusion que
// la linea de mandatos no produce, hay DOS motores: el que se audita y el que
// contesta al frontend. A partir de ahi, un cliente que reproduce el analisis
// en su maquina obtiene algo distinto de lo que ve en la pantalla, y la unica
// propiedad que hace verificable a este producto -que cualquiera pueda repetir
// lo que se afirma- se pierde en la capa mas tonta de todas.
//
// LO QUE SE DECIDE AQUI, Y SON CUATRO COSAS
//
//  1. **El codigo de salida NO es un estado HTTP.** Tres significa «falta algo
//     por contestar o hay trabajo que hacer», que es el estado NORMAL de un
//     cliente que empieza. Devolverlo como 4xx haria que un panel pintara en
//     rojo a todo el mundo el primer dia, y que un reintentador automatico
//     repitiera un analisis que salio perfectamente. Sale 200 con el codigo
//     dentro del cuerpo.
//
//  2. **Sin credenciales configuradas no se arranca.** No hay modo abierto
//     «para desarrollo»: un servidor que ejecuta procesos y lee expedientes de
//     varios clientes no puede tener un estado por defecto permisivo, porque
//     ese estado por defecto acaba en produccion un viernes.
//
//  3. **Un cliente no ve a otro, y se comprueba con rutas resueltas.** El
//     aislamiento ya vive en `cliente` y en `motor`; aqui no se reimplementa,
//     se usa. Dos implementaciones de la misma barrera se anulan.
//
//  4. **Los dos idiomas.** No como cortesia: un expediente pedido en ingles
//     con motivos en castellano dentro es lo que ya se corrigio en las senales
//     y en los formularios, y volveria por aqui si la API eligiera idioma por
//     su cuenta.
package api

import (
	"crypto/subtle"
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"actaira.com/plataforma/cliente"
	"actaira.com/plataforma/motor"
	"actaira.com/plataforma/vencimientos"
)

// Esquema del sobre. El cuerpo del motor viaja DENTRO, sin tocar.
const Esquema = "actaira/api/v1"

// ErrSinCredenciales se devuelve al construir el servidor sin un almacen de
// credenciales. Es un error de arranque y no una advertencia a proposito.
var ErrSinCredenciales = errors.New(
	"no hay credenciales configuradas: este servidor ejecuta procesos y lee expedientes " +
		"de varios clientes, asi que no tiene modo abierto")

// Credenciales asocia un token con el cliente que puede tocar. Se carga de un
// fichero que controla quien opera, y NUNCA se escribe desde aqui.
type Credenciales struct{ porToken map[string]string }

// CargarCredenciales lee un JSON {"token":"id-de-cliente"}.
//
// El fichero tiene que tener permisos de solo-dueno. Comprobarlo al arrancar
// -y negarse- evita el caso que de verdad pasa: alguien copia el fichero a un
// servidor, se le queda 0644, y nadie vuelve a mirarlo nunca.
func CargarCredenciales(ruta string) (*Credenciales, error) {
	if err := soloLoLeeSuDueno(ruta); err != nil {
		return nil, fmt.Errorf("credenciales: %w", err)
	}
	crudo, err := os.ReadFile(ruta)
	if err != nil {
		return nil, fmt.Errorf("credenciales: %w", err)
	}
	var m map[string]string
	if err := json.Unmarshal(crudo, &m); err != nil {
		return nil, fmt.Errorf("credenciales: %w", err)
	}
	if len(m) == 0 {
		return nil, ErrSinCredenciales
	}
	for token, id := range m {
		if len(token) < 24 {
			return nil, fmt.Errorf(
				"credenciales: el token de %q tiene %d caracteres. Menos de 24 se adivina, y "+
					"aqui no se avisa: no se arranca", id, len(token))
		}
	}
	return &Credenciales{porToken: m}, nil
}

// DeMapa construye credenciales en memoria. Para pruebas y para quien las
// gestione en otro sitio.
func DeMapa(m map[string]string) (*Credenciales, error) {
	if len(m) == 0 {
		return nil, ErrSinCredenciales
	}
	copia := make(map[string]string, len(m))
	for k, v := range m {
		copia[k] = v
	}
	return &Credenciales{porToken: copia}, nil
}

// Cliente devuelve el identificador que ese token puede tocar.
//
// La comparacion es de tiempo constante y se recorre el mapa ENTERO aunque ya
// se haya encontrado: salir antes filtra, por el reloj, cuantos tokens
// comparten prefijo con el que se prueba.
func (c *Credenciales) Cliente(token string) (string, bool) {
	encontrado, ok := "", false
	for k, v := range c.porToken {
		if subtle.ConstantTimeCompare([]byte(k), []byte(token)) == 1 {
			encontrado, ok = v, true
		}
	}
	return encontrado, ok
}

// Servidor sirve los verbos del motor por HTTP. Un valor cero no sirve.
type Servidor struct {
	motor   *motor.Motor
	espacio *cliente.Espacio
	revisor *vencimientos.Revisor

	// Vigilancia es el planificador que corre por su cuenta, si lo hay.
	//
	// Se publica para que `/salud` pueda decir si la vigilancia esta viva y
	// cuantas pasadas lleva, en vez de que alguien lo suponga. Un servicio que
	// contesta «vivo: true» mientras su unica tarea de fondo esta parada es un
	// estado de salud que miente, y es exactamente lo que habia: el campo
	// `revisor` se guardaba y no se leia en ningun sitio.
	Vigilancia *vencimientos.Planificador

	// Topes es cuantos verbos del motor pueden correr a la vez, en la maquina
	// y por cliente. Ver `guardas.go`: un verbo del motor es un PROCESO que lee
	// el repositorio entero, y no habia nada que limitara cuantos hay a la vez.
	Topes Tope

	limitador *limitador
	ritmo     *ritmo

	// Emisor es el proveedor de identidad, si esta configurado.
	//
	// DOS MODOS, Y SE DICE CUAL ESTA PUESTO. Con emisor, quien llama trae un
	// testigo firmado por el proveedor y de ahi salen el cliente y los roles.
	// Sin emisor, se usan las credenciales estaticas: un token por cliente, sin
	// papeles y sin caducidad.
	//
	// El segundo modo no se quita porque una instalacion pequena no tiene un
	// proveedor de identidad, y obligarla a montar uno para arrancar es como se
	// consigue que la gente deje el servidor abierto «mientras tanto». Lo que
	// no se hace es dejar el modo en duda: el arranque dice cual esta activo, y
	// con credenciales estaticas dice ademas que no hay papeles.
	Emisor       *Emisor
	credenciales *Credenciales
	registro     *slog.Logger
	Reloj        func() time.Time
}

func Nuevo(m *motor.Motor, espacio *cliente.Espacio, rev *vencimientos.Revisor,
	cred *Credenciales, registro *slog.Logger) (*Servidor, error) {
	if m == nil || espacio == nil {
		return nil, errors.New("api: hacen falta motor y espacio de clientes")
	}
	if cred == nil {
		return nil, ErrSinCredenciales
	}
	if registro == nil {
		registro = slog.New(slog.NewTextHandler(os.Stderr, nil))
	}
	s := &Servidor{motor: m, espacio: espacio, revisor: rev, credenciales: cred,
		registro: registro, Reloj: time.Now, Topes: TopesPorOmision}
	s.limitador = nuevoLimitador(s.Topes)
	s.ritmo = nuevoRitmo(0, 0, func() time.Time { return s.Reloj() })
	return s, nil
}

// --- el sobre ------------------------------------------------------------

// Respuesta es lo que viaja. `Documento` es lo del motor, intacto.
type Respuesta struct {
	Esquema    string         `json:"esquema"`
	Verbo      string         `json:"verbo"`
	Codigo     int            `json:"codigo"`
	Completo   bool           `json:"completo"`
	HayTrabajo bool           `json:"hay_trabajo"`
	Documento  map[string]any `json:"documento"`
	Duracion   string         `json:"duracion"`

	// FirmaVerificada dice si el cuerpo del evento venia firmado y la firma
	// cuadraba. Solo aparece en la respuesta de `empujon`.
	//
	// Va en el SOBRE y no solo en el registro del servidor. Un registro lo rota
	// alguien y se pierde; esta respuesta es la que el cliente guarda y la que
	// ata el evento a lo que el motor decidio con el. Si el evento no se pudo
	// atribuir a nadie, eso tiene que viajar con la decision que produjo, no
	// quedarse en otro sitio.
	//
	// `null` -- el puntero nulo -- significa «esta ruta no recibe eventos», que
	// no es lo mismo que `false`, que significa «lo recibi y no venia firmado».
	FirmaVerificada *bool `json:"firma_verificada,omitempty"`
}

// Fallo es lo que viaja cuando algo se rompe de verdad. Siempre bilingue.
type Fallo struct {
	Esquema string            `json:"esquema"`
	Que     map[string]string `json:"que"`
}

func escribir(w http.ResponseWriter, estado int, cuerpo any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.WriteHeader(estado)
	_ = json.NewEncoder(w).Encode(cuerpo)
}

func fallar(w http.ResponseWriter, estado int, es, en string) {
	escribir(w, estado, Fallo{Esquema: "actaira/api/fallo/v1",
		Que: map[string]string{"es": es, "en": en}})
}

// --- idioma ---------------------------------------------------------------

// idiomaDe elige entre los dos que existen, y SOLO entre esos.
//
// Lo que no hace es negociar con `Accept-Language` a base de prefijos: un
// `fr-FR` que acabara en castellano porque es lo primero de la lista seria
// peor que el castellano por defecto, porque nadie se daria cuenta.
func idiomaDe(r *http.Request) string {
	if q := r.URL.Query().Get("idioma"); q == "es" || q == "en" {
		return q
	}
	for _, trozo := range strings.Split(r.Header.Get("Accept-Language"), ",") {
		switch strings.ToLower(strings.TrimSpace(strings.SplitN(trozo, ";", 2)[0])) {
		case "es", "es-es", "es-419", "es-mx", "es-ar":
			return "es"
		case "en", "en-us", "en-gb":
			return "en"
		}
	}
	return "es"
}

// --- autenticacion --------------------------------------------------------

func (s *Servidor) conCliente(
	siguiente func(http.ResponseWriter, *http.Request, *cliente.Cliente),
) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		cabecera := r.Header.Get("Authorization")
		token := ""
		if despues, hay := strings.CutPrefix(cabecera, "Bearer "); hay {
			token = strings.TrimSpace(despues)
		}
		// CON EMISOR: el cliente y los roles salen del testigo verificado.
		//
		// De ningun otro sitio. Un servidor que lea el cliente de una cabecera
		// deja que quien llama elija de quien es el expediente que va a abrir,
		// y uno que lea los roles de una cabecera deja que elija sus propios
		// permisos. Los dos fallos funcionan perfectamente en todas las
		// pruebas, porque las pruebas mandan la cabecera correcta.
		if s.Emisor != nil {
			identidad, err := s.Emisor.Verificar(token, s.Reloj())
			if err != nil {
				if !s.ritmo.permite("sin-credencial") {
					demasiadas(w, 60, "demasiados intentos", "too many attempts")
					return
				}
				s.registro.Warn("testigo rechazado", "ruta", r.URL.Path,
					"error", err.Error())
				fallar(w, http.StatusUnauthorized,
					"credencial no valida", "invalid credential")
				return
			}
			pedido := r.PathValue("cliente")
			if pedido != "" && pedido != identidad.Cliente {
				s.registro.Warn("testigo de un cliente usado contra otro",
					"tiene", identidad.Cliente, "pidio", pedido,
					"sujeto", identidad.Sujeto)
				fallar(w, http.StatusUnauthorized,
					"credencial no valida", "invalid credential")
				return
			}
			if !s.ritmo.permite("cliente:" + identidad.Cliente) {
				demasiadas(w, 30,
					"demasiadas peticiones: espera unos segundos",
					"too many requests: wait a few seconds")
				return
			}
			c, err := s.espacio.De(identidad.Cliente)
			if err != nil {
				fallar(w, http.StatusInternalServerError,
					"no se pudo abrir el espacio del cliente",
					"could not open the client space")
				return
			}
			// Los roles viajan con la peticion para que el manejador del verbo
			// pueda comprobarlos. Se meten en el contexto y no en una variable
			// del servidor: dos peticiones a la vez tienen dos identidades.
			r = r.WithContext(conIdentidad(r.Context(), identidad))
			empezo := s.Reloj()
			siguiente(w, r, c)
			s.registro.Info("acceso", "cliente", identidad.Cliente,
				"sujeto", identidad.Sujeto, "roles", strings.Join(identidad.Roles, ","),
				"metodo", r.Method, "ruta", r.URL.Path,
				"duracion", s.Reloj().Sub(empezo).String())
			return
		}

		id, ok := s.credenciales.Cliente(token)
		if !ok {
			// Un cubo COMPARTIDO para los intentos que no identifican a nadie.
			// Sin el, adivinar un token es gratis: cada intento fallido no
			// gasta el cubo de ningun cliente, porque no hay cliente.
			if !s.ritmo.permite("sin-credencial") {
				s.registro.Warn("demasiados intentos sin credencial valida",
					"ruta", r.URL.Path)
				demasiadas(w, 60,
					"demasiados intentos", "too many attempts")
				return
			}
			// Ni se dice que el token no existe ni que el cliente no existe:
			// las dos respuestas juntas son un oraculo para enumerar clientes.
			fallar(w, http.StatusUnauthorized,
				"credencial no valida", "invalid credential")
			return
		}
		pedido := r.PathValue("cliente")
		if pedido != "" && pedido != id {
			// Mismo 401 y no 403: un 403 confirmaria que ese cliente existe.
			s.registro.Warn("credencial de un cliente usada contra otro",
				"tiene", id, "pidio", pedido)
			fallar(w, http.StatusUnauthorized,
				"credencial no valida", "invalid credential")
			return
		}
		// EL RITMO, por credencial y despues de identificarla.
		//
		// Antes de identificarla no se puede: limitar por dirección de origen
		// castiga a todo el que salga por la misma pasarela, que en una empresa
		// son todos. Y limitar despues significa que un atacante que prueba
		// tokens gasta el cubo de... nadie, porque su token no existe. Por eso
		// hay dos cubos: el de la credencial valida, y uno compartido para los
		// intentos fallidos, que es el que frena el adivinar.
		if !s.ritmo.permite("cliente:" + id) {
			s.registro.Warn("cliente al tope de ritmo", "cliente", id, "ruta", r.URL.Path)
			demasiadas(w, 30,
				"demasiadas peticiones: espera unos segundos",
				"too many requests: wait a few seconds")
			return
		}

		c, err := s.espacio.De(id)
		if err != nil {
			fallar(w, http.StatusInternalServerError,
				"no se pudo abrir el espacio del cliente", "could not open the client space")
			return
		}

		// EL REGISTRO DE ACCESO. Quien pidio que y cuando.
		//
		// Habia registro de los accesos ANOMALOS -- una credencial de un
		// cliente usada contra otro -- y ninguno de los normales. Con eso, la
		// pregunta que hace un auditor despues de un incidente («quien leyo el
		// expediente de este cliente en marzo») no se puede contestar, y la de
		// un cliente («quien ha estado mirando lo mio») tampoco.
		//
		// NO se registra el token, ni entero ni en trozos. Lo que identifica al
		// que llama es el cliente al que la credencial da acceso; el token es
		// el secreto, y un secreto en un registro que se rota, se archiva y se
		// manda a un agregador deja de ser un secreto.
		empezo := s.Reloj()
		siguiente(w, r, c)
		s.registro.Info("acceso", "cliente", id, "metodo", r.Method,
			"ruta", r.URL.Path, "duracion", s.Reloj().Sub(empezo).String())
	}
}

// ConTopes cambia los topes y rehace el limitador.
//
// Existe porque los topes se fijaban en el constructor y no se podian tocar: un
// valor por omision que nadie puede ajustar no es un valor por omision, es una
// constante disfrazada, y la primera maquina grande o el primer webhook con
// rafagas se estrella contra ella sin salida.
//
// Devuelve el propio servidor para poder encadenarlo al construirlo.
func (s *Servidor) ConTopes(t Tope) *Servidor {
	s.Topes = t
	s.limitador = nuevoLimitador(t)
	return s
}

// --- las rutas ------------------------------------------------------------

// Rutas devuelve el enrutador. Los verbos que EXISTEN y ni uno mas.
//
// Anadir aqui un verbo que la linea de mandatos no tenga seria empezar el
// segundo motor por el sitio mas facil de no notar.
func (s *Servidor) Rutas() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /", s.panel)
	mux.HandleFunc("GET /salud", s.salud)
	mux.HandleFunc("GET /v1/verbos", s.verbos)
	mux.HandleFunc("POST /v1/clientes/{cliente}/plan", s.conCliente(s.plan))
	mux.HandleFunc("POST /v1/clientes/{cliente}/vigilar", s.conCliente(s.vigilar))
	mux.HandleFunc("GET /v1/clientes/{cliente}/vencimientos", s.conCliente(s.vencimientos))
	mux.HandleFunc("GET /v1/clientes/{cliente}/noconformidades", s.conCliente(s.noconformidades))
	mux.HandleFunc("POST /v1/clientes/{cliente}/empujon", s.conCliente(s.empujon))
	// Los verbos de LECTURA que la consola necesita. Ver `lectura.go`: la API
	// traducia cinco de los diecinueve del motor, y la pantalla no podia
	// ensenar ni la evidencia, ni el cuestionario, ni la declaracion de
	// aplicabilidad, ni el expediente.
	mux.HandleFunc("GET /v1/clientes/{cliente}/almacen", s.conCliente(s.almacen))
	mux.HandleFunc("POST /v1/clientes/{cliente}/preguntar", s.conCliente(s.preguntar))
	mux.HandleFunc("POST /v1/clientes/{cliente}/soa", s.conCliente(s.soa))
	mux.HandleFunc("POST /v1/clientes/{cliente}/anexo", s.conCliente(s.anexo))
	mux.HandleFunc("GET /v1/clientes/{cliente}/revision", s.conCliente(s.revision))
	return mux
}

//go:embed panel.html
var panelHTML []byte

// panel sirve la pagina DESDE EL PROPIO SERVIDOR, y eso no es comodidad.
//
// Servida aqui, la pagina y la API comparten origen: no hace falta CORS, no
// hay una lista de origenes que alguien acabara poniendo en `*`, y no hay un
// segundo sitio donde desplegar una version que se queda vieja. El caso que
// esto evita no es teorico: un panel servido aparte y una API que acepta
// cualquier origen es una pagina de otro leyendo el expediente de un cliente
// con la credencial que el navegador manda sola.
//
// Quien la quiera alojar en otro sitio tiene la pagina en `panel/panel.html`,
// y entonces el CORS lo pone delante quien opere, a sabiendas.
func (s *Servidor) panel(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		fallar(w, http.StatusNotFound, "aqui no hay nada", "nothing here")
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	// La politica se CALCULA de los bytes de la pagina, no se escribe aqui.
	// Ver `csp.go`: llevaba `'unsafe-inline'` en script y en estilo, que apaga
	// casi entera la proteccion que una politica de este tipo sirve para dar.
	w.Header().Set("Content-Security-Policy", PoliticaDelPanel)
	w.Header().Set("Referrer-Policy", "no-referrer")
	_, _ = w.Write(panelHTML)
}

func (s *Servidor) salud(w http.ResponseWriter, r *http.Request) {
	cuerpo := map[string]any{
		"esquema": "actaira/api/salud/v1", "vivo": true,
		"cuando": s.Reloj().UTC().Format(time.RFC3339),
		// Cuantos verbos del motor hay corriendo, y cual es el tope. Sin esto,
		// un 429 por concurrencia no se puede diagnosticar desde fuera: quien
		// lo recibe no sabe si la maquina esta llena o si es su propio tope.
		"motor": map[string]any{
			"en_curso":         s.limitador.enCurso(),
			"tope_global":      s.Topes.Global,
			"tope_por_cliente": s.Topes.PorCliente,
		},
	}
	// EL ESTADO DE LA VIGILANCIA, que es lo que de verdad se vende.
	//
	// «vivo: true» solo dice que el proceso HTTP contesta. La unica tarea que
	// este servicio hace sin que nadie la pida es darse cuenta de que algo
	// caduco, y hasta ahora no habia forma de saber desde fuera si estaba
	// corriendo -- de hecho no corria, y el estado de salud seguia diciendo
	// que si. Un estado de salud que no cubre la tarea principal del servicio
	// es un estado de salud que miente por omision.
	if s.Vigilancia == nil {
		cuerpo["vigilancia"] = map[string]any{
			"activa": false,
			"nota": "no hay planificador: nada caducara por su cuenta y el expediente " +
				"solo se revisara cuando alguien lo pida",
		}
	} else {
		fallidos := s.Vigilancia.Fallidos()
		cuerpo["vigilancia"] = map[string]any{
			"activa":    true,
			"intervalo": s.Vigilancia.Intervalo.String(),
			"pasadas":   s.Vigilancia.Pasadas(),
			// Los avisos que no se pudieron entregar se PUBLICAN. Registrarlos
			// y seguir deja al cliente creyendo que le avisan cuando no, que es
			// la unica forma de que una vigilancia sea peor que ninguna.
			"avisos_sin_entregar": len(fallidos),
		}
	}
	escribir(w, http.StatusOK, cuerpo)
}

// VERBOS es lo que esta API sabe pedirle al motor, con el esquema que devuelve
// cada uno. Se publica para que un cliente no tenga que descubrirlo probando.
var VERBOS = []map[string]string{
	{"verbo": "plan", "metodo": "POST", "ruta": "/v1/clientes/{cliente}/plan"},
	{"verbo": "vigilar", "metodo": "POST", "ruta": "/v1/clientes/{cliente}/vigilar"},
	{"verbo": "vigilar --solo-almacen", "metodo": "GET",
		"ruta": "/v1/clientes/{cliente}/vencimientos"},
	{"verbo": "noconformidad listar", "metodo": "GET",
		"ruta": "/v1/clientes/{cliente}/noconformidades"},
	{"verbo": "empujon", "metodo": "POST", "ruta": "/v1/clientes/{cliente}/empujon"},
	{"verbo": "almacen verificar", "metodo": "GET",
		"ruta": "/v1/clientes/{cliente}/almacen"},
	{"verbo": "preguntar", "metodo": "POST", "ruta": "/v1/clientes/{cliente}/preguntar"},
	{"verbo": "soa", "metodo": "POST", "ruta": "/v1/clientes/{cliente}/soa"},
	{"verbo": "anexo", "metodo": "POST", "ruta": "/v1/clientes/{cliente}/anexo?cual=iv|v"},
	{"verbo": "revision", "metodo": "GET", "ruta": "/v1/clientes/{cliente}/revision"},
}

func (s *Servidor) verbos(w http.ResponseWriter, r *http.Request) {
	escribir(w, http.StatusOK, map[string]any{
		"esquema": "actaira/api/verbos/v1", "verbos": VERBOS,
		"nota": map[string]string{
			"es": "esta API traduce transporte y nunca significado: el documento que devuelve " +
				"cada ruta es el que emite el motor, con su propio esquema dentro",
			"en": "this API translates transport and never meaning: the document each route " +
				"returns is the one the engine emits, with its own schema inside"}})
}

// Perfil es lo que el cliente dice de su sistema. Se pasa al motor tal cual:
// aqui no se deduce nada de ello.
type Perfil struct {
	Roles            []string `json:"roles"`
	AltoRiesgo       string   `json:"alto_riesgo"`
	ViaAnexo         string   `json:"via_anexo"`
	SectorPublico    string   `json:"sector_publico"`
	ModeloUsoGeneral string   `json:"modelo_uso_general"`
	RiesgoSistemico  string   `json:"riesgo_sistemico"`
	Fecha            string   `json:"fecha"`
}

var tri = map[string]bool{"si": true, "no": true, "": true}

type par struct{ bandera, valor string }

// aArgumentos convierte el perfil en los argumentos del motor.
//
// Se ordena por PAREJAS y no por la lista plana. La primera version llamaba a
// `sort.Strings` sobre las cadenas sueltas, que separa cada bandera de su
// valor y produce una linea de mandatos absurda: el motor contestaba con un
// error y esta capa lo traducia a «el motor no devolvio un documento que esta
// plataforma entienda», que es verdad y no dice nada. El orden se quiere para
// que dos peticiones iguales den la misma linea -- y por tanto la misma
// ejecucion reproducible --, no para ordenar texto.
func (p Perfil) aArgumentos() ([]string, error) {
	var pares []par
	for _, rol := range p.Roles {
		// Contra la lista GENERADA desde el motor, no contra una escrita aqui.
		//
		// Habia una lista a mano en este `switch` y estaba mal: decia
		// `responsable_del_despliegue` y `fabricante_de_productos` donde el
		// motor dice `responsable_despliegue` y `fabricante_producto`, y no
		// tenia `proveedor_modelo`. El efecto no era rechazar lo que no
		// entiende: era ACEPTAR el nombre equivocado que mandaba el panel y
		// pasarselo al motor, que no lo reconocia y contestaba que no le ataba
		// ninguna obligacion. Una validacion que confirma el error en vez de
		// cazarlo es peor que no tener validacion, porque da confianza.
		if !RolConocido(rol) {
			return nil, fmt.Errorf(
				"rol desconocido: %q. Los del Reglamento son %v", rol, RolesDelReglamento)
		}
		pares = append(pares, par{"--rol", rol})
	}
	for _, x := range []par{
		{"--alto-riesgo", p.AltoRiesgo}, {"--sector-publico", p.SectorPublico},
		{"--modelo-uso-general", p.ModeloUsoGeneral}, {"--riesgo-sistemico", p.RiesgoSistemico},
	} {
		if !tri[x.valor] {
			return nil, fmt.Errorf("%s: %q no es si, no, ni vacio", x.bandera, x.valor)
		}
		if x.valor != "" {
			pares = append(pares, x)
		}
	}
	if p.ViaAnexo != "" {
		if p.ViaAnexo != "anexo_i" && p.ViaAnexo != "anexo_iii" {
			return nil, fmt.Errorf("via_anexo: %q", p.ViaAnexo)
		}
		pares = append(pares, par{"--via-anexo", p.ViaAnexo})
	}
	if p.Fecha != "" {
		if _, err := time.Parse("2006-01-02", p.Fecha); err != nil {
			return nil, fmt.Errorf("fecha: %q no es AAAA-MM-DD", p.Fecha)
		}
		pares = append(pares, par{"--fecha", p.Fecha})
	}
	sort.SliceStable(pares, func(i, j int) bool {
		if pares[i].bandera != pares[j].bandera {
			return pares[i].bandera < pares[j].bandera
		}
		return pares[i].valor < pares[j].valor
	})
	args := make([]string, 0, 2*len(pares))
	for _, x := range pares {
		args = append(args, x.bandera, x.valor)
	}
	return args, nil
}

// EL PERMISO SE COMPRUEBA AQUI, no en cada ruta.
//
// Por aqui pasa todo verbo del motor, asi que una ruta nueva nace con el
// control puesto. Repartirlo por los manejadores habria hecho que el permiso
// dependiera de acordarse, y la ruta numero once es la que alguien olvida --
// que es exactamente lo que le paso a la tabla de banderas cuando se anadieron
// cinco rutas de golpe y tres quedaron sin declarar.
func (s *Servidor) correr(w http.ResponseWriter, r *http.Request, c *cliente.Cliente,
	verbo, trabajo string, args ...string) {
	if !s.exigirPapel(w, r, verbo) {
		return
	}
	soltar, lleno := s.limitador.entrar(c.ID)
	if soltar == nil {
		// LO QUE SE AGOTA AQUI NO SON PETICIONES: ES LA MAQUINA.
		//
		// Un verbo del motor arranca un PROCESO aparte que lee el repositorio
		// entero del cliente y puede tardar minutos. No habia nada que limitara
		// cuantos corren a la vez, asi que N peticiones simultaneas eran N
		// procesos. No hace falta un atacante: basta una integracion continua
		// que dispare el plan en cada push de cada rama. Y como un solo binario
		// sirve a todos los clientes, el que se queda sin maquina no es solo el
		// que empujo.
		s.registro.Warn("verbo rechazado por concurrencia",
			"cliente", c.ID, "verbo", verbo, "motivo", lleno,
			"en_curso", s.limitador.enCurso())
		demasiadas(w, 15, "no se pudo empezar ahora mismo: "+lleno,
			"could not start right now: "+lleno)
		return
	}
	defer soltar()
	res, err := s.motor.Ejecutar(r.Context(), verbo, trabajo, args...)
	s.terminar(w, c, verbo, res, err)
}

// correrSinRuta es para los verbos cuyo primer positional NO es una ruta.
func (s *Servidor) correrSinRuta(w http.ResponseWriter, r *http.Request,
	c *cliente.Cliente, verbo string, args ...string) {
	if !s.exigirPapel(w, r, verbo) {
		return
	}
	// El mismo tope que en `correr`. Un verbo sin ruta arranca exactamente el
	// mismo proceso; acotar solo uno de los dos caminos deja abierto el otro, y
	// el que queda abierto es el que se usara.
	soltar, lleno := s.limitador.entrar(c.ID)
	if soltar == nil {
		s.registro.Warn("verbo rechazado por concurrencia",
			"cliente", c.ID, "verbo", verbo, "motivo", lleno,
			"en_curso", s.limitador.enCurso())
		demasiadas(w, 15, "no se pudo empezar ahora mismo: "+lleno,
			"could not start right now: "+lleno)
		return
	}
	defer soltar()
	res, err := s.motor.EjecutarSinRuta(r.Context(), verbo, c.Raiz, args...)
	s.terminar(w, c, verbo, res, err)
}

func (s *Servidor) terminar(w http.ResponseWriter, c *cliente.Cliente, verbo string,
	res motor.Resultado, err error) {
	s.terminarConFirma(w, c, verbo, res, err, nil)
}

func (s *Servidor) terminarConFirma(w http.ResponseWriter, c *cliente.Cliente,
	verbo string, res motor.Resultado, err error, firma *bool) {
	if err != nil {
		if errors.Is(err, motor.ErrFueraDeAlcance) {
			fallar(w, http.StatusForbidden,
				"esa ruta no cuelga del espacio de este cliente",
				"that path does not hang off this client's space")
			return
		}
		s.registro.Error("el motor fallo", "verbo", verbo, "cliente", c.ID, "error", err)
		fallar(w, http.StatusBadGateway,
			"el motor no devolvio un documento que esta plataforma entienda",
			"the engine did not return a document this platform understands")
		return
	}
	// 200 CON el codigo dentro. Tres no es un error: es el estado normal de un
	// cliente al que le falta contestar algo.
	escribir(w, http.StatusOK, Respuesta{
		Esquema: Esquema, Verbo: res.Verbo, Codigo: res.Codigo,
		Completo: res.Completo(), HayTrabajo: res.HayTrabajo(),
		Documento: res.Documento, Duracion: res.Duracion.Round(time.Millisecond).String(),
		FirmaVerificada: firma})
}

func (s *Servidor) leerPerfil(w http.ResponseWriter, r *http.Request) (Perfil, []string, bool) {
	var p Perfil
	if r.Body != nil {
		dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<16))
		dec.DisallowUnknownFields()
		if err := dec.Decode(&p); err != nil && err.Error() != "EOF" {
			fallar(w, http.StatusBadRequest,
				"el cuerpo no es un perfil que esta API entienda: "+err.Error(),
				"the body is not a profile this API understands: "+err.Error())
			return p, nil, false
		}
	}
	args, err := p.aArgumentos()
	if err != nil {
		fallar(w, http.StatusBadRequest, err.Error(), err.Error())
		return p, nil, false
	}
	return p, args, true
}

func (s *Servidor) plan(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	_, args, ok := s.leerPerfil(w, r)
	if !ok {
		return
	}
	args = append(args, "--idioma", idiomaDe(r))
	s.correr(w, r, c, "plan", c.Trabajo(), args...)
}

func (s *Servidor) vigilar(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	p, args, ok := s.leerPerfil(w, r)
	if !ok {
		return
	}
	// `vigilar` NO tiene `--fecha`: el vencimiento se mide contra un reloj, no
	// contra una fecha de evaluacion, y darle las dos banderas habria sido dos
	// fuentes para lo mismo. Asi que la fecha del perfil se traduce al reloj.
	args = quitar(args, "--fecha")
	if p.Fecha != "" {
		args = append(args, "--ahora", p.Fecha+"T00:00:00+00:00")
	}
	args = append(args, "--almacen", c.Almacen(), "--idioma", idiomaDe(r))
	s.correr(w, r, c, "vigilar", c.Trabajo(), args...)
}

// quitar saca una bandera y su valor de la lista.
func quitar(args []string, bandera string) []string {
	fuera := make([]string, 0, len(args))
	for i := 0; i < len(args); i++ {
		if args[i] == bandera {
			i++ // y su valor
			continue
		}
		fuera = append(fuera, args[i])
	}
	return fuera
}

// BANDERAS dice que le manda cada ruta al motor, aparte del perfil.
//
// Se publica para poder comprobarlo contra el `--help` del verbo. La pasada
// adversarial de la fase 20 encontro tres rutas mandando banderas que su verbo
// NO acepta -- `noconformidad --idioma`, `vigilar --fecha` --, y el motor
// contestaba con un error de uso que esta capa traducia a «el motor no
// devolvio un documento que esta plataforma entienda». El contrato de
// documentos cubria las SALIDAS; las entradas no las cubria nadie.
// La tabla estaba a mano, y esa es la parte que fallo. Al anadir cinco rutas de
// lectura de golpe, nadie anadio sus banderas aqui, asi que la puerta siguio
// verde mientras TRES de las cinco mandaban banderas que su verbo no acepta y
// contestaban 502. Una puerta no puede cazar lo que nadie declaro.
//
// Se cierra con `test_toda_ruta_publicada_declara_sus_banderas`, que exige una
// entrada por cada verbo de `VERBOS`: olvidarse de declarar pasa a ser el fallo,
// en vez de la forma de saltarse la comprobacion.
var BANDERAS = map[string][]string{
	"plan":          {"--idioma", "--json", "--fecha", "--rol", "--alto-riesgo", "--via-anexo"},
	"vigilar":       {"--idioma", "--json", "--almacen", "--ahora", "--rol", "--alto-riesgo", "--via-anexo"},
	"noconformidad": {"--idioma", "--json", "--almacen"},
	"empujon":       {"--idioma", "--json", "--almacen"},
	// `almacen` NO lleva `--idioma`: su veredicto no tiene prosa traducible
	// fuera de la nota, que va en los dos idiomas dentro del documento.
	"almacen": {"--json"},
	// Ni `preguntar` ni `soa` aceptan `--almacen`. Se les pasaba, y por eso las
	// dos contestaban 502.
	"preguntar": {"--idioma", "--json", "--respuestas", "--rol", "--alto-riesgo"},
	"soa":       {"--idioma", "--json", "--respuestas", "--rol", "--alto-riesgo"},
	"anexo":     {"--idioma", "--json", "--cual", "--respuestas", "--rol", "--alto-riesgo"},
	"revision":  {"--idioma", "--json", "--almacen"},
}

// verboDe saca el nombre del verbo de una entrada de `VERBOS`.
//
// La tabla publica «vigilar --solo-almacen» y «noconformidad listar» porque eso
// es lo que se ejecuta, y quien lee la API quiere verlo entero. Lo que hay que
// buscar en `BANDERAS` es el primer token.
func verboDe(entrada string) string {
	for i := 0; i < len(entrada); i++ {
		if entrada[i] == ' ' {
			return entrada[:i]
		}
	}
	return entrada
}

func (s *Servidor) vencimientos(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	// Sin repositorio: para saber QUE CADUCO hacen falta el almacen y el reloj,
	// y no el codigo del cliente. Es la ruta que puede correr un cron sin que
	// nadie haya empujado nada.
	s.correr(w, r, c, "vigilar", c.Almacen(),
		"--solo-almacen", "--almacen", c.Almacen(), "--idioma", idiomaDe(r))
}

func (s *Servidor) noconformidades(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	// Sin ruta de trabajo: el primer positional de este verbo es la ACCION.
	// La version anterior le pasaba el almacen como ruta y la linea salia
	// `noconformidad <ruta> listar`, que el motor rechaza; esta capa lo
	// traducia a «el motor no devolvio un documento que esta plataforma
	// entienda», que es verdad y no dice nada. Lo encontro la pasada
	// adversarial de la fase 20 probando las rutas una por una contra el
	// motor de verdad, que es lo unico que lo habria encontrado: las pruebas
	// de esta capa corrian sin binario.
	s.correrSinRuta(w, r, c, "noconformidad", "listar",
		"--almacen", c.Almacen(), "--idioma", idiomaDe(r))
}

func (s *Servidor) empujon(w http.ResponseWriter, r *http.Request, c *cliente.Cliente) {
	// El cuerpo del webhook se guarda y se le pasa al motor por fichero: pasarlo
	// por la linea de mandatos habria metido el cuerpo de un tercero en la tabla
	// de procesos de la maquina, que la lee cualquiera.
	crudo, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20))
	if err != nil {
		fallar(w, http.StatusRequestEntityTooLarge,
			"el cuerpo del evento es demasiado grande", "the event body is too large")
		return
	}
	// LA FIRMA, antes de tocar nada.
	//
	// La credencial demuestra que quien llama puede tocar el espacio de este
	// cliente; la firma demuestra que el CUERPO viene del proveedor y llego
	// intacto. Son preguntas distintas, y con solo la credencial cualquiera que
	// la tenga puede inventarse un evento: decir que se empujo un commit que no
	// existe. El motor decidiria sobre el y lo escribiria en el expediente.
	//
	// Se comprueba ANTES de escribir el fichero temporal: un evento que no se
	// va a atender no tiene por que pasar por el disco del cliente.
	firmado := false
	switch err := verificarFirma(r, c.ID, crudo); {
	case err == nil:
		firmado = true
	case errors.Is(err, ErrSinSecreto):
		// El tercer estado: este cliente no ha configurado secreto. Se atiende
		// -- exigirlo siempre romperia a todo el que ya tiene el webhook puesto
		// sin secreto, y lo que hace la gente cuando su integracion deja de
		// funcionar de golpe es quitar el webhook -- pero NO en silencio.
		s.registro.Warn("evento atendido SIN FIRMA: este cliente no tiene secreto "+
			"de webhook configurado, asi que el evento no se puede atribuir a nadie",
			"cliente", c.ID, "variable", VariableDelSecreto+strings.ToUpper(c.ID))
	default:
		s.registro.Warn("evento RECHAZADO por firma",
			"cliente", c.ID, "error", err.Error())
		fallar(w, http.StatusUnauthorized,
			"la firma del evento no es valida: "+err.Error(),
			"the event signature is not valid: "+err.Error())
		return
	}
	// Un fichero POR PETICION y no un nombre fijo. Con un nombre fijo, dos
	// empujones del mismo cliente a la vez se pisaban y el motor podia leer el
	// cuerpo del otro: decidir sobre un evento que no era el que llego es peor
	// que fallar, porque el resultado es plausible.
	f, err := os.CreateTemp(c.Raiz, "empujon-*.json")
	if err != nil {
		fallar(w, http.StatusInternalServerError,
			"no se pudo guardar el evento", "could not store the event")
		return
	}
	ruta := f.Name()
	// Y se borra al salir: es el cuerpo de un tercero y no tiene por que
	// quedarse en el espacio del cliente despues de haberse decidido.
	defer func() { _ = os.Remove(ruta) }()
	if _, err := f.Write(crudo); err != nil || f.Close() != nil {
		fallar(w, http.StatusInternalServerError,
			"no se pudo guardar el evento", "could not store the event")
		return
	}
	if err := os.Chmod(ruta, 0o600); err != nil {
		fallar(w, http.StatusInternalServerError,
			"no se pudo guardar el evento", "could not store the event")
		return
	}
	s.correrConFirma(w, r, c, &firmado, "empujon", ruta,
		"--almacen", c.Almacen(), "--idioma", idiomaDe(r))
}

// correrConFirma es `correr` pasando ademas si el evento venia firmado.
//
// Se separa en vez de anadirle un parametro a `correr` porque `correr` lo
// llaman nueve rutas y ocho no reciben eventos: darles a todas un parametro que
// siempre es nulo invita a pasarle cualquier cosa el dia que alguien tenga
// prisa, y entonces una ruta que no recibe eventos publicaria `firma_verificada`.
func (s *Servidor) correrConFirma(w http.ResponseWriter, r *http.Request,
	c *cliente.Cliente, firma *bool, verbo, trabajo string, args ...string) {
	if !s.exigirPapel(w, r, verbo) {
		return
	}
	soltar, lleno := s.limitador.entrar(c.ID)
	if soltar == nil {
		s.registro.Warn("verbo rechazado por concurrencia",
			"cliente", c.ID, "verbo", verbo, "motivo", lleno,
			"en_curso", s.limitador.enCurso())
		demasiadas(w, 15, "no se pudo empezar ahora mismo: "+lleno,
			"could not start right now: "+lleno)
		return
	}
	defer soltar()
	res, err := s.motor.Ejecutar(r.Context(), verbo, trabajo, args...)
	s.terminarConFirma(w, c, verbo, res, err, firma)
}
