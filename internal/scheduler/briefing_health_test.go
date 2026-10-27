package scheduler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
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

// AC-6 (Issue #1581): Waechter ueber coreBriefingSources selbst.
//
// coreBriefingSources entscheidet, welcher Diagnose-Quellname als ECHTER
// Briefing-Ausfall zaehlt. Traegt jemand dort eine Anreicherungsquelle ein
// ("thunder", "radar_nowcast", "geosphere_clouds", ...), meldet
// check-gregor20.sh kuenftig einen Briefing-Ausfall, obwohl nur eine
// nicht-briefing-kritische Anreicherung ausgefallen ist — genau die
// Vermengung, vor der ADR-0018 warnt und die #1581 mit einem EIGENEN Kanal
// (enrichment_health) vermeidet.
//
// Geprueft wird auf GLEICHHEIT der Map, nicht nur auf Anwesenheit der beiden
// Kernquellen: sonst faengt der Test einen zusaetzlichen Eintrag nicht.
func TestCoreBriefingSourcesEnthaeltGenauDieBeidenBriefingQuellen(t *testing.T) {
	erwartet := map[string]bool{"briefing": true, "briefing_nacht": true}

	if len(coreBriefingSources) != len(erwartet) {
		t.Fatalf("coreBriefingSources hat %d Eintraege statt %d: %#v — eine Anreicherungsquelle gehoert in enrichment_health (#1581), nicht hierher",
			len(coreBriefingSources), len(erwartet), coreBriefingSources)
	}
	for name, want := range erwartet {
		got, vorhanden := coreBriefingSources[name]
		if !vorhanden {
			t.Errorf("coreBriefingSources[%q] fehlt — beide Briefing-Abrufe (Tag und Nacht) sind briefing-kritisch (#1115 F002)", name)
			continue
		}
		if got != want {
			t.Errorf("coreBriefingSources[%q] = %v, erwartet %v", name, got, want)
		}
	}
	for name := range coreBriefingSources {
		if _, erlaubt := erwartet[name]; !erlaubt {
			t.Errorf("coreBriefingSources enthaelt den zusaetzlichen Schluessel %q — ein Ausfall dort waere ab sofort ein gemeldeter BRIEFING-Ausfall. Anreicherungs-Pfade gehoeren nach enrichment_health (#1581 AC-6)", name)
		}
	}
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

// Issue #1262 AC-4: corrupt_trips_total aggregates
// users/<uid>/diagnostics/corrupt_trips.json (written by Python's
// record_corrupt_trip_observability) across ALL users, privacy-safe (only
// counts + timestamp, no user_id/filenames in the response).
func TestBriefingHealthCorruptTripsTotalAggregatesAcrossUsers(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1262-usera", "tdd-1262-userb")

	writeCorruptTripsFile(t, tmpDir, "tdd-1262-usera", 2, "2026-07-16T10:00:00Z")
	writeCorruptTripsFile(t, tmpDir, "tdd-1262-userb", 1, "2026-07-16T12:00:00Z")

	code, body, rawBody := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh := body["briefing_health"].(map[string]any)

	if got := bh["corrupt_trips_total"]; got != float64(3) {
		t.Errorf("corrupt_trips_total: want 3, got %v", got)
	}
	if got := bh["corrupt_trips_last_run_at"]; got != "2026-07-16T12:00:00Z" {
		t.Errorf("corrupt_trips_last_run_at: want jüngstes last_run, got %v", got)
	}

	forbidden := []string{"tdd-1262-usera", "tdd-1262-userb"}
	for _, id := range forbidden {
		if strings.Contains(rawBody, id) {
			t.Errorf("Privacy-Leak: response contains identifier %q", id)
		}
	}
}

// Fail-soft: no diagnostics/corrupt_trips.json anywhere -> zero total, nil
// timestamp, no panic.
func TestBriefingHealthCorruptTripsTotalZeroWhenNoFiles(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1262-usera")

	code, body, _ := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh := body["briefing_health"].(map[string]any)

	if got := bh["corrupt_trips_total"]; got != float64(0) {
		t.Errorf("corrupt_trips_total: want 0, got %v", got)
	}
	if got := bh["corrupt_trips_last_run_at"]; got != nil {
		t.Errorf("corrupt_trips_last_run_at: want nil, got %v", got)
	}
}

// writeCorruptTripsFile writes a real users/<uid>/diagnostics/corrupt_trips.json
// (Python-written shape: notified/last_skipped_count/last_run). Only the
// last_skipped_count/last_run fields are relevant to the Go aggregate.
func writeCorruptTripsFile(t *testing.T, tmpDir, userID string, lastSkippedCount int, lastRun string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "users", userID, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	body := `{"notified":[],"last_skipped_count":` + strconv.Itoa(lastSkippedCount) +
		`,"last_run":"` + lastRun + `"}`
	path := filepath.Join(dir, "corrupt_trips.json")
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatalf("write corrupt_trips.json: %v", err)
	}
}

