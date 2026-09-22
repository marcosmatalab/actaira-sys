package api

import (
	"crypto"
	"crypto/ecdsa"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/sha512"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"strings"
	"time"
)

// Verificacion de identidad con OIDC, escrita contra la biblioteca estandar.
//
// POR QUE A MANO, Y POR QUE ESO NORMALMENTE ES MALA IDEA
// --------------------------------------------------------
// Este modulo no tiene ni una dependencia externa, y no es una casualidad: es
// lo que permite que alguien lo audite entero en una tarde. Meter una
// biblioteca de JWT cambiaria esa propiedad por un fichero, y con ella toda su
// cadena de suministro.
//
// La contrapartida es seria y conviene decirla: verificar JWT a mano es una
// fuente clasica de vulnerabilidades, y casi todas son las mismas cuatro. Se
// nombran aqui porque cada una tiene su linea de codigo y su prueba:
//
//  1. `alg: none`. Un testigo que dice no estar firmado, y un verificador que
//     se lo cree. Aqui el algoritmo del testigo NUNCA elige el camino: se
//     comprueba contra una lista cerrada ANTES de mirar nada mas.
//  2. Confusion de algoritmo. Un testigo firmado con HMAC usando como clave la
//     clave PUBLICA del emisor, que es publica. Aqui las claves simetricas no
//     se admiten en absoluto, asi que el ataque no tiene donde empezar.
//  3. Confusion de clave. Un `kid` que apunta a una clave de otro tipo. Aqui
//     se comprueba que el tipo de la clave case con la familia del algoritmo.
//  4. Reclamaciones sin comprobar. Un testigo valido de OTRO emisor, o para
//     OTRA audiencia, o caducado. Se comprueban las cuatro, y el emisor y la
//     audiencia son OBLIGATORIOS de configurar: sin ellos no se arranca.
//
// LO QUE ESTE MODULO NO HACE
// ---------------------------
// No descubre la configuracion del emisor por `/.well-known`: la clave publica
// se configura. No refresca el juego de claves por su cuenta. No soporta
// testigos cifrados. Y no sustituye a un proveedor de identidad: valida lo que
// el proveedor emitio.
//
// Se dice porque un modulo llamado `oidc.go` invita a suponer que hace todo lo
// que hace una biblioteca de OIDC, y hace una parte.

// ErrTestigo es la familia de errores de verificacion.
var ErrTestigo = errors.New("el testigo no verifica")

// ALGORITMOS son los que se admiten, y la lista es cerrada.
//
// Solo asimetricos. Un algoritmo simetrico -- HS256 y familia -- obligaria a
// compartir el secreto de firma con este servidor, y entonces este servidor
// podria EMITIR testigos ademas de verificarlos. Un verificador que puede
// emitir no es un verificador.
//
// Y sin ellos, la confusion de algoritmo no tiene donde empezar: el ataque
// clasico consiste en firmar con HMAC usando la clave publica del emisor como
// secreto, y depende de que el verificador acepte HMAC.
var ALGORITMOS = map[string]crypto.Hash{
	"RS256": crypto.SHA256, "RS384": crypto.SHA384, "RS512": crypto.SHA512,
	"PS256": crypto.SHA256, "PS384": crypto.SHA384, "PS512": crypto.SHA512,
	"ES256": crypto.SHA256, "ES384": crypto.SHA384, "ES512": crypto.SHA512,
}

// Emisor describe al proveedor de identidad en el que este servidor confia.
type Emisor struct {
	// Iss tiene que casar EXACTAMENTE con la reclamacion `iss` del testigo.
	Iss string
	// Aud es la audiencia que este servidor espera. Un testigo valido emitido
	// para OTRO servicio del mismo proveedor no vale aqui: es la diferencia
	// entre «esta firmado por quien digo» y «es para mi».
	Aud string
	// Claves son las publicas del emisor, por `kid`.
	Claves map[string]crypto.PublicKey
	// ReclamacionDelCliente es la reclamacion que dice a que cliente pertenece
	// quien llama. Por omision `actaira_cliente`.
	ReclamacionDelCliente string
	// ReclamacionDeRoles es la que trae los roles. Por omision `roles`.
	ReclamacionDeRoles string
	// Desfase es cuanto se tolera de reloj desajustado. Por omision 60 s.
	Desfase time.Duration
}

