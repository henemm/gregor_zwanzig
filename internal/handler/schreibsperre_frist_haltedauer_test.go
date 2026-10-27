package handler

import (
	"bytes"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

// #2158 Fix-Loop 4 (F-9, F-12, F-13): je Stelle von lockBriefingOr503 ein
// 503-Lauf (Sperre von aussen, kurze Frist) und ein Haltedauer-Lauf (Sperre
// ist ZUM ZEITPUNKT DER ANTWORT noch belegt -- die Antwort entsteht am Ende
// des Lese-Aendern-Schreiben-Zyklus, vor dem defer-Unlock).

type sperrStelle struct {
	name                       string
	id                         string
	seed                       func(t *testing.T, s *store.Store)
	h                          func(s *store.Store) http.HandlerFunc
	method, pattern, url, body string
	wantCode                   int
}

func p2158Stellen() []sperrStelle {
	const u = "u1"
	seedPreset := func(t *testing.T, s *store.Store) {
		t.Helper()
		if err := s.WithUser(u).SaveComparePreset(comparePresetPutBodyStruct("cp1", u)); err != nil {
			t.Fatal(err)
		}
	}
	seedT := func(t *testing.T, s *store.Store) { seedTrip(t, s.WithUser(u), "t1", "Alt") }
	none := func(t *testing.T, s *store.Store) {}
	newTripBody := `{"id":"t-neu","name":"Neu","stages":[{"id":"S1","name":"D1","date":"2026-05-01","waypoints":[{"id":"W1","name":"P","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`
	return []sperrStelle{
		{"trip.go_Get", "t1", seedT, TripHandler, "GET", "/api/trips/{id}", "/api/trips/t1", "", 200},
		{"trip.go_Create", "t-neu", none, CreateTripHandler, "POST", "/api/trips", "/api/trips", newTripBody, 201},
		{"trip.go_Update", "t1", seedT, UpdateTripHandler, "PUT", "/api/trips/{id}", "/api/trips/t1", `{"name":"Neu"}`, 200},
		{"trip.go_State", "t1", seedT, UpdateTripStateHandler, "PATCH", "/api/trips/{id}/state", "/api/trips/t1/state", `{"paused":true}`, 200},
		{"trip.go_ConfirmWaypoint", "t1", seedT, ConfirmWaypointHandler, "PATCH", "/api/trips/{id}/waypoints/{waypointId}/confirm", "/api/trips/t1/waypoints/W1/confirm", `{"confirmed":true}`, 200},
		{"trip.go_Delete", "t1", seedT, DeleteTripHandler, "DELETE", "/api/trips/{id}", "/api/trips/t1", "", 204},
		{"compare_preset.go_Update", "cp1", seedPreset, UpdateComparePresetHandler, "PUT", "/api/compare/presets/{id}", "/api/compare/presets/cp1", comparePresetPutBody("Neu"), 200},
		{"compare_preset.go_Delete", "cp1", seedPreset, DeleteComparePresetHandler, "DELETE", "/api/compare/presets/{id}", "/api/compare/presets/cp1", "", 204},
		{"compare_preset.go_State", "cp1", seedPreset, UpdateComparePresetStateHandler, "PATCH", "/api/compare/presets/{id}/state", "/api/compare/presets/cp1/state", `{"archived":true}`, 200},
		{"compare_preset.go_Get", "cp1", seedPreset, GetComparePresetHandler, "GET", "/api/compare/presets/{id}", "/api/compare/presets/cp1", "", 200},
		{"briefing_subscription.go_GetRoute", "t1", seedT, GetBriefingHandler, "GET", "/api/briefings/{id}", "/api/briefings/t1?kind=route", "", 200},
		{"briefing_subscription.go_GetVergleich", "cp1", seedPreset, GetBriefingHandler, "GET", "/api/briefings/{id}", "/api/briefings/cp1?kind=vergleich", "", 200},
		{"briefing_subscription.go_UpdateVergleich", "cp1", seedPreset, UpdateBriefingHandler, "PUT", "/api/briefings/{id}", "/api/briefings/cp1?kind=vergleich", comparePresetPutBody("Neu"), 200},
		{"weather_config.go_Get", "t1", seedT, GetTripWeatherConfigHandler, "GET", "/api/trips/{id}/weather-config", "/api/trips/t1/weather-config", "", 200},
		{"weather_config.go_Put", "t1", seedT, PutTripWeatherConfigHandler, "PUT", "/api/trips/{id}/weather-config", "/api/trips/t1/weather-config", `{"theme":"kompakt"}`, 200},
	}
}

// p2158Fremdsperre haelt den flock auf briefings/<id>.json.lock von aussen.
func p2158Fremdsperre(t *testing.T, s *store.Store, u, id string) (release func()) {
	t.Helper()
	dir := s.WithUser(u).BriefingsDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	f, err := os.OpenFile(filepath.Join(dir, id+".json.lock"), os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		t.Fatal(err)
	}
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX); err != nil {
		t.Fatal(err)
	}
	return func() { _ = syscall.Flock(int(f.Fd()), syscall.LOCK_UN); f.Close() }
}

