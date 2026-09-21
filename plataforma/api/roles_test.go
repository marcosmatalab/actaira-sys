package api

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// El vocabulario de roles tenia CUATRO copias escritas a mano -- el catalogo, el
// motor, este paquete y el panel -- y dos estaban mal. Este fichero fija las dos
// propiedades que impiden que vuelva a pasar: que la lista de aqui es la del
// motor, y que un rol que no este en ella no llega nunca a la linea de mandatos.

func TestLaListaDeRolesEsLaQuePublicaElMotor(t *testing.T) {
	// `panel/roles.json` lo genera el mismo guion que genera `roles_generado.go`
	// desde `motor/src/actaira_motor/roles.py`. Comparar los dos derivados entre
	// si comprueba que este lado no se ha quedado atras sin necesitar Python
	// para correr el test.
	ruta := filepath.Join("..", "..", "panel", "roles.json")
	crudo, err := os.ReadFile(ruta)
	if err != nil {
		t.Skipf("no esta %s: %v", ruta, err)
	}
	var doc struct {
		Roles []struct {
			ID string `json:"id"`
		} `json:"roles"`
	}
	if err := json.Unmarshal(crudo, &doc); err != nil {
		t.Fatal(err)
	}
	if len(doc.Roles) != len(RolesDelReglamento) {
		t.Fatalf("el panel conoce %d roles y este lado %d",
			len(doc.Roles), len(RolesDelReglamento))
	}
	for i, r := range doc.Roles {
		if r.ID != RolesDelReglamento[i] {
			t.Errorf("rol %d: el panel dice %q y este lado %q", i, r.ID, RolesDelReglamento[i])
		}
	}
}

func TestUnRolQueElMotorNoConoceNoLlegaALaLineaDeMandatos(t *testing.T) {
	// El caso real: el panel mandaba `responsable_del_despliegue`, la lista de
	// aqui tenia ese mismo nombre equivocado, asi que la validacion lo DEJABA
	// PASAR y el motor contestaba que no le ataba ninguna obligacion. Se
	// comprueban los dos nombres de entonces y uno inventado.
	for _, malo := range []string{
		"responsable_del_despliegue", "fabricante_de_productos", "rol_inventado_zzz",
	} {
		p := Perfil{Roles: []string{malo}}
		_, err := p.aArgumentos()
		if err == nil {
			t.Errorf("%q paso la validacion", malo)
			continue
		}
		if !strings.Contains(err.Error(), malo) {
			t.Errorf("el error de %q no lo nombra: %v", malo, err)
		}
	}
}

func TestLosSieteRolesDelReglamentoSiPasan(t *testing.T) {
	// La otra mitad: arreglarlo rechazando todo seria igual de inutil.
	for _, bueno := range RolesDelReglamento {
		p := Perfil{Roles: []string{bueno}}
		if _, err := p.aArgumentos(); err != nil {
			t.Errorf("%q no pasa: %v", bueno, err)
		}
	}
	if !RolConocido("proveedor_modelo") {
		t.Error("falta `proveedor_modelo`, que es el que no estaba declarado en ningun sitio")
	}
}
