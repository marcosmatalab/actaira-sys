// Package motor es el lado Go de la frontera con el motor de Actaira.
//
// La arquitectura decide que el motor sea Python y la plataforma Go, y que la
// frontera entre los dos sea UN PROCESO Y UN JSON. Este paquete es ese lado: no
// reimplementa ninguna regla, no conoce ningun articulo, y no sabe que es una
// obligacion. Lo unico que sabe es invocar un verbo, respetar un plazo, aislar
// a un cliente de otro y leer un documento que declara su version.
//
// Lo que NO hace, y es deliberado:
//
//   - No interpreta los codigos de salida como exito o fracaso. Tres significa
//     «esta incompleto o hay trabajo que hacer», y tratarlo como un fallo haria
//     que la plataforma marcara en rojo el estado normal de un cliente que
//     empieza. Se devuelve tal cual y decide quien llama.
//   - No transforma el documento. Lo que sale del motor es lo que se guarda y
//     lo que se ensena, con su campo `esquema` dentro. Una plataforma que
//     reescribe el expediente antes de guardarlo deja de poder demostrar que el
//     expediente es el que emitio el motor.
package motor

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// Resultado de una ejecucion. `Codigo` se devuelve sin interpretar.
type Resultado struct {
	Verbo     string
	Codigo    int
	Documento map[string]any
	Esquema   string
	Duracion  time.Duration
}

// Completo es true solo con codigo 0. Con 3 el documento es valido y esta
// incompleto, que es un estado del cliente y no un fallo de la herramienta.
func (r Resultado) Completo() bool { return r.Codigo == 0 }

// HayTrabajo es true con codigo 3: falta contestar, falta firmar, o hay algo
// que volver a observar.
func (r Resultado) HayTrabajo() bool { return r.Codigo == 3 }

// Motor invoca al binario del motor. Un valor cero no sirve: usa Nuevo.
type Motor struct {
	Binario        string        // ruta o nombre del ejecutable `actaira`
	RaizDeClientes string        // toda ruta de trabajo tiene que colgar de aqui
	Plazo          time.Duration // un verbo que no termina a tiempo se mata
}

func Nuevo(binario, raizDeClientes string, plazo time.Duration) (*Motor, error) {
	raiz, err := filepath.Abs(raizDeClientes)
	if err != nil {
		return nil, fmt.Errorf("raiz de clientes: %w", err)
	}
	if plazo <= 0 {
		plazo = 2 * time.Minute
	}
	return &Motor{Binario: binario, RaizDeClientes: raiz, Plazo: plazo}, nil
}

// ErrFueraDeAlcance se devuelve cuando la ruta de trabajo no cuelga de la raiz
// de clientes. Es la unica barrera de aislamiento de este paquete y por eso se
// comprueba con rutas ya resueltas: comparar cadenas sin resolver deja pasar
// `../` y un cliente leeria el repositorio de otro.
var ErrFueraDeAlcance = errors.New("la ruta de trabajo no cuelga de la raiz de clientes")

func (m *Motor) rutaSegura(trabajo string) (string, error) {
	// Con los enlaces SEGUIDOS. Ver `rutas.go`: esto comparaba cadenas, asi que
	// un directorio de trabajo que fuera un enlace a otro sitio pasaba entero y
	// el motor leia la carpeta de otro cliente.
	ok, err := dentroDe(m.RaizDeClientes, trabajo)
	if err != nil {
		return "", err // ErrNoSeSabe: ni dentro ni fuera, y no se deja pasar
	}
	if !ok {
		return "", ErrFueraDeAlcance
	}
	abs, err := filepath.Abs(trabajo)
	if err != nil {
		return "", err
	}
	return abs, nil
}

