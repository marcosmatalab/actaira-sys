// Planificador: lo que convierte el revisor en vigilancia y no en una funcion
// que nadie llama.
//
// QUE ESTABA ROTO, Y NO ERA UN DETALLE
// --------------------------------------
// El paquete `vencimientos` estaba escrito, probado y documentado como «el
// unico trabajo que la suscripcion hace de verdad: darse cuenta de que algo
// dejo de valer sin que nadie haya empujado nada».
//
// Y no corria nunca. `main.go` construia el servidor con
// `api.Nuevo(m, espacio, nil, cred, registro)` -- el revisor, literalmente
// `nil` -- y el campo `revisor` del servidor no se leia en ningun sitio de
// `api.go`. El paquete compilaba, sus pruebas pasaban, y el producto en marcha
// no lo invocaba jamas.
//
// Eso no es una funcionalidad incompleta: es una funcionalidad que el producto
// dice tener y no tiene. La vigilancia se reducia a que alguien llamara al
// endpoint de vencimientos por su cuenta, es decir, a que alguien se acordara
// -- que es justo lo que se vende no tener que hacer.
//
// QUE HACE ESTE FICHERO, Y QUE DELIBERADAMENTE NO
// -------------------------------------------------
// Hace lo minimo que merece llamarse vigilancia y puede sostenerse:
//
//   - corre cada `Intervalo`, con una desviacion aleatoria para que N
//     instancias no despierten a la vez;
//   - escribe CADA pasada en un registro que se anade y no se edita, incluidas
//     las pasadas en las que no habia nada que avisar. Un registro que solo
//     guarda los avisos no distingue «no habia nada» de «no se miro», y esa es
//     la distincion de la que depende todo este producto;
//   - reintenta la entrega con espera creciente y, cuando se rinde, lo manda a
//     una cola de fallidos que TAMBIEN se publica. Un aviso que se pierde en
//     silencio es peor que no tener avisos, porque el cliente cree que los
//     tiene.
//
// Lo que NO hace, dicho aqui para que nadie lo suponga leyendo el nombre:
//
//   - No es una cola duradera entre procesos. El registro sobrevive al
//     reinicio y permite saber que quedo sin entregar, pero dos instancias de
//     este binario sobre el mismo espacio revisarian las dos. Para eso hace
//     falta una cola de verdad, y anadirla es una decision de despliegue que
//     este binario no puede tomar solo.
//   - No garantiza la entrega. `Entregar` es de quien lo configura; esto
//     cuenta los intentos, no promete que el destinatario lea.
//   - No escala. Recorre los clientes en serie. Con miles, hace falta otra
//     cosa, y ese dia se sabra por el tiempo de pasada, que se registra.
package vencimientos

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"math/rand"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// ErrSinEntrega se devuelve al construir un planificador sin destino.
//
// Es un error y no un valor por omision a proposito. Un planificador que revisa
// y no entrega es exactamente el fallo que este fichero existe para arreglar,
// solo que una capa mas arriba: algo que parece vigilancia y no avisa a nadie.
var ErrSinEntrega = errors.New(
	"un planificador sin `Entregar` revisaria y no avisaria a nadie, que es la forma " +
		"de tener vigilancia en el organigrama y no en la realidad")

// Entrega es lo que hace llegar un aviso a una persona. Devuelve error si no
// pudo, y entonces se reintenta.
type Entrega func(ctx context.Context, a Aviso) error

