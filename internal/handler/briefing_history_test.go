package handler

// Issue #559 (AC-1, AC-4, AC-5) — BriefingHistoryHandler.
// Spec: docs/specs/modules/issue_559_archiv_fertigstellen.md
//
// TDD RED — Issue #2281 (Epic #2345 P4), AC-8 + AC-9, Test 9/10.
// Spec: docs/specs/modules/feat_2281_vergleich_versand_historie.md
//
// Seit #2281 bedient BriefingHistoryHandler den kind-neutralen Endpunkt
// GET /api/briefings/{id}/briefing-history?kind=route|vergleich. Die
// Bestandstests (#559) laufen deshalb ueber diese Route mit kind=route; der
// Trip-Alias /api/trips/{id}/briefing-history wird ueber den ECHTEN Router in
// internal/router/briefing_history_route_test.go geprueft (Verdrahtung +
// byte-gleiche Antwort, AC-9).

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/store"
)

const briefingHistoryPattern = "/api/briefings/{id}/briefing-history"

func briefingHistoryRouter(s *store.Store) *chi.Mux {
	router := chi.NewRouter()
	router.Get(briefingHistoryPattern, BriefingHistoryHandler(s))
	return router
}

func getBriefingHistory(t *testing.T, s *store.Store, userID, path string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	if userID != "" {
		req = withUserCtx(req, userID)
	}
	w := httptest.NewRecorder()
	briefingHistoryRouter(s).ServeHTTP(w, req)
	return w
}

func decodeHistory(t *testing.T, w *httptest.ResponseRecorder) []map[string]interface{} {
	t.Helper()
	var result []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatalf("kein gueltiges JSON-Array: %v (body=%s)", err, w.Body.String())
	}
	if result == nil {
		t.Fatalf("Antwort ist null statt []: %s", w.Body.String())
	}
	return result
}

func TestBriefingHistoryHandler_Unauthorized(t *testing.T) {
	s := newTestStore(t)
	// No user context set — UserIDFromContext returns "". Gueltiges kind,
	// damit 401 nicht mit der 400 fuer fehlendes kind verwechselt wird.
	w := getBriefingHistory(t, s, "", "/api/briefings/trip-123/briefing-history?kind=route")
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d: %s", w.Code, w.Body.String())
	}
}

func TestBriefingHistoryHandler_EmptyForUnknownTrip(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "test", []map[string]interface{}{
		{"trip_id": "trip-other", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
	})

	w := getBriefingHistory(t, s, "test", "/api/briefings/trip-123/briefing-history?kind=route")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if result := decodeHistory(t, w); len(result) != 0 {
		t.Errorf("expected empty array, got %d entries", len(result))
	}
}

func TestBriefingHistoryHandler_ReturnsMatchingEntries(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "test", []map[string]interface{}{
		{"trip_id": "trip-123", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-123", "kind": "evening", "sent_at": "2026-05-01T18:05:00Z", "channels": []string{"email", "telegram"}},
		{"trip_id": "trip-other", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
	})

	w := getBriefingHistory(t, s, "test", "/api/briefings/trip-123/briefing-history?kind=route")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %s", ct)
	}
	result := decodeHistory(t, w)
	if len(result) != 2 {
		t.Fatalf("expected 2 entries for trip-123, got %d", len(result))
	}
	first := result[0]
	if first["kind"] != "morning" {
		t.Errorf("expected kind=morning, got %v", first["kind"])
	}
	if first["sent_at"] != "2026-05-01T07:00:00Z" {
		t.Errorf("unexpected sent_at: %v", first["sent_at"])
	}
}

func TestBriefingHistoryHandler_EmptyWhenNoLog(t *testing.T) {
	s := newTestStore(t)
	w := getBriefingHistory(t, s, "test", "/api/briefings/trip-123/briefing-history?kind=route")
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if result := decodeHistory(t, w); len(result) != 0 {
		t.Errorf("expected empty array when no log, got %d entries", len(result))
	}
}

// --- #2281 AC-8: kind ist Pflicht und wird geprueft ------------------------

