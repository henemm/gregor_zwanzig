package store

// Issue #1981 — Alarm-Abwahl wirkt auch bei Alt-Vokabular in metric_alert_levels.
//
// Der Go-Ladepfad (LoadComparePresets / LoadComparePreset, beide ueber
// normalizeLoadedComparePreset) muss Alt-Schluessel im Summary-Vokabular
// (temp_max_c, gust_max_kmh, ...) in die Alarm-Namen uebersetzen. Der Editor
// liest ueber genau diesen Pfad — so zeigt er denselben Wert, den die
// Python-Auswertung anwendet (AC-2, PO-Entscheid Variante A).
//
// Die Faelle stehen in der gemeinsamen Fixture
// tests/fixtures/metric_alert_levels_alt_vokabular/faelle.json, die auch
// tests/tdd/test_alarm_abwahl_alt_vokabular.py prueft (AC-9, Go <-> Python).
//
// Spec: docs/specs/modules/fix_1981_alarm_abwahl_alt_vokabular.md
// Keine Mocks — echter Filesystem-Roundtrip via t.TempDir().

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"testing"
)

type altVokabularFall struct {
	Name     string                 `json:"name"`
	Eingabe  map[string]interface{} `json:"eingabe"`
	Erwartet map[string]interface{} `json:"erwartet"`
}

// loadAltVokabularFaelle liest die gemeinsame Fixture relativ zu DIESER
// Testdatei (Pfadregel #1409), nie ueber einen festen Hauptrepo-Pfad.
func loadAltVokabularFaelle(t *testing.T) []altVokabularFall {
	t.Helper()
	_, self, _, _ := runtime.Caller(0)
	path := filepath.Join(filepath.Dir(self), "..", "..", "tests", "fixtures",
		"metric_alert_levels_alt_vokabular", "faelle.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("Fixture lesen: %v", err)
	}
	var doc struct {
		Faelle []altVokabularFall `json:"faelle"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("Fixture parsen: %v", err)
	}
	if len(doc.Faelle) == 0 {
		t.Fatal("Fixture enthaelt keine Faelle")
	}
	return doc.Faelle
}

// writeComparePresetWithLevels legt eine Vergleichsdatei mit den gegebenen
// metric_alert_levels unter briefings/<id>.json ab.
func writeComparePresetWithLevels(t *testing.T, tmpDir, id string, levels map[string]interface{}) {
	t.Helper()
	elem := map[string]interface{}{
		"id": id, "name": id, "user_id": "user1", "kind": "vergleich",
		"location_ids": []string{"loc-a"}, "schedule": "daily",
		"hour_from": 6, "hour_to": 9, "empfaenger": []string{"test@example.com"},
		"created_at": "2026-01-01T00:00:00Z",
		"display_config": map[string]interface{}{"metric_alert_levels": levels},
	}
	arr, err := json.Marshal([]interface{}{elem})
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	writeComparePresetsJSON(t, tmpDir, "user1", string(arr))
}

func levelsOf(t *testing.T, dc map[string]interface{}) map[string]interface{} {
	t.Helper()
	if dc == nil {
		t.Fatal("DisplayConfig ist nil")
	}
	levels, ok := dc["metric_alert_levels"].(map[string]interface{})
	if !ok {
		t.Fatalf("metric_alert_levels nicht lesbar: %#v", dc["metric_alert_levels"])
	}
	return levels
}

// loadLevelsBothPaths laedt ueber BEIDE Go-Lesepfade (Liste und Einzelabruf
// des Editors) und verlangt, dass sie uebereinstimmen.
func loadLevelsBothPaths(t *testing.T, levels map[string]interface{}) map[string]interface{} {
	t.Helper()
	tmpDir := t.TempDir()
	s := New(tmpDir, "user1")
	writeComparePresetWithLevels(t, tmpDir, "cp-1981", levels)

	presets, err := s.LoadComparePresets()
	if err != nil || len(presets) != 1 {
		t.Fatalf("LoadComparePresets: %v (n=%d)", err, len(presets))
	}
	single, err := s.LoadComparePreset("cp-1981")
	if err != nil || single == nil {
		t.Fatalf("LoadComparePreset: %v", err)
	}
	ausListe := levelsOf(t, presets[0].DisplayConfig)
	ausEinzel := levelsOf(t, single.DisplayConfig)
	if !reflect.DeepEqual(ausListe, ausEinzel) {
		t.Fatalf("Liste %v != Einzelabruf %v", ausListe, ausEinzel)
	}
	return ausEinzel
}

// AC-2 (Go): gespeicherte Alt-Stufe steht nach dem Laden unter dem Alarm-Namen.
func TestComparePresetLoad_AltSchluesselGiltUnterAlarmNamen(t *testing.T) {
	got := loadLevelsBothPaths(t, map[string]interface{}{"gust_max_kmh": "off"})
	want := map[string]interface{}{"wind_gust": "off"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("Erwartet %v, erhalten %v", want, got)
	}
}

// AC-3 (Go): Neu-Schluessel gewinnt, Alt-Schluessel wird entfernt.
func TestComparePresetLoad_NeuSchluesselGewinnt(t *testing.T) {
	got := loadLevelsBothPaths(t, map[string]interface{}{
		"temp_max_c": "off", "temperature_max": "standard",
	})
	want := map[string]interface{}{"temperature_max": "standard"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("Erwartet %v, erhalten %v", want, got)
	}
}

// AC-4 + AC-9 (Go): jeder Fall der gemeinsamen Fixture liefert exakt
// 'erwartet' — fremde Schluessel bleiben mit Wert erhalten.
func TestComparePresetLoad_FaelleAusGemeinsamerFixture(t *testing.T) {
	for _, fall := range loadAltVokabularFaelle(t) {
		t.Run(fall.Name, func(t *testing.T) {
			got := loadLevelsBothPaths(t, fall.Eingabe)
			if !reflect.DeepEqual(got, fall.Erwartet) {
				t.Fatalf("Erwartet %v, erhalten %v", fall.Erwartet, got)
			}
		})
	}
}

// AC-5 (Go): zweiter Lauf auf dem Ergebnis des ersten ist ein No-Op.
func TestComparePresetLoad_ZweiterLaufIstNoOp(t *testing.T) {
	for _, fall := range loadAltVokabularFaelle(t) {
		t.Run(fall.Name, func(t *testing.T) {
			erster := loadLevelsBothPaths(t, fall.Eingabe)
			zweiter := loadLevelsBothPaths(t, erster)
			if !reflect.DeepEqual(erster, fall.Erwartet) || !reflect.DeepEqual(zweiter, erster) {
				t.Fatalf("1. Lauf %v, 2. Lauf %v, erwartet %v", erster, zweiter, fall.Erwartet)
			}
		})
	}
}

// Sanity: die Fixture-Namen sind eindeutig (Subtests sonst verdeckt).
func TestAltVokabularFixture_NamenEindeutig(t *testing.T) {
	gesehen := map[string]bool{}
	for _, fall := range loadAltVokabularFaelle(t) {
		if gesehen[fall.Name] {
			t.Fatal(fmt.Sprintf("doppelter Fall-Name %q", fall.Name))
		}
		gesehen[fall.Name] = true
	}
}
