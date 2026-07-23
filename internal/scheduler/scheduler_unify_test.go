// Issue #1250 Scheibe 7c — Scheduler-Vereinheitlichung von trip_reports_hourly
// und compare_presets_daily zu einem gemeinsamen Cron-Eintrag briefing_dispatch.
//
// TDD RED: briefingDispatch() existiert noch nicht auf *Scheduler. Bis
// Phase 6 (Implementierung) schlägt dieses Package nicht mal an, weil die
// Methode undefiniert ist — das ist der gewünschte RED-Zustand.
package scheduler

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// findJob is a small helper to locate a job map by its "id" field inside the
// slice returned by Scheduler.Status()["jobs"].
func findJob(t *testing.T, jobs []map[string]any, id string) map[string]any {
	t.Helper()
	for _, job := range jobs {
		if job["id"] == id {
			return job
		}
	}
	t.Fatalf("job %q not found in status jobs %v", id, jobs)
	return nil
}

// --- AC-39: Ein einziger Cron-Eintrag briefing_dispatch statt zwei stündlicher
// Einträge (trip_reports_hourly + compare_presets_daily), Status() bleibt aber
// nach außen unverändert (9 logische Job-Zeilen). ---

func TestBriefingDispatch_UnifiedSingleCronEntry(t *testing.T) {
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	entries := sched.cron.Entries()
	// Nach der Vereinheitlichung kollabieren die zwei "0 * * * *"-Briefing-
	// Einträge (trip_reports_hourly, compare_presets_daily) zu einem
	// briefing_dispatch-Eintrag → 9 - 1 = 8 Cron-Einträge insgesamt.
	// AKTUELL (vor Implementierung): 9 Einträge → dieser Test ist RED.
	if len(entries) != 8 {
		t.Fatalf("expected 8 cron entries after unifying briefing jobs into "+
			"briefing_dispatch, got %d", len(entries))
	}

	status := sched.Status()
	jobs, ok := status["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status jobs should be a slice, got %T", status["jobs"])
	}
	// Verhaltensneutral nach außen: weiterhin 9 logische Job-Zeilen im Status,
	// auch wenn intern nur noch 8 Cron-Einträge existieren.
	if len(jobs) != 9 {
		t.Fatalf("expected Status() to still expose 9 job rows (unified cron "+
			"entry expands into 2 logical rows), got %d", len(jobs))
	}

	var sawTripReports, sawComparePresets bool
	for _, job := range jobs {
		switch job["id"] {
		case "trip_reports_hourly":
			sawTripReports = true
		case "compare_presets_daily":
			sawComparePresets = true
		}
	}
	if !sawTripReports {
		t.Fatal("Status() jobs should still include id=trip_reports_hourly")
	}
	if !sawComparePresets {
		t.Fatal("Status() jobs should still include id=compare_presets_daily")
	}
}

// --- AC-23/AC-24/AC-39: briefingDispatch() ruft nacheinander tripReports()
// und comparePresetsDaily() auf; beide Endpunkte werden je Nutzer getroffen,
// beide last_run-Einträge werden im Status separat geführt. ---

