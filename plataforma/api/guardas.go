package api

import (
	"fmt"
	"net/http"
	"strconv"
	"sync"
	"time"
)

// Lo que impide que un cliente se lleve por delante a los demas.
//
// EL PROBLEMA, Y POR QUE NO ES EL HABITUAL
// ------------------------------------------
// Casi todo lo que sirve esta API es barato. Un verbo del motor no: `plan`
// arranca un PROCESO aparte que lee el repositorio entero del cliente y puede
// tardar minutos. No habia nada que limitara cuantos corren a la vez.
//
// Con eso, N peticiones simultaneas son N procesos del motor. No hace falta un
// atacante: basta un cliente con una integracion continua mal configurada que
// dispare el plan en cada push de cada rama. Y como el espacio de clientes lo
// sirve un solo binario, el que se queda sin maquina no es solo el que empujo:
// son todos.
//
// Esto no es la limitacion de ritmo tipica, que cuenta peticiones por minuto.
// Aqui lo que se agota no son peticiones: es memoria y CPU, y se agota mientras
// la peticion sigue abierta. Por eso lo que se limita es la CONCURRENCIA -- lo
// que hay corriendo a la vez -- y no el ritmo. El ritmo se limita ademas,
// porque las peticiones baratas tambien se pueden usar para adivinar un token.
//
// DOS TOPES Y NO UNO
// -------------------
// Un tope global protege la maquina. Un tope POR CLIENTE es el que hace que un
// cliente no pueda ocupar el global entero: sin el, el primero que llegue con
// veinte peticiones deja a los demas esperando aunque haya sitio reservado para
// ellos. Es la diferencia entre un servidor que aguanta y un servidor que
// aguanta para todos.

// Tope describe cuantos verbos del motor pueden correr a la vez.
type Tope struct {
	Global     int // en toda la maquina
	PorCliente int
}

// TopesPorOmision son deliberadamente bajos. Un verbo del motor es un proceso
// que lee un repositorio entero; cuatro a la vez ya es una maquina ocupada.
var TopesPorOmision = Tope{Global: 4, PorCliente: 2}

type limitador struct {
	tope       Tope
	mu         sync.Mutex
	global     int
	porCliente map[string]int
}

func nuevoLimitador(t Tope) *limitador {
	if t.Global <= 0 {
		t.Global = TopesPorOmision.Global
	}
	if t.PorCliente <= 0 || t.PorCliente > t.Global {
		t.PorCliente = min(TopesPorOmision.PorCliente, t.Global)
	}
	return &limitador{tope: t, porCliente: map[string]int{}}
}

// entrar reserva un hueco. Devuelve (soltar, motivo): si `soltar` es nil, no
// habia sitio y `motivo` dice CUAL de los dos topes se lleno.
//
// Decir cual importa: «demasiadas peticiones» no le dice a nadie que hacer, y
// «has llegado a tu tope de 2 en curso» y «la maquina esta al completo» piden
// cosas distintas -- esperar tu turno o avisar a quien opera.
func (l *limitador) entrar(cliente string) (func(), string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.porCliente[cliente] >= l.tope.PorCliente {
		return nil, fmt.Sprintf(
			"ya tienes %d verbos del motor en curso, que es tu tope", l.tope.PorCliente)
	}
	if l.global >= l.tope.Global {
		return nil, fmt.Sprintf(
			"la maquina tiene %d verbos del motor en curso, que es su tope", l.tope.Global)
	}
	l.global++
	l.porCliente[cliente]++
	return func() {
		l.mu.Lock()
		defer l.mu.Unlock()
		l.global--
		l.porCliente[cliente]--
		if l.porCliente[cliente] <= 0 {
			// Se borra la entrada. Dejarla a cero hace que este mapa crezca con
			// cada cliente que haya pasado alguna vez, y un mapa que solo crece
			// en un proceso que vive meses es una fuga.
			delete(l.porCliente, cliente)
		}
	}, ""
}

// EnCurso es cuantos verbos del motor hay corriendo. Lo publica `/salud`.
func (l *limitador) enCurso() int {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.global
}

// --- ritmo ----------------------------------------------------------------

