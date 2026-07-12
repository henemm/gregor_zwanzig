package handler

import "testing"

// TDD — Issue #1231, Slice 3: PUT /api/trips/{id} muss `corridors` annehmen
// und additiv (kein Replace) neben AlertRules persistieren — sonst kann der
// CorridorEditor (route) Wertebereiche nicht speichern (AC-10).

func TestUpdateTripHandlerPersistsCorridors(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "corridor-trip", "Korridor-Trip")

	body := `{"id":"corridor-trip","name":"Korridor-Trip","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}],` +
		`"corridors":[{"metric":"wind_gust","range":[null,70],"notify":true,"mark":false}]}`

	if code := putUpdate(t, s, "corridor-trip", body); code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}

	got := loadTripOrFail(t, s, "corridor-trip")
	if len(got.Corridors) != 1 {
		t.Fatalf("expected 1 corridor, got %d", len(got.Corridors))
	}
	c := got.Corridors[0]
	if c.Metric != "wind_gust" || !c.Notify || c.Mark {
		t.Errorf("unexpected corridor: %+v", c)
	}
	if c.Range[0] != nil || c.Range[1] == nil || *c.Range[1] != 70 {
		t.Errorf("unexpected range: %+v", c.Range)
	}
}

func TestUpdateTripHandlerPreservesCorridorsOnMinimalPut(t *testing.T) {
	s := newTestStore(t)
	seedTrip(t, s, "corridor-preserve", "Korridor-Trip")
	seedBody := `{"id":"corridor-preserve","name":"Korridor-Trip","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}],` +
		`"corridors":[{"metric":"snow_line","range":[1500,null],"notify":true,"mark":false}]}`
	if code := putUpdate(t, s, "corridor-preserve", seedBody); code != 200 {
		t.Fatalf("seed PUT: expected 200, got %d", code)
	}

	// Zweiter PUT ohne "corridors" im Body — RMW-Kontrakt (analog AlertRules)
	// darf bestehende Korridore nicht loeschen.
	minimal := minimalBody("corridor-preserve", "Renamed")
	if code := putUpdate(t, s, "corridor-preserve", minimal); code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}

	got := loadTripOrFail(t, s, "corridor-preserve")
	if len(got.Corridors) != 1 || got.Corridors[0].Metric != "snow_line" {
		t.Fatalf("corridors was dropped/replaced by minimal PUT (RMW-Verletzung), got %+v", got.Corridors)
	}
}
