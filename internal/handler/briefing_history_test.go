package handler

// TDD GREEN: Issue #559 — BriefingHistoryHandler Tests (AC-1, AC-4, AC-5).
// Spec: docs/specs/modules/issue_559_archiv_fertigstellen.md

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
)

func TestBriefingHistoryHandler_Unauthorized(t *testing.T) {
	s := newTestStore(t)
	router := chi.NewRouter()
	router.Get("/api/trips/{id}/briefing-history", BriefingHistoryHandler(s))

	req := httptest.NewRequest(http.MethodGet, "/api/trips/trip-123/briefing-history", nil)
	// No user context set — UserIDFromContext returns ""
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d: %s", w.Code, w.Body.String())
	}
}

func TestBriefingHistoryHandler_EmptyForUnknownTrip(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "test", []map[string]interface{}{
		{"trip_id": "trip-other", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
	})

	router := chi.NewRouter()
	router.Get("/api/trips/{id}/briefing-history", BriefingHistoryHandler(s))

	req := httptest.NewRequest(http.MethodGet, "/api/trips/trip-123/briefing-history", nil)
	req = withUserCtx(req, "test")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var result []interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatalf("not valid JSON array: %v", err)
	}
	if len(result) != 0 {
		t.Errorf("expected empty array, got %d entries", len(result))
	}
}

func TestBriefingHistoryHandler_ReturnsMatchingEntries(t *testing.T) {
	s := newTestStore(t)
	seedBriefingLog(t, s.DataDir, "test", []map[string]interface{}{
		{"trip_id": "trip-123", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
		{"trip_id": "trip-123", "kind": "evening", "sent_at": "2026-05-01T18:05:00Z", "channels": []string{"email", "signal"}},
		{"trip_id": "trip-other", "kind": "morning", "sent_at": "2026-05-01T07:00:00Z", "channels": []string{"email"}},
	})

	router := chi.NewRouter()
	router.Get("/api/trips/{id}/briefing-history", BriefingHistoryHandler(s))

	req := httptest.NewRequest(http.MethodGet, "/api/trips/trip-123/briefing-history", nil)
	req = withUserCtx(req, "test")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %s", ct)
	}

	var result []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatalf("not valid JSON: %v", err)
	}
	if len(result) != 2 {
		t.Fatalf("expected 2 entries for trip-123, got %d", len(result))
	}

	first := result[0]
	if first["kind"] != "morning" {
		t.Errorf("expected kind=morning, got %v", first["kind"])
	}
	if first["sent_at"] != "2026-05-01T07:00:00Z" {
		t.Errorf("unexpected sent_at: %v", first["sent_at"])
	}
}

func TestBriefingHistoryHandler_EmptyWhenNoLog(t *testing.T) {
	s := newTestStore(t)

	router := chi.NewRouter()
	router.Get("/api/trips/{id}/briefing-history", BriefingHistoryHandler(s))

	req := httptest.NewRequest(http.MethodGet, "/api/trips/trip-123/briefing-history", nil)
	req = withUserCtx(req, "test")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var result []interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatalf("not valid JSON array: %v", err)
	}
	if len(result) != 0 {
		t.Errorf("expected empty array when no log, got %d entries", len(result))
	}
}
