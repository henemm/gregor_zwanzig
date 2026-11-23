package handler

// Issue #3047 Runde 7, Paket p11 — Spec feat_3047_einstellung_gleich_mail_pruefkatalog.md
// „Nachtrag Runde 7", PO 2026-11-16 „Amtliche Warnungen Neuanlage" (loest #1258 AC-4 ab):
// neue Trips und Orts-Vergleiche bekommen Warnungen im Briefing UND als Alarm. Der
// Anlage-Handler schreibt beide Felder nach der gemeinsamen Regel (Briefing ODER Alarm an
// -> beides an) ausdruecklich; nur ein ausdrueckliches „beides aus" bleibt aus.
// Zwei Nutzer je Fall (Mandantentrennung).

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

type warnFall struct {
	name   string
	felder map[string]interface{}
	an     bool
}

var neuanlageWarnFaelle = []warnFall{
	{"ohne_felder", map[string]interface{}{}, true},
	{"bisherige_neuanlage_briefing_an_alarm_aus", map[string]interface{}{
		"official_alerts_enabled": true, "official_warnings": map[string]interface{}{"enabled": false}}, true},
	{"briefing_aus_alarm_an", map[string]interface{}{
		"official_alerts_enabled": false, "official_warnings": map[string]interface{}{"enabled": true}}, true},
	{"beides_aus_bleibt_aus", map[string]interface{}{
		"official_alerts_enabled": false, "official_warnings": map[string]interface{}{"enabled": false}}, false},
}

func neuanlagePost(t *testing.T, s *store.Store, pfad string, h http.HandlerFunc, uid string, body map[string]interface{}) {
	t.Helper()
	buf, _ := json.Marshal(body)
	r := chi.NewRouter()
	r.Post(pfad, h)
	req := addUserToContext(httptest.NewRequest(http.MethodPost, pfad, bytes.NewReader(buf)), uid)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("%s %s: erwartet 201, bekam %d: %s", uid, pfad, w.Code, w.Body.String())
	}
}

func pruefeWarnFelder(t *testing.T, wer string, briefing *bool, alarm *model.OfficialWarningsConfig, an bool) {
	t.Helper()
	if briefing == nil || *briefing != an {
		t.Errorf("%s: official_alerts_enabled nicht ausdruecklich %v: %v", wer, an, briefing)
	}
	if alarm == nil || alarm.Enabled != an {
		t.Errorf("%s: official_warnings.enabled nicht %v: %+v", wer, an, alarm)
	}
}

func TestNeuanlageTrip_AmtlicheWarnungenBeidesAn_ZweiNutzer(t *testing.T) {
	for _, f := range neuanlageWarnFaelle {
		t.Run(f.name, func(t *testing.T) {
			basis := t.TempDir()
			for _, uid := range []string{"nutzer-a-p11", "nutzer-b-p11"} {
				s := store.New(basis, uid)
				body := map[string]interface{}{"id": "trip-p11", "name": "Neu " + uid,
					"stages": []map[string]interface{}{{"id": "S1", "name": "D1", "date": "2026-11-20",
						"waypoints": []map[string]interface{}{{"id": "W1", "name": "P", "lat": 47.0, "lon": 11.0, "elevation_m": 500}}}}}
				for k, v := range f.felder {
					body[k] = v
				}
				neuanlagePost(t, s, "/api/trips", CreateTripHandler(s, ""), uid, body)
				trip, err := s.WithUser(uid).LoadTrip("trip-p11")
				if err != nil {
					t.Fatalf("%s LoadTrip: %v", uid, err)
				}
				pruefeWarnFelder(t, uid, trip.OfficialAlertsEnabled, trip.OfficialWarnings, f.an)
				if trip.Name != "Neu "+uid {
					t.Errorf("Mandantentrennung: %s liest %q", uid, trip.Name)
				}
			}
		})
	}
}

func TestNeuanlageVergleich_AmtlicheWarnungenBeidesAn_ZweiNutzer(t *testing.T) {
	for _, f := range neuanlageWarnFaelle {
		t.Run(f.name, func(t *testing.T) {
			basis := t.TempDir()
			for _, uid := range []string{"nutzer-a-p11", "nutzer-b-p11"} {
				s := store.New(basis, uid)
				body := map[string]interface{}{"name": "Neu " + uid, "schedule": "manual",
					"profil": "wandern", "location_ids": []string{"loc-a"}}
				for k, v := range f.felder {
					body[k] = v
				}
				neuanlagePost(t, s, "/api/compare/presets", CreateComparePresetHandler(s, ""), uid, body)
				presets, err := s.WithUser(uid).LoadComparePresets()
				if err != nil || len(presets) != 1 {
					t.Fatalf("%s: erwartet genau 1 Preset, bekam %d (%v)", uid, len(presets), err)
				}
				p := presets[0]
				pruefeWarnFelder(t, uid, p.OfficialAlertsEnabled, p.OfficialWarnings, f.an)
				if p.Name != "Neu "+uid {
					t.Errorf("Mandantentrennung: %s liest %q", uid, p.Name)
				}
			}
		})
	}
}