// Issue #1421: the real 2026-07-29 incident. providerErrorStreakGapThreshold
// (2h) is applied when walking BACK from the newest error to find the streak
// start, but was never checked FORWARD against "now" — so a streak that has
// long since gone quiet keeps being reported as an ongoing outage. This test
// reproduces the incident directly: a burst of four errors around 05:00:04
// UTC, then silence, queried 8h later (the monitor's actual query pattern).
//
// AC-1: the ongoing-outage field must be empty once the newest error is
// farther in the past than the gap threshold.
// AC-3 (bundled): the 24h error-frequency count must be unaffected by AC-1 —
// all four errors are still within the 24h window and must still be counted.
//
// Calls analyzeBriefingProviderErrors directly (not via HTTP): the function
// already takes `now` as a parameter, so the incident's exact timestamps can
// be reproduced without depending on wall-clock timing during the test run.
func TestProviderErrorStreakEndsWhenQueriedLongAfterLastError(t *testing.T) {
	tmpDir := t.TempDir()
	incidentStart := time.Date(2026, 7, 29, 5, 0, 4, 0, time.UTC)
	queriedAt := incidentStart.Add(8 * time.Hour)
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+incidentStart.Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		`{"ts":"`+incidentStart.Add(15*time.Second).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		`{"ts":"`+incidentStart.Add(30*time.Second).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		`{"ts":"`+incidentStart.Add(45*time.Second).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
	)

	since, recent := analyzeBriefingProviderErrors(tmpDir, queriedAt)

	if since != "" {
		t.Errorf("streakSince: want empty (queried %v after last error, beyond the %v gap threshold), got %q",
			queriedAt.Sub(incidentStart), providerErrorStreakGapThreshold, since)
	}
	if recent != 4 {
		t.Errorf("recentCount: want 4 (all four errors still within 24h), got %d", recent)
	}
}

// Issue #1421 AC-2 (the counter-proof — MUST stay green): a genuinely ongoing
// outage with error gaps under the threshold, spread over several hours, must
// keep reporting the true streak start. This guards against a fix that
// silences real outages instead of just clearing finished ones.
func TestProviderErrorStreakStaysOpenWhileGapsUnderThreshold(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Date(2026, 7, 29, 13, 0, 0, 0, time.UTC)
	streakStart := now.Add(-6 * time.Hour)
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+streakStart.Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		`{"ts":"`+streakStart.Add(90*time.Minute).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		`{"ts":"`+streakStart.Add(3*time.Hour).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		`{"ts":"`+streakStart.Add(4*time.Hour+30*time.Minute).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		// last error 90min before "now" — still within the gap threshold, so
		// the outage must still read as ongoing.
		`{"ts":"`+now.Add(-90*time.Minute).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
	)

	since, recent := analyzeBriefingProviderErrors(tmpDir, now)

	want := streakStart.Format(time.RFC3339)
	if since != want {
		t.Errorf("streakSince: want %q (still-ongoing outage, all gaps <=90min), got %q", want, since)
	}
	if recent != 5 {
		t.Errorf("recentCount: want 5, got %d", recent)
	}
}

// Issue #1421 (adversary boundary check): the gap threshold must be applied
// symmetrically forward and backward. A latest error just OUTSIDE the
// threshold ends the outage; the existing backward walk
// (briefing_health.go:242) treats a gap exactly AT the threshold as still
// connected (">" not ">="), so the forward check must match that same
// operator for consistency — this test picks "threshold + 1s" to stay
// unambiguously on the "ended" side regardless of which operator is used.
func TestProviderErrorStreakEndsJustOverGapThreshold(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Date(2026, 7, 29, 13, 0, 0, 0, time.UTC)
	errAt := now.Add(-providerErrorStreakGapThreshold - time.Second)
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+errAt.Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
	)

	if since, _ := analyzeBriefingProviderErrors(tmpDir, now); since != "" {
		t.Errorf("gap %v (threshold+1s): want ended outage (empty streakSince), got %q", now.Sub(errAt), since)
	}
}