// cubo es un cubo de fichas por credencial.
//
// Limita las peticiones BARATAS, que la concurrencia no cubre porque terminan
// enseguida. Lo que se protege aqui no es la maquina: es el token. Un atacante
// que pruebe credenciales a ritmo de red da muchos intentos por minuto, y aunque
// el token tenga veinticuatro caracteres, no poner tope es regalar el unico
// dato que hace falta para leer el expediente entero de un cliente.
// _LIMPIAR_A_PARTIR_DE es cuantos cubos tiene que haber para molestarse en
// limpiar. Por debajo, recorrer el mapa cuesta mas que lo que ocupa.
const _LIMPIAR_A_PARTIR_DE = 1024

type cubo struct {
	fichas float64
	ultimo time.Time
}

type ritmo struct {
	porMinuto float64
	punta     float64
	reloj     func() time.Time
	mu        sync.Mutex
	cubos     map[string]*cubo
}

func nuevoRitmo(porMinuto, punta float64, reloj func() time.Time) *ritmo {
	if porMinuto <= 0 {
		porMinuto = 120
	}
	if punta <= 0 {
		punta = 40
	}
	if reloj == nil {
		reloj = time.Now
	}
	return &ritmo{porMinuto: porMinuto, punta: punta, reloj: reloj,
		cubos: map[string]*cubo{}}
}

// permite consume una ficha. Devuelve false si no quedaban.
func (r *ritmo) permite(clave string) bool {
	ahora := r.reloj()
	r.mu.Lock()
	defer r.mu.Unlock()
	c, hay := r.cubos[clave]
	if !hay {
		// Se limpia AQUI, al crear una entrada nueva, y no desde un hilo
		// aparte. La primera version tenia `olvidar` escrito y nadie lo
		// llamaba: codigo muerto que aparentaba resolver la fuga que
		// documentaba, que es peor que no tenerlo, porque quien lo lea dara el
		// problema por resuelto.
		if len(r.cubos) >= _LIMPIAR_A_PARTIR_DE {
			r.olvidar(ahora)
		}
		c = &cubo{fichas: r.punta, ultimo: ahora}
		r.cubos[clave] = c
	}
	transcurrido := ahora.Sub(c.ultimo).Minutes()
	if transcurrido > 0 {
		c.fichas = min64(r.punta, c.fichas+transcurrido*r.porMinuto)
		c.ultimo = ahora
	}
	if c.fichas < 1 {
		return false
	}
	c.fichas--
	return true
}

// olvidar quita los cubos que nadie ha tocado en mas de una hora.
//
// Sin esto, el mapa guarda una entrada por cada credencial que haya llamado
// alguna vez, y en un proceso que vive meses eso solo crece. No es urgente y por
// eso no hay un hilo: se limpia al pasar, que es cuando se sabe que hay carga.
//
// LA CONDICION ERA `c.fichas >= r.punta && ...`, Y NO PODIA CUMPLIRSE NUNCA.
//
// El relleno de un cubo es PEREZOSO: solo ocurre dentro de `permite`, cuando
// alguien llama. Un cubo que se uso una vez y nadie volvio a tocar se queda en
// `punta - 1` fichas para siempre, porque no hay nadie que lo rellene. Asi que
// «lleno y sin tocar en una hora» describe un cubo que no existe: los recien
// creados estan llenos pero acaban de tocarse, y los viejos nunca estan llenos.
// La funcion recorria el mapa entero y no borraba nada.
//
// Mirar solo el tiempo es ademas lo correcto: con cualquier ritmo positivo, un
// cubo sin tocar en una hora se rellenaria hasta la punta en cuanto alguien lo
// usara, asi que olvidarlo no le quita ni una ficha a nadie.
func (r *ritmo) olvidar(ahora time.Time) {
	for k, c := range r.cubos {
		if ahora.Sub(c.ultimo) > time.Hour {
			delete(r.cubos, k)
		}
	}
}

func min64(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

// --- las respuestas -------------------------------------------------------

// demasiadas contesta 429 con `Retry-After`.
//
// La cabecera no es cortesia: sin ella, un cliente bien escrito reintenta en
// bucle y convierte el tope en una tormenta. Con ella, espera.
func demasiadas(w http.ResponseWriter, segundos int, motivo, reason string) {
	w.Header().Set("Retry-After", strconv.Itoa(segundos))
	fallar(w, http.StatusTooManyRequests, motivo, reason)
}
