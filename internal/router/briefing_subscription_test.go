package router

// TDD RED — Issue #1250 Scheibe 6: API-Konsolidierung (/api/briefings*).
//
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md § AC-20..AC-22
// Context: docs/context/feat-1250-s6-api-konsolidierung.md
//
// Diese Tests laufen gegen den ECHTEN Produktions-Router (router.New(...),
// dieselbe Verdrahtung wie cmd/server/main.go) mit seinen AKTUELLEN Routen —
// OHNE neue /api/briefings*-Registrierung. Solange internal/router/router.go
// keine /api/briefings*-Routen kennt, antwortet chi mit 404 (Route nicht
// registriert) fuer JEDEN Request gegen diese Pfade. Das ist das RED-Signal:
// Tests 1-7 (und ihre Unterpunkte) erwarten NICHT 404, sondern das jeweils
// fachlich korrekte Ergebnis (200/201/400/404-aus-Cross-User-Gruenden) und
// scheitern deshalb heute. Test 8 ist der Regressions-Guard (AC-20) und ist
// schon HEUTE gruen — er beweist nur, dass die Delegate-Invariante (Alt-Endpoints
// bleiben unveraendert) durch S6 nicht verletzt werden darf.
//
// Kein Mock: echter store.New(...) auf t.TempDir(), echte httptest-Requests
// gegen den vollstaendig verdrahteten chi-Router inkl. AuthMiddleware (gueltiges
// gz_session-Cookie per authmw.SignSession, analog
// legacy_subscription_routes_removed_test.go).

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// =============================================================================
// Helpers
// =============================================================================

// newBriefingTestRouter baut den echten Produktions-Router (identische Deps-
// Verdrahtung wie cmd/server/main.go) und gibt zusaetzlich den zugrunde
// liegenden *store.Store sowie das SessionSecret zurueck, damit Tests Fixtures
// direkt ueber die Store-Methoden seeden UND Cookies fuer beliebige User-IDs
// signieren koennen (fuer die Zwei-Nutzer-Isolationstests).
func newBriefingTestRouter(t *testing.T) (http.Handler, *store.Store, string) {
	t.Helper()

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()

	s := store.New(cfg.DataDir, cfg.UserID)

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
		WeatherProvider:    nil,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})

	return r, s, cfg.SessionSecret
}

// sessionCookieFor signiert ein gueltiges gz_session-Cookie fuer userId, damit
// AuthMiddleware den Request bis zur chi-Routenaufloesung durchlaesst.
func sessionCookieFor(userId, secret string) *http.Cookie {
	return &http.Cookie{Name: "gz_session", Value: authmw.SignSession(userId, secret)}
}

