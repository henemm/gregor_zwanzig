package handler

// #2157 AC-e: Magic-Link-Protokollzeilen nennen die Adresse nur maskiert.
// Spec: docs/specs/modules/pii_log_masking.md (Fundstelle 7)
//
// Log-Mitschnitt über log.SetOutput (Muster auth_password_reset_mail_test.go);
// der Versand-Fehlerfall läuft über die bestehende Naht sendVerificationMailFn
// (Muster auth_test.go) — ersetzt wird nur der Netzrand.

import (
	"bytes"
	"errors"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
)

const (
	piiTestAdresse     = "finder-2157@beispiel.de"
	piiTestMaskiert    = "***@beispiel.de"
	piiTestLokalTeil   = "finder-2157"
	piiMitschnittFrist = 2 * time.Second
)

// sichererMitschnitt schützt den Puffer gegen die Dispatch-Goroutine.
type sichererMitschnitt struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (m *sichererMitschnitt) Write(p []byte) (int, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.buf.Write(p)
}

func (m *sichererMitschnitt) String() string {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.buf.String()
}

func logMitschneiden(t *testing.T) *sichererMitschnitt {
	t.Helper()
	m := &sichererMitschnitt{}
	log.SetOutput(m)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	return m
}

func magicLinkAnfordern(t *testing.T, cfg *config.Config) {
	t.Helper()
	s := newTestStore(t)
	h := MagicLinkRequestHandler(s, cfg)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link",
		strings.NewReader(`{"email":"`+piiTestAdresse+`"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

func warteAufZeile(m *sichererMitschnitt, merkmal string) string {
	frist := time.Now().Add(piiMitschnittFrist)
	for time.Now().Before(frist) {
		for _, zeile := range strings.Split(m.String(), "\n") {
			if strings.Contains(zeile, merkmal) {
				return zeile
			}
		}
		time.Sleep(10 * time.Millisecond)
	}
	return ""
}

func pruefeMaskierteZeile(t *testing.T, zeile, merkmal string) {
	t.Helper()
	if zeile == "" {
		t.Fatalf("AC-e: Protokollzeile %q erschien nicht binnen %v", merkmal, piiMitschnittFrist)
	}
	if strings.Contains(strings.ToLower(zeile), piiTestLokalTeil) {
		t.Errorf("#2157 AC-e: Magic-Link-Log nennt die Adresse im Klartext: %q", zeile)
	}
	if !strings.Contains(zeile, piiTestMaskiert) {
		t.Errorf("#2157 AC-e: maskierte Form %q fehlt: %q", piiTestMaskiert, zeile)
	}
}

func TestMagicLinkLogOhneSMTPNenntAdresseNurMaskiert_2157(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	m := logMitschneiden(t)

	magicLinkAnfordern(t, &config.Config{SMTPHost: ""})

	const merkmal = "magic-link: SMTP not configured"
	pruefeMaskierteZeile(t, warteAufZeile(m, merkmal), merkmal)
}

func TestMagicLinkLogBeiVersandfehlerNenntAdresseNurMaskiert_2157(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	orig := sendVerificationMailFn
	sendVerificationMailFn = func(c mail.MailConfig, to string, msg mail.Mail) error {
		return errors.New("netzrand im test absichtlich gescheitert")
	}
	t.Cleanup(func() { sendVerificationMailFn = orig })
	m := logMitschneiden(t)

	magicLinkAnfordern(t, &config.Config{
		SMTPHost: "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x",
	})

	const merkmal = "magic-link: mail send failed"
	pruefeMaskierteZeile(t, warteAufZeile(m, merkmal), merkmal)
}
