package notify

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestSendMQ_NoSecret_NoOp verifies fail-soft when CLAUDE_MQ_SECRET is unset.
func TestSendMQ_NoSecret_NoOp(t *testing.T) {
	t.Setenv("CLAUDE_MQ_SECRET", "")
	t.Setenv("CLAUDE_MQ_URL", "http://127.0.0.1:1") // would fail if used

	if err := SendMQ("gregor", "infra", "normal", "subj", "body"); err != nil {
		t.Fatalf("expected nil error when secret unset, got %v", err)
	}
}

// TestSendMQ_PostsWithHeadersAndBody hits a real httptest server and verifies
// that the request reaches it with the expected headers and JSON payload.
func TestSendMQ_PostsWithHeadersAndBody(t *testing.T) {
	type captured struct {
		method string
		secret string
		ctype  string
		body   mqMessage
	}
	var got captured

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got.method = r.Method
		got.secret = r.Header.Get("X-MQ-Secret")
		got.ctype = r.Header.Get("Content-Type")
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &got.body)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	t.Setenv("CLAUDE_MQ_SECRET", "test-secret")
	t.Setenv("CLAUDE_MQ_URL", server.URL)

	err := SendMQ("gregor", "infra", "normal", "the-subj", "the-body")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if got.method != "POST" {
		t.Errorf("expected POST, got %s", got.method)
	}
	if got.secret != "test-secret" {
		t.Errorf("expected secret header 'test-secret', got %q", got.secret)
	}
	if got.ctype != "application/json" {
		t.Errorf("expected Content-Type application/json, got %q", got.ctype)
	}
	if got.body.Sender != "gregor" || got.body.Recipient != "infra" ||
		got.body.Priority != "normal" || got.body.Subject != "the-subj" ||
		got.body.Body != "the-body" {
		t.Errorf("body mismatch: %+v", got.body)
	}
}

// TestSendMQ_HTTPError returns error on >=400 status.
func TestSendMQ_HTTPError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	t.Setenv("CLAUDE_MQ_SECRET", "test-secret")
	t.Setenv("CLAUDE_MQ_URL", server.URL)

	err := SendMQ("gregor", "infra", "normal", "subj", "body")
	if err == nil {
		t.Fatal("expected error on HTTP 500")
	}
}
