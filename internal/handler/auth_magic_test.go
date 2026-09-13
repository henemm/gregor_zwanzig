package handler

// TDD RED: Issue #449 — Magic Link / OTP Login per E-Mail
// Spec: docs/specs/modules/issue_449_magic_link.md
//
// Tests für MagicLinkRequestHandler und MagicLinkVerifyHandler.
// Muss FEHLSCHLAGEN bis implementiert (Compile-Fehler: Funktionen existieren nicht).
// Ausführung: cd <repo> && go test ./internal/handler/... -run TestMagicLink -v

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// resetOTPStore löscht alle OTP-Einträge zwischen Tests.
// Delegiert an ResetOTPStoreForTest (aus export_test.go).
func init() {
	// Sicherstellen, dass otpStore beim Paket-Start leer ist.
	ResetOTPStoreForTest()
}

// --- MagicLinkRequestHandler ---

// AC-1: Immer 200, egal ob E-Mail bekannt oder nicht.
func TestMagicLinkRequestHandler_AlwaysReturns200(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	// GIVEN: Leerer Store, SMTP nicht konfiguriert
	s := newTestStore(t)
	cfg := &config.Config{SMTPHost: ""}

	h := MagicLinkRequestHandler(s, cfg)

	// WHEN: Unbekannte E-Mail-Adresse
	body := `{"email":"unknown@example.com"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 200 {"status":"ok"} — keine User-Enumeration
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]string
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("expected JSON response: %v", err)
	}
	if resp["status"] != "ok" {
		t.Errorf("expected status 'ok', got '%s'", resp["status"])
	}
}

// AC-2 (seit #2147): Das Anfordern legt KEIN Konto an; der neue User
// m-{8hex} entsteht erst beim Einlösen des Codes — mit email = mail_to.
func TestMagicLinkRequestHandler_CreatesNewUserForUnknownEmail(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	cfg := &config.Config{SMTPHost: "", SessionSecret: "test-secret"}

	w := magicLinkAnmeldungMitZwischenstand(t, s, cfg, "newuser@example.com", 0)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 on redeem, got %d: %s", w.Code, w.Body.String())
	}

	ids, err := s.ListUserIDs()
	if err != nil {
		t.Fatalf("ListUserIDs: %v", err)
	}
	if len(ids) != 1 {
		t.Fatalf("expected exactly one new user after redeem, got %v", ids)
	}
	userID := ids[0]
	if !strings.HasPrefix(userID, "m-") || len(userID) != 10 { // "m-" + 8 hex chars
		t.Errorf("expected user ID m-{8hex}, got '%s'", userID)
	}
	user, _ := s.LoadUser(userID)
	if user == nil {
		t.Fatal("expected loaded user, got nil")
	}
	if user.Email != "newuser@example.com" || user.MailTo != "newuser@example.com" {
		t.Errorf("expected Email=MailTo='newuser@example.com', got %q / %q", user.Email, user.MailTo)
	}
}

// AC-3 (seit #2147): Bestehender User mit dieser Adresse als Kontaktadresse →
// weder Anfordern noch Einlösen legt ein Duplikat an; Anmeldung ins Bestandskonto.
func TestMagicLinkRequestHandler_UsesExistingUserForKnownEmail(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	existingUser := model.User{
		ID:        "existing-alice",
		Email:     "alice@example.com",
		CreatedAt: time.Now(),
	}
	if err := s.SaveUser(existingUser); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	cfg := &config.Config{SMTPHost: "", SessionSecret: "test-secret"}
	w := magicLinkAnmeldungMitZwischenstand(t, s, cfg, "alice@example.com", 1)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 on redeem, got %d: %s", w.Code, w.Body.String())
	}
	ids, _ := s.ListUserIDs()
	if len(ids) != 1 || ids[0] != "existing-alice" {
		t.Errorf("expected only 'existing-alice' in store, got %v", ids)
	}
	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["id"] != "existing-alice" {
		t.Errorf("expected login into 'existing-alice', got '%s'", resp["id"])
	}
}

// magicLinkAnmeldungMitZwischenstand: Anfordern → Kontenzahl muss noch
// wantBefore sein (kein Anlegen beim Anfordern) → Einlösen.
func magicLinkAnmeldungMitZwischenstand(t *testing.T, s *store.Store, cfg *config.Config, email string, wantBefore int) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link", strings.NewReader(`{"email":"`+email+`"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	MagicLinkRequestHandler(s, cfg).ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 on request, got %d", w.Code)
	}
	if ids, _ := s.ListUserIDs(); len(ids) != wantBefore {
		t.Fatalf("request step must not create an account: expected %d users, got %v", wantBefore, ids)
	}
	return einloesen(s, cfg, email, otpCodeFor(t, email))
}

