package scheduler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
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

// writeDiagnosticsLog writes a real data/diagnostics/openmeteo_calls.jsonl with
// the given raw JSONL lines (already-formatted JSON objects, one per line).
func writeDiagnosticsLog(t *testing.T, tmpDir string, lines ...string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir diagnostics: %v", err)
	}
	body := strings.Join(lines, "\n") + "\n"
	path := filepath.Join(dir, "openmeteo_calls.jsonl")
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatalf("write openmeteo_calls.jsonl: %v", err)
	}
}

// Issue #1115 AC-4: a persistently failing model channel must stay visible even
// while briefings keep going out via the intra-Open-Meteo fallback. The health
// signal must grow with outage duration: provider_error_streak_since points at
// the earliest error of the current contiguous streak, and
// provider_errors_recent_count counts briefing errors in the last 24h. A single
// old error outside 24h must NOT inflate recent_count nor extend the streak.
//
// KEINE Mocks: a real openmeteo_calls.jsonl in t.TempDir(), real BriefingHealth().
func TestBriefingHealthProviderErrorStreakGrowsWithDuration(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1115-usera")

	now := time.Now().UTC()
	streakStart := now.Add(-3 * time.Hour)
	// REAL production format: the writer (src/providers/call_log.py) records an
	// HTTP outage as {"status":503,"error":null} — error is NEVER a string for a
	// status failure. A 503 with error:null IS the outage signal; a 200 is a
	// success. See the confirmed real line in data/diagnostics/openmeteo_calls.jsonl.
	line := func(ts time.Time, source string, status int) string {
		return `{"ts":"` + ts.Format(time.RFC3339) + `","endpoint":"/v1/dwd-icon",` +
			`"status":` + strconv.Itoa(status) + `,"source":"` + source + `","error":null}`
	}
	// Pure network failure: no HTTP response, so status is null and error is set.
	netErrLine := func(ts time.Time, source string) string {
		return `{"ts":"` + ts.Format(time.RFC3339) + `","endpoint":"/v1/dwd-icon",` +
			`"status":null,"source":"` + source + `","error":"read tcp: connection timeout"}`
	}

	writeDiagnosticsLog(t, tmpDir,
		// Old, isolated 503 outage 48h ago: outside 24h AND separated from the
		// current streak by a >2h gap — must NOT count.
		line(now.Add(-48*time.Hour), "briefing", 503),
		// A successful briefing call (status 200, error null) must be ignored.
		line(now.Add(-90*time.Minute), "briefing", 200),
		// A 4xx content error (e.g. #353 date-out-of-range) must NOT count as an
		// outage — otherwise every bad request would raise a false alarm.
		line(now.Add(-80*time.Minute), "briefing", 400),
		// Current contiguous streak: two 503/null outages + one pure network
		// failure, ~1h apart (gaps <= 2h). All three are real outage forms.
		line(streakStart, "briefing", 503),
		netErrLine(now.Add(-2*time.Hour), "briefing"),
		line(now.Add(-1*time.Hour), "briefing", 503),
		// A non-briefing outage (e.g. alert probe) must be ignored (source filter).
		line(now.Add(-30*time.Minute), "alert", 503),
	)

	code, body, _ := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh := body["briefing_health"].(map[string]any)

	// recent_count: the three streak errors within 24h — the 48h-old one and
	// the non-briefing/successful entries must be excluded.
	if got := bh["provider_errors_recent_count"]; got != float64(3) {
		t.Errorf("provider_errors_recent_count: want 3, got %v", got)
	}

	sinceRaw, ok := bh["provider_error_streak_since"].(string)
	if !ok {
		t.Fatalf("provider_error_streak_since missing or wrong type: %v", bh["provider_error_streak_since"])
	}
	since, err := time.Parse(time.RFC3339, sinceRaw)
	if err != nil {
		t.Fatalf("provider_error_streak_since not RFC3339: %v", err)
	}
	// Streak start is the earliest error of the current streak (~3h ago), NOT
	// the isolated 48h-old error.
	if diff := since.Sub(streakStart); diff < -2*time.Second || diff > 2*time.Second {
		t.Errorf("provider_error_streak_since: want ~%v (start of current streak), got %v",
			streakStart.Format(time.RFC3339), sinceRaw)
	}

	// The duration signal must grow with the outage: now - streak_since ~ 3h,
	// which is strictly larger than a fresh (just-started) outage would yield.
	age := now.Sub(since)
	if age < 2*time.Hour+55*time.Minute || age > 3*time.Hour+5*time.Minute {
		t.Errorf("outage duration (now - streak_since): want ~3h, got %v", age)
	}
}