// Planificador corre al revisor cada cierto tiempo y entrega lo que salga.
type Planificador struct {
	Revisor   *Revisor
	Intervalo time.Duration
	Entregar  Entrega
	Registro  *slog.Logger

	// Bitacora es el fichero al que se anade cada pasada y cada intento. Si
	// esta vacio, no se escribe, y eso se dice al arrancar en vez de quedar
	// implicito.
	Bitacora string

	// Reintentos es cuantas veces se intenta una entrega antes de rendirse.
	Reintentos int
	// EsperaBase es la primera espera entre intentos; se duplica en cada uno.
	EsperaBase time.Duration

	// Reloj y Dormir existen para las pruebas. Una prueba de un planificador
	// que espera de verdad tarda lo que espera, asi que no se escribe, y
	// entonces esto no se prueba.
	Reloj  func() time.Time
	Dormir func(context.Context, time.Duration) bool

	// revisarTodos es la costura por la que las pruebas meten un revisor falso.
	//
	// Por omision es `p.Revisor.RevisarTodos`. Existe porque lo que hay que
	// probar aqui es el PLANIFICADOR -- que reintenta, que no se calla lo que
	// no entrego, que anota tambien las pasadas vacias -- y un revisor de
	// verdad necesitaria el motor, el espacio y un almacen de evidencia. Una
	// prueba que necesita todo eso para comprobar un reintento no se escribe,
	// y entonces el reintento no se prueba.
	revisarTodos func(context.Context, time.Time) ([]Aviso, []error)

	// preparada protege a `preparar` de correrse dos veces a la vez.
	//
	// `preparar` ESCRIBE campos del planificador -- el revisor, el intervalo,
	// los reintentos, el reloj -- y lo llaman los DOS metodos publicos:
	// `Correr` una vez al empezar y `UnaPasada` en cada pasada. Los dos son
	// exportados, asi que nada impide que alguien dispare una pasada suelta
	// mientras el bucle corre, y entonces hay dos escritores sobre los mismos
	// campos sin candado: una carrera de datos de manual.
	//
	// No la cazaba `-race` porque ninguna prueba los llama a la vez, que es
	// justo lo que hace peligrosa a una carrera latente: no la ve quien mira,
	// la ve quien despliega.
	preparada     sync.Once
	errAlPreparar error

	mu       sync.Mutex
	pasadas  int
	fallidos []Aviso
	// perdidos es CUANTOS avisos no se han entregado en toda la vida del
	// proceso. `fallidos` guarda solo los ultimos, asi que no se puede contar
	// por el; ver `_ULTIMOS_FALLIDOS`.
	perdidos int
}

// _ULTIMOS_FALLIDOS es cuantos avisos no entregados se guardan ENTEROS.
//
// La lista crecia sin tope. Este proceso vive meses y `Entregar` es de quien lo
// configura: un destino caido -- una URL que dejo de existir, un buzon lleno --
// mete un aviso por cliente y por pasada, y ninguno se va nunca. Es la misma
// fuga que ya se cerro en el limitador de ritmo y en el de concurrencia, y aqui
// se habia dejado abierta.
//
// Lo que NO se hace es contar de menos. Olvidar un aviso y publicar un numero
// mas bajo seria decirle al cliente que le fallan menos avisos de los que le
// fallan, que es exactamente la clase de mentira por omision contra la que
// existe este fichero. Asi que el DETALLE se acota y la CUENTA no: `Fallidos`
// devuelve los ultimos y `SinEntregar` dice cuantos hubo.
const _ULTIMOS_FALLIDOS = 256

// Pasadas es cuantas veces ha revisado. Se publica para que el estado de salud
// pueda decir si la vigilancia esta viva, en vez de que alguien lo suponga.
func (p *Planificador) Pasadas() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.pasadas
}

// Fallidos son los ULTIMOS avisos que no se pudieron entregar tras agotar los
// intentos, hasta `_ULTIMOS_FALLIDOS`.
//
// Se guardan y se publican. La alternativa -- registrarlos y seguir -- deja al
// cliente creyendo que le avisan cuando no le avisan, que es la unica forma de
// que una vigilancia sea peor que ninguna.
//
// Son los ultimos y no todos porque la lista crecia sin tope en un proceso que
// vive meses. Cuantos hubo EN TOTAL lo dice `SinEntregar`, que no se acota: el
// detalle se puede perder, la cuenta no.
func (p *Planificador) Fallidos() []Aviso {
	p.mu.Lock()
	defer p.mu.Unlock()
	return append([]Aviso(nil), p.fallidos...)
}

