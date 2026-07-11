package handler

import (
	"bytes"
	"log"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/middleware"
)

// TDD GREEN — Issue #1219 Scheibe 2a-i: Versand des E-Mail-Bestätigungslinks.
// Spec: docs/specs/modules/fix_1219_verify_flow_2a.md (AC-1, AC-2, AC-3, AC-6,
// AC-8, AC-9). Echter Handler + echter Store + echte Platte, keine Mocks.
// Die eigentliche Sende-Guard-Logik (AC-3/AC-4/AC-5) ist bereits am
// mail-Paket selbst abgedeckt (verify_send_test.go) — hier wird der
// Handler-Trigger (Token-Erzeugung + Store-Zustand) geprüft; kein echter
// SMTP-Dial nötig (Spec-Vorgabe).

func seedVerifyUser(t *testing.T, dir, id, json string) {
	t.Helper()
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("seed setup failed: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(json), 0644); err != nil {
		t.Fatalf("seed write failed: %v", err)
	}
}

// AC-1: eine echte mail_to-Änderung erzeugt einen Verifikations-Token unter
// data/users/<userId>/email_verification.json UND löst GENAU EINEN
// Sendeversuch mit to=<neue Adresse> über den Resend-Sonderpfad aus.
//
// Adversary Fix-Loop F001 (#1219, Testabdeckung): die ursprüngliche Fassung
// prüfte nur die Token-Datei, nicht den vom Spec-Text geforderten Nachweis
// "Mailversand hat genau einen Aufruf mit to=neu@x.de erhalten". Der neue
// Test-Seam sendVerificationMailFn (internal/handler/auth.go) macht den
// Resend-Sonderpfad-Aufruf beobachtbar, ohne einen echten SMTP-Dial zu
// benötigen — Test-Doppel wird per defer zurückgesetzt (Issue #1219).
func TestUpdateProfileHandler_MailToChangeCreatesVerificationToken_AC1(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "vera")
	seedVerifyUser(t, dir, "vera", `{"id":"vera","mail_to":"alt@x.de"}`)

	type observedCall struct{ to string }
	calls := make(chan observedCall, 4)
	origSendVerificationMailFn := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- observedCall{to: to}
		return nil
	}
	defer func() { sendVerificationMailFn = origSendVerificationMailFn }()

	// "vera" ist KEIN Test-User (mail.IsTestUser==false) — der reale
	// Resend-Sonderpfad-Zweig wird genommen, dessen Aufruf oben beobachtet
	// wird. cfg.SMTPHost muss nur nicht-leer sein, damit der Handler den
	// Sendezweig überhaupt betritt; der Wert selbst ist irrelevant, da
	// sendVerificationMailFn den echten Dial ersetzt.
	cfg := config.Config{PublicHost: "https://gregor20.henemm.com", SMTPHost: "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x"}
	h := UpdateProfileHandler(s, cfg)
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(`{"mail_to":"neu@x.de"}`))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "vera"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-1: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	tokenPath := filepath.Join(dir, "email_verification.json")
	if _, err := os.Stat(tokenPath); err != nil {
		t.Fatalf("AC-1: email_verification.json muss nach mail_to-Änderung existieren: %v", err)
	}

	select {
	case c := <-calls:
		if c.to != "neu@x.de" {
			t.Errorf("AC-1: erwarteter Versand-Aufruf mit to=neu@x.de, war: %q", c.to)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("AC-1: erwarteter GENAU-EIN Versand-Aufruf blieb innerhalb 2s aus")
	}
	select {
	case extra := <-calls:
		t.Errorf("AC-1: erwartet GENAU EINEN Versand-Aufruf, zusätzlicher Aufruf beobachtet: %+v", extra)
	default:
		// kein zweiter Aufruf — erwartetes Verhalten
	}
}

// AC-2: ein No-Op-Update (identischer mail_to-Wert) erzeugt KEINEN Token.
func TestUpdateProfileHandler_NoOpUpdateCreatesNoVerificationToken_AC2(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "wade")
	seedVerifyUser(t, dir, "wade", `{"id":"wade","mail_to":"wade@x.de"}`)

	cfg := config.Config{PublicHost: "https://gregor20.henemm.com", SMTPHost: "127.0.0.1", SMTPPort: 1, SMTPUser: "u", SMTPPass: "p"}
	h := UpdateProfileHandler(s, cfg)
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(`{"mail_to":"wade@x.de"}`))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "wade"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-2: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	tokenPath := filepath.Join(dir, "email_verification.json")
	if _, err := os.Stat(tokenPath); err == nil {
		t.Errorf("AC-2: No-Op-Update darf keinen email_verification.json erzeugen")
	}
}

