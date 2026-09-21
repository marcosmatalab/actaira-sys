package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"

	"actaira.com/plataforma/cliente"
	"actaira.com/plataforma/motor"
)

const TOKEN = "un-token-suficientemente-largo-para-acme"
const OTRO = "otro-token-suficientemente-largo-para-beta"

func elMotor(t *testing.T) string {
	t.Helper()
	if ruta, err := exec.LookPath("actaira"); err == nil {
		return ruta
	}
	t.Skip("el binario `actaira` no esta instalado en este entorno")
	return ""
}

// montar deja un servidor con dos clientes y una copia del repositorio de
// prueba dentro del espacio de acme.
func montar(t *testing.T) (*Servidor, string) {
	t.Helper()
	raiz := t.TempDir()
	esp, err := cliente.AbrirEspacio(filepath.Join(raiz, "clientes"))
	if err != nil {
		t.Fatal(err)
	}
	m, err := motor.Nuevo("actaira", esp.Raiz, 3*time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	cred, err := DeMapa(map[string]string{TOKEN: "acme", OTRO: "beta"})
	if err != nil {
		t.Fatal(err)
	}
	registro := slog.New(slog.NewTextHandler(new(bytes.Buffer), nil))
	s, err := Nuevo(m, esp, nil, cred, registro)
	if err != nil {
		t.Fatal(err)
	}
	return s, esp.Raiz
}

func conRepositorio(t *testing.T, raizDeClientes string) {
	t.Helper()
	fixture := os.Getenv("ACTAIRA_FIXTURE")
	if fixture == "" {
		t.Skip("sin ACTAIRA_FIXTURE no hay repositorio de prueba que barrer")
	}
	destino := filepath.Join(raizDeClientes, "acme", "trabajo")
	if err := os.MkdirAll(filepath.Dir(destino), 0o750); err != nil {
		t.Fatal(err)
	}
	if out, err := exec.Command("cp", "-r", fixture, destino).CombinedOutput(); err != nil {
		t.Fatalf("copiando el fixture: %v: %s", err, out)
	}
}

func pedir(t *testing.T, s *Servidor, metodo, ruta, token, cuerpo string) *httptest.ResponseRecorder {
	t.Helper()
	var cuerpoLector *strings.Reader
	if cuerpo == "" {
		cuerpoLector = strings.NewReader("")
	} else {
		cuerpoLector = strings.NewReader(cuerpo)
	}
	r := httptest.NewRequest(metodo, ruta, cuerpoLector)
	if token != "" {
		r.Header.Set("Authorization", "Bearer "+token)
	}
	w := httptest.NewRecorder()
	s.Rutas().ServeHTTP(w, r)
	return w
}

// --- lo que no se arranca -------------------------------------------------

func TestSinCredencialesNoSeArranca(t *testing.T) {
	// No hay modo abierto «para desarrollo»: un servidor que ejecuta procesos
	// y lee expedientes de varios clientes no puede tener un estado por
	// defecto permisivo, porque ese estado acaba en produccion un viernes.
	esp, _ := cliente.AbrirEspacio(t.TempDir())
	m, _ := motor.Nuevo("actaira", esp.Raiz, time.Minute)
	if _, err := Nuevo(m, esp, nil, nil, nil); err != ErrSinCredenciales {
		t.Fatalf("se esperaba ErrSinCredenciales, salio %v", err)
	}
	if _, err := DeMapa(map[string]string{}); err != ErrSinCredenciales {
		t.Fatalf("un mapa vacio tampoco: %v", err)
	}
}

func TestUnFicheroDeCredencialesQueLeeCualquieraSeRechaza(t *testing.T) {
	// El caso que de verdad pasa: alguien copia el fichero a un servidor, se
	// le queda 0644, y nadie vuelve a mirarlo nunca.
	//
	// La prueba se parte por sistema porque la PREGUNTA es distinta en cada
	// uno, no porque en uno sea mas floja. En POSIX los bits informan y se
	// exige que el rechazo venga de ellos. En Windows no informan, y lo que se
	// exige es que el servidor se niegue a arrancar diciendo que no puede
	// saberlo -- que es el tercer estado -- en vez de dar por buenos unos bits
	// que Go sintetiza.
	ruta := filepath.Join(t.TempDir(), "cred.json")
	cuerpo := []byte(`{"` + TOKEN + `":"acme"}`)
	if err := os.WriteFile(ruta, cuerpo, 0o644); err != nil {
		t.Fatal(err)
	}
	if runtime.GOOS == "windows" {
		_, err := CargarCredenciales(ruta)
		if !errors.Is(err, ErrPermisosIndeterminables) {
			t.Fatalf("se esperaba el tercer estado, salio %v", err)
		}
		if !strings.Contains(err.Error(), VariableDeAfirmacion) {
			t.Fatalf("el mensaje tiene que decir como afirmarlo, salio %v", err)
		}
		t.Setenv(VariableDeAfirmacion, "1")
		if _, err := CargarCredenciales(ruta); err != nil {
			t.Fatalf("con la afirmacion del operador tiene que cargar: %v", err)
		}
		return
	}
	if _, err := CargarCredenciales(ruta); err == nil ||
		!strings.Contains(err.Error(), "0600") {
		t.Fatalf("se esperaba una negativa por permisos, salio %v", err)
	}
	if err := os.Chmod(ruta, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := CargarCredenciales(ruta); err != nil {
		t.Fatalf("con 0600 tiene que cargar: %v", err)
	}
}

func TestLaAfirmacionDelOperadorNoSirveDeAtajoDondeSiSePuedeMedir(t *testing.T) {
	// La pregunta adversarial sobre el arreglo anterior: una via de escape que
	// valga en TODOS los sistemas no es un tercer estado, es un interruptor
	// para apagar el control. En POSIX los bits se pueden leer, asi que la
	// variable no puede tener ningun efecto: un 0644 se rechaza igual.
	if runtime.GOOS == "windows" {
		t.Skip("aqui los bits no informan y la afirmacion es la unica salida")
	}
	ruta := filepath.Join(t.TempDir(), "cred.json")
	if err := os.WriteFile(ruta, []byte(`{"`+TOKEN+`":"acme"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv(VariableDeAfirmacion, "1")
	if _, err := CargarCredenciales(ruta); err == nil ||
		!strings.Contains(err.Error(), "0600") {
		t.Fatalf("la afirmacion apago el control donde SI se puede medir: %v", err)
	}
}

func TestUnTokenCortoNoSeAvisa_SeRechaza(t *testing.T) {
	ruta := filepath.Join(t.TempDir(), "cred.json")
	if runtime.GOOS == "windows" {
		t.Setenv(VariableDeAfirmacion, "1")
	}
	_ = os.WriteFile(ruta, []byte(`{"corto":"acme"}`), 0o600)
	if _, err := CargarCredenciales(ruta); err == nil ||
		!strings.Contains(err.Error(), "24") {
		t.Fatalf("se esperaba una negativa por longitud, salio %v", err)
	}
}

// --- aislamiento ----------------------------------------------------------

func TestSinCredencialNoSePasa(t *testing.T) {
	s, _ := montar(t)
	for _, caso := range []struct{ token, nombre string }{
		{"", "sin cabecera"}, {"inventado", "un token que no existe"},
	} {
		w := pedir(t, s, "POST", "/v1/clientes/acme/plan", caso.token, "")
		if w.Code != http.StatusUnauthorized {
			t.Errorf("%s: salio %d", caso.nombre, w.Code)
		}
	}
}

func TestLaCredencialDeUnClienteNoSirveParaOtro(t *testing.T) {
	s, _ := montar(t)
	w := pedir(t, s, "POST", "/v1/clientes/acme/plan", OTRO, "")
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("salio %d", w.Code)
	}
	// Y sale 401, no 403: un 403 confirmaria que ese cliente existe, y con eso
	// se enumera la lista de clientes de la plataforma probando nombres.
	if strings.Contains(w.Body.String(), "acme") {
		t.Errorf("la respuesta nombra al cliente que se pidio: %s", w.Body.String())
	}
}

func TestLaRespuestaDeNoAutorizadoEsLaMISMA(t *testing.T) {
	// El gemelo del anterior. Dos cuerpos distintos para «token que no existe»
	// y «token de otro cliente» son un oraculo: se distingue un cliente que
	// existe de uno que no sin tener credencial de ninguno.
	s, _ := montar(t)
	a := pedir(t, s, "POST", "/v1/clientes/acme/plan", "inventado-pero-largo-de-verdad", "")
	b := pedir(t, s, "POST", "/v1/clientes/acme/plan", OTRO, "")
	if a.Body.String() != b.Body.String() || a.Code != b.Code {
		t.Errorf("respuestas distintas:\n  %s\n  %s", a.Body.String(), b.Body.String())
	}
}

// --- el codigo de salida no es un estado HTTP ----------------------------

func TestTresSaleComo200ConElCodigoDentro(t *testing.T) {
	elMotor(t)
	s, raiz := montar(t)
	conRepositorio(t, raiz)
	w := pedir(t, s, "POST", "/v1/clientes/acme/plan", TOKEN,
		`{"roles":["proveedor"],"alto_riesgo":"si","via_anexo":"anexo_iii","fecha":"2027-12-02"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("salio %d: %s", w.Code, w.Body.String())
	}
	var r Respuesta
	if err := json.Unmarshal(w.Body.Bytes(), &r); err != nil {
		t.Fatal(err)
	}
	if r.Codigo == 0 {
		t.Skip("este fixture sale limpio; el caso que importa es el de codigo 3")
	}
	if r.Codigo != 1 && r.Codigo != 3 {
		t.Fatalf("codigo inesperado %d", r.Codigo)
	}
	if r.Completo {
		t.Error("con codigo distinto de 0 no esta completo")
	}
	if r.Documento == nil || r.Documento["esquema"] == nil {
		t.Error("el documento del motor tiene que viajar entero, con su esquema dentro")
	}
}

// --- LA regla: la API traduce transporte, nunca significado ---------------

func TestElDocumentoEsElMISMOQueSaleDeLaLineaDeMandatos(t *testing.T) {
	// Es la propiedad entera de este paquete. En cuanto la API pueda producir
	// una conclusion que la linea de mandatos no produce, hay dos motores: el
	// que se audita y el que contesta al frontend.
	binario := elMotor(t)
	s, raiz := montar(t)
	conRepositorio(t, raiz)
	trabajo := filepath.Join(raiz, "acme", "trabajo")

	w := pedir(t, s, "POST", "/v1/clientes/acme/plan", TOKEN,
		`{"roles":["proveedor"],"alto_riesgo":"si","via_anexo":"anexo_iii","fecha":"2027-12-02"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("salio %d: %s", w.Code, w.Body.String())
	}
	var porHttp Respuesta
	if err := json.Unmarshal(w.Body.Bytes(), &porHttp); err != nil {
		t.Fatal(err)
	}

	ctx, cancelar := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancelar()
	cmd := exec.CommandContext(ctx, binario, "plan", trabajo,
		"--alto-riesgo", "si", "--fecha", "2027-12-02", "--idioma", "es",
		"--rol", "proveedor", "--via-anexo", "anexo_iii", "--json")
	salida, _ := cmd.Output()
	var porLinea map[string]any
	if err := json.Unmarshal(salida, &porLinea); err != nil {
		t.Fatalf("la linea de mandatos no devolvio JSON: %v", err)
	}
	if !reflect.DeepEqual(porHttp.Documento, porLinea) {
		t.Error("el documento de la API no es el de la linea de mandatos: hay dos motores")
	}
}

func TestNingunaRutaInventaUnVerboQueElMotorNoTiene(t *testing.T) {
	// Anadir aqui un verbo que la linea de mandatos no tenga seria empezar el
	// segundo motor por el sitio mas facil de no notar.
	binario := elMotor(t)
	ayuda, err := exec.Command(binario, "--help").Output()
	if err != nil {
		t.Fatal(err)
	}
	texto := string(ayuda)
	for _, v := range VERBOS {
		primero := strings.Fields(v["verbo"])[0]
		if !strings.Contains(texto, primero) {
			t.Errorf("la API expone %q y el motor no lo tiene", primero)
		}
	}
}

func TestNingunaRespuestaDeLaApiAfirmaCumplimiento(t *testing.T) {
	// La primera negativa de la casa, comprobada en la capa por la que sale
	// todo. Un sobre que anadiera «conforme» seria justo el pliegue que el
	// motor lleva doce fases evitando.
	s, _ := montar(t)
	for _, ruta := range []string{"/salud", "/v1/verbos"} {
		w := pedir(t, s, "GET", ruta, TOKEN, "")
		cuerpo := strings.ToLower(w.Body.String())
		for _, prohibida := range []string{"cumple", "conforme", "compliant",
			"puntuacion", "score", "porcentaje"} {
			if strings.Contains(cuerpo, prohibida) {
				t.Errorf("%s: aparece %q", ruta, prohibida)
			}
		}
	}
}

// --- el perfil se valida, no se adivina -----------------------------------

func TestUnPerfilQueNoSeEntiendeSeRechazaEnVezDeAdivinarse(t *testing.T) {
	s, _ := montar(t)
	casos := map[string]string{
		"un rol que no existe": `{"roles":["dueno"]}`,
		"un tri que no es tri": `{"alto_riesgo":"quiza"}`,
		"una fecha que no es":  `{"fecha":"el martes"}`,
		"un anexo inventado":   `{"via_anexo":"anexo_vii"}`,
		"un campo desconocido": `{"presupuesto":10}`,
	}
	for nombre, cuerpo := range casos {
		w := pedir(t, s, "POST", "/v1/clientes/acme/plan", TOKEN, cuerpo)
		if w.Code != http.StatusBadRequest {
			t.Errorf("%s: salio %d, se esperaba 400", nombre, w.Code)
		}
		var f Fallo
		_ = json.Unmarshal(w.Body.Bytes(), &f)
		if f.Que["es"] == "" || f.Que["en"] == "" {
			t.Errorf("%s: el fallo tiene que salir en los dos idiomas", nombre)
		}
	}
}

func TestUnPerfilVacioSiValeYEsDeliberado(t *testing.T) {
	// El gemelo. Un validador que lo rechace todo pasa el test anterior y hace
	// inutil la API: no saber todavia que eres es el estado con el que empieza
	// cualquiera, y el motor lo trata como «sin resolver», no como un error.
	p := Perfil{}
	args, err := p.aArgumentos()
	if err != nil {
		t.Fatalf("un perfil vacio tiene que valer: %v", err)
	}
	if len(args) != 0 {
		t.Errorf("y no anade argumentos: %v", args)
	}
}

// --- los dos idiomas ------------------------------------------------------

func TestElIdiomaSaleDeLaPeticionYNoDeUnaSuposicion(t *testing.T) {
	casos := []struct {
		url, cabecera, quiere string
	}{
		{"/x", "", "es"},
		{"/x?idioma=en", "", "en"},
		{"/x?idioma=es", "en-GB", "es"},
		{"/x", "en-GB,en;q=0.9", "en"},
		{"/x", "es-ES,es;q=0.9", "es"},
		// Un `fr-FR` que acabara en castellano porque es lo primero de la
		// lista seria peor que el castellano por defecto: nadie se daria
		// cuenta de que le contestaron en un idioma que no pidio.
		{"/x", "fr-FR,fr;q=0.9", "es"},
		{"/x?idioma=de", "", "es"},
	}
	for _, c := range casos {
		r := httptest.NewRequest("GET", c.url, nil)
		if c.cabecera != "" {
			r.Header.Set("Accept-Language", c.cabecera)
		}
		if hay := idiomaDe(r); hay != c.quiere {
			t.Errorf("%q + %q: salio %q, se esperaba %q", c.url, c.cabecera, hay, c.quiere)
		}
	}
}

// --- el empujon -----------------------------------------------------------

func cuerpoDeEmpujon(sha, origen string) string {
	return `{"ref":"refs/heads/main","after":"` + sha + `",` +
		`"before":"` + strings.Repeat("b", 40) + `",` +
		`"repository":{"clone_url":"https://github.com/x/` + origen + `.git",` +
		`"full_name":"x/` + origen + `"},` +
		`"commits":[{"added":[],"modified":["docs/a.png"],"removed":[]}]}`
}

func TestElCuerpoDelEventoNoPasaPorLaLineaDeMandatos(t *testing.T) {
	// Pasarlo como argumento habria metido el cuerpo de un tercero en la tabla
	// de procesos de la maquina, que la lee cualquiera con una sesion. Va por
	// fichero, y el fichero NO se queda: es el cuerpo de un tercero y no tiene
	// por que vivir en el espacio del cliente despues de haberse decidido.
	elMotor(t)
	s, raiz := montar(t)
	sha := strings.Repeat("a", 40)
	w := pedir(t, s, "POST", "/v1/clientes/acme/empujon", TOKEN, cuerpoDeEmpujon(sha, "y"))
	if w.Code != http.StatusOK {
		t.Fatalf("salio %d: %s", w.Code, w.Body.String())
	}
	var r Respuesta
	if err := json.Unmarshal(w.Body.Bytes(), &r); err != nil {
		t.Fatal(err)
	}
	// Que el motor leyera el cuerpo se demuestra porque lo que decide habla de
	// ESTE commit: si el fichero no hubiera llegado, no habria documento.
	if fmt.Sprint(r.Documento["decision"]) == "" {
		t.Errorf("sin decision: %v", r.Documento)
	}
	e, _ := r.Documento["empujon"].(map[string]any)
	if e == nil || e["referencia_inmutable"] != sha {
		t.Errorf("el motor no leyo este cuerpo: %v", r.Documento["empujon"])
	}
	restos, _ := filepath.Glob(filepath.Join(raiz, "acme", "empujon-*.json"))
	if len(restos) != 0 {
		t.Errorf("quedan cuerpos de terceros en el espacio del cliente: %v", restos)
	}
}

func TestDosEmpujonesALaVezNoSePisan(t *testing.T) {
	// Con un nombre de fichero fijo, dos empujones del mismo cliente a la vez
	// se pisaban y el motor podia decidir sobre el cuerpo del OTRO. Decidir
	// sobre un evento que no llego es peor que fallar, porque el resultado es
	// plausible y nadie lo mira.
	elMotor(t)
	s, _ := montar(t)
	shas := []string{strings.Repeat("a", 40), strings.Repeat("c", 40),
		strings.Repeat("d", 40), strings.Repeat("e", 40)}
	// El tope de concurrencia se sube a proposito para que los cuatro corran a
	// la vez. Lo que esta prueba mide es la COLISION de ficheros entre dos
	// empujones simultaneos; con el tope por omision (dos), dos de los cuatro
	// se rechazarian con 429 y la prueba dejaria de medir aquello para lo que
	// se escribio. El comportamiento del tope se prueba aparte, en
	// `TestUnEmpujonPorEncimaDelTopeSeRECHAZA_NoSeContestaMal`.
	s.ConTopes(Tope{Global: len(shas), PorCliente: len(shas)})
	salidas := make([]string, len(shas))
	var espera sync.WaitGroup
	for i, sha := range shas {
		espera.Add(1)
		go func(i int, sha string) {
			defer espera.Done()
			w := pedir(t, s, "POST", "/v1/clientes/acme/empujon", TOKEN,
				cuerpoDeEmpujon(sha, "y"))
			var r Respuesta
			_ = json.Unmarshal(w.Body.Bytes(), &r)
			if e, ok := r.Documento["empujon"].(map[string]any); ok {
				salidas[i] = fmt.Sprint(e["referencia_inmutable"])
			}
		}(i, sha)
	}
	espera.Wait()
	for i, sha := range shas {
		if salidas[i] != sha {
			t.Errorf("la peticion %d pidio %s y le contestaron sobre %q", i, sha[:8], salidas[i])
		}
	}
}

func TestUnaRutaEnLOSARGUMENTOSTambienPasaLaBarrera(t *testing.T) {
	// La barrera solo miraba el primer positional, asi que dependia de que
	// ninguna ruta del API acabara nunca en `args`. Una barrera que descansa
	// en que quien llama se acuerde no es una barrera: el dia que se olvide,
	// no falla nada.
	raiz := t.TempDir()
	m, err := motor.Nuevo("actaira", filepath.Join(raiz, "clientes"), time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	_, err = m.Ejecutar(context.Background(),
		"vigilar", filepath.Join(raiz, "clientes", "acme"),
		"--almacen", filepath.Join(raiz, "de-otro", "evidencia.jsonl"))
	if !errors.Is(err, motor.ErrFueraDeAlcance) {
		t.Fatalf("se esperaba ErrFueraDeAlcance y salio %v", err)
	}
}

func TestPeroUnaRutaDelPROPIOClienteEnLosArgumentosSiPasa(t *testing.T) {
	// El gemelo. Una barrera que rechace toda ruta absoluta pasa el test
	// anterior y deja la plataforma sin poder pasarle su propio almacen.
	raiz := t.TempDir()
	m, _ := motor.Nuevo("actaira", filepath.Join(raiz, "clientes"), time.Minute)
	if err := m.ArgumentosSeguros([]string{
		"--almacen", filepath.Join(raiz, "clientes", "acme", "evidencia.jsonl"),
		"--idioma", "es"}); err != nil {
		t.Fatalf("la ruta del propio cliente tiene que pasar: %v", err)
	}
}

func TestLasCuatroRutasContestanConUnDocumento(t *testing.T) {
	// Lo que encontro la pasada adversarial: `noconformidades` salia 502
	// porque su primer positional es la ACCION y no una ruta. Las pruebas de
	// esta capa corrian sin binario, asi que nadie lo vio hasta probar las
	// rutas una por una contra el motor de verdad.
	elMotor(t)
	s, raiz := montar(t)
	conRepositorio(t, raiz)
	casos := []struct{ metodo, ruta, cuerpo string }{
		{"POST", "/v1/clientes/acme/plan", `{"alto_riesgo":"si","fecha":"2027-12-02"}`},
		{"POST", "/v1/clientes/acme/vigilar", `{"alto_riesgo":"si","fecha":"2027-12-02"}`},
		{"GET", "/v1/clientes/acme/vencimientos", ""},
		{"GET", "/v1/clientes/acme/noconformidades", ""},
	}
	for _, c := range casos {
		w := pedir(t, s, c.metodo, c.ruta, TOKEN, c.cuerpo)
		if w.Code != http.StatusOK {
			t.Errorf("%s: salio %d — %s", c.ruta, w.Code, w.Body.String())
			continue
		}
		var r Respuesta
		if err := json.Unmarshal(w.Body.Bytes(), &r); err != nil {
			t.Errorf("%s: %v", c.ruta, err)
			continue
		}
		if r.Documento == nil || r.Documento["esquema"] == nil {
			t.Errorf("%s: sin documento con esquema dentro", c.ruta)
		}
	}
}

func TestLaSaludNoPideCredencialPeroTampocoDiceNada(t *testing.T) {
	s, _ := montar(t)
	w := pedir(t, s, "GET", "/salud", "", "")
	if w.Code != http.StatusOK {
		t.Fatalf("salio %d", w.Code)
	}
	cuerpo := w.Body.String()
	for _, filtracion := range []string{"acme", "beta", TOKEN, "/tmp"} {
		if strings.Contains(cuerpo, filtracion) {
			t.Errorf("la salud filtra %q", filtracion)
		}
	}
}

func TestNingunaRutaMandaUnaBanderaQueSuVerboNoAcepta(t *testing.T) {
	// El contrato de documentos cubria las SALIDAS. Las entradas no las cubria
	// nadie, y tres rutas mandaban banderas que su verbo no acepta: el motor
	// contestaba con un error de uso y esta capa lo traducia a «el motor no
	// devolvio un documento que esta plataforma entienda», que es verdad y no
	// dice nada. Ahora la frontera se comprueba por los dos lados.
	binario := elMotor(t)
	for verbo, banderas := range BANDERAS {
		ayuda, err := exec.Command(binario, verbo, "--help").Output()
		if err != nil {
			t.Fatalf("%s --help: %v", verbo, err)
		}
		texto := string(ayuda)
		for _, bandera := range banderas {
			if !strings.Contains(texto, bandera) {
				t.Errorf("la API manda %q a `%s` y el verbo no la acepta", bandera, verbo)
			}
		}
	}
}

func TestYLaListaDeBanderasEsLaQueSeMandaDeVerdad(t *testing.T) {
	// El gemelo. Una lista que solo se comprueba contra el `--help` se queda
	// vieja en cuanto una ruta anada una bandera y nadie la apunte aqui, y
	// entonces la puerta pasa sin mirar lo que importa.
	fuente, err := os.ReadFile("api.go")
	if err != nil {
		t.Fatal(err)
	}
	texto := string(fuente)
	corte := strings.Index(texto, "var BANDERAS")
	rutas := texto[strings.Index(texto, "func (s *Servidor) plan("):]
	for _, bandera := range []string{"--almacen", "--idioma", "--ahora"} {
		if !strings.Contains(rutas, `"`+bandera+`"`) {
			t.Errorf("%q no aparece en ninguna ruta: sobra de la lista", bandera)
		}
	}
	if corte < 0 {
		t.Fatal("no esta la lista de banderas")
	}
}

func TestUnEmpujonPorEncimaDelTopeSeRECHAZA_NoSeContestaMal(t *testing.T) {
	// La otra mitad del tope de concurrencia, y la que de verdad importa para
	// un endpoint de ingesta: rechazar NO puede convertirse en contestar mal.
	//
	// Un webhook que recibe 429 con `Retry-After` no pierde el evento si quien
	// lo manda respeta la cabecera. Un webhook al que se le contesta sobre el
	// cuerpo de OTRO empujon si lo pierde, y ademas lo sustituye por una
	// respuesta plausible que nadie va a mirar.
	elMotor(t)
	s, _ := montar(t)
	s.ConTopes(Tope{Global: 1, PorCliente: 1})

	shas := []string{strings.Repeat("a", 40), strings.Repeat("b", 40),
		strings.Repeat("c", 40)}
	codigos := make([]int, len(shas))
	reintentar := make([]string, len(shas))
	referencias := make([]string, len(shas))
	var espera sync.WaitGroup
	for i, sha := range shas {
		espera.Add(1)
		go func(i int, sha string) {
			defer espera.Done()
			w := pedir(t, s, "POST", "/v1/clientes/acme/empujon", TOKEN,
				cuerpoDeEmpujon(sha, "y"))
			codigos[i] = w.Code
			reintentar[i] = w.Header().Get("Retry-After")
			var r Respuesta
			_ = json.Unmarshal(w.Body.Bytes(), &r)
			if e, ok := r.Documento["empujon"].(map[string]any); ok {
				referencias[i] = fmt.Sprint(e["referencia_inmutable"])
			}
		}(i, sha)
	}
	espera.Wait()

	rechazados := 0
	for i, sha := range shas {
		switch codigos[i] {
		case http.StatusTooManyRequests:
			rechazados++
			if reintentar[i] == "" {
				t.Errorf("la peticion %d se rechazo sin `Retry-After`: quien la manda "+
					"reintentaria en bucle y el tope se convertiria en una tormenta", i)
			}
			if referencias[i] != "" {
				t.Errorf("la peticion %d se rechazo Y contesto sobre %q", i, referencias[i])
			}
		default:
			// Si se contesta, se contesta sobre lo que se pidio. Siempre.
			if referencias[i] != sha {
				t.Errorf("la peticion %d pidio %s y le contestaron sobre %q",
					i, sha[:8], referencias[i])
			}
		}
	}
	if rechazados == 0 {
		t.Fatalf("con tope 1 y tres empujones a la vez no se rechazo ninguno: "+
			"el limitador no esta enchufado. Codigos: %v", codigos)
	}
	if rechazados == len(shas) {
		t.Fatalf("se rechazaron los tres: un tope que no deja pasar nada no es un tope")
	}
}