// Issue #1115 AC-4: a single old briefing error outside the 24h window must not
// register as a recent outage (no false-positive escalation), and a missing log
// yields the null signal (fail-soft).
func TestBriefingHealthProviderErrorStreakSilentWhenOnlyOld(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1115-usera")

	old := time.Now().UTC().Add(-48 * time.Hour).Format(time.RFC3339)
	// REAL production format: 503 outage carries error:null.
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+old+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`)

	_, body, _ := callStatusEndpoint(t, sched)
	bh := body["briefing_health"].(map[string]any)

	if got := bh["provider_errors_recent_count"]; got != float64(0) {
		t.Errorf("provider_errors_recent_count: want 0 for only-old error, got %v", got)
	}
	if got := bh["provider_error_streak_since"]; got != nil {
		t.Errorf("provider_error_streak_since: want nil for only-old error, got %v", got)
	}
}

// Issue #1115 AC-4 (false-alarm guard): a 4xx briefing line (content error such
// as #353 date-out-of-range, written as status:400/error:null) must NOT register
// as a provider outage — otherwise a routine bad request would falsely escalate.
func TestBriefingHealthFourxxIsNotProviderOutage(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1115-usera")

	now := time.Now().UTC().Add(-1 * time.Hour).Format(time.RFC3339)
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+now+`","endpoint":"/v1/dwd-icon","status":400,"source":"briefing","error":null}`)

	_, body, _ := callStatusEndpoint(t, sched)
	bh := body["briefing_health"].(map[string]any)

	if got := bh["provider_errors_recent_count"]; got != float64(0) {
		t.Errorf("provider_errors_recent_count: want 0 for 4xx content error, got %v", got)
	}
	if got := bh["provider_error_streak_since"]; got != nil {
		t.Errorf("provider_error_streak_since: want nil for 4xx content error, got %v", got)
	}
	if got := bh["last_provider_error_at"]; got != nil {
		t.Errorf("last_provider_error_at: want nil for 4xx content error, got %v", got)
	}
}

// Issue #1115 AC-4: a pure network failure (no HTTP response, so status:null and
// error populated) must still count as a provider outage — this is the only case
// the inherited #1114 error!=nil check covered, and it must keep working.
func TestBriefingHealthNetworkErrorCountsAsOutage(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1115-usera")

	ts := time.Now().UTC().Add(-30 * time.Minute).Format(time.RFC3339)
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+ts+`","endpoint":"/v1/dwd-icon","status":null,"source":"briefing","error":"read tcp: connection timeout"}`)

	_, body, _ := callStatusEndpoint(t, sched)
	bh := body["briefing_health"].(map[string]any)

	if got := bh["provider_errors_recent_count"]; got != float64(1) {
		t.Errorf("provider_errors_recent_count: want 1 for network error, got %v", got)
	}
	if _, ok := bh["provider_error_streak_since"].(string); !ok {
		t.Errorf("provider_error_streak_since: want RFC3339 string for network error, got %v", bh["provider_error_streak_since"])
	}
	if got := bh["last_provider_error_at"]; got != ts {
		t.Errorf("last_provider_error_at: want %q for network error, got %v", ts, got)
	}
}

// Issue #1115 F002: the night briefing weather fetch is written with source
// "briefing_nacht" (src/providers/call_log.py's _fetch_night_weather). It is a
// CORE briefing fetch, so a 503 outage on that source MUST count — otherwise a
// persistent night-only outage would stay invisible to the AC-4 escalation
// signal (the exact "silently degraded persistent state" AC-4 rules out).
//
// KEINE Mocks: a real openmeteo_calls.jsonl in t.TempDir(), real BriefingHealth().
func TestBriefingHealthNightBriefingCountsAsOutage(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1115-usera")

	ts := time.Now().UTC().Add(-30 * time.Minute).Format(time.RFC3339)
	// REAL production form of a night-briefing outage: 503 with error:null.
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+ts+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing_nacht","error":null}`)

	_, body, _ := callStatusEndpoint(t, sched)
	bh := body["briefing_health"].(map[string]any)

	if got := bh["provider_errors_recent_count"]; got != float64(1) {
		t.Errorf("provider_errors_recent_count: want 1 for briefing_nacht outage, got %v", got)
	}
	if _, ok := bh["provider_error_streak_since"].(string); !ok {
		t.Errorf("provider_error_streak_since: want RFC3339 string for briefing_nacht outage, got %v", bh["provider_error_streak_since"])
	}
	if got := bh["last_provider_error_at"]; got != ts {
		t.Errorf("last_provider_error_at: want %q for briefing_nacht outage, got %v", ts, got)
	}
}

// Issue #1115 F002 (false-alarm guard): an enrichment source (e.g. "ensemble"
// or "vergleich") is NOT a core briefing fetch. A 503 there is not a briefing
// outage and must NOT register — otherwise an enrichment hiccup would falsely
// escalate the briefing-health signal.
func TestBriefingHealthEnrichmentSourceIsNotBriefingOutage(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1115-usera")

	e1 := time.Now().UTC().Add(-30 * time.Minute).Format(time.RFC3339)
	e2 := time.Now().UTC().Add(-20 * time.Minute).Format(time.RFC3339)
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+e1+`","endpoint":"/v1/dwd-icon","status":503,"source":"ensemble","error":null}`,
		`{"ts":"`+e2+`","endpoint":"/v1/dwd-icon","status":503,"source":"vergleich","error":null}`)

	_, body, _ := callStatusEndpoint(t, sched)
	bh := body["briefing_health"].(map[string]any)

	if got := bh["provider_errors_recent_count"]; got != float64(0) {
		t.Errorf("provider_errors_recent_count: want 0 for enrichment outage, got %v", got)
	}
	if got := bh["provider_error_streak_since"]; got != nil {
		t.Errorf("provider_error_streak_since: want nil for enrichment outage, got %v", got)
	}
	if got := bh["last_provider_error_at"]; got != nil {
		t.Errorf("last_provider_error_at: want nil for enrichment outage, got %v", got)
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