func TestBriefingHistoryHandler_MissingKind_400_AC8(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "userA", []map[string]interface{}{
		{"trip_id": "gleich", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
	})
	w := getBriefingHistory(t, s, "userA", "/api/briefings/gleich/briefing-history")
	if w.Code != http.StatusBadRequest {
		t.Errorf("AC-8: fehlendes kind: erwartet 400, bekommen %d: %s", w.Code, w.Body.String())
	}
}

func TestBriefingHistoryHandler_InvalidKind_400_AC8(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "userA", []map[string]interface{}{
		{"trip_id": "gleich", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
	})
	// "trip"/"compare" sind Log-Typen, KEINE gueltigen Web-kinds.
	for _, k := range []string{"quatsch", "trip", "compare", "ROUTE"} {
		w := getBriefingHistory(t, s, "userA", "/api/briefings/gleich/briefing-history?kind="+k)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-8: kind=%q: erwartet 400, bekommen %d: %s", k, w.Code, w.Body.String())
		}
	}
}

func TestBriefingHistoryHandler_InvalidID_400_AC8(t *testing.T) {
	s := newTestStore(t)
	for _, id := range []string{".", ".."} {
		w := getBriefingHistory(t, s, "userA", "/api/briefings/"+id+"/briefing-history?kind=route")
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-8: ID %q: erwartet 400, bekommen %d: %s", id, w.Code, w.Body.String())
		}
	}
}

// --- #2281 AC-8: kind filtert nach entity_type -----------------------------

// mixedHistoryLog: dieselbe ID als Alt-Trip-Eintrag, neuer Trip-Eintrag und
// zwei Compare-Eintraege.
func mixedHistoryLog() []map[string]interface{} {
	return []map[string]interface{}{
		{"trip_id": "gleich", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
		{"entity_id": "gleich", "entity_type": "trip", "trip_id": "gleich", "kind": "evening", "sent_at": "2026-05-01T18:00:00Z", "channels": []string{"telegram"}, "on_demand": true},
		{"entity_id": "gleich", "entity_type": "compare", "kind": "morning", "sent_at": "2026-05-02T07:00:00Z", "channels": []string{"sms"}, "on_demand": false},
		{"entity_id": "gleich", "entity_type": "compare", "kind": "evening", "sent_at": "2026-05-02T18:00:00Z", "channels": []string{"email", "premium_sms"}, "on_demand": true},
		{"entity_id": "andere", "entity_type": "compare", "kind": "morning", "sent_at": "2026-05-03T07:00:00Z", "channels": []string{"email"}},
	}
}

func TestBriefingHistoryHandler_KindVergleich_OnlyCompareEntries_AC8(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "userA", mixedHistoryLog())

	w := getBriefingHistory(t, s, "userA", "/api/briefings/gleich/briefing-history?kind=vergleich")
	if w.Code != http.StatusOK {
		t.Fatalf("200 erwartet, %d bekommen: %s", w.Code, w.Body.String())
	}
	result := decodeHistory(t, w)
	if len(result) != 2 {
		t.Fatalf("AC-8: kind=vergleich: genau 2 Compare-Eintraege erwartet, %d bekommen: %s", len(result), w.Body.String())
	}
	wantSent := []string{"2026-05-02T07:00:00Z", "2026-05-02T18:00:00Z"}
	wantOnDemand := []bool{false, true}
	for i, e := range result {
		if e["sent_at"] != wantSent[i] {
			t.Errorf("AC-8: Eintrag %d sent_at=%v, erwartet %s", i, e["sent_at"], wantSent[i])
		}
		od, has := e["on_demand"]
		if !has {
			t.Errorf("AC-8: Eintrag %d ohne on_demand-Feld (Antwortform {sent_at, kind, channels, on_demand}): %v", i, e)
		} else if od != wantOnDemand[i] {
			t.Errorf("AC-8: Eintrag %d on_demand=%v, erwartet %v", i, od, wantOnDemand[i])
		}
		if _, has := e["channels"]; !has {
			t.Errorf("AC-8: Eintrag %d ohne channels: %v", i, e)
		}
	}
	if result[1]["kind"] != "evening" {
		t.Errorf("AC-8: kind (Slot) des 2. Compare-Eintrags=%v, erwartet evening", result[1]["kind"])
	}
}

