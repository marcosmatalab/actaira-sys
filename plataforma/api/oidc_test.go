package api

import (
	"crypto"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/hmac"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"
)

// Verificar JWT a mano es una fuente clasica de vulnerabilidades, y casi todas
// son las mismas cuatro. Este fichero las ATACA, porque escribir el
// verificador sin intentar romperlo seria justamente lo que el producto
// reprocha a los demas: una comprobacion que nadie ha visto morder.
//
//	1. `alg: none`
//	2. confusion de algoritmo (HMAC con la clave publica como secreto)
//	3. confusion de clave (un `kid` que apunta a otro tipo de clave)
//	4. reclamaciones sin comprobar (otro emisor, otra audiencia, caducado)

var AHORA = time.Date(2027, 12, 2, 10, 0, 0, 0, time.UTC)

func b64u(b []byte) string { return base64.RawURLEncoding.EncodeToString(b) }

// emisorDePruebas monta un emisor con una clave RSA recien hecha.
func emisorDePruebas(t *testing.T) (*Emisor, *rsa.PrivateKey) {
	t.Helper()
	k, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	return &Emisor{
		Iss: "https://idp.example/acme", Aud: "actaira",
		Claves: map[string]crypto.PublicKey{"k1": &k.PublicKey},
	}, k
}

// firmarRS256 arma un testigo valido y deja tocar el cuerpo antes de firmar.
func firmarRS256(t *testing.T, k *rsa.PrivateKey, kid string, cuerpo map[string]any) string {
	t.Helper()
	cab, _ := json.Marshal(map[string]string{"alg": "RS256", "typ": "JWT", "kid": kid})
	cue, _ := json.Marshal(cuerpo)
	firmado := b64u(cab) + "." + b64u(cue)
	h := sha256.Sum256([]byte(firmado))
	firma, err := rsa.SignPKCS1v15(rand.Reader, k, crypto.SHA256, h[:])
	if err != nil {
		t.Fatal(err)
	}
	return firmado + "." + b64u(firma)
}

func cuerpoBueno() map[string]any {
	return map[string]any{
		"iss": "https://idp.example/acme", "aud": "actaira", "sub": "ana@acme",
		"exp": AHORA.Add(time.Hour).Unix(), "iat": AHORA.Add(-time.Minute).Unix(),
		"actaira_cliente": "acme", "roles": []string{"cumplimiento"},
	}
}

func TestUnTestigoBuenoVerificaYTraeLoQueDice(t *testing.T) {
	e, k := emisorDePruebas(t)
	id, err := e.Verificar(firmarRS256(t, k, "k1", cuerpoBueno()), AHORA)
	if err != nil {
		t.Fatalf("un testigo correcto no verifica: %v", err)
	}
	if id.Cliente != "acme" || id.Sujeto != "ana@acme" {
		t.Fatalf("identidad mal leida: %+v", id)
	}
	if len(id.Roles) != 1 || id.Roles[0] != "cumplimiento" {
		t.Fatalf("roles mal leidos: %v", id.Roles)
	}
}

// --- 1. alg: none ---------------------------------------------------------

func TestAlgNoneNoPasa(t *testing.T) {
	// El ataque mas viejo: un testigo que dice no estar firmado, y un
	// verificador que se lo cree porque el testigo eligio el camino.
	e, _ := emisorDePruebas(t)
	cab, _ := json.Marshal(map[string]string{"alg": "none", "typ": "JWT", "kid": "k1"})
	cue, _ := json.Marshal(cuerpoBueno())
	for _, testigo := range []string{
		b64u(cab) + "." + b64u(cue) + ".",                     // sin firma
		b64u(cab) + "." + b64u(cue) + "." + b64u([]byte("x")), // con basura
	} {
		if _, err := e.Verificar(testigo, AHORA); !errors.Is(err, ErrTestigo) {
			t.Fatalf("`alg: none` paso: %v", err)
		}
	}
	// Y con la grafia que se usa para esquivar comparaciones perezosas.
	for _, alg := range []string{"None", "NONE", "nOnE", ""} {
		cab, _ := json.Marshal(map[string]string{"alg": alg, "kid": "k1"})
		testigo := b64u(cab) + "." + b64u(cue) + "."
		if _, err := e.Verificar(testigo, AHORA); err == nil {
			t.Errorf("`alg: %q` paso", alg)
		}
	}
}

