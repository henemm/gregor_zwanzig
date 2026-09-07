// TDD-RED fuer Issue #2142 Scheibe 1 (AC-4, Test 4): Installationsreihenfolge
// ist eine Zusicherung, keine Stilfrage.
//
// egress.Install merkt sich den vorgefundenen Transport und stellt ihn bei
// Uninstall zeiger-identisch wieder her. Laeuft coreauth.Install NACH
// egress.Install, verschwindet der Auth-Header bei einem egress.Uninstall()
// still mit — und jeder Aufruf an den Python-Core liefe ab Scheibe 2 in 401.
package coreauth

import (
	"net/http"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/egress"
)

func TestCoreAuthSurvivesEgressUninstall(t *testing.T) {
	var core captured
	coreSrv := newCapturingServer(t, &core)

	// Env=staging, weil egress.Install nur in Staging bzw. mit TestFixtureDir
	// installiert; ohne echten Egress-Waechter waere die Reihenfolge nicht
	// pruefbar.
	cfg := &config.Config{
		PythonCoreURL:    coreSrv.URL,
		CoreSharedSecret: testCoreSecret,
		Env:              "staging",
	}

	orig := http.DefaultTransport
	Install(cfg)
	installed := egress.Install(cfg)
	t.Cleanup(func() {
		egress.Uninstall()
		Uninstall()
		http.DefaultTransport = orig
	})
	if !installed {
		t.Fatal("egress.Install haette in Staging installieren muessen — Reihenfolge sonst nicht pruefbar")
	}

	egress.Uninstall()

	mustGet(t, coreSrv.URL+"/config")
	if core.hits != 1 {
		t.Fatalf("Positivkontrolle: Python-Core-Fake wurde nicht erreicht (hits=%d)", core.hits)
	}
	if core.header != testCoreSecret {
		t.Fatalf("Auth-Header nach egress.Uninstall() verloren: erwartet %q, angekommen %q", testCoreSecret, core.header)
	}
}
