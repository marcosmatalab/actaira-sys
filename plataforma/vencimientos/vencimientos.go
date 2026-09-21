// Package vencimientos es el unico trabajo que la suscripcion hace de verdad:
// darse cuenta de que algo dejo de valer sin que nadie haya empujado nada.
//
// POR QUE NO BARRE EL REPOSITORIO
// --------------------------------
// Para saber QUE CADUCO no hace falta el codigo del cliente: hace falta su
// almacen de evidencia y un reloj. El motor tiene un modo para eso
// (`vigilar --solo-almacen`) y este paquete lo usa. Pedirle el repositorio a un
// cliente que no ha empujado nada seria trabajo inutil y ademas obligaria a
// tener una copia fresca de su codigo permanentemente, que es exactamente lo
// que un cliente con secretos en el repositorio no quiere.
//
// POR QUE NO CALCULA LA CADUCIDAD AQUI
// -------------------------------------
// Seria una tarde de trabajo y dos definiciones de la misma propiedad. La regla
// 10 de esta casa: dos comprobaciones sobre la misma propiedad comparten su
// definicion o SE ANULAN. La frescura, la revalidacion y los cinco estados
// viven en el motor, con sus pruebas, y aqui solo se lee la respuesta.
package vencimientos

import (
	"context"
	"fmt"
	"sort"
	"time"

	"actaira.com/plataforma/cliente"
	"actaira.com/plataforma/motor"
)

// Aviso es lo que se le manda a una persona. Nunca lleva un veredicto: lleva
// que hay que volver a mirar y por que.
type Aviso struct {
	Cliente   string
	Cuando    time.Time
	Controles []string          // los que hay que volver a observar
	Estados   map[string]int    // cuantos en cada estado
	Motivos   map[string]string // control -> por que, en el idioma pedido
}

// HayQueAvisar es falso cuando no hay nada que volver a mirar. Un aviso vacio
// enviado igualmente ensena a la gente a archivar los avisos sin leerlos.
func (a Aviso) HayQueAvisar() bool { return len(a.Controles) > 0 }

type Revisor struct {
	Espacio *cliente.Espacio
	Motor   *motor.Motor
	Idioma  string // "es" o "en"
}

// Revisar pregunta al motor que caduco para UN cliente.
func (r *Revisor) Revisar(ctx context.Context, id string, ahora time.Time) (Aviso, error) {
	c, err := r.Espacio.De(id)
	if err != nil {
		return Aviso{}, err
	}
	res, err := r.Motor.Ejecutar(ctx, "vigilar", c.Raiz,
		"--solo-almacen", "--almacen", c.Almacen(),
		"--ahora", ahora.UTC().Format(time.RFC3339))
	if err != nil {
		return Aviso{}, fmt.Errorf("cliente %s: %w", id, err)
	}
	if res.Esquema != "actaira/vigilancia/v1" {
		return Aviso{}, fmt.Errorf("cliente %s: esquema inesperado %q", id, res.Esquema)
	}

	aviso := Aviso{Cliente: id, Cuando: ahora, Estados: map[string]int{},
		Motivos: map[string]string{}}
	for _, x := range comoLista(res.Documento["a_reobservar"]) {
		if s, vale := x.(string); vale {
			aviso.Controles = append(aviso.Controles, s)
		}
	}
	sort.Strings(aviso.Controles)
	if cuenta, vale := res.Documento["recuento"].(map[string]any); vale {
		for k, v := range cuenta {
			if n, esNumero := v.(float64); esNumero {
				aviso.Estados[k] = int(n)
			}
		}
	}
	for _, v := range comoLista(res.Documento["veredictos"]) {
		m, vale := v.(map[string]any)
		if !vale || m["accion"] != "reobservar" {
			continue
		}
		id, _ := m["control_id"].(string)
		if motivos, hay := m["motivo"].(map[string]any); hay {
			if t, esTexto := motivos[r.idioma()].(string); esTexto {
				aviso.Motivos[id] = t
			}
		}
	}
	return aviso, nil
}

// RevisarTodos recorre el espacio entero. Un cliente que falla NO detiene a los
// demas: se devuelve su error y se sigue, porque si no, el primer almacen
// corrupto deja sin aviso a todos los clientes de detras.
func (r *Revisor) RevisarTodos(ctx context.Context, ahora time.Time) ([]Aviso, []error) {
	ids, err := r.Espacio.Todos()
	if err != nil {
		return nil, []error{err}
	}
	var avisos []Aviso
	var fallos []error
	for _, id := range ids {
		a, err := r.Revisar(ctx, id, ahora)
		if err != nil {
			fallos = append(fallos, err)
			continue
		}
		if a.HayQueAvisar() {
			avisos = append(avisos, a)
		}
	}
	return avisos, fallos
}

func (r *Revisor) idioma() string {
	if r.Idioma == "en" {
		return "en"
	}
	return "es"
}

func comoLista(v any) []any {
	l, _ := v.([]any)
	return l
}
