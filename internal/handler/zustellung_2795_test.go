package handler

// Issue #2795 S3b Teil 1a — Reiter „Zustellung“, Backend-Schreibpfade.
// SPEC: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.1 (Schreiben),
// §4.2 (send_email fuer Orte); AC-4, AC-7, AC-8, AC-23 (Serverteil), AC-34.
//
// Co-located Handler-Tests gegen echten Store (t.TempDir, keine Mocks), echte
// Router-Strecke (briefingVergleichEtagRouter), Nutzer aus dem Auth-Kontext
// (addUserToContext ueber doReq) — nie "default".
//
// Format-Toleranz: ob der Server "06:45" oder "06:45:00" speichert/liefert,
// ist nicht Teil der Zusicherung; geprueft wird die Uhrzeit (clockH2795).
//
// RED heute:
//   * Trip-/Preset-PUT kappen 06:45 auf 06:00 (compare_preset.go:59,
//     trip.go:405), 06:50 wird still zu 06:00 statt 400.
//   * ComparePreset kennt kein send_email: der typisierte Unmarshal in
//     applyComparePresetPatch verwirft den Schluessel.
//
// Ausfuehrung: go test ./internal/handler -run 2795 -v

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func clockH2795(v interface{}) string {
	s, ok := v.(string)
	if !ok {
		return "<kein String>"
	}
	if len(s) == 5 {
		return s
	}
	if len(s) == 8 && s[5:] == ":00" {
		return s[:5]
	}
	return s
}

func seedTripFor2795(t *testing.T, s *store.Store, uid, id string) string {
	t.Helper()
	su := s.WithUser(uid)
	trip := model.Trip{
		ID: id, Name: "Trip " + id,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-08-20",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{
			"enabled":      true,
			"send_email":   true,
			"morning_time": "07:00:00",
			"evening_time": "18:00:00",
		},
		DisplayConfig: map[string]interface{}{
			"ampel": map[string]interface{}{"template": "allgemein"},
		},
	}
	if err := su.SaveTrip(&trip); err != nil {
		t.Fatalf("seed trip %s/%s: %v", uid, id, err)
	}
	return filepath.Join(su.BriefingsDir(), id+".json")
}

func seedPresetFor2795(t *testing.T, s *store.Store, uid, id string) string {
	t.Helper()
	su := s.WithUser(uid)
	p := comparePresetPutBodyStruct(id, uid)
	trueVal := true
	m, e := "07:00:00", "18:00:00"
	p.MorningEnabled, p.MorningTime = &trueVal, &m
	p.EveningEnabled, p.EveningTime = &trueVal, &e
	p.DisplayConfig = map[string]interface{}{
		"ampel": map[string]interface{}{"template": "allgemein"},
	}
	if err := su.SaveComparePreset(p); err != nil {
		t.Fatalf("seed preset %s/%s: %v", uid, id, err)
	}
	return filepath.Join(su.BriefingsDir(), id+".json")
}

func readJSON2795(t *testing.T, path string) map[string]interface{} {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("Datei %s lesen: %v", path, err)
	}
	var m map[string]interface{}
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatalf("Datei %s parsen: %v", path, err)
	}
	return m
}

func tripMorning2795(t *testing.T, path string) interface{} {
	rc, _ := readJSON2795(t, path)["report_config"].(map[string]interface{})
	return rc["morning_time"]
}

// ─────────────────────── AC-4: 06:45 ueberlebt Schreiben + Lesen ───────────

