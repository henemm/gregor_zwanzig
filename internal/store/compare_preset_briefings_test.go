package store

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// Issue #1250 Scheibe 7b (feat-1250-s7b-vergleich-cutover): Go-Seite des
// vergleich-Cutovers compare_presets.json -> briefings/<id>.json
// (kind="vergleich"). Spiegelt store_trip_briefings_test.go (S7a route), nur
// der kind-Filter ist invertiert.
//
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md, AC-31/32/33/38.
//
// Gegen den ALTEN Code (LoadComparePresets las compare_presets.json als Array,
// DeleteComparePresetHandler filterte nur ein Array) waeren alle Faelle hier
// rot: die briefings/-Fixtures wuerden ignoriert, und ohne echtes os.Remove
// wuerde das geloeschte Preset beim Reload wiederauferstehen.

// helper: legt ein briefings/<id>.json mit dem gegebenen kind an.
func writeBriefingPresetFixture(t *testing.T, tmpDir, userID, id, kind, name string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "users", userID, "briefings")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir briefings: %v", err)
	}
	raw := `{"id":"` + id + `","name":"` + name + `","kind":"` + kind + `","schedule":"daily","empfaenger":["x@example.com"]}`
	if err := os.WriteFile(filepath.Join(dir, id+".json"), []byte(raw), 0644); err != nil {
		t.Fatalf("write fixture %s: %v", id, err)
	}
}

// AC-31/34: LoadComparePresets globt briefings/, filtert INVERS auf
// kind=="vergleich" — kind=route bleibt aussen vor, die Legacy-
// compare_presets.json wird nicht mehr gelesen.
func TestLoadComparePresets_ReadsBriefingsDir_InverseKindFilter(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-cp-a")

	writeBriefingPresetFixture(t, tmpDir, "cutover-cp-a", "vergleich-1", "vergleich", "Vergleich Eins")
	writeBriefingPresetFixture(t, tmpDir, "cutover-cp-a", "route-1", "route", "Route Eins")

	// Legacy-compare_presets.json mit einem GANZ anderen Preset — muss ignoriert
	// werden (Vor-Cutover-Pfad ist tot).
	userDir := filepath.Join(tmpDir, "users", "cutover-cp-a")
	legacy := `[{"id":"legacy-only","name":"Aus Alt-Datei","kind":"vergleich","schedule":"daily","empfaenger":["x@example.com"]}]`
	if err := os.WriteFile(filepath.Join(userDir, "compare_presets.json"), []byte(legacy), 0644); err != nil {
		t.Fatalf("write legacy: %v", err)
	}

	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(presets) != 1 {
		t.Fatalf("LoadComparePresets muss briefings/ lesen und NUR kind=\"vergleich\" liefern (AC-31), got %d: %+v", len(presets), presets)
	}
	if presets[0].ID != "vergleich-1" {
		t.Fatalf("expected vergleich-1 (aus briefings/), got %q — route-Eintrag oder Legacy-Datei faelschlich geladen", presets[0].ID)
	}
}

// AC-31 (Einzel-Load): LoadComparePreset liest briefings/<id>.json nur fuer
// kind=vergleich; fuer eine route-Datei liefert es nil (kein Preset).
func TestLoadComparePreset_KindGuard(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-cp-b")

	writeBriefingPresetFixture(t, tmpDir, "cutover-cp-b", "verg", "vergleich", "Vergleich")
	writeBriefingPresetFixture(t, tmpDir, "cutover-cp-b", "trip", "route", "Trip")

	p, err := s.LoadComparePreset("verg")
	if err != nil {
		t.Fatalf("LoadComparePreset(verg): %v", err)
	}
	if p == nil || p.ID != "verg" {
		t.Fatalf("expected vergleich-Preset, got %+v", p)
	}

	route, err := s.LoadComparePreset("trip")
	if err != nil {
		t.Fatalf("LoadComparePreset(trip): %v", err)
	}
	if route != nil {
		t.Fatalf("LoadComparePreset muss fuer kind=route nil liefern (AC-31), got %+v", route)
	}
}

