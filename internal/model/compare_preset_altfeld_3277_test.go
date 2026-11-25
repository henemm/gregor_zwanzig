package model

// Issue #3277 AC-6 (docs/specs/modules/feat_3277_altfelder_entfernen.md):
// `outlook_enabled` ist Altfeld (ADR-0124 Nr. 6, ersetzt durch
// display_config.placements.outlook_reports). Das ComparePreset-Struct traegt
// kein typisiertes Feld mehr dafuer: ein Preset-JSON mit `outlook_enabled`
// laedt ohne Fehler, und der Schluessel wird nicht als eigenes Feld
// zurueckgeschrieben. Die Tabelle in display_config bleibt erhalten.

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"
)

func TestComparePreset3277_KeinFeldOutlookEnabled(t *testing.T) {
	typ := reflect.TypeOf(ComparePreset{})
	for i := 0; i < typ.NumField(); i++ {
		f := typ.Field(i)
		name := strings.Split(f.Tag.Get("json"), ",")[0]
		if name == "outlook_enabled" || f.Name == "OutlookEnabled" {
			t.Fatalf("ComparePreset traegt noch das Altfeld %s (json %q)", f.Name, name)
		}
	}
}

func TestComparePreset3277_RoundtripOhneOutlookEnabled(t *testing.T) {
	roh := []byte(`{"id":"cp-3277","name":"V","user_id":"nutzer-a3277","location_ids":["a"],` +
		`"schedule":"daily","profil":"ALLGEMEIN","hour_from":9,"hour_to":16,"forecast_hours":48,` +
		`"empfaenger":["x@example.invalid"],"created_at":"2026-07-01T00:00:00Z","corridors":[],` +
		`"outlook_enabled":false,` +
		`"display_config":{"placements":{"version":1,"rows":[],"outlook_reports":["morning"]}}}`)
	var p ComparePreset
	if err := json.Unmarshal(roh, &p); err != nil {
		t.Fatalf("Preset mit outlook_enabled laedt nicht: %v", err)
	}
	aus, err := json.Marshal(p)
	if err != nil {
		t.Fatalf("Preset schreibt nicht: %v", err)
	}
	var zurueck map[string]interface{}
	if err := json.Unmarshal(aus, &zurueck); err != nil {
		t.Fatal(err)
	}
	if _, da := zurueck["outlook_enabled"]; da {
		t.Fatalf("outlook_enabled wird als typisiertes Feld zurueckgeschrieben: %s", aus)
	}
	dc, _ := zurueck["display_config"].(map[string]interface{})
	pl, _ := dc["placements"].(map[string]interface{})
	if pl == nil || !reflect.DeepEqual(pl["outlook_reports"], []interface{}{"morning"}) {
		t.Fatalf("Tabelle ging verloren: %s", aus)
	}
}
