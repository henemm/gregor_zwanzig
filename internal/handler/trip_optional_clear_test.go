package handler

// TDD RED: Issue #2211 (Workflow fix-2211-optional-felder-null)
// Spec: docs/specs/bugfix/optional_felder_null_leert.md
//
// Kontrakt (#99, nie umgesetzt): "Feld vorhanden mit Wert null = ausdruecklich
// leeren; Feld fehlt = Bestand behalten". Alle Tests arbeiten mit ROHEN
// JSON-Bodies durch den echten Router -- Struct-Literale koennen "fehlt" und
// null nicht unterscheiden. Jeder Test assertet ZUERST Status 200 (der Trip-PUT
// braucht keinen If-Match; ohne Header wird angenommen), dann das Feld.
//
// Ausfuehrung:
//   go test ./internal/handler/ -run 'TestTripOptional|TestComparePresetOptional' -v

import (
	"fmt"
	"net/http"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

var tripOptionalFields = []string{
	"alert_cooldown_minutes", "alert_quiet_from", "alert_quiet_to",
	"official_alerts_enabled", "official_alert_triggers_enabled",
	"region", "activity",
}

func optStrPtr(v string) *string { return &v }
func optIntPtr(v int) *int       { return &v }
func optBoolPtr(v bool) *bool    { return &v }

// seedTripAllOptionals legt einen Trip fuer user an, bei dem alle 7 Felder gesetzt sind.
func seedTripAllOptionals(t *testing.T, s *store.Store, user, id string) {
	t.Helper()
	trip := model.Trip{
		ID: id, Name: "Optional-Trip",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		AlertCooldownMinutes:         optIntPtr(45),
		AlertQuietFrom:               optStrPtr("22:00"),
		AlertQuietTo:                 optStrPtr("06:00"),
		OfficialAlertsEnabled:        optBoolPtr(false),
		OfficialAlertTriggersEnabled: optBoolPtr(false),
		Region:                       "Zillertal",
		Activity:                     "wandern",
	}
	if err := s.WithUser(user).SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip: %v", err)
	}
}

func derefOr[T any](p *T, def T) T {
	if p == nil {
		return def
	}
	return *p
}

// optSnapshot liest die 7 Felder aus dem Store; nil bzw. "" => "<leer>".
func optSnapshot(t *testing.T, s *store.Store, user, id string) map[string]string {
	t.Helper()
	tr, err := s.WithUser(user).LoadTrip(id)
	if err != nil || tr == nil {
		t.Fatalf("LoadTrip(%s/%s): %v / %v", user, id, tr, err)
	}
	out := map[string]string{}
	set := func(k string, present bool, v interface{}) {
		if present {
			out[k] = fmt.Sprint(v)
		} else {
			out[k] = "<leer>"
		}
	}
	set("alert_cooldown_minutes", tr.AlertCooldownMinutes != nil, derefOr(tr.AlertCooldownMinutes, 0))
	set("alert_quiet_from", tr.AlertQuietFrom != nil, derefOr(tr.AlertQuietFrom, ""))
	set("alert_quiet_to", tr.AlertQuietTo != nil, derefOr(tr.AlertQuietTo, ""))
	set("official_alerts_enabled", tr.OfficialAlertsEnabled != nil, derefOr(tr.OfficialAlertsEnabled, false))
	set("official_alert_triggers_enabled", tr.OfficialAlertTriggersEnabled != nil, derefOr(tr.OfficialAlertTriggersEnabled, false))
	set("region", tr.Region != "", tr.Region)
	set("activity", tr.Activity != "", tr.Activity)
	return out
}

var optSeedValues = map[string]string{
	"alert_cooldown_minutes":          "45",
	"alert_quiet_from":                "22:00",
	"alert_quiet_to":                  "06:00",
	"official_alerts_enabled":         "false",
	"official_alert_triggers_enabled": "false",
	"region":                          "Zillertal",
	"activity":                        "wandern",
}

func putOK(t *testing.T, r http.Handler, path, user, body string) {
	t.Helper()
	w := doReq(r, http.MethodPut, path, body, "", user)
	if w.Code != http.StatusOK {
		t.Fatalf("PUT %s body=%s: erwartet 200, bekommen %d: %s", path, body, w.Code, w.Body.String())
	}
}

// Test 2 (AC-1, AC-3, AC-9): null leert genau dieses Feld, die uebrigen 6 bleiben.
func TestTripOptionalClear_NullClearsExactlyThatField(t *testing.T) {
	for _, field := range tripOptionalFields {
		t.Run(field, func(t *testing.T) {
			s := newTestStore(t)
			seedTripAllOptionals(t, s, "userA", "t-null")
			r := briefingVergleichEtagRouter(s)
			putOK(t, r, "/api/trips/t-null", "userA", `{"`+field+`":null}`)
			got := optSnapshot(t, s, "userA", "t-null")
			for _, f := range tripOptionalFields {
				want := optSeedValues[f]
				if f == field {
					want = "<leer>"
				}
				if got[f] != want {
					t.Errorf("Feld %s nach {%q:null}: erwartet %q, bekommen %q", f, field, want, got[f])
				}
			}
		})
	}
}

