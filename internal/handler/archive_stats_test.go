package handler

// Echte Verhaltenstests für ArchiveStatsHandler (Issue #772).
// Keine Mocks, kein Source-Grep: echter newTestStore, echte JSON-Log-Dateien,
// echter Handler-Aufruf via httptest. Helfer (seedBriefingLog/seedAlertLog/
// withUserCtx/newTestStore) stammen aus cockpit_test.go bzw. trip_write_test.go.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// decodeCounts liest die {"briefings":{...},"alerts":{...}}-Maps aus der Response.
func decodeCounts(t *testing.T, w *httptest.ResponseRecorder) (map[string]float64, map[string]float64) {
	t.Helper()
	var resp struct {
		Briefings map[string]float64 `json:"briefings"`
		Alerts    map[string]float64 `json:"alerts"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("response is not valid JSON: %v (body=%s)", err, w.Body.String())
	}
	return resp.Briefings, resp.Alerts
}

// AC-5: Geseedete Logs + Auth-Kontext → 200, application/json, korrekte Counts.
func TestArchiveStatsHandler_ReturnsCountsJson(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "test", []map[string]interface{}{
		{"trip_id": "trip-A", "kind": "morning", "sent_at": "2026-06-10T07:00:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-A", "kind": "evening", "sent_at": "2026-06-10T18:00:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-B", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"telegram"}},
	})
	seedAlertLog(t, s.DataDir, "test", []map[string]interface{}{
		{"trip_id": "trip-A", "sent_at": "2026-06-10T09:00:00Z", "changes_count": 1, "severity": "LOW"},
		{"trip_id": "trip-B", "sent_at": "2026-06-11T10:00:00Z", "changes_count": 2, "severity": "MODERATE"},
		{"trip_id": "trip-B", "sent_at": "2026-06-11T12:00:00Z", "changes_count": 1, "severity": "LOW"},
	})

	h := ArchiveStatsHandler(s)
	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", ct)
	}

	briefings, alerts := decodeCounts(t, w)
	if briefings["trip-A"] != 2 {
		t.Errorf("expected briefings trip-A=2, got %v", briefings["trip-A"])
	}
	if briefings["trip-B"] != 1 {
		t.Errorf("expected briefings trip-B=1, got %v", briefings["trip-B"])
	}
	if alerts["trip-A"] != 1 {
		t.Errorf("expected alerts trip-A=1, got %v", alerts["trip-A"])
	}
	if alerts["trip-B"] != 2 {
		t.Errorf("expected alerts trip-B=2, got %v", alerts["trip-B"])
	}
}

// AC-6: Nutzer ohne Logs → 200, briefings und alerts jeweils leeres Objekt (kein null).
func TestArchiveStatsHandler_EmptyWhenNoLogs(t *testing.T) {
	s := newTestStore(t)

	h := ArchiveStatsHandler(s)
	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Distinguish empty-object {} from null at the raw-JSON level.
	var raw struct {
		Briefings *map[string]int `json:"briefings"`
		Alerts    *map[string]int `json:"alerts"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &raw); err != nil {
		t.Fatalf("not valid JSON: %v (body=%s)", err, w.Body.String())
	}
	if raw.Briefings == nil {
		t.Fatal("briefings is null, expected empty object {}")
	}
	if raw.Alerts == nil {
		t.Fatal("alerts is null, expected empty object {}")
	}
	if len(*raw.Briefings) != 0 {
		t.Errorf("expected empty briefings, got %v", *raw.Briefings)
	}
	if len(*raw.Alerts) != 0 {
		t.Errorf("expected empty alerts, got %v", *raw.Alerts)
	}
}

// AC-7: Handler nacheinander mit userA- und userB-Kontext → jeder nur eigene Counts.
func TestArchiveStatsHandler_IsolatedPerUser(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "userA", []map[string]interface{}{
		{"trip_id": "trip-A1", "kind": "morning", "sent_at": "2026-06-10T07:00:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-A1", "kind": "evening", "sent_at": "2026-06-10T18:00:00Z", "channels": []string{"email"}},
	})
	seedAlertLog(t, s.DataDir, "userA", []map[string]interface{}{
		{"trip_id": "trip-A1", "sent_at": "2026-06-10T09:00:00Z", "changes_count": 1, "severity": "LOW"},
	})
	seedBriefingLog(t, s.DataDir, "userB", []map[string]interface{}{
		{"trip_id": "trip-B1", "kind": "morning", "sent_at": "2026-06-11T07:00:00Z", "channels": []string{"telegram"}},
	})
	seedAlertLog(t, s.DataDir, "userB", []map[string]interface{}{
		{"trip_id": "trip-B1", "sent_at": "2026-06-11T10:00:00Z", "changes_count": 2, "severity": "MODERATE"},
		{"trip_id": "trip-B1", "sent_at": "2026-06-11T12:00:00Z", "changes_count": 1, "severity": "LOW"},
	})

	h := ArchiveStatsHandler(s)

	// userA
	reqA := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "userA")
	wA := httptest.NewRecorder()
	h.ServeHTTP(wA, reqA)
	if wA.Code != http.StatusOK {
		t.Fatalf("userA: expected 200, got %d: %s", wA.Code, wA.Body.String())
	}
	aBrief, aAlert := decodeCounts(t, wA)
	if aBrief["trip-A1"] != 2 {
		t.Errorf("userA: expected briefings trip-A1=2, got %v", aBrief["trip-A1"])
	}
	if aAlert["trip-A1"] != 1 {
		t.Errorf("userA: expected alerts trip-A1=1, got %v", aAlert["trip-A1"])
	}
	if _, leaked := aBrief["trip-B1"]; leaked {
		t.Errorf("cross-user leak: userB trip-B1 in userA briefings: %v", aBrief)
	}
	if _, leaked := aAlert["trip-B1"]; leaked {
		t.Errorf("cross-user leak: userB trip-B1 in userA alerts: %v", aAlert)
	}

	// userB
	reqB := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/archive/stats", nil), "userB")
	wB := httptest.NewRecorder()
	h.ServeHTTP(wB, reqB)
	if wB.Code != http.StatusOK {
		t.Fatalf("userB: expected 200, got %d: %s", wB.Code, wB.Body.String())
	}
	bBrief, bAlert := decodeCounts(t, wB)
	if bBrief["trip-B1"] != 1 {
		t.Errorf("userB: expected briefings trip-B1=1, got %v", bBrief["trip-B1"])
	}
	if bAlert["trip-B1"] != 2 {
		t.Errorf("userB: expected alerts trip-B1=2, got %v", bAlert["trip-B1"])
	}
	if _, leaked := bBrief["trip-A1"]; leaked {
		t.Errorf("cross-user leak: userA trip-A1 in userB briefings: %v", bBrief)
	}
	if _, leaked := bAlert["trip-A1"]; leaked {
		t.Errorf("cross-user leak: userA trip-A1 in userB alerts: %v", bAlert)
	}
}
