package api

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"fmt"
	"net/http"
	"os"
	"strings"
)

// La firma del webhook, que es otra cosa que la credencial.
//
// QUE DEMUESTRA CADA UNA, Y POR QUE NO SE PUEDEN SUSTITUIR
// ----------------------------------------------------------
// La ruta `empujon` recibe el cuerpo de un evento de un sistema de terceros --
// GitHub, GitLab, lo que el cliente tenga -- y lo unico que la protegia era la
// credencial del cliente. Una auditoria externa lo puso asi: «los webhooks no
// verifican firmas HMAC del proveedor; dependen de bearer token».
//
// Las dos cosas responden preguntas distintas:
//
//	la credencial   demuestra que quien llama tiene permiso para tocar el
//	                espacio de ESTE cliente.
//	la firma        demuestra que el CUERPO viene del proveedor y llego intacto.
//
// Con solo la credencial, cualquiera que la tenga puede inventarse un evento:
// decir que se empujo un commit que no existe, o que se empujo a una rama que
// nadie toco. El motor decidiria sobre ese evento y escribiria una observacion
// en el expediente del cliente. Y la credencial la tienen mas manos de las que
// parece -- esta en la configuracion del webhook, en el gestor de secretos, en
// la integracion continua -- porque esta pensada para llamar, no para atestiguar.
//
// POR QUE ES OPCIONAL, Y POR QUE ESO NO ES UNA PUERTA TRASERA
// -------------------------------------------------------------
// Se exige cuando el cliente ha configurado un secreto compartido, y no antes.
// Exigirla siempre romperia a todo el que ya tiene el webhook puesto sin
// secreto -- que es como se configura por omision en casi todos los sistemas --
// y lo que hace la gente cuando su integracion deja de funcionar de golpe no es
// configurar el secreto: es quitar el webhook.
//
// Lo que NO se hace es callarse. Si no hay secreto, el arranque lo dice, y la
// respuesta del propio empujon lleva `firma_verificada: false`. La diferencia
// entre «opcional en silencio» y «opcional y dicho» es toda: en el segundo caso
// el expediente registra que ese evento no se pudo atribuir a nadie.
//
// LO QUE ESTA FIRMA NO DEMUESTRA
// --------------------------------
// Que el evento sea CIERTO. Demuestra que lo firmo quien tiene el secreto
// compartido y que el cuerpo no se toco por el camino; si el proveedor manda un
// evento equivocado, llegara firmado. Es integridad y origen, no veracidad, y
// es la misma distincion que el sello de evidencia hace entre integridad e
// identidad.

// ErrSinSecreto indica que ese cliente no tiene secreto de webhook configurado.
var ErrSinSecreto = errors.New("no hay secreto de webhook para este cliente")

// ErrFirmaNoValida indica que el cuerpo no casa con la firma.
var ErrFirmaNoValida = errors.New("la firma del evento no casa con su cuerpo")

// CABECERAS son las que se miran, en orden.
//
// Cada proveedor usa la suya y ninguno usa la del otro. Se miran todas porque
// el cliente configura el webhook en SU sistema, no en este: exigir una
// cabecera concreta seria exigirle que cambie de proveedor.
var CABECERAS = []string{
	"X-Hub-Signature-256", // GitHub, y todo lo que copio su formato
	"X-Gitlab-Token",      // GitLab manda el secreto en claro, no una firma
	"X-Actaira-Firma",     // el nombre propio, para quien integre a mano
}

// VariableDelSecreto es el prefijo de la variable de entorno que trae el
// secreto de cada cliente: `ACTAIRA_SECRETO_WEBHOOK_<CLIENTE>`.
//
// Del ENTORNO y no de un fichero de configuracion a proposito: es la misma
// decision que el remediador de red, y por el mismo motivo. Este modulo no
// guarda secretos, los lee de quien ejecuta, y asi no hay ningun sitio del que
// se puedan filtrar por estar escritos.
const VariableDelSecreto = "ACTAIRA_SECRETO_WEBHOOK_"

