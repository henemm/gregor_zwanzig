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

// AC-27: ein gesetztes, aber zu kurzes Maschinen-Geheimnis haelt den
// Endpunkt geschlossen (fail-closed), statt mit dem schwachen Wert zu oeffnen.
func TestMaschinenGeheimnisse_ZuKurzHaeltEndpunktGeschlossen(t *testing.T) {
	kurz := "kurz-aber-gesetzt"
	lang := strings.Repeat("s", 32)

	r, _, _ := schutzRouter2961(t, func(c *config.Config) { c.StatusToken = kurz })
	req := httptest.NewRequest(http.MethodGet, "/api/scheduler/status", nil)
	req.Header.Set("X-GZ-Status-Token", kurz)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("kurzes Status-Token: erwartet 401 (geschlossen), bekommen %d", w.Code)
	}

	r, _, _ = schutzRouter2961(t, func(c *config.Config) { c.StatusToken = lang })
	req = httptest.NewRequest(http.MethodGet, "/api/scheduler/status", nil)
	req.Header.Set("X-GZ-Status-Token", lang)
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("ausreichend langes Status-Token: erwartet 200, bekommen %d", w.Code)
	}

	r, _, _ = schutzRouter2961(t, func(c *config.Config) { c.TelegramWebhookSecret = kurz })
	req = httptest.NewRequest(http.MethodPost, "/api/webhooks/telegram/inbound", strings.NewReader(`{}`))
	req.Header.Set("X-Telegram-Bot-Api-Secret-Token", kurz)
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code < 400 {
		t.Fatalf("kurzes Telegram-Secret: Endpunkt muss geschlossen sein, bekommen %d", w.Code)
	}

	r, _, _ = schutzRouter2961(t, func(c *config.Config) {
		c.StalwartWebhookPathSecret = kurz
		c.StalwartWebhookSecret = lang
	})
	req = httptest.NewRequest(http.MethodPost, "/api/webhooks/mail/"+kurz, strings.NewReader(`{}`))
	req.Header.Set("Authorization", "Bearer "+lang)
	w = httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code < 400 {
		t.Fatalf("kurzes Mail-Pfadgeheimnis: Endpunkt muss geschlossen sein, bekommen %d", w.Code)
	}
}
