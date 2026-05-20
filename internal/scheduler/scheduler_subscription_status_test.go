package scheduler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED: Issue #252 — BuildCompareSubscriptionsStatus()
//
// Spec: docs/specs/modules/issue_252_compare_presets.md §5
// AC-4: GET /api/scheduler/subscriptions-status (authenticated) liefert
//       compare_subscriptions-Array mit id, name, enabled, last_run, last_status
//       pro aktivem Preset.
//
// Adversary Finding 3 (Privacy-Leak): Status() darf compare_subscriptions
// NICHT mehr enthalten — Daten werden nur via authenticated Endpoint exposed.

func seedSubscriptionForStatus(t *testing.T, s *store.Store, sub model.CompareSubscription) {
	t.Helper()
	if err := s.SaveSubscription(sub); err != nil {
		t.Fatalf("seedSubscriptionForStatus: %v", err)
	}
}

func TestStatusIncludesCompareSubscriptions(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	s.ProvisionUserDirs("default")
	os.MkdirAll(filepath.Join(tmpDir, "users", "default"), 0755)
	os.WriteFile(filepath.Join(tmpDir, "users", "default", "user.json"),
		[]byte(`{"id":"default"}`), 0644)

	now := time.Now()
	seedSubscriptionForStatus(t, s, model.CompareSubscription{
		ID:              "status-sub-1",
		Name:            "Zillertal vs Stubai",
		Enabled:         true,
		ForecastHours:   48,
		Schedule:        "daily_morning",
		TimeWindowStart: 9,
		TimeWindowEnd:   16,
		TopN:            3,
		LastRun:         &now,
		LastStatus:      "ok",
	})

	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, err := New(cfg, s)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	subsSlice := sched.BuildCompareSubscriptionsStatus()
	if len(subsSlice) == 0 {
		t.Fatal("BuildCompareSubscriptionsStatus() ist leer, erwartet mindestens 1 Eintrag")
	}

	entry := subsSlice[0]
	if entry["id"] != "status-sub-1" {
		t.Errorf("id: want 'status-sub-1', got %v", entry["id"])
	}
	if entry["name"] != "Zillertal vs Stubai" {
		t.Errorf("name: want 'Zillertal vs Stubai', got %v", entry["name"])
	}
	if entry["last_status"] != "ok" {
		t.Errorf("last_status: want 'ok', got %v", entry["last_status"])
	}
	if entry["last_run"] == nil {
		t.Error("last_run: erwartet non-nil")
	}
}

func TestStatusCompareSubscriptionsEmptyWhenNone(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	s.ProvisionUserDirs("default")
	os.MkdirAll(filepath.Join(tmpDir, "users", "default"), 0755)
	os.WriteFile(filepath.Join(tmpDir, "users", "default", "user.json"),
		[]byte(`{"id":"default"}`), 0644)

	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, _ := New(cfg, s)

	subsSlice := sched.BuildCompareSubscriptionsStatus()
	if len(subsSlice) != 0 {
		t.Errorf("erwartet leeres Array, got %d Einträge", len(subsSlice))
	}
}

// Adversary Finding 3: /api/scheduler/status (public) darf compare_subscriptions
// NICHT mehr enthalten. Privacy-Leak vermeiden.
func TestSchedulerStatusEndpointJSON(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	s.ProvisionUserDirs("default")
	os.MkdirAll(filepath.Join(tmpDir, "users", "default"), 0755)
	os.WriteFile(filepath.Join(tmpDir, "users", "default", "user.json"),
		[]byte(`{"id":"default"}`), 0644)

	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, _ := New(cfg, s)

	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(sched.Status())
	})

	req := httptest.NewRequest(http.MethodGet, "/api/scheduler/status", nil)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("JSON parse: %v", err)
	}
	// Privacy-Fix: compare_subscriptions darf NICHT mehr im public Status sein.
	if _, ok := body["compare_subscriptions"]; ok {
		t.Error("Status() soll compare_subscriptions NICHT mehr enthalten (Privacy-Fix)")
	}
}

// Finding 4: leere Felder (last_status == "", last_run == nil) müssen aus der
// Map weggelassen werden, nicht als Null/Empty-String serialisiert.
func TestBuildCompareSubscriptionsStatusOmitsEmptyFields(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	s.ProvisionUserDirs("default")
	os.MkdirAll(filepath.Join(tmpDir, "users", "default"), 0755)
	os.WriteFile(filepath.Join(tmpDir, "users", "default", "user.json"),
		[]byte(`{"id":"default"}`), 0644)

	seedSubscriptionForStatus(t, s, model.CompareSubscription{
		ID:              "no-runs-yet",
		Name:            "Never Ran",
		Enabled:         true,
		ForecastHours:   48,
		Schedule:        "daily_morning",
		TimeWindowStart: 9,
		TimeWindowEnd:   16,
		TopN:            3,
		// LastRun == nil, LastStatus == ""
	})

	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, _ := New(cfg, s)

	subsSlice := sched.BuildCompareSubscriptionsStatus()
	if len(subsSlice) == 0 {
		t.Fatal("erwartet 1 Eintrag")
	}
	entry := subsSlice[0]
	if _, ok := entry["last_status"]; ok {
		t.Errorf("last_status sollte fehlen (war \"\"), got %v", entry["last_status"])
	}
	if _, ok := entry["last_run"]; ok {
		t.Errorf("last_run sollte fehlen (war nil), got %v", entry["last_run"])
	}
}
