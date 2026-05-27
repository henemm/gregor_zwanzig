package handler

// TDD RED: Issue #393 — Cockpit-Kacheln: GET /api/cockpit/status Handler.
// Spec: docs/specs/modules/issue_393_cockpit_kacheln.md (AC-3, AC-4, AC-5, AC-6, AC-7)
//
// CockpitStatusHandler existiert noch nicht → Paket kompiliert nicht → ALLE Tests ROT.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
)

// seedBriefingLog schreibt eine briefing_log.json in das Test-Store-Verzeichnis.
func seedBriefingLog(t *testing.T, dataDir, userID string, entries []map[string]interface{}) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", userID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatal(err)
	}
	data := map[string]interface{}{"entries": entries}
	b, _ := json.Marshal(data)
	if err := os.WriteFile(filepath.Join(dir, "briefing_log.json"), b, 0644); err != nil {
		t.Fatal(err)
	}
}

// seedAlertLog schreibt eine alert_log.json in das Test-Store-Verzeichnis.
func seedAlertLog(t *testing.T, dataDir, userID string, entries []map[string]interface{}) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", userID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatal(err)
	}
	data := map[string]interface{}{"entries": entries}
	b, _ := json.Marshal(data)
	if err := os.WriteFile(filepath.Join(dir, "alert_log.json"), b, 0644); err != nil {
		t.Fatal(err)
	}
}

// withUserCtx setzt eine User-ID im Request-Kontext (analog zum Auth-Middleware).
func withUserCtx(r *http.Request, userID string) *http.Request {
	ctx := middleware.ContextWithUserID(r.Context(), userID)
	return r.WithContext(ctx)
}

// AC-3: Leere Arrays wenn Log-Files nicht existieren — kein 500-Error.
func TestCockpitStatusHandler_EmptyWhenNoLogs(t *testing.T) {
	s := newTestStore(t)

	h := CockpitStatusHandler(s)
	req := httptest.NewRequest(http.MethodGet, "/api/cockpit/status", nil)
	req = withUserCtx(req, "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("response is not valid JSON: %v", err)
	}

	briefings, ok := resp["briefings"]
	if !ok {
		t.Fatal("response missing 'briefings' field")
	}
	alerts, ok := resp["alerts"]
	if !ok {
		t.Fatal("response missing 'alerts' field")
	}

	b, _ := briefings.([]interface{})
	a, _ := alerts.([]interface{})
	if len(b) != 0 {
		t.Errorf("expected empty briefings array, got %d entries", len(b))
	}
	if len(a) != 0 {
		t.Errorf("expected empty alerts array, got %d entries", len(a))
	}
}

// AC-4/5: Nur heutige Briefings werden zurückgegeben.
func TestCockpitStatusHandler_FiltersBriefingsByToday(t *testing.T) {
	s := newTestStore(t)
	today := time.Now().UTC().Format("2006-01-02")
	yesterday := time.Now().UTC().AddDate(0, 0, -1).Format("2006-01-02")

	seedBriefingLog(t, s.DataDir, "test", []map[string]interface{}{
		{"trip_id": "trip-1", "kind": "morning", "sent_at": today + "T07:03:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-1", "kind": "evening", "sent_at": yesterday + "T18:05:00Z", "channels": []string{"email"}},
	})

	h := CockpitStatusHandler(s)
	req := httptest.NewRequest(http.MethodGet, "/api/cockpit/status", nil)
	req = withUserCtx(req, "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	briefings := resp["briefings"].([]interface{})

	if len(briefings) != 1 {
		t.Fatalf("expected 1 briefing (today only), got %d", len(briefings))
	}
	entry := briefings[0].(map[string]interface{})
	if entry["kind"] != "morning" {
		t.Errorf("expected kind=morning, got %v", entry["kind"])
	}
}

// AC-6/7: Nur Alerts der letzten 24h werden zurückgegeben.
func TestCockpitStatusHandler_FiltersAlertsByLast24h(t *testing.T) {
	s := newTestStore(t)
	now := time.Now().UTC()
	recent := now.Add(-2 * time.Hour).Format(time.RFC3339)
	old := now.Add(-25 * time.Hour).Format(time.RFC3339)

	seedAlertLog(t, s.DataDir, "test", []map[string]interface{}{
		{"trip_id": "trip-1", "sent_at": recent, "changes_count": 2, "severity": "MODERATE"},
		{"trip_id": "trip-1", "sent_at": old, "changes_count": 1, "severity": "LOW"},
	})

	h := CockpitStatusHandler(s)
	req := httptest.NewRequest(http.MethodGet, "/api/cockpit/status", nil)
	req = withUserCtx(req, "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	alerts := resp["alerts"].([]interface{})

	if len(alerts) != 1 {
		t.Fatalf("expected 1 alert (last 24h only), got %d", len(alerts))
	}
	entry := alerts[0].(map[string]interface{})
	if entry["severity"] != "MODERATE" {
		t.Errorf("expected severity=MODERATE, got %v", entry["severity"])
	}
}

// AC-3: Response immer JSON mit beiden Feldern, auch wenn beide Log-Files leer sind.
func TestCockpitStatusHandler_ReturnsJsonStructure(t *testing.T) {
	s := newTestStore(t)

	h := CockpitStatusHandler(s)
	req := httptest.NewRequest(http.MethodGet, "/api/cockpit/status", nil)
	req = withUserCtx(req, "test")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	ct := w.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %s", ct)
	}

	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("not valid JSON: %v", err)
	}
	if _, hasBriefings := resp["briefings"]; !hasBriefings {
		t.Error("response missing 'briefings' key")
	}
	if _, hasAlerts := resp["alerts"]; !hasAlerts {
		t.Error("response missing 'alerts' key")
	}
}