// Identidad es lo que queda de un testigo DESPUES de verificarlo.
//
// Todo lo que hay aqui sale del testigo firmado. Nada sale de una cabecera:
// esa es la regla entera de este fichero. Un servidor que lea el cliente de una
// cabecera deja que quien llama elija de quien es el expediente que va a leer.
type Identidad struct {
	Sujeto  string
	Cliente string
	Roles   []string
	Expira  time.Time
}

func (e *Emisor) reclamacionDelCliente() string {
	if e.ReclamacionDelCliente == "" {
		return "actaira_cliente"
	}
	return e.ReclamacionDelCliente
}

func (e *Emisor) reclamacionDeRoles() string {
	if e.ReclamacionDeRoles == "" {
		return "roles"
	}
	return e.ReclamacionDeRoles
}

func (e *Emisor) desfase() time.Duration {
	if e.Desfase <= 0 {
		return time.Minute
	}
	return e.Desfase
}

// Valido comprueba que el emisor esta configurado para poder verificar algo.
//
// Sin `Iss` o sin `Aud` no se arranca. Un verificador que no comprueba de quien
// viene el testigo acepta el de cualquier proveedor; uno que no comprueba para
// quien es acepta el que se emitio para otro servicio del mismo proveedor. Las
// dos son omisiones comunes y las dos vacian la comprobacion.
func (e *Emisor) Valido() error {
	if e.Iss == "" {
		return errors.New("un emisor sin `iss` aceptaria testigos de cualquier proveedor")
	}
	if e.Aud == "" {
		return errors.New(
			"un emisor sin `aud` aceptaria un testigo emitido para otro servicio del " +
				"mismo proveedor: estar firmado por quien digo no es ser para mi")
	}
	if len(e.Claves) == 0 {
		return errors.New("un emisor sin claves publicas no puede verificar nada")
	}
	return nil
}

// `typ` NO ESTA AQUI, Y NO ES UN OLVIDO.
//
// Estaba: se leia en cada testigo y no se comparaba con nada. Un campo asi es
// peor que no tenerlo en un fichero que enumera los cuatro fallos clasicos de
// verificar JWT a mano y dice que «cada una tiene su linea de codigo y su
// prueba»: quien lo lea dara por hecho que el tipo se comprueba.
//
// Y no se comprueba a proposito. La recomendacion de tipar explicitamente
// (RFC 8725) sirve para que un testigo de un tipo no valga como otro, y aqui no
// hay mas que uno: este servidor solo acepta testigos de acceso de SU emisor,
// para SU audiencia. Exigir un valor concreto ademas rompe con proveedores
// reales, que escriben `JWT`, `at+jwt` o `Bearer` segun les parece.
//
// Lo que SI cierra ese hueco es lo de abajo: `iss` exacto, `aud` obligatoria,
// `exp` obligatoria y el algoritmo contra una lista cerrada de asimetricos.
type cabeceraTestigo struct {
	Alg string `json:"alg"`
	Kid string `json:"kid"`
}

type cuerpoTestigo struct {
	Iss string          `json:"iss"`
	Sub string          `json:"sub"`
	Aud json.RawMessage `json:"aud"`
	Exp int64           `json:"exp"`
	Nbf int64           `json:"nbf"`
	Iat int64           `json:"iat"`
}

func b64(s string) ([]byte, error) { return base64.RawURLEncoding.DecodeString(s) }

