package router

// Issue #2961 (GA10) — Zugriffslog ohne Geheimnisse; Mindestlaenge der
// Maschinen-Geheimnisse.
// Spec: docs/specs/modules/security_haertung_2026_11_go_anmeldung.md (AC-26, AC-27).

import (
	"log"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	chimw "github.com/go-chi/chi/v5/middleware"

	"github.com/henemm/gregor-api/internal/config"
)

// AC-26: Webhook-Pfadgeheimnisse und die Query-Werte code/state/token stehen
// nicht im Klartext im Zugriffslog; der restliche Pfad bleibt lesbar.
func TestZugriffslog_MaskiertGeheimnisse(t *testing.T) {
	// Echter chi-Logger, nur die Ausgabe in einen Puffer (Muster
	// TestEinladungToken_ErscheintNieImAccessLog).
	var buf syncBuf
	orig := chimw.DefaultLogger
	chimw.DefaultLogger = chimw.RequestLogger(&chimw.DefaultLogFormatter{Logger: log.New(&buf, "", 0), NoColor: true})
	t.Cleanup(func() { chimw.DefaultLogger = orig })
	r, _, _ := schutzRouter2961(t, nil)

	for _, p := range []string{
		"/api/webhooks/sms/GEHEIMPFAD-SMS-0123456789abcdef",
		"/api/webhooks/mail/GEHEIMPFAD-MAIL-0123456789abcdef",
		"/api/auth/google/callback?code=GEHEIMCODE-4711&state=GEHEIMSTATE-0815&scope=email",
		"/api/locations?token=GEHEIMTOKEN-1234",
	} {
		method := http.MethodGet
		if strings.HasPrefix(p, "/api/webhooks/") {
			method = http.MethodPost
		}
		req := httptest.NewRequest(method, p, nil)
		r.ServeHTTP(httptest.NewRecorder(), req)
	}
	ausgabe := buf.String()
	for _, geheim := range []string{"GEHEIMPFAD-SMS", "GEHEIMPFAD-MAIL", "GEHEIMCODE", "GEHEIMSTATE", "GEHEIMTOKEN"} {
		if strings.Contains(ausgabe, geheim) {
			t.Errorf("Zugriffslog enthaelt %q im Klartext:\n%s", geheim, ausgabe)
		}
	}
	for _, sichtbar := range []string{"/api/webhooks/sms/***", "/api/auth/google/callback", "scope=email"} {
		if !strings.Contains(ausgabe, sichtbar) {
			t.Errorf("Zugriffslog soll %q enthalten:\n%s", sichtbar, ausgabe)
		}
	}
}

// AC-27: ein gesetztes, aber kurzes Maschinen-Geheimnis erzeugt beim Aufbau
// eine Warnzeile, der Endpunkt arbeitet mit dem konfigurierten Wert weiter
// (ein Deploy schliesst keinen Eingangskanal still). Fail-closed bleibt nur
// der Fall "kein Geheimnis gesetzt" (eigene Tests der Routen).
func TestMaschinenGeheimnisse_KurzWarntUndBleibtInBetrieb(t *testing.T) {
	kurz := "kurz-aber-gesetzt"
	var logBuf syncBuf
	alt := log.Writer()
	log.SetOutput(&logBuf)
	t.Cleanup(func() { log.SetOutput(alt) })

	r, _, _ := schutzRouter2961(t, func(c *config.Config) {
		c.StatusToken = kurz
		c.TelegramWebhookSecret = kurz
		c.StalwartWebhookPathSecret = kurz
		c.StalwartWebhookSecret = kurz
	})
	for _, name := range []string{"GZ_STATUS_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "STALWART_WEBHOOK_PATH_SECRET", "STALWART_WEBHOOK_SECRET"} {
		if !strings.Contains(logBuf.String(), "WARN [config] "+name) {
			t.Errorf("Warnzeile fuer %s fehlt:\n%s", name, logBuf.String())
		}
	}

	schick := func(method, pfad string, header map[string]string) int {
		req := httptest.NewRequest(method, pfad, strings.NewReader(`{}`))
		req.Header.Set("Content-Type", "application/json")
		for k, v := range header {
			req.Header.Set(k, v)
		}
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		return w.Code
	}
	if c := schick(http.MethodGet, "/api/scheduler/status", map[string]string{"X-GZ-Status-Token": kurz}); c != http.StatusOK {
		t.Fatalf("kurzes Status-Token: erwartet 200 (in Betrieb), bekommen %d", c)
	}
	if c := schick(http.MethodGet, "/api/scheduler/status", map[string]string{"X-GZ-Status-Token": "falsch"}); c != http.StatusUnauthorized {
		t.Fatalf("falsches Status-Token: erwartet 401, bekommen %d", c)
	}
	if c := schick(http.MethodPost, "/api/webhooks/telegram/inbound", map[string]string{"X-Telegram-Bot-Api-Secret-Token": "falsch"}); c != http.StatusForbidden {
		t.Fatalf("Telegram mit kurzem Secret, falscher Header: erwartet 403 (konfiguriert), bekommen %d", c)
	}
	if c := schick(http.MethodPost, "/api/webhooks/telegram/inbound", map[string]string{"X-Telegram-Bot-Api-Secret-Token": kurz}); c == http.StatusForbidden || c == http.StatusServiceUnavailable {
		t.Fatalf("Telegram mit kurzem Secret, richtiger Header: Endpunkt muss arbeiten, bekommen %d", c)
	}
	if c := schick(http.MethodPost, "/api/webhooks/mail/"+kurz, map[string]string{"Authorization": "Bearer " + kurz}); c == http.StatusForbidden || c == http.StatusServiceUnavailable {
		t.Fatalf("Mail mit kurzen Secrets: Endpunkt muss arbeiten, bekommen %d", c)
	}
}