// AC-32: SaveComparePreset schreibt briefings/<id>.json (kind=vergleich
// erzwungen, damit der invers-kind-Filter es beim Reload nicht verwirft), die
// Legacy-compare_presets.json bleibt byte-unveraendert liegen (Rollback).
func TestSaveComparePreset_WritesBriefingsDir_LeavesLegacyUntouched(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-cp-c")

	userDir := filepath.Join(tmpDir, "users", "cutover-cp-c")
	if err := os.MkdirAll(userDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	legacyPath := filepath.Join(userDir, "compare_presets.json")
	legacyBytes := []byte(`[{"id":"cp-1","name":"Alt-Version"}]`)
	if err := os.WriteFile(legacyPath, legacyBytes, 0644); err != nil {
		t.Fatalf("write legacy: %v", err)
	}

	// Preset OHNE kind speichern -> SaveComparePreset muss kind=vergleich setzen.
	p := model.ComparePreset{ID: "cp-1", Name: "Neu-Gespeichert", Schedule: "daily", Empfaenger: []string{"a@example.com"}}
	if err := s.SaveComparePreset(p); err != nil {
		t.Fatalf("SaveComparePreset: %v", err)
	}

	briefingsPath := filepath.Join(userDir, "briefings", "cp-1.json")
	data, err := os.ReadFile(briefingsPath)
	if err != nil {
		t.Fatalf("SaveComparePreset muss briefings/<id>.json schreiben (AC-32), Datei fehlt: %v", err)
	}
	var saved map[string]interface{}
	if err := json.Unmarshal(data, &saved); err != nil {
		t.Fatalf("unmarshal briefings file: %v", err)
	}
	if saved["name"] != "Neu-Gespeichert" {
		t.Fatalf("briefings-Datei traegt falschen Namen: %v", saved["name"])
	}
	if saved["kind"] != "vergleich" {
		t.Fatalf("SaveComparePreset muss kind=\"vergleich\" erzwingen (sonst verwirft der Load-Filter die Datei), got %v", saved["kind"])
	}

	// Reload sieht das Preset (Beweis, dass kind gesetzt wurde).
	reloaded, err := s.LoadComparePresets()
	if err != nil || len(reloaded) != 1 || reloaded[0].ID != "cp-1" {
		t.Fatalf("Reload muss das frisch gespeicherte Preset liefern, got err=%v presets=%+v", err, reloaded)
	}

	after, err := os.ReadFile(legacyPath)
	if err != nil {
		t.Fatalf("read legacy after save: %v", err)
	}
	if string(after) != string(legacyBytes) {
		t.Fatalf("compare_presets.json muss beim Cutover-Save byte-unveraendert bleiben (Rollback, AC-32)\nbefore: %s\nafter:  %s", legacyBytes, after)
	}
}

// AC-33 (F-A, KRITISCH): DeleteComparePreset entfernt briefings/<id>.json
// tatsaechlich (os.Remove); Reload liefert es nicht zurueck; ein zweites
// Preset desselben Users bleibt erhalten.
func TestDeleteComparePreset_RemovesFile_NoResurrection(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-cp-d")

	writeBriefingPresetFixture(t, tmpDir, "cutover-cp-d", "to-delete", "vergleich", "Wird geloescht")
	writeBriefingPresetFixture(t, tmpDir, "cutover-cp-d", "keep", "vergleich", "Bleibt")

	if err := s.DeleteComparePreset("to-delete"); err != nil {
		t.Fatalf("DeleteComparePreset: %v", err)
	}

	deletedPath := filepath.Join(tmpDir, "users", "cutover-cp-d", "briefings", "to-delete.json")
	if _, err := os.Stat(deletedPath); !os.IsNotExist(err) {
		t.Fatalf("F-A/AC-33: DeleteComparePreset muss briefings/<id>.json ENTFERNEN, Datei existiert noch (stat err=%v)", err)
	}

	presets, err := s.LoadComparePresets()
	if err != nil {
		t.Fatalf("LoadComparePresets: %v", err)
	}
	if len(presets) != 1 || presets[0].ID != "keep" {
		t.Fatalf("F-A/AC-33: nach Delete darf nur das zweite Preset bleiben (kein Wiederauferstehen), got %+v", presets)
	}
}

// AC-33 (Guard): DeleteComparePreset darf eine kind=route-Datei (Trip) NIE
// entfernen, auch wenn deren ID mit der angefragten Preset-ID kollidiert
// (invertierter DeleteTrip-Guard).
func TestDeleteComparePreset_DoesNotRemoveRouteKindFile(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-cp-e")

	writeBriefingPresetFixture(t, tmpDir, "cutover-cp-e", "shared-id", "route", "Trip mit Kollisions-ID")
	routePath := filepath.Join(tmpDir, "users", "cutover-cp-e", "briefings", "shared-id.json")
	before, _ := os.ReadFile(routePath)

	if err := s.DeleteComparePreset("shared-id"); err != nil {
		t.Fatalf("DeleteComparePreset: %v", err)
	}

	after, err := os.ReadFile(routePath)
	if err != nil {
		t.Fatalf("AC-33-Guard: kind=route-Datei wurde faelschlich entfernt: %v", err)
	}
	if string(after) != string(before) {
		t.Fatalf("AC-33-Guard: kind=route-Datei wurde veraendert:\nbefore: %s\nafter:  %s", before, after)
	}
}

// AC-38: Roundtrip Load->Save->Load bewahrt jeden Feldsatz (Corridors,
// LocationIDs, display_config, Slot-Felder) — kein Top-Level-Feldverlust.
func TestSaveComparePreset_RoundtripPreservesFields(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "cutover-cp-f")

	dir := filepath.Join(tmpDir, "users", "cutover-cp-f", "briefings")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	fixture := `{
		"id": "cp-full",
		"name": "Voller Feldsatz",
		"user_id": "cutover-cp-f",
		"kind": "vergleich",
		"location_ids": ["loc-a", "loc-b", "loc-c"],
		"schedule": "manual",
		"profil": "SUMMER_TREKKING",
		"hour_from": 8,
		"hour_to": 17,
		"forecast_hours": 72,
		"empfaenger": ["a@example.com", "b@example.com"],
		"morning_enabled": true,
		"morning_time": "07:30:00",
		"evening_enabled": false,
		"evening_time": "19:00:00",
		"end_date": "2026-12-31",
		"display_config": {"region": "Tirol", "ideal_ranges": {"wind": {"max": 30}}},
		"corridors": [{"metric": "wind_gust", "range": [10, 60], "notify": true, "mark": true}]
	}`
	path := filepath.Join(dir, "cp-full.json")
	if err := os.WriteFile(path, []byte(fixture), 0644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}

	loaded, err := s.LoadComparePreset("cp-full")
	if err != nil || loaded == nil {
		t.Fatalf("LoadComparePreset: err=%v loaded=%v", err, loaded)
	}

	if err := s.SaveComparePreset(*loaded); err != nil {
		t.Fatalf("SaveComparePreset: %v", err)
	}

	rewritten, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read back: %v", err)
	}
	var saved map[string]interface{}
	if err := json.Unmarshal(rewritten, &saved); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if locs, ok := saved["location_ids"].([]interface{}); !ok || len(locs) != 3 {
		t.Fatalf("location_ids verloren beim Roundtrip (AC-38): %v", saved["location_ids"])
	}
	dc, ok := saved["display_config"].(map[string]interface{})
	if !ok || dc["region"] != "Tirol" {
		t.Fatalf("display_config verloren beim Roundtrip (AC-38): %v", saved["display_config"])
	}
	if cors, ok := saved["corridors"].([]interface{}); !ok || len(cors) != 1 {
		t.Fatalf("corridors verloren beim Roundtrip (AC-38): %v", saved["corridors"])
	}
	if saved["end_date"] != "2026-12-31" {
		t.Fatalf("end_date verloren beim Roundtrip (AC-38): %v", saved["end_date"])
	}
	// Issue #1280: Read-Heilung normalisiert morning_time beim Laden auf die
	// volle Stunde (07:30 -> 07:00, in-memory); das Feld selbst bleibt beim
	// Roundtrip erhalten (kein Verlust, AC-38) — nur der Wert ist jetzt korrekt
	// stundengenau statt krumm.
	if saved["morning_time"] != "07:00:00" {
		t.Fatalf("morning_time verloren beim Roundtrip (AC-38): %v", saved["morning_time"])
	}

	// Feld-fuer-Feld ueber Reload: Load2 muss dem Load1 gleichen.
	reloaded, err := s.LoadComparePreset("cp-full")
	if err != nil || reloaded == nil {
		t.Fatalf("second LoadComparePreset: err=%v", err)
	}
	if len(reloaded.LocationIDs) != 3 || len(reloaded.Corridors) != 1 {
		t.Fatalf("AC-38: Feldsatz nach Roundtrip unvollstaendig: locs=%v corridors=%v", reloaded.LocationIDs, reloaded.Corridors)
	}
}
