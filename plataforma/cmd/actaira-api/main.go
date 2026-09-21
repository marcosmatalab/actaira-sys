// Comando actaira-api: sirve los verbos del motor por HTTP.
//
// No tiene configuracion por defecto que valga para produccion, y es a
// proposito. Sin fichero de credenciales no arranca; sin raiz de clientes no
// arranca; y el binario del motor se busca en el PATH para que la version que
// contesta por HTTP sea EXACTAMENTE la misma que corre quien la audita en su
// maquina.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"time"

	"actaira.com/plataforma/api"
	"actaira.com/plataforma/cliente"
	"actaira.com/plataforma/motor"
	"actaira.com/plataforma/vencimientos"
)

func main() {
	direccion := flag.String("escucha", "127.0.0.1:8787",
		"donde escuchar. Por defecto solo local: exponerlo a la red es una decision, no un descuido")
	raiz := flag.String("clientes", "", "la raiz bajo la que vive cada cliente")
	credenciales := flag.String("credenciales", "", "fichero JSON {token: cliente}, en 0600")
	binario := flag.String("motor", "actaira", "el ejecutable del motor")
	revisarCada := flag.Duration("revisar-cada", time.Hour,
		"cada cuanto se revisa que caduco, sin que nadie empuje nada. Cero lo apaga, "+
			"y apagarlo se dice en voz alta al arrancar: es el unico trabajo que la "+
			"suscripcion hace por su cuenta")
	bitacora := flag.String("bitacora", "",
		"fichero al que se anade cada pasada de vigilancia y cada intento de entrega. "+
			"Se anotan tambien las pasadas sin avisos: una bitacora que solo escribe "+
			"cuando hay algo no distingue «no habia nada» de «no se miro»")
	idiomaAvisos := flag.String("idioma-avisos", "es", "el idioma de los motivos: es o en")
	emisor := flag.String("emisor", "",
		"fichero JSON con la configuracion del proveedor de identidad: `iss`, `aud` y "+
			"sus claves publicas en PEM. Con el, el cliente y los papeles salen del "+
			"testigo firmado. Sin el se usan las credenciales estaticas, que no tienen "+
			"papeles ni caducan")
	topeGlobal := flag.Int("tope-global", api.TopesPorOmision.Global,
		"cuantos verbos del motor pueden correr a la vez en esta maquina. Cada uno es "+
			"un PROCESO que lee el repositorio entero de un cliente, asi que este numero "+
			"es memoria y CPU, no peticiones por minuto")
	topeCliente := flag.Int("tope-por-cliente", api.TopesPorOmision.PorCliente,
		"y cuantos puede tener un solo cliente. Es lo que impide que el primero que "+
			"llegue con veinte peticiones ocupe el tope global entero y deje fuera a los "+
			"demas, que comparten este binario")
	plazo := flag.Duration("plazo", 3*time.Minute, "lo que puede tardar un verbo")
	flag.Parse()

	registro := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelInfo}))

	if *raiz == "" || *credenciales == "" {
		fmt.Fprintln(os.Stderr,
			"hacen falta --clientes y --credenciales. Este servidor ejecuta procesos y lee\n"+
				"expedientes de varios clientes, asi que no tiene valores por defecto que\n"+
				"sirvan: un arranque comodo acaba siendo el arranque de produccion.")
		os.Exit(2)
	}

	cred, err := api.CargarCredenciales(*credenciales)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	espacio, err := cliente.AbrirEspacio(*raiz)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	m, err := motor.Nuevo(*binario, espacio.Raiz, *plazo)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	// EL REVISOR SE CONSTRUYE Y SE ARRANCA. Aqui habia un `nil`.
	//
	// El paquete `vencimientos` esta escrito, probado y documentado como «el
	// unico trabajo que la suscripcion hace de verdad», y no corria nunca: se
	// le pasaba `nil` al servidor y el campo no se leia en ningun sitio. El
	// producto decia tener vigilancia continua y lo que tenia era un endpoint
	// que alguien podia llamar si se acordaba, que es justo lo que se vende no
	// tener que hacer.
	rev := &vencimientos.Revisor{Espacio: espacio, Motor: m, Idioma: *idiomaAvisos}
	s, err := api.Nuevo(m, espacio, rev, cred, registro)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	s.ConTopes(api.Tope{Global: *topeGlobal, PorCliente: *topeCliente})

	// EL MODO DE AUTENTICACION, dicho en voz alta al arrancar.
	//
	// Los dos modos son legitimos y tienen alcances muy distintos, y lo unico
	// inaceptable es que quien opera el servidor no sepa cual esta puesto. Un
	// servidor con credenciales estaticas no tiene papeles: cualquier
	// credencial valida puede pedir cualquier verbo de su cliente.
	if *emisor != "" {
		e, err := api.CargarEmisor(*emisor)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		s.Emisor = e
		registro.Info("identidad por OIDC",
			"iss", e.Iss, "aud", e.Aud, "claves", len(e.Claves),
			"papeles", strings.Join(api.PapelesConocidos(), ","))
	} else {
		registro.Warn("identidad por CREDENCIAL ESTATICA: no hay papeles, asi que "+
			"cualquier credencial valida puede pedir cualquier verbo de su cliente, y "+
			"no caduca. Para repartir permisos, arranca con --emisor",
			"clientes", espacio.Raiz)
	}
	registro.Info("topes de concurrencia del motor",
		"global", s.Topes.Global, "por_cliente", s.Topes.PorCliente)

	ctx, parar := context.WithCancel(context.Background())
	defer parar()
	if *revisarCada > 0 {
		plan := &vencimientos.Planificador{
			Revisor: rev, Intervalo: *revisarCada, Registro: registro,
			Bitacora: *bitacora,
			// Sin destino configurado, la entrega escribe en el registro y dice
			// con todas las letras que nadie lo recibe. La alternativa -- no
			// arrancar -- es lo que habia, y dejaba el producto sin vigilancia
			// sin decirlo. Que arranque avisando de su propio limite es peor
			// que una entrega de verdad y mucho mejor que el silencio.
			Entregar: vencimientos.EntregaAlRegistro(registro),
		}
		s.Vigilancia = plan
		go func() {
			if err := plan.Correr(ctx); err != nil && !errors.Is(err, context.Canceled) {
				registro.Error("la vigilancia se paro", "error", err)
			}
		}()
		registro.Warn("vigilancia en marcha SIN destino de avisos configurado: "+
			"los avisos se escriben en este registro y no los recibe nadie",
			"revisar_cada", revisarCada.String())
	} else {
		registro.Warn("VIGILANCIA APAGADA con --revisar-cada=0: nada caducara por su " +
			"cuenta y el expediente solo se revisara cuando alguien lo pida")
	}

	servidor := &http.Server{
		Addr:              *direccion,
		Handler:           s.Rutas(),
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       60 * time.Second,
		// Sin WriteTimeout: un `plan` sobre un repositorio grande tarda mas que
		// cualquier valor razonable, y cortarlo por la mitad daria una
		// respuesta truncada que el cliente leeria como un documento.
	}
	registro.Info("escuchando", "direccion", *direccion, "clientes", espacio.Raiz)
	if err := servidor.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		registro.Error("el servidor se paro", "error", err)
		os.Exit(1)
	}
}