// Verificar comprueba el testigo y devuelve la identidad que lleva dentro.
func (e *Emisor) Verificar(testigo string, ahora time.Time) (Identidad, error) {
	if err := e.Valido(); err != nil {
		return Identidad{}, fmt.Errorf("%w: %v", ErrTestigo, err)
	}

	partes := strings.Split(testigo, ".")
	if len(partes) != 3 {
		return Identidad{}, fmt.Errorf("%w: no tiene tres partes", ErrTestigo)
	}

	crudoCabecera, err := b64(partes[0])
	if err != nil {
		return Identidad{}, fmt.Errorf("%w: la cabecera no decodifica", ErrTestigo)
	}
	var cab cabeceraTestigo
	if err := json.Unmarshal(crudoCabecera, &cab); err != nil {
		return Identidad{}, fmt.Errorf("%w: la cabecera no es JSON", ErrTestigo)
	}

	// EL ALGORITMO NO LO ELIGE EL TESTIGO.
	//
	// Se comprueba contra la lista cerrada ANTES de mirar la clave, la firma o
	// cualquier otra cosa. `alg: none` no llega aqui: no esta en la lista, y no
	// hay ninguna rama que lo trate distinto. Tampoco los simetricos, asi que
	// la confusion de algoritmo no tiene donde empezar.
	hash, admitido := ALGORITMOS[cab.Alg]
	if !admitido {
		return Identidad{}, fmt.Errorf(
			"%w: algoritmo %q, y los admitidos son asimetricos: %s",
			ErrTestigo, cab.Alg, strings.Join(algoritmosOrdenados(), ", "))
	}

	clave, hay := e.Claves[cab.Kid]
	if !hay {
		return Identidad{}, fmt.Errorf("%w: no hay clave publica con kid %q", ErrTestigo, cab.Kid)
	}

	firma, err := b64(partes[2])
	if err != nil {
		return Identidad{}, fmt.Errorf("%w: la firma no decodifica", ErrTestigo)
	}
	firmado := []byte(partes[0] + "." + partes[1])

	if err := comprobarFirma(cab.Alg, hash, clave, firmado, firma); err != nil {
		return Identidad{}, fmt.Errorf("%w: %v", ErrTestigo, err)
	}

	crudoCuerpo, err := b64(partes[1])
	if err != nil {
		return Identidad{}, fmt.Errorf("%w: el cuerpo no decodifica", ErrTestigo)
	}
	var cuerpo cuerpoTestigo
	if err := json.Unmarshal(crudoCuerpo, &cuerpo); err != nil {
		return Identidad{}, fmt.Errorf("%w: el cuerpo no es JSON", ErrTestigo)
	}

	// Las reclamaciones. Todas, y con el emisor comparado en tiempo constante
	// por costumbre: no hay un ataque de tiempo util aqui, pero una comparacion
	// de identidad que a veces es constante y a veces no es una que alguien
	// copiara al sitio donde si importa.
	if subtle.ConstantTimeCompare([]byte(cuerpo.Iss), []byte(e.Iss)) != 1 {
		return Identidad{}, fmt.Errorf("%w: lo emitio %q y se esperaba %q",
			ErrTestigo, cuerpo.Iss, e.Iss)
	}
	if !audienciaIncluye(cuerpo.Aud, e.Aud) {
		return Identidad{}, fmt.Errorf(
			"%w: su audiencia no incluye %q. Un testigo valido emitido para otro "+
				"servicio del mismo proveedor no vale aqui", ErrTestigo, e.Aud)
	}

	d := e.desfase()
	if cuerpo.Exp == 0 {
		return Identidad{}, fmt.Errorf(
			"%w: no trae `exp`. Un testigo sin caducidad vale para siempre, y lo que "+
				"vale para siempre no se puede revocar", ErrTestigo)
	}
	expira := time.Unix(cuerpo.Exp, 0)
	if ahora.After(expira.Add(d)) {
		return Identidad{}, fmt.Errorf("%w: caduco el %s", ErrTestigo,
			expira.UTC().Format(time.RFC3339))
	}
	if cuerpo.Nbf != 0 && ahora.Add(d).Before(time.Unix(cuerpo.Nbf, 0)) {
		return Identidad{}, fmt.Errorf("%w: todavia no vale", ErrTestigo)
	}
	if cuerpo.Iat != 0 && ahora.Add(d).Before(time.Unix(cuerpo.Iat, 0)) {
		return Identidad{}, fmt.Errorf("%w: dice haberse emitido en el futuro", ErrTestigo)
	}

	// EL CLIENTE Y LOS ROLES SALEN DEL TESTIGO FIRMADO. De ningun otro sitio.
	var libre map[string]any
	if err := json.Unmarshal(crudoCuerpo, &libre); err != nil {
		return Identidad{}, fmt.Errorf("%w: el cuerpo no es un objeto", ErrTestigo)
	}
	cliente, _ := libre[e.reclamacionDelCliente()].(string)
	if cliente == "" {
		return Identidad{}, fmt.Errorf(
			"%w: no trae la reclamacion %q, asi que no dice de que cliente es. Leerla "+
				"de una cabecera dejaria que quien llama eligiera de quien es el "+
				"expediente que va a abrir",
			ErrTestigo, e.reclamacionDelCliente())
	}

	return Identidad{
		Sujeto: cuerpo.Sub, Cliente: cliente,
		Roles: comoCadenas(libre[e.reclamacionDeRoles()]), Expira: expira,
	}, nil
}

