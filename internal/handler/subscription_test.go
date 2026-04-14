package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/store"
)

// Write tests use CreateSubscriptionHandler to seed data (no manual file setup needed)

// ============================================================================
// Read Tests
// ============================================================================

func TestSubscriptionsHandler(t *testing.T) {
	s := store.New("../../data", "default")

	h := SubscriptionsHandler(s)
	req := httptest.NewRequest("GET", "/api/subscriptions", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var subs []map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &subs); err != nil {
		t.Fatalf("expected JSON array, got error: %v", err)
	}
	if len(subs) == 0 {
		t.Error("expected at least one subscription")
	}

	ct := w.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("expected Content-Type application/json, got %s", ct)
	}
}

func TestSubscriptionHandlerFound(t *testing.T) {
	s := store.New("../../data", "default")

	r := chi.NewRouter()
	r.Get("/api/subscriptions/{id}", SubscriptionHandler(s))

	req := httptest.NewRequest("GET", "/api/subscriptions/zillertal-t-glich", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	var sub map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &sub); err != nil {
		t.Fatalf("expected JSON object, got error: %v", err)
	}
	if sub["name"] == nil {
		t.Error("expected name field in response")
	}
}

func TestSubscriptionHandlerNotFound(t *testing.T) {
	s := store.New("../../data", "default")

	r := chi.NewRouter()
	r.Get("/api/subscriptions/{id}", SubscriptionHandler(s))

	req := httptest.NewRequest("GET", "/api/subscriptions/nonexistent", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}

	var body map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &body)
	if body["error"] != "not_found" {
		t.Errorf("expected error not_found, got %v", body["error"])
	}
}

// ============================================================================
// Write Tests
// ============================================================================

func TestCreateSubscriptionHandler(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"test-sub","name":"Test Sub","enabled":true,"locations":["*"],"forecast_hours":48,"time_window_start":9,"time_window_end":16,"schedule":"weekly","weekday":4,"include_hourly":true,"top_n":3,"send_email":true,"send_signal":false}`

	h := CreateSubscriptionHandler(s)
	req := httptest.NewRequest("POST", "/api/subscriptions", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["id"] != "test-sub" {
		t.Errorf("expected id test-sub, got %v", resp["id"])
	}
}

func TestCreateSubscriptionHandlerInvalid(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"no-name"}`

	h := CreateSubscriptionHandler(s)
	req := httptest.NewRequest("POST", "/api/subscriptions", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestCreateSubscriptionHandlerDuplicateID(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"dup","name":"First","enabled":true,"locations":[],"forecast_hours":48,"time_window_start":9,"time_window_end":16,"schedule":"weekly","weekday":4,"include_hourly":true,"top_n":3,"send_email":true,"send_signal":false}`

	h := CreateSubscriptionHandler(s)

	// First create
	req := httptest.NewRequest("POST", "/api/subscriptions", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != 201 {
		t.Fatalf("first create: expected 201, got %d", w.Code)
	}

	// Duplicate create
	req = httptest.NewRequest("POST", "/api/subscriptions", strings.NewReader(body))
	w = httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != 409 {
		t.Fatalf("duplicate create: expected 409, got %d", w.Code)
	}
}

func TestUpdateSubscriptionHandler(t *testing.T) {
	s := newTestStore(t)

	// Create first
	createBody := `{"id":"upd","name":"Original","enabled":true,"locations":[],"forecast_hours":48,"time_window_start":9,"time_window_end":16,"schedule":"weekly","weekday":4,"include_hourly":true,"top_n":3,"send_email":true,"send_signal":false}`
	ch := CreateSubscriptionHandler(s)
	req := httptest.NewRequest("POST", "/api/subscriptions", strings.NewReader(createBody))
	w := httptest.NewRecorder()
	ch.ServeHTTP(w, req)

	// Update
	updateBody := `{"id":"upd","name":"Updated","enabled":false,"locations":["loc1"],"forecast_hours":24,"time_window_start":8,"time_window_end":15,"schedule":"daily_morning","weekday":0,"include_hourly":false,"top_n":5,"send_email":true,"send_signal":true}`

	r := chi.NewRouter()
	r.Put("/api/subscriptions/{id}", UpdateSubscriptionHandler(s))

	req = httptest.NewRequest("PUT", "/api/subscriptions/upd", strings.NewReader(updateBody))
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["name"] != "Updated" {
		t.Errorf("expected name Updated, got %v", resp["name"])
	}
}

func TestUpdateSubscriptionHandlerNotFound(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"ghost","name":"Ghost","enabled":true,"locations":[],"forecast_hours":48,"time_window_start":9,"time_window_end":16,"schedule":"weekly","weekday":4,"include_hourly":true,"top_n":3,"send_email":true,"send_signal":false}`

	r := chi.NewRouter()
	r.Put("/api/subscriptions/{id}", UpdateSubscriptionHandler(s))

	req := httptest.NewRequest("PUT", "/api/subscriptions/ghost", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestDeleteSubscriptionHandler(t *testing.T) {
	s := newTestStore(t)

	// Create first
	createBody := `{"id":"del","name":"Delete Me","enabled":true,"locations":[],"forecast_hours":48,"time_window_start":9,"time_window_end":16,"schedule":"weekly","weekday":4,"include_hourly":true,"top_n":3,"send_email":true,"send_signal":false}`
	ch := CreateSubscriptionHandler(s)
	req := httptest.NewRequest("POST", "/api/subscriptions", strings.NewReader(createBody))
	w := httptest.NewRecorder()
	ch.ServeHTTP(w, req)

	// Delete
	r := chi.NewRouter()
	r.Delete("/api/subscriptions/{id}", DeleteSubscriptionHandler(s))

	req = httptest.NewRequest("DELETE", "/api/subscriptions/del", nil)
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d", w.Code)
	}
}