// Issue #1421 (adversary boundary check, other direction): a latest error
// just INSIDE the gap threshold must still read as an ongoing outage — the
// fix must not shrink the threshold.
func TestProviderErrorStreakStillOngoingJustUnderGapThreshold(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Date(2026, 7, 29, 13, 0, 0, 0, time.UTC)
	errAt := now.Add(-providerErrorStreakGapThreshold + time.Second)
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+errAt.Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
	)

	since, _ := analyzeBriefingProviderErrors(tmpDir, now)
	want := errAt.Format(time.RFC3339)
	if since != want {
		t.Errorf("gap %v (threshold-1s): want ongoing outage, streakSince=%q, got %q", now.Sub(errAt), want, since)
	}
}

// Issue #1421 AC-3 + AC-4: an outage that has ended (latest error farther in
// the past than the gap threshold) must still surface its 24h error
// frequency (AC-3), but the ongoing-outage field itself must be a real Go
// nil — not the empty string — so the external monitor (which distinguishes
// both) does not keep escalating a finished outage (AC-4).
//
// Calls sched.BriefingHealth() directly (not via HTTP/JSON round-trip): AC-4
// requires the check at the map-building call site (briefing_health.go:118-121),
// which decides whether to store the inner function's "" return value into the
// map at all — not just at analyzeBriefingProviderErrors' return value.
//
// KEINE Mocks: real openmeteo_calls.jsonl in t.TempDir(), real BriefingHealth().
func TestBriefingHealthEndedOutageKeepsCountButClearsStreakField(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-1421-usera")

	now := time.Now().UTC()
	// Mirrors the real 2026-07-29 incident: a short burst of errors, then
	// silence well beyond the 2h gap threshold (here: 8h, like the incident).
	base := now.Add(-8 * time.Hour)
	writeDiagnosticsLog(t, tmpDir,
		`{"ts":"`+base.Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		`{"ts":"`+base.Add(15*time.Second).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		`{"ts":"`+base.Add(30*time.Second).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
		`{"ts":"`+base.Add(45*time.Second).Format(time.RFC3339)+`","endpoint":"/v1/dwd-icon","status":503,"source":"briefing","error":null}`,
	)

	bh := sched.BriefingHealth()

	if got := bh["provider_errors_recent_count"]; got != 4 {
		t.Errorf("provider_errors_recent_count: want 4 (AC-3: 24h frequency must survive), got %v", got)
	}
	if got := bh["provider_error_streak_since"]; got != nil {
		t.Errorf("provider_error_streak_since: want real nil (AC-1/AC-4: outage ended 8h ago, beyond the %v gap threshold), got %#v (%T)",
			providerErrorStreakGapThreshold, got, got)
	}
}

// ---------------------------------------------------------------------------
// TDD RED — Issue #2073 Scheibe 2 (AC-10 bis AC-13): Betreiber-Aggregat über
// das nutzerbezogene Journal users/<uid>/diagnostics/
// track_resolution_failures.jsonl, geschrieben von
// src/services/track_resolution_health.py.
//
// Spec: docs/specs/modules/fix_2073_s2_sichtbarer_fehlschlag.md
//
// Bauart-Zwilling zu analyzeAlertAnchorRejections (#1661): gleiche zwei
// Signale (streakSince + recentCount), gleiche Datenschutzgrenze (#252).
//
// OFFENER PUNKT (bewusst NICHT gepinnt): die Gap-Schwelle. Die Spec lässt sie
// offen ("Kadenzwahl dort begründen"), deshalb liegen alle Zeitstempel hier
// nur 5 Minuten auseinander — unter jeder plausiblen Schwelle. Der Zuschnitt
// verdient eine eigene Begründung in der GREEN-Phase: _failed_lookups dämpft
// auf HÖCHSTENS EINE Zeile je Etappe und Prozess, ein dauerhaft defekter Trip
// erzeugt also nach der ersten Zeile tagelang keine weitere. Eine kurze
// Schwelle (60 min wie beim Anker) ließe den Streak fast sofort auslaufen,
// obwohl die Degradierung anhält — das wäre kein mit der Ausfalldauer
// WACHSENDES Signal im Sinne von ADR-0018.
// ---------------------------------------------------------------------------