func TestBriefingHistoryHandler_KindRoute_OnlyTripEntriesInclLegacy_AC8(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "userA", mixedHistoryLog())

	w := getBriefingHistory(t, s, "userA", "/api/briefings/gleich/briefing-history?kind=route")
	if w.Code != http.StatusOK {
		t.Fatalf("200 erwartet, %d bekommen: %s", w.Code, w.Body.String())
	}
	result := decodeHistory(t, w)
	if len(result) != 2 {
		t.Fatalf("AC-8: kind=route: genau 2 Trip-Eintraege erwartet (Alt + neu, kein Compare), %d bekommen: %s", len(result), w.Body.String())
	}
	if result[0]["sent_at"] != "2026-05-01T07:00:00Z" || result[1]["sent_at"] != "2026-05-01T18:00:00Z" {
		t.Errorf("AC-8: falsche Eintraege fuer kind=route: %s", w.Body.String())
	}
	// Alt-Eintrag ohne on_demand liefert false, nicht fehlend.
	if od, has := result[0]["on_demand"]; !has || od != false {
		t.Errorf("AC-8: Alt-Eintrag on_demand=%v (vorhanden=%v), erwartet false", od, has)
	}
	if result[1]["on_demand"] != true {
		t.Errorf("AC-8: Trip-Handversand on_demand=%v, erwartet true", result[1]["on_demand"])
	}
}

// AC-8: zwei Nutzer mit gleichlautenden IDs — jeder sieht nur seine Datei.
func TestBriefingHistoryHandler_TwoUsersSameID_Isolated_AC8(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "userA", []map[string]interface{}{
		{"entity_id": "gleich", "entity_type": "compare", "kind": "morning", "sent_at": "2026-05-02T07:00:00Z", "channels": []string{"email"}},
	})
	seedBriefingLog(t, s.DataDir, "userB", []map[string]interface{}{
		{"entity_id": "gleich", "entity_type": "compare", "kind": "morning", "sent_at": "2026-06-02T07:00:00Z", "channels": []string{"telegram"}},
		{"entity_id": "gleich", "entity_type": "compare", "kind": "evening", "sent_at": "2026-06-02T18:00:00Z", "channels": []string{"telegram"}},
	})

	wA := getBriefingHistory(t, s, "userA", "/api/briefings/gleich/briefing-history?kind=vergleich")
	a := decodeHistory(t, wA)
	if len(a) != 1 || a[0]["sent_at"] != "2026-05-02T07:00:00Z" {
		t.Errorf("AC-8: userA sieht nicht genau seinen Eintrag: %s", wA.Body.String())
	}
	wB := getBriefingHistory(t, s, "userB", "/api/briefings/gleich/briefing-history?kind=vergleich")
	b := decodeHistory(t, wB)
	if len(b) != 2 {
		t.Errorf("AC-8: userB sieht nicht genau seine 2 Eintraege: %s", wB.Body.String())
	}
	for _, e := range b {
		if e["sent_at"] == "2026-05-02T07:00:00Z" {
			t.Errorf("AC-8: Cross-User-Leck — userA-Eintrag in userB-Antwort: %s", wB.Body.String())
		}
	}

	// Fremde/unbekannte ID: 200 mit [] (keine Existenzpruefung).
	wU := getBriefingHistory(t, s, "userA", "/api/briefings/unbekannt/briefing-history?kind=vergleich")
	if wU.Code != http.StatusOK {
		t.Fatalf("AC-8: unbekannte ID: 200 erwartet, %d bekommen: %s", wU.Code, wU.Body.String())
	}
	if u := decodeHistory(t, wU); len(u) != 0 {
		t.Errorf("AC-8: unbekannte ID: [] erwartet, bekommen %s", wU.Body.String())
	}
}
