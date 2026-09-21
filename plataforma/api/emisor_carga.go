package api

import (
	"crypto"
	"crypto/ecdsa"
	"crypto/rsa"
	"crypto/x509"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"os"
	"time"
)

// Cargar la configuracion del proveedor de identidad DE UN FICHERO.
//
// POR QUE DE UN FICHERO Y NO DE `/.well-known`
// -----------------------------------------------
// Lo comodo seria pedirle al proveedor su configuracion y su juego de claves al
// arrancar. No se hace, y el motivo es el mismo que gobierna todo el
// aislamiento de este servidor: arrancar significaria confiar en lo que
// conteste una direccion de red, y esa direccion viene de la configuracion.
// Quien pueda cambiar la configuracion ya puede hacer mucho dano; lo que no
// tiene por que poder es que el servidor acepte, sin que nadie lo revise,
// cualquier clave que le devuelva un servidor.
//
// Con el juego de claves en un fichero, rotar una clave es un cambio que se ve
// en un diff y que alguien aprueba. Es mas trabajo, y es el trabajo correcto:
// esas claves deciden de quien es cada expediente que se abre.
//
// LO QUE ESTO NO HACE, dicho para que nadie lo suponga: no refresca el juego de
// claves solo. Cuando el proveedor rote, hay que volver a escribir el fichero y
// reiniciar. Para una instalacion que rote a diario eso es poco; para la
// mayoria, que rota cuando toca, es exactamente lo que hace falta.

// ConfiguracionDeEmisor es el fichero que se lee.
type ConfiguracionDeEmisor struct {
	Iss                   string            `json:"iss"`
	Aud                   string            `json:"aud"`
	ReclamacionDelCliente string            `json:"reclamacion_del_cliente"`
	ReclamacionDeRoles    string            `json:"reclamacion_de_roles"`
	DesfaseSegundos       int               `json:"desfase_segundos"`
	Claves                map[string]string `json:"claves"` // kid -> clave publica en PEM
}

// CargarEmisor lee la configuracion del proveedor de identidad.
func CargarEmisor(ruta string) (*Emisor, error) {
	// Los mismos permisos que las credenciales. No lleva secretos -- son claves
	// PUBLICAS -- pero decide de quien es cada expediente: quien pueda
	// reescribir este fichero puede emitirse a si mismo un testigo de
	// cualquier cliente.
	if err := soloLoLeeSuDueno(ruta); err != nil {
		return nil, fmt.Errorf("emisor: %w", err)
	}
	crudo, err := os.ReadFile(ruta)
	if err != nil {
		return nil, fmt.Errorf("emisor: %w", err)
	}
	var c ConfiguracionDeEmisor
	if err := json.Unmarshal(crudo, &c); err != nil {
		return nil, fmt.Errorf("emisor: %w", err)
	}

	claves := map[string]crypto.PublicKey{}
	for kid, texto := range c.Claves {
		k, err := clavePublicaDePEM(texto)
		if err != nil {
			return nil, fmt.Errorf("emisor: la clave %q: %w", kid, err)
		}
		claves[kid] = k
	}

	e := &Emisor{
		Iss: c.Iss, Aud: c.Aud, Claves: claves,
		ReclamacionDelCliente: c.ReclamacionDelCliente,
		ReclamacionDeRoles:    c.ReclamacionDeRoles,
		Desfase:               time.Duration(c.DesfaseSegundos) * time.Second,
	}
	if err := e.Valido(); err != nil {
		return nil, fmt.Errorf("emisor: %w", err)
	}
	return e, nil
}

// clavePublicaDePEM admite una clave publica o un certificado.
//
// Y RECHAZA una clave PRIVADA con un mensaje propio. Pasar la privada donde va
// la publica es un error de copiar y pegar que ocurre, y el mensaje por omision
// -- «no se pudo analizar» -- haria que alguien probara a arreglarlo a ciegas
// con el fichero mas sensible que tiene delante.
func clavePublicaDePEM(texto string) (crypto.PublicKey, error) {
	bloque, _ := pem.Decode([]byte(texto))
	if bloque == nil {
		return nil, fmt.Errorf("no es PEM")
	}
	switch bloque.Type {
	case "PRIVATE KEY", "RSA PRIVATE KEY", "EC PRIVATE KEY":
		return nil, fmt.Errorf(
			"es una clave PRIVADA (%s). Aqui va la PUBLICA del proveedor de "+
				"identidad: con la privada, este servidor podria emitir testigos "+
				"ademas de verificarlos, y un verificador que puede emitir no es un "+
				"verificador", bloque.Type)
	case "CERTIFICATE":
		cert, err := x509.ParseCertificate(bloque.Bytes)
		if err != nil {
			return nil, err
		}
		return comprobarTipo(cert.PublicKey)
	}
	k, err := x509.ParsePKIXPublicKey(bloque.Bytes)
	if err != nil {
		return nil, err
	}
	return comprobarTipo(k)
}

// comprobarTipo rechaza lo que este servidor no sabe verificar.
//
// Aceptar una clave de un tipo sin camino de verificacion la dejaria en el
// juego de claves y fallaria al primer testigo que la usara -- en produccion,
// no al arrancar. Fallar al arrancar es lo unico util aqui.
func comprobarTipo(k crypto.PublicKey) (crypto.PublicKey, error) {
	switch k.(type) {
	case *rsa.PublicKey, *ecdsa.PublicKey:
		return k, nil
	}
	return nil, fmt.Errorf(
		"tipo de clave %T: este servidor verifica RSA y ECDSA. Una clave que no "+
			"sabe verificar fallaria al primer testigo que la usara, en produccion", k)
}
