package router

// TDD RED — Issue #2163 Scheibe 1, Punkt-7-Block (abtrennbar), AC-17/AC-18.
// Spec: docs/specs/modules/auth_haertung_go_2163.md
//
// Ueber den ECHTEN Router (router.New inkl. AuthMiddleware) pruefen die
// Webhook-Eingaenge ihre Secrets aus config.Config (Router reicht
// deps.Config.<Feld> an die Handler durch), nicht mehr per os.Getenv.
//
// Diskriminator ("Koeder"): In der Umgebung stehen fuer alle sechs Variablen
// bewusst FALSCHE Koeder-Werte; die richtigen Werte stehen NUR im Config-Feld
// (nach config.Load ueberschrieben). Der Wert kommt also allein aus der Config
// — die Umgebung ist ausschliesslich die Falle fuer einen Handler, der noch
// os.Getenv liest:
//   - richtiger Config-Wert                 -> Erfolg (200)
//   - Koeder-Wert aus der Umgebung          -> 403
//   - leeres Config-Feld (Koeder in Umgebung) -> 503 (fail-closed)
// Ohne Koeder (nur "keine Umgebung") wuerde die Mutation "Handler liest weiter
// os.Getenv" im 503-Fall nicht auffallen.
//
// Telegram-Link (TELEGRAM_BOT_USERNAME, telegram_connect.go): konfiguriert ->
// 200 mit t.me/<bot>; leer -> 500 wie bisher.
//
// RED-Beleg: Build-Fehler "cfg.TelegramWebhookSecret undefined" usw. (bricht
// das Testbinary des Pakets internal/router bis zur Umsetzung).

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const cfgWebhookPublicHost = "https://test.example.com"

// koederEnv stellt fuer alle sechs Variablen (unpraefixiert UND GZ_) falsche
// Werte in die Umgebung. config.Load liest sie in die Felder; der Test
// ueberschreibt die Felder danach mit den richtigen Werten.
func koederEnv(t *testing.T) {
	t.Helper()
	for k, v := range map[string]string{
		"TELEGRAM_WEBHOOK_SECRET":      "tg-koeder",
		"TELEGRAM_BOT_USERNAME":        "koeder_bot",
		"SEVEN_WEBHOOK_PATH_SECRET":    "sms-pfad-koeder",
		"SEVEN_WEBHOOK_SIGNING_KEY":    "sms-key-koeder",
		"STALWART_WEBHOOK_PATH_SECRET": "mail-pfad-koeder",
		"STALWART_WEBHOOK_SECRET":      "mail-bearer-koeder",
	} {
		t.Setenv(k, v)
		t.Setenv("GZ_"+k, v)
	}
}

type cfgWebhookCore struct {
	mu        sync.Mutex
	tgHeaders []string
	smsPolls  atomic.Int32
	mailPolls atomic.Int32
}

func (c *cfgWebhookCore) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch r.URL.Path {
	case "/api/internal/telegram-webhook":
		c.mu.Lock()
		c.tgHeaders = append(c.tgHeaders, r.Header.Get(tgHeader))
		c.mu.Unlock()
	case "/api/scheduler/inbound-sms":
		c.smsPolls.Add(1)
	case "/api/scheduler/inbound-commands":
		c.mailPolls.Add(1)
	}
	io.Copy(io.Discard, r.Body)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprint(w, `{"status":"ok","processed":0,"count":0}`)
}

func (c *cfgWebhookCore) telegramHeaders() []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return append([]string(nil), c.tgHeaders...)
}