// --- 2. confusion de algoritmo -------------------------------------------

func TestUnTestigoFirmadoConHMACYLaClavePUBLICANoPasa(t *testing.T) {
	// El ataque: la clave publica del emisor es publica, asi que cualquiera
	// puede firmar con HMAC usandola de secreto. Solo funciona si el
	// verificador acepta HMAC; aqui no se admite ninguno simetrico.
	e, k := emisorDePruebas(t)
	publica, err := json.Marshal(k.PublicKey.N.String())
	if err != nil {
		t.Fatal(err)
	}
	cab, _ := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT", "kid": "k1"})
	cue, _ := json.Marshal(cuerpoBueno())
	firmado := b64u(cab) + "." + b64u(cue)
	m := hmac.New(sha256.New, publica)
	m.Write([]byte(firmado))
	testigo := firmado + "." + b64u(m.Sum(nil))

	if _, err := e.Verificar(testigo, AHORA); !errors.Is(err, ErrTestigo) {
		t.Fatalf("un testigo HMAC firmado con la clave publica paso: %v", err)
	}
	if _, hay := ALGORITMOS["HS256"]; hay {
		t.Error("HS256 esta en la lista de admitidos: el ataque tendria donde empezar")
	}
}

// --- 3. confusion de clave ------------------------------------------------

func TestUnKidQueApuntaAOtroTipoDeClaveNoPasa(t *testing.T) {
	// El testigo dice RS256 y el `kid` apunta a una clave de curva eliptica.
	// Sin comprobar que el tipo case con la familia del algoritmo, la firma
	// entraria en una rama que no le corresponde.
	e, k := emisorDePruebas(t)
	ec, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	e.Claves["torcida"] = &ec.PublicKey

	testigo := firmarRS256(t, k, "torcida", cuerpoBueno())
	if _, err := e.Verificar(testigo, AHORA); !errors.Is(err, ErrTestigo) {
		t.Fatalf("un kid del tipo equivocado paso: %v", err)
	}
}

func TestUnKidDesconocidoNoPasa(t *testing.T) {
	e, k := emisorDePruebas(t)
	if _, err := e.Verificar(firmarRS256(t, k, "otra", cuerpoBueno()), AHORA); err == nil {
		t.Fatal("un kid que no esta configurado paso")
	}
}

func TestUnaFirmaDEOTRAClaveNoPasa(t *testing.T) {
	e, _ := emisorDePruebas(t)
	otra, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := e.Verificar(firmarRS256(t, otra, "k1", cuerpoBueno()), AHORA); err == nil {
		t.Fatal("un testigo firmado con otra clave paso")
	}
}

func TestUnCuerpoTOCADODespuesDeFirmarNoPasa(t *testing.T) {
	e, k := emisorDePruebas(t)
	testigo := firmarRS256(t, k, "k1", cuerpoBueno())
	partes := strings.Split(testigo, ".")

	// Se cambia el cliente. Es el ataque util: el testigo es de alguien de
	// `acme` y se reescribe para leer el expediente de `beta`.
	cuerpo := cuerpoBueno()
	cuerpo["actaira_cliente"] = "beta"
	nuevo, _ := json.Marshal(cuerpo)
	tocado := partes[0] + "." + b64u(nuevo) + "." + partes[2]

	if _, err := e.Verificar(tocado, AHORA); !errors.Is(err, ErrTestigo) {
		t.Fatalf("un cuerpo reescrito paso: %v", err)
	}
}

