package motor

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// El aislamiento entre clientes, resuelto contra el DISCO y no contra la cadena.
//
// QUE ESTABA ROTO
// ----------------
// `rutaSegura` hacia `filepath.Abs` y luego `filepath.Rel` contra la raiz de
// clientes. `Abs` llama a `Clean`, que resuelve los `..` LEXICOS -- y por eso el
// traversal clasico `../../etc` si estaba cerrado -- pero no toca el disco y no
// sabe nada de enlaces simbolicos.
//
// Con eso, un directorio de trabajo que sea un enlace a otro sitio pasa la
// comprobacion entera: la cadena cuelga de la raiz, luego esta dentro. El motor
// recibe esa ruta y lee lo que haya al otro lado. En una plataforma donde cada
// cliente tiene su carpeta bajo la misma raiz, el otro lado es la carpeta de
// otro cliente.
//
// Reproducido: `clientes/acme/trabajo` como enlace a un directorio de fuera, y
// el motor leyendo sus ficheros sin una sola queja.
//
// POR QUE NO BASTABA CON QUE LO MIRARA EL MOTOR
// -----------------------------------------------
// El lado Python tiene su propia guarda: `Arbol._dentro` resuelve cada fichero y
// exige que caiga bajo la raiz. Pero esa guarda compara contra `raiz.resolve()`,
// es decir, contra la raiz YA SEGUIDA. Si el enlace es la raiz misma, resolverla
// lleva al destino y todo lo que hay debajo esta, efectivamente, dentro. La
// guarda protege contra un enlace DENTRO del arbol y se anula a si misma cuando
// el enlace ES el arbol.
//
// Esa es la barrera que de verdad hace falta aqui: quien sabe donde empieza el
// espacio de un cliente es esta capa, no el motor, que recibe una ruta y no tiene
// forma de saber de que cliente es.
//
// COMO SE RESUELVE UNA RUTA QUE TODAVIA NO EXISTE
// ------------------------------------------------
// `filepath.EvalSymlinks` falla si la ruta no existe, y aqui se comprueban
// tambien rutas de SALIDA -- un `--almacen` que se va a crear, un `--sarif` que
// todavia no esta. Asi que se resuelve el ANTECESOR mas largo que si existe y se
// vuelve a pegar el resto de forma lexica. Es lo correcto y no lo comodo: lo
// comodo seria no comprobar las que no existen, y entonces bastaria con pedir
// una salida en una ruta inexistente para escribir donde uno quiera.

// ErrNoSeSabe se devuelve cuando la resolucion no se puede completar por una
// razon que no es «esta fuera»: un permiso denegado, un ciclo de enlaces, un
// sistema de ficheros que desaparece a mitad.
//
// Es un tercer estado y no un sinonimo de ninguno de los dos. Tratarlo como
// «dentro» abre el agujero que se acaba de cerrar; tratarlo como «fuera» sin
// decirlo convierte un problema de operacion en un error de aislamiento que
// nadie sabra diagnosticar. Se dice lo que paso y NO se deja pasar.
var ErrNoSeSabe = errors.New("no se pudo resolver la ruta para comprobar el aislamiento")

// resolverLoQueSePueda devuelve la ruta con sus enlaces seguidos hasta donde
// existe, mas el resto pegado sin seguir nada.
func resolverLoQueSePueda(ruta string) (string, error) {
	abs, err := filepath.Abs(ruta)
	if err != nil {
		return "", fmt.Errorf("%w: %v", ErrNoSeSabe, err)
	}
	resto := ""
	actual := abs
	for {
		resuelto, err := filepath.EvalSymlinks(actual)
		if err == nil {
			if resto == "" {
				return resuelto, nil
			}
			return filepath.Join(resuelto, resto), nil
		}
		if !os.IsNotExist(err) {
			// Ni «existe y esta fuera» ni «no existe todavia»: no se sabe.
			return "", fmt.Errorf("%w: %s: %v", ErrNoSeSabe, actual, err)
		}
		padre := filepath.Dir(actual)
		if padre == actual {
			// Se llego a la raiz del volumen sin encontrar nada que exista.
			return abs, nil
		}
		resto = filepath.Join(filepath.Base(actual), resto)
		actual = padre
	}
}

// dentroDe dice si `candidato` cae bajo `raiz`, con los enlaces de los dos ya
// seguidos. La comparacion se hace por COMPONENTES y no por prefijo de cadena:
// `/clientes/acme-malo` empieza por `/clientes/acme` y no esta dentro de el.
func dentroDe(raiz, candidato string) (bool, error) {
	raizReal, err := resolverLoQueSePueda(raiz)
	if err != nil {
		return false, err
	}
	candReal, err := resolverLoQueSePueda(candidato)
	if err != nil {
		return false, err
	}
	rel, err := filepath.Rel(raizReal, candReal)
	if err != nil {
		return false, nil // volumenes distintos en Windows: esta fuera
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return false, nil
	}
	return true, nil
}
