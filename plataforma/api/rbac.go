package api

import (
	"fmt"
	"sort"
	"strings"
)

// Quien puede pedir que.
//
// POR QUE TRES PAPELES Y NO QUINCE
// ----------------------------------
// Un modelo de permisos con un rol por endpoint se configura mal siempre: nadie
// sabe cual de los quince necesita una persona, asi que se le dan todos «de
// momento». Aqui hay tres, y salen de quien usa esto de verdad:
//
//	lectura        ve el expediente y no lo cambia. Es el auditor, y es el
//	               papel que mas gente tiene.
//	observacion    puede pedirle al motor que vuelva a mirar. Cuesta maquina y
//	               escribe evidencia, asi que no lo tiene todo el mundo.
//	remediacion    puede mover el ciclo de una no conformidad y recibir eventos.
//
// Y uno mas que no es un papel sino una llave:
//
//	admin          todo lo anterior. Existe porque una instalacion pequena no
//	               quiere repartir tres roles, y porque sin el la gente se
//	               inventa uno que los junte.
//
// LA REGLA DE FONDO
// ------------------
// Los roles salen del TESTIGO VERIFICADO y de ningun otro sitio. Un servidor
// que los lea de una cabecera deja que quien llama elija sus propios permisos,
// que es el fallo mas facil de cometer y el mas dificil de ver: funciona
// perfectamente en todas las pruebas, porque las pruebas mandan la cabecera
// correcta.

// Papeles son los roles que este servidor entiende.
const (
	PapelLectura     = "lectura"
	PapelObservacion = "observacion"
	PapelRemediacion = "remediacion"
	PapelAdmin       = "admin"
)

// PERMISOS dice que papel hace falta para cada verbo.
//
// La clave es el VERBO y no la ruta. Dos rutas pueden invocar el mismo verbo --
// `vigilar` y `vigilar --solo-almacen` lo hacen -- y lo que cuesta maquina y
// escribe evidencia es el verbo, no el camino por el que se pidio.
var PERMISOS = map[string]string{
	// Leer. No cambian nada y no arrancan el motor sobre el repositorio.
	"almacen":       PapelLectura,
	"noconformidad": PapelLectura,
	"revision":      PapelLectura,
	"soa":           PapelLectura,
	"anexo":         PapelLectura,
	"preguntar":     PapelLectura,

	// Mirar de nuevo. Arranca un proceso que lee el repositorio entero y
	// escribe evidencia en el expediente.
	"plan":    PapelObservacion,
	"vigilar": PapelObservacion,

	// Mover trabajo y recibir eventos de fuera.
	"empujon":  PapelRemediacion,
	"remediar": PapelRemediacion,
}

// JERARQUIA dice que papeles incluye cada uno.
//
// `observacion` incluye `lectura` porque pedir una observacion sin poder ver el
// resultado no tiene sentido, y repartir los dos por separado solo consigue que
// alguien se olvide del segundo.
var JERARQUIA = map[string][]string{
	PapelAdmin:       {PapelLectura, PapelObservacion, PapelRemediacion},
	PapelObservacion: {PapelLectura},
	PapelRemediacion: {PapelLectura},
}

// Puede dice si esos roles alcanzan para ese verbo.
func Puede(roles []string, verbo string) bool {
	hace_falta, conocido := PERMISOS[verboDe(verbo)]
	if !conocido {
		// Un verbo sin permiso declarado NO se deja pasar.
		//
		// Es la eleccion contraria a la comoda, y el motivo esta escrito en
		// otros tres sitios de este arbol: una tabla a mano se queda corta en
		// cuanto alguien anade algo, y lo que decide entonces es el valor por
		// omision. Si fuera «deja pasar», la ruta nueva naceria sin permisos;
		// asi nace sin funcionar, que se arregla en un minuto y se nota.
		return false
	}
	for _, r := range roles {
		if alcanza(r, hace_falta) {
			return true
		}
	}
	return false
}

func alcanza(tiene, hace_falta string) bool {
	if tiene == hace_falta {
		return true
	}
	for _, incluido := range JERARQUIA[tiene] {
		if incluido == hace_falta {
			return true
		}
	}
	return false
}

// PapelesConocidos son los que este servidor entiende, ordenados.
func PapelesConocidos() []string {
	vistos := map[string]bool{PapelAdmin: true}
	for _, p := range PERMISOS {
		vistos[p] = true
	}
	fuera := make([]string, 0, len(vistos))
	for p := range vistos {
		fuera = append(fuera, p)
	}
	sort.Strings(fuera)
	return fuera
}

// ExplicarNegativa dice que hacia falta y que habia, sin filtrar nada util.
//
// Un 403 que solo dice «prohibido» obliga a quien lo recibe a adivinar, y lo
// que hace la gente cuando adivina permisos es pedir el rol mas alto. Decir que
// papel falta no revela nada que quien llama no pueda deducir probando.
func ExplicarNegativa(roles []string, verbo string) string {
	hace_falta, conocido := PERMISOS[verboDe(verbo)]
	if !conocido {
		return fmt.Sprintf(
			"el verbo %q no tiene permiso declarado, asi que no se deja pasar. "+
				"Los declarados son: %s", verbo, strings.Join(verbosConPermiso(), ", "))
	}
	tenia := "ninguno"
	if len(roles) > 0 {
		tenia = strings.Join(roles, ", ")
	}
	return fmt.Sprintf("para %q hace falta el papel %q y el testigo trae: %s",
		verbo, hace_falta, tenia)
}

func verbosConPermiso() []string {
	fuera := make([]string, 0, len(PERMISOS))
	for v := range PERMISOS {
		fuera = append(fuera, v)
	}
	sort.Strings(fuera)
	return fuera
}
