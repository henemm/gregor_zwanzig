package model

import (
	"encoding/json"
	"strings"
	"testing"
)

// Issue #303 AC-2 — Marshal/Omit-Semantik der vier neuen Waypoint-Felder.
//
// Ersetzt den #296-Test TestWaypointJSON_HasArrivalNotOriginConfirmed: dieser
// behauptete, origin/confirmed dürften NICHT im JSON erscheinen. Nach #303 ist
// das falsch — die Felder sind reguläre, additive omitempty-Felder.

func ptrBool(b bool) *bool { return &b }

// TestWaypointJSON_NewFieldsMarshalAndOmit prüft beide Richtungen:
// gesetzte Felder erscheinen im JSON, Zero-Value-Felder werden ausgelassen.
func TestWaypointJSON_NewFieldsMarshalAndOmit(t *testing.T) {
	// Gesetzte Felder → alle drei Keys im JSON.
	wp := Waypoint{
		ID:         "W1",
		Name:       "Gipfel",
		Lat:        47.0,
		Lon:        11.0,
		ElevationM: 2500,
		Origin:     "algorithmic",
		Confirmed:  ptrBool(true),
	}
	b, err := json.Marshal(wp)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	js := string(b)
	if !strings.Contains(js, `"origin":"algorithmic"`) {
		t.Fatalf("origin fehlt im JSON, war: %s", js)
	}
	if !strings.Contains(js, `"confirmed":true`) {
		t.Fatalf("confirmed fehlt im JSON, war: %s", js)
	}

	// confirmed=false MUSS serialisierbar sein (*bool, nicht bool+omitempty).
	wpFalse := Waypoint{ID: "W2", Name: "Tal", Lat: 47.0, Lon: 11.0, ElevationM: 800,
		Confirmed: ptrBool(false)}
	bf, err := json.Marshal(wpFalse)
	if err != nil {
		t.Fatalf("marshal false: %v", err)
	}
	if !strings.Contains(string(bf), `"confirmed":false`) {
		t.Fatalf("confirmed:false ging verloren (bool+omitempty-Falle), war: %s", string(bf))
	}

	// Zero-Value → keiner der vier neuen Keys.
	zero := Waypoint{ID: "W3", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500}
	bz, err := json.Marshal(zero)
	if err != nil {
		t.Fatalf("marshal zero: %v", err)
	}
	jz := string(bz)
	for _, key := range []string{`"origin"`, `"confirmed"`, `"arrival_override"`} {
		if strings.Contains(jz, key) {
			t.Fatalf("Zero-Value darf %s nicht enthalten, war: %s", key, jz)
		}
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
