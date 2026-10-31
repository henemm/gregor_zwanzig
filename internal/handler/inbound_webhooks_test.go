package handler

// TDD RED: Issue #2439 Scheibe (a) — Push-Eingang fuer Befehle, Webhook-
// Handler. Spec: docs/specs/modules/feat_2439_befehle_push_eingang.md
//
// AC-Zuordnung:
//   AC-3   TestSMSWebhook_Abgewiesen_* / TestMailWebhook_Abgewiesen_*
//          (kein Lauf am Server, rejected_total++, last_received bleibt nil)
//   AC-4   TestSMSWebhook_503_* / TestMailWebhook_503_*
//   AC-9   TestWebhooks_StatusZaehler_GueltigUndAbgewiesen (Zaehler im Status)
//   AC-12  Die SMS-Signatur wird ausschliesslich gegen die Fixture
//          internal/handler/testdata/seven_sms_mo.json geprueft -- ein Testvektor
//          (Test-Schluessel, Fantasienummern) nach dem gegen seven.io belegten
//          Algorithmus (docs/artifacts/feat-2439-befehle-push-eingang/
//          seven-signatur-nachweis.md, testdata/README.md); hier wird NICHTS
//          selbst signiert.
//          Fehlt die Datei, scheitern die SMS-Tests mit klarer Meldung (t.Fatalf).
//   AC-1/AC-2 (Handler-Seite) TestSMSWebhook_Gueltig_* / TestMailWebhook_Gueltig_*
//          (200 + der Poll-Job laeuft am Server SOFORT, ohne 5-min-Tick).
//
// Die Fixture ist ein Testvektor (kein Mitschnitt: der echte Schluessel und echte
// Nummern duerfen nicht ins Repo). Format (JSON):
//   { "url": "<volle Ziel-URL inkl. Pfad-Secret>", "method": "POST",
//     "headers": { "X-Signature": ..., "X-Timestamp": ..., "X-Nonce": ...,
//                  "Content-Type": ... },
//     "body": "<roher Body als String>", "signing_key": "...",
//     "public_host": "https://..." }
// Pfad-Secret = letztes Pfadsegment von "url"; Uhr = X-Timestamp (Unix-Sekunden).
//
// Mail: Die Header-Form des Stalwart-Webhooks wird vor GREEN gegen Stalwart
// v0.16.26 bestaetigt. Bis dahin prueft der Test NUR das Mindestmass:
// Pfad-Secret + "Authorization: Bearer <STALWART_WEBHOOK_SECRET>". Zeigt die
// Verifikation eine andere Form (z. B. X-Signature-HMAC), ist DIESER Test
// bewusst mit anzupassen -- nicht den Handler an den Test.
//
// Env: SEVEN_WEBHOOK_PATH_SECRET, SEVEN_WEBHOOK_SIGNING_KEY,
//      STALWART_WEBHOOK_PATH_SECRET, STALWART_WEBHOOK_SECRET.
// Kein t.Parallel() (t.Setenv).
//
// Der Scheduler zeigt auf einen httptest-"Python-Core", der Aufrufe zaehlt. Er
// antwortet mit processed=1, damit der Kick keine Nachversuche (3/8 s) macht.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	webhookPfadSMS  = "/api/scheduler/inbound-sms"
	webhookPfadMail = "/api/scheduler/inbound-commands"
)

// ---------------------------------------------------------------------------
// Aufbau: Scheduler gegen zaehlenden Fake-Core
// ---------------------------------------------------------------------------

type zaehlenderCore struct {
	srv  *httptest.Server
	sms  atomic.Int32
	mail atomic.Int32
}

func neuerZaehlenderCore(t *testing.T) *zaehlenderCore {
	t.Helper()
	c := &zaehlenderCore{}
	c.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case webhookPfadSMS:
			c.sms.Add(1)
		case webhookPfadMail:
			c.mail.Add(1)
		}
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","processed":1,"count":1}`)
	}))
	t.Cleanup(c.srv.Close)
	return c
}

