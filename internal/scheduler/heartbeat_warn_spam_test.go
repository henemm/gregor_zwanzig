// Issue #1931 AC-1: briefing_dispatch mit bewusst leerer
// heartbeatComparePresets-URL (Prod-Normalfall seit #1898) darf keine
// MQ-Warnung mehr an infra ausloesen, auch nicht nach mehreren Laeufen im
// selben Prozess.
package scheduler

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

func TestBriefingDispatch_EmptyHeartbeatURL_DoesNotWarnInfra(t *testing.T) {
	type call struct {
		recipient string
		subject   string
	}
	var mu sync.Mutex
	var calls []call

	triggerServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","count":1}`)
	}))
	defer triggerServer.Close()

	cfg := &config.Config{
		PythonCoreURL:     triggerServer.URL,
		SchedulerTimezone: "Europe/Vienna",
		// HeartbeatComparePresets bewusst leer gelassen (Prod-Zustand, #1898).
	}
	sched, err := New(cfg, testStore(t))
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	sched.notifier = func(_, recipient, _, subject, _ string) error {
		mu.Lock()
		calls = append(calls, call{recipient, subject})
		mu.Unlock()
		return nil
	}

	sched.briefingDispatch()
	sched.briefingDispatch()

	mu.Lock()
	n := len(calls)
	got := append([]call(nil), calls...)
	mu.Unlock()
	if n != 0 {
		t.Fatalf("expected 0 notifier calls for briefing_dispatch with empty "+
			"heartbeat URL (accepted state since #1898), got %d: %v", n, got)
	}
}
