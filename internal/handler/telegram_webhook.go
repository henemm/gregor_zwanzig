package handler

// Telegram Inbound Webhook Gateway (Issue #637).
//
// Public, secret-protected entrypoint. Telegram pushes updates to
// POST /api/webhooks/telegram/inbound (Issue #1814). After secret verification
// the raw body is forwarded to the internal Python core
// (/api/internal/telegram-webhook).
//
// Einziger Auth-Träger ist der HTTP-Header X-Telegram-Bot-Api-Secret-Token
// (Konstantzeit-Vergleich gegen TELEGRAM_WEBHOOK_SECRET). Der URL-Pfad wird
// nie gelesen. Die frühere Route mit Secret im Pfad ist entfernt (#1814 Scheibe 2).
//
// Spec: docs/specs/modules/telegram_webhook_inbound.md,
// docs/specs/modules/fix_1814_telegram_webhook_secret_nicht_im_pfad.md

import (
	"bytes"
	"crypto/sha256"
	"crypto/subtle"
	"io"
	"log"
	"net/http"
	"sync/atomic"
	"time"
)

// rejectedWebhookRequests zählt mit falschem/fehlendem Secret abgewiesene
// Requests (Prozess-Counter) — Grundlage für Anomalie-/Angriffs-Alerts.
var rejectedWebhookRequests atomic.Int64

// RejectedTelegramWebhookCount liefert den aktuellen 403-Zähler (für Monitoring).
func RejectedTelegramWebhookCount() int64 {
	return rejectedWebhookRequests.Load()
}

// TelegramWebhookHandler returns the public webhook gateway handler.
// pythonCoreURL is the internal Python core base URL (config.PythonCoreURL);
// secret is config.TelegramWebhookSecret (Issue #2715, leer = 503).
func TelegramWebhookHandler(pythonCoreURL, secret string) http.HandlerFunc {
	client := &http.Client{Timeout: 5 * time.Second}
	return func(w http.ResponseWriter, r *http.Request) {
		if secret == "" {
			// fail-closed: kein offener Endpoint ohne konfiguriertes Secret.
			http.Error(w, "webhook not configured", http.StatusServiceUnavailable)
			return
		}
		if !secretEqual(r.Header.Get("X-Telegram-Bot-Api-Secret-Token"), secret) {
			n := rejectedWebhookRequests.Add(1)
			log.Printf("[telegram-webhook] 403 rejected (count=%d, remote=%s)", n, r.RemoteAddr)
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}

		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}

		// Synchroner Forward mit 5-s-Timeout. Telegrams eigenes Webhook-Read-Timeout
		// liegt bei ~60 s, sodass unser 5-s-Cap die Antwortzeit nach oben begrenzt
		// und ein Retry-Sturm ausgeschlossen ist. Fehler beim Forward werden geloggt
		// und ändern die 200-Antwort an Telegram nicht — Telegram soll nie retrien.
		url := pythonCoreURL + "/api/internal/telegram-webhook"
		fwd, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
		if err != nil {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		fwd.Header.Set("Content-Type", "application/json")
		// Issue #2142 (AC-10): Python prüft das Telegram-Secret ein zweites Mal
		// (Defense in Depth) — ohne diesen Header antwortet der Core mit 403.
		fwd.Header.Set("X-Telegram-Bot-Api-Secret-Token", secret)
		resp, err := client.Do(fwd)
		if err != nil {
			log.Printf("[telegram-webhook] forward error: %v", err)
		} else {
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}

		w.WriteHeader(http.StatusOK)
	}
}

// secretEqual vergleicht konstantzeitig (sha256 + ConstantTimeCompare, #2159).
func secretEqual(got, want string) bool {
	a, b := sha256.Sum256([]byte(got)), sha256.Sum256([]byte(want))
	return subtle.ConstantTimeCompare(a[:], b[:]) == 1
}
