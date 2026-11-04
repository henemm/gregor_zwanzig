package handler

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/store"
)

// Issue #2237 (AC-6/7/8): Loeschen ueber den ECHTEN Handler-Weg raeumt die
// Sperrdatei des eigenen Nutzers ab -- erst NACH dem Freigeben der Sperre
// (die Haltedauer bis zur Antwort prueft schreibsperre_frist_haltedauer_test.go).
// Echtes Dateisystem, zwei Nutzer mit gleicher ID.

func dlcExists(p string) bool { _, err := os.Stat(p); return err == nil }

// dlcSeedB legt fuer Nutzer B eine gleichnamige .json (ueber seed) und eine
// Sperrdatei mit eindeutigem Inhalt an und liefert beide Inhalte zurueck.
func dlcSeedB(t *testing.T, s *store.Store, id string, seed func()) (jsonB, lockB []byte) {
	t.Helper()
	seed()
	dir := s.WithUser("u-b").BriefingsDir()
	if err := os.WriteFile(filepath.Join(dir, id+".json.lock"), []byte("lock-b"), 0o600); err != nil {
		t.Fatal(err)
	}
	jb, err := os.ReadFile(filepath.Join(dir, id+".json"))
	if err != nil {
		t.Fatal(err)
	}
	return jb, []byte("lock-b")
}

func dlcAssertBUnchanged(t *testing.T, s *store.Store, id string, jsonB, lockB []byte) {
	t.Helper()
	dir := s.WithUser("u-b").BriefingsDir()
	for name, want := range map[string][]byte{id + ".json": jsonB, id + ".json.lock": lockB} {
		got, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil || !bytes.Equal(got, want) {
			t.Errorf("%s von Nutzer B veraendert/entfernt: err=%v", name, err)
		}
	}
}

// AC-8 + Zwei-Nutzer: DELETE /api/trips/{id} als A entfernt .json und .lock
// von A; .json und .lock von B mit gleicher ID bleiben byte-identisch.
func TestDeleteTripHandler_RaeumtEigeneSperrdateiAb_ZweiNutzer(t *testing.T) {
	s := store.New(t.TempDir(), "u-a")
	seedTrip(t, s.WithUser("u-a"), "t1", "A")
	jsonB, lockB := dlcSeedB(t, s, "t1", func() { seedTrip(t, s.WithUser("u-b"), "t1", "B") })

	w := p2158Do(DeleteTripHandler(s), "DELETE", "/api/trips/{id}", "/api/trips/t1", "", "u-a")
	if w.Code != 204 {
		t.Fatalf("DELETE: %d (%s)", w.Code, w.Body.String())
	}
	dirA := s.WithUser("u-a").BriefingsDir()
	for _, n := range []string{"t1.json", "t1.json.lock"} {
		if dlcExists(filepath.Join(dirA, n)) {
			t.Errorf("%s von A muss nach dem Loeschen weg sein", n)
		}
	}
	dlcAssertBUnchanged(t, s, "t1", jsonB, lockB)
}

// AC-6/7: DELETE /api/compare/presets/{id} als A entfernt .json und .lock von
// A; B mit gleicher Preset-ID bleibt unveraendert.
func TestDeleteComparePresetHandler_RaeumtEigeneSperrdateiAb_ZweiNutzer(t *testing.T) {
	s := store.New(t.TempDir(), "u-a")
	if err := s.WithUser("u-a").SaveComparePreset(comparePresetPutBodyStruct("cp1", "u-a")); err != nil {
		t.Fatal(err)
	}
	jsonB, lockB := dlcSeedB(t, s, "cp1", func() {
		if err := s.WithUser("u-b").SaveComparePreset(comparePresetPutBodyStruct("cp1", "u-b")); err != nil {
			t.Fatal(err)
		}
	})

	w := p2158Do(DeleteComparePresetHandler(s), "DELETE", "/api/compare/presets/{id}", "/api/compare/presets/cp1", "", "u-a")
	if w.Code != 204 {
		t.Fatalf("DELETE: %d (%s)", w.Code, w.Body.String())
	}
	dirA := s.WithUser("u-a").BriefingsDir()
	for _, n := range []string{"cp1.json", "cp1.json.lock"} {
		if dlcExists(filepath.Join(dirA, n)) {
			t.Errorf("%s von A muss nach dem Loeschen weg sein", n)
		}
	}
	dlcAssertBUnchanged(t, s, "cp1", jsonB, lockB)
}

// Kein erfolgreiches Loeschen (404) => die vom Handler angelegte Sperrdatei
// bleibt; nur nach erfolgreichem Delete wird aufgeraeumt.
func TestDeleteComparePresetHandler_404LaesstSperrdateiStehen(t *testing.T) {
	s := store.New(t.TempDir(), "u-a")
	w := p2158Do(DeleteComparePresetHandler(s), "DELETE", "/api/compare/presets/{id}", "/api/compare/presets/unbekannt", "", "u-a")
	if w.Code != 404 {
		t.Fatalf("DELETE: %d (%s)", w.Code, w.Body.String())
	}
	if !dlcExists(filepath.Join(s.WithUser("u-a").BriefingsDir(), "unbekannt.json.lock")) {
		t.Error("Sperrdatei darf ohne erfolgreiches Loeschen nicht entfernt werden")
	}
}

// AC-8 (zweiter Teil): ein Ortsvergleich-Preset ueber den TRIP-Loeschpfad
// angefragt -> Datei UND Sperrdatei bleiben bestehen.
func TestDeleteTripHandler_VergleichBleibtSamtSperrdatei(t *testing.T) {
	s := store.New(t.TempDir(), "u-a")
	if err := s.WithUser("u-a").SaveComparePreset(comparePresetPutBodyStruct("cp1", "u-a")); err != nil {
		t.Fatal(err)
	}
	w := p2158Do(DeleteTripHandler(s), "DELETE", "/api/trips/{id}", "/api/trips/cp1", "", "u-a")
	if w.Code != 204 {
		t.Fatalf("DELETE: %d (%s)", w.Code, w.Body.String())
	}
	dirA := s.WithUser("u-a").BriefingsDir()
	for _, n := range []string{"cp1.json", "cp1.json.lock"} {
		if !dlcExists(filepath.Join(dirA, n)) {
			t.Errorf("%s darf ueber den Trip-Pfad nicht entfernt werden", n)
		}
	}
}