// cfgWebhookRouter baut den echten Router; die Webhook-Werte kommen allein aus
// set(cfg). Nutzer alice/bob mit gueltigen Sitzungen.
func cfgWebhookRouter(t *testing.T, set func(cfg *config.Config)) (http.Handler, *cfgWebhookCore, string) {
	t.Helper()
	koederEnv(t)
	t.Setenv("GZ_ENV", "")

	core := &cfgWebhookCore{}
	srv := httptest.NewServer(core)
	t.Cleanup(srv.Close)

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.UserID = "ops"
	cfg.PythonCoreURL = srv.URL
	cfg.PublicHost = cfgWebhookPublicHost
	// Ausgangszustand: kein Webhook konfiguriert (Koeder aus der Umgebung
	// verworfen); set() setzt die richtigen Werte des jeweiligen Falls.
	cfg.TelegramWebhookSecret = ""
	cfg.TelegramBotUsername = ""
	cfg.SevenWebhookPathSecret = ""
	cfg.SevenWebhookSigningKey = ""
	cfg.StalwartWebhookPathSecret = ""
	cfg.StalwartWebhookSecret = ""
	set(cfg)

	s := store.New(cfg.DataDir, cfg.UserID)
	for _, id := range []string{"alice", "bob"} {
		if err := s.SaveUser(model.User{ID: id, CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
		if err := s.AddSession(id, sessionIDFor(id)); err != nil {
			t.Fatalf("AddSession %s: %v", id, err)
		}
	}
	wa, err := webauthn.New(&webauthn.Config{
		RPID: cfg.WebAuthnRPID, RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins: []string{"http://localhost:5173"},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := New(Deps{
		Config: cfg, Store: s, WebAuthn: wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})
	return r, core, cfg.SessionSecret
}

func waitAtLeast(c *atomic.Int32, n int32) bool {
	deadline := time.Now().Add(3 * time.Second)
	for c.Load() < n && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}
	return c.Load() >= n
}

// --- AC-17: Telegram -------------------------------------------------------

func TestTelegramWebhook_SecretAusConfig_Falsch403_Richtig200_Leer503_AC17(t *testing.T) {
	const richtig = "tg-richtig-2163"
	body := `{"update_id":7,"message":{"chat":{"id":1001},"text":"status"}}`

	t.Run("richtig -> 200 und Weiterreichung mit Config-Secret", func(t *testing.T) {
		r, core, _ := cfgWebhookRouter(t, func(c *config.Config) { c.TelegramWebhookSecret = richtig })
		w := tgPost(r, "/api/webhooks/telegram/inbound", body, richtig)
		if w.Code != http.StatusOK {
			t.Fatalf("AC-17: richtiges Config-Secret: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
		}
		got := core.telegramHeaders()
		if len(got) != 1 || got[0] != richtig {
			t.Errorf("AC-17: Core muss genau ein Update mit dem Config-Secret im Header sehen, sah %v", got)
		}
	})

	t.Run("Koeder aus Umgebung und falsch -> 403", func(t *testing.T) {
		r, core, _ := cfgWebhookRouter(t, func(c *config.Config) { c.TelegramWebhookSecret = richtig })
		for _, h := range []string{"tg-koeder", "falsch", ""} {
			w := tgPost(r, "/api/webhooks/telegram/inbound", body, h)
			if w.Code != http.StatusForbidden {
				t.Errorf("AC-17: Header %q: erwartet 403, bekommen %d", h, w.Code)
			}
		}
		if n := len(core.telegramHeaders()); n != 0 {
			t.Errorf("AC-17: abgewiesene Updates duerfen den Core nicht erreichen, sah %d", n)
		}
	})

	t.Run("leeres Config-Feld -> 503 trotz Koeder in Umgebung", func(t *testing.T) {
		r, _, _ := cfgWebhookRouter(t, func(c *config.Config) {})
		for _, h := range []string{"tg-koeder", richtig} {
			w := tgPost(r, "/api/webhooks/telegram/inbound", body, h)
			if w.Code != http.StatusServiceUnavailable {
				t.Errorf("AC-17: leeres Config-Secret, Header %q: erwartet 503 (fail-closed), bekommen %d", h, w.Code)
			}
		}
	})
}

// --- AC-17 (Bot-Name): Telegram-Link ----------------------------------------

func TestTelegramLink_BotNameAusConfig_AC17(t *testing.T) {
	get := func(r http.Handler, secret string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodGet, "/api/auth/telegram-link", nil)
		req.AddCookie(sessionCookieFor("alice", secret))
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		return w
	}

	t.Run("konfiguriert -> 200 mit t.me/<Config-Bot>", func(t *testing.T) {
		r, _, secret := cfgWebhookRouter(t, func(c *config.Config) { c.TelegramBotUsername = "richtiger_bot" })
		w := get(r, secret)
		if w.Code != http.StatusOK {
			t.Fatalf("Bot-Name aus Config: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
		}
		var resp struct {
			Link string `json:"link"`
		}
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("Antwort kein JSON: %v — %s", err, w.Body.String())
		}
		if !strings.HasPrefix(resp.Link, "https://t.me/richtiger_bot?start=") {
			t.Errorf("Link muss den Bot-Namen aus der Config tragen (nicht den Koeder), bekommen %q", resp.Link)
		}
	})

	t.Run("leer -> 500 wie bisher trotz Koeder in Umgebung", func(t *testing.T) {
		r, _, secret := cfgWebhookRouter(t, func(c *config.Config) {})
		w := get(r, secret)
		if w.Code != http.StatusInternalServerError {
			t.Errorf("leerer Bot-Name: erwartet 500, bekommen %d: %s", w.Code, w.Body.String())
		}
	})
}

// --- AC-18: seven.io (Pfad-Secret + Signatur) --------------------------------

func sevenSignedPost(r http.Handler, pfadSecret, signierKey, signierPfadSecret string) *httptest.ResponseRecorder {
	body := `{"webhook_event":"sms_mo","data":{"text":"status"}}`
	ts := strconv.FormatInt(time.Now().Unix(), 10)
	nonce := fmt.Sprintf("ac18-%d", time.Now().UnixNano())
	fullURL := cfgWebhookPublicHost + "/api/webhooks/sms/" + signierPfadSecret
	req := httptest.NewRequest(http.MethodPost, "/api/webhooks/sms/"+pfadSecret, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Timestamp", ts)
	req.Header.Set("X-Nonce", nonce)
	req.Header.Set("X-Signature", sevenSignaturUnabhaengig(signierKey, ts, nonce, http.MethodPost, fullURL, body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req) // ohne Sitzung
	return w
}

func TestSevenWebhook_SecretsAusConfig_Falsch403_Richtig200_Leer503_AC18(t *testing.T) {
	const pfad, key = "sms-pfad-richtig", "sms-key-richtig"
	setBeide := func(c *config.Config) { c.SevenWebhookPathSecret = pfad; c.SevenWebhookSigningKey = key }

	t.Run("richtig -> 200 und Kick", func(t *testing.T) {
		r, core, _ := cfgWebhookRouter(t, setBeide)
		w := sevenSignedPost(r, pfad, key, pfad)
		if w.Code != http.StatusOK {
			t.Fatalf("AC-18 seven: richtige Config-Werte: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
		}
		if !waitAtLeast(&core.smsPolls, 1) {
			t.Error("AC-18 seven: angenommener Webhook muss premium_sms_poll anstossen")
		}
	})

	t.Run("falsch -> 403", func(t *testing.T) {
		r, _, _ := cfgWebhookRouter(t, setBeide)
		faelle := []struct{ name, pfad, key, signPfad string }{
			{"Koeder-Pfad + Koeder-Signatur aus Umgebung", "sms-pfad-koeder", "sms-key-koeder", "sms-pfad-koeder"},
			{"richtiger Pfad, Signatur mit Koeder-Key", pfad, "sms-key-koeder", pfad},
			{"falscher Pfad, richtige Signatur", "falsch", key, "falsch"},
		}
		for _, f := range faelle {
			if w := sevenSignedPost(r, f.pfad, f.key, f.signPfad); w.Code != http.StatusForbidden {
				t.Errorf("AC-18 seven: %s: erwartet 403, bekommen %d", f.name, w.Code)
			}
		}
	})

	t.Run("leer -> 503 trotz Koeder in Umgebung", func(t *testing.T) {
		faelle := []struct {
			name string
			set  func(*config.Config)
		}{
			{"beide leer", func(c *config.Config) {}},
			{"nur Pfad-Secret gesetzt", func(c *config.Config) { c.SevenWebhookPathSecret = pfad }},
			{"nur Signier-Key gesetzt", func(c *config.Config) { c.SevenWebhookSigningKey = key }},
		}
		for _, f := range faelle {
			r, _, _ := cfgWebhookRouter(t, f.set)
			for _, p := range []string{"sms-pfad-koeder", pfad} {
				if w := sevenSignedPost(r, p, "sms-key-koeder", p); w.Code != http.StatusServiceUnavailable {
					t.Errorf("AC-18 seven: %s, Pfad %q: erwartet 503 (fail-closed), bekommen %d", f.name, p, w.Code)
				}
			}
		}
	})
}

// --- AC-18: Stalwart (Pfad-Secret + Bearer) ----------------------------------

func stalwartPost(r http.Handler, pfadSecret, bearer string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/webhooks/mail/"+pfadSecret, strings.NewReader(`{}`))
	req.Header.Set("Content-Type", "application/json")
	if bearer != "" {
		req.Header.Set("Authorization", "Bearer "+bearer)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req) // ohne Sitzung
	return w
}

func TestStalwartWebhook_SecretsAusConfig_Falsch403_Richtig200_Leer503_AC18(t *testing.T) {
	const pfad, bearer = "mail-pfad-richtig", "mail-bearer-richtig"
	setBeide := func(c *config.Config) { c.StalwartWebhookPathSecret = pfad; c.StalwartWebhookSecret = bearer }

	t.Run("richtig -> 200 und Kick", func(t *testing.T) {
		r, core, _ := cfgWebhookRouter(t, setBeide)
		w := stalwartPost(r, pfad, bearer)
		if w.Code != http.StatusOK {
			t.Fatalf("AC-18 Stalwart: richtige Config-Werte: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
		}
		if !waitAtLeast(&core.mailPolls, 1) {
			t.Error("AC-18 Stalwart: angenommener Webhook muss inbound_command_poll anstossen")
		}
	})

	t.Run("falsch -> 403", func(t *testing.T) {
		r, _, _ := cfgWebhookRouter(t, setBeide)
		faelle := []struct{ name, pfad, bearer string }{
			{"Koeder-Pfad + Koeder-Bearer aus Umgebung", "mail-pfad-koeder", "mail-bearer-koeder"},
			{"richtiger Pfad, Koeder-Bearer", pfad, "mail-bearer-koeder"},
			{"falscher Pfad, richtiger Bearer", "falsch", bearer},
			{"richtiger Pfad, ohne Bearer", pfad, ""},
		}
		for _, f := range faelle {
			if w := stalwartPost(r, f.pfad, f.bearer); w.Code != http.StatusForbidden {
				t.Errorf("AC-18 Stalwart: %s: erwartet 403, bekommen %d", f.name, w.Code)
			}
		}
	})

	t.Run("leer -> 503 trotz Koeder in Umgebung", func(t *testing.T) {
		faelle := []struct {
			name string
			set  func(*config.Config)
		}{
			{"beide leer", func(c *config.Config) {}},
			{"nur Pfad-Secret gesetzt", func(c *config.Config) { c.StalwartWebhookPathSecret = pfad }},
			{"nur Bearer gesetzt", func(c *config.Config) { c.StalwartWebhookSecret = bearer }},
		}
		for _, f := range faelle {
			r, _, _ := cfgWebhookRouter(t, f.set)
			if w := stalwartPost(r, "mail-pfad-koeder", "mail-bearer-koeder"); w.Code != http.StatusServiceUnavailable {
				t.Errorf("AC-18 Stalwart: %s: erwartet 503 (fail-closed), bekommen %d", f.name, w.Code)
			}
		}
	})
}