// writeTrackResolutionJournal writes a real
// users/<uid>/diagnostics/track_resolution_failures.jsonl from the given RAW
// lines — raw on purpose, so AC-13 can inject a deliberately corrupt one.
func writeTrackResolutionJournal(t *testing.T, tmpDir, userID string, lines ...string) {
	t.Helper()
	dir := filepath.Join(tmpDir, "users", userID, "diagnostics")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	body := strings.Join(lines, "\n") + "\n"
	path := filepath.Join(dir, "track_resolution_failures.jsonl")
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatalf("write track_resolution_failures.jsonl: %v", err)
	}
}

// trackResolutionFailureLine builds one FULL journal line, exactly as the
// Python writer produces it (ts + trip_id + stage_id + reason + detail).
// Deliberately full: AC-11 requires that the Go side counts such a line
// correctly while decoding nothing but the timestamp.
func trackResolutionFailureLine(ts time.Time, tripID, stageID, reason string) string {
	return `{"ts":"` + ts.Format(time.RFC3339) +
		`","trip_id":"` + tripID +
		`","stage_id":"` + stageID +
		`","reason":"` + reason +
		`","detail":111.0}`
}

// AC-10 (Aggregat): zwei Nutzer, je ein Fehlschlag innerhalb der Gap-Schwelle
// -> recentCount summiert beide, streakSince nennt den FRÜHESTEN Zeitpunkt
// der zusammenhängenden Serie.
func TestTrackResolutionFailuresAggregateAcrossTwoUsers(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC().Truncate(time.Second)
	frueh := now.Add(-10 * time.Minute)
	spaet := now.Add(-5 * time.Minute)

	writeTrackResolutionJournal(t, tmpDir, "tdd-2073-s2-anna",
		trackResolutionFailureLine(frueh, "tour-anna", "T1", "no_candidate_within_tolerance"))
	writeTrackResolutionJournal(t, tmpDir, "tdd-2073-s2-bodo",
		trackResolutionFailureLine(spaet, "tour-bodo", "T2", "ambiguous_result"))

	since, recent := analyzeTrackResolutionFailures(tmpDir, now)

	if recent != 2 {
		t.Errorf("recentCount: want 2 (über BEIDE Nutzer summiert), got %d", recent)
	}
	if want := frueh.Format(time.RFC3339); since != want {
		t.Errorf("streakSince: want %s (frühester Zeitpunkt der Serie), got %q", want, since)
	}
}

// AC-10 (Status-Endpunkt): dieselben zwei Signale erscheinen als
// Top-Level-Schlüssel unter briefing_health — und der ausgegebene Körper
// trägt KEINE Nutzer-, Trip- oder Etappenkennung (AC-11, Datenschutz #252).
func TestTrackResolutionFailureStatusKeysCarryNoIdentifiers(t *testing.T) {
	tmpDir := t.TempDir()
	sched := newBriefingHealthTestScheduler(t, tmpDir, "tdd-2073-s2-anna", "tdd-2073-s2-bodo")
	now := time.Now().UTC().Truncate(time.Second)
	frueh := now.Add(-10 * time.Minute)

	writeTrackResolutionJournal(t, tmpDir, "tdd-2073-s2-anna",
		trackResolutionFailureLine(frueh, "tour-anna", "T1", "no_candidate_within_tolerance"))
	writeTrackResolutionJournal(t, tmpDir, "tdd-2073-s2-bodo",
		trackResolutionFailureLine(now.Add(-5*time.Minute), "tour-bodo", "T2", "ambiguous_result"))

	code, body, rawBody := callStatusEndpoint(t, sched)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}
	bh := body["briefing_health"].(map[string]any)

	if got := bh["track_resolution_failures_recent_count"]; got != float64(2) {
		t.Errorf("track_resolution_failures_recent_count: want 2, got %v", got)
	}
	if got := bh["track_resolution_failure_streak_since"]; got != frueh.Format(time.RFC3339) {
		t.Errorf("track_resolution_failure_streak_since: want %s, got %v",
			frueh.Format(time.RFC3339), got)
	}

	verboten := []string{
		"tdd-2073-s2-anna", "tdd-2073-s2-bodo", // Nutzerkennung
		"tour-anna", "tour-bodo", // Trip-Kennung
		"no_candidate_within_tolerance", "ambiguous_result", // Grund
	}
	for _, id := range verboten {
		if strings.Contains(rawBody, id) {
			t.Errorf("Datenschutzgrenze #252 verletzt: Antwort enthält %q", id)
		}
	}
}