// SinEntregar es cuantos avisos no se han entregado en toda la vida de este
// proceso. Es la cifra que publica el estado de salud.
func (p *Planificador) SinEntregar() int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.perdidos
}

// preparar rellena lo que falte, UNA sola vez.
func (p *Planificador) preparar() error {
	p.preparada.Do(func() { p.errAlPreparar = p.prepararUnaVez() })
	return p.errAlPreparar
}

func (p *Planificador) prepararUnaVez() error {
	if p.revisarTodos == nil {
		if p.Revisor == nil {
			return errors.New("un planificador sin revisor no revisa nada")
		}
		p.revisarTodos = p.Revisor.RevisarTodos
	}
	if p.Entregar == nil {
		return ErrSinEntrega
	}
	if p.Intervalo <= 0 {
		p.Intervalo = time.Hour
	}
	if p.Reintentos <= 0 {
		p.Reintentos = 3
	}
	if p.EsperaBase <= 0 {
		p.EsperaBase = 5 * time.Second
	}
	if p.Reloj == nil {
		p.Reloj = time.Now
	}
	if p.Registro == nil {
		p.Registro = slog.New(slog.NewTextHandler(os.Stderr, nil))
	}
	if p.Dormir == nil {
		p.Dormir = dormir
	}
	return nil
}

// dormir espera `d` o hasta que el contexto termine. Devuelve false si termino.
func dormir(ctx context.Context, d time.Duration) bool {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-t.C:
		return true
	}
}

// Correr revisa una vez y luego cada `Intervalo`, hasta que el contexto termine.
//
// La PRIMERA pasada es inmediata a proposito. Con la primera al cabo de un
// intervalo, un despliegue nuevo pasa su primera hora sin vigilar y nadie lo
// nota, porque no hay nada que mirar para notarlo.
func (p *Planificador) Correr(ctx context.Context) error {
	if err := p.preparar(); err != nil {
		return err
	}
	p.Registro.Info("vigilancia en marcha",
		"intervalo", p.Intervalo.String(), "bitacora", p.Bitacora,
		"reintentos", p.Reintentos)
	for {
		p.UnaPasada(ctx)
		// Hasta un diez por ciento de desviacion, para que N instancias no
		// despierten en el mismo segundo y le caigan encima al motor a la vez.
		desviacion := time.Duration(rand.Int63n(int64(p.Intervalo/10) + 1))
		if !p.Dormir(ctx, p.Intervalo+desviacion) {
			p.Registro.Info("vigilancia parada", "pasadas", p.Pasadas())
			return ctx.Err()
		}
	}
}

// UnaPasada revisa el espacio entero una vez y entrega lo que salga.
//
// No devuelve error. Un fallo de un cliente no puede parar la pasada -- si no,
// el primer almacen corrupto deja sin aviso a todos los de detras -- y un fallo
// de entrega no puede parar las demas entregas. Todo se registra, y lo que no
// se pudo entregar queda en `Fallidos`.
func (p *Planificador) UnaPasada(ctx context.Context) {
	if err := p.preparar(); err != nil {
		p.Registro.Error("la pasada no se puede correr", "error", err)
		return
	}
	empezo := p.Reloj()
	avisos, fallos := p.revisarTodos(ctx, empezo)

	for _, e := range fallos {
		// Un cliente que no se pudo revisar NO es un cliente sin nada que
		// avisar. Se dice, y se anota en la bitacora con su nombre.
		p.Registro.Error("no se pudo revisar a un cliente", "error", e.Error())
		p.anotar(map[string]any{
			"tipo": "fallo_de_revision", "cuando": empezo.UTC().Format(time.RFC3339),
			"error": e.Error()})
	}

	entregados, perdidos := 0, 0
	for _, a := range avisos {
		if p.entregarConReintentos(ctx, a) {
			entregados++
			continue
		}
		perdidos++
		p.mu.Lock()
		p.perdidos++
		p.fallidos = append(p.fallidos, a)
		if sobran := len(p.fallidos) - _ULTIMOS_FALLIDOS; sobran > 0 {
			// Se tira por DELANTE: lo que le interesa a quien mira el estado
			// de salud es lo ultimo que fallo, no lo de hace tres meses.
			p.fallidos = append([]Aviso(nil), p.fallidos[sobran:]...)
		}
		p.mu.Unlock()
	}

	p.mu.Lock()
	p.pasadas++
	pasada := p.pasadas
	p.mu.Unlock()

	p.anotar(map[string]any{
		"tipo": "pasada", "n": pasada,
		"cuando":   empezo.UTC().Format(time.RFC3339),
		"duracion": p.Reloj().Sub(empezo).String(),
		// Se anotan las cuatro cifras aunque sean cero. Una bitacora que solo
		// escribe cuando hay algo no distingue «no habia nada» de «no se miro».
		"avisos": len(avisos), "entregados": entregados,
		"no_entregados": perdidos, "clientes_con_fallo": len(fallos),
	})
	p.Registro.Info("pasada de vigilancia", "n", pasada, "avisos", len(avisos),
		"entregados", entregados, "no_entregados", perdidos,
		"clientes_con_fallo", len(fallos))
}