func TestBriefingDispatch_TriggersBothEndpointsAndRecordsBothLastRuns(t *testing.T) {
	var mu sync.Mutex
	var receivedPaths []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		receivedPaths = append(receivedPaths, r.URL.Path)
		mu.Unlock()
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","count":1}`)
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	createTestUsers(t, tmpDir, s, []string{"alice", "bob"})

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, s)
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	// RED: briefingDispatch does not exist yet on *Scheduler.
	sched.briefingDispatch()

	mu.Lock()
	paths := append([]string(nil), receivedPaths...)
	mu.Unlock()

	var tripHits, compareHits int
	for _, p := range paths {
		if strings.HasPrefix(p, "/api/scheduler/trip-reports") {
			tripHits++
		}
		if strings.HasPrefix(p, "/api/scheduler/compare-presets-daily") {
			compareHits++
		}
	}
	if tripHits != 2 {
		t.Fatalf("expected 2 hits on /api/scheduler/trip-reports (one per user), got %d: %v", tripHits, paths)
	}
	if compareHits != 2 {
		t.Fatalf("expected 2 hits on /api/scheduler/compare-presets-daily (one per user), got %d: %v", compareHits, paths)
	}

	status := sched.Status()
	jobs := status["jobs"].([]map[string]any)

	tripJob := findJob(t, jobs, "trip_reports_hourly")
	tripLR, ok := tripJob["last_run"].(map[string]any)
	if !ok || tripLR == nil {
		t.Fatal("trip_reports_hourly should have last_run after briefingDispatch()")
	}
	if tripLR["status"] != "ok" {
		t.Fatalf("expected trip_reports_hourly last_run.status=ok, got %v", tripLR["status"])
	}

	compareJob := findJob(t, jobs, "compare_presets_daily")
	compareLR, ok := compareJob["last_run"].(map[string]any)
	if !ok || compareLR == nil {
		t.Fatal("compare_presets_daily should have last_run after briefingDispatch()")
	}
	if compareLR["status"] != "ok" {
		t.Fatalf("expected compare_presets_daily last_run.status=ok, got %v", compareLR["status"])
	}
}

// --- AC-39 continue-on-error: Fehler im trip-reports-Aufruf darf den
// compare-presets-Aufruf nicht verhindern. ---

func TestBriefingDispatch_ContinueOnError(t *testing.T) {
	var mu sync.Mutex
	var compareHit bool

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.HasPrefix(r.URL.Path, "/api/scheduler/trip-reports"):
			w.WriteHeader(http.StatusInternalServerError)
			fmt.Fprint(w, `{"error":"boom"}`)
		case strings.HasPrefix(r.URL.Path, "/api/scheduler/compare-presets-daily"):
			mu.Lock()
			compareHit = true
			mu.Unlock()
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok","count":1}`)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
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

	// RED: briefingDispatch does not exist yet.
	sched.briefingDispatch()

	mu.Lock()
	hit := compareHit
	mu.Unlock()
	if !hit {
		t.Fatal("compare-presets-daily endpoint should still be hit despite trip-reports failure (continue-on-error)")
	}

	status := sched.Status()
	jobs := status["jobs"].([]map[string]any)

	tripJob := findJob(t, jobs, "trip_reports_hourly")
	tripLR, ok := tripJob["last_run"].(map[string]any)
	if !ok || tripLR == nil {
		t.Fatal("trip_reports_hourly should have last_run after briefingDispatch()")
	}
	if tripLR["status"] != "error" {
		t.Fatalf("expected trip_reports_hourly last_run.status=error, got %v", tripLR["status"])
	}

	compareJob := findJob(t, jobs, "compare_presets_daily")
	compareLR, ok := compareJob["last_run"].(map[string]any)
	if !ok || compareLR == nil {
		t.Fatal("compare_presets_daily should have last_run after briefingDispatch()")
	}
	if compareLR["status"] != "ok" {
		t.Fatalf("expected compare_presets_daily last_run.status=ok, got %v", compareLR["status"])
	}
}

// --- #1346 löst die #1250-AC-40-Kopplung ab: Heartbeat pingt nicht mehr
// allein am compare-Erfolg, sondern nur wenn BEIDE Teil-Jobs ok sind — sonst
// verdeckt ein Trip-Briefing-Totalausfall den Heartbeat-Erfolg. ---

