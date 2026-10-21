package router

// TDD RED — Issue #2281 (Epic #2345 P4), AC-8 + AC-9, Test 9/10.
// SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md
//
// Verdrahtungs-Nachweis ueber den ECHTEN Produktions-Router
// (newBriefingTestRouter, dieselbe Deps-Verdrahtung wie cmd/server/main.go,
// inklusive AuthMiddleware und echten Session-Cookies). Die Handler-Tests in
// internal/handler/briefing_history_test.go registrieren die Route selbst —
// sie bleiben gruen, auch wenn die Zeile in router.go fehlt. Diese Datei
// schliesst genau diese Luecke und prueft zusaetzlich den Trip-Alias (AC-9).

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

// seedHistoryLogFor schreibt users/<uid>/briefing_log.json direkt auf Platte
// (so wie der Python-Schreiber es tut).
func seedHistoryLogFor(t *testing.T, dataDir, uid string, entries []map[string]interface{}) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", uid)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	b, err := json.Marshal(map[string]interface{}{"entries": entries})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "briefing_log.json"), b, 0o644); err != nil {
		t.Fatal(err)
	}
}

func getHistoryAs(t *testing.T, r http.Handler, uid, secret, path string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	if uid != "" {
		req.AddCookie(sessionCookieFor(uid, secret))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func decodeHistoryArray(t *testing.T, w *httptest.ResponseRecorder) []map[string]interface{} {
	t.Helper()
	var out []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil {
		t.Fatalf("kein gueltiges JSON-Array: %v (status=%d body=%s)", err, w.Code, w.Body.String())
	}
	if out == nil {
		t.Fatalf("Antwort ist null statt []: %s", w.Body.String())
	}
	return out
}

// Gleiche ID als Alt-Trip-Eintrag, neuer Trip-Eintrag und Compare-Eintrag —
// damit ein Alias, der kind=route verliert, den Compare-Eintrag durchreicht
// und der Byte-Vergleich nicht vakuum-gruen ([]==[]) wird.
func historyLogUserA() []map[string]interface{} {
	return []map[string]interface{}{
		{"trip_id": "gleich", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
		{"entity_id": "gleich", "entity_type": "trip", "trip_id": "gleich", "kind": "evening", "sent_at": "2026-05-01T18:00:00Z", "channels": []string{"telegram"}, "on_demand": true},
		{"entity_id": "gleich", "entity_type": "compare", "kind": "morning", "sent_at": "2026-05-02T07:00:00Z", "channels": []string{"sms"}, "on_demand": false},
	}
}

// AC-8: Route ist im Produktions-Router verdrahtet, geschuetzt, und liefert
// pro kind nur die passenden Eintraege.
func TestBriefingHistoryRoute_IsWiredAndFiltersByKind_AC8(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedHistoryLogFor(t, s.DataDir, "userA", historyLogUserA())

	w := getHistoryAs(t, r, "userA", secret, "/api/briefings/gleich/briefing-history?kind=vergleich")
	if w.Code == http.StatusNotFound || w.Code == http.StatusMethodNotAllowed {
		t.Fatalf("VERDRAHTUNG FEHLT: GET /api/briefings/{id}/briefing-history antwortet %d — "+
			"die Route ist im Produktions-Router nicht registriert: %s", w.Code, w.Body.String())
	}
	if w.Code != http.StatusOK {
		t.Fatalf("AC-8: 200 erwartet, %d bekommen: %s", w.Code, w.Body.String())
	}
	v := decodeHistoryArray(t, w)
	if len(v) != 1 || v[0]["sent_at"] != "2026-05-02T07:00:00Z" {
		t.Errorf("AC-8: kind=vergleich muss genau den Compare-Eintrag liefern: %s", w.Body.String())
	}

	wR := getHistoryAs(t, r, "userA", secret, "/api/briefings/gleich/briefing-history?kind=route")
	rt := decodeHistoryArray(t, wR)
	if len(rt) != 2 {
		t.Errorf("AC-8: kind=route muss genau die 2 Trip-Eintraege (inkl. Alt) liefern: %s", wR.Body.String())
	}

	// Ohne Anmeldung: 401, keine Daten.
	wAnon := getHistoryAs(t, r, "", secret, "/api/briefings/gleich/briefing-history?kind=vergleich")
	if wAnon.Code != http.StatusUnauthorized {
		t.Errorf("AC-8: ohne Anmeldung 401 erwartet, bekommen %d: %s", wAnon.Code, wAnon.Body.String())
	}

	// kind fehlt / ungueltig: 400 auch ueber den echten Router.
	for _, p := range []string{
		"/api/briefings/gleich/briefing-history",
		"/api/briefings/gleich/briefing-history?kind=quatsch",
	} {
		wk := getHistoryAs(t, r, "userA", secret, p)
		if wk.Code != http.StatusBadRequest {
			t.Errorf("AC-8: %s: 400 erwartet, bekommen %d: %s", p, wk.Code, wk.Body.String())
		}
	}
	// Ungueltig geformte ID: 400.
	wd := getHistoryAs(t, r, "userA", secret, "/api/briefings/./briefing-history?kind=route")
	if wd.Code != http.StatusBadRequest {
		t.Errorf("AC-8: ID \".\": 400 erwartet, bekommen %d: %s", wd.Code, wd.Body.String())
	}
}

// AC-8: zwei echte Nutzer (Session-Cookies) mit gleichlautender ID — jeder
// sieht nur die eigene Datei; fremde/unbekannte ID ergibt 200 [].
func TestBriefingHistoryRoute_TwoUsersSameID_Isolated_AC8(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedHistoryLogFor(t, s.DataDir, "userA", historyLogUserA())
	seedHistoryLogFor(t, s.DataDir, "userB", []map[string]interface{}{
		{"entity_id": "gleich", "entity_type": "compare", "kind": "evening", "sent_at": "2026-07-09T18:00:00Z", "channels": []string{"telegram"}, "on_demand": true},
		{"entity_id": "nurB", "entity_type": "compare", "kind": "morning", "sent_at": "2026-07-10T07:00:00Z", "channels": []string{"email"}},
	})

	wA := getHistoryAs(t, r, "userA", secret, "/api/briefings/gleich/briefing-history?kind=vergleich")
	a := decodeHistoryArray(t, wA)
	if len(a) != 1 || a[0]["sent_at"] != "2026-05-02T07:00:00Z" {
		t.Errorf("AC-8: userA sieht nicht genau seinen Compare-Eintrag: %s", wA.Body.String())
	}

	wB := getHistoryAs(t, r, "userB", secret, "/api/briefings/gleich/briefing-history?kind=vergleich")
	b := decodeHistoryArray(t, wB)
	if len(b) != 1 || b[0]["sent_at"] != "2026-07-09T18:00:00Z" {
		t.Errorf("AC-8: userB sieht nicht genau seinen Compare-Eintrag (Cross-User-Leck?): %s", wB.Body.String())
	}

	// userA fragt nach userBs ID: 200 [] — keine Existenzpruefung, kein Leck.
	wF := getHistoryAs(t, r, "userA", secret, "/api/briefings/nurB/briefing-history?kind=vergleich")
	if wF.Code != http.StatusOK {
		t.Fatalf("AC-8: fremde ID: 200 erwartet, %d bekommen: %s", wF.Code, wF.Body.String())
	}
	if f := decodeHistoryArray(t, wF); len(f) != 0 {
		t.Errorf("AC-8: fremde ID liefert Daten von userB: %s", wF.Body.String())
	}
}

// AC-9: der bestehende Trip-Aufruf liefert byte-gleich dieselbe Antwort wie
// der neue Endpunkt mit kind=route — und NICHT den Compare-Eintrag.
func TestTripBriefingHistoryAlias_ByteEqualToKindRoute_AC9(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)
	seedHistoryLogFor(t, s.DataDir, "userA", historyLogUserA())

	wNew := getHistoryAs(t, r, "userA", secret, "/api/briefings/gleich/briefing-history?kind=route")
	if wNew.Code != http.StatusOK {
		t.Fatalf("AC-9: neuer Endpunkt mit kind=route: 200 erwartet, %d bekommen: %s", wNew.Code, wNew.Body.String())
	}
	wAlias := getHistoryAs(t, r, "userA", secret, "/api/trips/gleich/briefing-history")
	if wAlias.Code != http.StatusOK {
		t.Fatalf("AC-9: Trip-Alias: 200 erwartet, %d bekommen: %s", wAlias.Code, wAlias.Body.String())
	}

	newEntries := decodeHistoryArray(t, wNew)
	if len(newEntries) != 2 {
		t.Fatalf("AC-9: Vorbedingung — kind=route liefert %d statt 2 Eintraege: %s", len(newEntries), wNew.Body.String())
	}
	if wAlias.Body.String() != wNew.Body.String() {
		t.Errorf("AC-9: Trip-Alias und kind=route liefern unterschiedliche Antworten:\nalias: %s\nneu:   %s",
			wAlias.Body.String(), wNew.Body.String())
	}
	if ct := wAlias.Header().Get("Content-Type"); ct != wNew.Header().Get("Content-Type") {
		t.Errorf("AC-9: Content-Type unterscheidet sich: alias=%q neu=%q", ct, wNew.Header().Get("Content-Type"))
	}
	for _, e := range decodeHistoryArray(t, wAlias) {
		if e["sent_at"] == "2026-05-02T07:00:00Z" {
			t.Errorf("AC-9: Trip-Alias liefert den Compare-Eintrag mit gleicher ID: %s", wAlias.Body.String())
		}
		if _, has := e["on_demand"]; !has {
			t.Errorf("AC-9: Trip-Alias-Eintrag ohne on_demand (Antwortform): %v", e)
		}
	}
}
