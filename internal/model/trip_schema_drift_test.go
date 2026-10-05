package model

// Trip-Schema-Drift-Gate, Go-Seite (#2058, Spec trip_schema_drift_gate).
//
// Liest dieselbe voll besetzte Fixture wie tests/test_trip_schema_drift.py,
// schreibt sie ueber model.Trip zurueck und vergleicht die Schluesselmengen
// je Ebene (Trip / Etappe / Wegpunkt) in BEIDE Richtungen. Ein Schluessel,
// den nur ein Modell kennt, geht beim Speichern (Listen werden als Ganzes
// ersetzt) still verloren.
//
// Pfadanker: os.Getwd()-Aufstieg bis go.mod (-trimpath-fest, wie
// internal/mail/recipient_parity_test.go).

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
)

// driftAllowlist — IDENTISCH zur Allowlist in tests/test_trip_schema_drift.py.
// Je Eintrag Seite + Begruendung; keine Pauschal-Ausnahme.
var driftAllowlist = map[string]struct{ side, reason string }{
	"send_premium_sms": {"go_only", "in Go aus report_config.send_premium_sms abgeleitet (store/trip.go)"},
	"trip":             {"python_only", "Python-Legacy-Wrapper in KNOWN_TOP_LEVEL, wird nie geschrieben"},
}

func driftRepoRoot(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("os.Getwd: %v", err)
	}
	for i := 0; i < 6; i++ {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	t.Fatalf("kein go.mod oberhalb von %q gefunden", dir)
	return ""
}

func driftFixture(t *testing.T) []byte {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(driftRepoRoot(t), "tests", "fixtures", "trip_schema_full.json"))
	if err != nil {
		t.Fatalf("Fixture nicht lesbar: %v", err)
	}
	return raw
}

func keysOf(m map[string]interface{}) map[string]bool {
	out := map[string]bool{}
	for k := range m {
		out[k] = true
	}
	return out
}

// driftLevels liefert die Schluesselmengen je Ebene eines Trip-JSON.
func driftLevels(t *testing.T, raw []byte) map[string]map[string]bool {
	t.Helper()
	var trip map[string]interface{}
	if err := json.Unmarshal(raw, &trip); err != nil {
		t.Fatalf("JSON: %v", err)
	}
	stages, _ := trip["stages"].([]interface{})
	if len(stages) == 0 {
		t.Fatalf("keine Etappe im JSON")
	}
	stage := stages[0].(map[string]interface{})
	wps, _ := stage["waypoints"].([]interface{})
	if len(wps) == 0 {
		t.Fatalf("kein Wegpunkt im JSON")
	}
	return map[string]map[string]bool{
		"trip":     keysOf(trip),
		"stage":    keysOf(stage),
		"waypoint": keysOf(wps[0].(map[string]interface{})),
	}
}

func driftBefunde(expected, actual map[string]map[string]bool) []string {
	var out []string
	for level, exp := range expected {
		act := actual[level]
		for k := range exp {
			if !act[k] {
				out = append(out, level+": nur in Fixture (Go verwirft): "+k)
			}
		}
		for k := range act {
			if !exp[k] {
				out = append(out, level+": nur in Go-Ausgabe (nicht in Fixture): "+k)
			}
		}
	}
	sort.Strings(out)
	return out
}

func goRoundtrip(t *testing.T, raw []byte) []byte {
	t.Helper()
	var trip Trip
	if err := json.Unmarshal(raw, &trip); err != nil {
		t.Fatalf("Unmarshal in model.Trip: %v", err)
	}
	out, err := json.Marshal(trip)
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	return out
}

// AC-2 / AC-4: Roundtrip ueber model.Trip — Schluesselmengen aller drei
// Ebenen stimmen mit der Fixture ueberein (inkl. suggestion_reason).
func TestTripSchemaDrift_RoundtripSchluesselmengen(t *testing.T) {
	raw := driftFixture(t)
	befunde := driftBefunde(driftLevels(t, raw), driftLevels(t, goRoundtrip(t, raw)))
	if len(befunde) > 0 {
		t.Fatalf("Schema-Drift Python<->Go:\n  %s", strings.Join(befunde, "\n  "))
	}
}

