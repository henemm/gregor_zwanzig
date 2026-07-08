package scheduler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED: Issue #1114 — briefing_health Aggregat in /api/scheduler/status
//
// Spec: docs/specs/modules/issue_1114_briefing_health.md
//
// KEINE Mocks: echte Dateien in t.TempDir(), echter httptest-Roundtrip gegen
// den realen Handler (Muster: scheduler_subscription_status_test.go:107-142).

// newBriefingHealthTestScheduler builds a Scheduler backed by tmpDir, with the
// given userIDs registered (user.json written for each so ListUserIDs() sees
// them).
func newBriefingHealthTestScheduler(t *testing.T, tmpDir string, userIDs ...string) *Scheduler {
	t.Helper()
	s := store.New(tmpDir, "default")
	for _, uid := range userIDs {
		dir := filepath.Join(tmpDir, "users", uid)
		if err := os.MkdirAll(dir, 0755); err != nil {
			t.Fatalf("mkdir user dir: %v", err)
		}
		if err := os.WriteFile(filepath.Join(dir, "user.json"),
			[]byte(`{"id":"`+uid+`"}`), 0644); err != nil {
			t.Fatalf("write user.json: %v", err)
		}
	}

	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, s)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return sched
}

// writePendingBriefingsFile writes a real pending_briefings.json for userID
// with the given entries (JSON literal for entries array).
func writePendingBriefingsFile(t *testing.T, tmpDir, userID, entriesJSON string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "users", userID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	body := `{"entries":[` + entriesJSON + `]}`
	path := filepath.Join(dir, "pending_briefings.json")
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatalf("write pending_briefings.json: %v", err)
	}
}

// callStatusEndpoint performs a real HTTP roundtrip against the Status()
// handler, exactly like TestSchedulerStatusEndpointJSON.
func callStatusEndpoint(t *testing.T, sched *Scheduler) (int, map[string]any, string) {
	t.Helper()
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sched.Status())
	})

	req := httptest.NewRequest(http.MethodGet, "/api/scheduler/status", nil)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	rawBody := w.Body.String()
	var body map[string]any
	if err := json.Unmarshal([]byte(rawBody), &body); err != nil {
		t.Fatalf("JSON parse: %v", err)
	}
	return w.Code, body, rawBody
}

// AC-1: null state, no markers anywhere.
func TestBriefingHealthNullStateWhenNoMarkers(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1114-usera")

	code, body, _ := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}

	bh, ok := body["briefing_health"].(map[string]any)
	if !ok {
		t.Fatalf("briefing_health missing or wrong type: %v", body["briefing_health"])
	}
	if got := bh["open_pending_briefings"]; got != float64(0) {
		t.Errorf("open_pending_briefings: want 0, got %v", got)
	}
	if got := bh["degraded_segments_total"]; got != float64(0) {
		t.Errorf("degraded_segments_total: want 0, got %v", got)
	}
	if got := bh["oldest_pending_age_hours"]; got != float64(0) {
		t.Errorf("oldest_pending_age_hours: want 0, got %v", got)
	}
	if got := bh["last_provider_error_at"]; got != nil {
		t.Errorf("last_provider_error_at: want nil, got %v", got)
	}
}

// AC-2: aggregation across two real users.
func TestBriefingHealthAggregatesAcrossTwoUsers(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1114-usera", "tdd-1114-userb")

	now := time.Now().UTC().Format(time.RFC3339)
	writePendingBriefingsFile(t, tmpDir, "tdd-1114-usera",
		`{"trip_id":"trip-a1","report_type":"morning","date":"2026-07-08",`+
			`"slot_hour":7,"failed_segment_ids":["seg1","seg2"],"attempts":0,`+
			`"created_at":"`+now+`"}`)
	writePendingBriefingsFile(t, tmpDir, "tdd-1114-userb",
		`{"trip_id":"trip-b1","report_type":"evening","date":"2026-07-08",`+
			`"slot_hour":18,"failed_segment_ids":["seg3"],"attempts":0,`+
			`"created_at":"`+now+`"}`)

	code, body, _ := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh := body["briefing_health"].(map[string]any)

	if got := bh["open_pending_briefings"]; got != float64(2) {
		t.Errorf("open_pending_briefings: want 2, got %v", got)
	}
	if got := bh["degraded_segments_total"]; got != float64(3) {
		t.Errorf("degraded_segments_total: want 3, got %v", got)
	}
}

