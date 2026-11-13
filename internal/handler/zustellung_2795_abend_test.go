package handler

// Issue #2795 Fix-Runde 1, Finding F004: die Rasterpruefung (AC-8) gilt auch
// fuer das Abendbriefing. Ein PUT mit evening_time ausserhalb 00/15/30/45 wird
// fuer Trip UND Orts-Briefing mit 400 abgelehnt, die Datei bleibt unveraendert;
// eine rasterkonforme Abendzeit (18:45) wird gespeichert.
// Echter Store (t.TempDir), echte Router-Strecke, Nutzer aus dem Auth-Kontext.

import (
	"net/http"
	"os"
	"testing"
)

func TestUpdate_2795_AbendzeitAusserhalbRasterWird400(t *testing.T) {
	for _, eingabe := range []string{"18:50", "18:50:00", "19:07"} {
		t.Run(eingabe, func(t *testing.T) {
			s := newTestStore(t)
			tripPfad := seedTripFor2795(t, s, "usera", "trip-2795-abend")
			presetPfad := seedPresetFor2795(t, s, "usera", "cp-2795-abend")
			tripVorher, _ := os.ReadFile(tripPfad)
			presetVorher, _ := os.ReadFile(presetPfad)
			r := briefingVergleichEtagRouter(s)

			w := doReq(r, http.MethodPut, "/api/trips/trip-2795-abend",
				`{"report_config":{"evening_time":"`+eingabe+`"}}`, "", "usera")
			if w.Code != http.StatusBadRequest {
				t.Errorf("F004: Trip-PUT evening_time %s erwartet 400, got %d: %s", eingabe, w.Code, w.Body.String())
			}
			w = doReq(r, http.MethodPut, "/api/compare/presets/cp-2795-abend",
				`{"evening_time":"`+eingabe+`"}`, "", "usera")
			if w.Code != http.StatusBadRequest {
				t.Errorf("F004: Preset-PUT evening_time %s erwartet 400, got %d: %s", eingabe, w.Code, w.Body.String())
			}
			tripNachher, _ := os.ReadFile(tripPfad)
			presetNachher, _ := os.ReadFile(presetPfad)
			if string(tripVorher) != string(tripNachher) {
				t.Errorf("F004: Trip-Datei nach abgelehntem PUT veraendert: %s", tripNachher)
			}
			if string(presetVorher) != string(presetNachher) {
				t.Errorf("F004: Preset-Datei nach abgelehntem PUT veraendert: %s", presetNachher)
			}
		})
	}
}

func TestUpdate_2795_AbendzeitImRasterWirdGespeichert(t *testing.T) {
	s := newTestStore(t)
	tripPfad := seedTripFor2795(t, s, "usera", "trip-2795-abend-ok")
	presetPfad := seedPresetFor2795(t, s, "usera", "cp-2795-abend-ok")
	r := briefingVergleichEtagRouter(s)

	w := doReq(r, http.MethodPut, "/api/trips/trip-2795-abend-ok",
		`{"report_config":{"evening_time":"18:45"}}`, "", "usera")
	if w.Code != http.StatusOK {
		t.Fatalf("F004: Trip-PUT 18:45 erwartet 200, got %d: %s", w.Code, w.Body.String())
	}
	rc, _ := readJSON2795(t, tripPfad)["report_config"].(map[string]interface{})
	if c := clockH2795(rc["evening_time"]); c != "18:45" {
		t.Errorf("F004: Trip-Abendzeit gespeichert als %q, erwartet 18:45", c)
	}
	w = doReq(r, http.MethodPut, "/api/compare/presets/cp-2795-abend-ok",
		`{"evening_time":"18:45"}`, "", "usera")
	if w.Code != http.StatusOK {
		t.Fatalf("F004: Preset-PUT 18:45 erwartet 200, got %d: %s", w.Code, w.Body.String())
	}
	if c := clockH2795(readJSON2795(t, presetPfad)["evening_time"]); c != "18:45" {
		t.Errorf("F004: Preset-Abendzeit gespeichert als %q, erwartet 18:45", c)
	}
}