// AC-4: der Wert von suggestion_reason bleibt beim Go-Save erhalten.
func TestTripSchemaDrift_SuggestionReasonBleibtErhalten(t *testing.T) {
	raw := driftFixture(t)
	var out struct {
		Stages []struct {
			Waypoints []map[string]interface{} `json:"waypoints"`
		} `json:"stages"`
	}
	if err := json.Unmarshal(goRoundtrip(t, raw), &out); err != nil {
		t.Fatalf("Ausgabe nicht lesbar: %v", err)
	}
	got := out.Stages[0].Waypoints[0]["suggestion_reason"]
	if got != "Passhöhe" {
		t.Fatalf("suggestion_reason nach Go-Roundtrip = %v, erwartet \"Passhöhe\"", got)
	}
}

// AC-3 (Richtung Fixture->Go): ein nur im anderen Modell vorhandenes
// Wegpunkt-/Etappen-/Trip-Feld wird mit Ebene und Schluessel gemeldet.
func TestTripSchemaDrift_EinseitigesFeldWirdGemeldet(t *testing.T) {
	for _, level := range []string{"trip", "stage", "waypoint"} {
		var doc map[string]interface{}
		if err := json.Unmarshal(driftFixture(t), &doc); err != nil {
			t.Fatal(err)
		}
		stage := doc["stages"].([]interface{})[0].(map[string]interface{})
		switch level {
		case "trip":
			doc["nur_im_anderen_modell"] = "x"
		case "stage":
			stage["nur_im_anderen_modell"] = "x"
		case "waypoint":
			stage["waypoints"].([]interface{})[0].(map[string]interface{})["nur_im_anderen_modell"] = "x"
		}
		raw, _ := json.Marshal(doc)
		befunde := driftBefunde(driftLevels(t, raw), driftLevels(t, goRoundtrip(t, raw)))
		found := false
		for _, b := range befunde {
			if strings.HasPrefix(b, level+":") && strings.Contains(b, "nur_im_anderen_modell") {
				found = true
			}
		}
		if !found {
			t.Errorf("Ebene %s: einseitiges Feld nicht gemeldet (Befunde: %v)", level, befunde)
		}
	}
}

func jsonTags(typ reflect.Type) map[string]bool {
	out := map[string]bool{}
	for i := 0; i < typ.NumField(); i++ {
		tag := strings.Split(typ.Field(i).Tag.Get("json"), ",")[0]
		if tag != "" && tag != "-" {
			out[tag] = true
		}
	}
	return out
}

// AC-2 (Go-Struct-Seite): jedes Go-Feld steht in der Fixture oder in der
// Allowlist — ein neues, nur in Go angelegtes Feld wird sofort rot, auch
// wenn die Fixture noch nicht mitgewachsen ist.
func TestTripSchemaDrift_JedesGoFeldStehtInFixtureOderAllowlist(t *testing.T) {
	levels := driftLevels(t, driftFixture(t))
	for level, typ := range map[string]reflect.Type{
		"trip": reflect.TypeOf(Trip{}), "stage": reflect.TypeOf(Stage{}), "waypoint": reflect.TypeOf(Waypoint{}),
	} {
		for tag := range jsonTags(typ) {
			if levels[level][tag] {
				continue
			}
			if e, ok := driftAllowlist[tag]; ok && level == "trip" && e.side == "go_only" {
				continue
			}
			t.Errorf("%s: Go-Feld %q fehlt in der Fixture und steht nicht in der Allowlist", level, tag)
		}
	}
}

// AC-5: Allowlist ist exakt — go_only-Eintraege existieren im Go-Modell und
// nicht in der Fixture, python_only-Eintraege existieren NICHT im Go-Modell.
func TestTripSchemaDrift_AllowlistIstExakt(t *testing.T) {
	levels := driftLevels(t, driftFixture(t))
	tags := jsonTags(reflect.TypeOf(Trip{}))
	for key, e := range driftAllowlist {
		if levels["trip"][key] {
			t.Errorf("%s gehoert nicht in die gemeinsame Fixture", key)
		}
		switch e.side {
		case "go_only":
			if !tags[key] {
				t.Errorf("Allowlist-Eintrag %q (go_only) existiert im Go-Modell nicht mehr: %s", key, e.reason)
			}
		case "python_only":
			if tags[key] {
				t.Errorf("Allowlist-Eintrag %q (python_only) ist jetzt im Go-Modell modelliert — Eintrag veraltet", key)
			}
		default:
			t.Errorf("Allowlist-Eintrag %q hat unbekannte Seite %q", key, e.side)
		}
	}
	if len(driftAllowlist) != 2 {
		t.Errorf("Allowlist hat %d Eintraege, erwartet genau 2 (send_premium_sms, trip)", len(driftAllowlist))
	}
}
