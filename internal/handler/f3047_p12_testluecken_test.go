package handler

// Issue #3047 Runde 7, Paket p12 (Testluecken TL5, TL6 aus dem Editor-Inventar):
// Mutationen, die bisher alle Tests ueberlebten, bei korrektem Verhalten.
//
// TL5 (M16): PUT /api/trips/{id} mit `alert_channels` OHNE `email` darf den
// Bestandswert der E-Mail-Alarmzeile nicht verlieren (Feld-Merge in trip.go).
// TL6 (M21): GET /api/compare/presets/{id} heilt ein halbes Tagesfenster-Paar
// beim Laden (ClampComparePresetDayWindow im Store-Lesepfad) — sonst zeigt der
// Orte-Editor ein halbes Paar, das die Ausgabe nicht verwendet.
//
// Beide mit zwei Nutzern (Mandantentrennung, CLAUDE.md).
//
//   go test ./internal/handler/ -run 'F3047P12' -count=1

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func p12SeedTrip(t *testing.T, s *store.Store, user string, ac *model.AlertChannelsConfig) {
	t.Helper()
	trip := model.Trip{
		ID: "p12-trip", Name: "P12 " + user,
		Stages: []model.Stage{{
			ID: "S1", Name: "D1", Date: "2026-07-15",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AlertChannels: ac,
	}
	if err := s.WithUser(user).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip %s: %v", user, err)
	}
}

func p12Bool(t *testing.T, name string, p *bool, want bool) {
	t.Helper()
	if p == nil || *p != want {
		t.Errorf("%s: erwartet %v, bekommen %v", name, want, p)
	}
}

// TL5: Nutzer A schaltet im Alarm-Reiter nur Telegram um (Body ohne `email`);
// sein E-Mail-Alarm „aus" bleibt aus, Nutzer B (gleiche Trip-ID) bleibt unberuehrt.
func TestF3047P12_TL5_TripAlertChannelsOhneEmail_ZweiNutzer_BehaeltEmail(t *testing.T) {
	s := newTestStore(t)
	p12SeedTrip(t, s, "nutzer-a", &model.AlertChannelsConfig{
		Email: boolPtr(false), Telegram: boolPtr(true), Sms: boolPtr(false), PremiumSms: boolPtr(false),
	})
	p12SeedTrip(t, s, "nutzer-b", &model.AlertChannelsConfig{
		Email: boolPtr(true), Telegram: boolPtr(false), Sms: boolPtr(true), PremiumSms: boolPtr(false),
	})

	r := chi.NewRouter()
	r.Put("/api/trips/{id}", UpdateTripHandler(s))
	buf, _ := json.Marshal(map[string]interface{}{"alert_channels": map[string]interface{}{"telegram": false}})
	req := httptest.NewRequest(http.MethodPut, "/api/trips/p12-trip", bytes.NewReader(buf))
	req.Header.Set("Content-Type", "application/json")
	req = addUserToContext(req, "nutzer-a")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	a, err := s.WithUser("nutzer-a").LoadTrip("p12-trip")
	if err != nil || a.AlertChannels == nil {
		t.Fatalf("LoadTrip nutzer-a: %v / %+v", err, a)
	}
	p12Bool(t, "A email (fehlte im Body, Bestand false)", a.AlertChannels.Email, false)
	p12Bool(t, "A telegram (gesendet)", a.AlertChannels.Telegram, false)
	p12Bool(t, "A sms (Bestand)", a.AlertChannels.Sms, false)

	b, err := s.WithUser("nutzer-b").LoadTrip("p12-trip")
	if err != nil || b.AlertChannels == nil {
		t.Fatalf("LoadTrip nutzer-b: %v / %+v", err, b)
	}
	p12Bool(t, "B email", b.AlertChannels.Email, true)
	p12Bool(t, "B sms", b.AlertChannels.Sms, true)
	if b.Name != "P12 nutzer-b" {
		t.Errorf("Fremdzugriff: Name von B geaendert zu %q", b.Name)
	}
}

// TL6: Bestandsdatei mit halbem Tagesfenster (nur Start) wird beim Laden geheilt;
// das gueltige Paar des zweiten Nutzers bleibt erhalten.
func TestF3047P12_TL6_ComparePresetHalbesTagesfenster_ZweiNutzer_GetGeheilt(t *testing.T) {
	dir := t.TempDir()
	s := store.New(dir, "nutzer-a")
	basis := `"location_ids":["loc-a"],"schedule":"manual","profil":"SUMMER_TREKKING",` +
		`"morning_time":"07:00:00","empfaenger":["x@example.com"],"created_at":"2026-01-01T00:00:00Z"`
	writeComparePresetBriefingFixture(t, dir, "nutzer-a",
		`[{"id":"p12-ort","name":"A","user_id":"nutzer-a","day_window_start_hour":6,`+basis+`}]`)
	writeComparePresetBriefingFixture(t, dir, "nutzer-b",
		`[{"id":"p12-ort","name":"B","user_id":"nutzer-b","day_window_start_hour":7,"day_window_end_hour":21,`+basis+`}]`)

	r := chi.NewRouter()
	r.Get("/api/compare/presets/{id}", GetComparePresetHandler(s))
	lese := func(user string) model.ComparePreset {
		req := addUserToContext(httptest.NewRequest(http.MethodGet, "/api/compare/presets/p12-ort", nil), user)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("GET %s: erwartet 200, bekommen %d: %s", user, w.Code, w.Body.String())
		}
		var p model.ComparePreset
		if err := json.Unmarshal(w.Body.Bytes(), &p); err != nil {
			t.Fatalf("Unmarshal %s: %v", user, err)
		}
		return p
	}

	a := lese("nutzer-a")
	if a.Name != "A" {
		t.Fatalf("falscher Datensatz fuer nutzer-a: %q", a.Name)
	}
	if a.DayWindowStartHour != nil || a.DayWindowEndHour != nil {
		t.Errorf("halbes Paar nicht geheilt: start=%v end=%v (Editor zeigte halbes Fenster)",
			a.DayWindowStartHour, a.DayWindowEndHour)
	}
	b := lese("nutzer-b")
	if b.Name != "B" || b.DayWindowStartHour == nil || *b.DayWindowStartHour != 7 ||
		b.DayWindowEndHour == nil || *b.DayWindowEndHour != 21 {
		t.Errorf("gueltiges Paar von B veraendert: %+v / %v / %v", b.Name, b.DayWindowStartHour, b.DayWindowEndHour)
	}
}
