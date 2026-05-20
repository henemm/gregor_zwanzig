package handler

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// Adversary Finding 1: recipients=["not-an-email"] mit send_email=true muss
// HTTP 400 zurückgeben, nicht 201. Validiert die Recipients-Schleife in
// validateSubscription().

func TestCreateSubscriptionHandler_RejectsInvalidRecipient(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"bad-recip","name":"Bad","enabled":true,"locations":[],"forecast_hours":48,"time_window_start":9,"time_window_end":16,"schedule":"daily_morning","weekday":0,"include_hourly":true,"top_n":3,"send_email":true,"send_signal":false,"recipients":["not-an-email"]}`

	h := CreateSubscriptionHandler(s)
	req := httptest.NewRequest("POST", "/api/subscriptions", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for invalid recipient, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "recipients") {
		t.Errorf("error body should mention 'recipients', got: %s", w.Body.String())
	}
}

func TestCreateSubscriptionHandler_AcceptsValidRecipient(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"good-recip","name":"Good","enabled":true,"locations":[],"forecast_hours":48,"time_window_start":9,"time_window_end":16,"schedule":"daily_morning","weekday":0,"include_hourly":true,"top_n":3,"send_email":true,"send_signal":false,"recipients":["valid@example.com"]}`

	h := CreateSubscriptionHandler(s)
	req := httptest.NewRequest("POST", "/api/subscriptions", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201 for valid recipient, got %d: %s", w.Code, w.Body.String())
	}
}

// Wenn send_email=false ist, brauchen wir Recipients nicht zu validieren —
// die Subscription läuft nicht via Mail. Aber: leere Recipients sind okay,
// die Schleife läuft nur wenn es welche gibt.
func TestCreateSubscriptionHandler_EmptyRecipientsOK(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"no-recip","name":"NoRecip","enabled":true,"locations":[],"forecast_hours":48,"time_window_start":9,"time_window_end":16,"schedule":"daily_morning","weekday":0,"include_hourly":true,"top_n":3,"send_email":true,"send_signal":false,"recipients":[]}`

	h := CreateSubscriptionHandler(s)
	req := httptest.NewRequest("POST", "/api/subscriptions", bytes.NewBufferString(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusCreated {
		t.Fatalf("expected 201 for empty recipients (no validation needed), got %d: %s", w.Code, w.Body.String())
	}
}
