package api

import "errors"

// El fichero de credenciales guarda tokens que dan acceso al expediente entero
// de un cliente. Que solo lo pueda leer su dueno es un control de seguridad, y
// como todo control de seguridad tiene que poder decir TRES cosas y no dos.
//
// POR QUE TRES ESTADOS Y NO DOS
// ------------------------------
// Estaba escrito con dos: los bits POSIX dicen que puede leerlo alguien mas, o
// no. En Windows los bits que devuelve `os.Stat` no vienen del sistema de
// ficheros: son un valor sintetizado, y para un fichero normal salen siempre
// 0666. El resultado era que en Windows el servidor NO ARRANCABA NUNCA --
// cualquier fichero de credenciales, por bien protegido que estuviera por su
// lista de control de acceso, se rechazaba por unos permisos que nadie habia
// puesto.
//
// Ese fallo es fail-closed, asi que no filtraba nada, y por eso es tentador
// dejarlo. Se arregla igual, por dos razones. La primera es que un control que
// siempre dice que no deja de ser un control: el operador que se lo encuentra
// busca la forma de saltarselo, y la encuentra. La segunda es la de esta casa:
// una comprobacion tiene que distinguir "he mirado y esta mal" de "no puedo
// mirar", porque quien lee el resultado toma decisiones distintas con cada
// una. Confundirlas es lo mismo que confunde un 42501 con una politica.
//
// Asi que:
//
//	seguro           he mirado y solo lo lee su dueno. Arranca.
//	inseguro         he mirado y lo lee alguien mas. No arranca, y se dice.
//	indeterminable   estos bits no informan en este sistema. No arranca
//	                 tampoco, pero el mensaje dice otra cosa y ofrece la
//	                 unica salida honesta: que el operador AFIRME que lo ha
//	                 protegido por otro medio.
//
// El tercer estado no se resuelve solo. Nunca se convierte en "seguro" por su
// cuenta: hace falta que una persona lo declare. Un control que se
// auto-absuelve cuando no puede medir es exactamente el fail-open que este
// producto existe para no tener.

// ErrPermisosIndeterminables indica que los permisos del fichero no se pueden
// leer de forma fiable en este sistema. No es un permiso concedido ni negado.
var ErrPermisosIndeterminables = errors.New(
	"los permisos de este fichero no se pueden comprobar en este sistema operativo")

// VariableDeAfirmacion es el nombre de la variable de entorno con la que un
// operador AFIRMA que ha protegido el fichero por otro medio -- una lista de
// control de acceso, un almacen de secretos, un volumen cifrado.
//
// Es una afirmacion de una persona, no una medicion, y el servidor la trata
// como tal: queda en el registro de arranque con ese nombre, para que un
// auditor vea que ahi no hubo comprobacion sino palabra de alguien.
const VariableDeAfirmacion = "ACTAIRA_PERMISOS_AFIRMADOS_POR_EL_OPERADOR"
