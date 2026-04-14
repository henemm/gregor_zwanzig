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
	"github.com/robfig/cron/v3"
)

// jobResult tracks the last execution of a scheduled job.
type jobResult struct {
	Time   time.Time `json:"time"`
	Status string    `json:"status"` // "ok" or "error"
	Error  string    `json:"error,omitempty"`
}

// Scheduler wraps robfig/cron and triggers Python services via HTTP.
type Scheduler struct {
	cron             *cron.Cron
	pythonURL        string
	heartbeatMorning string
	heartbeatEvening string
	client           *http.Client
	mu               sync.RWMutex
	lastRuns         map[string]*jobResult
}

// New creates a Scheduler from config. Returns error if timezone is invalid.
func New(cfg *config.Config) (*Scheduler, error) {
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
		lastRuns:         make(map[string]*jobResult),
	}

	// Morning subscriptions at 07:00
	s.cron.AddFunc("0 7 * * *", s.morningSubscriptions)
	// Evening subscriptions at 18:00
	s.cron.AddFunc("0 18 * * *", s.eveningSubscriptions)
	// Trip reports hourly at :00
	s.cron.AddFunc("0 * * * *", s.tripReports)
	// Alert checks every 30 minutes
	s.cron.AddFunc("0,30 * * * *", s.alertChecks)
	// Inbound commands every 5 minutes
	s.cron.AddFunc("*/5 * * * *", s.inboundCommands)

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

func (s *Scheduler) morningSubscriptions() {
	log.Println("[scheduler] Running morning subscriptions...")
	s.recordRun("morning_subscriptions", func() error {
		return s.triggerEndpoint("/api/scheduler/morning-subscriptions")
	})
	// Ping heartbeat only on success
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
		return s.triggerEndpoint("/api/scheduler/evening-subscriptions")
	})
	// Ping heartbeat only on success
	s.mu.RLock()
	lr := s.lastRuns["evening_subscriptions"]
	s.mu.RUnlock()
	if lr != nil && lr.Status == "ok" {
		s.pingHeartbeat(s.heartbeatEvening)
	}
}

func (s *Scheduler) tripReports() {
	s.recordRun("trip_reports_hourly", func() error {
		return s.triggerEndpoint("/api/scheduler/trip-reports")
	})
}

func (s *Scheduler) alertChecks() {
	s.recordRun("alert_checks", func() error {
		return s.triggerEndpoint("/api/scheduler/alert-checks")
	})
}

func (s *Scheduler) inboundCommands() {
	s.recordRun("inbound_command_poll", func() error {
		return s.triggerEndpoint("/api/scheduler/inbound-commands")
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

// triggerEndpoint sends a POST to the Python FastAPI trigger endpoint.
func (s *Scheduler) triggerEndpoint(path string) error {
	url := s.pythonURL + path
	resp, err := s.client.Post(url, "application/json", nil)
	if err != nil {
		return fmt.Errorf("HTTP error: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}
	log.Printf("[scheduler] %s → %d", path, resp.StatusCode)
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

// jobNames maps cron entry indices to human-readable job identifiers.
var jobNames = []struct {
	id   string
	name string
}{
	{"morning_subscriptions", "Morning Subscriptions (07:00)"},
	{"evening_subscriptions", "Evening Subscriptions (18:00)"},
	{"trip_reports_hourly", "Trip Reports (hourly check)"},
	{"alert_checks", "Alert Checks (every 30 min)"},
	{"inbound_command_poll", "Inbound Command Poll (every 5min)"},
}

// Status returns current scheduler state for API exposure.
func (s *Scheduler) Status() map[string]any {
	s.mu.RLock()
	defer s.mu.RUnlock()

	entries := s.cron.Entries()
	jobs := make([]map[string]any, 0, len(entries))
	for i, e := range entries {
		job := map[string]any{
			"next_run": e.Next.Format(time.RFC3339),
		}
		if i < len(jobNames) {
			job["id"] = jobNames[i].id
			job["name"] = jobNames[i].name
			if lr, ok := s.lastRuns[jobNames[i].id]; ok {
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