// AC-3: eine Änderung auf eine reservierte RFC-2606-Test-Domain löst zwar
// weiterhin eine Token-Erzeugung aus (Guard sitzt im Versandpfad, siehe
// mail.recipientBlockedForVerification-Tests), der Handler darf dabei aber
// nicht abstürzen oder blockieren — synchrone Antwort bleibt 200.
func TestUpdateProfileHandler_ReservedDomainDoesNotCrashHandler_AC3(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "xena")
	seedVerifyUser(t, dir, "xena", `{"id":"xena","mail_to":"alt@x.de"}`)

	cfg := config.Config{PublicHost: "https://gregor20.henemm.com", SMTPHost: "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x"}
	h := UpdateProfileHandler(s, cfg)
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(`{"mail_to":"foo@example.com"}`))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "xena"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-3: expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-6: ein Test-User (IsTestUser==true) mit NUR SMTPHost konfiguriert
// (kein GoogleSMTPHost) darf NICHT über den Resend-Sonderpfad versendet
// werden — der Handler muss synchron "Google SMTP not configured" loggen und
// abbrechen, statt auf cfg.SMTPHost auszuweichen.
func TestUpdateProfileHandler_TestUserUsesGoogleSMTPNotResend_AC6(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "test-yara")
	seedVerifyUser(t, dir, "test-yara", `{"id":"test-yara","mail_to":"alt@x.de"}`)

	var logBuf bytes.Buffer
	log.SetOutput(&logBuf)
	defer log.SetOutput(os.Stderr)

	cfg := config.Config{
		PublicHost: "https://gregor20.henemm.com",
		SMTPHost:   "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x",
		// GoogleSMTPHost bewusst leer
	}
	h := UpdateProfileHandler(s, cfg)
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(`{"mail_to":"neu-yara@x.de"}`))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "test-yara"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-6: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(logBuf.String(), "Google SMTP not configured") {
		t.Errorf("AC-6: Test-User ohne GoogleSMTPHost muss 'Google SMTP not configured' loggen "+
			"(Beweis, dass NICHT auf den Resend-Sonderpfad ausgewichen wird), Log: %s", logBuf.String())
	}
}

// AC-8: zwei verschiedene Nutzer (A/B) ändern beide ihre Adresse — jeder
// Token liegt ausschließlich im eigenen Nutzerverzeichnis.
func TestUpdateProfileHandler_TokenIsolatedPerUser_AC8(t *testing.T) {
	s := newTestStore(t)
	dirA := filepath.Join(s.DataDir, "users", "alice-a")
	dirB := filepath.Join(s.DataDir, "users", "bob-b")
	seedVerifyUser(t, dirA, "alice-a", `{"id":"alice-a","mail_to":"alice-old@x.de"}`)
	seedVerifyUser(t, dirB, "bob-b", `{"id":"bob-b","mail_to":"bob-old@x.de"}`)

	cfg := config.Config{PublicHost: "https://gregor20.henemm.com", SMTPHost: "127.0.0.1", SMTPPort: 1, SMTPUser: "u", SMTPPass: "p"}
	h := UpdateProfileHandler(s, cfg)

	for _, tc := range []struct{ userId, body string }{
		{"alice-a", `{"mail_to":"alice-new@x.de"}`},
		{"bob-b", `{"mail_to":"bob-new@x.de"}`},
	} {
		req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(tc.body))
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), tc.userId))
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		if w.Code != 200 {
			t.Fatalf("AC-8: expected 200 for %s, got %d", tc.userId, w.Code)
		}
	}

	if _, err := os.Stat(filepath.Join(dirA, "email_verification.json")); err != nil {
		t.Errorf("AC-8: Token für alice-a muss unter deren eigenem Verzeichnis liegen: %v", err)
	}
	if _, err := os.Stat(filepath.Join(dirB, "email_verification.json")); err != nil {
		t.Errorf("AC-8: Token für bob-b muss unter deren eigenem Verzeichnis liegen: %v", err)
	}
	// Cross-Check: kein Token im jeweils anderen Verzeichnis fehlplatziert (das
	// wäre strukturell unmöglich mit UserDir(userId), aber die Assertion
	// dokumentiert die Invariante explizit).
	dataA, _ := os.ReadFile(filepath.Join(dirA, "email_verification.json"))
	dataB, _ := os.ReadFile(filepath.Join(dirB, "email_verification.json"))
	if string(dataA) == string(dataB) {
		t.Errorf("AC-8: Tokens von alice-a und bob-b dürfen nicht identisch sein")
	}
}

// AC-9: ExpiresAt liegt bei Erzeugung + 24 Stunden (Toleranz ±1 Minute),
// NICHT bei den 30 Minuten des Passwort-Reset-Tokens.
func TestUpdateProfileHandler_TokenExpiresIn24Hours_AC9(t *testing.T) {
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "zack")
	seedVerifyUser(t, dir, "zack", `{"id":"zack","mail_to":"alt@x.de"}`)

	cfg := config.Config{PublicHost: "https://gregor20.henemm.com", SMTPHost: "127.0.0.1", SMTPPort: 1, SMTPUser: "u", SMTPPass: "p"}
	h := UpdateProfileHandler(s, cfg)
	before := time.Now()
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(`{"mail_to":"zack-neu@x.de"}`))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "zack"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != 200 {
		t.Fatalf("AC-9: expected 200, got %d", w.Code)
	}

	token, err := s.LoadVerificationToken("zack")
	if err != nil || token == nil {
		t.Fatalf("AC-9: LoadVerificationToken failed: %v", err)
	}
	expectedMin := before.Add(24*time.Hour - time.Minute)
	expectedMax := before.Add(24*time.Hour + time.Minute)
	if token.ExpiresAt.Before(expectedMin) || token.ExpiresAt.After(expectedMax) {
		t.Errorf("AC-9: ExpiresAt %v liegt nicht innerhalb 24h ±1min ab %v", token.ExpiresAt, before)
	}
}
