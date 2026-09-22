package vencimientos

import (
	"context"
	"io"
	"log/slog"
	"sync"
	"testing"
	"time"
)

// LOS DOS METODOS PUBLICOS, A LA VEZ.
//
// `preparar` ESCRIBE campos del planificador -- los reintentos, la espera, el
// reloj, la forma de dormir -- y lo llaman `Correr` al empezar y `UnaPasada` en
// cada pasada. Los dos son exportados, asi que nada impide disparar una pasada
// suelta mientras el bucle corre. Ninguna otra prueba los llama a la vez, y por
// eso el detector de carreras no tenia nada que ver: una carrera que nadie
// ejecuta no la ve quien mira, la ve quien despliega.
func TestCorrerYUnaPasadaALaVezNoSePisan(t *testing.T) {
	p := &Planificador{
		// Lo demas se deja SIN rellenar a proposito: son justo los campos que
		// `preparar` escribe, y por tanto donde estaria la carrera.
		revisarTodos: func(context.Context, time.Time) ([]Aviso, []error) { return nil, nil },
		Entregar:     func(context.Context, Aviso) error { return nil },
		Intervalo:    time.Millisecond,
		Registro:     slog.New(slog.NewTextHandler(io.Discard, nil)),
	}
	ctx, parar := context.WithCancel(context.Background())
	arranque := make(chan struct{})
	var wg sync.WaitGroup
	wg.Add(2)
	go func() { defer wg.Done(); <-arranque; _ = p.Correr(ctx) }()
	go func() {
		defer wg.Done()
		<-arranque
		for i := 0; i < 200; i++ {
			p.UnaPasada(ctx)
		}
	}()
	close(arranque)
	time.Sleep(60 * time.Millisecond)
	parar()
	wg.Wait()
	if p.Pasadas() == 0 {
		t.Fatal("no corrio ninguna pasada: la prueba no llego a ejercitar nada")
	}
}
