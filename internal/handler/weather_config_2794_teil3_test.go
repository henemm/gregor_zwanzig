package handler

// Issue #2794 S3a Teil 3 — Reiter Wetter, Speicherweg Trip.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md (Datenfluss und
// Speicherwege, AC-20, AC-30, serverseitige Seite von AC-17).
//
// Echte Handler, echter Store im Temp-Verzeichnis, zwei Nutzer ueber den
// echten Auth-Kontext (middleware.ContextWithUserID). Kein Mock. Beide Nutzer
// tragen dieselbe Trip-Kennung, damit ein Cross-User-Leck auffiele.

import (
	"encoding/json"
	"net/http"
	"reflect"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const teil3TripID = "t-2794-teil3"

func teil3TripRouter(s *store.Store) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.Lang(s))
	r.Get("/api/trips/{id}/weather-config", GetTripWeatherConfigHandler(s))
	r.Put("/api/trips/{id}/weather-config", PutTripWeatherConfigHandler(s))
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	return r
}

// teil3AmpelA: Nutzer A mit gesetzten Grenzen und Alarm-ab-Stufen.
func teil3AmpelA() obj {
	return obj{"template": "allgemein", "metrics": obj{
		"temperature": obj{"upper": obj{"yellow": 28.0, "orange": 32.0, "red": 36.0}, "alarm_ab": "orange"},
		"gust":        obj{"upper": obj{"yellow": 45.0, "orange": 60.0, "red": 80.0}, "alarm_ab": "red"},
	}}
}

// teil3AmpelBAlt: B's bisherige Abweichungen (gust), die im neuen Payload fehlen.
func teil3AmpelBAlt() obj {
	return obj{"template": "allgemein", "metrics": obj{
		"gust": obj{"upper": obj{"yellow": 40.0, "orange": 55.0, "red": 70.0}, "alarm_ab": "yellow"},
	}}
}

func teil3SeedTrip(t *testing.T, s *store.Store, user string, ampel obj, extra obj) {
	t.Helper()
	dc := obj{
		"preset_name":         "allgemein",
		"metrics":             []interface{}{obj{"metric_id": "temperature", "enabled": true}, obj{"metric_id": "gust", "enabled": true}},
		"ampel":               ampel,
		"metric_alert_levels": obj{"wind_gust": "sensibel", "temperature": "standard"},
		"alarm_ab_migration":  "2793",
		// Zustellungs-Felder (Reiter Zustellung, nicht vom Reiter Wetter angefasst)
		"channel_layouts": obj{"sms": obj{"metrics": []interface{}{"temperature"}}},
		"hourly_enabled":  true,
	}
	for k, v := range extra {
		dc[k] = v
	}
	trip := model.Trip{ID: teil3TripID, Name: "Trip " + user,
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}},
		DisplayConfig: dc,
		ReportConfig:  obj{"send_email": true, "morning_time": "07:00:00", "day_window_start_hour": 6.0, "day_window_end_hour": 18.0},
	}
	if err := s.WithUser(user).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip %s: %v", user, err)
	}
}

func teil3Fingerprint(t *testing.T, s *store.Store, user, id string) string {
	t.Helper()
	fp, err := s.WithUser(user).BriefingFingerprint(id)
	if err != nil || fp == "" {
		t.Fatalf("BriefingFingerprint %s/%s: %q %v", user, id, fp, err)
	}
	return fp
}

func teil3LoadTrip(t *testing.T, s *store.Store, user string) *model.Trip {
	t.Helper()
	trip, err := s.WithUser(user).LoadTrip(teil3TripID)
	if err != nil || trip == nil {
		t.Fatalf("LoadTrip %s: %v", user, err)
	}
	return trip
}