// AC-10: Wenn SMTPHost leer → 200 + Log-Warnung, kein Panic.
func TestMagicLinkRequestHandler_EmptySMTPLogsWarning(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	// GIVEN: SMTP nicht konfiguriert, Log-Output abfangen
	var logBuf bytes.Buffer
	log.SetOutput(&logBuf)
	defer log.SetOutput(os.Stderr) // RED-Bugfix: nil zerstört den Default-Logger und bricht Folgetests im Package.

	s := newTestStore(t)
	cfg := &config.Config{SMTPHost: ""}
	h := MagicLinkRequestHandler(s, cfg)

	// WHEN: Anfrage mit beliebiger E-Mail
	body := `{"email":"smtp-test@example.com"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 200 und SMTP-Warnung im Log
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200 even without SMTP, got %d", w.Code)
	}
	// Log muss eine SMTP-Warnung enthalten (nicht paniken)
	logOutput := logBuf.String()
	if !strings.Contains(strings.ToLower(logOutput), "smtp") {
		t.Errorf("expected SMTP warning in log, got: %s", logOutput)
	}
}

// Ungültige Body → 400.
func TestMagicLinkRequestHandler_EmptyEmailReturns400(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	cfg := &config.Config{SMTPHost: ""}
	h := MagicLinkRequestHandler(s, cfg)

	body := `{"email":""}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for empty email, got %d: %s", w.Code, w.Body.String())
	}
}

// --- MagicLinkVerifyHandler ---

