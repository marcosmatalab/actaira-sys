package cliente

import (
	"errors"
	"path/filepath"
	"testing"
)

func TestUnIdentificadorRaroSeRechazaYNoSeLimpia(t *testing.T) {
	// Limpiar deja la puerta abierta al siguiente que olvide limpiar.
	e, err := AbrirEspacio(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	for _, malo := range []string{"", ".", "..", "../otro", "a/b", "ACME", "x",
		"con espacio", "acme/../otro", "-acme", "acme-"} {
		if _, err := e.De(malo); !errors.Is(err, ErrIdentificadorInvalido) {
			t.Errorf("%q: se esperaba rechazo y salio %v", malo, err)
		}
	}
}

func TestUnIdentificadorNormalSiVale(t *testing.T) {
	// El gemelo: una validacion que lo rechaza todo pasa el test anterior.
	e, _ := AbrirEspacio(t.TempDir())
	for _, bueno := range []string{"acme", "acme-sl", "cliente-2027", "a1b"} {
		c, err := e.De(bueno)
		if err != nil {
			t.Fatalf("%q: %v", bueno, err)
		}
		if filepath.Base(c.Raiz) != bueno {
			t.Errorf("%q acabo en %q", bueno, c.Raiz)
		}
	}
}

func TestLaCarpetaDeUnClienteNoContieneLaDeOtro(t *testing.T) {
	e, _ := AbrirEspacio(t.TempDir())
	acme, _ := e.De("acme")
	otro, _ := e.De("otro")
	if acme.Contiene(otro.Raiz) {
		t.Fatal("un cliente no puede contener la carpeta de otro")
	}
	if acme.Contiene(filepath.Join(acme.Raiz, "..", "otro", "evidencia.jsonl")) {
		t.Fatal("un `..` no puede salir del cliente")
	}
	if !acme.Contiene(acme.Almacen()) {
		t.Fatal("su propio almacen si tiene que estar dentro")
	}
}

func TestTodosDevuelveSoloCarpetasConNombreValido(t *testing.T) {
	e, _ := AbrirEspacio(t.TempDir())
	e.De("acme")
	e.De("cliente-2027")
	ids, err := e.Todos()
	if err != nil {
		t.Fatal(err)
	}
	if len(ids) != 2 || ids[0] != "acme" || ids[1] != "cliente-2027" {
		t.Fatalf("inesperado: %v", ids)
	}
}