// NombreDelSecreto es la variable de entorno de la que sale el secreto de ese
// cliente. Se exporta porque hay DOS sitios que la nombran y tienen que decir
// lo mismo.
//
// ESTO ESTABA ESCRITO DOS VECES Y LAS DOS NO COINCIDIAN.
//
// La conversion vivia solo aqui dentro. El manejador de `empujon`, cuando
// atiende un evento de un cliente sin secreto configurado, avisa en el registro
// y le dice al operador QUE VARIABLE poner -- y la componia por su cuenta,
// pegando el prefijo al identificador en mayusculas y sin convertir nada.
//
// Un identificador de cliente valido puede llevar guiones, y casi todos los
// llevan (`cliente.go` los admite, y `acme-corp` es la forma normal). Asi que
// el aviso mandaba exportar `ACTAIRA_SECRETO_WEBHOOK_ACME-CORP`, que ni
// siquiera es un nombre de variable que la mayoria de los interpretes de
// ordenes deje escribir, mientras el codigo leia
// `ACTAIRA_SECRETO_WEBHOOK_ACME_CORP`. El operador hace lo que dice el aviso,
// el webhook sigue sin firmar para siempre, y no falla nada: la ruta atiende
// el evento igual y solo deja de poder atribuirlo a nadie.
//
// Es la regla 10 en su forma mas barata de cometer: dos formas de calcular el
// mismo nombre, y la que ve una persona era la equivocada.
func NombreDelSecreto(cliente string) string {
	// El nombre del cliente va en mayusculas y con los guiones convertidos:
	// una variable de entorno no puede llevar un guion.
	return VariableDelSecreto + strings.ToUpper(
		strings.NewReplacer("-", "_", ".", "_").Replace(cliente))
}

// secretoDe devuelve el secreto compartido de un cliente, si lo hay.
func secretoDe(cliente string) (string, bool) {
	v := os.Getenv(NombreDelSecreto(cliente))
	return v, v != ""
}

// verificarFirma comprueba el cuerpo contra la firma que traiga la peticion.
//
// Devuelve `ErrSinSecreto` cuando ese cliente no tiene secreto configurado, que
// NO es un fallo: es el tercer estado. Quien lo recibe decide, y lo que decide
// este servidor es dejarlo pasar diciendolo, no dejarlo pasar en silencio.
func verificarFirma(r *http.Request, cliente string, cuerpo []byte) error {
	secreto, hay := secretoDe(cliente)
	if !hay {
		return ErrSinSecreto
	}

	suma := hmac.New(sha256.New, []byte(secreto))
	suma.Write(cuerpo)
	esperada := hex.EncodeToString(suma.Sum(nil))

	for _, cabecera := range CABECERAS {
		traida := strings.TrimSpace(r.Header.Get(cabecera))
		if traida == "" {
			continue
		}
		// GitHub manda `sha256=<hex>`; otros mandan el hex pelado.
		traida = strings.TrimPrefix(traida, "sha256=")

		if cabecera == "X-Gitlab-Token" {
			// GitLab no firma: manda el secreto tal cual. Se compara con el
			// secreto y no con la firma, porque comparar un secreto en claro
			// contra un HMAC siempre daria falso y el cliente veria su webhook
			// rechazado sin entender por que.
			//
			// Esto demuestra MENOS que una firma -- dice quien llama, no que el
			// cuerpo llegara intacto -- y por eso quien lo use tiene que
			// saberlo. Se acepta porque es lo que ese proveedor manda, y
			// rechazarlo seria pedirle al cliente que cambie de proveedor.
			if subtle.ConstantTimeCompare([]byte(traida), []byte(secreto)) == 1 {
				return nil
			}
			return fmt.Errorf("%w: el token de %s no es el configurado",
				ErrFirmaNoValida, cabecera)
		}

		// Tiempo constante. Una comparacion normal se sale en el primer byte
		// que difiere, y eso deja adivinar la firma byte a byte midiendo lo que
		// tarda en contestar.
		if subtle.ConstantTimeCompare([]byte(traida), []byte(esperada)) == 1 {
			return nil
		}
		return fmt.Errorf("%w: la de %s no cuadra con el cuerpo recibido",
			ErrFirmaNoValida, cabecera)
	}

	return fmt.Errorf("%w: hay secreto configurado para %q y el evento no trae "+
		"ninguna de las cabeceras de firma (%s). Un evento sin firmar en un cliente "+
		"que firma es lo que hay que mirar, no lo que hay que dejar pasar",
		ErrFirmaNoValida, cliente, strings.Join(CABECERAS, ", "))
}
