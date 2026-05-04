package scheduler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

func testStore(t *testing.T) *store.Store {
	t.Helper()
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	// Create default user so jobs have at least one user to iterate
	s.ProvisionUserDirs("default")
	os.MkdirAll(filepath.Join(tmpDir, "users", "default"), 0755)
	os.WriteFile(filepath.Join(tmpDir, "users", "default", "user.json"),
		[]byte(`{"id":"default"}`), 0644)
	return s
}

// --- Test: New with valid timezone ---

func TestNew_ValidTimezone(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}

	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() returned error for valid timezone: %v", err)
	}
	if sched == nil {
		t.Fatal("New() returned nil scheduler")
	}
	if sched.cron == nil {
		t.Fatal("Scheduler has nil cron instance")
	}
}

// --- Test: New with invalid timezone ---

func TestNew_InvalidTimezone(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Invalid/Timezone",
	}

	sched, err := New(cfg, testStore(t))
	if err == nil {
		t.Fatal("New() should return error for invalid timezone")
	}
	if sched != nil {
		t.Fatal("New() should return nil scheduler on error")
	}
}

// --- Test: triggerEndpoint success ---

func TestTriggerEndpoint_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("Expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/api/scheduler/morning-subscriptions" {
			t.Errorf("Expected path /api/scheduler/morning-subscriptions, got %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","count":2}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	err = sched.triggerEndpointForUser("/api/scheduler/morning-subscriptions", "default")
	if err != nil {
		t.Fatalf("triggerEndpoint() returned error: %v", err)
	}
}

// --- Test: triggerEndpoint when Python is down ---

func TestTriggerEndpoint_PythonDown(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:19999", // nothing listening
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	// Use short timeout so test doesn't hang
	sched.client = &http.Client{Timeout: 1 * time.Second}

	err = sched.triggerEndpointForUser("/api/scheduler/trip-reports", "default")
	if err == nil {
		t.Fatal("triggerEndpoint() should return error when Python is down")
	}
}

// --- Test: triggerEndpoint when Python returns 500 ---

func TestTriggerEndpoint_PythonError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprint(w, `{"error":"internal server error"}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	err = sched.triggerEndpointForUser("/api/scheduler/alert-checks", "default")
	if err == nil {
		t.Fatal("triggerEndpoint() should return error for HTTP 500")
	}
	if err.Error() == "" {
		t.Fatal("Error message should not be empty")
	}
}

// --- Test: Status returns job info ---

func TestStatus(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.Start()
	defer sched.Stop()

	status := sched.Status()

	running, ok := status["running"].(bool)
	if !ok || !running {
		t.Fatal("Status should show running=true")
	}

	tz, ok := status["timezone"].(string)
	if !ok || tz != "Europe/Vienna" {
		t.Fatalf("Expected timezone Europe/Vienna, got %v", tz)
	}

	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status jobs should be a slice, got %T", status["jobs"])
	}
	if len(jobs) != 5 {
		t.Fatalf("Expected 5 jobs, got %d", len(jobs))
	}

	// Each job should have id, name, next_run, last_run
	for i, job := range jobs {
		nextRun, ok := job["next_run"].(string)
		if !ok || nextRun == "" {
			t.Fatalf("Job %d missing next_run", i)
		}
		if _, err := time.Parse(time.RFC3339, nextRun); err != nil {
			t.Fatalf("Job %d next_run %q is not valid RFC3339: %v", i, nextRun, err)
		}
		if _, ok := job["id"]; !ok {
			t.Fatalf("Job %d missing id", i)
		}
		if _, ok := job["name"]; !ok {
			t.Fatalf("Job %d missing name", i)
		}
	}
}

// --- Test: recordRun tracks success ---

func TestRecordRun_Success(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.recordRun("test_job", func() error {
		return nil
	})

	sched.mu.RLock()
	defer sched.mu.RUnlock()
	lr, ok := sched.lastRuns["test_job"]
	if !ok {
		t.Fatal("lastRuns should contain test_job")
	}
	if lr.Status != "ok" {
		t.Fatalf("Expected status ok, got %s", lr.Status)
	}
	if lr.Error != "" {
		t.Fatalf("Expected empty error, got %s", lr.Error)
	}
}

// --- Test: recordRun tracks failure ---

func TestRecordRun_Failure(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.recordRun("test_job", func() error {
		return fmt.Errorf("boom")
	})

	sched.mu.RLock()
	defer sched.mu.RUnlock()
	lr, ok := sched.lastRuns["test_job"]
	if !ok {
		t.Fatal("lastRuns should contain test_job")
	}
	if lr.Status != "error" {
		t.Fatalf("Expected status error, got %s", lr.Status)
	}
	if lr.Error != "boom" {
		t.Fatalf("Expected error 'boom', got %s", lr.Error)
	}
}

// --- Test: morningSubscriptions records run + triggers endpoint ---

func TestMorningSubscriptions_RecordsRun(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok"}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.morningSubscriptions()

	sched.mu.RLock()
	defer sched.mu.RUnlock()
	lr, ok := sched.lastRuns["morning_subscriptions"]
	if !ok {
		t.Fatal("morningSubscriptions should record last run")
	}
	if lr.Status != "ok" {
		t.Fatalf("Expected status ok, got %s", lr.Status)
	}
}

// --- Test: Failed trigger records error ---

func TestMorningSubscriptions_FailedTrigger_RecordsError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprint(w, `{"error":"boom"}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.morningSubscriptions()

	sched.mu.RLock()
	defer sched.mu.RUnlock()
	lr, ok := sched.lastRuns["morning_subscriptions"]
	if !ok {
		t.Fatal("morningSubscriptions should record last run even on failure")
	}
	if lr.Status != "error" {
		t.Fatalf("Expected status error, got %s", lr.Status)
	}
}

// --- Test: pingHeartbeat success ---

func TestPingHeartbeat_Success(t *testing.T) {
	var pinged bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("Expected GET for heartbeat, got %s", r.Method)
		}
		pinged = true
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		HeartbeatMorning:  server.URL + "/heartbeat/morning",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.pingHeartbeat("morning_subscriptions", sched.heartbeatMorning)
	if !pinged {
		t.Fatal("Heartbeat server was not pinged")
	}
}

