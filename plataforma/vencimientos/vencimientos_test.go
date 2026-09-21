package vencimientos

import (
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"actaira.com/plataforma/cliente"
	"actaira.com/plataforma/motor"
)

func TestUnAvisoVacioNoSeEnvia(t *testing.T) {
	// Un aviso vacio enviado igualmente ensena a la gente a archivar los
	// avisos sin leerlos, y entonces el que importa tampoco se lee.
	if (Aviso{}).HayQueAvisar() {
		t.Error("sin controles no hay nada que avisar")
	}
	if !(Aviso{Controles: []string{"ACT-C-009"}}).HayQueAvisar() {
		t.Error("con controles si hay que avisar")
	}
}

// preparar deja un cliente con evidencia de verdad, escrita por el motor.
func preparar(t *testing.T) (*Revisor, string, time.Time) {
	t.Helper()
	binario, err := exec.LookPath("actaira")
	if err != nil {
		t.Skip("el binario `actaira` no esta instalado en este entorno")
	}
	fixture := os.Getenv("ACTAIRA_FIXTURE")
	if fixture == "" {
		t.Skip("sin ACTAIRA_FIXTURE no hay repositorio de ejemplo")
	}
	raiz := t.TempDir()
	esp, err := cliente.AbrirEspacio(filepath.Join(raiz, "clientes"))
	if err != nil {
		t.Fatal(err)
	}
	c, err := esp.De("acme")
	if err != nil {
		t.Fatal(err)
	}
	t0 := time.Date(2027, 12, 2, 10, 0, 0, 0, time.UTC)

	// Un barrido de verdad, para que el almacen tenga evidencia fechada.
	cmd := exec.Command(binario, "vigilar", fixture, "--alto-riesgo", "si",
		"--almacen", c.Almacen(), "--ahora", t0.Format(time.RFC3339), "--registrar", "--json")
	if salida, err := cmd.CombinedOutput(); err != nil {
		if ee, vale := err.(*exec.ExitError); !vale || ee.ExitCode() != 3 {
			t.Fatalf("barrido: %v\n%s", err, salida)
		}
	}
	m, err := motor.Nuevo(binario, esp.Raiz, time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	return &Revisor{Espacio: esp, Motor: m, Idioma: "es"}, "acme", t0
}

func TestRecienBarridoNoHayNadaQueAvisar(t *testing.T) {
	r, id, t0 := preparar(t)
	a, err := r.Revisar(context.Background(), id, t0.Add(time.Hour))
	if err != nil {
		t.Fatal(err)
	}
	if a.HayQueAvisar() {
		t.Fatalf("nada deberia haber caducado en una hora: %v", a.Controles)
	}
}

func TestPasadaLaFrescuraSiHayQueAvisar(t *testing.T) {
	// El gemelo, y es la razon de existir del producto de suscripcion: nadie
	// ha empujado nada y aun asi hay algo que volver a mirar.
	r, id, t0 := preparar(t)
	a, err := r.Revisar(context.Background(), id, t0.AddDate(0, 0, 45))
	if err != nil {
		t.Fatal(err)
	}
	if !a.HayQueAvisar() {
		t.Fatal("a los 45 dias la evidencia de nivel maquina ya caduco")
	}
	if a.Estados["rancia"] == 0 {
		t.Errorf("se esperaba evidencia rancia: %v", a.Estados)
	}
	for _, c := range a.Controles {
		if a.Motivos[c] == "" {
			t.Errorf("%s: un aviso sin motivo no se puede atender", c)
		}
	}
}

func TestElRevisorNoInventaNingunVeredicto(t *testing.T) {
	r, id, t0 := preparar(t)
	a, err := r.Revisar(context.Background(), id, t0.AddDate(0, 0, 45))
	if err != nil {
		t.Fatal(err)
	}
	crudo, _ := json.Marshal(a)
	for _, prohibido := range []string{"cumple", "conforme", "aprobado", "%"} {
		if len(crudo) > 0 && containsFold(string(crudo), prohibido) {
			t.Errorf("el aviso no puede contener %q: %s", prohibido, crudo)
		}
	}
}

func containsFold(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		iguales := true
		for j := 0; j < len(sub); j++ {
			a, b := s[i+j], sub[j]
			if a >= 'A' && a <= 'Z' {
				a += 32
			}
			if b >= 'A' && b <= 'Z' {
				b += 32
			}
			if a != b {
				iguales = false
				break
			}
		}
		if iguales {
			return true
		}
	}
	return false
}
