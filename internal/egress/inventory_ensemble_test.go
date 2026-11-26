// TDD RED — Issue #3348: Ensemble-Host im Egress-Inventar.
// Spec: docs/specs/modules/fix_3348_ensemble_egress.md, AC-3.
//
// Zwillingsliste zur Python-Seite: der Ensemble-Host von Open-Meteo steht mit
// derselben Isolationsart wie der Haupt-Host api.open-meteo.com.
// Python-Gegenstueck: tests/tdd/test_egress_ensemble_host_freigabe.py.
package egress

import "testing"

func TestInventoryDeclaresEnsembleHostLikeMainOpenMeteoHost(t *testing.T) {
	kind, ok := Inventory["ensemble-api.open-meteo.com"]
	if !ok || kind != TestAccess {
		t.Fatalf("ensemble-api.open-meteo.com must be declared TestAccess, got declared=%v kind=%q", ok, kind)
	}
	if kind != Inventory["api.open-meteo.com"] {
		t.Errorf("ensemble host kind %q differs from api.open-meteo.com %q", kind, Inventory["api.open-meteo.com"])
	}
}
