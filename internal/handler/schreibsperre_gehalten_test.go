package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// p2158WartetAufSperre haelt die Sperre von aussen (unlock), startet fn und
// beweist: fn kommt NICHT fertig, solange die Sperre gehalten wird, und
// laeuft nach der Freigabe durch. Wer die Sperre im Handler weglaesst, wird
// hier sofort fertig -> Test rot. (Das "nicht fertig" ist kein Sleep-Raten:
// bei vorhandener Sperre ist fn strukturell blockiert.)
func p2158WartetAufSperre(t *testing.T, unlock func(), fn func()) {
	t.Helper()
	done := make(chan struct{})
	go func() { fn(); close(done) }()
	select {
	case <-done:
		unlock()
		t.Fatalf("Handler lief trotz gehaltener Sperre durch -- Sperre fehlt")
	case <-time.After(300 * time.Millisecond):
	}
	unlock()
	select {
	case <-done:
	case <-time.After(10 * time.Second):
		t.Fatalf("Handler nach Freigabe nicht fertig -- Verklemmung?")
	}
}

// F-1 (#2158): PUT auf einen Ort nimmt die Orts-Sperre.
func TestLocationLock_UpdatePut_WartetAufOrtsSperre(t *testing.T) {
	s := store.New(t.TempDir(), "u1")
	if err := s.SaveLocation(model.Location{ID: "o1", Name: "Alt", Lat: 47, Lon: 11}); err != nil {
		t.Fatal(err)
	}
	var code int
	p2158WartetAufSperre(t, s.WithUser("u1").LockLocation("o1"), func() {
		w := p2158Do(UpdateLocationHandler(s), "PUT", "/api/locations/{id}", "/api/locations/o1",
			`{"name":"Neu","lat":47,"lon":11}`, "u1")
		code = w.Code
	})
	if code != 200 {
		t.Fatalf("PUT: %d", code)
	}
	if l, _ := s.WithUser("u1").LoadLocation("o1"); l == nil || l.Name != "Neu" {
		t.Fatalf("PUT nicht wirksam: %+v", l)
	}
}

// F-1 (#2158): DELETE auf einen Ort nimmt die Orts-Sperre; ein PATCH danach
// sieht 404 (Ort nicht wiederauferstanden).
func TestLocationLock_Delete_WartetAufOrtsSperre(t *testing.T) {
	s := store.New(t.TempDir(), "u1")
	if err := s.SaveLocation(model.Location{ID: "o1", Name: "O", Lat: 47, Lon: 11}); err != nil {
		t.Fatal(err)
	}
	var code int
	p2158WartetAufSperre(t, s.WithUser("u1").LockLocation("o1"), func() {
		w := p2158Do(DeleteLocationHandler(s), "DELETE", "/api/locations/{id}", "/api/locations/o1", "", "u1")
		code = w.Code
	})
	if code != 204 {
		t.Fatalf("DELETE: %d", code)
	}
	if l, _ := s.WithUser("u1").LoadLocation("o1"); l != nil {
		t.Fatalf("Ort nicht geloescht: %+v", l)
	}
	w := p2158Do(PatchLocationHandler(s), "PATCH", "/api/locations/{id}", "/api/locations/o1", `{"group_id":"g"}`, "u1")
	if w.Code != 404 {
		t.Fatalf("PATCH nach DELETE: %d (Ort wiederauferstanden?)", w.Code)
	}
}

// F-2 (#2158): DELETE einer Gruppe haelt die aeussere Gruppen-Sperre
// (schuetzt gegen parallele Create/Update ANDERER Gruppen).
func TestGroupLock_DeleteHandler_WartetAufGruppenSperre(t *testing.T) {
	s := store.New(t.TempDir(), "u1")
	su := s.WithUser("u1")
	if err := su.SaveGroup(model.Group{ID: "g1", Name: "G1", Order: 0}); err != nil {
		t.Fatal(err)
	}
	if err := su.SaveGroup(model.Group{ID: "g2", Name: "G2", Order: 1}); err != nil {
		t.Fatal(err)
	}
	var code int
	p2158WartetAufSperre(t, su.LockGroups(), func() {
		w := p2158Do(DeleteGroupHandler(s), "DELETE", "/api/groups/{id}", "/api/groups/g1", "", "u1")
		code = w.Code
	})
	if code != 204 {
		t.Fatalf("DELETE: %d", code)
	}
	gs, _ := su.LoadGroups()
	if len(gs) != 1 || gs[0].ID != "g2" {
		t.Fatalf("Endstand: %+v", gs)
	}
}