// AC-11: die Decoder-Struct trägt AUSSCHLIESSLICH den Zeitstempel — wie
// anchorRejectedEntry. Eine volle Journalzeile (mit trip_id/stage_id/reason)
// wird trotzdem korrekt gezählt: json.Unmarshal ignoriert Unbekanntes, und es
// wird nichts davon weitergereicht.
func TestTrackResolutionFailureEntryDecodesOnlyTheTimestamp(t *testing.T) {
	typ := reflect.TypeOf(trackResolutionFailureEntry{})
	if typ.NumField() != 1 {
		t.Fatalf("Datenschutzgrenze #252: die Decoder-Struct darf GENAU ein Feld "+
			"tragen (nur den Zeitstempel), hat aber %d", typ.NumField())
	}
	if name := typ.Field(0).Name; name != "Ts" {
		t.Errorf("das einzige Feld muss der Zeitstempel sein, ist %q", name)
	}

	tmpDir := t.TempDir()
	now := time.Now().UTC().Truncate(time.Second)
	writeTrackResolutionJournal(t, tmpDir, "tdd-2073-s2-voll",
		trackResolutionFailureLine(now.Add(-5*time.Minute), "tour-voll", "T3", "implausible_measurement"))

	_, recent := analyzeTrackResolutionFailures(tmpDir, now)
	if recent != 1 {
		t.Errorf("eine VOLLE Journalzeile muss trotzdem zählen: want 1, got %d", recent)
	}
}

// AC-10 (Adversary-Finding F003): "Fehlschlaege der LETZTEN 24 h" — ein
// Eintrag ausserhalb des Fensters darf den Recent-Count nicht aufblaehen. Ohne
// diesen Waechter laesst sich der Zeitfilter ersatzlos entfernen
// (recentCount := len(failureTimes)), ohne dass ein Test rot wird — der Kern
// von "recent" waere dann ungeprueft.
//
// Beide Eintraege liegen im SELBEN Journal, damit der Test nicht versehentlich
// nur die Nutzer-Aggregation prueft. Der alte Eintrag liegt zugleich weiter
// zurueck als die Gap-Schwelle, der frische innerhalb — streakSince muss also
// den FRISCHEN nennen und darf nicht ueber die Luecke hinweg zusammenlaufen.
func TestTrackResolutionFailuresRecentCountExcludesEntriesOlderThan24h(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC().Truncate(time.Second)
	alt := now.Add(-30 * time.Hour)   // ausserhalb der 24h
	frisch := now.Add(-2 * time.Hour) // innerhalb der 24h

	writeTrackResolutionJournal(t, tmpDir, "tdd-2073-s2-fenster",
		trackResolutionFailureLine(alt, "tour-alt", "T1", "no_candidate_within_tolerance"),
		trackResolutionFailureLine(frisch, "tour-frisch", "T2", "ambiguous_result"))

	since, recent := analyzeTrackResolutionFailures(tmpDir, now)

	if recent != 1 {
		t.Errorf("recentCount: want 1 (nur der Eintrag von vor %v zaehlt, der von vor %v ist aelter als 24h), got %d",
			now.Sub(frisch), now.Sub(alt), recent)
	}
	if want := frisch.Format(time.RFC3339); since != want {
		t.Errorf("streakSince: want %s (der alte Eintrag liegt jenseits der Gap-Schwelle), got %q", want, since)
	}
}

