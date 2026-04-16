package scheduler

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED: Tests for multi-user scheduler — must FAIL until implemented.

func createTestUsers(t *testing.T, tmpDir string, s *store.Store, userIDs []string) {
	t.Helper()
	for _, id := range userIDs {
		s.ProvisionUserDirs(id)
		dir := filepath.Join(tmpDir, "users", id)
		os.WriteFile(filepath.Join(dir, "user.json"),
			[]byte(`{"id":"`+id+`"}`), 0644)
	}
}

func TestNewWithStore(t *testing.T) {
	// GIVEN: Config and Store
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	cfg := &config.Config{
		PythonCoreURL:     "http://localhost:8000",
		SchedulerTimezone: "Europe/Vienna",
	}

	// WHEN: Creating scheduler with store
	sched, err := New(cfg, s)

	// THEN: No error, store is set
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	if sched.store == nil {
		t.Fatal("Scheduler should have a store reference")
	}
}

func TestTriggerEndpointForUser_SendsUserID(t *testing.T) {
	// GIVEN: HTTP server that records the user_id query param
	var receivedUserID string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedUserID = r.URL.Query().Get("user_id")
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok"}`)
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, _ := New(cfg, s)

	// WHEN: Triggering endpoint for user "alice"
	err := sched.triggerEndpointForUser("/api/scheduler/morning-subscriptions", "alice")

	// THEN: user_id=alice was sent
	if err != nil {
		t.Fatalf("triggerEndpointForUser error: %v", err)
	}
	if receivedUserID != "alice" {
		t.Fatalf("Expected user_id=alice, got %q", receivedUserID)
	}
}

func TestMorningSubscriptions_IteratesOverAllUsers(t *testing.T) {
	// GIVEN: Two registered users and a server that records user_ids
	var mu sync.Mutex
	var receivedUserIDs []string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		mu.Lock()
		receivedUserIDs = append(receivedUserIDs, uid)
		mu.Unlock()
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok"}`)
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	createTestUsers(t, tmpDir, s, []string{"alice", "bob"})

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, _ := New(cfg, s)

	// WHEN: Running morning subscriptions
	sched.morningSubscriptions()

	// THEN: Both users triggered
	if len(receivedUserIDs) != 2 {
		t.Fatalf("Expected 2 requests, got %d: %v", len(receivedUserIDs), receivedUserIDs)
	}
	joined := strings.Join(receivedUserIDs, ",")
	if !strings.Contains(joined, "alice") || !strings.Contains(joined, "bob") {
		t.Fatalf("Expected alice and bob in user IDs, got %v", receivedUserIDs)
	}
}

func TestMorningSubscriptions_ContinuesOnUserError(t *testing.T) {
	// GIVEN: Two users, first user's request fails
	var mu sync.Mutex
	var receivedUserIDs []string
	callCount := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.URL.Query().Get("user_id")
		mu.Lock()
		receivedUserIDs = append(receivedUserIDs, uid)
		callCount++
		count := callCount
		mu.Unlock()

		if count == 1 {
			w.WriteHeader(http.StatusInternalServerError)
			fmt.Fprint(w, `{"error":"boom"}`)
		} else {
			w.WriteHeader(http.StatusOK)
			fmt.Fprint(w, `{"status":"ok"}`)
		}
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	createTestUsers(t, tmpDir, s, []string{"alice", "bob"})

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, _ := New(cfg, s)

	// WHEN: Running morning subscriptions (first fails, second succeeds)
	sched.morningSubscriptions()

	// THEN: Both users were processed (continue-on-error)
	if len(receivedUserIDs) != 2 {
		t.Fatalf("Expected 2 requests (continue-on-error), got %d", len(receivedUserIDs))
	}
}

func TestMorningSubscriptions_NoUsers_Noop(t *testing.T) {
	// GIVEN: No registered users
	var requestsMade int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestsMade++
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")

	cfg := &config.Config{
		PythonCoreURL:     server.URL,
		SchedulerTimezone: "Europe/Vienna",
	}
	sched, _ := New(cfg, s)

	// WHEN: Running morning subscriptions with no users
	sched.morningSubscriptions()

	// THEN: No HTTP requests made
	if requestsMade != 0 {
		t.Fatalf("Expected 0 requests with no users, got %d", requestsMade)
	}
}
