// Package scheduler implements a Go cron-based scheduler that triggers
// Python services via HTTP POST endpoints.
//
// SPEC: docs/specs/modules/go_scheduler.md v1.0
package scheduler

import (
	_ "time/tzdata" // Embed timezone data for portability

	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
	"github.com/robfig/cron/v3"
)

// jobResult tracks the last execution of a scheduled job.
type jobResult struct {
	Time   time.Time `json:"time"`
	Status string    `json:"status"` // "ok" or "error"
	Error  string    `json:"error,omitempty"`
}

// jobMeta holds the human-readable identity of a cron job.
type jobMeta struct {
	id   string
	name string
}

// Scheduler wraps robfig/cron and triggers Python services via HTTP.
type Scheduler struct {
	cron             *cron.Cron
	pythonURL        string
	heartbeatMorning string
	heartbeatEvening string
	client           *http.Client
	store            *store.Store
	mu               sync.RWMutex
	lastRuns         map[string]*jobResult
	entryMap         map[cron.EntryID]jobMeta // maps cron EntryID → job identity
}

// New creates a Scheduler from config and store. Returns error if timezone is invalid.
func New(cfg *config.Config, st *store.Store) (*Scheduler, error) {
	loc, err := time.LoadLocation(cfg.SchedulerTimezone)
	if err != nil {
		return nil, fmt.Errorf("invalid timezone %q: %w", cfg.SchedulerTimezone, err)
	}

	s := &Scheduler{
		cron:             cron.New(cron.WithLocation(loc)),
		pythonURL:        cfg.PythonCoreURL,
		heartbeatMorning: cfg.HeartbeatMorning,
		heartbeatEvening: cfg.HeartbeatEvening,
		client:           &http.Client{Timeout: 120 * time.Second},
		store:            st,
		lastRuns:         make(map[string]*jobResult),
		entryMap:         make(map[cron.EntryID]jobMeta),
	}

	// Register jobs and store EntryID → jobMeta mapping
	type jobDef struct {
		expr string
		fn   func()
		id   string
		name string
	}
	jobs := []jobDef{
		{"0 7 * * *", s.morningSubscriptions, "morning_subscriptions", "Morning Subscriptions (07:00)"},
		{"0 18 * * *", s.eveningSubscriptions, "evening_subscriptions", "Evening Subscriptions (18:00)"},
		{"0 * * * *", s.tripReports, "trip_reports_hourly", "Trip Reports (hourly check)"},
		{"0,30 * * * *", s.alertChecks, "alert_checks", "Alert Checks (every 30 min)"},
		{"*/5 * * * *", s.inboundCommands, "inbound_command_poll", "Inbound Command Poll (every 5min)"},
	}
	for _, j := range jobs {
		eid, _ := s.cron.AddFunc(j.expr, j.fn)
		s.entryMap[eid] = jobMeta{id: j.id, name: j.name}
	}

	return s, nil
}

// Start begins cron scheduling.
func (s *Scheduler) Start() {
	s.cron.Start()
	log.Printf("[scheduler] Started: 5 jobs, timezone %s", s.cron.Location())
}

// Stop gracefully shuts down the scheduler and waits for running jobs.
func (s *Scheduler) Stop() {
	ctx := s.cron.Stop()
	<-ctx.Done()
	log.Println("[scheduler] Stopped")
}

// runForAllUsers iterates over all registered users and triggers the endpoint
// for each. Returns nil only if all users succeeded.
func (s *Scheduler) runForAllUsers(jobID, path string) error {
	userIDs, err := s.store.ListUserIDs()
	if err != nil {
		return fmt.Errorf("list users: %w", err)
	}
	if len(userIDs) == 0 {
		log.Printf("[scheduler] %s: no users registered, skipping", jobID)
		return nil
	}

	var firstErr error
	for _, uid := range userIDs {
		if err := s.triggerEndpointForUser(path, uid); err != nil {
			log.Printf("[scheduler] %s: user %s failed: %v", jobID, uid, err)
			if firstErr == nil {
				firstErr = err
			}
			// continue — do not stop other users
		}
	}
	return firstErr
}

