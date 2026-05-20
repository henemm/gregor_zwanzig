package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED: Issue #252 — PatchSubscriptionRunStatusHandler
//
// Spec: docs/specs/modules/issue_252_compare_presets.md §2
// AC-4: PATCH /api/subscriptions/{id}/run-status schreibt last_run + last_status
// ohne andere Felder zu überschreiben.

func seedSubscription(t *testing.T, s *store.Store, sub model.CompareSubscription) {
	t.Helper()
	if err := s.SaveSubscription(sub); err != nil {
		t.Fatalf("seed SaveSubscription: %v", err)
	}
}

func TestPatchSubscriptionRunStatusHandler_WritesLastRunAndStatus(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")
	seedSubscription(t, s, model.CompareSubscription{
		ID:            "patch-test",
		Name:          "Patch Test",
		Enabled:       true,
		ForecastHours: 48,
		Schedule:      "daily_morning",
		TimeWindowStart: 9,
		TimeWindowEnd:   16,
		TopN:          3,
	})

	r := chi.NewRouter()
	r.Patch("/api/subscriptions/{id}/run-status", PatchSubscriptionRunStatusHandler(s))

	now := time.Now().UTC().Format(time.RFC3339)
	body := map[string]string{"last_run": now, "last_status": "ok"}
	b, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/api/subscriptions/patch-test/run-status", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp model.CompareSubscription
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal response: %v", err)
	}
	if resp.LastStatus != "ok" {
		t.Errorf("last_status: want 'ok', got %q", resp.LastStatus)
	}
	if resp.LastRun == nil {
		t.Error("last_run: want non-nil, got nil")
	}
}

func TestPatchSubscriptionRunStatusHandler_PreservesExistingFields(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")
	recip := []string{"keep@test.com"}
	seedSubscription(t, s, model.CompareSubscription{
		ID:            "preserve-test",
		Name:          "Preserve Me",
		Enabled:       true,
		ForecastHours: 48,
		Schedule:      "daily_morning",
		TimeWindowStart: 9,
		TimeWindowEnd:   16,
		TopN:          3,
		Recipients:    recip,
	})

	r := chi.NewRouter()
	r.Patch("/api/subscriptions/{id}/run-status", PatchSubscriptionRunStatusHandler(s))

	now := time.Now().UTC().Format(time.RFC3339)
	body := map[string]string{"last_run": now, "last_status": "error"}
	b, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/api/subscriptions/preserve-test/run-status", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var resp model.CompareSubscription
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp.Name != "Preserve Me" {
		t.Errorf("name changed: want 'Preserve Me', got %q", resp.Name)
	}
	if len(resp.Recipients) == 0 || resp.Recipients[0] != "keep@test.com" {
		t.Errorf("recipients lost: %v", resp.Recipients)
	}
}

func TestPatchSubscriptionRunStatusHandler_NotFound(t *testing.T) {
	s := store.New(t.TempDir(), "default")
	s.ProvisionUserDirs("default")

	r := chi.NewRouter()
	r.Patch("/api/subscriptions/{id}/run-status", PatchSubscriptionRunStatusHandler(s))

	body := map[string]string{"last_run": time.Now().UTC().Format(time.RFC3339), "last_status": "ok"}
	b, _ := json.Marshal(body)

	req := httptest.NewRequest(http.MethodPatch, "/api/subscriptions/does-not-exist/run-status", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", w.Code)
	}
}

// TDD RED: CompareSubscription model must have Recipients, LastRun, LastStatus fields.
// This test verifies that the Go struct has the new fields at compile time.
func TestCompareSubscriptionModelHasNewFields(t *testing.T) {
	sub := model.CompareSubscription{
		ID:         "field-test",
		Name:       "Field Test",
		Recipients: []string{"a@test.com"},
		LastStatus: "ok",
	}
	now := time.Now()
	sub.LastRun = &now

	if len(sub.Recipients) != 1 {
		t.Errorf("Recipients: want 1, got %d", len(sub.Recipients))
	}
	if sub.LastStatus != "ok" {
		t.Errorf("LastStatus: want 'ok', got %q", sub.LastStatus)
	}
	if sub.LastRun == nil {
		t.Error("LastRun should not be nil")
	}
}