func TestBriefingDispatch_HeartbeatOnlyOnCompareOk(t *testing.T) {
	t.Run("trip failure despite compare ok -> heartbeat NOT pinged", func(t *testing.T) {
		var mu sync.Mutex
		var heartbeatHits int

		heartbeatServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			mu.Lock()
			heartbeatHits++
			mu.Unlock()
			w.WriteHeader(http.StatusOK)
		}))
		defer heartbeatServer.Close()

		triggerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			switch {
			case strings.HasPrefix(r.URL.Path, "/api/scheduler/trip-reports"):
				w.WriteHeader(http.StatusInternalServerError)
				fmt.Fprint(w, `{"error":"boom"}`)
			case strings.HasPrefix(r.URL.Path, "/api/scheduler/compare-presets-daily"):
				w.WriteHeader(http.StatusOK)
				fmt.Fprint(w, `{"status":"ok","count":1}`)
			default:
				w.WriteHeader(http.StatusNotFound)
			}
		}))
		defer triggerServer.Close()

		cfg := &config.Config{
			PythonCoreURL:           triggerServer.URL,
			HeartbeatComparePresets: heartbeatServer.URL + "/heartbeat/compare-presets",
			SchedulerTimezone:       "Europe/Vienna",
		}
		sched, err := New(cfg, testStore(t))
		if err != nil {
			t.Fatalf("New() error: %v", err)
		}
		sched.notifier = func(_, _, _, _, _ string) error { return nil }

		sched.briefingDispatch()

		mu.Lock()
		hits := heartbeatHits
		mu.Unlock()
		if hits != 0 {
			t.Fatalf("expected 0 heartbeat pings when trip-reports fails despite compare ok (#1346), got %d", hits)
		}
	})

	t.Run("compare fails -> heartbeat not pinged", func(t *testing.T) {
		var mu sync.Mutex
		var heartbeatHits int

		heartbeatServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			mu.Lock()
			heartbeatHits++
			mu.Unlock()
			w.WriteHeader(http.StatusOK)
		}))
		defer heartbeatServer.Close()

		triggerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			switch {
			case strings.HasPrefix(r.URL.Path, "/api/scheduler/trip-reports"):
				w.WriteHeader(http.StatusOK)
				fmt.Fprint(w, `{"status":"ok","count":1}`)
			case strings.HasPrefix(r.URL.Path, "/api/scheduler/compare-presets-daily"):
				w.WriteHeader(http.StatusInternalServerError)
				fmt.Fprint(w, `{"error":"boom"}`)
			default:
				w.WriteHeader(http.StatusNotFound)
			}
		}))
		defer triggerServer.Close()

		cfg := &config.Config{
			PythonCoreURL:           triggerServer.URL,
			HeartbeatComparePresets: heartbeatServer.URL + "/heartbeat/compare-presets",
			SchedulerTimezone:       "Europe/Vienna",
		}
		sched, err := New(cfg, testStore(t))
		if err != nil {
			t.Fatalf("New() error: %v", err)
		}
		sched.notifier = func(_, _, _, _, _ string) error { return nil }

		sched.briefingDispatch()

		mu.Lock()
		hits := heartbeatHits
		mu.Unlock()
		if hits != 0 {
			t.Fatalf("expected heartbeat NOT to be pinged when compare-presets-daily fails, got %d hits", hits)
		}
	})

	t.Run("both ok -> heartbeat pinged exactly once", func(t *testing.T) {
		var mu sync.Mutex
		var heartbeatHits int

		heartbeatServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			mu.Lock()
			heartbeatHits++
			mu.Unlock()
			w.WriteHeader(http.StatusOK)
		}))
		defer heartbeatServer.Close()

		triggerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok","count":1}`)
		}))
		defer triggerServer.Close()

		cfg := &config.Config{
			PythonCoreURL:           triggerServer.URL,
			HeartbeatComparePresets: heartbeatServer.URL + "/heartbeat/compare-presets",
			SchedulerTimezone:       "Europe/Vienna",
		}
		sched, err := New(cfg, testStore(t))
		if err != nil {
			t.Fatalf("New() error: %v", err)
		}
		sched.notifier = func(_, _, _, _, _ string) error { return nil }

		sched.briefingDispatch()

		mu.Lock()
		hits := heartbeatHits
		mu.Unlock()
		if hits != 1 {
			t.Fatalf("expected exactly 1 heartbeat ping when both jobs ok, got %d", hits)
		}
	})
}

