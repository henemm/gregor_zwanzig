package model

import (
	"encoding/json"
	"strings"
	"testing"
)

// TDD RED — Tests für Epic #136 Master-Spec Datenmodell-Patches.
// Erwartet: FAIL bis Trip.Shortcode und Trip.Activity in trip.go ergänzt sind.

func TestTrip_ShortcodeRoundtrip(t *testing.T) {
	in := Trip{ID: "t1", Name: "GR20 Test", Shortcode: "GR20"}
	b, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if !strings.Contains(string(b), `"shortcode":"GR20"`) {
		t.Fatalf("marshal sollte shortcode-Feld enthalten, war: %s", string(b))
	}
	var out Trip
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if out.Shortcode != "GR20" {
		t.Fatalf("expected Shortcode=GR20, got %q", out.Shortcode)
	}
}

func TestTrip_ShortcodeOmitEmpty(t *testing.T) {
	in := Trip{ID: "t1", Name: "ohne Kürzel"}
	b, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if strings.Contains(string(b), `"shortcode"`) {
		t.Fatalf("leere Shortcode darf NICHT serialisiert werden, war: %s", string(b))
	}
}

func TestTrip_ActivityRoundtrip(t *testing.T) {
	cases := []string{"trekking", "skitour", "hochtour", "klettersteig", "mtb"}
	for _, val := range cases {
		t.Run(val, func(t *testing.T) {
			in := Trip{ID: "t1", Name: "Trip", Activity: val}
			b, err := json.Marshal(in)
			if err != nil {
				t.Fatalf("marshal: %v", err)
			}
			expected := `"activity":"` + val + `"`
			if !strings.Contains(string(b), expected) {
				t.Fatalf("expected %q in JSON, got %s", expected, string(b))
			}
			var out Trip
			if err := json.Unmarshal(b, &out); err != nil {
				t.Fatalf("unmarshal: %v", err)
			}
			if out.Activity != val {
				t.Fatalf("expected Activity=%s, got %q", val, out.Activity)
			}
		})
	}
}

func TestTrip_ActivityOmitEmpty(t *testing.T) {
	in := Trip{ID: "t1", Name: "ohne Activity"}
	b, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if strings.Contains(string(b), `"activity"`) {
		t.Fatalf("leere Activity darf NICHT serialisiert werden, war: %s", string(b))
	}
}

// Backwards-Compat: Bestand ohne neue Felder muss weiterhin laden.
func TestTrip_LegacyJSON_NoNewFields(t *testing.T) {
	legacy := `{"id":"gr221","name":"Mallorca","stages":[]}`
	var out Trip
	if err := json.Unmarshal([]byte(legacy), &out); err != nil {
		t.Fatalf("legacy JSON sollte laden, fehler: %v", err)
	}
	if out.Shortcode != "" {
		t.Fatalf("expected leer Shortcode, got %q", out.Shortcode)
	}
	if out.Activity != "" {
		t.Fatalf("expected leer Activity, got %q", out.Activity)
	}
}