func neuerSchedulerFuer(t *testing.T, core *zaehlenderCore) *scheduler.Scheduler {
	t.Helper()
	cfg := &config.Config{PythonCoreURL: core.srv.URL, SchedulerTimezone: "Europe/Vienna"}
	dir := t.TempDir()
	st := store.New(dir, "default")
	st.ProvisionUserDirs("default")
	s, err := scheduler.New(cfg, st)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	return s
}

func warteBis(t *testing.T, limit time.Duration, cond func() bool, msg string) {
	t.Helper()
	deadline := time.Now().Add(limit)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("Zeitueberschreitung nach %v: %s", limit, msg)
}

func keinLaufInnerhalb(t *testing.T, core *zaehlenderCore, was string) {
	t.Helper()
	time.Sleep(300 * time.Millisecond)
	if n := core.sms.Load() + core.mail.Load(); n != 0 {
		t.Errorf("%s: es darf KEIN Poll-Lauf am Core ankommen, gezaehlt: sms=%d mail=%d",
			was, core.sms.Load(), core.mail.Load())
	}
}

// pushStatus liest Status()["jobs"][id]["push"].
func pushStatus(t *testing.T, s *scheduler.Scheduler, jobID string) map[string]any {
	t.Helper()
	jobs, ok := s.Status()["jobs"].([]map[string]any)
	if !ok {
		t.Fatalf("Status()[\"jobs\"] hat unerwarteten Typ")
	}
	for _, j := range jobs {
		if j["id"] != jobID {
			continue
		}
		push, ok := j["push"].(map[string]any)
		if !ok {
			t.Fatalf("Job %q: Feld \"push\" fehlt: %T", jobID, j["push"])
		}
		return push
	}
	t.Fatalf("Job %q nicht im Status", jobID)
	return nil
}

func zahl(t *testing.T, v any) int {
	t.Helper()
	switch n := v.(type) {
	case int:
		return n
	case int32:
		return int(n)
	case int64:
		return int(n)
	case uint64:
		return int(n)
	case float64:
		return int(n)
	}
	t.Fatalf("Zahlenfeld erwartet, bekam %T", v)
	return 0
}

// ---------------------------------------------------------------------------
// seven.io-Fixture (aufgezeichnet)
// ---------------------------------------------------------------------------

type sevenFixture struct {
	URL        string            `json:"url"`
	Method     string            `json:"method"`
	Headers    map[string]string `json:"headers"`
	Body       string            `json:"body"`
	SigningKey string            `json:"signing_key"`
	PublicHost string            `json:"public_host"`
}

func (f sevenFixture) pfadSecret(t *testing.T) string {
	t.Helper()
	u, err := url.Parse(f.URL)
	if err != nil {
		t.Fatalf("Fixture-url nicht parsebar: %v", err)
	}
	return u.Path[strings.LastIndex(u.Path, "/")+1:]
}

func (f sevenFixture) zeit(t *testing.T) time.Time {
	t.Helper()
	sec, err := strconv.ParseInt(f.Headers["X-Timestamp"], 10, 64)
	if err != nil {
		t.Fatalf("Fixture X-Timestamp keine Unix-Sekunden: %q (%v)", f.Headers["X-Timestamp"], err)
	}
	return time.Unix(sec, 0)
}

