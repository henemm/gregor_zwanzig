package store

// Issue #2422 S3, AC-20: die flachen Trip-Felder morning_enabled/evening_enabled
// folgen EINER Regel, die in der geteilten Fallzeilen-Tabelle
// tests/fixtures/report_config_slot_faelle.json steht (Python, Go und TS lesen
// dieselbe Datei). Keine Mocks — echter Filesystem-Roundtrip via t.TempDir().
//
// Die Tabelle wird relativ zu DIESER Testdatei aufgeloest (runtime.Caller), nie
// ueber den festen Hauptrepo-Pfad (sonst falsches Gruen aus dem Worktree).

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

type slotFall struct {
	Name         string                 `json:"name"`
	ReportConfig map[string]interface{} `json:"report_config"`
	FlatMorning  *bool                  `json:"flat_morning"`
	FlatEvening  *bool                  `json:"flat_evening"`
}

func ladeSlotFaelle(t *testing.T) []slotFall {
	t.Helper()
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller lieferte keinen Pfad")
	}
	path := filepath.Join(filepath.Dir(thisFile), "..", "..", "tests", "fixtures", "report_config_slot_faelle.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("geteilte Fallzeilen-Tabelle nicht lesbar (%s): %v", path, err)
	}
	var tabelle struct {
		Faelle []slotFall `json:"faelle"`
	}
	if err := json.Unmarshal(raw, &tabelle); err != nil {
		t.Fatalf("Tabelle nicht parsebar: %v", err)
	}
	if len(tabelle.Faelle) < 12 {
		t.Fatalf("Tabelle hat %d Faelle, erwartet >= 12 (Datei gekuerzt?)", len(tabelle.Faelle))
	}
	return tabelle.Faelle
}

func boolPtrText(p *bool) string {
	if p == nil {
		return "nil"
	}
	if *p {
		return "true"
	}
	return "false"
}

func gleicheBoolPtr(a, b *bool) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

// gegenteil liefert einen Wert, der GARANTIERT vom Sollwert abweicht — so
// beweist der Test, dass die Ableitung ihn ueberschreibt (kein Stale).
func gegenteil(soll *bool) *bool {
	v := true
	if soll != nil && *soll {
		v = false
	}
	return &v
}

// AC-20, Weg 1 (SaveTrip): in-memory abgeleitete Felder folgen der Tabelle, auch
// wenn vorher ein veralteter, falscher Wert im Trip stand.
func TestDeriveFlatFields_SlotFaelle(t *testing.T) {
	for _, f := range ladeSlotFaelle(t) {
		f := f
		t.Run("save/"+f.Name, func(t *testing.T) {
			s := New(t.TempDir(), "slot-nutzer-ac20")
			trip := model.Trip{
				ID:             "slot-" + f.Name,
				Name:           "Slot " + f.Name,
				ReportConfig:   f.ReportConfig,
				MorningEnabled: gegenteil(f.FlatMorning), // veralteter Wert
				EveningEnabled: gegenteil(f.FlatEvening),
			}
			if err := s.SaveTrip(&trip); err != nil {
				t.Fatalf("SaveTrip: %v", err)
			}
			if !gleicheBoolPtr(trip.MorningEnabled, f.FlatMorning) {
				t.Errorf("MorningEnabled nach SaveTrip = %s, Tabelle sagt %s (report_config=%v)",
					boolPtrText(trip.MorningEnabled), boolPtrText(f.FlatMorning), f.ReportConfig)
			}
			if !gleicheBoolPtr(trip.EveningEnabled, f.FlatEvening) {
				t.Errorf("EveningEnabled nach SaveTrip = %s, Tabelle sagt %s (report_config=%v)",
					boolPtrText(trip.EveningEnabled), boolPtrText(f.FlatEvening), f.ReportConfig)
			}
		})
	}
}

// AC-20, Weg 2 (LoadTrip aus der Datei im Persistenzformat): der Block liegt als
// JSON auf Platte (so schreiben ihn Editor und Python; ein leerer Block `{}` bleibt
// dabei erhalten). Ein flaches Feld, das dort veraltet steht, wird beim Laden
// ueberschrieben.
func TestDeriveFlatFields_SlotFaelle_LoadVonPlatte(t *testing.T) {
	for _, f := range ladeSlotFaelle(t) {
		f := f
		t.Run("load/"+f.Name, func(t *testing.T) {
			s := New(t.TempDir(), "slot-nutzer-ac20")
			datei := map[string]interface{}{
				"id":     "slot-" + f.Name,
				"name":   "Slot " + f.Name,
				"stages": []interface{}{},
				// Veralteter flacher Wert auf Platte — muss ueberschrieben werden.
				"morning_enabled": *gegenteil(f.FlatMorning),
				"evening_enabled": *gegenteil(f.FlatEvening),
			}
			if f.ReportConfig != nil {
				datei["report_config"] = f.ReportConfig
			}
			raw, err := json.Marshal(datei)
			if err != nil {
				t.Fatal(err)
			}
			dir := s.BriefingsDir()
			if err := os.MkdirAll(dir, 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(dir, "slot-"+f.Name+".json"), raw, 0o644); err != nil {
				t.Fatal(err)
			}

			loaded, err := s.LoadTrip("slot-" + f.Name)
			if err != nil || loaded == nil {
				t.Fatalf("LoadTrip: trip=%v err=%v", loaded, err)
			}
			if !gleicheBoolPtr(loaded.MorningEnabled, f.FlatMorning) {
				t.Errorf("MorningEnabled nach Load = %s, Tabelle sagt %s (report_config=%v)",
					boolPtrText(loaded.MorningEnabled), boolPtrText(f.FlatMorning), f.ReportConfig)
			}
			if !gleicheBoolPtr(loaded.EveningEnabled, f.FlatEvening) {
				t.Errorf("EveningEnabled nach Load = %s, Tabelle sagt %s (report_config=%v)",
					boolPtrText(loaded.EveningEnabled), boolPtrText(f.FlatEvening), f.ReportConfig)
			}
		})
	}
}