// AC-4 (Trip): PUT report_config.morning_time 06:45 -> Datei, GET-Antwort und
// Flach-Feld zeigen 06:45. Beide Eingabeformate.
func TestUpdateTrip_2795_ViertelstundeBleibtUeberPutUndGet(t *testing.T) {
	for _, eingabe := range []string{"06:45", "06:45:00"} {
		t.Run(eingabe, func(t *testing.T) {
			s := newTestStore(t)
			pfad := seedTripFor2795(t, s, "usera", "trip-2795")
			r := briefingVergleichEtagRouter(s)

			w := doReq(r, http.MethodPut, "/api/trips/trip-2795",
				`{"report_config":{"morning_time":"`+eingabe+`"}}`, "", "usera")
			if w.Code != http.StatusOK {
				t.Fatalf("AC-4: PUT 06:45 erwartet 200, got %d: %s", w.Code, w.Body.String())
			}
			if c := clockH2795(tripMorning2795(t, pfad)); c != "06:45" {
				t.Errorf("AC-4: gespeichert %q, erwartet 06:45 (kein Kappen auf 06:00)", c)
			}
			g := doReq(r, http.MethodGet, "/api/trips/trip-2795", "", "", "usera")
			var got model.Trip
			if err := json.Unmarshal(g.Body.Bytes(), &got); err != nil {
				t.Fatalf("GET parsen: %v (%s)", err, g.Body.String())
			}
			if c := clockH2795(got.ReportConfig["morning_time"]); c != "06:45" {
				t.Errorf("AC-4: GET report_config.morning_time %q, erwartet 06:45", c)
			}
			if got.MorningTime == nil || clockH2795(*got.MorningTime) != "06:45" {
				t.Errorf("AC-4: GET Flach-Feld morning_time %v, erwartet 06:45", got.MorningTime)
			}
			// RMW: Fremdfelder unveraendert.
			rc, _ := readJSON2795(t, pfad)["report_config"].(map[string]interface{})
			if rc["send_email"] != true || rc["enabled"] != true {
				t.Errorf("AC-4/RMW: report_config-Fremdfelder veraendert: %v", rc)
			}
		})
	}
}

// AC-4 (Orte): Preset-PUT morning_time 06:45 -> Datei und GET zeigen 06:45.
func TestUpdateComparePreset_2795_ViertelstundeBleibtUeberPutUndGet(t *testing.T) {
	for _, eingabe := range []string{"06:45", "06:45:00"} {
		t.Run(eingabe, func(t *testing.T) {
			s := newTestStore(t)
			pfad := seedPresetFor2795(t, s, "usera", "cp-2795")
			r := briefingVergleichEtagRouter(s)

			w := doReq(r, http.MethodPut, "/api/compare/presets/cp-2795",
				`{"morning_time":"`+eingabe+`"}`, "", "usera")
			if w.Code != http.StatusOK {
				t.Fatalf("AC-4: Preset-PUT 06:45 erwartet 200, got %d: %s", w.Code, w.Body.String())
			}
			if c := clockH2795(readJSON2795(t, pfad)["morning_time"]); c != "06:45" {
				t.Errorf("AC-4: Preset gespeichert %q, erwartet 06:45", c)
			}
			g := doReq(r, http.MethodGet, "/api/compare/presets/cp-2795", "", "", "usera")
			var got map[string]interface{}
			_ = json.Unmarshal(g.Body.Bytes(), &got)
			if c := clockH2795(got["morning_time"]); c != "06:45" {
				t.Errorf("AC-4: Preset-GET morning_time %q, erwartet 06:45", c)
			}
		})
	}
}

// ─────────────────────── AC-8: Sekunden -> :00, 06:50 -> 400 ───────────────

// AC-8: "06:45:30" wird angenommen und als 06:45 gespeichert (Sekunden werden
// zu :00, die Minute bleibt) — Trip und Preset.
func TestUpdate_2795_SekundenWerdenNullMinuteBleibt(t *testing.T) {
	s := newTestStore(t)
	tripPfad := seedTripFor2795(t, s, "usera", "trip-2795-s")
	presetPfad := seedPresetFor2795(t, s, "usera", "cp-2795-s")
	r := briefingVergleichEtagRouter(s)

	w := doReq(r, http.MethodPut, "/api/trips/trip-2795-s",
		`{"report_config":{"morning_time":"06:45:30"}}`, "", "usera")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-8: Trip-PUT 06:45:30 erwartet 200, got %d: %s", w.Code, w.Body.String())
	}
	if c := clockH2795(tripMorning2795(t, tripPfad)); c != "06:45" {
		t.Errorf("AC-8: Trip 06:45:30 gespeichert als %q, erwartet 06:45 (Sekunden :00)", c)
	}
	w = doReq(r, http.MethodPut, "/api/compare/presets/cp-2795-s",
		`{"morning_time":"06:45:30"}`, "", "usera")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-8: Preset-PUT 06:45:30 erwartet 200, got %d: %s", w.Code, w.Body.String())
	}
	if c := clockH2795(readJSON2795(t, presetPfad)["morning_time"]); c != "06:45" {
		t.Errorf("AC-8: Preset 06:45:30 gespeichert als %q, erwartet 06:45", c)
	}
}

