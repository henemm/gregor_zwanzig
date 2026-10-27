package store

// Issue #2216 — ComparePresetsUsingLocation: welche Ortsvergleiche des Nutzers
// referenzieren einen Ort. Spec: fix_2216_ort_loeschen_sperre.md.

import (
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

func speichereVergleich(t *testing.T, s *Store, id string, locIDs ...string) {
	t.Helper()
	p := model.ComparePreset{ID: id, Name: "N-" + id, LocationIDs: locIDs, Schedule: "daily", Profil: "ALLGEMEIN"}
	if err := s.SaveComparePreset(p); err != nil {
		t.Fatalf("Vorbedingung: %v", err)
	}
}

func TestComparePresetsUsingLocation_TrefferUndKeinTreffer(t *testing.T) {
	s := New(t.TempDir(), "test").WithUser("nutzer-usage-2216")
	speichereVergleich(t, s, "c1", "a", "b")
	speichereVergleich(t, s, "c2", "b")
	speichereVergleich(t, s, "c3", "c")

	got, err := s.ComparePresetsUsingLocation("b")
	if err != nil {
		t.Fatal(err)
	}
	ids := map[string]bool{}
	for _, p := range got {
		ids[p.ID] = true
	}
	if len(got) != 2 || !ids["c1"] || !ids["c2"] {
		t.Errorf("erwartet c1+c2, bekommen %v", ids)
	}
	none, err := s.ComparePresetsUsingLocation("unbenutzt")
	if err != nil || len(none) != 0 {
		t.Errorf("erwartet leer ohne Fehler, bekommen %v / %v", none, err)
	}
}

func TestComparePresetsUsingLocation_Nutzertrennung(t *testing.T) {
	base := New(t.TempDir(), "test")
	a, b := base.WithUser("nutzer-a-2216"), base.WithUser("nutzer-b-2216")
	speichereVergleich(t, a, "ca", "x")

	got, err := b.ComparePresetsUsingLocation("x")
	if err != nil || len(got) != 0 {
		t.Errorf("B darf A's Vergleiche nicht sehen: %v / %v", got, err)
	}
}