// argumentosSeguros comprueba TODA ruta absoluta que se le pase al motor.
//
// La primera version solo miraba el primer positional, y con eso la barrera
// dependia de que ninguna ruta del API acabara nunca en `args`. Un
// `--almacen /etc/algo` habria pasado entero: la barrera no puede descansar en
// que quien llama se acuerde, porque el dia que se olvide no falla nada.
func (m *Motor) ArgumentosSeguros(args []string) error {
	for _, a := range args {
		if filepath.IsAbs(a) {
			if _, err := m.rutaSegura(a); err != nil {
				return fmt.Errorf("%s: %w", a, ErrFueraDeAlcance)
			}
		}
	}
	return nil
}

// EjecutarSinRuta corre un verbo cuyo primer positional NO es una ruta.
//
// `noconformidad listar` es el caso: su primer positional es la accion. Antes
// se llamaba a `Ejecutar` pasandole el almacen como ruta de trabajo, y la
// linea salia `noconformidad <ruta> listar`, que el motor rechaza por
// argumento invalido. Esta capa lo traducia a «el motor no devolvio un
// documento que esta plataforma entienda», que es verdad y no dice nada.
//
// `dentroDe` no se le pasa al motor: es el espacio del cliente, y existe para
// que un verbo sin ruta siga sin poder correrse fuera de el.
func (m *Motor) EjecutarSinRuta(ctx context.Context, verbo, dentroDe string,
	args ...string) (Resultado, error) {
	if _, err := m.rutaSegura(dentroDe); err != nil {
		return Resultado{Verbo: verbo}, err
	}
	return m.correr(ctx, verbo, append([]string{}, args...))
}

// Ejecutar corre un verbo con --json sobre una ruta de trabajo.
func (m *Motor) Ejecutar(ctx context.Context, verbo, trabajo string, args ...string) (Resultado, error) {
	abs, err := m.rutaSegura(trabajo)
	if err != nil {
		return Resultado{Verbo: verbo}, err
	}
	return m.correr(ctx, verbo, append([]string{abs}, args...))
}

func (m *Motor) correr(ctx context.Context, verbo string, args []string) (Resultado, error) {
	inicio := time.Now()
	if err := m.ArgumentosSeguros(args); err != nil {
		return Resultado{Verbo: verbo}, err
	}
	ctx, cancelar := context.WithTimeout(ctx, m.Plazo)
	defer cancelar()

	completos := append([]string{verbo}, args...)
	completos = append(completos, "--json")
	cmd := exec.CommandContext(ctx, m.Binario, completos...)
	var salida, errores bytes.Buffer
	cmd.Stdout, cmd.Stderr = &salida, &errores

	codigo := 0
	if err := cmd.Run(); err != nil {
		var ee *exec.ExitError
		if errors.As(err, &ee) {
			codigo = ee.ExitCode()
		} else {
			return Resultado{Verbo: verbo}, fmt.Errorf("%s: %w", verbo, err)
		}
	}
	if ctx.Err() != nil {
		return Resultado{Verbo: verbo}, fmt.Errorf("%s: se paso del plazo de %s", verbo, m.Plazo)
	}

	var doc map[string]any
	if err := json.Unmarshal(salida.Bytes(), &doc); err != nil {
		return Resultado{Verbo: verbo, Codigo: codigo}, fmt.Errorf(
			"%s: la salida no es un documento JSON (codigo %d): %s",
			verbo, codigo, primeraLinea(errores.String()))
	}
	esquema, _ := doc["esquema"].(string)
	if esquema == "" {
		return Resultado{Verbo: verbo, Codigo: codigo}, fmt.Errorf(
			"%s: el documento no declara su campo `esquema`, asi que no se puede saber si esta plataforma lo entiende", verbo)
	}
	return Resultado{
		Verbo: verbo, Codigo: codigo, Documento: doc,
		Esquema: esquema, Duracion: time.Since(inicio),
	}, nil
}

func primeraLinea(s string) string {
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		s = s[:i]
	}
	if len(s) > 220 {
		s = s[:220]
	}
	return strings.TrimSpace(s)
}