// AC-3: oldest marker across two users wins.
func TestBriefingHealthOldestMarkerWins(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1114-usera", "tdd-1114-userb")

	fiveHoursAgo := time.Now().UTC().Add(-5 * time.Hour).Format(time.RFC3339)
	oneHourAgo := time.Now().UTC().Add(-1 * time.Hour).Format(time.RFC3339)

	writePendingBriefingsFile(t, tmpDir, "tdd-1114-usera",
		`{"trip_id":"trip-a1","report_type":"morning","date":"2026-07-08",`+
			`"slot_hour":7,"failed_segment_ids":["seg1"],"attempts":0,`+
			`"created_at":"`+fiveHoursAgo+`"}`)
	writePendingBriefingsFile(t, tmpDir, "tdd-1114-userb",
		`{"trip_id":"trip-b1","report_type":"evening","date":"2026-07-08",`+
			`"slot_hour":18,"failed_segment_ids":["seg2"],"attempts":0,`+
			`"created_at":"`+oneHourAgo+`"}`)

	_, body, _ := callStatusEndpoint(t, sched)
	bh := body["briefing_health"].(map[string]any)

	age, ok := bh["oldest_pending_age_hours"].(float64)
	if !ok {
		t.Fatalf("oldest_pending_age_hours missing or wrong type: %v", bh["oldest_pending_age_hours"])
	}
	if age < 4.9 || age > 5.1 {
		t.Errorf("oldest_pending_age_hours: want ~5.0, got %v", age)
	}
}

// AC-4: Privacy — no user/trip identifiers leak into the public response.
func TestBriefingHealthResponseContainsNoUserIdentifiers(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1114-usera", "tdd-1114-userb")

	now := time.Now().UTC().Format(time.RFC3339)
	writePendingBriefingsFile(t, tmpDir, "tdd-1114-usera",
		`{"trip_id":"trip-a1","report_type":"morning","date":"2026-07-08",`+
			`"slot_hour":7,"failed_segment_ids":["seg1"],"attempts":0,`+
			`"created_at":"`+now+`"}`)
	writePendingBriefingsFile(t, tmpDir, "tdd-1114-userb",
		`{"trip_id":"trip-b1","report_type":"evening","date":"2026-07-08",`+
			`"slot_hour":18,"failed_segment_ids":["seg2"],"attempts":0,`+
			`"created_at":"`+now+`"}`)

	_, _, rawBody := callStatusEndpoint(t, sched)

	forbidden := []string{"tdd-1114-usera", "tdd-1114-userb", "trip-a1", "trip-b1"}
	for _, id := range forbidden {
		if strings.Contains(rawBody, id) {
			t.Errorf("Privacy-Leak: response contains identifier %q", id)
		}
	}
}

// AC-5: fail-soft when openmeteo_calls.jsonl is entirely absent.
func TestBriefingHealthNullProviderErrorWhenLogMissing(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1114-usera")

	// Explicitly ensure no diagnostics dir exists.
	diagDir := filepath.Join(tmpDir, "diagnostics")
	if _, err := os.Stat(diagDir); err == nil {
		t.Fatalf("diagnostics dir unexpectedly exists")
	}

	code, body, _ := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh := body["briefing_health"].(map[string]any)
	if got := bh["last_provider_error_at"]; got != nil {
		t.Errorf("last_provider_error_at: want nil, got %v", got)
	}
}

// Adversary F001: a pending_briefings.json marker must be counted even when
// its user directory has NO user.json (e.g. after an incomplete account
// deletion). ListUserIDs() only sees directories with user.json, so this
// case was silently dropped before the fix. This test MUST fail against the
// old ListUserIDs()-based enumeration and pass once markers are found via a
// direct glob over data/users/*/pending_briefings.json.
func TestBriefingHealthCountsMarkersWithoutUserJson(t *testing.T) {
	tmpDir := t.TempDir()
	// No newBriefingHealthTestScheduler user registration here on purpose:
	// the user directory must exist ONLY because of pending_briefings.json,
	// with no user.json ever written.
	sched := newBriefingHealthTestScheduler(t, tmpDir)

	now := time.Now().UTC().Format(time.RFC3339)
	writePendingBriefingsFile(t, tmpDir, "tdd-1114-orphan",
		`{"trip_id":"trip-orphan1","report_type":"morning","date":"2026-07-08",`+
			`"slot_hour":7,"failed_segment_ids":["seg1","seg2"],"attempts":0,`+
			`"created_at":"`+now+`"}`)

	// Sanity: confirm no user.json was written for this user directory.
	if _, err := os.Stat(filepath.Join(tmpDir, "users", "tdd-1114-orphan", "user.json")); err == nil {
		t.Fatalf("test setup error: user.json unexpectedly exists")
	}

	code, body, _ := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh := body["briefing_health"].(map[string]any)

	if got := bh["open_pending_briefings"]; got != float64(1) {
		t.Errorf("open_pending_briefings: want 1, got %v", got)
	}
	if got := bh["degraded_segments_total"]; got != float64(2) {
		t.Errorf("degraded_segments_total: want 2, got %v", got)
	}
}

// AC-6: existing Status() fields remain unchanged after the additive key.
func TestBriefingHealthExistingFieldsUnchanged(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "default")

	_, body, _ := callStatusEndpoint(t, sched)

	if _, ok := body["running"].(bool); !ok {
		t.Errorf("running: expected bool field present, got %v", body["running"])
	}
	if _, ok := body["jobs"].([]any); !ok {
		t.Errorf("jobs: expected array field present, got %v", body["jobs"])
	}
	if _, ok := body["timezone"].(string); !ok {
		t.Errorf("timezone: expected string field present, got %v", body["timezone"])
	}
	if _, ok := body["briefing_health"]; !ok {
		t.Errorf("briefing_health: expected additive field present")
	}
}