// --- Test: pingHeartbeat failure does not panic ---

func TestPingHeartbeat_Failure(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		HeartbeatMorning:  "http://localhost:19999/heartbeat/nope",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	// Should not panic — fire-and-forget with logging
	sched.pingHeartbeat("morning_subscriptions", sched.heartbeatMorning)
}

// --- Test: pingHeartbeat with empty URL is a no-op (no HTTP request) ---

func TestPingHeartbeat_EmptyURL(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	// Replace notifier with no-op so we don't try to call the real MQ in unit tests.
	sched.notifier = func(_, _, _, _, _ string) error { return nil }

	// Should not panic or make any HTTP request
	sched.pingHeartbeat("morning_subscriptions", "")
}

// ---------------------------------------------------------------------------
// Issue #118 — Empty Heartbeat-URL muss MQ-Notification an infra triggern
// ---------------------------------------------------------------------------

// TestPingHeartbeat_EmptyURL_TriggersNotifier — Wenn HeartbeatURL leer ist
// (ENV nicht gesetzt), muss der konfigurierte notifier (Function-Field am
// Scheduler) genau einmal aufgerufen werden mit recipient="infra".
func TestPingHeartbeat_EmptyURL_TriggersNotifier(t *testing.T) {
	type call struct {
		recipient string
		subject   string
	}
	var calls []call

	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	// Inject test notifier — RED: notifier field doesn't exist on Scheduler yet
	sched.notifier = func(_, recipient, _, subject, _ string) error {
		calls = append(calls, call{recipient, subject})
		return nil
	}

	// New signature: (jobName, url) — RED: current signature is (url) only
	sched.pingHeartbeat("morning_subscriptions", "")

	if len(calls) != 1 {
		t.Fatalf("expected 1 notifier call for empty URL, got %d", len(calls))
	}
	if calls[0].recipient != "infra" {
		t.Errorf("expected recipient=infra, got %q", calls[0].recipient)
	}
}