// Adversary-Finding F002: die Gap-Schwelle war nur in eine Richtung bewacht —
// alle Fixtures nutzten Luecken von 5-10 Minuten, eine Vergroesserung der
// Konstante auf einen praktisch unendlichen Wert liess alles gruen (Mutation
// M12: 26h -> 100000h). Ein Streak, der beliebig weit zurueckreicht, meldet
// eine laengst beendete Degradierung als andauernd.
//
// Die Luecken sind deshalb bewusst ABSOLUT gewaehlt, nicht aus der Konstante
// abgeleitet: eine aus der Konstante berechnete Luecke waechst mit der
// Mutation mit und faengt sie nie. Geprueft wird damit das Band, das die
// dokumentierte Begruendung der Konstante aufspannt (Tages-Rhythmus aus
// Briefing/Deploy): eine Luecke von 12h muss verbinden, eine von 48h nicht.
// Der exakte Zahlenwert bleibt frei waehlbar, solange er in diesem Band liegt.
func TestTrackResolutionFailureStreakDoesNotBridgeGapOverThreshold(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC().Truncate(time.Second)
	// Der spaetere Eintrag liegt 1h vor "jetzt", damit der Streak ueberhaupt
	// noch laeuft; der fruehere 48h davor, also jenseits jedes plausiblen
	// Tages-Rhythmus.
	spaet := now.Add(-1 * time.Hour)
	frueh := spaet.Add(-48 * time.Hour)

	writeTrackResolutionJournal(t, tmpDir, "tdd-2073-s2-luecke",
		trackResolutionFailureLine(frueh, "tour-x", "T1", "ambiguous_result"),
		trackResolutionFailureLine(spaet, "tour-x", "T2", "ambiguous_result"))

	since, _ := analyzeTrackResolutionFailures(tmpDir, now)

	if want := spaet.Format(time.RFC3339); since != want {
		t.Errorf("streakSince: want %s — die Luecke von 48h ueberschreitet die Schwelle %v, der Streak darf nicht bis %s zurueckreichen; got %q",
			want, trackResolutionFailureStreakGapThreshold,
			frueh.Format(time.RFC3339), since)
	}

	// Positivkontrolle: dieselben zwei Eintraege mit einer Luecke von 12h
	// laufen sehr wohl zu einem Streak zusammen. Ohne sie bewiese der spaete
	// Zeitpunkt oben nichts — er ergaebe sich auch, wenn der Rueckwaertslauf
	// ueberhaupt nicht arbeitete oder die Schwelle auf 0 stuende.
	nahDir := t.TempDir()
	nah := spaet.Add(-12 * time.Hour)
	writeTrackResolutionJournal(t, nahDir, "tdd-2073-s2-luecke-nah",
		trackResolutionFailureLine(nah, "tour-x", "T1", "ambiguous_result"),
		trackResolutionFailureLine(spaet, "tour-x", "T2", "ambiguous_result"))

	sinceNah, _ := analyzeTrackResolutionFailures(nahDir, now)
	if want := nah.Format(time.RFC3339); sinceNah != want {
		t.Errorf("Positivkontrolle gescheitert: bei einer Luecke von 12h (innerhalb der Schwelle %v) muss der Streak bis %s zurueckreichen, got %q",
			trackResolutionFailureStreakGapThreshold, want, sinceNah)
	}
}

// AC-12: kein Journal vorhanden (frischer Deploy) -> Leer-/Null-Defaults,
// kein Fehler, kein Panic.
func TestTrackResolutionFailuresZeroWhenNoJournalExists(t *testing.T) {
	tmpDir := t.TempDir()

	since, recent := analyzeTrackResolutionFailures(tmpDir, time.Now().UTC())

	if since != "" {
		t.Errorf("streakSince: want \"\" ohne Journal, got %q", since)
	}
	if recent != 0 {
		t.Errorf("recentCount: want 0 ohne Journal, got %d", recent)
	}
}

// AC-13: eine beschädigte Zeile zwischen zwei gültigen wird übersprungen, die
// beiden gültigen zählen weiter — fail-soft, kein Absturz.
func TestTrackResolutionFailuresSkipCorruptLineBetweenValidOnes(t *testing.T) {
	tmpDir := t.TempDir()
	now := time.Now().UTC().Truncate(time.Second)
	erste := now.Add(-10 * time.Minute)
	zweite := now.Add(-5 * time.Minute)

	writeTrackResolutionJournal(t, tmpDir, "tdd-2073-s2-kaputt",
		trackResolutionFailureLine(erste, "tour-x", "T1", "ambiguous_result"),
		`{"ts":"2026-08-22T10:00:00Z","trip_id":`, // abgeschnitten, kein gültiges JSON
		trackResolutionFailureLine(zweite, "tour-x", "T2", "ambiguous_result"))

	since, recent := analyzeTrackResolutionFailures(tmpDir, now)

	if recent != 2 {
		t.Errorf("recentCount: want 2 (die beiden gültigen Zeilen), got %d", recent)
	}
	if want := erste.Format(time.RFC3339); since != want {
		t.Errorf("streakSince: want %s, got %q", want, since)
	}
}
