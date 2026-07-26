package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// Issue #1395 Scheibe 1: Inhalts-Fingerabdruck der ROHDATEI (nicht des geladenen
// Objekts). Echte Dateisystem-Operationen, kein Mock.

// seedHealableTrip legt eine Trip-Rohdatei mit einer Versandzeit an, die der
// Lese-Pfad in-memory heilt (07:30:00 -> 07:00:00, healTripSlotTimes).
func seedHealableTrip(t *testing.T, s *Store, id string) {
	t.Helper()
	if err := os.MkdirAll(s.BriefingsDir(), 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	data, err := json.MarshalIndent(map[string]interface{}{
		"id": id, "name": "Heilbar", "kind": "route",
		"report_config": map[string]interface{}{"morning_time": "07:30:00"},
	}, "", "  ")
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(filepath.Join(s.BriefingsDir(), id+".json"), data, 0644); err != nil {
		t.Fatalf("seed: %v", err)
	}
}

func fingerprintOrFail(t *testing.T, s *Store, id string) string {
	t.Helper()
	fp, err := s.BriefingFingerprint(id)
	if err != nil {
		t.Fatalf("BriefingFingerprint(%q): %v", id, err)
	}
	return fp
}

// Der Fingerabdruck folgt den Bytes: gleiche Datei -> gleicher Wert,
// geaenderte Datei -> anderer Wert.
func TestBriefingFingerprint_FollowsFileBytes(t *testing.T) {
	s := New(t.TempDir(), "fpuser")
	trip := model.Trip{ID: "t1", Name: "Alpha"}
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	first := fingerprintOrFail(t, s, "t1")
	if first == "" {
		t.Fatal("erwarte nicht-leeren Fingerabdruck fuer eine existierende Datei")
	}
	if again := fingerprintOrFail(t, s, "t1"); again != first {
		t.Errorf("unveraenderte Datei muss denselben Fingerabdruck liefern: %q != %q", first, again)
	}

	trip.Name = "Beta"
	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip 2: %v", err)
	}
	if changed := fingerprintOrFail(t, s, "t1"); changed == first {
		t.Errorf("geaenderte Datei muss einen anderen Fingerabdruck liefern, blieb %q", changed)
	}
}

// In-Memory-Heilung beim Laden (healTripSlotTimes, SyncAlertRules) schreibt
// NICHT zurueck -- der Fingerabdruck der Datei bleibt davon unberuehrt.
func TestBriefingFingerprint_UnaffectedByInMemoryHealing(t *testing.T) {
	s := New(t.TempDir(), "healuser")
	seedHealableTrip(t, s, "t1")
	before := fingerprintOrFail(t, s, "t1")

	loaded, err := s.LoadTrip("t1")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip: %v / %v", loaded, err)
	}
	if got := loaded.ReportConfig["morning_time"]; got != "07:00:00" {
		t.Fatalf("erwarte in-memory geheilte Zeit 07:00:00, bekam %v", got)
	}

	if after := fingerprintOrFail(t, s, "t1"); after != before {
		t.Errorf("Lese-Heilung darf den Datei-Fingerabdruck nicht aendern: %q -> %q", before, after)
	}
}

// Bekannte Eigenschaft fuer S2/S3: SaveTrip schreibt die Datei auch dann neu,
// wenn der Aufrufer fachlich nichts geaendert hat -- Load heilt in-memory,
// Save persistiert die geheilte Fassung. Ein Fingerabdruck aus einer GET-
// Antwort ist also nach einem Leerlauf-PUT veraltet.
func TestBriefingFingerprint_SaveAfterHealingLoadRewritesFile(t *testing.T) {
	s := New(t.TempDir(), "rewriteuser")
	seedHealableTrip(t, s, "t1")
	before := fingerprintOrFail(t, s, "t1")

	loaded, err := s.LoadTrip("t1")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip: %v / %v", loaded, err)
	}
	if err := s.SaveTrip(loaded); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}

	after := fingerprintOrFail(t, s, "t1")
	if after == before {
		t.Fatal("SaveTrip ist jetzt byte-stabil -- dokumentierte Eigenschaft hat sich geaendert, S2/S3 neu bewerten")
	}
	// Zweiter Leerlauf-Zyklus muss stabil sein, sonst driftet die Datei endlos.
	loaded2, err := s.LoadTrip("t1")
	if err != nil || loaded2 == nil {
		t.Fatalf("LoadTrip 2: %v / %v", loaded2, err)
	}
	if err := s.SaveTrip(loaded2); err != nil {
		t.Fatalf("SaveTrip 2: %v", err)
	}
	if third := fingerprintOrFail(t, s, "t1"); third != after {
		t.Errorf("Leerlauf-Save muss ab dem zweiten Zyklus byte-stabil sein: %q -> %q", after, third)
	}
}

// Vergleichs-Presets liegen in derselben Datei-Ebene -- gleiche Funktion.
func TestBriefingFingerprint_WorksForComparePreset(t *testing.T) {
	s := New(t.TempDir(), "cmpuser")
	p := model.ComparePreset{ID: "c1", Name: "Orte", Schedule: "daily"}
	if err := s.SaveComparePreset(p); err != nil {
		t.Fatalf("SaveComparePreset: %v", err)
	}
	first := fingerprintOrFail(t, s, "c1")
	if first == "" {
		t.Fatal("erwarte nicht-leeren Fingerabdruck fuer eine Vergleichs-Datei")
	}

	p.Name = "Orte 2"
	if err := s.SaveComparePreset(p); err != nil {
		t.Fatalf("SaveComparePreset 2: %v", err)
	}
	if changed := fingerprintOrFail(t, s, "c1"); changed == first {
		t.Errorf("geaenderte Vergleichs-Datei muss anderen Fingerabdruck liefern, blieb %q", changed)
	}
}

// Fehlende Datei ist kein Fehler, sondern der Zustand "es gibt noch keinen
// Stand" -> leerer Fingerabdruck.
func TestBriefingFingerprint_MissingFileYieldsEmptyWithoutError(t *testing.T) {
	s := New(t.TempDir(), "leeruser")
	fp, err := s.BriefingFingerprint("gibtsnicht")
	if err != nil {
		t.Fatalf("fehlende Datei darf keinen Fehler liefern, bekam: %v", err)
	}
	if fp != "" {
		t.Errorf("erwarte leeren Fingerabdruck fuer fehlende Datei, bekam %q", fp)
	}
}