func ladeSevenFixture(t *testing.T) sevenFixture {
	t.Helper()
	p := filepath.Join("testdata", "seven_sms_mo.json")
	raw, err := os.ReadFile(p)
	if err != nil {
		t.Fatalf("AC-12: aufgezeichnete seven.io-Fixture %s fehlt (%v). Sie muss vor GREEN "+
			"als Testvektor nach dem belegten Algorithmus vorliegen (Header X-Signature/"+
			"X-Timestamp/X-Nonce, roher Body, Test-Signing-Key, PublicHost, siehe testdata/README.md).", p, err)
	}
	var f sevenFixture
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatalf("Fixture %s kein gueltiges JSON: %v", p, err)
	}
	for name, v := range map[string]string{
		"url": f.URL, "body": f.Body, "signing_key": f.SigningKey, "public_host": f.PublicHost,
		"headers.X-Signature": f.Headers["X-Signature"], "headers.X-Timestamp": f.Headers["X-Timestamp"],
		"headers.X-Nonce": f.Headers["X-Nonce"],
	} {
		if v == "" {
			t.Fatalf("Fixture %s: Feld %s fehlt/leer", p, name)
		}
	}
	return f
}

// smsAufbau: Fixture laden, Env setzen, Handler hinter chi mit der echten Route.
type smsAufbau struct {
	fix    sevenFixture
	core   *zaehlenderCore
	sched  *scheduler.Scheduler
	router http.Handler
}

func neuerSMSAufbau(t *testing.T, jetzt func(fix sevenFixture) time.Time) *smsAufbau {
	t.Helper()
	fix := ladeSevenFixture(t)
	t.Setenv("SEVEN_WEBHOOK_PATH_SECRET", fix.pfadSecret(t))
	t.Setenv("SEVEN_WEBHOOK_SIGNING_KEY", fix.SigningKey)
	core := neuerZaehlenderCore(t)
	sched := neuerSchedulerFuer(t, core)
	uhr := fix.zeit(t)
	if jetzt != nil {
		uhr = jetzt(fix)
	}
	r := chi.NewRouter()
	r.Post("/api/webhooks/sms/{secret}", InboundSMSWebhook(sched, fix.PublicHost, func() time.Time { return uhr }))
	return &smsAufbau{fix: fix, core: core, sched: sched, router: r}
}

// anfrage baut die aufgezeichnete Anfrage nach; mutate darf sie veraendern.
func (a *smsAufbau) anfrage(pfadSecret string, body string, mutate func(*http.Request)) *http.Request {
	req := httptest.NewRequest(http.MethodPost, "/api/webhooks/sms/"+pfadSecret, strings.NewReader(body))
	for k, v := range a.fix.Headers {
		req.Header.Set(k, v)
	}
	if mutate != nil {
		mutate(req)
	}
	return req
}

func (a *smsAufbau) senden(req *http.Request) *httptest.ResponseRecorder {
	rr := httptest.NewRecorder()
	a.router.ServeHTTP(rr, req)
	return rr
}

// ---------------------------------------------------------------------------
// SMS: gueltig (AC-1 Handler-Seite, AC-9, AC-12)
// ---------------------------------------------------------------------------

func TestSMSWebhook_Gueltig_200KickLaeuftSofortUndZaehlerSteigen(t *testing.T) {
	a := neuerSMSAufbau(t, nil)

	rr := a.senden(a.anfrage(a.fix.pfadSecret(t), a.fix.Body, nil))

	if rr.Code != http.StatusOK {
		t.Fatalf("aufgezeichnete, gueltig signierte Anfrage: erwartet 200, bekam %d: %s", rr.Code, rr.Body.String())
	}
	warteBis(t, 3*time.Second, func() bool { return a.core.sms.Load() >= 1 },
		"der gueltige Webhook muss premium_sms_poll sofort anstossen (POST /inbound-sms am Core)")
	if a.core.mail.Load() != 0 {
		t.Errorf("SMS-Webhook darf den Mail-Poll nicht anstossen, Aufrufe: %d", a.core.mail.Load())
	}
	push := pushStatus(t, a.sched, "premium_sms_poll")
	if zahl(t, push["received_total"]) != 1 {
		t.Errorf("received_total erwartet 1, bekam %v", push["received_total"])
	}
	if zahl(t, push["rejected_total"]) != 0 {
		t.Errorf("rejected_total erwartet 0, bekam %v", push["rejected_total"])
	}
	if push["last_received"] == nil {
		t.Error("last_received muss nach bestandener Pruefung gesetzt sein")
	}
}

