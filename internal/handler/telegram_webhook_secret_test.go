package handler

// Issue #2159 AC-8 — Verhaltens-Erhalt des Webhook-Vergleichs. Die Konstantzeit
// selbst ist nicht messbar; dieser Test ist schon heute gruen und bewacht, dass
// die Umstellung auf subtle.ConstantTimeCompare richtig/falsch/fehlend/
// Praefix/Laenge nicht verwischt.

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func TestTelegramWebhookHandler_SecretMatrix(t *testing.T) {
	os.Setenv("TELEGRAM_WEBHOOK_SECRET", "s3cr3t-lang-genug")
	defer os.Unsetenv("TELEGRAM_WEBHOOK_SECRET")

	cases := []struct {
		name   string
		set    bool
		header string
		want   int
	}{
		{"richtig", true, "s3cr3t-lang-genug", http.StatusOK},
		{"fehlend", false, "", http.StatusForbidden},
		{"leer", true, "", http.StatusForbidden},
		{"praefix", true, "s3cr3t", http.StatusForbidden},
		{"zu lang", true, "s3cr3t-lang-genug-und-mehr", http.StatusForbidden},
		{"gleiche Laenge, anderes Zeichen", true, "s3cr3t-lang-genuX", http.StatusForbidden},
	}
	for _, tc := range cases {
		forwarded := false
		backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			forwarded = true
			w.WriteHeader(http.StatusOK)
		}))
		h := TelegramWebhookHandler(backend.URL)
		req := httptest.NewRequest("POST", "/api/webhooks/telegram/x", bytes.NewBufferString(`{"update_id":1}`))
		if tc.set {
			req.Header.Set("X-Telegram-Bot-Api-Secret-Token", tc.header)
		}
		rr := httptest.NewRecorder()
		h(rr, req)
		backend.Close()
		if rr.Code != tc.want {
			t.Errorf("%s: erwartet %d, bekam %d", tc.name, tc.want, rr.Code)
		}
		if forwarded != (tc.want == http.StatusOK) {
			t.Errorf("%s: Weiterleitung=%v passt nicht zu %d", tc.name, forwarded, tc.want)
		}
	}
}
