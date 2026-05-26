package store

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TDD RED — Issue #296-BE AC-4 (Go-Seite).
// Erwartet: FAIL bis das additive Feld `arrival_calculated` (omitempty) im
// Waypoint-Modell existiert. Solange das Feld fehlt, bleibt zwar das Laden
// fehlerfrei — der Test prüft aber zusätzlich, dass nach Roundtrip KEIN
// `arrival_calculated` ungewollt erscheint UND alle Bestandsfelder erhalten
// bleiben. Sobald das Modell-Feld eingeführt ist, schützt der Test gegen
// Datenverlust.
//
// AC-4: bestehende Trip-JSON OHNE arrival_calculated → LoadTrip → SaveTrip →
// LoadTrip; alle bestehenden Wegpunkt-Felder unverändert, kein Fehler.

func TestTripRoundTrip_PreservesFieldsWithoutArrival(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	// Bestands-JSON OHNE arrival_calculated (Legacy).
	legacyJSON := `{
		"id": "legacy-arrival",
		"name": "Legacy Trip",
		"stages": [
			{
				"id": "S1",
				"name": "Tag 1",
				"date": "2026-05-23",
				"waypoints": [
					{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500,"suggested":true},
					{"id":"W2","name":"Ziel","lat":47.036,"lon":11.0,"elevation_m":800}
				]
			}
		]
	}`
	path := filepath.Join(tripDir, "legacy-arrival.json")
	if err := os.WriteFile(path, []byte(legacyJSON), 0644); err != nil {
		t.Fatalf("write legacy json: %v", err)
	}

	loaded, err := s.LoadTrip("legacy-arrival")
	if err != nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected trip, got nil")
	}

	// Roundtrip: speichern und neu laden.
	if err := s.SaveTrip(*loaded); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	reloaded, err := s.LoadTrip("legacy-arrival")
	if err != nil {
		t.Fatalf("re-LoadTrip: %v", err)
	}
	if reloaded == nil {
		t.Fatal("expected reloaded trip, got nil")
	}

	if len(reloaded.Stages) != 1 {
		t.Fatalf("expected 1 stage, got %d", len(reloaded.Stages))
	}
	wps := reloaded.Stages[0].Waypoints
	if len(wps) != 2 {
		t.Fatalf("expected 2 waypoints, got %d", len(wps))
	}

	// Bestandsfelder unverändert.
	if wps[0].ID != "W1" || wps[0].Name != "Start" {
		t.Fatalf("wp[0] id/name verändert: %+v", wps[0])
	}
	if wps[0].Lat != 47.0 || wps[0].Lon != 11.0 || wps[0].ElevationM != 500 {
		t.Fatalf("wp[0] lat/lon/elevation verändert: %+v", wps[0])
	}
	if !wps[0].Suggested {
		t.Fatalf("wp[0] suggested ging verloren: %+v", wps[0])
	}
	if wps[1].ID != "W2" || wps[1].ElevationM != 800 {
		t.Fatalf("wp[1] verändert: %+v", wps[1])
	}

	// Legacy-Trip hatte kein arrival_calculated → darf nach Roundtrip
	// (ohne Berechnung) nicht im File auftauchen (omitempty).
	written, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read written: %v", err)
	}
	if strings.Contains(string(written), `"arrival_calculated"`) {
		t.Fatalf("Legacy-Roundtrip darf kein arrival_calculated erzeugen, war: %s", string(written))
	}

	// Persistierter arrival_calculated muss beim Laden erhalten bleiben (AC-4):
	// Wegpunkt mit gesetztem Feld → nach LoadTrip muss ArrivalCalculated != nil.
	persistedJSON := `{
		"id": "persisted-arrival",
		"name": "Persisted Trip",
		"stages": [
			{
				"id": "S1",
				"name": "Tag 1",
				"date": "2026-05-23",
				"waypoints": [
					{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500,"arrival_calculated":"08:00"}
				]
			}
		]
	}`
	p2 := filepath.Join(tripDir, "persisted-arrival.json")
	if err := os.WriteFile(p2, []byte(persistedJSON), 0644); err != nil {
		t.Fatalf("write persisted json: %v", err)
	}
	loaded2, err := s.LoadTrip("persisted-arrival")
	if err != nil {
		t.Fatalf("LoadTrip persisted: %v", err)
	}
	wp := loaded2.Stages[0].Waypoints[0]
	if wp.ArrivalCalculated == nil || *wp.ArrivalCalculated != "08:00" {
		t.Fatalf("persistierter arrival_calculated ging verloren: %v", wp.ArrivalCalculated)
	}
}

// TestTripRoundTrip_WithConfirmationFields — Issue #303 AC-3.
// Ein Trip-JSON mit allen vier neuen Feldern gesetzt durchläuft
// LoadTrip → SaveTrip → LoadTrip ohne Feldverlust. confirmed ist *bool —
// false UND true müssen den Roundtrip überleben.
func TestTripRoundTrip_WithConfirmationFields(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "trips")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	confirmedJSON := `{
		"id": "conf-trip",
		"name": "Confirmed Trip",
		"stages": [
			{
				"id": "S1",
				"name": "Tag 1",
				"date": "2026-05-26",
				"waypoints": [
					{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500,
					 "origin":"algorithmic","confirmed":true,
					 "suggestion_reason":"detected_peak","arrival_override":"11:45"},
					{"id":"W2","name":"Tal","lat":47.05,"lon":11.05,"elevation_m":800,
					 "origin":"algorithmic","confirmed":false,
					 "suggestion_reason":"detected_valley"}
				]
			}
		]
	}`
	path := filepath.Join(tripDir, "conf-trip.json")
	if err := os.WriteFile(path, []byte(confirmedJSON), 0644); err != nil {
		t.Fatalf("write conf json: %v", err)
	}

	loaded, err := s.LoadTrip("conf-trip")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if err := s.SaveTrip(*loaded); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	reloaded, err := s.LoadTrip("conf-trip")
	if err != nil || reloaded == nil {
		t.Fatalf("re-LoadTrip: %v", err)
	}

	wps := reloaded.Stages[0].Waypoints
	if len(wps) != 2 {
		t.Fatalf("expected 2 waypoints, got %d", len(wps))
	}

	// W1 — alle vier Felder gesetzt, confirmed=true.
	if wps[0].Origin != "algorithmic" {
		t.Fatalf("W1 origin ging verloren: %q", wps[0].Origin)
	}
	if wps[0].Confirmed == nil || !*wps[0].Confirmed {
		t.Fatalf("W1 confirmed=true ging verloren: %v", wps[0].Confirmed)
	}
	if wps[0].SuggestionReason == nil || *wps[0].SuggestionReason != "detected_peak" {
		t.Fatalf("W1 suggestion_reason ging verloren: %v", wps[0].SuggestionReason)
	}
	if wps[0].ArrivalOverride == nil || *wps[0].ArrivalOverride != "11:45" {
		t.Fatalf("W1 arrival_override ging verloren: %v", wps[0].ArrivalOverride)
	}

	// W2 — confirmed=false MUSS erhalten bleiben (*bool, nicht bool+omitempty).
	if wps[1].Confirmed == nil || *wps[1].Confirmed {
		t.Fatalf("W2 confirmed=false ging durch Roundtrip verloren: %v", wps[1].Confirmed)
	}
	if wps[1].SuggestionReason == nil || *wps[1].SuggestionReason != "detected_valley" {
		t.Fatalf("W2 suggestion_reason ging verloren: %v", wps[1].SuggestionReason)
	}
}
