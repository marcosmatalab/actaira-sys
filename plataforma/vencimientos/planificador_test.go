package vencimientos

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"
)

// El paquete `vencimientos` estaba escrito, probado y documentado como «el
// unico trabajo que la suscripcion hace de verdad», y NO CORRIA NUNCA: `main`
// construia el servidor con el revisor a `nil` y el campo no se leia en ningun
// sitio. Compilaba, sus pruebas pasaban, y el producto no lo invocaba.
//
// Estas pruebas van sobre el planificador que lo arranca, y cubren lo que hace
// falta para que «vigilancia» signifique algo: que corra sola, que no se calle
// lo que no pudo entregar, y que deje constancia tambien cuando no habia nada.

func silencio() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func lineas(t *testing.T, ruta string) []map[string]any {
	t.Helper()
	f, err := os.Open(ruta)
	if err != nil {
		t.Fatalf("no hay bitacora en %s: %v", ruta, err)
	}
	defer f.Close()
	var fuera []map[string]any
	s := bufio.NewScanner(f)
	for s.Scan() {
		var m map[string]any
		if err := json.Unmarshal(s.Bytes(), &m); err != nil {
			t.Fatalf("linea de bitacora ilegible: %v", err)
		}
		fuera = append(fuera, m)
	}
	return fuera
}

// revisorFalso sustituye al revisor de verdad: aqui se prueba el PLANIFICADOR,
// y un revisor real necesitaria el motor, el espacio y un almacen.
type revisorFalso struct {
	avisos []Aviso
	fallos []error
	veces  int32
}

func (r *revisorFalso) todos(context.Context, time.Time) ([]Aviso, []error) {
	atomic.AddInt32(&r.veces, 1)
	return r.avisos, r.fallos
}

// conRevisor arma un planificador cuyo `RevisarTodos` es el del falso. Se hace
// envolviendo el metodo en un Revisor con un Espacio y un Motor nulos: no se
// llega a usar ninguno porque `UnaPasada` solo llama a `RevisarTodos`, y por
// eso el planificador toma la funcion y no la estructura.
func conRevisor(f *revisorFalso, e Entrega) *Planificador {
	p := &Planificador{Entregar: e, Registro: silencio(), Reintentos: 3,
		EsperaBase: time.Microsecond}
	p.revisarTodos = f.todos
	return p
}

func TestUnaPasadaEntregaLosAvisosQueSalen(t *testing.T) {
	f := &revisorFalso{avisos: []Aviso{
		{Cliente: "acme", Controles: []string{"ACT-72-DRIFT"}},
		{Cliente: "beta", Controles: []string{"ACT-12-VERSION"}},
	}}
	var entregados int32
	p := conRevisor(f, func(context.Context, Aviso) error {
		atomic.AddInt32(&entregados, 1)
		return nil
	})
	p.UnaPasada(context.Background())

	if entregados != 2 {
		t.Fatalf("se entregaron %d de 2 avisos", entregados)
	}
	if p.Pasadas() != 1 {
		t.Fatalf("pasadas=%d", p.Pasadas())
	}
	if n := len(p.Fallidos()); n != 0 {
		t.Fatalf("hay %d fallidos y no deberia haber ninguno", n)
	}
}

func TestUnAvisoQueNoSePuedeEntregarNoSePierdeEnSILENCIO(t *testing.T) {
	// Es la prueba que importa. Un aviso perdido sin dejar rastro es peor que
	// no tener avisos: el cliente cree que le avisan y no le avisan.
	f := &revisorFalso{avisos: []Aviso{{Cliente: "acme", Controles: []string{"ACT-72-DRIFT"}}}}
	var intentos int32
	bitacora := filepath.Join(t.TempDir(), "vigilancia.jsonl")
	p := conRevisor(f, func(context.Context, Aviso) error {
		atomic.AddInt32(&intentos, 1)
		return errors.New("el destinatario no contesta")
	})
	p.Bitacora = bitacora
	p.UnaPasada(context.Background())

	if intentos != 3 {
		t.Errorf("se intento %d veces y los reintentos son 3", intentos)
	}
	fallidos := p.Fallidos()
	if len(fallidos) != 1 || fallidos[0].Cliente != "acme" {
		t.Fatalf("el aviso no quedo en la lista de fallidos: %v", fallidos)
	}

	var hayNoEntregado bool
	for _, l := range lineas(t, bitacora) {
		if l["tipo"] == "no_entregado" && l["cliente"] == "acme" {
			hayNoEntregado = true
		}
	}
	if !hayNoEntregado {
		t.Error("la bitacora no dice que ese aviso no se entrego")
	}
}

