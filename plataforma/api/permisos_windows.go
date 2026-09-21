//go:build windows

package api

import (
	"fmt"
	"os"
)

// soloLoLeeSuDueno NO puede decidir en Windows leyendo los bits de `os.Stat`.
//
// Ahi el modo no viene del sistema de ficheros: Go lo sintetiza a partir del
// atributo de solo lectura, y para un fichero normal sale siempre 0666. Quien
// decide de verdad quien lee el fichero es su lista de control de acceso, que
// esos bits no reflejan. Mirarlos y concluir "inseguro" era decidir sobre un
// dato que no mide lo que se pregunta.
//
// Leer la lista de control de acceso de verdad exige `golang.org/x/sys/windows`.
// Este modulo no tiene ni una dependencia externa a proposito -- es lo que
// permite auditarlo entero -- y anadir una para esta comprobacion cambiaria esa
// propiedad por una sola funcion. Asi que se devuelve el tercer estado y se le
// pide al operador que AFIRME, que es lo unico que aqui se puede saber.
func soloLoLeeSuDueno(ruta string) error {
	if _, err := os.Stat(ruta); err != nil {
		return err
	}
	if os.Getenv(VariableDeAfirmacion) == "1" {
		return nil
	}
	return fmt.Errorf(
		"%w: %s. En Windows los bits que devuelve `os.Stat` no vienen del sistema de "+
			"ficheros y no dicen quien puede leerlo. Protege el fichero con su lista de "+
			"control de acceso (por ejemplo `icacls %s /inheritance:r /grant:r %%USERNAME%%:R`) "+
			"y arranca con %s=1 para AFIRMAR que lo has hecho. Esa afirmacion queda en el "+
			"registro de arranque como afirmacion, no como comprobacion",
		ErrPermisosIndeterminables, ruta, ruta, VariableDeAfirmacion)
}
