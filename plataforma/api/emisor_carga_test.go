package api

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/json"
	"encoding/pem"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func pemPublica(t *testing.T, k any) string {
	t.Helper()
	b, err := x509.MarshalPKIXPublicKey(k)
	if err != nil {
		t.Fatal(err)
	}
	return string(pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: b}))
}

func escribirEmisor(t *testing.T, c ConfiguracionDeEmisor) string {
	t.Helper()
	ruta := filepath.Join(t.TempDir(), "emisor.json")
	crudo, _ := json.Marshal(c)
	if err := os.WriteFile(ruta, crudo, 0o600); err != nil {
		t.Fatal(err)
	}
	if runtime.GOOS == "windows" {
		t.Setenv(VariableDeAfirmacion, "1")
	}
	return ruta
}

func TestUnEmisorBienEscritoCarga(t *testing.T) {
	k, _ := rsa.GenerateKey(rand.Reader, 2048)
	ruta := escribirEmisor(t, ConfiguracionDeEmisor{
		Iss: "https://idp.example", Aud: "actaira",
		Claves: map[string]string{"k1": pemPublica(t, &k.PublicKey)},
	})
	e, err := CargarEmisor(ruta)
	if err != nil {
		t.Fatalf("no carga: %v", err)
	}
	if len(e.Claves) != 1 {
		t.Fatalf("cargo %d claves", len(e.Claves))
	}
}

func TestUnaClaveECDSATambienCarga(t *testing.T) {
	k, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	ruta := escribirEmisor(t, ConfiguracionDeEmisor{
		Iss: "https://idp.example", Aud: "actaira",
		Claves: map[string]string{"k1": pemPublica(t, &k.PublicKey)},
	})
	if _, err := CargarEmisor(ruta); err != nil {
		t.Fatalf("una clave ECDSA no carga: %v", err)
	}
}

func TestUnaClavePRIVADASeRechazaDiciendoQueLoEs(t *testing.T) {
	// Pasar la privada donde va la publica es un error de copiar y pegar que
	// ocurre. El mensaje por omision -- «no se pudo analizar» -- haria que
	// alguien probara a arreglarlo a ciegas con el fichero mas sensible que
	// tiene delante.
	k, _ := rsa.GenerateKey(rand.Reader, 2048)
	b, _ := x509.MarshalPKCS8PrivateKey(k)
	privada := string(pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: b}))

	ruta := escribirEmisor(t, ConfiguracionDeEmisor{
		Iss: "https://idp.example", Aud: "actaira",
		Claves: map[string]string{"k1": privada},
	})
	_, err := CargarEmisor(ruta)
	if err == nil {
		t.Fatal("una clave privada se acepto como publica")
	}
	if !strings.Contains(err.Error(), "PRIVADA") {
		t.Errorf("el error no dice que es una clave privada: %v", err)
	}
}

func TestUnEmisorSINIssONINAudNoCarga(t *testing.T) {
	k, _ := rsa.GenerateKey(rand.Reader, 2048)
	publica := pemPublica(t, &k.PublicKey)
	for _, c := range []ConfiguracionDeEmisor{
		{Aud: "actaira", Claves: map[string]string{"k1": publica}},
		{Iss: "https://idp.example", Claves: map[string]string{"k1": publica}},
		{Iss: "https://idp.example", Aud: "actaira"},
	} {
		if _, err := CargarEmisor(escribirEmisor(t, c)); err == nil {
			t.Errorf("cargo un emisor incompleto: %+v", c)
		}
	}
}

func TestUnFicheroDeEmisorQueLeeCualquieraSeRechaza(t *testing.T) {
	// No lleva secretos -- son claves publicas -- pero decide de quien es cada
	// expediente: quien pueda reescribirlo puede emitirse a si mismo un testigo
	// de cualquier cliente.
	if runtime.GOOS == "windows" {
		t.Skip("aqui los bits no informan y la afirmacion es la unica salida")
	}
	k, _ := rsa.GenerateKey(rand.Reader, 2048)
	ruta := filepath.Join(t.TempDir(), "emisor.json")
	crudo, _ := json.Marshal(ConfiguracionDeEmisor{
		Iss: "https://idp.example", Aud: "actaira",
		Claves: map[string]string{"k1": pemPublica(t, &k.PublicKey)},
	})
	if err := os.WriteFile(ruta, crudo, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := CargarEmisor(ruta); err == nil {
		t.Fatal("un fichero de emisor legible por cualquiera se acepto")
	}
}
