package router

// TDD RED: Issue #2439 Scheibe (a) — die Webhook-Pfade
// /api/webhooks/sms/{secret} und /api/webhooks/mail/{secret} sind ueber den
// ECHTEN Router (router.New inkl. AuthMiddleware) sitzungsfrei erreichbar.
// Spec: docs/specs/modules/feat_2439_befehle_push_eingang.md
//
// AC-Zuordnung: AC-3 (falsches Secret -> 403, NICHT 401), AC-4 (Env fehlt ->
// 503, NICHT 401), AC-9 (Status-Endpoint ohne X-GZ-Status-Token weiterhin 401).
//
// RED-Signal heute: die Pfade sind nicht geroutet und nicht in der
// Sitzungs-Ausnahme -- die AuthMiddleware antwortet 401.
// Kein t.Parallel() (t.Setenv).

import (
	"crypto/hmac"
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
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
)

func webhookPost(r http.Handler, pfad string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, pfad, strings.NewReader(`{}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req) // bewusst OHNE gz_session-Cookie
	return w
}

func TestInboundWebhooks_SitzungsfreiErreichbar_FalschesSecretIst403(t *testing.T) {
	// Issue #2163: Werte gelten ueber config.Load, also VOR dem Router-Aufbau.
	t.Setenv("SEVEN_WEBHOOK_PATH_SECRET", "richtig-sms-pfad")
	t.Setenv("SEVEN_WEBHOOK_SIGNING_KEY", "signing-key-test")
	t.Setenv("STALWART_WEBHOOK_PATH_SECRET", "richtig-mail-pfad")
	t.Setenv("STALWART_WEBHOOK_SECRET", "stalwart-secret-test")
	r, _ := s2Router(t, s2Optionen{statusToken: s2Token})

	for _, pfad := range []string{"/api/webhooks/sms/falsch", "/api/webhooks/mail/falsch"} {
		w := webhookPost(r, pfad)
		if w.Code != http.StatusForbidden {
			t.Errorf("POST %s ohne Sitzung, falsches Pfad-Secret: erwartet 403 (Pfad ist sitzungsfrei, "+
				"Handler weist ab), bekam %d: %s", pfad, w.Code, w.Body.String())
		}
	}
}

func TestInboundWebhooks_EnvFehlt_503StattSitzungsabweisung(t *testing.T) {
	for _, k := range []string{"SEVEN_WEBHOOK_PATH_SECRET", "SEVEN_WEBHOOK_SIGNING_KEY",
		"STALWART_WEBHOOK_PATH_SECRET", "STALWART_WEBHOOK_SECRET"} {
		t.Setenv(k, "")
		t.Setenv("GZ_"+k, "")
	}
	r, _ := s2Router(t, s2Optionen{statusToken: s2Token})

	for _, pfad := range []string{"/api/webhooks/sms/irgendwas", "/api/webhooks/mail/irgendwas"} {
		w := webhookPost(r, pfad)
		if w.Code != http.StatusServiceUnavailable {
			t.Errorf("POST %s ohne konfigurierte Secrets: erwartet 503 (fail-closed), bekam %d: %s",
				pfad, w.Code, w.Body.String())
		}
	}
}

// Kontrollen: die Ausnahme ist auf die beiden Praefixe begrenzt, und der
// Status-Endpoint bleibt ohne Token abgewiesen (AC-9).
func TestInboundWebhooks_AusnahmeBleibtEng_StatusBleibtGeschuetzt(t *testing.T) {
	r, secret := s2Router(t, s2Optionen{statusToken: s2Token})

	pruefe401(t, "Status ohne Token", statusAbruf(t, r, secret, nil, ""))

	req := httptest.NewRequest(http.MethodGet, "/api/trips", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("GET /api/trips ohne Sitzung: weiterhin 401 erwartet, bekam %d", w.Code)
	}
}

// ---------------------------------------------------------------------------
// Adversary-Luecke F004: PublicHost ist im ECHTEN Router verdrahtet.
// ---------------------------------------------------------------------------

// sevenVektor ist der Testvektor internal/handler/testdata/seven_sms_mo.json.
type sevenVektor struct {
	URL        string            `json:"url"`
	Headers    map[string]string `json:"headers"`
	Body       string            `json:"body"`
	SigningKey string            `json:"signing_key"`
	PublicHost string            `json:"public_host"`
}

// sevenSignaturUnabhaengig rechnet das in testdata/README.md beschriebene
// Verfahren unabhaengig vom Produktionscode nach.
func sevenSignaturUnabhaengig(key, ts, nonce, method, fullURL, body string) string {
	sum := md5.Sum([]byte(body))
	msg := strings.Join([]string{ts, nonce, method, fullURL, hex.EncodeToString(sum[:])}, "\n")
	mac := hmac.New(sha256.New, []byte(key))
	mac.Write([]byte(msg))
	return hex.EncodeToString(mac.Sum(nil))
}

// Ein gueltig signierter seven.io-Webhook durch router.New: die Signatur-URL
// muss aus cfg.PublicHost (Env GZ_PUBLIC_HOST) entstehen. Der Router benutzt die
// echte Uhr, daher wird der Vektor mit frischem Timestamp/Nonce neu signiert --
// der Signier-Helfer ist vorher gegen die aufgezeichnete Signatur geprueft.
func TestInboundWebhooks_SMS_GueltigSigniertDurchEchtenRouter_200UndKick(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "handler", "testdata", "seven_sms_mo.json"))
	if err != nil {
		t.Fatalf("Testvektor lesen: %v", err)
	}
	var v sevenVektor
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatalf("Testvektor parsen: %v", err)
	}
	u, err := url.Parse(v.URL)
	if err != nil {
		t.Fatalf("Vektor-URL: %v", err)
	}
	pfadSecret := strings.TrimPrefix(u.Path, "/api/webhooks/sms/")

	// Helfer-Gegenprobe gegen die aufgezeichnete Signatur.
	if got := sevenSignaturUnabhaengig(v.SigningKey, v.Headers["X-Timestamp"], v.Headers["X-Nonce"],
		http.MethodPost, v.URL, v.Body); got != v.Headers["X-Signature"] {
		t.Fatalf("Signier-Helfer reproduziert die Vektor-Signatur nicht: %s != %s", got, v.Headers["X-Signature"])
	}

	var smsPolls atomic.Int32
	core := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/scheduler/inbound-sms" {
			smsPolls.Add(1)
		}
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok","processed":1,"count":1}`)
	}))
	t.Cleanup(core.Close)

	t.Setenv("GZ_PUBLIC_HOST", v.PublicHost)
	t.Setenv("SEVEN_WEBHOOK_PATH_SECRET", pfadSecret)
	t.Setenv("SEVEN_WEBHOOK_SIGNING_KEY", v.SigningKey)
	r, _ := s2Router(t, s2Optionen{statusToken: s2Token, pythonZiel: core.URL})

	ts := strconv.FormatInt(time.Now().Unix(), 10)
	nonce := fmt.Sprintf("f004-%d", time.Now().UnixNano())
	req := httptest.NewRequest(http.MethodPost, "/api/webhooks/sms/"+pfadSecret, strings.NewReader(v.Body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Timestamp", ts)
	req.Header.Set("X-Nonce", nonce)
	req.Header.Set("X-Signature", sevenSignaturUnabhaengig(v.SigningKey, ts, nonce, http.MethodPost, v.URL, v.Body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req) // ohne Sitzung

	if w.Code != http.StatusOK {
		t.Fatalf("gueltig signierter Webhook durch den echten Router: erwartet 200 (Signatur-URL aus "+
			"cfg.PublicHost), bekam %d: %s", w.Code, w.Body.String())
	}
	deadline := time.Now().Add(3 * time.Second)
	for smsPolls.Load() < 1 && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}
	if smsPolls.Load() < 1 {
		t.Fatal("der Webhook muss premium_sms_poll sofort anstossen (POST /api/scheduler/inbound-sms am Core)")
	}
}
