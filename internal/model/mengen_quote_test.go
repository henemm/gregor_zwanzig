package model

// TDD RED — Mengen-Quoten je Tier (S5, Issue #2482). Spec:
// docs/specs/modules/mengen_quoten_je_tier.md — AC-3 (Grenzwert-Tabelle,
// fail-closed free).
//
// RED-Signal: QuotaFor und Quota existieren nicht (Uebersetzungsfehler, auf
// das Paket model begrenzt).

import "testing"

func TestQuotaFor_TabelleJeTarif(t *testing.T) {
	faelle := []struct {
		tier string
		want Quota
	}{
		{"free", Quota{Trips: 3, ComparePresets: 2, Locations: 10}},
		{"standard", Quota{Trips: 15, ComparePresets: 10, Locations: 50}},
		{"premium", Quota{Trips: 50, ComparePresets: 30, Locations: 200}},
	}
	for _, f := range faelle {
		if got := QuotaFor(f.tier); got != f.want {
			t.Errorf("QuotaFor(%q) = %+v, erwartet %+v", f.tier, got, f.want)
		}
	}
}

// Leerer oder unbekannter Tarif ist fail-closed free — auch ohne dass der
// Aufrufer vorher EffectiveTier anwendet.
func TestQuotaFor_LeerOderUnbekanntIstFree(t *testing.T) {
	free := QuotaFor("free")
	for _, tier := range []string{"", "gold", "Premium", "admin"} {
		if got := QuotaFor(tier); got != free {
			t.Errorf("QuotaFor(%q) = %+v, erwartet free %+v", tier, got, free)
		}
	}
}