// F-9: Fristablauf => 503 + Retry-After: 5, kein Inhalt, Datei byte-identisch.
func TestSchreibsperre_FristablaufJeStelle_503OhneSchreiben(t *testing.T) {
	const u = "u1"
	for _, tc := range p2158Stellen() {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			s := store.New(t.TempDir(), u)
			tc.seed(t, s)
			datei := filepath.Join(s.WithUser(u).BriefingsDir(), tc.id+".json")
			vorher, _ := os.ReadFile(datei) // fehlt bei Create: nil
			release := p2158Fremdsperre(t, s, u, tc.id)
			defer release()
			defer store.SetBriefingLockTimeout(150 * time.Millisecond)()

			w := p2158Do(tc.h(s), tc.method, tc.pattern, tc.url, tc.body, u)

			if w.Code != 503 {
				t.Fatalf("erwartet 503, bekam %d (%s)", w.Code, w.Body.String())
			}
			if got := w.Header().Get("Retry-After"); got != "5" {
				t.Fatalf("Retry-After=%q, erwartet \"5\"", got)
			}
			if !strings.Contains(w.Body.String(), `"busy"`) || strings.Contains(w.Body.String(), `"`+tc.id+`"`) {
				t.Fatalf("Rumpf ist keine reine Busy-Antwort: %s", w.Body.String())
			}
			if w.Header().Get("ETag") != "" {
				t.Fatalf("503 traegt einen ETag")
			}
			nachher, _ := os.ReadFile(datei)
			if !bytes.Equal(vorher, nachher) {
				t.Fatalf("Datei trotz 503 veraendert")
			}
		})
	}
}

// F-9 (Compare-Create): die Kennung entsteht im Handler, die Sperre laesst
// sich nicht vorab von aussen halten. Stattdessen wird der NICHT-Timeout-
// Fehlerzweig von lockBriefingOr503 ausgeloest (briefings ist eine Datei =>
// Sperrdatei nicht anlegbar => 500). `if !okB { return }` muss danach sofort
// zurueckkehren: genau EINE Fehlerantwort. Ohne return liefe der Handler
// weiter und haengte eine zweite JSON-Antwort an.
func TestSchreibsperre_CreateComparePreset_SperrfehlerBrichtAb(t *testing.T) {
	const u = "u1"
	dir := t.TempDir()
	s := store.New(dir, u)
	if err := os.MkdirAll(filepath.Join(dir, "users", u), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(s.WithUser(u).BriefingsDir(), []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	w := p2158Do(CreateComparePresetHandler(s), "POST", "/api/compare/presets", "/api/compare/presets",
		comparePresetPutBody("Neu"), u)
	if w.Code != 500 {
		t.Fatalf("erwartet 500, bekam %d (%s)", w.Code, w.Body.String())
	}
	if got := strings.TrimSpace(w.Body.String()); got != `{"error":"store_error"}` {
		t.Fatalf("erwartet genau EINE Fehlerantwort, bekam: %s", got)
	}
}

// p2158Sonde: ResponseWriter, der bei jedem Schreiben prueft, ob der flock auf
// einer Sperrdatei unter briefings/ NOCH belegt ist. Die Antwort entsteht im
// Handler vor dem defer-Unlock; ist die Sperre dann frei, wurde sie zu frueh
// (vor Ende des Zyklus) freigegeben.
type p2158Sonde struct {
	*httptest.ResponseRecorder
	dir     string
	t       *testing.T
	schreib int
}

func (p *p2158Sonde) pruefe() {
	p.schreib++
	matches, _ := filepath.Glob(filepath.Join(p.dir, "*.lock"))
	held := 0
	for _, m := range matches {
		f, err := os.OpenFile(m, os.O_RDWR, 0o600)
		if err != nil {
			continue
		}
		err = syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB)
		if err == nil {
			_ = syscall.Flock(int(f.Fd()), syscall.LOCK_UN)
		} else if errors.Is(err, syscall.EWOULDBLOCK) {
			held++
		}
		f.Close()
	}
	if held == 0 {
		p.t.Errorf("Sperre bei der Antwort schon freigegeben (%d Sperrdateien, keine belegt) -- Haltedauer verkuerzt", len(matches))
	}
}
func (p *p2158Sonde) WriteHeader(c int)           { p.pruefe(); p.ResponseRecorder.WriteHeader(c) }
func (p *p2158Sonde) Write(b []byte) (int, error) { p.pruefe(); return p.ResponseRecorder.Write(b) }

// F-12: die Sperre haelt bis zum Ende des Zyklus (defer), nicht nur zum Erwerb.
func TestSchreibsperre_HaltedauerJeStelle_BisZurAntwortBelegt(t *testing.T) {
	const u = "u1"
	for _, tc := range p2158Stellen() {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			s := store.New(t.TempDir(), u)
			tc.seed(t, s)
			p := &p2158Sonde{ResponseRecorder: httptest.NewRecorder(), dir: s.WithUser(u).BriefingsDir(), t: t}
			p2158DoW(p, tc.h(s), tc.method, tc.pattern, tc.url, tc.body, u)
			if p.Code != tc.wantCode {
				t.Fatalf("%s %s: %d (%s)", tc.method, tc.url, p.Code, p.Body.String())
			}
			if p.schreib == 0 {
				t.Fatal("Sonde hat keine Antwort gesehen")
			}
		})
	}
}

