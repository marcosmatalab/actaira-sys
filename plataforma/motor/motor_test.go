package motor

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// elMotor localiza el binario. Si no esta, los tests que lo necesitan se
// saltan: este paquete tiene que poder compilarse y probarse sin Python.
func elMotor(t *testing.T) string {
	t.Helper()
	if ruta, err := exec.LookPath("actaira"); err == nil {
		return ruta
	}
	t.Skip("el binario `actaira` no esta instalado en este entorno")
	return ""
}

func TestUnaRutaDeOtroClienteNoSeEjecuta(t *testing.T) {
	// La unica barrera de aislamiento de este paquete, y la que mas importa:
	// sin ella un cliente leeria el repositorio de otro con un `../`.
	raiz := t.TempDir()
	m, err := Nuevo("actaira", filepath.Join(raiz, "clientes"), time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	for _, mala := range []string{
		filepath.Join(raiz, "otro"),
		filepath.Join(raiz, "clientes", "..", "otro"),
		"/etc",
	} {
		if _, err := m.Ejecutar(context.Background(), "plan", mala); err != ErrFueraDeAlcance {
			t.Errorf("%s: se esperaba ErrFueraDeAlcance y salio %v", mala, err)
		}
	}
}

func TestUnaRutaDelPropioClienteSiPasaLaBarrera(t *testing.T) {
	// El gemelo. Una barrera que lo rechazara todo pasaria el test anterior y
	// no serviria para nada.
	raiz := t.TempDir()
	trabajo := filepath.Join(raiz, "clientes", "acme", "repo")
	if err := os.MkdirAll(trabajo, 0o755); err != nil {
		t.Fatal(err)
	}
	m, _ := Nuevo("actaira", filepath.Join(raiz, "clientes"), time.Minute)
	if _, err := m.rutaSegura(trabajo); err != nil {
		t.Fatalf("la ruta del propio cliente tiene que pasar: %v", err)
	}
}

func TestTresNoEsUnFallo(t *testing.T) {
	// El motor sale con 3 cuando falta contestar, falta firmar o hay algo que
	// volver a observar. Tratarlo como fallo marcaria en rojo el estado normal
	// de un cliente que empieza.
	r := Resultado{Codigo: 3}
	if r.Completo() {
		t.Error("tres no esta completo")
	}
	if !r.HayTrabajo() {
		t.Error("tres es trabajo, no error")
	}
	if (Resultado{Codigo: 0}).HayTrabajo() {
		t.Error("cero no es trabajo pendiente")
	}
}

func TestElPlanDeVerdadSeLeeYDeclaraSuEsquema(t *testing.T) {
	binario := elMotor(t)
	fixture := os.Getenv("ACTAIRA_FIXTURE")
	if fixture == "" {
		t.Skip("sin ACTAIRA_FIXTURE no hay repositorio de ejemplo que barrer")
	}
	raiz := filepath.Dir(fixture)
	m, err := Nuevo(binario, raiz, 2*time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	r, err := m.Ejecutar(context.Background(), "plan", fixture, "--alto-riesgo", "si",
		"--fecha", "2027-12-02")
	if err != nil {
		t.Fatalf("plan: %v", err)
	}
	if r.Esquema != "actaira/plan/v1" {
		t.Errorf("esquema inesperado: %q", r.Esquema)
	}
	if _, hay := r.Documento["lineas"]; !hay {
		t.Error("el plan tiene que traer sus lineas")
	}
	// Ninguna plataforma puede emitir un porcentaje que el motor no emite.
	if strings.Contains(strings.ToLower(r.Verbo), "%") {
		t.Error("imposible por construccion, pero queda escrito")
	}
}
