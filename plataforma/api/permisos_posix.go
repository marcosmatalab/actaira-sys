//go:build !windows

package api

import (
	"fmt"
	"os"
)

// soloLoLeeSuDueno comprueba los bits POSIX, que aqui SI informan.
func soloLoLeeSuDueno(ruta string) error {
	info, err := os.Stat(ruta)
	if err != nil {
		return err
	}
	if info.Mode().Perm()&0o077 != 0 {
		return fmt.Errorf(
			"%s tiene permisos %o y lo puede leer alguien mas. Ponlo en 0600",
			ruta, info.Mode().Perm())
	}
	return nil
}