// Signatur-URL kommt aus publicHost + Pfad, NIE aus r.URL/Host-Header.
func TestSMSWebhook_AndererHostHeaderBleibtGueltig(t *testing.T) {
	a := neuerSMSAufbau(t, nil)

	req := a.anfrage(a.fix.pfadSecret(t), a.fix.Body, func(r *http.Request) {
		r.Host = "intern.example:8090"
		r.Header.Set("X-Forwarded-Host", "intern.example:8090")
	})
	rr := a.senden(req)

	if rr.Code != http.StatusOK {
		t.Fatalf("anderer Host-Header bei gleicher Anfrage: erwartet 200 (Signatur-URL aus PublicHost), bekam %d", rr.Code)
	}
	warteBis(t, 3*time.Second, func() bool { return a.core.sms.Load() >= 1 }, "Lauf erwartet")
}

// ---------------------------------------------------------------------------
// SMS: abgewiesen (AC-3) -- 403, kein Lauf, rejected_total++, last_received nil
// ---------------------------------------------------------------------------

func TestSMSWebhook_Abgewiesen_Varianten(t *testing.T) {
	faelle := []struct {
		name string
		// baut Aufbau + Anfrage; liefert Aufbau und Request
		bauen func(t *testing.T) (*smsAufbau, *http.Request)
	}{
		{"manipulierter Body", func(t *testing.T) (*smsAufbau, *http.Request) {
			a := neuerSMSAufbau(t, nil)
			b := a.fix.Body + " "
			return a, a.anfrage(a.fix.pfadSecret(t), b, nil)
		}},
		{"falsches Pfad-Secret", func(t *testing.T) (*smsAufbau, *http.Request) {
			a := neuerSMSAufbau(t, nil)
			return a, a.anfrage(a.fix.pfadSecret(t)+"x", a.fix.Body, nil)
		}},
		{"veralteter Timestamp (Fixture + 31 s)", func(t *testing.T) (*smsAufbau, *http.Request) {
			a := neuerSMSAufbau(t, func(f sevenFixture) time.Time { return f.zeit(t).Add(31 * time.Second) })
			return a, a.anfrage(a.fix.pfadSecret(t), a.fix.Body, nil)
		}},
		{"Timestamp aus der Zukunft (Fixture - 31 s)", func(t *testing.T) (*smsAufbau, *http.Request) {
			a := neuerSMSAufbau(t, func(f sevenFixture) time.Time { return f.zeit(t).Add(-31 * time.Second) })
			return a, a.anfrage(a.fix.pfadSecret(t), a.fix.Body, nil)
		}},
		{"fehlende Signatur", func(t *testing.T) (*smsAufbau, *http.Request) {
			a := neuerSMSAufbau(t, nil)
			return a, a.anfrage(a.fix.pfadSecret(t), a.fix.Body, func(r *http.Request) { r.Header.Del("X-Signature") })
		}},
		{"veraenderte Signatur", func(t *testing.T) (*smsAufbau, *http.Request) {
			a := neuerSMSAufbau(t, nil)
			return a, a.anfrage(a.fix.pfadSecret(t), a.fix.Body, func(r *http.Request) {
				sig := r.Header.Get("X-Signature")
				flip := "0"
				if strings.HasSuffix(sig, "0") {
					flip = "1"
				}
				r.Header.Set("X-Signature", sig[:len(sig)-1]+flip)
			})
		}},
		{"veraenderte Nonce", func(t *testing.T) (*smsAufbau, *http.Request) {
			a := neuerSMSAufbau(t, nil)
			return a, a.anfrage(a.fix.pfadSecret(t), a.fix.Body, func(r *http.Request) {
				r.Header.Set("X-Nonce", r.Header.Get("X-Nonce")+"x")
			})
		}},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			a, req := f.bauen(t)

			rr := a.senden(req)

			if rr.Code != http.StatusForbidden {
				t.Errorf("erwartet 403, bekam %d", rr.Code)
			}
			keinLaufInnerhalb(t, a.core, f.name)
			push := pushStatus(t, a.sched, "premium_sms_poll")
			if zahl(t, push["rejected_total"]) != 1 {
				t.Errorf("rejected_total erwartet 1, bekam %v", push["rejected_total"])
			}
			if zahl(t, push["received_total"]) != 0 {
				t.Errorf("received_total darf bei Abweisung nicht steigen, bekam %v", push["received_total"])
			}
			if push["last_received"] != nil {
				t.Errorf("last_received muss nil bleiben, bekam %v", push["last_received"])
			}
		})
	}
}