func (s *Scheduler) morningSubscriptions() {
	log.Println("[scheduler] Running morning subscriptions...")
	s.recordRun("morning_subscriptions", func() error {
		return s.runForAllUsers("morning_subscriptions", "/api/scheduler/morning-subscriptions")
	})
	s.mu.RLock()
	lr := s.lastRuns["morning_subscriptions"]
	s.mu.RUnlock()
	if lr != nil && lr.Status == "ok" {
		s.pingHeartbeat(s.heartbeatMorning)
	}
}

func (s *Scheduler) eveningSubscriptions() {
	log.Println("[scheduler] Running evening subscriptions...")
	s.recordRun("evening_subscriptions", func() error {
		return s.runForAllUsers("evening_subscriptions", "/api/scheduler/evening-subscriptions")
	})
	s.mu.RLock()
	lr := s.lastRuns["evening_subscriptions"]
	s.mu.RUnlock()
	if lr != nil && lr.Status == "ok" {
		s.pingHeartbeat(s.heartbeatEvening)
	}
}

func (s *Scheduler) tripReports() {
	s.recordRun("trip_reports_hourly", func() error {
		return s.runForAllUsers("trip_reports_hourly", "/api/scheduler/trip-reports")
	})
}

func (s *Scheduler) alertChecks() {
	s.recordRun("alert_checks", func() error {
		return s.runForAllUsers("alert_checks", "/api/scheduler/alert-checks")
	})
}

func (s *Scheduler) inboundCommands() {
	s.recordRun("inbound_command_poll", func() error {
		return s.runForAllUsers("inbound_command_poll", "/api/scheduler/inbound-commands")
	})
}

// recordRun executes a job function and stores the result.
func (s *Scheduler) recordRun(jobID string, fn func() error) {
	err := fn()
	s.mu.Lock()
	defer s.mu.Unlock()
	if err != nil {
		log.Printf("[scheduler] %s failed: %v", jobID, err)
		s.lastRuns[jobID] = &jobResult{
			Time:   time.Now().In(s.cron.Location()),
			Status: "error",
			Error:  err.Error(),
		}
	} else {
		s.lastRuns[jobID] = &jobResult{
			Time:   time.Now().In(s.cron.Location()),
			Status: "ok",
		}
	}
}

// triggerEndpointForUser sends a POST to the Python trigger endpoint for a specific user.
func (s *Scheduler) triggerEndpointForUser(path, userID string) error {
	url := s.pythonURL + path + "?user_id=" + userID
	resp, err := s.client.Post(url, "application/json", nil)
	if err != nil {
		return fmt.Errorf("HTTP error: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}
	log.Printf("[scheduler] %s?user_id=%s → %d", path, userID, resp.StatusCode)
	return nil
}

// pingHeartbeat sends a GET to BetterStack. Fire-and-forget with logging.
func (s *Scheduler) pingHeartbeat(url string) {
	if url == "" {
		return
	}
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		log.Printf("[scheduler] Heartbeat ping failed: %v", err)
		return
	}
	resp.Body.Close()
	log.Printf("[scheduler] Heartbeat ping OK: ...%s", url[len(url)-8:])
}

// Status returns current scheduler state for API exposure.
func (s *Scheduler) Status() map[string]any {
	s.mu.RLock()
	defer s.mu.RUnlock()

	entries := s.cron.Entries()
	jobs := make([]map[string]any, 0, len(entries))
	for _, e := range entries {
		job := map[string]any{
			"next_run": e.Next.Format(time.RFC3339),
		}
		if meta, ok := s.entryMap[e.ID]; ok {
			job["id"] = meta.id
			job["name"] = meta.name
			if lr, ok := s.lastRuns[meta.id]; ok {
				job["last_run"] = map[string]any{
					"time":   lr.Time.Format(time.RFC3339),
					"status": lr.Status,
					"error":  lr.Error,
				}
			} else {
				job["last_run"] = nil
			}
		} else {
			job["id"] = int(e.ID)
			job["last_run"] = nil
		}
		jobs = append(jobs, job)
	}
	return map[string]any{
		"running":  true,
		"jobs":     jobs,
		"timezone": s.cron.Location().String(),
	}
}
