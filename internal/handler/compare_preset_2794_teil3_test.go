package handler

// Issue #2794 S3a Teil 3 — Reiter Wetter, Speicherweg Orts-Briefing
// (Vergleich). Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
// (Datenfluss und Speicherwege, AC-20, AC-30, serverseitige Seite von AC-17).
//
// Wie der echte Hub-Weg (enqueueHubWrite): erst GET fuer den ETag, dann PUT
// mit If-Match. Echte Handler, echter Store im Temp-Verzeichnis, zwei Nutzer
// mit derselben Preset-Kennung ueber den echten Auth-Kontext. Kein Mock.

import (
	"encoding/json"
	"net/http"
	"reflect"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const teil3PresetID = "cp-2794-teil3"

func teil3CompareRouter(s *store.Store) http.Handler {
	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	r.Put("/api/compare/presets/{id}", UpdateComparePresetHandler(s))
	return r
}

func teil3SeedPreset(t *testing.T, s *store.Store, user string, ampel obj, extra obj) {
	t.Helper()
	dc := obj{
		"active_metrics":      []interface{}{"temperature", "gust"},
		"ampel":               ampel,
		"metric_alert_levels": obj{"wind_gust": "sensibel"},
		"alarm_ab_migration":  "2793",
		// Zustellungs-Felder (Reiter Zustellung)
		"channel_layouts": obj{"sms": obj{"metrics": []interface{}{"temperature"}}},
		"ideal_ranges":    obj{"temp_max_c": obj{"min": 10.0}},
	}
	for k, v := range extra {
		dc[k] = v
	}
	an := true
	start, end := 6, 18
	cp := model.ComparePreset{ID: teil3PresetID, Name: "Vergleich " + user, UserID: user,
		LocationIDs: []string{"loc-1", "loc-2"}, Schedule: "daily", Profil: "ALLGEMEIN",
		ForecastHours: 48, HourFrom: 6, HourTo: 18, Empfaenger: []string{user + "@example.com"},
		DisplayConfig:         dc,
		OfficialAlertsEnabled: &an,
		OfficialWarnings:      &model.OfficialWarningsConfig{Enabled: true, Sources: []string{"geosphere_warn"}},
		DayWindowStartHour:    &start,
		DayWindowEndHour:      &end,
	}
	if err := s.WithUser(user).SaveComparePreset(cp); err != nil {
		t.Fatalf("SaveComparePreset %s: %v", user, err)
	}
}

func teil3LoadPreset(t *testing.T, s *store.Store, user string) *model.ComparePreset {
	t.Helper()
	p, err := s.WithUser(user).LoadComparePreset(teil3PresetID)
	if err != nil || p == nil {
		t.Fatalf("LoadComparePreset %s: %v", user, err)
	}
	return p
}

// teil3HubPut: GET (ETag) und PUT mit If-Match, wie die Hub-Schreibschlange.
func teil3HubPut(t *testing.T, h http.Handler, user string, body obj) int {
	t.Helper()
	path := "/api/compare/presets/" + teil3PresetID
	g := doReq(h, http.MethodGet, path, "", "", user)
	if g.Code != http.StatusOK {
		t.Fatalf("GET %s: %d %s", user, g.Code, g.Body.String())
	}
	et := mustETag(t, g)
	raw, _ := json.Marshal(body)
	w := doReq(h, http.MethodPut, path, string(raw), et, user)
	if w.Code == http.StatusOK {
		mustETag(t, w)
	}
	return w.Code
}

func teil3BPayloadVergleich(wert bool) obj {
	return obj{
		"display_config": obj{
			"active_metrics": []interface{}{"temperature", "gust", "wind"},
			"ampel": obj{"template": "allgemein", "metrics": obj{
				"wind": obj{"upper": obj{"yellow": 30.0, "orange": 50.0, "red": 70.0}, "alarm_ab": "orange"},
			}},
		},
		"official_alerts_enabled": wert,
		"official_warnings":       obj{"enabled": wert},
		"radar_alert_enabled":     true,
		"day_window_start_hour":   7,
		"day_window_end_hour":     20,
	}
}

// AC-30 (Vergleich): B speichert ueber den Hub-Weg; A speichert parallel eine
// unabhaengige Einstellung. A bleibt unveraendert, B bekommt nichts von A,
// B's nicht angefasste display_config-Schluessel bleiben, ampel als Ganzes ersetzt.
func TestTeil3_2794_ComparePreset_ZweiNutzer_FeldErhalt(t *testing.T) {
	s := newTestStore(t)
	teil3SeedPreset(t, s, "nutzer-a", teil3AmpelA(), obj{"metric_alert_levels": obj{"thunder_level": "off"}, "alarm_ab_migration": "2793-a"})
	teil3SeedPreset(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	h := teil3CompareRouter(s)

	fpA := teil3Fingerprint(t, s, "nutzer-a", teil3PresetID)
	vorherA := teil3LoadPreset(t, s, "nutzer-a")
	vorherB := teil3LoadPreset(t, s, "nutzer-b")

	if code := teil3HubPut(t, h, "nutzer-b", teil3BPayloadVergleich(false)); code != http.StatusOK {
		t.Fatalf("B PUT: %d", code)
	}
	if teil3Fingerprint(t, s, "nutzer-a", teil3PresetID) != fpA {
		t.Fatalf("Datei von A durch B's Speichern veraendert")
	}

	// A speichert parallel eine unabhaengige Einstellung.
	if code := teil3HubPut(t, h, "nutzer-a", obj{"display_config": obj{"theme": "dunkel"}}); code != http.StatusOK {
		t.Fatalf("A PUT: %d", code)
	}
	a := teil3LoadPreset(t, s, "nutzer-a")
	for _, k := range []string{"active_metrics", "ampel", "metric_alert_levels", "alarm_ab_migration", "channel_layouts", "ideal_ranges"} {
		if !reflect.DeepEqual(a.DisplayConfig[k], vorherA.DisplayConfig[k]) {
			t.Errorf("A display_config[%s] veraendert: vorher %v, nachher %v", k, vorherA.DisplayConfig[k], a.DisplayConfig[k])
		}
	}
	if a.DisplayConfig["theme"] != "dunkel" {
		t.Errorf("A's eigene Einstellung nicht gespeichert")
	}
	if !reflect.DeepEqual(a.OfficialAlertsEnabled, vorherA.OfficialAlertsEnabled) ||
		!reflect.DeepEqual(a.OfficialWarnings, vorherA.OfficialWarnings) ||
		!reflect.DeepEqual(a.RadarAlertEnabled, vorherA.RadarAlertEnabled) ||
		!reflect.DeepEqual(a.DayWindowStartHour, vorherA.DayWindowStartHour) ||
		!reflect.DeepEqual(a.DayWindowEndHour, vorherA.DayWindowEndHour) ||
		!reflect.DeepEqual(a.Empfaenger, vorherA.Empfaenger) {
		t.Errorf("A top-level-Felder veraendert: %+v", a)
	}

	b := teil3LoadPreset(t, s, "nutzer-b")
	gotAmpel, _ := json.Marshal(b.DisplayConfig["ampel"])
	wantAmpel, _ := json.Marshal(teil3BPayloadVergleich(false)["display_config"].(obj)["ampel"])
	if string(gotAmpel) != string(wantAmpel) {
		t.Errorf("B ampel nicht als Ganzes ersetzt:\n got %s\nwant %s", gotAmpel, wantAmpel)
	}
	if !reflect.DeepEqual(b.DisplayConfig["active_metrics"], []interface{}{"temperature", "gust", "wind"}) {
		t.Errorf("B active_metrics = %v", b.DisplayConfig["active_metrics"])
	}
	for _, k := range []string{"metric_alert_levels", "alarm_ab_migration", "channel_layouts", "ideal_ranges"} {
		if !reflect.DeepEqual(b.DisplayConfig[k], vorherB.DisplayConfig[k]) {
			t.Errorf("B display_config[%s] verloren/veraendert: vorher %v, nachher %v", k, vorherB.DisplayConfig[k], b.DisplayConfig[k])
		}
	}
	if b.DisplayConfig["alarm_ab_migration"] == "2793-a" || b.DisplayConfig["theme"] != nil {
		t.Errorf("B hat Werte von A bekommen: %v", b.DisplayConfig)
	}
	if b.OfficialAlertsEnabled == nil || *b.OfficialAlertsEnabled {
		t.Errorf("B official_alerts_enabled = %v", b.OfficialAlertsEnabled)
	}
	if b.OfficialWarnings == nil || b.OfficialWarnings.Enabled {
		t.Errorf("B official_warnings = %+v", b.OfficialWarnings)
	}
	if b.OfficialWarnings != nil && !reflect.DeepEqual(b.OfficialWarnings.Sources, []string{"geosphere_warn"}) {
		t.Errorf("B official_warnings.sources verloren: %+v", b.OfficialWarnings)
	}
	if b.RadarAlertEnabled == nil || !*b.RadarAlertEnabled {
		t.Errorf("B radar_alert_enabled = %v", b.RadarAlertEnabled)
	}
	if b.DayWindowStartHour == nil || *b.DayWindowStartHour != 7 || b.DayWindowEndHour == nil || *b.DayWindowEndHour != 20 {
		t.Errorf("B Tagesfenster = %v-%v", b.DayWindowStartHour, b.DayWindowEndHour)
	}
	if !reflect.DeepEqual(b.Empfaenger, vorherB.Empfaenger) || !reflect.DeepEqual(b.LocationIDs, vorherB.LocationIDs) {
		t.Errorf("B Zustellungs-/Orts-Felder veraendert: %v %v", b.Empfaenger, b.LocationIDs)
	}
}

// AC-20 (Vergleich): beide Felder false bzw. true speichern und wieder lesen
// (ueber GET, wie der Hub hydriert); beides bleibt zugleich erhalten.
func TestTeil3_2794_ComparePreset_AmtlicheWarnungen_RoundtripBeideFelder(t *testing.T) {
	s := newTestStore(t)
	teil3SeedPreset(t, s, "nutzer-a", teil3AmpelA(), nil)
	teil3SeedPreset(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	h := teil3CompareRouter(s)
	// Ausgangslage: Felder laufen auseinander (Bericht an, Alarm aus).
	if code := teil3HubPut(t, h, "nutzer-a", obj{"official_alerts_enabled": true, "official_warnings": obj{"enabled": false}}); code != http.StatusOK {
		t.Fatalf("Seed: %d", code)
	}
	fpB := teil3Fingerprint(t, s, "nutzer-b", teil3PresetID)

	for _, wert := range []bool{false, true, false} {
		if code := teil3HubPut(t, h, "nutzer-a", teil3BPayloadVergleich(wert)); code != http.StatusOK {
			t.Fatalf("PUT %v: %d", wert, code)
		}
		g := doReq(h, http.MethodGet, "/api/compare/presets/"+teil3PresetID, "", "", "nutzer-a")
		var got struct {
			OfficialAlertsEnabled *bool `json:"official_alerts_enabled"`
			OfficialWarnings      *struct {
				Enabled bool `json:"enabled"`
			} `json:"official_warnings"`
		}
		if err := json.Unmarshal(g.Body.Bytes(), &got); err != nil {
			t.Fatalf("GET decode: %v (%s)", err, g.Body.String())
		}
		if got.OfficialAlertsEnabled == nil || *got.OfficialAlertsEnabled != wert {
			t.Errorf("wert=%v: GET official_alerts_enabled = %v", wert, got.OfficialAlertsEnabled)
		}
		if got.OfficialWarnings == nil || got.OfficialWarnings.Enabled != wert {
			t.Errorf("wert=%v: GET official_warnings = %+v", wert, got.OfficialWarnings)
		}
		// Ein nachfolgender Speichervorgang ohne Warn-Felder kippt keinen der beiden.
		if code := teil3HubPut(t, h, "nutzer-a", obj{"display_config": obj{"theme": "x"}}); code != http.StatusOK {
			t.Fatalf("Folge-PUT: %d", code)
		}
		p := teil3LoadPreset(t, s, "nutzer-a")
		if p.OfficialAlertsEnabled == nil || *p.OfficialAlertsEnabled != wert || p.OfficialWarnings == nil || p.OfficialWarnings.Enabled != wert {
			t.Errorf("wert=%v: nach Folge-PUT nicht mehr beide gleich: %v / %+v", wert, p.OfficialAlertsEnabled, p.OfficialWarnings)
		}
	}
	if teil3Fingerprint(t, s, "nutzer-b", teil3PresetID) != fpB {
		t.Errorf("B veraendert")
	}
}

// AC-17 serverseitig (Vergleich): oben gelb 50, orange 40 wird abgewiesen,
// die zuvor gespeicherten Grenzen bleiben (Datei byte-gleich), B unberuehrt.
func TestTeil3_2794_ComparePreset_UngueltigeReihenfolge_Abgewiesen(t *testing.T) {
	s := newTestStore(t)
	teil3SeedPreset(t, s, "nutzer-a", teil3AmpelA(), nil)
	teil3SeedPreset(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	fpA := teil3Fingerprint(t, s, "nutzer-a", teil3PresetID)
	fpB := teil3Fingerprint(t, s, "nutzer-b", teil3PresetID)
	h := teil3CompareRouter(s)

	kaputt := teil3BPayloadVergleich(false)
	kaputt["display_config"] = obj{
		"active_metrics": []interface{}{"temperature", "gust", "wind"},
		"ampel": obj{"template": "allgemein", "metrics": obj{
			"wind": obj{"upper": obj{"yellow": 50.0, "orange": 40.0, "red": 70.0}},
		}},
	}
	if code := teil3HubPut(t, h, "nutzer-a", kaputt); code != http.StatusBadRequest {
		t.Fatalf("erwartet 400, got %d", code)
	}
	if teil3Fingerprint(t, s, "nutzer-a", teil3PresetID) != fpA {
		t.Errorf("A-Datei trotz Ablehnung veraendert")
	}
	if teil3Fingerprint(t, s, "nutzer-b", teil3PresetID) != fpB {
		t.Errorf("B-Datei veraendert")
	}
	a := teil3LoadPreset(t, s, "nutzer-a")
	got, _ := json.Marshal(a.DisplayConfig["ampel"])
	want, _ := json.Marshal(teil3AmpelA())
	if string(got) != string(want) {
		t.Errorf("Grenzen nicht erhalten:\n got %s\nwant %s", got, want)
	}
}
