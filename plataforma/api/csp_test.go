package api

import (
	"strings"
	"testing"
)

// La politica llevaba `script-src 'unsafe-inline'` y `style-src
// 'unsafe-inline'`, que apagan casi entera la proteccion contra inyeccion de
// script. Estas pruebas fijan que no vuelvan, y que lo que las sustituye cubra
// de verdad la pagina que se sirve.

func TestLaPoliticaNoPermiteScriptEnLinea(t *testing.T) {
	p := PoliticaDelPanel
	directivas := map[string]string{}
	for _, d := range strings.Split(p, "; ") {
		partes := strings.SplitN(d, " ", 2)
		if len(partes) == 2 {
			directivas[partes[0]] = partes[1]
		} else {
			directivas[partes[0]] = ""
		}
	}
	if strings.Contains(directivas["script-src"], "'unsafe-inline'") {
		t.Errorf("script-src volvio a permitir codigo en linea: %q", directivas["script-src"])
	}
	if !strings.Contains(directivas["script-src"], "'sha256-") {
		t.Errorf("script-src no nombra el hash del bloque: %q", directivas["script-src"])
	}
	// `style-src-attr 'unsafe-inline'` SI esta, y es otra cosa: permite los
	// atributos `style=` del HTML y NO permite un `<style>` inyectado. Lo que
	// no puede volver es el `'unsafe-inline'` de `style-src` a secas.
	if strings.Contains(directivas["style-src"], "'unsafe-inline'") {
		t.Errorf("style-src volvio a permitir un <style> inyectado: %q", directivas["style-src"])
	}
	if directivas["connect-src"] != "'self'" {
		t.Errorf("connect-src dejo de ser 'self': %q. Es lo que impide que un script "+
			"colado en la pagina se mande el expediente del cliente a otro sitio",
			directivas["connect-src"])
	}
}

func TestLaPoliticaSeCalculaDeLaPaginaQueDeVerdadSeSIRVE(t *testing.T) {
	// Un hash escrito a mano se queda viejo en cuanto alguien toca el panel, y
	// se manifiesta de la peor forma: la pagina deja de funcionar entera, asi
	// que quien lo sufre vuelve a poner `'unsafe-inline'` y sigue. Aqui se
	// comprueba que cambiar la pagina cambia la politica.
	otra := politicaDe([]byte("<html><style>body{color:red}</style>" +
		"<script>console.log(1)</script></html>"))
	if otra == PoliticaDelPanel {
		t.Fatal("dos paginas distintas dan la misma politica: no se esta calculando")
	}
	if !strings.Contains(otra, "'sha256-") {
		t.Fatalf("no salio ningun hash: %q", otra)
	}
}

func TestUnaPaginaSinBloquesNoProduceUnaPoliticaVacia(t *testing.T) {
	// Una politica con `script-src ` y nada detras no es restrictiva: segun el
	// navegador, es invalida y se ignora entera. Fallar hacia `'none'` es lo
	// unico correcto aqui.
	p := politicaDe([]byte("<html><body>nada</body></html>"))
	if !strings.Contains(p, "script-src 'none'") {
		t.Errorf("script-src no cayo a 'none': %q", p)
	}
	if !strings.Contains(p, "style-src 'none'") {
		t.Errorf("style-src no cayo a 'none': %q", p)
	}
}
