package motor

import (
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"
	"time"
)

// enlazar crea un enlace a un directorio, o salta la prueba si el sistema no
// deja. En Windows `os.Symlink` necesita privilegio; una union (`mklink /J`) no,
// y para lo que aqui se comprueba -- que la resolucion sigue el enlace -- se
// comporta igual.
func enlazar(t *testing.T, destino, enlace string) {
	t.Helper()
	if err := os.Symlink(destino, enlace); err == nil {
		return
	}
	if runtime.GOOS != "windows" {
		t.Skipf("este sistema no deja crear enlaces")
	}
	if err := exec.Command("cmd", "/c", "mklink", "/J", enlace, destino).Run(); err != nil {
		t.Skipf("ni symlink ni union: %v", err)
	}
}

func TestUnEnlaceQueSaleDelEspacioDelClienteNoPasa(t *testing.T) {
	// EL ESCAPE, reproducido. `rutaSegura` comparaba cadenas: la ruta del
	// enlace cuelga de la raiz, luego «esta dentro», y el motor leia lo que
	// hubiera al otro lado. En una plataforma donde cada cliente tiene su
	// carpeta bajo la misma raiz, el otro lado es la carpeta de otro cliente.
	base := t.TempDir()
	otro := filepath.Join(base, "otro-cliente")
	if err := os.MkdirAll(otro, 0o700); err != nil {
		t.Fatal(err)
	}
	raiz := filepath.Join(base, "clientes")
	acme := filepath.Join(raiz, "acme")
	if err := os.MkdirAll(acme, 0o700); err != nil {
		t.Fatal(err)
	}
	trabajo := filepath.Join(acme, "trabajo")
	enlazar(t, otro, trabajo)

	m, err := Nuevo("actaira", raiz, time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := m.rutaSegura(trabajo); !errors.Is(err, ErrFueraDeAlcance) {
		t.Fatalf("el enlace paso la barrera de aislamiento: %v", err)
	}
}

func TestUnDirectorioDeVerdadDentroDelEspacioSiPasa(t *testing.T) {
	// La otra mitad. Cerrarlo rechazando todo seria igual de inutil, y ademas
	// es el fallo que de verdad se cuela en produccion: lo que no arranca se
	// arregla, lo que arranca de mas no.
	base := t.TempDir()
	raiz := filepath.Join(base, "clientes")
	trabajo := filepath.Join(raiz, "acme", "trabajo")
	if err := os.MkdirAll(trabajo, 0o700); err != nil {
		t.Fatal(err)
	}
	m, _ := Nuevo("actaira", raiz, time.Minute)
	if _, err := m.rutaSegura(trabajo); err != nil {
		t.Fatalf("un directorio normal del cliente no pasa: %v", err)
	}
}

func TestUnaRutaDeSalidaQueTodaviaNoExisteSeComprueba_Igual(t *testing.T) {
	// `filepath.EvalSymlinks` falla si la ruta no existe, y aqui se comprueban
	// tambien rutas de SALIDA: un `--almacen` que se va a crear, un `--sarif`
	// que todavia no esta. Si no comprobarlas fuera la salida facil, bastaria
	// con pedir la salida en una ruta inexistente para escribir donde sea.
	base := t.TempDir()
	raiz := filepath.Join(base, "clientes")
	if err := os.MkdirAll(filepath.Join(raiz, "acme"), 0o700); err != nil {
		t.Fatal(err)
	}
	m, _ := Nuevo("actaira", raiz, time.Minute)

	dentro := filepath.Join(raiz, "acme", "aun-no", "ev.jsonl")
	if _, err := m.rutaSegura(dentro); err != nil {
		t.Errorf("una salida futura DENTRO del espacio no pasa: %v", err)
	}
	fuera := filepath.Join(base, "aun-no", "ev.jsonl")
	if _, err := m.rutaSegura(fuera); !errors.Is(err, ErrFueraDeAlcance) {
		t.Errorf("una salida futura FUERA del espacio paso: %v", err)
	}
}

func TestUnHermanoConElMismoPrefijoNoCuentaComoDentro(t *testing.T) {
	// `/clientes/acme-malo` empieza por `/clientes/acme` y no esta dentro de el.
	// Por eso la comparacion es por componentes y no por prefijo de cadena.
	base := t.TempDir()
	acme := filepath.Join(base, "acme")
	vecino := filepath.Join(base, "acme-malo")
	for _, d := range []string{acme, vecino} {
		if err := os.MkdirAll(d, 0o700); err != nil {
			t.Fatal(err)
		}
	}
	m, _ := Nuevo("actaira", acme, time.Minute)
	if _, err := m.rutaSegura(vecino); !errors.Is(err, ErrFueraDeAlcance) {
		t.Fatalf("un hermano con el mismo prefijo paso: %v", err)
	}
}

func TestUnEnlaceEnUnARGUMENTOTampocoPasa(t *testing.T) {
	// `ArgumentosSeguros` comprueba toda ruta absoluta de la linea, no solo el
	// primer positional. Con la comparacion lexica, un `--almacen` apuntando a
	// un enlace habria escrito la evidencia de un cliente en el espacio de otro.
	base := t.TempDir()
	otro := filepath.Join(base, "otro-cliente")
	raiz := filepath.Join(base, "clientes")
	if err := os.MkdirAll(otro, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(raiz, "acme"), 0o700); err != nil {
		t.Fatal(err)
	}
	enlace := filepath.Join(raiz, "acme", "almacenes")
	enlazar(t, otro, enlace)

	m, _ := Nuevo("actaira", raiz, time.Minute)
	err := m.ArgumentosSeguros([]string{"--almacen", filepath.Join(enlace, "ev.jsonl")})
	if !errors.Is(err, ErrFueraDeAlcance) {
		t.Fatalf("un enlace en un argumento paso: %v", err)
	}
}
