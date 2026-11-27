package store

// TDD RED — Issue #3092 (ADR-0101): SaveTrip / SaveComparePreset bewahren dem
// Go-Modell unbekannte Top-Level-Felder der vorhandenen Datei.
// Spec: docs/specs/modules/fix_3092_unbekannte_felder_erhalten.md — AC-4, AC-6, AC-8, AC-9.
//
// Mock-frei: echter Store auf t.TempDir(), Dateiinhalt wird roh eingelesen.

import (
	"bytes"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func uf3092Store(t *testing.T, user string) *Store {
	t.Helper()
	return New(t.TempDir(), "test").WithUser(user)
}

func uf3092Pfad(s *Store, id string) string {
	return filepath.Join(s.BriefingsDir(), id+".json")
}

func uf3092Schreiben(t *testing.T, s *Store, id string, m map[string]interface{}) {
	t.Helper()
	if err := os.MkdirAll(s.BriefingsDir(), 0o755); err != nil {
		t.Fatal(err)
	}
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(uf3092Pfad(s, id), data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func uf3092Roh(t *testing.T, s *Store, id string) map[string]json.RawMessage {
	t.Helper()
	data, err := os.ReadFile(uf3092Pfad(s, id))
	if err != nil {
		t.Fatalf("Datei lesen: %v", err)
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("Datei ist kein JSON-Objekt: %v", err)
	}
	return m
}

func uf3092Trip(id string, extra map[string]interface{}) map[string]interface{} {
	m := map[string]interface{}{
		"id": id, "name": "Tour", "kind": "route",
		"stages": []interface{}{map[string]interface{}{
			"id": "S1", "name": "Tag 1", "date": "2026-08-01",
			"waypoints": []interface{}{map[string]interface{}{
				"id": "W1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 800,
			}},
		}},
	}
	for k, v := range extra {
		m[k] = v
	}
	return m
}

func uf3092Preset(id string, extra map[string]interface{}) map[string]interface{} {
	m := map[string]interface{}{
		"id": id, "name": "Vergleich", "kind": "vergleich",
		"location_ids": []string{"loc-a", "loc-b"},
		"schedule":     "daily", "profil": "ALLGEMEIN",
		"created_at":   "2026-09-01T00:00:00Z",
	}
	for k, v := range extra {
		m[k] = v
	}
	return m
}

var uf3092Fremd = map[string]interface{}{"x": 1, "liste": []interface{}{"a", "b"}}

func uf3092FremdfeldGleich(t *testing.T, raw map[string]json.RawMessage) {
	t.Helper()
	got, ok := raw["zukunftsfeld"]
	if !ok {
		t.Fatalf("zukunftsfeld fehlt nach dem Speichern (Schluessel: %v)", schluessel(raw))
	}
	var a interface{}
	_ = json.Unmarshal(got, &a)
	am, _ := json.Marshal(a)
	wm, _ := json.Marshal(uf3092Fremd)
	if !bytes.Equal(am, wm) {
		t.Errorf("zukunftsfeld veraendert: %s, erwartet %s", am, wm)
	}
}

func schluessel(m map[string]json.RawMessage) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

// AC-4 (Trip): geleertes paused_at verschwindet, unbekanntes Feld bleibt.
func TestUnbekannteFelder3092_AC4_TripGeleertesFeldNichtWiederbelebt(t *testing.T) {
	s := uf3092Store(t, "alice")
	uf3092Schreiben(t, s, "t1", uf3092Trip("t1", map[string]interface{}{
		"paused_at": "2026-09-01T10:00:00Z", "zukunftsfeld": uf3092Fremd,
	}))
	trip, err := s.LoadTrip("t1")
	if err != nil || trip == nil {
		t.Fatalf("LoadTrip: %v %v", trip, err)
	}
	if trip.PausedAt == nil {
		t.Fatalf("Vorbedingung: paused_at muss geladen sein")
	}
	trip.PausedAt = nil
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	raw := uf3092Roh(t, s, "t1")
	if _, ok := raw["paused_at"]; ok {
		t.Errorf("paused_at aus der Altdatei wiederbelebt: %s", raw["paused_at"])
	}
	uf3092FremdfeldGleich(t, raw)
}

// AC-4 (Ortsvergleich): geleertes archived_at verschwindet, unbekanntes Feld bleibt.
func TestUnbekannteFelder3092_AC4_PresetGeleertesFeldNichtWiederbelebt(t *testing.T) {
	s := uf3092Store(t, "alice")
	uf3092Schreiben(t, s, "p1", uf3092Preset("p1", map[string]interface{}{
		"archived_at": "2026-09-01T10:00:00Z", "zukunftsfeld": uf3092Fremd,
	}))
	p, err := s.LoadComparePreset("p1")
	if err != nil || p == nil {
		t.Fatalf("LoadComparePreset: %v %v", p, err)
	}
	if p.ArchivedAt == nil {
		t.Fatalf("Vorbedingung: archived_at muss geladen sein")
	}
	p.ArchivedAt = nil
	if err := s.SaveComparePreset(*p); err != nil {
		t.Fatalf("SaveComparePreset: %v", err)
	}
	raw := uf3092Roh(t, s, "p1")
	if _, ok := raw["archived_at"]; ok {
		t.Errorf("archived_at aus der Altdatei wiederbelebt: %s", raw["archived_at"])
	}
	uf3092FremdfeldGleich(t, raw)
}

// AC-6: fehlende, leere oder kaputte Altdatei -> Speichern gelingt, Modellstand.
func TestUnbekannteFelder3092_AC6_FehlendeOderKaputteAltdatei(t *testing.T) {
	faelle := map[string]*string{"fehlt": nil, "leer": strPtr(""), "muell": strPtr("kein json {")}
	for name, inhalt := range faelle {
		name, inhalt := name, inhalt
		t.Run("trip_"+name, func(t *testing.T) {
			s := uf3092Store(t, "alice")
			if inhalt != nil {
				_ = os.MkdirAll(s.BriefingsDir(), 0o755)
				_ = os.WriteFile(uf3092Pfad(s, "t1"), []byte(*inhalt), 0o644)
			}
			uf3092Schreiben(t, s, "vorlage", uf3092Trip("vorlage", nil))
			trip, err := s.LoadTrip("vorlage")
			if err != nil || trip == nil {
				t.Fatalf("Vorlage laden: %v", err)
			}
			trip.ID = "t1"
			if err := s.SaveTrip(trip); err != nil {
				t.Fatalf("SaveTrip: %v", err)
			}
			raw := uf3092Roh(t, s, "t1")
			want, _ := json.Marshal(trip)
			var wantMap map[string]json.RawMessage
			_ = json.Unmarshal(want, &wantMap)
			if len(raw) != len(wantMap) {
				t.Errorf("Schluessel weichen vom Modellstand ab: %v vs %v", schluessel(raw), schluessel(wantMap))
			}
		})
		t.Run("preset_"+name, func(t *testing.T) {
			s := uf3092Store(t, "alice")
			if inhalt != nil {
				_ = os.MkdirAll(s.BriefingsDir(), 0o755)
				_ = os.WriteFile(uf3092Pfad(s, "p1"), []byte(*inhalt), 0o644)
			}
			uf3092Schreiben(t, s, "vorlage", uf3092Preset("vorlage", nil))
			p, err := s.LoadComparePreset("vorlage")
			if err != nil || p == nil {
				t.Fatalf("Vorlage laden: %v", err)
			}
			p.ID = "p1"
			if err := s.SaveComparePreset(*p); err != nil {
				t.Fatalf("SaveComparePreset: %v", err)
			}
			got, err := s.LoadComparePreset("p1")
			if err != nil || got == nil || got.Name != "Vergleich" {
				t.Errorf("Modellstand nicht lesbar: %+v %v", got, err)
			}
		})
	}
}

func strPtr(s string) *string { return &s }

// AC-8: Altfeld outlook_enabled (#3277) bleibt bei Go-Save erhalten.
func TestUnbekannteFelder3092_AC8_AltfeldBleibt(t *testing.T) {
	s := uf3092Store(t, "alice")
	uf3092Schreiben(t, s, "t1", uf3092Trip("t1", map[string]interface{}{"outlook_enabled": true}))
	uf3092Schreiben(t, s, "p1", uf3092Preset("p1", map[string]interface{}{"outlook_enabled": true}))

	trip, _ := s.LoadTrip("t1")
	if err := s.SaveTrip(trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	p, _ := s.LoadComparePreset("p1")
	if err := s.SaveComparePreset(*p); err != nil {
		t.Fatalf("SaveComparePreset: %v", err)
	}
	for _, id := range []string{"t1", "p1"} {
		raw := uf3092Roh(t, s, id)
		if string(raw["outlook_enabled"]) != "true" {
			t.Errorf("%s: outlook_enabled nach Go-Save verloren (Schluessel: %v)", id, schluessel(raw))
		}
	}
}

// AC-9: Groessenpruefung laeuft auf dem gemergten Ergebnis; Altdatei unveraendert.
func TestUnbekannteFelder3092_AC9_GroessePrueftGemergtesErgebnis(t *testing.T) {
	gross := strings.Repeat("x", MaxEntityFileBytes)
	s := uf3092Store(t, "alice")
	uf3092Schreiben(t, s, "t1", uf3092Trip("t1", map[string]interface{}{"zukunftsfeld": gross}))
	uf3092Schreiben(t, s, "p1", uf3092Preset("p1", map[string]interface{}{"zukunftsfeld": gross}))
	vorT, _ := os.ReadFile(uf3092Pfad(s, "t1"))
	vorP, _ := os.ReadFile(uf3092Pfad(s, "p1"))

	trip, _ := s.LoadTrip("t1")
	if trip == nil {
		t.Fatal("LoadTrip lieferte nil")
	}
	if err := s.SaveTrip(trip); !errors.Is(err, ErrEntityTooLarge) {
		t.Errorf("SaveTrip: erwartet ErrEntityTooLarge, bekommen %v", err)
	}
	p, _ := s.LoadComparePreset("p1")
	if p == nil {
		t.Fatal("LoadComparePreset lieferte nil")
	}
	if err := s.SaveComparePreset(*p); !errors.Is(err, ErrEntityTooLarge) {
		t.Errorf("SaveComparePreset: erwartet ErrEntityTooLarge, bekommen %v", err)
	}
	nachT, _ := os.ReadFile(uf3092Pfad(s, "t1"))
	nachP, _ := os.ReadFile(uf3092Pfad(s, "p1"))
	if !bytes.Equal(vorT, nachT) {
		t.Errorf("Trip-Altdatei wurde trotz Ablehnung veraendert")
	}
	if !bytes.Equal(vorP, nachP) {
		t.Errorf("Preset-Altdatei wurde trotz Ablehnung veraendert")
	}
}