// AC-3: wiederverwendete Nonce -- erste Anfrage gueltig, identische zweite 403.
func TestSMSWebhook_Abgewiesen_WiederverwendeteNonce(t *testing.T) {
	a := neuerSMSAufbau(t, nil)

	erste := a.senden(a.anfrage(a.fix.pfadSecret(t), a.fix.Body, nil))
	if erste.Code != http.StatusOK {
		t.Fatalf("erste (gueltige) Anfrage: erwartet 200, bekam %d", erste.Code)
	}
	warteBis(t, 3*time.Second, func() bool { return a.core.sms.Load() >= 1 }, "erster Lauf erwartet")
	time.Sleep(200 * time.Millisecond)
	laeufeVorher := a.core.sms.Load()

	zweite := a.senden(a.anfrage(a.fix.pfadSecret(t), a.fix.Body, nil))

	if zweite.Code != http.StatusForbidden {
		t.Errorf("zweite Anfrage mit derselben Nonce: erwartet 403, bekam %d", zweite.Code)
	}
	time.Sleep(300 * time.Millisecond)
	if got := a.core.sms.Load(); got != laeufeVorher {
		t.Errorf("Replay darf keinen weiteren Lauf ausloesen (vorher %d, nachher %d)", laeufeVorher, got)
	}
	push := pushStatus(t, a.sched, "premium_sms_poll")
	if zahl(t, push["rejected_total"]) != 1 || zahl(t, push["received_total"]) != 1 {
		t.Errorf("erwartet received_total=1, rejected_total=1, bekam %v / %v",
			push["received_total"], push["rejected_total"])
	}
}

// ---------------------------------------------------------------------------
// SMS: 503 fail-closed (AC-4)
// ---------------------------------------------------------------------------

