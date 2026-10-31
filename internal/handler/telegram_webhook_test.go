package handler

// TDD RED: Issue #637 — Telegram Inbound Webhook-Migration (Go Gateway).
// Spec: docs/specs/modules/telegram_webhook_inbound.md
//
// Muss FEHLSCHLAGEN bis TelegramWebhookHandler existiert (Compile-Fehler).
// Ausführung: go test ./internal/handler/... -run TestTelegramWebhook -v

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

// AC-1: Korrekter Secret-Header → 200 + roher Body wird an Python-Core
// (/api/internal/telegram-webhook) weitergeleitet.
func TestTelegramWebhookHandler_ValidSecretForwardsAndReturns200(t *testing.T) {
	os.Setenv("TELEGRAM_WEBHOOK_SECRET", "s3cr3t")
	defer os.Unsetenv("TELEGRAM_WEBHOOK_SECRET")

	forwarded := false
	var forwardedBody []byte
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		forwarded = true
		forwardedBody, _ = io.ReadAll(r.Body)
		if r.URL.Path != "/api/internal/telegram-webhook" {
			t.Errorf("an falschen Pfad weitergeleitet: %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	h := TelegramWebhookHandler(backend.URL)
	body := `{"update_id":1,"message":{"chat":{"id":12345},"text":"status"}}`
	req := httptest.NewRequest("POST", "/api/webhooks/telegram/whatever", bytes.NewBufferString(body))
	req.Header.Set("X-Telegram-Bot-Api-Secret-Token", "s3cr3t")
	rr := httptest.NewRecorder()

	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("erwartet 200, bekam %d", rr.Code)
	}
	if !forwarded {
		t.Fatal("erwartet: Request an Python-Core weitergeleitet — wurde nicht")
	}
	if string(forwardedBody) != body {
		t.Errorf("weitergeleiteter Body weicht ab: %q", string(forwardedBody))
	}
}

// AC-1: Falscher/fehlender Header → 403, KEIN Forwarding.
func TestTelegramWebhookHandler_WrongSecretReturns403NoForward(t *testing.T) {
	os.Setenv("TELEGRAM_WEBHOOK_SECRET", "s3cr3t")
	defer os.Unsetenv("TELEGRAM_WEBHOOK_SECRET")

	forwarded := false
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		forwarded = true
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	h := TelegramWebhookHandler(backend.URL)
	req := httptest.NewRequest("POST", "/api/webhooks/telegram/whatever", bytes.NewBufferString(`{"update_id":1}`))
	req.Header.Set("X-Telegram-Bot-Api-Secret-Token", "wrong")
	rr := httptest.NewRecorder()

	h(rr, req)

	if rr.Code != http.StatusForbidden {
		t.Fatalf("erwartet 403, bekam %d", rr.Code)
	}
	if forwarded {
		t.Fatal("bei falschem Secret darf NICHT weitergeleitet werden")
	}
}