// F-12 (Compare-Create): gleiche Sonde, Kennung entsteht im Handler.
func TestSchreibsperre_HaltedauerCompareCreate_BisZurAntwortBelegt(t *testing.T) {
	const u = "u1"
	s := store.New(t.TempDir(), u)
	p := &p2158Sonde{ResponseRecorder: httptest.NewRecorder(), dir: s.WithUser(u).BriefingsDir(), t: t}
	p2158DoW(p, CreateComparePresetHandler(s), "POST", "/api/compare/presets", "/api/compare/presets", comparePresetPutBody("Neu"), u)
	if p.Code != 201 || p.schreib == 0 {
		t.Fatalf("POST: %d, Schreibvorgaenge=%d (%s)", p.Code, p.schreib, p.Body.String())
	}
}

// F-13: Retry-After exakt "5"; Nicht-Timeout-Fehler => 500 ohne Retry-After.
func TestSchreibsperre_Hilfsfunktion_503Wert500Zweig(t *testing.T) {
	const u = "u1"
	s := store.New(t.TempDir(), u).WithUser(u)

	release := p2158Fremdsperre(t, s, u, "x1")
	defer release()
	defer store.SetBriefingLockTimeout(100 * time.Millisecond)()
	w := httptest.NewRecorder()
	if _, ok := lockBriefingOr503(w, s, "x1"); ok || w.Code != 503 || w.Header().Get("Retry-After") != "5" {
		t.Fatalf("Timeout: ok=%v code=%d retry=%q", ok, w.Code, w.Header().Get("Retry-After"))
	}

	w = httptest.NewRecorder()
	if _, ok := lockBriefingOr503(w, s, "../x"); ok || w.Code != 500 || w.Header().Get("Retry-After") != "" {
		t.Fatalf("Nicht-Timeout: ok=%v code=%d retry=%q", ok, w.Code, w.Header().Get("Retry-After"))
	}
}

// F-13: ungueltige Id => Fehler und KEINE Sperrdatei ausserhalb briefings/;
// LockBriefing faellt dann auf den Prozess-Mutex zurueck (schliesst weiter aus).
func TestBriefingLock_UngueltigeId_KeinPfadAusbruch_MutexFallback(t *testing.T) {
	const u = "u1"
	dir := t.TempDir()
	s := store.New(dir, u).WithUser(u)
	if err := os.MkdirAll(s.BriefingsDir(), 0o755); err != nil {
		t.Fatal(err)
	}
	if unlock, err := s.LockBriefingErr("../evil"); err == nil {
		unlock()
		t.Fatal("ungueltige Id wurde akzeptiert")
	}
	if _, err := os.Stat(filepath.Join(dir, "users", u, "evil.json.lock")); err == nil {
		t.Fatal("Sperrdatei ausserhalb briefings/ angelegt")
	}

	unlock := s.LockBriefing("../evil") // Fallback: nur Mutex
	got := make(chan struct{})
	go func() { u2 := s.LockBriefing("../evil"); close(got); u2() }()
	select {
	case <-got:
		unlock()
		t.Fatal("zweiter LockBriefing lief trotz gehaltener Sperre durch -- Mutex-Fallback fehlt")
	case <-time.After(200 * time.Millisecond):
	}
	unlock()
	select {
	case <-got:
	case <-time.After(5 * time.Second):
		t.Fatal("nach Freigabe nicht fortgesetzt")
	}
}
