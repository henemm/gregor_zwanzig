package handler

// Telegram Inbound Webhook Gateway (Issue #637).
//
// Public, secret-protected entrypoint. Telegram pushes updates to
// POST /api/webhooks/telegram/{secret}. After secret verification the raw body
// is forwarded to the internal Python core (/api/internal/telegram-webhook).
//
// Tech-Lead-Abweichung: Secret wird über den HTTP-Header
// X-Telegram-Bot-Api-Secret-Token geprüft (nicht über das URL-Segment) —
// verhindert Secret-Leak in Nginx-Access-Logs. Das {secret}-Pfadsegment bleibt
// als Defense-in-Depth-Routing erhalten, ist aber nicht der Auth-Träger.
//
// Spec: docs/specs/modules/telegram_webhook_inbound.md

import (
	"bytes"
	"io"
	"log"
	"net/http"
	"os"
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
// pythonCoreURL is the internal Python core base URL (config.PythonCoreURL).
func TelegramWebhookHandler(pythonCoreURL string) http.HandlerFunc {
	client := &http.Client{Timeout: 5 * time.Second}
	return func(w http.ResponseWriter, r *http.Request) {
		secret := os.Getenv("TELEGRAM_WEBHOOK_SECRET")
		if secret == "" {
			// fail-closed: kein offener Endpoint ohne konfiguriertes Secret.
			http.Error(w, "webhook not configured", http.StatusServiceUnavailable)
			return
		}
		if r.Header.Get("X-Telegram-Bot-Api-Secret-Token") != secret {
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
		resp, err := client.Post(url, "application/json", bytes.NewReader(body))
		if err != nil {
			log.Printf("[telegram-webhook] forward error: %v", err)
		} else {
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}

		w.WriteHeader(http.StatusOK)
	}
}