// --- 4. reclamaciones -----------------------------------------------------

func TestLasReclamacionesSeCOMPRUEBANTodas(t *testing.T) {
	e, k := emisorDePruebas(t)
	casos := []struct {
		nombre string
		toca   func(map[string]any)
	}{
		{"otro emisor", func(c map[string]any) { c["iss"] = "https://malo.example" }},
		{"otra audiencia", func(c map[string]any) { c["aud"] = "otro-servicio" }},
		{"caducado", func(c map[string]any) { c["exp"] = AHORA.Add(-2 * time.Hour).Unix() }},
		{"todavia no vale", func(c map[string]any) { c["nbf"] = AHORA.Add(time.Hour).Unix() }},
		{"emitido en el futuro", func(c map[string]any) { c["iat"] = AHORA.Add(time.Hour).Unix() }},
		{"sin exp", func(c map[string]any) { delete(c, "exp") }},
		{"sin cliente", func(c map[string]any) { delete(c, "actaira_cliente") }},
	}
	for _, caso := range casos {
		t.Run(caso.nombre, func(t *testing.T) {
			cuerpo := cuerpoBueno()
			caso.toca(cuerpo)
			if _, err := e.Verificar(firmarRS256(t, k, "k1", cuerpo), AHORA); err == nil {
				t.Fatalf("paso con %s", caso.nombre)
			}
		})
	}
}

func TestUnaAudienciaEnLISTATambienVale(t *testing.T) {
	// La especificacion admite `aud` como cadena o como lista, y un proveedor
	// que mande lista no puede quedarse fuera por eso.
	e, k := emisorDePruebas(t)
	cuerpo := cuerpoBueno()
	cuerpo["aud"] = []string{"otro-servicio", "actaira"}
	if _, err := e.Verificar(firmarRS256(t, k, "k1", cuerpo), AHORA); err != nil {
		t.Fatalf("una audiencia en lista que SI incluye la nuestra fallo: %v", err)
	}
	cuerpo["aud"] = []string{"otro-servicio", "un-tercero"}
	if _, err := e.Verificar(firmarRS256(t, k, "k1", cuerpo), AHORA); err == nil {
		t.Fatal("una lista que NO nos incluye paso")
	}
}

func TestUnEmisorSinIssOSinAudNoArranca(t *testing.T) {
	// Las dos omisiones mas comunes, y las dos vacian la comprobacion: sin
	// `iss` se acepta el testigo de cualquier proveedor; sin `aud`, el emitido
	// para otro servicio del mismo proveedor.
	k, _ := rsa.GenerateKey(rand.Reader, 2048)
	claves := map[string]crypto.PublicKey{"k1": &k.PublicKey}
	for _, e := range []*Emisor{
		{Aud: "actaira", Claves: claves},
		{Iss: "https://idp.example", Claves: claves},
		{Iss: "https://idp.example", Aud: "actaira"},
	} {
		if err := e.Valido(); err == nil {
			t.Errorf("un emisor incompleto se dio por valido: %+v", e)
		}
	}
}

func TestElDesfaseDeRelojSeTOLERAYTieneTecho(t *testing.T) {
	// Un minuto de desajuste entre maquinas es normal y rechazarlo produce
	// fallos intermitentes que nadie diagnostica. Una hora no lo es.
	e, k := emisorDePruebas(t)
	cuerpo := cuerpoBueno()
	cuerpo["exp"] = AHORA.Add(-30 * time.Second).Unix()
	if _, err := e.Verificar(firmarRS256(t, k, "k1", cuerpo), AHORA); err != nil {
		t.Errorf("treinta segundos de desfase se rechazaron: %v", err)
	}
	cuerpo["exp"] = AHORA.Add(-2 * time.Hour).Unix()
	if _, err := e.Verificar(firmarRS256(t, k, "k1", cuerpo), AHORA); err == nil {
		t.Error("dos horas de caducidad pasaron como desfase de reloj")
	}
}
