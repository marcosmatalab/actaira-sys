package api

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestElPanelSeSirveDelPropioServidor(t *testing.T) {
	// Servida aqui, la pagina y la API comparten origen: no hace falta CORS,
	// no hay una lista de origenes que alguien acabara poniendo en `*`, y no
	// hay un segundo sitio donde desplegar una version que se queda vieja.
	s, _ := montar(t)
	w := pedir(t, s, "GET", "/", "", "")
	if w.Code != http.StatusOK {
		t.Fatalf("salio %d", w.Code)
	}
	if !strings.Contains(w.Header().Get("Content-Type"), "text/html") {
		t.Errorf("tipo: %q", w.Header().Get("Content-Type"))
	}
	csp := w.Header().Get("Content-Security-Policy")
	for _, trozo := range []string{"connect-src 'self'", "frame-ancestors 'none'",
		"default-src 'none'"} {
		if !strings.Contains(csp, trozo) {
			t.Errorf("la politica no lleva %q: %s", trozo, csp)
		}
	}
	if !strings.Contains(w.Body.String(), "Actaira") {
		t.Error("la pagina no parece la pagina")
	}
}

func TestElPanelQueSeSirveEsElQueHAYENELARBOL(t *testing.T) {
	// Si el binario lleva una copia vieja, el cliente ve una pantalla que ya
	// no existe y nadie se entera: compila, arranca y sirve. `make panel`
	// copia la construida, y esto comprueba que se hizo.
	enElArbol, err := os.ReadFile(filepath.Join("..", "..", "panel", "panel.html"))
	if err != nil {
		t.Skip("sin panel construido: corre `make panel`")
	}
	if string(enElArbol) != string(panelHTML) {
		t.Error("el panel incrustado no es el construido: corre `make panel`")
	}
}

func TestUnaRutaQueNoExisteNoDevuelveLaPagina(t *testing.T) {
	// `GET /` en Go casa con TODO lo que no case con otra ruta, asi que sin
	// esta comprobacion un `/v1/clientes/acme/lo-que-sea` devolveria la pagina
	// con un 200 y quien la llamara la leeria como un documento.
	s, _ := montar(t)
	w := pedir(t, s, "GET", "/v1/lo-que-sea", TOKEN, "")
	if w.Code != http.StatusNotFound {
		t.Fatalf("salio %d", w.Code)
	}
	if strings.Contains(w.Body.String(), "<html") {
		t.Error("devuelve la pagina donde deberia decir que no hay nada")
	}
}

func TestLaPaginaNoLlevaCredencialesDentro(t *testing.T) {
	// La primera version de esta prueba tambien buscaba «acme», y salto con el
	// `placeholder="acme"` del formulario. Un ejemplo escrito en gris dentro de
	// un campo vacio no es una credencial ni un cliente configurado, y dejar la
	// prueba asi habria obligado a quitar el ejemplo -- que es justo lo que
	// hace intuitivo el formulario -- para callar un rojo que no decia nada.
	s, _ := montar(t)
	w := pedir(t, s, "GET", "/", "", "")
	cuerpo := w.Body.String()
	for _, filtracion := range []string{TOKEN, OTRO, "Bearer ey"} {
		if strings.Contains(cuerpo, filtracion) {
			t.Errorf("la pagina lleva %q dentro", filtracion)
		}
	}
	// Y los dos campos salen VACIOS: un `value=` ahi seria una credencial o un
	// cliente horneados en el binario.
	for _, id := range []string{"credencial", "cliente"} {
		i := strings.Index(cuerpo, `id="`+id+`"`)
		if i < 0 {
			t.Fatalf("no esta el campo %q", id)
		}
		fin := i + strings.Index(cuerpo[i:], ">")
		if strings.Contains(cuerpo[i:fin], "value=") {
			t.Errorf("el campo %q viene relleno: %s", id, cuerpo[i:fin])
		}
	}
}

var _ = httptest.NewRequest
