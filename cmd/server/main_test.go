// TDD fuer Issue #2142 Adversary-Finding F002: die Installationsreihenfolge
// der Transport-Waechter muss dort geprueft werden, wo sie wirkt — in der von
// main() tatsaechlich aufgerufenen installGuards() — nicht in einer im
// Testkoerper nachgebauten Aufrufkette.
package main

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/coreauth"
	"github.com/henemm/gregor-api/internal/egress"
)

func TestInstallGuardsOrderSurvivesEgressUninstall(t *testing.T) {
	var hits int
	var gotHeader string
	coreSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		gotHeader = r.Header.Get("X-GZ-Core-Auth")
		w.WriteHeader(http.StatusOK)
	}))
	defer coreSrv.Close()

	const secret = "core-shared-secret-fuer-main-test-0123456789"
	cfg := &config.Config{
		PythonCoreURL:    coreSrv.URL,
		CoreSharedSecret: secret,
		// Env=staging, weil egress.Install nur in Staging bzw. mit
		// TestFixtureDir installiert; ohne echten Egress-Waechter-Zyklus
		// waere die Reihenfolge nicht pruefbar.
		Env: "staging",
	}

	orig := http.DefaultTransport
	t.Cleanup(func() {
		egress.Uninstall()
		coreauth.Uninstall()
		http.DefaultTransport = orig
	})

	// Das ist die Pruefstelle: dieselbe Funktion, die main() aufruft.
	installGuards(cfg)

	// egress.Uninstall() darf den Auth-Header-Transport NICHT mit entfernen.
	egress.Uninstall()

	resp, err := http.Get(coreSrv.URL + "/config")
	if err != nil {
		t.Fatalf("GET fehlgeschlagen: %v", err)
	}
	resp.Body.Close()

	if hits != 1 {
		t.Fatalf("Positivkontrolle: Python-Core-Fake wurde nicht erreicht (hits=%d)", hits)
	}
	if gotHeader != secret {
		t.Fatalf("Auth-Header nach egress.Uninstall() verloren: erwartet %q, angekommen %q", secret, gotHeader)
	}
}
