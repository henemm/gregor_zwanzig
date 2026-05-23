package model

import (
	"encoding/json"
	"strings"
	"testing"
)

// TDD RED — Issue #296-BE AC-6.
// Erwartet: FAIL (Compile-Fehler) bis Waypoint.ArrivalCalculated existiert.
//
// AC-6: genau ein neues Feld `arrival_calculated`; KEINE Felder `origin`
// oder `confirmed`.

// TestWaypointJSON_HasArrivalNotOriginConfirmed prüft, dass eine Waypoint-Struct
// nach JSON-Marshalling das Feld `arrival_calculated` tragen kann und KEINE
// Felder `origin`/`confirmed` erzeugt (AC-6).
func TestWaypointJSON_HasArrivalNotOriginConfirmed(t *testing.T) {
	arr := "10:15"
	wp := Waypoint{
		ID:                "W1",
		Name:              "Gipfel",
		Lat:               47.0,
		Lon:               11.0,
		ElevationM:        2500,
		ArrivalCalculated: &arr,
	}

	b, err := json.Marshal(wp)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	js := string(b)

	if !strings.Contains(js, `"arrival_calculated":"10:15"`) {
		t.Fatalf("erwartet arrival_calculated:10:15 im JSON, war: %s", js)
	}
	if strings.Contains(js, `"origin"`) {
		t.Fatalf("Feld origin darf NICHT existieren, war: %s", js)
	}
	if strings.Contains(js, `"confirmed"`) {
		t.Fatalf("Feld confirmed darf NICHT existieren, war: %s", js)
	}
}

// TestWaypointJSON_ArrivalOmitEmpty prüft die omitempty-Semantik:
// ohne ArrivalCalculated darf das Feld NICHT serialisiert werden (additiv,
// backward-compatible).
func TestWaypointJSON_ArrivalOmitEmpty(t *testing.T) {
	wp := Waypoint{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500}

	b, err := json.Marshal(wp)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if strings.Contains(string(b), `"arrival_calculated"`) {
		t.Fatalf("leeres arrival_calculated darf NICHT serialisiert werden, war: %s", string(b))
	}
}
