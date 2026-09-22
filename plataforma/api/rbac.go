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
	//
	// DOS DE ESTAS CLAVES LLEVABAN EL NOMBRE DEL VERBO A SECAS, Y MENTIAN.
	//
	// `almacen` y `noconformidad` no son verbos de lectura: son verbos con
	// VARIAS acciones, y solo una de cada uno lee. `almacen` tiene ademas
	// `migrar`, que reescribe el almacen de evidencia entero; `noconformidad`
	// tiene `abrir` y `avanzar`, que mueven el ciclo de una no conformidad --
	// justo lo que el papel `remediacion` existe para repartir.
	//
	// Con la clave puesta en el verbo, la tabla declaraba de LECTURA todo eso.
	// Hoy no es un agujero: la API solo publica las dos acciones que leen. Pero
	// el dia que alguien anada la ruta que abre una no conformidad, nacera con
	// permiso de lectura y NADIE se enterara -- que es lo contrario de lo que
	// este fichero promete tres parrafos mas abajo, donde dice que una ruta sin
	// permiso declarado nace sin funcionar, «que se arregla en un minuto y se
	// nota». Un comentario que avala un control es peor que ninguno cuando es
	// falso.
	//
	// Asi que se declara la ACCION. Lo que no este aqui -- `almacen migrar`,
	// `noconformidad abrir`, `noconformidad avanzar` -- no tiene permiso
	// declarado y por tanto NO PASA, que es el valor por omision correcto.
	"almacen verificar":    PapelLectura,
	"noconformidad listar": PapelLectura,
	"revision":             PapelLectura,
	"soa":                  PapelLectura,
	"anexo":                PapelLectura,
	"preguntar":            PapelLectura,
	// No lee ni un byte del repositorio: la aplicabilidad sale del perfil.
	"aplicabilidad": PapelLectura,

	// Mirar de nuevo. Arrancan un proceso que lee el repositorio ENTERO del
	// cliente, que es lo que cuesta maquina.
	//
	// De los tres, solo `vigilar` ESCRIBE evidencia en el expediente. Esta
	// frase los agrupaba diciendo que lo hacian los tres, y durante un tiempo
	// no lo hacia ninguno: la ruta de `vigilar` no pasaba `--registrar`, asi
	// que el permiso se justificaba con un comportamiento que no ocurria. Un
	// comentario que avala un control es peor que ninguno cuando es falso,
	// porque quien lo lee deja de comprobarlo.
	"plan":      PapelObservacion,
	"comprobar": PapelObservacion,
	// Este ademas anade al almacen lo observado, o revalida lo que ya estaba.
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

// papelPara devuelve el papel que hace falta para eso, y si esta declarado.
//
// Mira la clave ENTERA primero -- «noconformidad listar» -- y solo despues el
// verbo a secas. Ese orden es el arreglo: con la busqueda hecha unicamente por
// el verbo, una accion que escribe heredaba el permiso de la que lee.
//
// El respaldo por el verbo se queda porque la mayoria de los verbos son uno y
// no tienen acciones: `plan`, `soa`, `anexo`. Para los que si las tienen, basta
// con NO declarar el verbo pelado, y entonces cada accion contesta por si misma
// o no pasa.
func papelPara(verbo string) (string, bool) {
	if p, hay := PERMISOS[verbo]; hay {
		return p, true
	}
	p, hay := PERMISOS[verboDe(verbo)]
	return p, hay
}

// Puede dice si esos roles alcanzan para ese verbo.
func Puede(roles []string, verbo string) bool {
	hace_falta, conocido := papelPara(verbo)
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
	hace_falta, conocido := papelPara(verbo)
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
