package router

// Issue #2961 Nachbesserung (Gegenpruefung F7, M93): ein kurzes
// SEVEN_WEBHOOK_PATH_SECRET erzeugt beim Aufbau eine Warnzeile und ist
// verdrahtet — der SMS-Eingang arbeitet mit genau diesem Wert.

import (
	"bytes"
	"log"
	"net/http"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
)

func TestSevenWebhook_KurzesPfadgeheimnisWarntUndIstVerdrahtet(t *testing.T) {
	const pfad, key = "kurz-sms-pfad", "sms-key-kurz"
	var logBuf bytes.Buffer
	alt := log.Writer()
	log.SetOutput(&logBuf)
	r, core, _ := cfgWebhookRouter(t, func(c *config.Config) {
		c.SevenWebhookPathSecret = pfad
		c.SevenWebhookSigningKey = key
	})
	log.SetOutput(alt)
	if !strings.Contains(logBuf.String(), "WARN [config] SEVEN_WEBHOOK_PATH_SECRET") {
		t.Fatalf("Warnzeile fuer SEVEN_WEBHOOK_PATH_SECRET fehlt:\n%s", logBuf.String())
	}
	if w := sevenSignedPost(r, pfad, key, pfad); w.Code != http.StatusOK {
		t.Fatalf("richtiger kurzer Pfad, richtige Signatur: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !waitAtLeast(&core.smsPolls, 1) {
		t.Error("angenommener Webhook muss den Abruf anstossen")
	}
	if w := sevenSignedPost(r, "anderer-pfad", key, "anderer-pfad"); w.Code != http.StatusForbidden {
		t.Fatalf("falscher Pfad: erwartet 403, bekommen %d", w.Code)
	}
}