func doBriefingRequest(t *testing.T, r http.Handler, method, path string, body []byte, cookie *http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	var req *http.Request
	if body != nil {
		req = httptest.NewRequest(method, path, bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
	} else {
		req = httptest.NewRequest(method, path, nil)
	}
	req.AddCookie(cookie)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// seedRouteTrip persistiert einen Trip mit mehreren Feldern (Name, Stages,
// ReportConfig) fuer userId — Grundlage fuer die Merge-Tests (AC-22).
func seedRouteTrip(t *testing.T, s *store.Store, userId, id string) *model.Trip {
	t.Helper()
	trip := model.Trip{
		ID:   id,
		Name: "Original Name",
		Stages: []model.Stage{{
			ID: "S1", Name: "Tag 1", Date: "2026-08-01",
			Waypoints: []model.Waypoint{{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500}},
		}},
		ReportConfig: map[string]interface{}{"channels": []interface{}{"email"}},
	}
	if err := s.WithUser(userId).SaveTrip(&trip); err != nil {
		t.Fatalf("seedRouteTrip: %v", err)
	}
	return &trip
}

// seedVergleichPreset persistiert ein ComparePreset mit mehreren Feldern
// (Name, LocationIDs, DisplayConfig) fuer userId — Grundlage fuer die
// Merge-Tests (AC-22, Preset-Seite).
func seedVergleichPreset(t *testing.T, s *store.Store, userId, id string) *model.ComparePreset {
	t.Helper()
	preset := model.ComparePreset{
		ID:            id,
		UserID:        userId,
		Name:          "Original Preset",
		LocationIDs:   []string{"loc-a", "loc-b"},
		Schedule:      "daily",
		Profil:        "SUMMER_TREKKING",
		HourFrom:      6,
		HourTo:        18,
		ForecastHours: 48,
		Empfaenger:    []string{"test@example.com"},
		DisplayConfig: map[string]interface{}{"theme": "compact"},
		CreatedAt:     time.Now().UTC(),
	}
	if err := s.WithUser(userId).SaveComparePresets([]model.ComparePreset{preset}); err != nil {
		t.Fatalf("seedVergleichPreset: %v", err)
	}
	return &preset
}

func minimalRouteCreateBody(id, name string) []byte {
	body := map[string]interface{}{
		"kind": "route",
		"id":   id,
		"name": name,
		"stages": []map[string]interface{}{{
			"id": "S1", "name": "Tag 1", "date": "2026-08-01",
			"waypoints": []map[string]interface{}{{
				"id": "W1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 500,
			}},
		}},
	}
	b, _ := json.Marshal(body)
	return b
}

func minimalVergleichCreateBody(name string) []byte {
	body := map[string]interface{}{
		"kind":         "vergleich",
		"name":         name,
		"location_ids": []string{"loc-1", "loc-2"},
		"schedule":     "daily",
		"profil":       "SUMMER_TREKKING",
		"hour_from":    6,
		"hour_to":      18,
		"empfaenger":   []string{"test@example.com"},
	}
	b, _ := json.Marshal(body)
	return b
}

// =============================================================================
// 1. GET /api/briefings/{id}?kind=route — Einzelabruf Trip
// =============================================================================

// TestBriefingsGet_Route_ReturnsTripStructure:
// GIVEN ein existierender Trip fuer user1
// WHEN  GET /api/briefings/{id}?kind=route
// THEN  200 + Body traegt mindestens id, name, kind=="route" (gleiche Struktur
//       wie /api/trips/{id}).
// Heute: /api/briefings* ist nicht registriert -> 404 -> RED.
func TestBriefingsGet_Route_ReturnsTripStructure(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedRouteTrip(t, s, "user1", "trip-briefing-1")
	cookie := sessionCookieFor("user1", secret)

	w := doBriefingRequest(t, r, "GET", "/api/briefings/trip-briefing-1?kind=route", nil, cookie)

	if w.Code != http.StatusOK {
		t.Fatalf("RED: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("expected JSON object, got error: %v", err)
	}
	if body["id"] != "trip-briefing-1" {
		t.Errorf("expected id trip-briefing-1, got %v", body["id"])
	}
	if body["name"] != "Original Name" {
		t.Errorf("expected name preserved, got %v", body["name"])
	}
	if body["kind"] != "route" {
		t.Errorf("expected kind=route, got %v", body["kind"])
	}
}

// =============================================================================
// 2. GET /api/briefings/{id}?kind=vergleich — Einzelabruf Preset
// =============================================================================

// TestBriefingsGet_Vergleich_ReturnsPresetStructure:
// GIVEN ein existierendes ComparePreset fuer user1
// WHEN  GET /api/briefings/{id}?kind=vergleich
// THEN  200 + Body traegt kind=="vergleich".
// Heute: 404 -> RED.
func TestBriefingsGet_Vergleich_ReturnsPresetStructure(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedVergleichPreset(t, s, "user1", "cp-briefing-1")
	cookie := sessionCookieFor("user1", secret)

	w := doBriefingRequest(t, r, "GET", "/api/briefings/cp-briefing-1?kind=vergleich", nil, cookie)

	if w.Code != http.StatusOK {
		t.Fatalf("RED: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("expected JSON object, got error: %v", err)
	}
	if body["id"] != "cp-briefing-1" {
		t.Errorf("expected id cp-briefing-1, got %v", body["id"])
	}
	if body["kind"] != "vergleich" {
		t.Errorf("expected kind=vergleich, got %v", body["kind"])
	}
}

// =============================================================================
// 3. GET /api/briefings — Aggregat-Liste
// =============================================================================

// TestBriefingsList_AggregatesTripsAndPresets:
// GIVEN 1 Trip UND 1 ComparePreset fuer user1
// WHEN  GET /api/briefings
// THEN  200 + beide Eintraege sind enthalten, jeder mit korrektem kind-Tag.
// Heute: 404 -> RED.
func TestBriefingsList_AggregatesTripsAndPresets(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedRouteTrip(t, s, "user1", "trip-agg-1")
	seedVergleichPreset(t, s, "user1", "cp-agg-1")
	cookie := sessionCookieFor("user1", secret)

	w := doBriefingRequest(t, r, "GET", "/api/briefings", nil, cookie)

	if w.Code != http.StatusOK {
		t.Fatalf("RED: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var items []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &items); err != nil {
		t.Fatalf("expected JSON array, got error: %v", err)
	}
	if len(items) != 2 {
		t.Fatalf("expected 2 aggregated entries, got %d: %v", len(items), items)
	}
	kinds := map[string]bool{}
	for _, it := range items {
		kind, _ := it["kind"].(string)
		kinds[kind] = true
	}
	if !kinds["route"] || !kinds["vergleich"] {
		t.Errorf("expected both kind=route and kind=vergleich in aggregate list, got %v", kinds)
	}
}

// =============================================================================
// 4. POST /api/briefings — Anlegen (route + vergleich)
// =============================================================================

// TestBriefingsCreate_Route_AppearsInTripsStore:
// GIVEN kein Trip mit der ID
// WHEN  POST /api/briefings mit Body {kind:"route", ...minimaler Trip...}
// THEN  200/201 UND der Trip ist danach via GET /api/trips/{id} abrufbar
//       (belegt: der neue Endpoint schreibt in den bestehenden Trip-Store,
//       kein Split-Brain).
// Heute: 404 -> RED.
func TestBriefingsCreate_Route_AppearsInTripsStore(t *testing.T) {
	r, _, secret := newBriefingTestRouter(t)
	cookie := sessionCookieFor("user1", secret)

	w := doBriefingRequest(t, r, "POST", "/api/briefings", minimalRouteCreateBody("trip-created-1", "Neu Angelegt"), cookie)

	if w.Code != http.StatusOK && w.Code != http.StatusCreated {
		t.Fatalf("RED: expected 200/201, got %d: %s", w.Code, w.Body.String())
	}

	getW := doBriefingRequest(t, r, "GET", "/api/trips/trip-created-1", nil, cookie)
	if getW.Code != http.StatusOK {
		t.Fatalf("expected created route to appear via GET /api/trips/{id}, got %d: %s", getW.Code, getW.Body.String())
	}
	var trip map[string]interface{}
	json.Unmarshal(getW.Body.Bytes(), &trip)
	if trip["name"] != "Neu Angelegt" {
		t.Errorf("expected name 'Neu Angelegt', got %v", trip["name"])
	}
}

// TestBriefingsCreate_Vergleich_AppearsInPresetsStore:
// GIVEN kein Preset mit diesem Namen
// WHEN  POST /api/briefings mit Body {kind:"vergleich", ...minimales Preset...}
// THEN  200/201 UND das Preset ist danach via GET /api/compare/presets/{id}
//       abrufbar (der neue Endpoint schreibt in den bestehenden Preset-Store).
// Heute: 404 -> RED.
func TestBriefingsCreate_Vergleich_AppearsInPresetsStore(t *testing.T) {
	r, _, secret := newBriefingTestRouter(t)
	cookie := sessionCookieFor("user1", secret)

	w := doBriefingRequest(t, r, "POST", "/api/briefings", minimalVergleichCreateBody("Neues Preset"), cookie)

	if w.Code != http.StatusOK && w.Code != http.StatusCreated {
		t.Fatalf("RED: expected 200/201, got %d: %s", w.Code, w.Body.String())
	}
	var created map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatalf("expected JSON object in create response: %v", err)
	}
	id, _ := created["id"].(string)
	if id == "" {
		t.Fatalf("expected created preset to carry an id, got %v", created)
	}

	getW := doBriefingRequest(t, r, "GET", "/api/compare/presets/"+id, nil, cookie)
	if getW.Code != http.StatusOK {
		t.Fatalf("expected created vergleich to appear via GET /api/compare/presets/{id}, got %d: %s", getW.Code, getW.Body.String())
	}
	var preset map[string]interface{}
	json.Unmarshal(getW.Body.Bytes(), &preset)
	if preset["name"] != "Neues Preset" {
		t.Errorf("expected name 'Neues Preset', got %v", preset["name"])
	}
}

// =============================================================================
// 5. PUT /api/briefings/{id}?kind=... — AC-22 partieller Merge
// =============================================================================

// TestBriefingsUpdate_Route_MergesPartialBody:
// GIVEN ein Trip mit mehreren Feldern (name, stages, report_config)
// WHEN  PUT /api/briefings/{id}?kind=route mit NUR {"name":"Neu"}
// THEN  200, und ein anschliessendes Laden zeigt name=="Neu" UND
//       stages/report_config unveraendert erhalten (Merge, kein Replace —
//       AC-22, KL-5: siebte Wiederholung des Datenverlust-Musters vermeiden).
// Heute: 404 -> RED.
func TestBriefingsUpdate_Route_MergesPartialBody(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedRouteTrip(t, s, "user1", "trip-merge-1")
	cookie := sessionCookieFor("user1", secret)

	partial, _ := json.Marshal(map[string]interface{}{"name": "Neu"})
	w := doBriefingRequest(t, r, "PUT", "/api/briefings/trip-merge-1?kind=route", partial, cookie)

	if w.Code != http.StatusOK {
		t.Fatalf("RED: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	reloaded, err := s.WithUser("user1").LoadTrip("trip-merge-1")
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	if reloaded == nil {
		t.Fatalf("trip disappeared after partial PUT")
	}
	if reloaded.Name != "Neu" {
		t.Errorf("expected name updated to 'Neu', got %q", reloaded.Name)
	}
	if len(reloaded.Stages) != 1 || reloaded.Stages[0].ID != "S1" {
		t.Errorf("merge FAIL: expected stages to survive a name-only PUT, got %+v", reloaded.Stages)
	}
	if reloaded.ReportConfig == nil || reloaded.ReportConfig["channels"] == nil {
		t.Errorf("merge FAIL: expected report_config to survive a name-only PUT, got %v", reloaded.ReportConfig)
	}
}

// TestBriefingsUpdate_Vergleich_MergesPartialBody:
// GIVEN ein ComparePreset mit mehreren Feldern (name, location_ids,
// display_config) — der Alt-Endpoint /api/compare/presets/{id} bekommt heute
// immer Voll-Objekte (Replace-sicher); der NEUE /api/briefings-Pfad muss aber
// auch ein partielles PUT mergen.
// WHEN  PUT /api/briefings/{id}?kind=vergleich mit NUR {"name":"Neu"}
// THEN  200, und ein anschliessendes Laden zeigt name=="Neu" UND
//       location_ids/display_config unveraendert erhalten.
// Heute: 404 -> RED.
func TestBriefingsUpdate_Vergleich_MergesPartialBody(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedVergleichPreset(t, s, "user1", "cp-merge-1")
	cookie := sessionCookieFor("user1", secret)

	partial, _ := json.Marshal(map[string]interface{}{"name": "Neu"})
	w := doBriefingRequest(t, r, "PUT", "/api/briefings/cp-merge-1?kind=vergleich", partial, cookie)

	if w.Code != http.StatusOK {
		t.Fatalf("RED: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	reloaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	idx := findPresetIdxForTest(reloaded, "cp-merge-1")
	if idx < 0 {
		t.Fatalf("preset disappeared after partial PUT")
	}
	if reloaded[idx].Name != "Neu" {
		t.Errorf("expected name updated to 'Neu', got %q", reloaded[idx].Name)
	}
	if len(reloaded[idx].LocationIDs) != 2 {
		t.Errorf("merge FAIL: expected location_ids to survive a name-only PUT, got %v", reloaded[idx].LocationIDs)
	}
	if reloaded[idx].DisplayConfig == nil || reloaded[idx].DisplayConfig["theme"] != "compact" {
		t.Errorf("merge FAIL: expected display_config to survive a name-only PUT, got %v", reloaded[idx].DisplayConfig)
	}
}

func findPresetIdxForTest(presets []model.ComparePreset, id string) int {
	for i, p := range presets {
		if p.ID == id {
			return i
		}
	}
	return -1
}

// =============================================================================
// 6. Edge: kind muss explizit sein (Pflicht-Refinement, Spec Edge Cases)
// =============================================================================

// TestBriefingsGet_MissingKind_Returns400:
// GIVEN einen existierenden Trip
// WHEN  GET /api/briefings/{id} OHNE ?kind=
// THEN  400 (kind wird NIE per Store-Probing geraten, Migrations-F001 —
//       Trip-ID == Preset-ID real moeglich).
// Heute: Route nicht registriert -> 404, NICHT 400 -> RED (Assertion ist
// explizit 400, nicht "irgendein Fehlercode").
func TestBriefingsGet_MissingKind_Returns400(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedRouteTrip(t, s, "user1", "trip-nokind-1")
	cookie := sessionCookieFor("user1", secret)

	w := doBriefingRequest(t, r, "GET", "/api/briefings/trip-nokind-1", nil, cookie)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("RED: expected 400 for missing kind, got %d: %s", w.Code, w.Body.String())
	}
}

// TestBriefingsPut_MissingKind_Returns400:
// GIVEN einen existierenden Trip
// WHEN  PUT /api/briefings/{id} OHNE ?kind=
// THEN  400.
// Heute: 404 -> RED.
func TestBriefingsPut_MissingKind_Returns400(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedRouteTrip(t, s, "user1", "trip-nokind-2")
	cookie := sessionCookieFor("user1", secret)

	body, _ := json.Marshal(map[string]interface{}{"name": "X"})
	w := doBriefingRequest(t, r, "PUT", "/api/briefings/trip-nokind-2", body, cookie)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("RED: expected 400 for missing kind, got %d: %s", w.Code, w.Body.String())
	}
}

// TestBriefingsDelete_MissingKind_Returns400:
// GIVEN einen existierenden Trip
// WHEN  DELETE /api/briefings/{id} OHNE ?kind=
// THEN  400.
// Heute: 404 -> RED.
func TestBriefingsDelete_MissingKind_Returns400(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedRouteTrip(t, s, "user1", "trip-nokind-3")
	cookie := sessionCookieFor("user1", secret)

	w := doBriefingRequest(t, r, "DELETE", "/api/briefings/trip-nokind-3", nil, cookie)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("RED: expected 400 for missing kind, got %d: %s", w.Code, w.Body.String())
	}
}

// TestBriefingsCreate_MissingKindInBody_Returns400:
// GIVEN einen POST-Body ohne kind-Feld
// WHEN  POST /api/briefings
// THEN  400, kein Anlegen (Spec Edge Case: "POST /api/briefings ohne
//       gueltiges kind im Body -> 400 Bad Request, kein Anlegen").
// Heute: 404 -> RED.
func TestBriefingsCreate_MissingKindInBody_Returns400(t *testing.T) {
	r, _, secret := newBriefingTestRouter(t)
	cookie := sessionCookieFor("user1", secret)

	body, _ := json.Marshal(map[string]interface{}{
		"id": "trip-missing-kind", "name": "Ohne Kind",
	})
	w := doBriefingRequest(t, r, "POST", "/api/briefings", body, cookie)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("RED: expected 400 for missing kind in body, got %d: %s", w.Code, w.Body.String())
	}
}

// TestBriefingsCreate_InvalidKindInBody_Returns400:
// GIVEN einen POST-Body mit ungueltigem kind-Wert ("unbekannt")
// WHEN  POST /api/briefings
// THEN  400, kein Anlegen.
// Heute: 404 -> RED.
func TestBriefingsCreate_InvalidKindInBody_Returns400(t *testing.T) {
	r, _, secret := newBriefingTestRouter(t)
	cookie := sessionCookieFor("user1", secret)

	body, _ := json.Marshal(map[string]interface{}{
		"kind": "unbekannt", "id": "trip-bad-kind", "name": "Falscher Kind",
	})
	w := doBriefingRequest(t, r, "POST", "/api/briefings", body, cookie)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("RED: expected 400 for invalid kind in body, got %d: %s", w.Code, w.Body.String())
	}
}

// =============================================================================
// 7. Zwei-Nutzer-Isolation (PFLICHT bei datenbewegenden Endpoints)
// =============================================================================

// TestBriefingsGet_CrossUserIsolation_OwnerOkIntruder404:
// GIVEN ein Trip von userA
// WHEN  (a) userA selbst GET /api/briefings/{id}?kind=route abruft
// THEN  200 (Eigentuemer darf lesen) — heute 404 -> RED, daher t.Fatalf hier
//       zuerst; der Test scheitert bereits an diesem Punkt, solange die
//       Route fehlt.
// WHEN  (b) userB (ein ANDERER Nutzer) denselben Request stellt
// THEN  404 (kein Cross-User-Zugriff, KEIN Store-Leck) — dieser Teil wird
//       erst NACH einer Implementierung sinnvoll geprueft, weil (a) vorher
//       bereits fehlschlaegt (t.Fatalf stoppt den Testlauf).
func TestBriefingsGet_CrossUserIsolation_OwnerOkIntruder404(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedRouteTrip(t, s, "userA", "trip-isolated-1")

	ownerCookie := sessionCookieFor("userA", secret)
	ownerW := doBriefingRequest(t, r, "GET", "/api/briefings/trip-isolated-1?kind=route", nil, ownerCookie)
	if ownerW.Code != http.StatusOK {
		t.Fatalf("RED: expected owner (userA) to get 200, got %d: %s", ownerW.Code, ownerW.Body.String())
	}

	intruderCookie := sessionCookieFor("userB", secret)
	intruderW := doBriefingRequest(t, r, "GET", "/api/briefings/trip-isolated-1?kind=route", nil, intruderCookie)
	if intruderW.Code != http.StatusNotFound {
		t.Errorf("user isolation broken: userB expected 404 for userA's trip, got %d: %s", intruderW.Code, intruderW.Body.String())
	}
}

// =============================================================================
// 8. AC-20 Regressions-Guard — bleibt GRUEN (kein RED-Test!)
// =============================================================================

// TestBriefingsRegressionGuard_TripAndPresetStructureUnchanged:
// GIVEN einen existierenden Trip UND ein existierendes ComparePreset
// WHEN  GET /api/trips/{id} bzw. GET /api/compare/presets/{id} (Alt-Endpoints,
//       heute schon registriert)
// THEN  liefern beide ihre HEUTIGE Struktur (id/name vorhanden) — dieser Test
//       ist bereits VOR jeder S6-Implementierung GRUEN und bleibt es danach
//       (er ist der "nicht brechen"-Guard, AC-20: dünne Kompat-Delegates
//       liefern dieselbe Response-Struktur wie vor Scheibe 6). KEIN RED-Test.
func TestBriefingsRegressionGuard_TripAndPresetStructureUnchanged(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedRouteTrip(t, s, "user1", "trip-guard-1")
	seedVergleichPreset(t, s, "user1", "cp-guard-1")
	cookie := sessionCookieFor("user1", secret)

	tripW := doBriefingRequest(t, r, "GET", "/api/trips/trip-guard-1", nil, cookie)
	if tripW.Code != http.StatusOK {
		t.Fatalf("guard: expected 200 from /api/trips/{id} (unrelated to S6), got %d: %s", tripW.Code, tripW.Body.String())
	}
	var trip map[string]interface{}
	json.Unmarshal(tripW.Body.Bytes(), &trip)
	if trip["id"] != "trip-guard-1" || trip["name"] != "Original Name" {
		t.Errorf("guard FAIL: /api/trips/{id} structure changed, got %v", trip)
	}

	presetW := doBriefingRequest(t, r, "GET", "/api/compare/presets/cp-guard-1", nil, cookie)
	if presetW.Code != http.StatusOK {
		t.Fatalf("guard: expected 200 from /api/compare/presets/{id} (unrelated to S6), got %d: %s", presetW.Code, presetW.Body.String())
	}
	var preset map[string]interface{}
	json.Unmarshal(presetW.Body.Bytes(), &preset)
	if preset["id"] != "cp-guard-1" || preset["name"] != "Original Preset" {
		t.Errorf("guard FAIL: /api/compare/presets/{id} structure changed, got %v", preset)
	}
}

// =============================================================================
// F008 (Fix-Loop) — Vergleich-PUT muss paused_at beim erstmaligen Pausieren
// materialisieren (S2-Dual-Write-Invariante), analog compare_preset.go:402.
// =============================================================================

// TestBriefingsUpdate_Vergleich_FirstTimePauseMaterializesPausedAt:
// GIVEN ein Preset mit schedule="daily" und paused_at=nil (noch nie pausiert)
// WHEN  PUT /api/briefings/{id}?kind=vergleich mit Body {"schedule":"manual"}
// THEN  Response UND Store zeigen schedule=="manual" UND paused_at != null
//       (store.MaterializePausedAt muss laufen, sonst bricht die S2-Dual-
//       Write-Invariante — Fix-Loop Finding F008).
func TestBriefingsUpdate_Vergleich_FirstTimePauseMaterializesPausedAt(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedVergleichPreset(t, s, "user1", "cp-pause-1")
	cookie := sessionCookieFor("user1", secret)

	body, _ := json.Marshal(map[string]interface{}{"schedule": "manual"})
	w := doBriefingRequest(t, r, "PUT", "/api/briefings/cp-pause-1?kind=vergleich", body, cookie)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var updated model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &updated); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if updated.Schedule != "manual" {
		t.Fatalf("expected schedule=manual, got %q", updated.Schedule)
	}
	if updated.PausedAt == nil {
		t.Fatalf("F008 REGRESSION: expected paused_at to be materialized on first-time pause, got nil")
	}

	reloaded, err := s.WithUser("user1").LoadComparePresets()
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	idx := findPresetIdxForTest(reloaded, "cp-pause-1")
	if idx < 0 {
		t.Fatalf("preset not found after reload")
	}
	if reloaded[idx].PausedAt == nil {
		t.Fatalf("F008 REGRESSION: expected persisted paused_at after reload, got nil")
	}
}

// TestBriefingsUpdate_Vergleich_AlreadyPausedPausedAtDoesNotDrift:
// GIVEN ein bereits pausiertes Preset (schedule="manual", paused_at gesetzt)
// WHEN  PUT /api/briefings/{id}?kind=vergleich OHNE Aenderung an schedule
//       (nur ein anderes Feld, z.B. name)
// THEN  paused_at bleibt der URSPRUENGLICHE Zeitstempel (kein Drift auf
//       "jetzt" bei jedem PUT — MaterializePausedAt-Guard: nur setzen wenn
//       paused_at noch nil war).
func TestBriefingsUpdate_Vergleich_AlreadyPausedPausedAtDoesNotDrift(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	original := seedVergleichPreset(t, s, "user1", "cp-pause-2")
	originalPausedAt := time.Date(2026, 1, 1, 12, 0, 0, 0, time.UTC)
	original.Schedule = "manual"
	original.PausedAt = &originalPausedAt
	if err := s.WithUser("user1").SaveComparePresets([]model.ComparePreset{*original}); err != nil {
		t.Fatalf("seed pause: %v", err)
	}
	cookie := sessionCookieFor("user1", secret)

	body, _ := json.Marshal(map[string]interface{}{"name": "Nur Name geaendert"})
	w := doBriefingRequest(t, r, "PUT", "/api/briefings/cp-pause-2?kind=vergleich", body, cookie)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var updated model.ComparePreset
	if err := json.Unmarshal(w.Body.Bytes(), &updated); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if updated.Name != "Nur Name geaendert" {
		t.Errorf("expected name updated, got %q", updated.Name)
	}
	if updated.PausedAt == nil || !updated.PausedAt.Equal(originalPausedAt) {
		t.Fatalf("drift REGRESSION: expected paused_at unchanged at %v, got %v", originalPausedAt, updated.PausedAt)
	}
}