func algoritmosOrdenados() []string {
	fuera := make([]string, 0, len(ALGORITMOS))
	for k := range ALGORITMOS {
		fuera = append(fuera, k)
	}
	// Orden estable para que el mensaje de error no cambie entre ejecuciones.
	for i := 1; i < len(fuera); i++ {
		for j := i; j > 0 && fuera[j] < fuera[j-1]; j-- {
			fuera[j], fuera[j-1] = fuera[j-1], fuera[j]
		}
	}
	return fuera
}

// comprobarFirma verifica, exigiendo que el TIPO de la clave case con la
// familia del algoritmo.
//
// Sin esa comprobacion, un `kid` que apunte a una clave del tipo equivocado
// entra en una rama que no le corresponde. Es la confusion de clave, y la
// version corta es: el testigo no puede elegir con que se le verifica.
func comprobarFirma(alg string, hash crypto.Hash, clave crypto.PublicKey,
	firmado, firma []byte) error {
	resumen := resumir(hash, firmado)

	switch {
	case strings.HasPrefix(alg, "RS"):
		k, vale := clave.(*rsa.PublicKey)
		if !vale {
			return fmt.Errorf("el kid apunta a una clave que no es RSA y el alg es %s", alg)
		}
		return rsa.VerifyPKCS1v15(k, hash, resumen, firma)

	case strings.HasPrefix(alg, "PS"):
		k, vale := clave.(*rsa.PublicKey)
		if !vale {
			return fmt.Errorf("el kid apunta a una clave que no es RSA y el alg es %s", alg)
		}
		return rsa.VerifyPSS(k, hash, resumen, firma,
			&rsa.PSSOptions{SaltLength: rsa.PSSSaltLengthEqualsHash, Hash: hash})

	case strings.HasPrefix(alg, "ES"):
		k, vale := clave.(*ecdsa.PublicKey)
		if !vale {
			return fmt.Errorf("el kid apunta a una clave que no es ECDSA y el alg es %s", alg)
		}
		// JWS manda la firma ECDSA como r||s con cada mitad rellenada al tamano
		// de la curva. `ecdsa.VerifyASN1` espera DER, asi que se parte a mano.
		mitad := len(firma) / 2
		if len(firma)%2 != 0 || mitad == 0 {
			return errors.New("la firma ECDSA no tiene dos mitades")
		}
		r := new(big.Int).SetBytes(firma[:mitad])
		s := new(big.Int).SetBytes(firma[mitad:])
		if !ecdsa.Verify(k, resumen, r, s) {
			return errors.New("la firma ECDSA no cuadra")
		}
		return nil
	}
	return fmt.Errorf("algoritmo %q sin camino de verificacion", alg)
}

func resumir(hash crypto.Hash, datos []byte) []byte {
	switch hash {
	case crypto.SHA256:
		h := sha256.Sum256(datos)
		return h[:]
	case crypto.SHA384:
		h := sha512.Sum384(datos)
		return h[:]
	case crypto.SHA512:
		h := sha512.Sum512(datos)
		return h[:]
	}
	return nil
}

// audienciaIncluye admite las dos formas que permite la especificacion: una
// cadena, o una lista de cadenas.
func audienciaIncluye(crudo json.RawMessage, esperada string) bool {
	if len(crudo) == 0 {
		return false
	}
	var una string
	if json.Unmarshal(crudo, &una) == nil {
		return subtle.ConstantTimeCompare([]byte(una), []byte(esperada)) == 1
	}
	var varias []string
	if json.Unmarshal(crudo, &varias) == nil {
		for _, a := range varias {
			if subtle.ConstantTimeCompare([]byte(a), []byte(esperada)) == 1 {
				return true
			}
		}
	}
	return false
}

func comoCadenas(v any) []string {
	switch x := v.(type) {
	case []any:
		fuera := make([]string, 0, len(x))
		for _, e := range x {
			if s, vale := e.(string); vale {
				fuera = append(fuera, s)
			}
		}
		return fuera
	case string:
		// Algunos proveedores mandan los roles separados por espacios.
		return strings.Fields(x)
	}
	return nil
}
