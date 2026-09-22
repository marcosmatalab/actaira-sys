package api

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// Los roles salen del TESTIGO VERIFICADO y de ningun otro sitio. Un servidor
// que los lea de una cabecera deja que quien llama elija sus propios permisos,
// y ese fallo funciona perfectamente en todas las pruebas -- porque las pruebas
// mandan la cabecera correcta.

func servidorConEmisor(t *testing.T) (*Servidor, *rsa.PrivateKey, string) {
	t.Helper()
	s, raiz := montar(t)
	k, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	s.Emisor = &Emisor{
		Iss: "https://idp.example/acme", Aud: "actaira",
		Claves: map[string]crypto.PublicKey{"k1": &k.PublicKey},
	}
	s.Reloj = func() time.Time { return AHORA }
	return s, k, raiz
}

func conTestigo(t *testing.T, s *Servidor, metodo, ruta, testigo, cuerpo string) *httptest.ResponseRecorder {
	t.Helper()
	var lector *strings.Reader
	if cuerpo == "" {
		lector = strings.NewReader("")
	} else {
		lector = strings.NewReader(cuerpo)
	}
	r := httptest.NewRequest(metodo, ruta, lector)
	r.Header.Set("Authorization", "Bearer "+testigo)
	r.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	s.Rutas().ServeHTTP(w, r)
	return w
}

func testigoCon(t *testing.T, k *rsa.PrivateKey, cliente string, roles []string) string {
	t.Helper()
	c := cuerpoBueno()
	c["actaira_cliente"] = cliente
	c["roles"] = roles
	return firmarRS256(t, k, "k1", c)
}

func TestConSoloLecturaNoSePuedePedirUnaObservacion(t *testing.T) {
	// `plan` arranca un proceso que lee el repositorio entero y escribe
	// evidencia. Un auditor no tiene por que poder hacerlo, y sobre todo: no
	// tiene por que poder hacerlo sin querer.
	s, k, _ := servidorConEmisor(t)
	testigo := testigoCon(t, k, "acme", []string{PapelLectura})

	w := conTestigo(t, s, "POST", "/v1/clientes/acme/plan", testigo,
		`{"alto_riesgo":"si","fecha":"2027-12-02"}`)
	if w.Code != http.StatusForbidden {
		t.Fatalf("lectura pudo pedir un plan: %d — %s", w.Code, w.Body.String())
	}
	// Y el 403 DICE que falta, en vez de obligar a adivinar. Quien adivina
	// permisos acaba pidiendo el rol mas alto.
	if !strings.Contains(w.Body.String(), PapelObservacion) {
		t.Errorf("el 403 no dice que papel hace falta: %s", w.Body.String())
	}
}

func TestConSoloLecturaSiSePuedeLEER(t *testing.T) {
	s, k, _ := servidorConEmisor(t)
	testigo := testigoCon(t, k, "acme", []string{PapelLectura})
	w := conTestigo(t, s, "GET", "/v1/clientes/acme/noconformidades", testigo, "")
	if w.Code == http.StatusForbidden {
		t.Fatalf("lectura no pudo leer: %s", w.Body.String())
	}
}

func TestObservacionINCLUYELectura(t *testing.T) {
	// Pedir una observacion sin poder ver el resultado no tiene sentido, y
	// repartir los dos papeles por separado solo consigue que alguien se olvide
	// del segundo.
	s, k, _ := servidorConEmisor(t)
	testigo := testigoCon(t, k, "acme", []string{PapelObservacion})
	w := conTestigo(t, s, "GET", "/v1/clientes/acme/noconformidades", testigo, "")
	if w.Code == http.StatusForbidden {
		t.Fatalf("observacion no pudo leer: %s", w.Body.String())
	}
}

func TestSinNingunPapelNoSePuedeNada(t *testing.T) {
	s, k, _ := servidorConEmisor(t)
	testigo := testigoCon(t, k, "acme", nil)
	w := conTestigo(t, s, "GET", "/v1/clientes/acme/noconformidades", testigo, "")
	if w.Code != http.StatusForbidden {
		t.Fatalf("un testigo sin papeles paso: %d", w.Code)
	}
}

func TestUnPapelINVENTADONoDaPermisos(t *testing.T) {
	// El proveedor de identidad puede mandar cualquier cadena en `roles`. Lo
	// que no puede es que una cadena desconocida abra algo.
	s, k, _ := servidorConEmisor(t)
	testigo := testigoCon(t, k, "acme", []string{"superadministrador", "root", "*"})
	w := conTestigo(t, s, "GET", "/v1/clientes/acme/noconformidades", testigo, "")
	if w.Code != http.StatusForbidden {
		t.Fatalf("un papel inventado dio permisos: %d", w.Code)
	}
}

func TestElCLIENTESaleDelTestigoYNoDeLaRUTA(t *testing.T) {
	// EL ataque que importa en multi-cliente: un testigo legitimo de `acme`
	// pidiendo el expediente de `beta`.
	s, k, _ := servidorConEmisor(t)
	testigo := testigoCon(t, k, "acme", []string{PapelAdmin})
	w := conTestigo(t, s, "GET", "/v1/clientes/beta/noconformidades", testigo, "")
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("un testigo de acme leyo el expediente de beta: %d", w.Code)
	}
}