func TestSMSWebhook_503_EnvFehlt(t *testing.T) {
	for _, fehlend := range []string{"SEVEN_WEBHOOK_PATH_SECRET", "SEVEN_WEBHOOK_SIGNING_KEY"} {
		t.Run("ohne "+fehlend, func(t *testing.T) {
			a := neuerSMSAufbau(t, nil)
			t.Setenv(fehlend, "")

			rr := a.senden(a.anfrage(a.fix.pfadSecret(t), a.fix.Body, nil))

			if rr.Code != http.StatusServiceUnavailable {
				t.Errorf("erwartet 503 (fail-closed), bekam %d", rr.Code)
			}
			keinLaufInnerhalb(t, a.core, "503")
			push := pushStatus(t, a.sched, "premium_sms_poll")
			if zahl(t, push["received_total"]) != 0 || zahl(t, push["rejected_total"]) != 0 {
				t.Errorf("503 darf keinen Zaehler beruehren, bekam received=%v rejected=%v",
					push["received_total"], push["rejected_total"])
			}
			if push["last_received"] != nil {
				t.Errorf("last_received muss nil bleiben, bekam %v", push["last_received"])
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Mail (Header-Form vor GREEN gegen Stalwart v0.16.26 bestaetigen)
// ---------------------------------------------------------------------------

const (
	mailPfadSecret = "mail-pfad-secret-test-1f3a"
	mailBearer     = "stalwart-bearer-secret-test-9c2e"
)

type mailAufbau struct {
	core   *zaehlenderCore
	sched  *scheduler.Scheduler
	router http.Handler
}

func neuerMailAufbau(t *testing.T) *mailAufbau {
	t.Helper()
	t.Setenv("STALWART_WEBHOOK_PATH_SECRET", mailPfadSecret)
	t.Setenv("STALWART_WEBHOOK_SECRET", mailBearer)
	core := neuerZaehlenderCore(t)
	sched := neuerSchedulerFuer(t, core)
	r := chi.NewRouter()
	r.Post("/api/webhooks/mail/{secret}", InboundMailWebhook(sched))
	return &mailAufbau{core: core, sched: sched, router: r}
}

func (m *mailAufbau) senden(pfadSecret, authHeader string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/webhooks/mail/"+pfadSecret,
		strings.NewReader(`{"events":[{"id":"message-ingest.ham"}]}`))
	req.Header.Set("Content-Type", "application/json")
	if authHeader != "" {
		req.Header.Set("Authorization", authHeader)
	}
	rr := httptest.NewRecorder()
	m.router.ServeHTTP(rr, req)
	return rr
}

func TestMailWebhook_Gueltig_200KickLaeuftSofort(t *testing.T) {
	m := neuerMailAufbau(t)

	rr := m.senden(mailPfadSecret, "Bearer "+mailBearer)

	if rr.Code != http.StatusOK {
		t.Fatalf("erwartet 200, bekam %d: %s", rr.Code, rr.Body.String())
	}
	warteBis(t, 3*time.Second, func() bool { return m.core.mail.Load() >= 1 },
		"der gueltige Mail-Webhook muss inbound_command_poll sofort anstossen")
	if m.core.sms.Load() != 0 {
		t.Errorf("Mail-Webhook darf den SMS-Poll nicht anstossen, Aufrufe: %d", m.core.sms.Load())
	}
	push := pushStatus(t, m.sched, "inbound_command_poll")
	if zahl(t, push["received_total"]) != 1 || push["last_received"] == nil {
		t.Errorf("erwartet received_total=1 und gesetztes last_received, bekam %v / %v",
			push["received_total"], push["last_received"])
	}
}

func TestMailWebhook_Abgewiesen_Varianten(t *testing.T) {
	faelle := []struct{ name, pfad, auth string }{
		{"falsches Pfad-Secret", mailPfadSecret + "x", "Bearer " + mailBearer},
		{"fehlender Authorization-Header", mailPfadSecret, ""},
		{"falsches Bearer-Secret", mailPfadSecret, "Bearer " + mailBearer + "x"},
		{"Praefix des Bearer-Secrets", mailPfadSecret, "Bearer " + mailBearer[:len(mailBearer)-1]},
		{"Secret ohne Bearer-Schema", mailPfadSecret, mailBearer},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			m := neuerMailAufbau(t)

			rr := m.senden(f.pfad, f.auth)

			if rr.Code != http.StatusForbidden {
				t.Errorf("erwartet 403, bekam %d", rr.Code)
			}
			keinLaufInnerhalb(t, m.core, f.name)
			push := pushStatus(t, m.sched, "inbound_command_poll")
			if zahl(t, push["rejected_total"]) != 1 {
				t.Errorf("rejected_total erwartet 1, bekam %v", push["rejected_total"])
			}
			if zahl(t, push["received_total"]) != 0 || push["last_received"] != nil {
				t.Errorf("abgewiesen: received_total/last_received duerfen nicht steigen, bekam %v / %v",
					push["received_total"], push["last_received"])
			}
		})
	}
}

func TestMailWebhook_503_EnvFehlt(t *testing.T) {
	for _, fehlend := range []string{"STALWART_WEBHOOK_PATH_SECRET", "STALWART_WEBHOOK_SECRET"} {
		t.Run("ohne "+fehlend, func(t *testing.T) {
			m := neuerMailAufbau(t)
			t.Setenv(fehlend, "")

			rr := m.senden(mailPfadSecret, "Bearer "+mailBearer)

			if rr.Code != http.StatusServiceUnavailable {
				t.Errorf("erwartet 503 (fail-closed), bekam %d", rr.Code)
			}
			keinLaufInnerhalb(t, m.core, "503")
			push := pushStatus(t, m.sched, "inbound_command_poll")
			if zahl(t, push["received_total"]) != 0 || zahl(t, push["rejected_total"]) != 0 {
				t.Errorf("503 darf keinen Zaehler beruehren, bekam received=%v rejected=%v",
					push["received_total"], push["rejected_total"])
			}
		})
	}
}

// ---------------------------------------------------------------------------
// AC-9: gueltige UND abgewiesene Aufrufe, danach Status lesen
// ---------------------------------------------------------------------------

func TestWebhooks_StatusZaehler_GueltigUndAbgewiesen(t *testing.T) {
	// Mail-Seite: 2 gueltig, 3 abgewiesen
	m := neuerMailAufbau(t)
	for i := 0; i < 2; i++ {
		if rr := m.senden(mailPfadSecret, "Bearer "+mailBearer); rr.Code != http.StatusOK {
			t.Fatalf("gueltiger Mail-Aufruf %d: erwartet 200, bekam %d", i, rr.Code)
		}
		time.Sleep(50 * time.Millisecond)
	}
	for i := 0; i < 3; i++ {
		if rr := m.senden(mailPfadSecret, "Bearer falsch"); rr.Code != http.StatusForbidden {
			t.Fatalf("abgewiesener Mail-Aufruf %d: erwartet 403, bekam %d", i, rr.Code)
		}
	}
	mail := pushStatus(t, m.sched, "inbound_command_poll")
	if got := zahl(t, mail["received_total"]); got != 2 {
		t.Errorf("mail.received_total erwartet 2 (nur bestandene Pruefung), bekam %d", got)
	}
	if got := zahl(t, mail["rejected_total"]); got != 3 {
		t.Errorf("mail.rejected_total erwartet 3, bekam %d", got)
	}
	if _, ok := mail["kicks_coalesced"]; !ok {
		t.Error("push.kicks_coalesced fehlt im Status")
	}
	// SMS-Zeile des Mail-Schedulers bleibt unberuehrt (Zaehler je Kanal).
	sms := pushStatus(t, m.sched, "premium_sms_poll")
	if zahl(t, sms["received_total"]) != 0 || zahl(t, sms["rejected_total"]) != 0 {
		t.Errorf("Mail-Aufrufe duerfen SMS-Zaehler nicht beruehren: %v / %v",
			sms["received_total"], sms["rejected_total"])
	}

	// SMS-Seite: 1 gueltig (Fixture), 1 abgewiesen (falsches Secret)
	a := neuerSMSAufbau(t, nil)
	if rr := a.senden(a.anfrage(a.fix.pfadSecret(t), a.fix.Body, nil)); rr.Code != http.StatusOK {
		t.Fatalf("gueltiger SMS-Aufruf: erwartet 200, bekam %d", rr.Code)
	}
	if rr := a.senden(a.anfrage("falsch", a.fix.Body, nil)); rr.Code != http.StatusForbidden {
		t.Fatalf("abgewiesener SMS-Aufruf: erwartet 403, bekam %d", rr.Code)
	}
	smsPush := pushStatus(t, a.sched, "premium_sms_poll")
	if zahl(t, smsPush["received_total"]) != 1 || zahl(t, smsPush["rejected_total"]) != 1 {
		t.Errorf("sms: erwartet received=1 rejected=1, bekam %v / %v",
			smsPush["received_total"], smsPush["rejected_total"])
	}
	if smsPush["last_received"] == nil {
		t.Error("sms.last_received muss nach dem gueltigen Aufruf gesetzt sein")
	}
}
