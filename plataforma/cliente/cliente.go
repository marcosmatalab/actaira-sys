// Package cliente describe donde viven los datos de un cliente y que puede
// tocarse de ellos.
//
// Es corto a proposito. Todo lo que sabe de cumplimiento vive en el motor; lo
// que vive aqui es la respuesta a una sola pregunta: dado un identificador de
// cliente, que rutas son suyas y cuales no. Esa pregunta es la que separa una
// plataforma multi cliente de un incidente.
package cliente

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
)

// ErrIdentificadorInvalido lo devuelve cualquier identificador que no sea
// exactamente lo que se espera. NO se sanea ni se recorta: un identificador
// que hay que limpiar antes de usar es un identificador que alguien acabara
// usando sin limpiar.
var ErrIdentificadorInvalido = errors.New("identificador de cliente invalido")

var valido = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$`)

// Cliente es una carpeta bajo la raiz, y nada mas.
type Cliente struct {
	ID   string
	Raiz string // ruta absoluta de la carpeta de ESTE cliente
}

// Espacio es la raiz de todos los clientes.
type Espacio struct{ Raiz string }

func AbrirEspacio(raiz string) (*Espacio, error) {
	abs, err := filepath.Abs(raiz)
	if err != nil {
		return nil, err
	}
	if err := os.MkdirAll(abs, 0o750); err != nil {
		return nil, err
	}
	return &Espacio{Raiz: abs}, nil
}

// De devuelve el cliente, creando su carpeta si hace falta.
//
// El identificador se valida contra una expresion cerrada en vez de limpiarse.
// Un `..`, una barra o un nombre vacio no se corrigen: se rechazan. La
// diferencia importa porque limpiar deja la puerta abierta al siguiente que
// olvide limpiar, y rechazar no.
func (e *Espacio) De(id string) (*Cliente, error) {
	if !valido.MatchString(id) {
		return nil, fmt.Errorf("%q: %w", id, ErrIdentificadorInvalido)
	}
	raiz := filepath.Join(e.Raiz, id)
	if err := os.MkdirAll(raiz, 0o750); err != nil {
		return nil, err
	}
	return &Cliente{ID: id, Raiz: raiz}, nil
}

func (e *Espacio) Todos() ([]string, error) {
	entradas, err := os.ReadDir(e.Raiz)
	if err != nil {
		return nil, err
	}
	var ids []string
	for _, x := range entradas {
		if x.IsDir() && valido.MatchString(x.Name()) {
			ids = append(ids, x.Name())
		}
	}
	sort.Strings(ids)
	return ids, nil
}

// Almacen es el fichero de evidencia de este cliente. Solo se anade, asi que
// la plataforma nunca lo reescribe: se lo pasa al motor y el motor agrega.
func (c *Cliente) Almacen() string { return filepath.Join(c.Raiz, "evidencia.jsonl") }

// Respuestas es el fichero con lo que han contestado las personas.
func (c *Cliente) Respuestas() string { return filepath.Join(c.Raiz, "respuestas.json") }

// Trabajo es donde se deja una copia del repositorio para barrerla.
func (c *Cliente) Trabajo() string { return filepath.Join(c.Raiz, "trabajo") }

// Contiene dice si una ruta cuelga de este cliente, con las rutas ya resueltas.
func (c *Cliente) Contiene(ruta string) bool {
	abs, err := filepath.Abs(ruta)
	if err != nil {
		return false
	}
	rel, err := filepath.Rel(c.Raiz, abs)
	if err != nil {
		return false
	}
	return rel != ".." && !filepath.IsAbs(rel) &&
		(rel == "." || rel[0] != '.' || (len(rel) > 1 && rel[1] != '.'))
}
