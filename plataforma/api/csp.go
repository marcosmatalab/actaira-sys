package api

import (
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"regexp"
	"strings"
)

// La politica de seguridad de contenido de la pagina, calculada de la PAGINA.
//
// QUE ESTABA MAL
// ---------------
// La politica llevaba `script-src 'unsafe-inline'` y `style-src
// 'unsafe-inline'`. Esas dos palabras apagan casi entera la proteccion contra
// inyeccion de script, que es de lo poco que una politica de seguridad de
// contenido sirve para dar. Estaban ahi por un motivo real -- la pagina se
// sirve como un solo fichero, con su estilo y su codigo dentro -- y no por
// descuido, pero el motivo no cambia el efecto.
//
// La alternativa habitual es un nonce por respuesta. Aqui no vale: la pagina
// esta incrustada en el binario con `go:embed` y se sirve tal cual, asi que
// meterle un nonce obligaria a reescribir el HTML en cada peticion.
//
// La que si vale es el hash. El contenido de cada bloque inline es fijo -- se
// fija al construir la pagina -- asi que su sha256 tambien lo es, y una
// politica que lo nombra permite ESE bloque y ningun otro. Un script inyectado
// despues no casa con ningun hash y el navegador no lo ejecuta.
//
// POR QUE SE CALCULA Y NO SE ESCRIBE
// ------------------------------------
// Un hash escrito a mano se queda viejo en cuanto alguien toca el panel, y la
// forma en que se manifiesta es la peor posible: la pagina deja de funcionar
// entera, asi que la reaccion natural de quien lo sufre es volver a poner
// `'unsafe-inline'` y seguir. Calcularlo de los bytes que se van a servir hace
// imposible que discrepen.

var (
	bloqueScript = regexp.MustCompile(`(?s)<script\b[^>]*>(.*?)</script>`)
	bloqueEstilo = regexp.MustCompile(`(?s)<style\b[^>]*>(.*?)</style>`)
)

// hashesDe devuelve las fuentes `'sha256-...'` de cada bloque que casa.
func hashesDe(html []byte, patron *regexp.Regexp) []string {
	var fuera []string
	vistos := map[string]bool{}
	for _, m := range patron.FindAllSubmatch(html, -1) {
		suma := sha256.Sum256(m[1])
		fuente := "'sha256-" + base64.StdEncoding.EncodeToString(suma[:]) + "'"
		if !vistos[fuente] {
			vistos[fuente] = true
			fuera = append(fuera, fuente)
		}
	}
	return fuera
}

// politicaDe arma la politica para ese HTML.
//
// `connect-src 'self'` es la directiva que de verdad importa y se queda: si
// alguien colara un script en la pagina, no podria mandarse el expediente del
// cliente a otro sitio. Que el campo de servidor de la pagina acepte texto
// libre y el navegador solo deje hablar con este origen era una contradiccion
// de la PANTALLA, no de la politica, y se arregla en la pantalla: ahora se
// rellena con su propio origen y dice por que.
func politicaDe(html []byte) string {
	script := hashesDe(html, bloqueScript)
	estilo := hashesDe(html, bloqueEstilo)
	if len(script) == 0 {
		// Sin ningun bloque reconocido, la politica quedaria vacia y la pagina
		// no arrancaria. Es un fallo de construccion, no una politica.
		script = []string{"'none'"}
	}
	if len(estilo) == 0 {
		estilo = []string{"'none'"}
	}
	return strings.Join([]string{
		"default-src 'none'",
		"img-src data:",
		// Los atributos `style=` sueltos del HTML no los cubre un hash de
		// bloque, asi que hace falta esta palabra aparte. Es mucho mas
		// estrecha que `'unsafe-inline'`: permite atributos de estilo y NO
		// permite un `<style>` inyectado.
		"style-src " + strings.Join(estilo, " ") +
			" 'unsafe-hashes' https://fonts.googleapis.com",
		"style-src-attr 'unsafe-inline'",
		"font-src https://fonts.gstatic.com",
		"script-src " + strings.Join(script, " "),
		"connect-src 'self'",
		"base-uri 'none'",
		"form-action 'none'",
		"frame-ancestors 'none'",
	}, "; ")
}

// PoliticaDelPanel es la politica del panel que sirve este binario. Se calcula
// una vez al arrancar, de los bytes incrustados.
var PoliticaDelPanel = politicaDe(panelHTML)

var _ = fmt.Sprintf // reservado para diagnosticos