func TestUnaCabeceraDeROLESNoDaPermisos(t *testing.T) {
	// El fallo mas facil de cometer y el mas dificil de ver. Se manda un
	// testigo con `lectura` y ademas cabeceras que dicen `admin`: si alguna
	// capa las mirara, el 403 se convertiria en 200.
	s, k, _ := servidorConEmisor(t)
	testigo := testigoCon(t, k, "acme", []string{PapelLectura})

	r := httptest.NewRequest("POST", "/v1/clientes/acme/plan",
		strings.NewReader(`{"alto_riesgo":"si","fecha":"2027-12-02"}`))
	r.Header.Set("Authorization", "Bearer "+testigo)
	r.Header.Set("Content-Type", "application/json")
	for _, cabecera := range []string{
		"X-Roles", "X-Actaira-Roles", "X-User-Roles", "Roles",
		"X-Actaira-Cliente", "X-Cliente", "X-Tenant-Id",
	} {
		r.Header.Set(cabecera, PapelAdmin+",beta")
	}
	w := httptest.NewRecorder()
	s.Rutas().ServeHTTP(w, r)

	if w.Code != http.StatusForbidden {
		t.Fatalf("una cabecera de roles dio permisos: %d — %s", w.Code, w.Body.String())
	}
}

func TestUnVerboSinPermisoDECLARADONoPasa(t *testing.T) {
	// La eleccion contraria a la comoda. Si el valor por omision fuera «deja
	// pasar», una ruta nueva naceria sin permisos y nadie lo notaria; asi nace
	// sin funcionar, que se arregla en un minuto.
	if Puede([]string{PapelAdmin}, "un-verbo-que-no-existe") {
		t.Fatal("un verbo sin permiso declarado paso con admin")
	}
	if !strings.Contains(ExplicarNegativa(nil, "un-verbo-que-no-existe"), "declarado") {
		t.Error("la negativa no explica que el verbo no esta declarado")
	}
}

func TestTodoVerboQuePUBLICALaAPITienePermisoDeclarado(t *testing.T) {
	// El hueco por el que se cuela una ruta nueva: existe, se publica, y nadie
	// dijo quien puede pedirla. Con el valor por omision cerrado no seria un
	// agujero -- naceria bloqueada -- pero si una ruta que no funciona y que
	// alguien arreglara con prisa dandole `admin`.
	for _, v := range VERBOS {
		// Con la MISMA busqueda que usa el control, y no con `verboDe`. Con
		// `verboDe` esta prueba solo exigia una entrada por verbo, asi que una
		// tabla que declaraba de lectura un verbo con acciones que escriben
		// salia verde: era la prueba la que redondeaba la pregunta.
		if _, hay := papelPara(v["verbo"]); !hay {
			t.Errorf("la API publica %q y PERMISOS no dice que papel hace falta",
				v["verbo"])
		}
	}
}

// Y LO QUE ESCRIBE NO PUEDE PASAR POR LECTURA.
//
// `almacen` tiene `migrar`, que reescribe el almacen de evidencia entero, y
// `noconformidad` tiene `abrir` y `avanzar`, que mueven el ciclo. Ninguna de
// las tres se publica hoy. Esta prueba fija que, si alguna se publica, nazca
// SIN permiso en vez de heredar el de la accion que lee.
func TestLasAccionesQueEscribenNoHeredanElPermisoDeLeer(t *testing.T) {
	for _, accion := range []string{
		"almacen migrar", "noconformidad abrir", "noconformidad avanzar",
	} {
		if Puede([]string{PapelLectura}, accion) {
			t.Errorf("%q pasa con papel de lectura, y esa accion escribe", accion)
		}
		if _, hay := papelPara(accion); hay {
			t.Errorf("%q tiene permiso declarado sin que nadie lo publique: "+
				"declararlo aqui es decidir por quien anada esa ruta", accion)
		}
	}
	// Y las dos que si se publican siguen pasando con lectura.
	for _, accion := range []string{"almacen verificar", "noconformidad listar"} {
		if !Puede([]string{PapelLectura}, accion) {
			t.Errorf("%q dejo de pasar con papel de lectura", accion)
		}
	}
}

func TestSinEmisorNoHayPapelesYEsoNoBloqueaNada(t *testing.T) {
	// El modo de credenciales estaticas. Inventarle un papel por omision seria
	// peor de las dos maneras: con `admin` se salta el control, con `lectura`
	// deja de funcionar y nadie entiende por que.
	s, _ := montar(t)
	if s.Emisor != nil {
		t.Fatal("montar() no deberia configurar emisor")
	}
	w := pedir(t, s, "GET", "/v1/clientes/acme/noconformidades", TOKEN, "")
	if w.Code == http.StatusForbidden {
		t.Fatalf("el modo estatico se bloqueo a si mismo: %s", w.Body.String())
	}
}