// teil3BPayloadWetter: was der Reiter Wetter im Trip auf /weather-config sendet
// (Ampel als vollstaendige Abweichungsmenge, metrics vollstaendig).
func teil3BPayloadWetter() obj {
	return obj{
		"ampel": obj{"template": "allgemein", "metrics": obj{
			"wind": obj{"upper": obj{"yellow": 30.0, "orange": 50.0, "red": 70.0}, "alarm_ab": "orange"},
		}},
		"metrics": []interface{}{
			obj{"metric_id": "temperature", "enabled": true},
			obj{"metric_id": "gust", "enabled": true},
			obj{"metric_id": "wind", "enabled": true},
		},
	}
}

// AC-30 (Trip): B speichert Ampel, Metriken, Warn-Felder und Tagesfenster;
// A speichert parallel eine unabhaengige Einstellung. A bleibt unveraendert,
// B bekommt nichts von A, B's nicht angefasste display_config-Schluessel
// bleiben, ampel wird als Ganzes ersetzt.
func TestTeil3_2794_TripWeatherConfig_ZweiNutzer_FeldErhalt(t *testing.T) {
	s := newTestStore(t)
	teil3SeedTrip(t, s, "nutzer-a", teil3AmpelA(), obj{"metric_alert_levels": obj{"thunder_level": "off"}, "alarm_ab_migration": "2793-a"})
	teil3SeedTrip(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	h := teil3TripRouter(s)

	fpA := teil3Fingerprint(t, s, "nutzer-a", teil3TripID)
	vorherA := teil3LoadTrip(t, s, "nutzer-a")
	vorherB := teil3LoadTrip(t, s, "nutzer-b")

	// B: Reiter Wetter speichert (Ampel/Metriken auf /weather-config,
	// Warn-Felder und Tagesfenster auf den Trip).
	w := ampelAnfrage(t, h, "PUT", "/api/trips/"+teil3TripID+"/weather-config", "nutzer-b", "de", teil3BPayloadWetter())
	if w.Code != http.StatusOK {
		t.Fatalf("B weather-config: %d %s", w.Code, w.Body.String())
	}
	w = ampelAnfrage(t, h, "PUT", "/api/trips/"+teil3TripID, "nutzer-b", "de", obj{
		"official_alerts_enabled": false,
		"official_warnings":       obj{"enabled": false},
		"report_config":           obj{"day_window_start_hour": 7, "day_window_end_hour": 20},
	})
	if w.Code != http.StatusOK {
		t.Fatalf("B trip: %d %s", w.Code, w.Body.String())
	}

	// A-Datei byte-gleich nach B's Speichern.
	if got := teil3Fingerprint(t, s, "nutzer-a", teil3TripID); got != fpA {
		t.Fatalf("Datei von A durch B's Speichern veraendert")
	}

	// A speichert parallel eine unabhaengige Einstellung.
	w = ampelAnfrage(t, h, "PUT", "/api/trips/"+teil3TripID+"/weather-config", "nutzer-a", "de", obj{"theme": "dunkel"})
	if w.Code != http.StatusOK {
		t.Fatalf("A weather-config: %d %s", w.Code, w.Body.String())
	}

	a := teil3LoadTrip(t, s, "nutzer-a")
	for _, k := range []string{"ampel", "metrics", "metric_alert_levels", "alarm_ab_migration", "channel_layouts", "hourly_enabled"} {
		if !reflect.DeepEqual(a.DisplayConfig[k], vorherA.DisplayConfig[k]) {
			t.Errorf("A display_config[%s] veraendert: vorher %v, nachher %v", k, vorherA.DisplayConfig[k], a.DisplayConfig[k])
		}
	}
	if a.DisplayConfig["theme"] != "dunkel" {
		t.Errorf("A's eigene Einstellung nicht gespeichert: %v", a.DisplayConfig["theme"])
	}
	if !reflect.DeepEqual(a.ReportConfig, vorherA.ReportConfig) ||
		!reflect.DeepEqual(a.OfficialAlertsEnabled, vorherA.OfficialAlertsEnabled) ||
		!reflect.DeepEqual(a.OfficialWarnings, vorherA.OfficialWarnings) {
		t.Errorf("A report_config/Warn-Felder veraendert")
	}

	b := teil3LoadTrip(t, s, "nutzer-b")
	// ampel als Ganzes ersetzt: alte gust-Abweichung weg, wind da, nichts von A.
	wantAmpel := teil3BPayloadWetter()["ampel"]
	gotAmpel, _ := json.Marshal(b.DisplayConfig["ampel"])
	wantRaw, _ := json.Marshal(wantAmpel)
	if string(gotAmpel) != string(wantRaw) {
		t.Errorf("B ampel nicht als Ganzes ersetzt:\n got %s\nwant %s", gotAmpel, wantRaw)
	}
	// nicht angefasste Schluessel bleiben bei B.
	for _, k := range []string{"metric_alert_levels", "alarm_ab_migration", "channel_layouts", "hourly_enabled", "preset_name"} {
		if !reflect.DeepEqual(b.DisplayConfig[k], vorherB.DisplayConfig[k]) {
			t.Errorf("B display_config[%s] verloren/veraendert: vorher %v, nachher %v", k, vorherB.DisplayConfig[k], b.DisplayConfig[k])
		}
	}
	if b.DisplayConfig["alarm_ab_migration"] == "2793-a" || b.DisplayConfig["theme"] != nil {
		t.Errorf("B hat Werte von A bekommen: %v", b.DisplayConfig)
	}
	if ml, _ := b.DisplayConfig["metric_alert_levels"].(map[string]interface{}); ml["thunder_level"] != nil {
		t.Errorf("B hat metric_alert_levels von A: %v", ml)
	}
	// Warn-Felder und Tagesfenster bei B gespeichert, report_config-Rest erhalten.
	if b.OfficialAlertsEnabled == nil || *b.OfficialAlertsEnabled {
		t.Errorf("B official_alerts_enabled nicht false: %v", b.OfficialAlertsEnabled)
	}
	if b.OfficialWarnings == nil || b.OfficialWarnings.Enabled {
		t.Errorf("B official_warnings.enabled nicht false: %+v", b.OfficialWarnings)
	}
	if b.ReportConfig["day_window_start_hour"] != 7.0 || b.ReportConfig["day_window_end_hour"] != 20.0 {
		t.Errorf("B Tagesfenster nicht gespeichert: %v", b.ReportConfig)
	}
	if b.ReportConfig["send_email"] != true || b.ReportConfig["morning_time"] == nil {
		t.Errorf("B report_config-Rest verloren: %v", b.ReportConfig)
	}
}

// AC-20 (Trip): official_alerts_enabled und official_warnings.enabled beide
// false bzw. beide true speichern und wieder lesen; beides bleibt zugleich
// erhalten. Zwei Nutzer, B bleibt unberuehrt.
func TestTeil3_2794_TripAmtlicheWarnungen_RoundtripBeideFelder(t *testing.T) {
	s := newTestStore(t)
	teil3SeedTrip(t, s, "nutzer-a", teil3AmpelA(), nil)
	teil3SeedTrip(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	h := teil3TripRouter(s)
	// Ausgangslage: Altfelder laufen auseinander (Bericht an, Alarm aus).
	w := ampelAnfrage(t, h, "PUT", "/api/trips/"+teil3TripID, "nutzer-a", "de", obj{
		"official_alerts_enabled": true, "official_warnings": obj{"enabled": false}})
	if w.Code != http.StatusOK {
		t.Fatalf("Seed: %d %s", w.Code, w.Body.String())
	}
	fpB := teil3Fingerprint(t, s, "nutzer-b", teil3TripID)

	for _, wert := range []bool{false, true, false} {
		w := ampelAnfrage(t, h, "PUT", "/api/trips/"+teil3TripID, "nutzer-a", "de", obj{
			"official_alerts_enabled": wert, "official_warnings": obj{"enabled": wert}})
		if w.Code != http.StatusOK {
			t.Fatalf("PUT %v: %d %s", wert, w.Code, w.Body.String())
		}
		// Wieder lesen ueber den Store (frischer Load von Platte).
		a := teil3LoadTrip(t, s, "nutzer-a")
		if a.OfficialAlertsEnabled == nil || *a.OfficialAlertsEnabled != wert {
			t.Errorf("wert=%v: official_alerts_enabled = %v", wert, a.OfficialAlertsEnabled)
		}
		if a.OfficialWarnings == nil || a.OfficialWarnings.Enabled != wert {
			t.Errorf("wert=%v: official_warnings = %+v", wert, a.OfficialWarnings)
		}
		// Ein nachfolgender Wetter-Speichervorgang (anderer Pfad) darf beide nicht kippen.
		w = ampelAnfrage(t, h, "PUT", "/api/trips/"+teil3TripID+"/weather-config", "nutzer-a", "de", teil3BPayloadWetter())
		if w.Code != http.StatusOK {
			t.Fatalf("weather-config: %d %s", w.Code, w.Body.String())
		}
		a = teil3LoadTrip(t, s, "nutzer-a")
		if a.OfficialAlertsEnabled == nil || *a.OfficialAlertsEnabled != wert || a.OfficialWarnings == nil || a.OfficialWarnings.Enabled != wert {
			t.Errorf("wert=%v: nach /weather-config nicht mehr beide gleich: %v / %+v", wert, a.OfficialAlertsEnabled, a.OfficialWarnings)
		}
	}
	if teil3Fingerprint(t, s, "nutzer-b", teil3TripID) != fpB {
		t.Errorf("B veraendert")
	}
}

// AC-17 serverseitig (Trip): oben gelb 50, orange 40 wird abgewiesen, die
// zuvor gespeicherten Grenzen bleiben (Datei byte-gleich), B unberuehrt.
func TestTeil3_2794_TripWeatherConfig_UngueltigeReihenfolge_Abgewiesen(t *testing.T) {
	s := newTestStore(t)
	teil3SeedTrip(t, s, "nutzer-a", teil3AmpelA(), nil)
	teil3SeedTrip(t, s, "nutzer-b", teil3AmpelBAlt(), nil)
	fpA := teil3Fingerprint(t, s, "nutzer-a", teil3TripID)
	fpB := teil3Fingerprint(t, s, "nutzer-b", teil3TripID)
	h := teil3TripRouter(s)

	kaputt := teil3BPayloadWetter()
	kaputt["ampel"] = obj{"template": "allgemein", "metrics": obj{
		"wind": obj{"upper": obj{"yellow": 50.0, "orange": 40.0, "red": 70.0}},
	}}
	w := ampelAnfrage(t, h, "PUT", "/api/trips/"+teil3TripID+"/weather-config", "nutzer-a", "de", kaputt)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("erwartet 400, got %d %s", w.Code, w.Body.String())
	}
	var e struct{ Code string }
	_ = json.Unmarshal(w.Body.Bytes(), &e)
	if e.Code != "ampel_ungueltig" {
		t.Errorf("Code = %q, erwartet ampel_ungueltig", e.Code)
	}
	if teil3Fingerprint(t, s, "nutzer-a", teil3TripID) != fpA {
		t.Errorf("A-Datei trotz Ablehnung veraendert")
	}
	if teil3Fingerprint(t, s, "nutzer-b", teil3TripID) != fpB {
		t.Errorf("B-Datei veraendert")
	}
	a := teil3LoadTrip(t, s, "nutzer-a")
	got, _ := json.Marshal(a.DisplayConfig["ampel"])
	want, _ := json.Marshal(teil3AmpelA())
	if string(got) != string(want) {
		t.Errorf("Grenzen nicht erhalten:\n got %s\nwant %s", got, want)
	}
}