// F-8 (#2158): Jede Stelle, die lockBriefingOr503 aufruft, muss die
// Briefing-Sperre WIRKLICH nehmen -- auch die Lese-Handler (Stempel und Rumpf
// muessen zusammengehoeren). Je Zeile ein eigener Test: wer genau diese Stelle
// auf einen Leer-Unlock umbaut, macht genau diesen Subtest rot.
func TestBriefingLock_HandlerStellen_WartenAufBriefingSperre(t *testing.T) {
	const u = "u1"
	seedPreset := func(t *testing.T, s *store.Store, id string) {
		t.Helper()
		if err := s.WithUser(u).SaveComparePreset(comparePresetPutBodyStruct(id, u)); err != nil {
			t.Fatal(err)
		}
	}
	seedT := func(t *testing.T, s *store.Store, id string) { seedTrip(t, s.WithUser(u), id, "Alt") }
	presetName := func(t *testing.T, s *store.Store, id string) string {
		t.Helper()
		p, _ := s.WithUser(u).LoadComparePreset(id)
		if p == nil {
			t.Fatalf("Preset %s fehlt", id)
		}
		return p.Name
	}
	tripOf := func(t *testing.T, s *store.Store, id string) *model.Trip {
		t.Helper()
		tr, _ := s.WithUser(u).LoadTrip(id)
		if tr == nil {
			t.Fatalf("Trip %s fehlt", id)
		}
		return tr
	}

	cases := []struct {
		name                       string
		id                         string
		seed                       func(t *testing.T, s *store.Store)
		h                          func(s *store.Store) http.HandlerFunc
		method, pattern, url, body string
		wantCode                   int
		check                      func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder)
	}{
		{"trip.go_Get", "t1", func(t *testing.T, s *store.Store) { seedT(t, s, "t1") }, TripHandler,
			"GET", "/api/trips/{id}", "/api/trips/t1", "", 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if !strings.Contains(w.Body.String(), `"t1"`) || w.Header().Get("ETag") == "" {
					t.Fatalf("GET ohne Rumpf/ETag: %s", w.Body.String())
				}
			}},
		{"trip.go_Create", "t-neu", func(t *testing.T, s *store.Store) {}, CreateTripHandler,
			"POST", "/api/trips", "/api/trips",
			`{"id":"t-neu","name":"Neu","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`, 201,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if tripOf(t, s, "t-neu").Name != "Neu" {
					t.Fatal("Trip nicht angelegt")
				}
			}},
		{"trip.go_State", "t1", func(t *testing.T, s *store.Store) { seedT(t, s, "t1") }, UpdateTripStateHandler,
			"PATCH", "/api/trips/{id}/state", "/api/trips/t1/state", `{"paused":true}`, 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if tripOf(t, s, "t1").PausedAt == nil {
					t.Fatal("Pause nicht gesetzt")
				}
			}},
		{"trip.go_ConfirmWaypoint", "t1", func(t *testing.T, s *store.Store) { seedT(t, s, "t1") }, ConfirmWaypointHandler,
			"PATCH", "/api/trips/{id}/waypoints/{waypointId}/confirm", "/api/trips/t1/waypoints/W1/confirm", `{"confirmed":true}`, 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				wp := tripOf(t, s, "t1").Stages[0].Waypoints[0]
				if wp.Confirmed == nil || !*wp.Confirmed {
					t.Fatal("Wegpunkt nicht bestaetigt")
				}
			}},
		{"compare_preset.go_Update", "cp1", func(t *testing.T, s *store.Store) { seedPreset(t, s, "cp1") }, UpdateComparePresetHandler,
			"PUT", "/api/compare/presets/{id}", "/api/compare/presets/cp1", comparePresetPutBody("Neu"), 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if presetName(t, s, "cp1") != "Neu" {
					t.Fatal("PUT nicht wirksam")
				}
			}},
		{"compare_preset.go_Get", "cp1", func(t *testing.T, s *store.Store) { seedPreset(t, s, "cp1") }, GetComparePresetHandler,
			"GET", "/api/compare/presets/{id}", "/api/compare/presets/cp1", "", 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if !strings.Contains(w.Body.String(), `"cp1"`) || w.Header().Get("ETag") == "" {
					t.Fatalf("GET ohne Rumpf/ETag: %s", w.Body.String())
				}
			}},
		{"briefing_subscription.go_GetRoute", "t1", func(t *testing.T, s *store.Store) { seedT(t, s, "t1") }, GetBriefingHandler,
			"GET", "/api/briefings/{id}", "/api/briefings/t1?kind=route", "", 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if !strings.Contains(w.Body.String(), `"t1"`) || w.Header().Get("ETag") == "" {
					t.Fatalf("GET ohne Rumpf/ETag: %s", w.Body.String())
				}
			}},
		{"briefing_subscription.go_GetVergleich", "cp1", func(t *testing.T, s *store.Store) { seedPreset(t, s, "cp1") }, GetBriefingHandler,
			"GET", "/api/briefings/{id}", "/api/briefings/cp1?kind=vergleich", "", 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if !strings.Contains(w.Body.String(), `"cp1"`) || w.Header().Get("ETag") == "" {
					t.Fatalf("GET ohne Rumpf/ETag: %s", w.Body.String())
				}
			}},
		{"briefing_subscription.go_UpdateVergleich", "cp1", func(t *testing.T, s *store.Store) { seedPreset(t, s, "cp1") }, UpdateBriefingHandler,
			"PUT", "/api/briefings/{id}", "/api/briefings/cp1?kind=vergleich", comparePresetPutBody("Neu"), 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if presetName(t, s, "cp1") != "Neu" {
					t.Fatal("PUT nicht wirksam")
				}
			}},
		{"weather_config.go_Get", "t1", func(t *testing.T, s *store.Store) { seedT(t, s, "t1") }, GetTripWeatherConfigHandler,
			"GET", "/api/trips/{id}/weather-config", "/api/trips/t1/weather-config", "", 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if w.Header().Get("ETag") == "" {
					t.Fatal("GET ohne ETag")
				}
			}},
		{"weather_config.go_Put", "t1", func(t *testing.T, s *store.Store) { seedT(t, s, "t1") }, PutTripWeatherConfigHandler,
			"PUT", "/api/trips/{id}/weather-config", "/api/trips/t1/weather-config", `{"theme":"kompakt"}`, 200,
			func(t *testing.T, s *store.Store, w *httptest.ResponseRecorder) {
				if tripOf(t, s, "t1").DisplayConfig["theme"] != "kompakt" {
					t.Fatal("PUT nicht wirksam")
				}
			}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			s := store.New(t.TempDir(), u)
			tc.seed(t, s)
			var w *httptest.ResponseRecorder
			p2158WartetAufSperre(t, s.WithUser(u).LockBriefing(tc.id), func() {
				w = p2158Do(tc.h(s), tc.method, tc.pattern, tc.url, tc.body, u)
			})
			if w.Code != tc.wantCode {
				t.Fatalf("%s %s: %d (%s)", tc.method, tc.url, w.Code, w.Body.String())
			}
			tc.check(t, s, w)
		})
	}
}