// AC-4: Valider Code innerhalb TTL → Session-Cookie + 200.
func TestMagicLinkVerifyHandler_ValidCode_SetsSessionCookie(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	// GIVEN: OTP manuell in Store legen (simuliert vorherigen Request-Aufruf)
	s := newTestStore(t)
	user := model.User{ID: "m-aabbccdd", Email: "verify@example.com", CreatedAt: time.Now()}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	// OTP-Eintrag direkt setzen (für Test-Isolation ohne Mail-Versand)
	otpStore.Store("verify@example.com", &otpEntry{
		code:      "123456",
		expiresAt: time.Now().Add(15 * time.Minute),
		attempts:  0,
	})

	cfg := &config.Config{SessionSecret: "test-secret"}
	h := MagicLinkVerifyHandler(s, cfg)

	// WHEN: Korrekter Code
	body := `{"email":"verify@example.com","code":"123456"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 200 mit User-ID
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]string
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("expected JSON: %v", err)
	}
	if resp["id"] != "m-aabbccdd" {
		t.Errorf("expected id 'm-aabbccdd', got '%s'", resp["id"])
	}

	// UND: gz_session Cookie gesetzt
	cookies := w.Result().Cookies()
	var sessionCookie *http.Cookie
	for _, c := range cookies {
		if c.Name == "gz_session" {
			sessionCookie = c
			break
		}
	}
	if sessionCookie == nil {
		t.Fatal("expected gz_session cookie to be set")
	}
	if !sessionCookie.HttpOnly {
		t.Error("gz_session cookie must be HttpOnly")
	}
	// Issue #2129: die Anmeldung gilt unbefristet, bis sie widerrufen wird.
	if sessionCookie.MaxAge != middleware.SessionMaxAgeSeconds {
		t.Errorf("expected MaxAge %d, got %d", middleware.SessionMaxAgeSeconds, sessionCookie.MaxAge)
	}
	if sessionCookie.SameSite != http.SameSiteLaxMode {
		t.Errorf("expected SameSite=Lax, got %v", sessionCookie.SameSite)
	}
}

// AC-5: Falscher Code → 400, Attempt-Counter wird erhöht.
func TestMagicLinkVerifyHandler_WrongCode_Returns400AndIncrementsAttempts(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	entry := &otpEntry{
		code:      "999999",
		expiresAt: time.Now().Add(15 * time.Minute),
		attempts:  0,
	}
	otpStore.Store("wrong@example.com", entry)

	cfg := &config.Config{SessionSecret: "test-secret"}
	h := MagicLinkVerifyHandler(s, cfg)

	// WHEN: Falscher Code
	body := `{"email":"wrong@example.com","code":"000000"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 400 mit Fehlertext
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["error"] != "invalid_or_expired_code" {
		t.Errorf("expected error 'invalid_or_expired_code', got '%s'", resp["error"])
	}

	// UND: Attempt-Counter erhöht
	if entry.attempts != 1 {
		t.Errorf("expected attempts=1, got %d", entry.attempts)
	}
}

// AC-6: Nach 3 Fehlversuchen → max_attempts_exceeded ohne Code-Vergleich.
func TestMagicLinkVerifyHandler_MaxAttempts_Returns400(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	otpStore.Store("maxattempts@example.com", &otpEntry{
		code:      "777777",
		expiresAt: time.Now().Add(15 * time.Minute),
		attempts:  3, // Bereits 3 Fehlversuche
	})

	cfg := &config.Config{SessionSecret: "test-secret"}
	h := MagicLinkVerifyHandler(s, cfg)

	// WHEN: 4. Versuch (auch mit richtigem Code!)
	body := `{"email":"maxattempts@example.com","code":"777777"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 400 max_attempts (auch bei richtigem Code)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["error"] != "max_attempts_exceeded" {
		t.Errorf("expected 'max_attempts_exceeded', got '%s'", resp["error"])
	}
}

// AC-7: Abgelaufener OTP → 400 + Eintrag gelöscht.
func TestMagicLinkVerifyHandler_ExpiredCode_Returns400AndDeletesEntry(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	email := "expired@example.com"
	otpStore.Store(email, &otpEntry{
		code:      "424242",
		expiresAt: time.Now().Add(-1 * time.Minute), // Bereits abgelaufen
		attempts:  0,
	})

	cfg := &config.Config{SessionSecret: "test-secret"}
	h := MagicLinkVerifyHandler(s, cfg)

	// WHEN: Abgelaufener Code
	body := `{"email":"expired@example.com","code":"424242"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 400
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", w.Code)
	}
	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["error"] != "invalid_or_expired_code" {
		t.Errorf("expected 'invalid_or_expired_code', got '%s'", resp["error"])
	}

	// UND: Eintrag aus Store gelöscht
	_, loaded := otpStore.Load(email)
	if loaded {
		t.Error("expired OTP entry should be deleted from store")
	}
}

// Unbekannte E-Mail bei Verify → 400.
func TestMagicLinkVerifyHandler_UnknownEmail_Returns400(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	cfg := &config.Config{SessionSecret: "test-secret"}
	h := MagicLinkVerifyHandler(s, cfg)

	// WHEN: E-Mail ohne OTP-Eintrag
	body := `{"email":"ghost@example.com","code":"111111"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 400
	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", w.Code, w.Body.String())
	}
}

// Valider Code → OTP-Eintrag wird aus Store gelöscht (Einmal-Verwendung).
func TestMagicLinkVerifyHandler_ValidCode_DeletesOTPEntry(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	s := newTestStore(t)
	email := "onetime@example.com"
	user := model.User{ID: "m-onetime1", Email: email, CreatedAt: time.Now()}
	s.SaveUser(user)

	otpStore.Store(email, &otpEntry{
		code:      "654321",
		expiresAt: time.Now().Add(15 * time.Minute),
		attempts:  0,
	})

	cfg := &config.Config{SessionSecret: "test-secret"}
	h := MagicLinkVerifyHandler(s, cfg)

	body := `{"email":"onetime@example.com","code":"654321"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	// OTP-Eintrag darf nach Einlösung nicht mehr im Store sein
	_, exists := otpStore.Load(email)
	if exists {
		t.Error("OTP entry must be deleted from store after successful verify (single-use)")
	}
}