// AC-8: eine Minute ausserhalb des Rasters (06:50) wird mit 400 abgelehnt —
// keine stille Verfaelschung zu 06:45 oder 06:00, Datei bleibt unveraendert.
func TestUpdate_2795_UnzulaessigeMinuteWird400(t *testing.T) {
	for _, eingabe := range []string{"06:50", "06:50:00", "07:01"} {
		t.Run(eingabe, func(t *testing.T) {
			s := newTestStore(t)
			tripPfad := seedTripFor2795(t, s, "usera", "trip-2795-bad")
			presetPfad := seedPresetFor2795(t, s, "usera", "cp-2795-bad")
			tripVorher, _ := os.ReadFile(tripPfad)
			presetVorher, _ := os.ReadFile(presetPfad)
			r := briefingVergleichEtagRouter(s)

			w := doReq(r, http.MethodPut, "/api/trips/trip-2795-bad",
				`{"report_config":{"morning_time":"`+eingabe+`"}}`, "", "usera")
			if w.Code != http.StatusBadRequest {
				t.Errorf("AC-8: Trip-PUT %s erwartet 400, got %d: %s", eingabe, w.Code, w.Body.String())
			}
			w = doReq(r, http.MethodPut, "/api/compare/presets/cp-2795-bad",
				`{"morning_time":"`+eingabe+`"}`, "", "usera")
			if w.Code != http.StatusBadRequest {
				t.Errorf("AC-8: Preset-PUT %s erwartet 400, got %d: %s", eingabe, w.Code, w.Body.String())
			}
			tripNachher, _ := os.ReadFile(tripPfad)
			presetNachher, _ := os.ReadFile(presetPfad)
			if string(tripVorher) != string(tripNachher) {
				t.Errorf("AC-8: Trip-Datei nach abgelehntem PUT veraendert: %s", tripNachher)
			}
			if string(presetVorher) != string(presetNachher) {
				t.Errorf("AC-8: Preset-Datei nach abgelehntem PUT veraendert: %s", presetNachher)
			}
		})
	}
}

// AC-7 (Regressionsschutz, heute gruen): 07:00/18:00 bleiben ueber PUT
// unveraendert — Trip und Preset.
func TestUpdate_2795_VolleStundeBleibtUnveraendert(t *testing.T) {
	s := newTestStore(t)
	tripPfad := seedTripFor2795(t, s, "usera", "trip-2795-h")
	presetPfad := seedPresetFor2795(t, s, "usera", "cp-2795-h")
	r := briefingVergleichEtagRouter(s)

	w := doReq(r, http.MethodPut, "/api/trips/trip-2795-h",
		`{"report_config":{"morning_time":"07:00","evening_time":"18:00:00"}}`, "", "usera")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-7: Trip-PUT expected 200, got %d: %s", w.Code, w.Body.String())
	}
	rc, _ := readJSON2795(t, tripPfad)["report_config"].(map[string]interface{})
	if clockH2795(rc["morning_time"]) != "07:00" || clockH2795(rc["evening_time"]) != "18:00" {
		t.Errorf("AC-7: Trip-Zeiten veraendert: morning=%v evening=%v", rc["morning_time"], rc["evening_time"])
	}
	w = doReq(r, http.MethodPut, "/api/compare/presets/cp-2795-h",
		`{"morning_time":"07:00:00","evening_time":"18:00"}`, "", "usera")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-7: Preset-PUT expected 200, got %d: %s", w.Code, w.Body.String())
	}
	pm := readJSON2795(t, presetPfad)
	if clockH2795(pm["morning_time"]) != "07:00" || clockH2795(pm["evening_time"]) != "18:00" {
		t.Errorf("AC-7: Preset-Zeiten veraendert: morning=%v evening=%v", pm["morning_time"], pm["evening_time"])
	}
}

// ─────────────────────── AC-23 (Server): send_email im Preset ──────────────

