package api

import (
	"fmt"
	"testing"
	"time"
)

// Un verbo del motor arranca un PROCESO que lee el repositorio entero del
// cliente y puede tardar minutos, y no habia nada que limitara cuantos corren a
// la vez. N peticiones simultaneas eran N procesos, y como un solo binario
// sirve a todos los clientes, el que se quedaba sin maquina no era solo el que
// empujo.

func TestUnClienteNoPuedeOcuparLaMaquinaENTERA(t *testing.T) {
	// El tope por cliente es lo que hace que el global no sea del primero que
	// llegue. Sin el, un cliente con veinte peticiones deja a los demas fuera
	// aunque haya sitio reservado para ellos.
	l := nuevoLimitador(Tope{Global: 4, PorCliente: 2})

	var sueltas []func()
	for i := 0; i < 2; i++ {
		soltar, motivo := l.entrar("acme")
		if soltar == nil {
			t.Fatalf("acme no pudo entrar en su intento %d: %s", i+1, motivo)
		}
		sueltas = append(sueltas, soltar)
	}
	if soltar, motivo := l.entrar("acme"); soltar != nil {
		t.Fatal("acme paso de su propio tope")
	} else if motivo == "" {
		t.Error("se rechazo sin decir por que")
	}

	// Y queda sitio para OTRO cliente, que es el punto.
	soltar, motivo := l.entrar("beta")
	if soltar == nil {
		t.Fatalf("beta no pudo entrar aunque quedaban 2 huecos: %s", motivo)
	}
	sueltas = append(sueltas, soltar)

	for _, s := range sueltas {
		s()
	}
	if l.enCurso() != 0 {
		t.Fatalf("quedaron %d en curso tras soltarlos todos", l.enCurso())
	}
	if soltar, _ := l.entrar("acme"); soltar == nil {
		t.Fatal("tras soltar, acme sigue sin poder entrar")
	}
}

func TestElMotivoDelRechazoDiceCUALDeLosDosTopesSeLLENO(t *testing.T) {
	// «Demasiadas peticiones» no le dice a nadie que hacer. «Has llegado a tu
	// tope» y «la maquina esta al completo» piden cosas distintas: esperar tu
	// turno, o avisar a quien opera.
	l := nuevoLimitador(Tope{Global: 2, PorCliente: 1})
	a, _ := l.entrar("acme")
	b, _ := l.entrar("beta")
	if a == nil || b == nil {
		t.Fatal("no entraron los dos primeros")
	}
	if _, motivo := l.entrar("acme"); motivo == "" || !contiene(motivo, "tu tope") {
		t.Errorf("el motivo del tope por cliente no lo dice: %q", motivo)
	}
	if _, motivo := l.entrar("gamma"); motivo == "" || !contiene(motivo, "la maquina") {
		t.Errorf("el motivo del tope global no lo dice: %q", motivo)
	}
	a()
	b()
}

func TestElMapaDeClientesNoCreceParaSIEMPRE(t *testing.T) {
	// Un mapa que solo crece en un proceso que vive meses es una fuga.
	l := nuevoLimitador(Tope{Global: 100, PorCliente: 1})
	for i := 0; i < 50; i++ {
		soltar, _ := l.entrar(fmt.Sprintf("cliente-%d", i))
		if soltar == nil {
			t.Fatalf("no entro el cliente %d", i)
		}
		soltar()
	}
	if n := len(l.porCliente); n != 0 {
		t.Fatalf("quedaron %d entradas para clientes que ya no tienen nada en curso", n)
	}
}

// --- ritmo ----------------------------------------------------------------

func TestElRitmoSeAGOTAYSeRELLENAConElTiempo(t *testing.T) {
	ahora := time.Date(2027, 12, 2, 10, 0, 0, 0, time.UTC)
	r := nuevoRitmo(60, 3, func() time.Time { return ahora })

	for i := 0; i < 3; i++ {
		if !r.permite("acme") {
			t.Fatalf("la ficha %d no se dio y la punta es 3", i+1)
		}
	}
	if r.permite("acme") {
		t.Fatal("se dio una cuarta ficha con la punta agotada")
	}
	// Un minuto despues, sesenta fichas mas: se rellena hasta la punta.
	ahora = ahora.Add(time.Minute)
	if !r.permite("acme") {
		t.Fatal("no se relleno con el tiempo")
	}
}

func TestCadaCredencialTieneSuPropioCubo(t *testing.T) {
	// Si no, el cliente que mas llama silencia a los demas, que es el fallo que
	// el tope por cliente evita en la concurrencia y hay que evitar tambien
	// aqui.
	ahora := time.Now()
	r := nuevoRitmo(60, 2, func() time.Time { return ahora })
	r.permite("acme")
	r.permite("acme")
	if r.permite("acme") {
		t.Fatal("acme paso de su punta")
	}
	if !r.permite("beta") {
		t.Fatal("beta se quedo sin fichas porque acme gasto las suyas")
	}
}

func TestLosCubosViejosSeOLVIDAN(t *testing.T) {
	// `olvidar` estaba escrito y no lo llamaba nadie: codigo muerto que
	// aparentaba resolver la fuga que documentaba, que es peor que no tenerlo
	// porque quien lo lea da el problema por resuelto.
	ahora := time.Date(2027, 12, 2, 10, 0, 0, 0, time.UTC)
	r := nuevoRitmo(60, 2, func() time.Time { return ahora })
	for i := 0; i < 5; i++ {
		r.permite(fmt.Sprintf("viejo-%d", i))
	}
	ahora = ahora.Add(2 * time.Hour) // llenos y sin usar
	r.olvidar(ahora)
	if n := len(r.cubos); n != 0 {
		t.Fatalf("quedaron %d cubos llenos y sin tocar en dos horas", n)
	}
}

func contiene(s, sub string) bool {
	return len(s) >= len(sub) && (func() bool {
		for i := 0; i+len(sub) <= len(s); i++ {
			if s[i:i+len(sub)] == sub {
				return true
			}
		}
		return false
	})()
}
