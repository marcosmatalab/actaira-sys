package api

import (
	"context"
	"net/http"
)

// La identidad verificada, llevada CON la peticion y no en el servidor.
//
// Dos peticiones a la vez tienen dos identidades. Guardarla en un campo del
// servidor -- que es la forma comoda -- haria que la segunda pisara a la
// primera, y el sintoma seria el peor posible: bajo carga, de vez en cuando,
// alguien opera con los permisos de otro. No falla nada, no salta ninguna
// prueba, y ocurre justo cuando hay trafico.

type claveDeIdentidad struct{}

func conIdentidad(ctx context.Context, id Identidad) context.Context {
	return context.WithValue(ctx, claveDeIdentidad{}, id)
}

// IdentidadDe saca la identidad verificada de una peticion.
//
// El segundo valor es false cuando no hay emisor configurado, es decir, cuando
// el servidor corre con credenciales estaticas. NO es lo mismo que una
// identidad vacia: con credenciales estaticas no hay papeles que comprobar, y
// tratar «no hay identidad» como «identidad sin papeles» dejaria ese modo sin
// poder hacer nada.
func IdentidadDe(r *http.Request) (Identidad, bool) {
	id, ok := r.Context().Value(claveDeIdentidad{}).(Identidad)
	return id, ok
}

// exigirPapel comprueba el permiso del verbo contra los roles del testigo.
//
// Devuelve true si se puede seguir. Si no, ya ha contestado 403.
//
// Con credenciales estaticas devuelve true siempre y NO en silencio: ese modo
// no tiene papeles, y el arranque lo dice con todas las letras. La alternativa
// -- inventarle un papel por omision al modo estatico -- seria peor de las dos
// maneras posibles: si es `admin`, el modo estatico se salta el control; si es
// `lectura`, el modo estatico deja de funcionar y nadie entiende por que.
func (s *Servidor) exigirPapel(w http.ResponseWriter, r *http.Request, verbo string) bool {
	id, hay := IdentidadDe(r)
	if !hay {
		return true
	}
	if Puede(id.Roles, verbo) {
		return true
	}
	s.registro.Warn("verbo rechazado por permisos",
		"sujeto", id.Sujeto, "cliente", id.Cliente, "verbo", verbo, "roles", id.Roles)
	fallar(w, http.StatusForbidden,
		"esta credencial no alcanza para eso: "+ExplicarNegativa(id.Roles, verbo),
		"this credential is not enough for that: "+ExplicarNegativa(id.Roles, verbo))
	return false
}