// AC-23: send_email=false ueber Preset-PUT steht danach im Preset und kommt
// im GET zurueck; Einschalten schreibt true; andere Felder bleiben unveraendert.
// RED heute: das Go-Modell kennt send_email nicht, der Schluessel geht verloren.
func TestUpdateComparePreset_2795_SendEmailRoundtrip(t *testing.T) {
	s := newTestStore(t)
	pfad := seedPresetFor2795(t, s, "usera", "cp-2795-mail")
	vorher := readJSON2795(t, pfad)
	r := briefingVergleichEtagRouter(s)

	for _, wert := range []bool{false, true, false} {
		body := `{"send_email":false}`
		if wert {
			body = `{"send_email":true}`
		}
		w := doReq(r, http.MethodPut, "/api/compare/presets/cp-2795-mail", body, "", "usera")
		if w.Code != http.StatusOK {
			t.Fatalf("AC-23: PUT %s erwartet 200, got %d: %s", body, w.Code, w.Body.String())
		}
		gespeichert := readJSON2795(t, pfad)
		if v, ok := gespeichert["send_email"]; !ok || v != wert {
			t.Errorf("AC-23: nach PUT %s steht send_email=%v (vorhanden=%v) im Preset, erwartet %v",
				body, v, ok, wert)
		}
		g := doReq(r, http.MethodGet, "/api/compare/presets/cp-2795-mail", "", "", "usera")
		var got map[string]interface{}
		_ = json.Unmarshal(g.Body.Bytes(), &got)
		if v, ok := got["send_email"]; !ok || v != wert {
			t.Errorf("AC-23: GET nach PUT %s liefert send_email=%v (vorhanden=%v), erwartet %v",
				body, v, ok, wert)
		}
		// Andere Felder unveraendert (Read-Modify-Write).
		for _, k := range []string{"name", "location_ids", "display_config", "morning_time", "evening_time", "profil"} {
			a, _ := json.Marshal(vorher[k])
			b, _ := json.Marshal(gespeichert[k])
			if string(a) != string(b) {
				t.Errorf("AC-23: Feld %s durch send_email-PUT veraendert: vorher %s, nachher %s", k, a, b)
			}
		}
	}
}

