package api

import (
	"encoding/json"
	"net/http"
	"strings"
	"testing"
)

// TODA ruta publicada se llama contra el MOTOR DE VERDAD.
//
// Este fichero existe porque el mismo fallo ocurrio cuatro veces en este arbol:
// un manejador le pasa al motor una bandera que ese verbo no acepta, la linea
// de mandatos falla por argumento invalido, y esta capa lo traduce a «el motor
// no devolvio un documento que esta plataforma entienda». El mensaje es cierto
// y no dice nada, y sobre todo: COMPILA.
//
// Paso con `noconformidad`, al que se le pasaba el almacen como ruta de trabajo
// y salia `noconformidad <ruta> listar`. Y volvio a pasar con `preguntar` y
// `soa` (que no tienen `--almacen`) y con `almacen` (que no tiene `--idioma`)
// en cuanto se anadieron cinco rutas de lectura de golpe. Las tres compilaban.
//
// Lo unico que lo encuentra es llamar. Las pruebas de esta capa corren con un
// motor falso -- tienen que hacerlo, o dependerian del interprete -- y un motor
// falso contesta a cualquier bandera.

func TestTodaRutaPublicadaContestaConUnDocumento(t *testing.T) {
	elMotor(t) // salta si no hay binario: esto necesita el motor de verdad
	s, raiz := montar(t)
	// CON el repositorio del cliente puesto. Sin el, `plan` y los demas verbos
	// que leen codigo fallan por una razon que no tiene nada que ver con lo que
	// esta prueba mide, y el rojo apunta al sitio equivocado.
	conRepositorio(t, raiz)

	perfil := `{"roles":["proveedor"],"alto_riesgo":"si",` +
		`"via_anexo":"anexo_iii","fecha":"2027-12-02"}`

	for _, v := range VERBOS {
		ruta := strings.Replace(v["ruta"], "{cliente}", "acme", 1)
		// La tabla publica la forma de la ruta, con sus alternativas para quien
		// la lee. Aqui hay que llamar a una concreta.
		ruta = strings.Replace(ruta, "?cual=iv|v", "?cual=iv", 1)

		var cuerpo string
		if v["metodo"] == "POST" && !strings.HasSuffix(ruta, "/empujon") {
			cuerpo = perfil
		}
		if strings.HasSuffix(ruta, "/empujon") {
			cuerpo = cuerpoDeEmpujon(strings.Repeat("a", 40), "y")
		}

		t.Run(v["verbo"], func(t *testing.T) {
			w := pedir(t, s, v["metodo"], ruta, TOKEN, cuerpo)
			if w.Code == http.StatusBadGateway {
				t.Fatalf("502 sobre %s %s: el motor no devolvio un documento. Casi "+
					"siempre es una bandera que ese verbo no acepta.\n  %s",
					v["metodo"], ruta, w.Body.String())
			}
			if w.Code != http.StatusOK {
				t.Fatalf("%s %s -> %d\n  %s", v["metodo"], ruta, w.Code, w.Body.String())
			}
			var r Respuesta
			if err := json.Unmarshal(w.Body.Bytes(), &r); err != nil {
				t.Fatalf("la respuesta no es JSON: %v", err)
			}
			esquema, _ := r.Documento["esquema"].(string)
			if esquema == "" {
				t.Fatalf("el documento no declara su `esquema`: %s",
					w.Body.String()[:min(300, len(w.Body.String()))])
			}
		})
	}
}

func TestLaTablaDeVerbosNoPublicaRutasQueNoExisten(t *testing.T) {
	// La tabla se publica para que un cliente no tenga que descubrir la API
	// probando. Una entrada que apunte a una ruta que el enrutador no tiene es
	// peor que no publicarla: manda a alguien a un 404 con la documentación en
	// la mano.
	s, _ := montar(t)
	mux, ok := s.Rutas().(*http.ServeMux)
	if !ok {
		t.Skip("el enrutador ya no es un ServeMux")
	}
	for _, v := range VERBOS {
		ruta := strings.Replace(v["ruta"], "{cliente}", "acme", 1)
		ruta = strings.Replace(ruta, "?cual=iv|v", "", 1)
		pet, err := http.NewRequest(v["metodo"], "http://x"+ruta, nil)
		if err != nil {
			t.Fatal(err)
		}
		if _, patron := mux.Handler(pet); patron == "" {
			t.Errorf("la tabla publica %s %s y el enrutador no la tiene",
				v["metodo"], v["ruta"])
		}
	}
}

func TestTodaRutaPublicadaDeclaraSusBanderas(t *testing.T) {
	// `BANDERAS` se comprueba contra el `--help` de cada verbo, y eso funciona.
	// Lo que no funcionaba es que la tabla es a mano: al anadir cinco rutas de
	// lectura de golpe nadie anadio sus banderas, asi que la puerta siguio
	// verde mientras tres de ellas mandaban banderas que su verbo no acepta.
	//
	// Una comprobacion que solo mira lo declarado se salta entera olvidandose
	// de declarar, que es lo que pasa siempre. Esto convierte el olvido en el
	// fallo.
	for _, v := range VERBOS {
		verbo := verboDe(v["verbo"])
		if _, hay := BANDERAS[verbo]; !hay {
			t.Errorf("la API publica el verbo %q y no declara que banderas le manda: "+
				"anadelo a BANDERAS o la comprobacion contra `--help` no lo mira", verbo)
		}
	}
}