func TestLaBitacoraAnotaTAMBIENLasPasadasSinAvisos(t *testing.T) {
	// Una bitacora que solo escribe cuando hay algo no distingue «no habia
	// nada» de «no se miro», y esa distincion es de la que depende el producto
	// entero.
	f := &revisorFalso{}
	bitacora := filepath.Join(t.TempDir(), "vigilancia.jsonl")
	p := conRevisor(f, func(context.Context, Aviso) error { return nil })
	p.Bitacora = bitacora
	p.UnaPasada(context.Background())

	ls := lineas(t, bitacora)
	if len(ls) != 1 || ls[0]["tipo"] != "pasada" {
		t.Fatalf("se esperaba una linea de pasada, hay %v", ls)
	}
	if ls[0]["avisos"].(float64) != 0 {
		t.Errorf("la pasada dice %v avisos", ls[0]["avisos"])
	}
}

func TestUnClienteQueFallaNoDejaSinAvisoALosDemas_YSeDICE(t *testing.T) {
	f := &revisorFalso{
		avisos: []Aviso{{Cliente: "beta", Controles: []string{"ACT-12-VERSION"}}},
		fallos: []error{errors.New("cliente acme: el almacen no verifica")},
	}
	var entregados int32
	bitacora := filepath.Join(t.TempDir(), "vigilancia.jsonl")
	p := conRevisor(f, func(context.Context, Aviso) error {
		atomic.AddInt32(&entregados, 1)
		return nil
	})
	p.Bitacora = bitacora
	p.UnaPasada(context.Background())

	if entregados != 1 {
		t.Errorf("el fallo de un cliente impidio avisar a otro: %d entregados", entregados)
	}
	var hayFallo bool
	for _, l := range lineas(t, bitacora) {
		if l["tipo"] == "fallo_de_revision" {
			hayFallo = true
		}
	}
	if !hayFallo {
		t.Error("un cliente que no se pudo revisar NO es un cliente sin nada que avisar, " +
			"y la bitacora no lo dice")
	}
}

func TestUnPlanificadorSinDestinoDeEntregaSeNIEGA(t *testing.T) {
	// Un planificador que revisa y no entrega es la misma clase de fallo que
	// este fichero existe para arreglar, una capa mas arriba: algo que parece
	// vigilancia y no avisa a nadie.
	p := &Planificador{Revisor: &Revisor{}, Registro: silencio()}
	if err := p.Correr(context.Background()); !errors.Is(err, ErrSinEntrega) {
		t.Fatalf("arranco sin destino de entrega: %v", err)
	}
}

func TestCorrerRevisaINMEDIATAMENTEYLuegoCadaIntervalo(t *testing.T) {
	// La primera pasada es inmediata a proposito: con la primera al cabo de un
	// intervalo, un despliegue nuevo pasa su primera hora sin vigilar y nadie
	// lo nota, porque no hay nada que mirar para notarlo.
	f := &revisorFalso{}
	p := conRevisor(f, func(context.Context, Aviso) error { return nil })
	p.Intervalo = time.Hour

	esperas := 0
	ctx, parar := context.WithCancel(context.Background())
	p.Dormir = func(context.Context, time.Duration) bool {
		esperas++
		if esperas >= 3 {
			parar()
			return false
		}
		return true
	}
	_ = p.Correr(ctx)

	if p.Pasadas() != 3 {
		t.Fatalf("dio %d pasadas con 3 esperas", p.Pasadas())
	}
	if atomic.LoadInt32(&f.veces) != 3 {
		t.Fatalf("reviso %d veces", f.veces)
	}
}
