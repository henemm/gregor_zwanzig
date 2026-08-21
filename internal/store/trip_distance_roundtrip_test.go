package store

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Issue #2036 (AC-6, Go-Seite) — die gemessene Wegstrecke muss den
// Editor-Schreibweg ueberleben.
//
// Die Spec nennt als Risiko #1: "Go-Modell vergessen => der erste
// Editor-Save wischt alle gemessenen Kilometer wieder weg" (Praezedenzfall
// `suggestion_reason`: existiert in Python, fehlt in Go, wird stumm
// verworfen). Genau dieses Szenario war bis zur Adversary-Runde 1 in
// KEINEM Test abgedeckt -- `internal/` referenzierte das Feld nirgends,
// also blieben `go build` und `go test` auch nach dem Entfernen des Feldes
// gruen (Mutation M12).
//
// Vorbild: trip_arrival_roundtrip_test.go (#296/#303, gleiche Bauart).

func TestTripRoundTrip_PreservesDistanceFromStart(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "briefings")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	// Vom Python-Kern geschriebener Stand: Etappenstart bei 0.0 km (gueltige
	// Messung!), danach steigende Wegstrecke.
	measuredJSON := `{
		"id": "measured-trip",
		"name": "Measured Trip",
		"stages": [
			{
				"id": "S1",
				"name": "Tag 1",
				"date": "2026-08-23",
				"waypoints": [
					{"id":"W1","name":"Start","lat":46.60,"lon":12.90,"elevation_m":500,
					 "distance_from_start_km":0.0},
					{"id":"W2","name":"Pass","lat":46.62,"lon":12.92,"elevation_m":800,
					 "distance_from_start_km":4.0},
					{"id":"W3","name":"Ziel","lat":46.65,"lon":12.95,"elevation_m":700,
					 "distance_from_start_km":11.0}
				]
			}
		]
	}`
	path := filepath.Join(tripDir, "measured-trip.json")
	if err := os.WriteFile(path, []byte(measuredJSON), 0644); err != nil {
		t.Fatalf("write measured json: %v", err)
	}

	loaded, err := s.LoadTrip("measured-trip")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip: %v", err)
	}

	// Der Editor-Save: laden, speichern, neu laden.
	if err := s.SaveTrip(loaded); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	reloaded, err := s.LoadTrip("measured-trip")
	if err != nil || reloaded == nil {
		t.Fatalf("re-LoadTrip: %v", err)
	}

	wps := reloaded.Stages[0].Waypoints
	if len(wps) != 3 {
		t.Fatalf("expected 3 waypoints, got %d", len(wps))
	}

	// W1: 0.0 km ist eine GUELTIGE Messung (Etappenstart) und darf nicht
	// als "leer" wegoptimiert werden -- deshalb *float64 statt float64 mit
	// omitempty. Genau diese Verwechslung fangen wir hier ab.
	if wps[0].DistanceFromStartKm == nil {
		t.Fatalf("W1: distance_from_start_km=0.0 ging verloren (nil nach Roundtrip)")
	}
	if *wps[0].DistanceFromStartKm != 0.0 {
		t.Fatalf("W1: distance_from_start_km verfaelscht: %v", *wps[0].DistanceFromStartKm)
	}
	if wps[1].DistanceFromStartKm == nil || *wps[1].DistanceFromStartKm != 4.0 {
		t.Fatalf("W2: distance_from_start_km ging verloren: %v", wps[1].DistanceFromStartKm)
	}
	if wps[2].DistanceFromStartKm == nil || *wps[2].DistanceFromStartKm != 11.0 {
		t.Fatalf("W3: distance_from_start_km ging verloren: %v", wps[2].DistanceFromStartKm)
	}

	// Auch auf der Platte, nicht nur im Speicher: der 0.0-Wert muss im JSON
	// stehen (sonst liest ihn der Python-Kern beim naechsten Lauf als
	// "nicht gemessen" und die Etappe faellt auf Segment-N zurueck).
	written, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read written: %v", err)
	}
	if !strings.Contains(string(written), `"distance_from_start_km"`) {
		t.Fatalf("distance_from_start_km fehlt in der geschriebenen Datei: %s", string(written))
	}
}

// Ein Bestandstrip OHNE gemessene Wegstrecke darf durch den Roundtrip
// keine bekommen -- `nil` heisst "nicht gemessen" und muss `nil` bleiben
// (Gegenstueck zu AC-14 auf der Python-Seite: None != 0.0).
func TestTripRoundTrip_LegacyTripStaysUnmeasured(t *testing.T) {
	tmpDir := t.TempDir()
	s := New(tmpDir, "test")

	tripDir := filepath.Join(tmpDir, "users", "test", "briefings")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	legacyJSON := `{
		"id": "legacy-distance",
		"name": "Legacy Trip",
		"stages": [
			{
				"id": "S1",
				"name": "Tag 1",
				"date": "2026-08-23",
				"waypoints": [
					{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500},
					{"id":"W2","name":"Ziel","lat":47.036,"lon":11.0,"elevation_m":800}
				]
			}
		]
	}`
	path := filepath.Join(tripDir, "legacy-distance.json")
	if err := os.WriteFile(path, []byte(legacyJSON), 0644); err != nil {
		t.Fatalf("write legacy json: %v", err)
	}

	loaded, err := s.LoadTrip("legacy-distance")
	if err != nil || loaded == nil {
		t.Fatalf("LoadTrip: %v", err)
	}
	if err := s.SaveTrip(loaded); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
	reloaded, err := s.LoadTrip("legacy-distance")
	if err != nil || reloaded == nil {
		t.Fatalf("re-LoadTrip: %v", err)
	}

	for i, wp := range reloaded.Stages[0].Waypoints {
		if wp.DistanceFromStartKm != nil {
			t.Fatalf("Wegpunkt %d hat unerwuenscht eine Distanz erhalten: %v",
				i, *wp.DistanceFromStartKm)
		}
	}

	written, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read written: %v", err)
	}
	if strings.Contains(string(written), `"distance_from_start_km"`) {
		t.Fatalf("unvermessener Trip traegt nach dem Roundtrip ein "+
			"distance_from_start_km: %s", string(written))
	}
}