// AC-23/Spec §4.2 (Regressionsschutz, heute gruen): ein Alt-Preset OHNE
// send_email bleibt nach einem fremden PUT ohne das Feld oder mit true —
// nie false (Alt-Presets duerfen nicht verstummen).
func TestUpdateComparePreset_2795_FehlendesSendEmailBleibtFehlendOderTrue(t *testing.T) {
	s := newTestStore(t)
	pfad := seedPresetFor2795(t, s, "usera", "cp-2795-alt")
	if _, ok := readJSON2795(t, pfad)["send_email"]; ok {
		t.Fatalf("Vorbedingung: Alt-Preset darf send_email nicht tragen")
	}
	r := briefingVergleichEtagRouter(s)
	w := doReq(r, http.MethodPut, "/api/compare/presets/cp-2795-alt", `{"name":"umbenannt"}`, "", "usera")
	if w.Code != http.StatusOK {
		t.Fatalf("PUT expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if v, ok := readJSON2795(t, pfad)["send_email"]; ok && v != true {
		t.Errorf("§4.2: fehlendes send_email wurde zu %v — Alt-Presets duerfen nicht verstummen", v)
	}
}

// ─────────────────────── AC-34: zwei Nutzer ────────────────────────────────

// AC-34: A aendert ueber Trip-PUT und Preset-PUT 06:45, send_email,
// Dringlichkeit, Stille Stunden und Cooldown an EIGENEN Objekten. B's Dateien
// (gleiche IDs!) bleiben byte-gleich; ein PUT von B auf A's Objekt ist kein
// Erfolg und aendert A's Datei nicht; A's Werte stehen danach in A's Dateien.
func TestZustellung_2795_ZweiNutzerGetrennt(t *testing.T) {
	s := newTestStore(t)
	tripA := seedTripFor2795(t, s, "usera", "trip-2795-mt")
	presetA := seedPresetFor2795(t, s, "usera", "cp-2795-mt")
	tripB := seedTripFor2795(t, s, "userb", "trip-2795-mt")
	presetB := seedPresetFor2795(t, s, "userb", "cp-2795-mt")
	tripBVorher, _ := os.ReadFile(tripB)
	presetBVorher, _ := os.ReadFile(presetB)
	r := briefingVergleichEtagRouter(s)

	tripBody := `{"report_config":{"morning_time":"06:45","send_email":false},` +
		`"alert_channel_thresholds":{"email":"LOW","telegram":"HIGH"},` +
		`"alert_quiet_from":"22:00","alert_quiet_to":"06:00","alert_cooldown_minutes":45}`
	if w := doReq(r, http.MethodPut, "/api/trips/trip-2795-mt", tripBody, "", "usera"); w.Code != http.StatusOK {
		t.Fatalf("AC-34: A Trip-PUT expected 200, got %d: %s", w.Code, w.Body.String())
	}
	presetBody := `{"morning_time":"06:45","send_email":false,` +
		`"alert_channel_thresholds":{"email":"LOW","telegram":"HIGH"},` +
		`"alert_quiet_from":"22:00","alert_quiet_to":"06:00","alert_cooldown_minutes":45}`
	if w := doReq(r, http.MethodPut, "/api/compare/presets/cp-2795-mt", presetBody, "", "usera"); w.Code != http.StatusOK {
		t.Fatalf("AC-34: A Preset-PUT expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// B's Dateien mit denselben IDs bleiben byte-gleich.
	if b, _ := os.ReadFile(tripB); string(b) != string(tripBVorher) {
		t.Errorf("AC-34: B's Trip durch A's PUT veraendert: %s", b)
	}
	if b, _ := os.ReadFile(presetB); string(b) != string(presetBVorher) {
		t.Errorf("AC-34: B's Preset durch A's PUT veraendert: %s", b)
	}

	// B schreibt auf eine nur bei A existierende ID: abgelehnt, A unveraendert.
	seedTripFor2795(t, s, "usera", "trip-2795-nur-a")
	seedPresetFor2795(t, s, "usera", "cp-2795-nur-a")
	nurATrip := filepath.Join(s.WithUser("usera").BriefingsDir(), "trip-2795-nur-a.json")
	nurAPreset := filepath.Join(s.WithUser("usera").BriefingsDir(), "cp-2795-nur-a.json")
	tVorher, _ := os.ReadFile(nurATrip)
	pVorher, _ := os.ReadFile(nurAPreset)
	if w := doReq(r, http.MethodPut, "/api/trips/trip-2795-nur-a",
		`{"report_config":{"morning_time":"05:15"}}`, "", "userb"); w.Code == http.StatusOK {
		t.Errorf("AC-34: B's Trip-PUT auf A's Objekt darf nicht 200 liefern")
	}
	if w := doReq(r, http.MethodPut, "/api/compare/presets/cp-2795-nur-a",
		`{"morning_time":"05:15","send_email":false}`, "", "userb"); w.Code == http.StatusOK {
		t.Errorf("AC-34: B's Preset-PUT auf A's Objekt darf nicht 200 liefern")
	}
	if b, _ := os.ReadFile(nurATrip); string(b) != string(tVorher) {
		t.Errorf("AC-34: A's Trip durch B's PUT veraendert: %s", b)
	}
	if b, _ := os.ReadFile(nurAPreset); string(b) != string(pVorher) {
		t.Errorf("AC-34: A's Preset durch B's PUT veraendert: %s", b)
	}
	if _, err := os.Stat(filepath.Join(s.WithUser("userb").BriefingsDir(), "trip-2795-nur-a.json")); err == nil {
		t.Errorf("AC-34: B's PUT hat unter B eine Datei mit A's ID angelegt")
	}

	// A's Werte sind in A's Dateien angekommen.
	ta := readJSON2795(t, tripA)
	rc, _ := ta["report_config"].(map[string]interface{})
	if c := clockH2795(rc["morning_time"]); c != "06:45" {
		t.Errorf("AC-34: A's Trip morning_time %q, erwartet 06:45", c)
	}
	if rc["send_email"] != false {
		t.Errorf("AC-34: A's Trip report_config.send_email %v, erwartet false", rc["send_email"])
	}
	if ta["alert_cooldown_minutes"] != float64(45) || ta["alert_quiet_from"] != "22:00" {
		t.Errorf("AC-34: A's Trip Cooldown/Stille Stunden nicht gespeichert: %v / %v",
			ta["alert_cooldown_minutes"], ta["alert_quiet_from"])
	}
	pa := readJSON2795(t, presetA)
	if c := clockH2795(pa["morning_time"]); c != "06:45" {
		t.Errorf("AC-34: A's Preset morning_time %q, erwartet 06:45", c)
	}
	if v, ok := pa["send_email"]; !ok || v != false {
		t.Errorf("AC-34: A's Preset send_email %v (vorhanden=%v), erwartet false", v, ok)
	}
	if th, _ := pa["alert_channel_thresholds"].(map[string]interface{}); th["telegram"] != "HIGH" {
		t.Errorf("AC-34: A's Preset Dringlichkeit nicht gespeichert: %v", pa["alert_channel_thresholds"])
	}
	if pa["alert_cooldown_minutes"] != float64(45) || pa["alert_quiet_to"] != "06:00" {
		t.Errorf("AC-34: A's Preset Cooldown/Stille Stunden nicht gespeichert: %v / %v",
			pa["alert_cooldown_minutes"], pa["alert_quiet_to"])
	}
}
