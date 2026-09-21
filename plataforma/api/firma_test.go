package api

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// La ruta de eventos estaba protegida SOLO por la credencial del cliente. Las
// dos cosas responden preguntas distintas: la credencial dice que quien llama
// puede tocar el espacio de este cliente; la firma dice que el CUERPO viene del
// proveedor y llego intacto.
//
// Con solo la credencial, cualquiera que la tenga puede inventarse un evento --
// decir que se empujo un commit que no existe -- y el motor decidiria sobre el
// y lo escribiria en el expediente. Y la credencial la tienen mas manos de las
// que parece: esta en la configuracion del webhook, en el gestor de secretos y
// en la integracion continua.

const SECRETO = "un-secreto-compartido-largo-de-verdad"

func firmar(cuerpo, secreto string) string {
	m := hmac.New(sha256.New, []byte(secreto))
	m.Write([]byte(cuerpo))
	return "sha256=" + hex.EncodeToString(m.Sum(nil))
}

func conFirma(t *testing.T, s *Servidor, cuerpo, cabecera, valor string) *httptest.ResponseRecorder {
	t.Helper()
	r := httptest.NewRequest("POST", "/v1/clientes/acme/empujon", strings.NewReader(cuerpo))
	r.Header.Set("Authorization", "Bearer "+TOKEN)
	r.Header.Set("Content-Type", "application/json")
	if cabecera != "" {
		r.Header.Set(cabecera, valor)
	}
	w := httptest.NewRecorder()
	s.Rutas().ServeHTTP(w, r)
	return w
}

func TestSinSecretoConfiguradoElEventoSeAtiendeYSeDICE(t *testing.T) {
	// El tercer estado. Exigir la firma siempre romperia a todo el que ya tiene
	// el webhook puesto sin secreto, que es como se configura por omision en
	// casi todos los sistemas; y lo que hace la gente cuando su integracion
	// deja de funcionar de golpe no es configurar el secreto, es quitar el
	// webhook. Se atiende, y NO en silencio.
	elMotor(t)
	s, raiz := montar(t)
	conRepositorio(t, raiz)

	cuerpo := cuerpoDeEmpujon(strings.Repeat("a", 40), "y")
	w := conFirma(t, s, cuerpo, "", "")
	if w.Code != http.StatusOK {
		t.Fatalf("sin secreto configurado el evento tiene que atenderse: %d", w.Code)
	}
	var r Respuesta
	if err := json.Unmarshal(w.Body.Bytes(), &r); err != nil {
		t.Fatal(err)
	}
	if r.FirmaVerificada == nil {
		t.Fatal("la respuesta no dice si el evento venia firmado")
	}
	if *r.FirmaVerificada {
		t.Error("dice que la firma se verifico y no habia secreto con que verificarla")
	}
}

func TestConSecretoUnaFirmaCORRECTAPasa(t *testing.T) {
	elMotor(t)
	t.Setenv(VariableDelSecreto+"ACME", SECRETO)
	s, raiz := montar(t)
	conRepositorio(t, raiz)

	cuerpo := cuerpoDeEmpujon(strings.Repeat("a", 40), "y")
	w := conFirma(t, s, cuerpo, "X-Hub-Signature-256", firmar(cuerpo, SECRETO))
	if w.Code != http.StatusOK {
		t.Fatalf("una firma correcta se rechazo: %d — %s", w.Code, w.Body.String())
	}
	var r Respuesta
	_ = json.Unmarshal(w.Body.Bytes(), &r)
	if r.FirmaVerificada == nil || !*r.FirmaVerificada {
		t.Error("la respuesta no dice que la firma se verifico")
	}
}