// Test 3 (AC-6): fehlt der Key, bleibt der Bestand -- {} und Teil-Body.
func TestTripOptionalClear_AbsentKeepsAll(t *testing.T) {
	for _, body := range []string{`{}`, `{"name":"X"}`} {
		t.Run(body, func(t *testing.T) {
			s := newTestStore(t)
			seedTripAllOptionals(t, s, "userA", "t-abs")
			r := briefingVergleichEtagRouter(s)
			putOK(t, r, "/api/trips/t-abs", "userA", body)
			got := optSnapshot(t, s, "userA", "t-abs")
			for _, f := range tripOptionalFields {
				if got[f] != optSeedValues[f] {
					t.Errorf("Feld %s nach %s: erwartet %q, bekommen %q", f, body, optSeedValues[f], got[f])
				}
			}
		})
	}
}

// Test 4 (AC-7): Wert setzt, auf Trip ohne Alarm-Felder.
func TestTripOptionalClear_ValueSetsAll(t *testing.T) {
	s := newTestStore(t)
	trip := model.Trip{ID: "t-val", Name: "Leer",
		Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}}}
	if err := s.WithUser("userA").SaveTrip(&trip); err != nil {
		t.Fatal(err)
	}
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/trips/t-val", "userA", `{"alert_cooldown_minutes":30,"alert_quiet_from":"22:00","alert_quiet_to":"06:00","official_alerts_enabled":true,"official_alert_triggers_enabled":true,"region":"Tirol","activity":"skitour"}`)
	got := optSnapshot(t, s, "userA", "t-val")
	want := map[string]string{
		"alert_cooldown_minutes": "30", "alert_quiet_from": "22:00", "alert_quiet_to": "06:00",
		"official_alerts_enabled": "true", "official_alert_triggers_enabled": "true",
		"region": "Tirol", "activity": "skitour",
	}
	for f, w := range want {
		if got[f] != w {
			t.Errorf("Feld %s: erwartet %q, bekommen %q", f, w, got[f])
		}
	}
}

// Test 5 (AC-8): Waechter -- null auf Pflicht-/Listen-Feldern behaelt den Bestand.
func TestTripOptionalClear_NullOnStagesAndNameKeepsExisting(t *testing.T) {
	for _, body := range []string{`{"stages":null}`, `{"name":null}`} {
		t.Run(body, func(t *testing.T) {
			s := newTestStore(t)
			seedTripAllOptionals(t, s, "userA", "t-w")
			r := briefingVergleichEtagRouter(s)
			putOK(t, r, "/api/trips/t-w", "userA", body)
			tr, err := s.WithUser("userA").LoadTrip("t-w")
			if err != nil || tr == nil {
				t.Fatalf("LoadTrip: %v", err)
			}
			if tr.Name != "Optional-Trip" {
				t.Errorf("Name nach %s: erwartet Optional-Trip, bekommen %q", body, tr.Name)
			}
			if len(tr.Stages) != 1 {
				t.Errorf("Etappen nach %s: erwartet 1, bekommen %d", body, len(tr.Stages))
			}
		})
	}
}

// Test 6 (AC-12): Das null uebersteht die Delegation PUT /api/briefings/{id}?kind=route.
func TestTripOptionalClear_NullSurvivesBriefingRouteDelegation(t *testing.T) {
	s := newTestStore(t)
	seedTripAllOptionals(t, s, "userA", "t-route")
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/briefings/t-route?kind=route", "userA", `{"alert_cooldown_minutes":null}`)
	got := optSnapshot(t, s, "userA", "t-route")
	if got["alert_cooldown_minutes"] != "<leer>" {
		t.Errorf("alert_cooldown_minutes ueber briefings-Route: erwartet leer, bekommen %q", got["alert_cooldown_minutes"])
	}
	if got["alert_quiet_from"] != "22:00" {
		t.Errorf("alert_quiet_from darf unberuehrt bleiben, bekommen %q", got["alert_quiet_from"])
	}
}

// AC-10: nur quiet_from null => to bleibt 06:00.
func TestTripOptionalClear_OnlyQuietFromNullKeepsQuietTo(t *testing.T) {
	s := newTestStore(t)
	seedTripAllOptionals(t, s, "userA", "t-half")
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/trips/t-half", "userA", `{"alert_quiet_from":null}`)
	got := optSnapshot(t, s, "userA", "t-half")
	if got["alert_quiet_from"] != "<leer>" {
		t.Errorf("alert_quiet_from: erwartet leer, bekommen %q", got["alert_quiet_from"])
	}
	if got["alert_quiet_to"] != "06:00" {
		t.Errorf("alert_quiet_to: erwartet 06:00, bekommen %q", got["alert_quiet_to"])
	}
}