// TestPingHeartbeat_EmptyURL_OnlyOncePerJob — sync.Once: zweimal mit
// gleichem jobName + leerer URL darf nur einen Notifier-Call auslösen
// (kein Spam bei jedem Cron-Tick).
func TestPingHeartbeat_EmptyURL_OnlyOncePerJob(t *testing.T) {
	var count int

	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.notifier = func(_, _, _, _, _ string) error {
		count++
		return nil
	}

	sched.pingHeartbeat("morning_subscriptions", "")
	sched.pingHeartbeat("morning_subscriptions", "")
	sched.pingHeartbeat("morning_subscriptions", "")

	if count != 1 {
		t.Fatalf("expected sync.Once: exactly 1 call for same job, got %d", count)
	}
}

// TestPingHeartbeat_EmptyURL_DifferentJobsSeparate — morning und evening
// haben separate sync.Once: jeweils einer pro Job.
func TestPingHeartbeat_EmptyURL_DifferentJobsSeparate(t *testing.T) {
	var count int

	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.notifier = func(_, _, _, _, _ string) error {
		count++
		return nil
	}

	sched.pingHeartbeat("morning_subscriptions", "")
	sched.pingHeartbeat("evening_subscriptions", "")

	if count != 2 {
		t.Fatalf("expected 2 calls (morning + evening), got %d", count)
	}
}

// --- Test: morningSubscriptions triggers endpoint + heartbeat ---

func TestMorningSubscriptions_TriggersHeartbeat(t *testing.T) {
	var calls []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls = append(calls, r.Method+" "+r.URL.Path)
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok"}`)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		HeartbeatMorning:  server.URL + "/heartbeat/morning",
		HeartbeatEvening:  server.URL + "/heartbeat/evening",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.morningSubscriptions()

	if len(calls) != 2 {
		t.Fatalf("Expected 2 calls (trigger + heartbeat), got %d: %v", len(calls), calls)
	}
	if calls[0] != "POST /api/scheduler/morning-subscriptions" {
		t.Errorf("First call should be POST trigger, got %s", calls[0])
	}
	if calls[1] != "GET /heartbeat/morning" {
		t.Errorf("Second call should be GET heartbeat, got %s", calls[1])
	}
}

// --- Test: Failed trigger skips heartbeat ---

func TestMorningSubscriptions_FailedTrigger_SkipsHeartbeat(t *testing.T) {
	triggerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprint(w, `{"error":"boom"}`)
	}))
	defer triggerServer.Close()

	var heartbeatPinged bool
	heartbeatServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		heartbeatPinged = true
		w.WriteHeader(http.StatusOK)
	}))
	defer heartbeatServer.Close()

	cfg := &config.Config{
		PythonCoreURL:     triggerServer.URL,
		HeartbeatMorning:  heartbeatServer.URL + "/heartbeat/morning",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	sched.morningSubscriptions()

	if heartbeatPinged {
		t.Fatal("Heartbeat should NOT be pinged when trigger fails")
	}
}

// --- Test: Status JSON is serializable ---

func TestStatus_JSONSerializable(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.Start()
	defer sched.Stop()

	status := sched.Status()

	data, err := json.Marshal(status)
	if err != nil {
		t.Fatalf("Status() not JSON serializable: %v", err)
	}
	if len(data) < 10 {
		t.Fatalf("JSON too short: %s", string(data))
	}
}

// --- Test: Status includes last_run after job execution ---

func TestStatus_IncludesLastRun(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.Start()
	defer sched.Stop()

	// Trigger a job manually
	sched.morningSubscriptions()

	status := sched.Status()
	jobs := status["jobs"].([]map[string]any)

	// Find morning_subscriptions job
	var found bool
	for _, job := range jobs {
		if job["id"] == "morning_subscriptions" {
			found = true
			lr, ok := job["last_run"].(map[string]any)
			if !ok || lr == nil {
				t.Fatal("morning_subscriptions should have last_run after execution")
			}
			if lr["status"] != "ok" {
				t.Fatalf("Expected last_run status ok, got %v", lr["status"])
			}
		}
	}
	if !found {
		t.Fatal("morning_subscriptions job not found in status")
	}
}
