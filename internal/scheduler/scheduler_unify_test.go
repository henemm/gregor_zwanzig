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

// --- AC-40: Heartbeat hängt ausschließlich am Erfolg des compare-Aufrufs,
// unabhängig vom Ausgang des trip-Aufrufs. ---

func TestBriefingDispatch_HeartbeatOnlyOnCompareOk(t *testing.T) {
	t.Run("compare ok despite trip failure -> heartbeat pinged exactly once", func(t *testing.T) {
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

		// RED: briefingDispatch does not exist yet.
		sched.briefingDispatch()

		mu.Lock()
		hits := heartbeatHits
		mu.Unlock()
		if hits != 1 {
			t.Fatalf("expected heartbeat to be pinged exactly once (compare succeeded despite trip failure), got %d", hits)
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

		// RED: briefingDispatch does not exist yet.
		sched.briefingDispatch()

		mu.Lock()
		hits := heartbeatHits
		mu.Unlock()
		if hits != 0 {
			t.Fatalf("expected heartbeat NOT to be pinged when compare-presets-daily fails, got %d hits", hits)
		}
	})
}