// --- AC-3/AC-4: edge-getriggerter MQ-Alarm bei Trip-Briefing-Totalausfall
// (analog dataWriteSelftest, #1346). ---

func TestBriefingDispatch_TripFailureTriggersMQAlarm(t *testing.T) {
	type call struct {
		sender, recipient, priority, subject, body string
	}
	var tripOK atomic.Bool
	tripOK.Store(true)

	triggerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.HasPrefix(r.URL.Path, "/api/scheduler/trip-reports"):
			if tripOK.Load() {
				w.WriteHeader(http.StatusOK)
				fmt.Fprint(w, `{"status":"ok","count":1}`)
			} else {
				w.WriteHeader(http.StatusInternalServerError)
				fmt.Fprint(w, `{"error":"boom"}`)
			}
		case strings.HasPrefix(r.URL.Path, "/api/scheduler/compare-presets-daily"):
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok","count":1}`)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer triggerServer.Close()

	// Dummy-Heartbeat-Server: verhindert, dass die "Heartbeat-URL leer"-Warnung
	// (warnMissingHeartbeatOnce) den Alarm-Zähler dieses Tests verfälscht.
	heartbeatServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer heartbeatServer.Close()

	cfg := &config.Config{
		PythonCoreURL:           triggerServer.URL,
		HeartbeatComparePresets: heartbeatServer.URL + "/heartbeat/compare-presets",
		SchedulerTimezone:       "Europe/Vienna",
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}

	var mu sync.Mutex
	var calls []call
	sched.notifier = func(sender, recipient, priority, subject, body string) error {
		mu.Lock()
		calls = append(calls, call{sender, recipient, priority, subject, body})
		mu.Unlock()
		return nil
	}
	snapshot := func() []call {
		mu.Lock()
		defer mu.Unlock()
		return append([]call(nil), calls...)
	}

	// Tick 1: trip ok -> 0 alarms.
	tripOK.Store(true)
	sched.briefingDispatch()
	if got := snapshot(); len(got) != 0 {
		t.Fatalf("expected 0 alarms after ok tick, got %d: %v", len(got), got)
	}

	// Tick 2: trip error -> exactly 1 alarm, high priority, to infra.
	tripOK.Store(false)
	sched.briefingDispatch()
	got := snapshot()
	if len(got) != 1 {
		t.Fatalf("expected exactly 1 alarm after ok->error transition, got %d: %v", len(got), got)
	}
	if got[0].sender != "gregor" || got[0].recipient != "infra" || got[0].priority != "high" {
		t.Fatalf("expected (gregor,infra,high,...), got (%q,%q,%q,...)", got[0].sender, got[0].recipient, got[0].priority)
	}
	if !strings.Contains(got[0].subject, "1346") ||
		!(strings.Contains(got[0].subject, "Briefing") || strings.Contains(got[0].subject, "Trip")) {
		t.Fatalf("expected subject to reference Briefing-Totalausfall + #1346, got %q", got[0].subject)
	}

	// Tick 3: trip stays error -> no additional alarm (edge-trigger).
	sched.briefingDispatch()
	if got := snapshot(); len(got) != 1 {
		t.Fatalf("expected no additional alarm on repeated error tick, got %d: %v", len(got), got)
	}

	// Tick 4: trip recovers -> exactly 1 recovery alarm, normal priority.
	tripOK.Store(true)
	sched.briefingDispatch()
	got = snapshot()
	if len(got) != 2 {
		t.Fatalf("expected exactly 2 alarms total after recovery, got %d: %v", len(got), got)
	}
	if got[1].priority != "normal" {
		t.Fatalf("expected recovery alarm priority normal, got %q", got[1].priority)
	}
}
