package router

// TDD RED — Mengen-Quoten je Tier (S5, Issue #2482, Epic #2138).
//
// Spec: docs/specs/modules/mengen_quoten_je_tier.md — AC-10, AC-11, AC-13
// (Backend-Anteil: Grenzen im Profil).
//
// Echter Produktions-Router (router.New) mit AuthMiddleware und echten
// gz_session-Cookies — geprueft wird dort, wo die Verdrahtung WIRKT: ein im
// Router vergessenes Admin-Set oder eine nicht durchgereichte Ausnahme-Liste
// wird hier rot, auch wenn die Handler-Tests gruen sind.
//
// Profil-Vertrag (festgelegt in dieser RED-Phase):
//   GET /api/auth/profile -> "quota": {"trips": N|null, "compare_presets": N|null, "locations": N|null}
//   null = unbegrenzt (Admin aus GZ_ADMIN_USER_IDS oder Konto aus GZ_QUOTA_EXEMPT_USER_IDS).
//
// RED-Signal: Config.QuotaExemptUserIDs existiert nicht (Uebersetzungsfehler,
// auf das Paket router begrenzt); danach Verhalten (201 statt 409, fehlendes
// "quota" im Profil).

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// quoteTestRouter: "ops" ist Admin, "tester" steht auf der Ausnahme-Liste,
// "alice" und "bob" sind normale Konten. Alle vier haben Tarif free.
func quoteTestRouter(t *testing.T) (http.Handler, *store.Store, string) {
	t.Helper()
	ziel := neuesPythonZiel(t)

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = ziel.srv.URL
	cfg.UserID = "ops"
	cfg.AdminUserIDs = "ops"
	cfg.QuotaExemptUserIDs = "tester"

	s := store.New(cfg.DataDir, cfg.UserID)
	for _, id := range []string{"alice", "bob", "ops", "tester"} {
		if err := s.SaveUser(model.User{ID: id, Tier: "free", CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
		if err := s.AddSession(id, sessionIDFor(id)); err != nil {
			t.Fatalf("AddSession %s: %v", id, err)
		}
	}

	wa, err := webauthn.New(&webauthn.Config{
		RPID:          cfg.WebAuthnRPID,
		RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins:     []string{"http://localhost:5173"},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := New(Deps{
		Config:             cfg,
		Store:              s,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})
	return r, s, cfg.SessionSecret
}

func quoteReq(t *testing.T, r http.Handler, secret, method, pfad, body, uid string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, pfad, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(sessionCookieFor(uid, secret))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func quoteTripJSON(id string) string {
	return `{"id":"` + id + `","name":"Trip ` + id + `","stages":[{"id":"S1","name":"Tag 1","date":"2026-05-01","waypoints":[{"id":"W1","name":"Start","lat":47.0,"lon":11.0,"elevation_m":500}]}]}`
}

func quotePresetJSON(name string) string {
	return `{"name":"` + name + `","location_ids":["loc-1","loc-2"],"schedule":"daily","profil":"SUMMER_TREKKING","hour_from":6,"hour_to":18}`
}

func quoteSeedRouteTrips(t *testing.T, s *store.Store, uid string, n int) {
	t.Helper()
	for i := 0; i < n; i++ {
		trip := model.Trip{ID: fmt.Sprintf("seed-%d", i), Name: "Seed",
			Stages: []model.Stage{{ID: "S1", Name: "D1", Date: "2026-05-01",
				Waypoints: []model.Waypoint{{ID: "W1", Name: "P", Lat: 47.0, Lon: 11.0, ElevationM: 500}}}}}
		if err := s.WithUser(uid).SaveTrip(&trip); err != nil {
			t.Fatalf("SaveTrip: %v", err)
		}
	}
}

func quoteSeedRoutePresets(t *testing.T, s *store.Store, uid string, n int) {
	t.Helper()
	for i := 0; i < n; i++ {
		p := model.ComparePreset{ID: fmt.Sprintf("seed-cp-%d", i), UserID: uid, Name: "Seed",
			LocationIDs: []string{"loc-a", "loc-b"}, Schedule: "daily", Profil: "SUMMER_TREKKING",
			HourFrom: 6, HourTo: 18, ForecastHours: 48, CreatedAt: time.Now().UTC()}
		if err := s.WithUser(uid).SaveComparePreset(p); err != nil {
			t.Fatalf("SaveComparePreset: %v", err)
		}
	}
}

func quoteErrorCode(w *httptest.ResponseRecorder) string {
	var b struct {
		Error string `json:"error"`
	}
	json.Unmarshal(w.Body.Bytes(), &b)
	return b.Error
}

// AC-10: Admin und Ausnahme-Konto werden ueber der Free-Grenze nie
// abgelehnt; ein normales Konto mit gleichem Tarif im selben Lauf schon.
func TestMengenQuoteRoute_AC10_AdminUndAusnahmeUnbegrenzt(t *testing.T) {
	r, _, secret := quoteTestRouter(t)

	for _, uid := range []string{"ops", "tester"} {
		for i := 0; i < 4; i++ {
			if w := quoteReq(t, r, secret, "POST", "/api/trips", quoteTripJSON(fmt.Sprintf("%s-trip-%d", uid, i)), uid); w.Code != http.StatusCreated {
				t.Fatalf("%s Trip %d: erwartet 201, bekommen %d: %s", uid, i+1, w.Code, w.Body.String())
			}
		}
		for i := 0; i < 3; i++ {
			if w := quoteReq(t, r, secret, "POST", "/api/compare/presets", quotePresetJSON(fmt.Sprintf("V %d", i)), uid); w.Code != http.StatusCreated {
				t.Fatalf("%s Ortsvergleich %d: erwartet 201, bekommen %d: %s", uid, i+1, w.Code, w.Body.String())
			}
		}
		for i := 0; i < 11; i++ {
			body := fmt.Sprintf(`{"name":"%s Ort %d","lat":46.%d,"lon":10.5}`, uid, i, i+1)
			if w := quoteReq(t, r, secret, "POST", "/api/locations", body, uid); w.Code != http.StatusCreated {
				t.Fatalf("%s Ort %d: erwartet 201, bekommen %d: %s", uid, i+1, w.Code, w.Body.String())
			}
		}
	}

	// Gegenprobe im selben Lauf: normales Konto, gleicher Tarif.
	for i := 0; i < 3; i++ {
		if w := quoteReq(t, r, secret, "POST", "/api/trips", quoteTripJSON(fmt.Sprintf("alice-trip-%d", i)), "alice"); w.Code != http.StatusCreated {
			t.Fatalf("alice Trip %d: erwartet 201, bekommen %d", i+1, w.Code)
		}
	}
	w := quoteReq(t, r, secret, "POST", "/api/trips", quoteTripJSON("alice-trip-3"), "alice")
	if w.Code != http.StatusConflict || quoteErrorCode(w) != "quota_exceeded" {
		t.Fatalf("alice 4. Trip: erwartet 409 quota_exceeded, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// AC-10: Die Ausnahme-Liste verleiht KEINE Admin-Rechte.
func TestMengenQuoteRoute_AC10_AusnahmeIstKeinAdmin(t *testing.T) {
	r, _, secret := quoteTestRouter(t)

	if w := trigger(t, r, secret, "POST", "/api/scheduler/trip-reports", "tester"); w.Code != http.StatusForbidden {
		t.Errorf("Ausnahme-Konto auf Admin-Route: erwartet 403, bekommen %d", w.Code)
	}
	w := quoteReq(t, r, secret, "GET", "/api/auth/profile", "", "tester")
	var p struct {
		Role string `json:"role"`
	}
	json.Unmarshal(w.Body.Bytes(), &p)
	if p.Role != "user" {
		t.Errorf("Ausnahme-Konto: Rolle erwartet user, bekommen %q", p.Role)
	}
}

// AC-11: POST /api/briefings erbt die Pruefung — fuer beide Arten.
func TestMengenQuoteRoute_AC11_BriefingsAnlegenAnDerGrenze(t *testing.T) {
	r, s, secret := quoteTestRouter(t)
	quoteSeedRouteTrips(t, s, "alice", 3)
	quoteSeedRoutePresets(t, s, "alice", 2)

	w := quoteReq(t, r, secret, "POST", "/api/briefings", string(minimalRouteCreateBody("briefing-trip", "Neu")), "alice")
	if w.Code != http.StatusConflict || quoteErrorCode(w) != "quota_exceeded" {
		t.Errorf("Briefing kind=route an der Grenze: erwartet 409 quota_exceeded, bekommen %d: %s", w.Code, w.Body.String())
	}
	if trips, _ := s.WithUser("alice").LoadTrips(); len(trips) != 3 {
		t.Errorf("es darf kein Trip entstehen, Bestand=%d", len(trips))
	}

	w = quoteReq(t, r, secret, "POST", "/api/briefings", string(minimalVergleichCreateBody("Neu")), "alice")
	if w.Code != http.StatusConflict || quoteErrorCode(w) != "quota_exceeded" {
		t.Errorf("Briefing kind=vergleich an der Grenze: erwartet 409 quota_exceeded, bekommen %d: %s", w.Code, w.Body.String())
	}
	if ps, _ := s.WithUser("alice").LoadComparePresets(); len(ps) != 2 {
		t.Errorf("es darf kein Ortsvergleich entstehen, Bestand=%d", len(ps))
	}
}

// AC-13 (Backend): Profil liefert die Grenzen; Admin/Ausnahme: null.
func TestMengenQuoteRoute_AC13_ProfilLiefertGrenzen(t *testing.T) {
	r, _, secret := quoteTestRouter(t)

	type quota struct {
		Trips          *int `json:"trips"`
		ComparePresets *int `json:"compare_presets"`
		Locations      *int `json:"locations"`
	}
	lade := func(uid string) (quota, map[string]json.RawMessage) {
		w := quoteReq(t, r, secret, "GET", "/api/auth/profile", "", uid)
		if w.Code != http.StatusOK {
			t.Fatalf("Profil %s: erwartet 200, bekommen %d", uid, w.Code)
		}
		var roh map[string]json.RawMessage
		json.Unmarshal(w.Body.Bytes(), &roh)
		var q quota
		if raw, ok := roh["quota"]; ok {
			json.Unmarshal(raw, &q)
		}
		return q, roh
	}

	q, roh := lade("alice")
	if _, ok := roh["quota"]; !ok {
		t.Fatalf("Profil muss das Feld quota tragen: %v", roh)
	}
	if q.Trips == nil || *q.Trips != 3 || q.ComparePresets == nil || *q.ComparePresets != 2 || q.Locations == nil || *q.Locations != 10 {
		t.Errorf("alice (free): erwartet 3/2/10, bekommen %+v", q)
	}

	for _, uid := range []string{"ops", "tester"} {
		q, roh := lade(uid)
		var inner map[string]json.RawMessage
		json.Unmarshal(roh["quota"], &inner)
		for _, k := range []string{"trips", "compare_presets", "locations"} {
			if string(inner[k]) != "null" {
				t.Errorf("%s: quota.%s muss null (unbegrenzt) sein, bekommen %s", uid, k, inner[k])
			}
		}
		_ = q
	}
}