func (p *Planificador) entregarConReintentos(ctx context.Context, a Aviso) bool {
	espera := p.EsperaBase
	for intento := 1; intento <= p.Reintentos; intento++ {
		err := p.Entregar(ctx, a)
		p.anotar(map[string]any{
			"tipo": "entrega", "cliente": a.Cliente, "intento": intento,
			"cuando":    p.Reloj().UTC().Format(time.RFC3339),
			"controles": a.Controles,
			"resultado": siONo(err), "error": textoDe(err)})
		if err == nil {
			return true
		}
		if intento == p.Reintentos {
			break
		}
		if !p.Dormir(ctx, espera) {
			return false
		}
		espera *= 2
	}
	p.Registro.Error("aviso NO entregado tras agotar los intentos",
		"cliente", a.Cliente, "intentos", p.Reintentos, "controles", a.Controles)
	p.anotar(map[string]any{
		"tipo": "no_entregado", "cliente": a.Cliente,
		"cuando":    p.Reloj().UTC().Format(time.RFC3339),
		"controles": a.Controles})
	return false
}

func siONo(err error) string {
	if err == nil {
		return "entregado"
	}
	return "fallo"
}

func textoDe(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}

// anotar anade una linea a la bitacora. No revienta: una bitacora que no se
// puede escribir no puede impedir que la vigilancia corra, pero SI se dice.
func (p *Planificador) anotar(linea map[string]any) {
	if p.Bitacora == "" {
		return
	}
	crudo, err := json.Marshal(linea)
	if err != nil {
		p.Registro.Error("no se pudo serializar una linea de bitacora", "error", err)
		return
	}
	if err := os.MkdirAll(filepath.Dir(p.Bitacora), 0o700); err != nil {
		p.Registro.Error("no se pudo crear la bitacora", "error", err)
		return
	}
	f, err := os.OpenFile(p.Bitacora, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		p.Registro.Error("no se pudo abrir la bitacora", "error", err)
		return
	}
	defer f.Close()
	if _, err := f.Write(append(crudo, '\n')); err != nil {
		p.Registro.Error("no se pudo escribir en la bitacora", "error", err)
	}
}

// EntregaAlRegistro es la entrega por omision: escribe el aviso en el registro
// del servidor.
//
// NO es una entrega de verdad y por eso se llama asi. Existe para que el
// planificador pueda arrancar sin un destino configurado sin caer en lo de
// antes -- que era no arrancar en absoluto -- y para que quede constancia de
// que el aviso se produjo. Quien la use tiene que saber que nadie recibe nada:
// el arranque lo dice con estas palabras.
func EntregaAlRegistro(r *slog.Logger) Entrega {
	return func(_ context.Context, a Aviso) error {
		r.Warn("AVISO DE VENCIMIENTO sin destino configurado: nadie lo recibe",
			"cliente", a.Cliente, "controles", a.Controles,
			"cuando", a.Cuando.UTC().Format(time.RFC3339))
		return nil
	}
}