func TestConSecretoUnCuerpoCAMBIADONoPasa(t *testing.T) {
	// Lo que la firma demuestra de verdad: que el cuerpo llego intacto. Se
	// firma un cuerpo y se manda otro.
	elMotor(t)
	t.Setenv(VariableDelSecreto+"ACME", SECRETO)
	s, raiz := montar(t)
	conRepositorio(t, raiz)

	original := cuerpoDeEmpujon(strings.Repeat("a", 40), "y")
	otro := cuerpoDeEmpujon(strings.Repeat("c", 40), "y")
	w := conFirma(t, s, otro, "X-Hub-Signature-256", firmar(original, SECRETO))
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("un cuerpo cambiado paso con %d", w.Code)
	}
}

func TestConSecretoUnEventoSINFirmaSeRECHAZA(t *testing.T) {
	// La via de escape que habria convertido la firma en un adorno: si un
	// cliente configura secreto y un evento llega sin cabecera, dejarlo pasar
	// «por compatibilidad» haria que bastara con quitar la cabecera.
	elMotor(t)
	t.Setenv(VariableDelSecreto+"ACME", SECRETO)
	s, raiz := montar(t)
	conRepositorio(t, raiz)

	w := conFirma(t, s, cuerpoDeEmpujon(strings.Repeat("a", 40), "y"), "", "")
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("un evento sin firmar paso con %d en un cliente que firma", w.Code)
	}
	if !strings.Contains(w.Body.String(), "firma") {
		t.Errorf("el rechazo no dice que fue por la firma: %s", w.Body.String())
	}
}

func TestLaFirmaDeOTROSecretoNoPasa(t *testing.T) {
	elMotor(t)
	t.Setenv(VariableDelSecreto+"ACME", SECRETO)
	s, raiz := montar(t)
	conRepositorio(t, raiz)

	cuerpo := cuerpoDeEmpujon(strings.Repeat("a", 40), "y")
	w := conFirma(t, s, cuerpo, "X-Hub-Signature-256", firmar(cuerpo, "otro-secreto-distinto"))
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("la firma de otro secreto paso con %d", w.Code)
	}
}

func TestElSecretoSeBuscaPorElNombreDELCliente(t *testing.T) {
	// Un secreto compartido entre clientes seria un solo secreto para todos: el
	// que lo tenga puede firmar eventos en el expediente de cualquiera.
	t.Setenv(VariableDelSecreto+"ACME", SECRETO)
	if s, hay := secretoDe("acme"); !hay || s != SECRETO {
		t.Error("no encuentra el secreto de su propio cliente")
	}
	if _, hay := secretoDe("beta"); hay {
		t.Error("el secreto de acme vale para beta")
	}
	// Un guion no puede ir en una variable de entorno y se convierte.
	t.Setenv(VariableDelSecreto+"MI_CLIENTE", "x")
	if _, hay := secretoDe("mi-cliente"); !hay {
		t.Error("un cliente con guion en el nombre no encuentra su secreto")
	}
}

func TestVerificarFirmaDistingueLosTresEstados(t *testing.T) {
	// Sin secreto, con firma buena y con firma mala son tres cosas, y la de en
	// medio no puede colapsar en ninguna de las otras dos.
	cuerpo := []byte(`{"x":1}`)
	r := httptest.NewRequest("POST", "/x", nil)

	if err := verificarFirma(r, "acme", cuerpo); !errors.Is(err, ErrSinSecreto) {
		t.Fatalf("sin secreto tiene que decir ErrSinSecreto: %v", err)
	}

	t.Setenv(VariableDelSecreto+"ACME", SECRETO)
	r.Header.Set("X-Actaira-Firma", strings.TrimPrefix(firmar(string(cuerpo), SECRETO), "sha256="))
	if err := verificarFirma(r, "acme", cuerpo); err != nil {
		t.Fatalf("una firma correcta con la cabecera propia fallo: %v", err)
	}

	r.Header.Set("X-Actaira-Firma", "0000")
	if err := verificarFirma(r, "acme", cuerpo); !errors.Is(err, ErrFirmaNoValida) {
		t.Fatalf("una firma mala tiene que decir ErrFirmaNoValida: %v", err)
	}
}