// F-8 (#2158): Compare-Create erzeugt die Kennung erst im Handler -- von aussen
// laesst sich die Sperre deshalb nicht vorab halten. Beweis stattdessen an der
// Wirkung: nur wer die Briefing-Sperre nimmt, legt die Sperrdatei
// briefings/<id>.json.lock an (ADR-0083-Pfad) -- die bleibt nach Freigabe liegen.
func TestBriefingLock_CreateComparePreset_LegtSperrdateiAn(t *testing.T) {
	const u = "u1"
	s := store.New(t.TempDir(), u)
	w := p2158Do(CreateComparePresetHandler(s), "POST", "/api/compare/presets", "/api/compare/presets",
		comparePresetPutBody("Neu"), u)
	if w.Code != 201 {
		t.Fatalf("POST: %d (%s)", w.Code, w.Body.String())
	}
	var out struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil || out.ID == "" {
		t.Fatalf("keine Kennung in der Antwort: %v %s", err, w.Body.String())
	}
	lock := filepath.Join(s.WithUser(u).BriefingsDir(), out.ID+".json.lock")
	if _, err := os.Stat(lock); err != nil {
		t.Fatalf("Create hat die Briefing-Sperre nicht genommen (keine Sperrdatei %s): %v", lock, err)
	}
}