// Test 7a (AC-11): Zwei Nutzer, A leert, B unberuehrt (Trip, gleiche ID).
func TestTripOptionalClear_TwoUsersIsolated(t *testing.T) {
	s := newTestStore(t)
	seedTripAllOptionals(t, s, "userA", "t-iso")
	seedTripAllOptionals(t, s, "userB", "t-iso")
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/trips/t-iso", "userA", `{"alert_cooldown_minutes":null}`)
	a := optSnapshot(t, s, "userA", "t-iso")
	b := optSnapshot(t, s, "userB", "t-iso")
	if a["alert_cooldown_minutes"] != "<leer>" {
		t.Errorf("Nutzer A: Pause erwartet leer, bekommen %q", a["alert_cooldown_minutes"])
	}
	if b["alert_cooldown_minutes"] != "45" {
		t.Errorf("Nutzer B darf nicht beruehrt werden: erwartet 45, bekommen %q", b["alert_cooldown_minutes"])
	}
}

func seedPresetAlarm(t *testing.T, s *store.Store, user, id string) {
	t.Helper()
	p := model.ComparePreset{
		ID: id, Name: "Vergleich", UserID: user, LocationIDs: []string{"loc-1"},
		Schedule: "daily", Profil: "ALLGEMEIN", HourFrom: 6, HourTo: 18,
		Empfaenger:           []string{"a@example.com"},
		AlertCooldownMinutes: optIntPtr(45),
		AlertQuietFrom:       optStrPtr("22:00"),
		AlertQuietTo:         optStrPtr("06:00"),
	}
	if err := s.WithUser(user).SaveComparePresets([]model.ComparePreset{p}); err != nil {
		t.Fatalf("SaveComparePresets: %v", err)
	}
}

func loadOnePreset(t *testing.T, s *store.Store, user string) model.ComparePreset {
	t.Helper()
	ps, err := s.WithUser(user).LoadComparePresets()
	if err != nil || len(ps) != 1 {
		t.Fatalf("LoadComparePresets(%s): n=%d err=%v", user, len(ps), err)
	}
	return ps[0]
}

// Test 8 (Waechter, erwartet gruen): Compare-PUT null leert, fehlt behaelt.
func TestComparePresetOptionalClear_NullClearsAbsentKeeps(t *testing.T) {
	s := newTestStore(t)
	seedPresetAlarm(t, s, "userA", "cp-opt")
	r := briefingVergleichEtagRouter(s)

	putOK(t, r, "/api/compare/presets/cp-opt", "userA", `{"name":"Nur Name"}`)
	p := loadOnePreset(t, s, "userA")
	if p.AlertCooldownMinutes == nil || *p.AlertCooldownMinutes != 45 ||
		p.AlertQuietFrom == nil || *p.AlertQuietFrom != "22:00" ||
		p.AlertQuietTo == nil || *p.AlertQuietTo != "06:00" {
		t.Errorf("fehlende Keys muessen Bestand behalten: %+v", p)
	}

	putOK(t, r, "/api/compare/presets/cp-opt", "userA",
		`{"alert_cooldown_minutes":null,"alert_quiet_from":null,"alert_quiet_to":null}`)
	p = loadOnePreset(t, s, "userA")
	if p.AlertCooldownMinutes != nil {
		t.Errorf("alert_cooldown_minutes: erwartet nil, bekommen %d", *p.AlertCooldownMinutes)
	}
	if p.AlertQuietFrom != nil {
		t.Errorf("alert_quiet_from: erwartet nil, bekommen %q", *p.AlertQuietFrom)
	}
	if p.AlertQuietTo != nil {
		t.Errorf("alert_quiet_to: erwartet nil, bekommen %q", *p.AlertQuietTo)
	}
}

// Test 7b (AC-11): Compare, zwei Nutzer.
func TestComparePresetOptionalClear_TwoUsersIsolated(t *testing.T) {
	s := newTestStore(t)
	seedPresetAlarm(t, s, "userA", "cp-iso")
	seedPresetAlarm(t, s, "userB", "cp-iso")
	r := briefingVergleichEtagRouter(s)
	putOK(t, r, "/api/compare/presets/cp-iso", "userA", `{"alert_cooldown_minutes":null}`)
	a, b := loadOnePreset(t, s, "userA"), loadOnePreset(t, s, "userB")
	if a.AlertCooldownMinutes != nil {
		t.Errorf("Nutzer A: Pause erwartet nil")
	}
	if b.AlertCooldownMinutes == nil || *b.AlertCooldownMinutes != 45 {
		t.Errorf("Nutzer B darf nicht beruehrt werden: %v", b.AlertCooldownMinutes)
	}
}
