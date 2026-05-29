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
	"github.com/henemm/gregor-api/internal/model"
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

// AC-2: Neuer User m-{8hex} wird angelegt, wenn E-Mail unbekannt.
func TestMagicLinkRequestHandler_CreatesNewUserForUnknownEmail(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	// GIVEN: Leerer Store
	s := newTestStore(t)
	cfg := &config.Config{SMTPHost: ""}

	h := MagicLinkRequestHandler(s, cfg)

	// WHEN: Neue E-Mail-Adresse
	body := `{"email":"newuser@example.com"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: Neuer User existiert im Store
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	ids, err := s.ListUserIDs()
	if err != nil {
		t.Fatalf("ListUserIDs: %v", err)
	}
	if len(ids) == 0 {
		t.Fatal("expected a new user to be created in the store")
	}

	// ID muss m-{8hex} Format haben
	userID := ids[0]
	if !strings.HasPrefix(userID, "m-") {
		t.Errorf("expected user ID with prefix 'm-', got '%s'", userID)
	}
	if len(userID) != 10 { // "m-" + 8 hex chars
		t.Errorf("expected ID length 10, got %d: '%s'", len(userID), userID)
	}

	// User hat E-Mail gesetzt
	user, _ := s.LoadUser(userID)
	if user == nil {
		t.Fatal("expected loaded user, got nil")
	}
	if user.Email != "newuser@example.com" {
		t.Errorf("expected Email 'newuser@example.com', got '%s'", user.Email)
	}
}

// AC-3: Bestehender User mit E-Mail → kein Duplikat.
func TestMagicLinkRequestHandler_UsesExistingUserForKnownEmail(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)

	// GIVEN: Bestehender User mit E-Mail-Feld
	s := newTestStore(t)
	existingUser := model.User{
		ID:        "existing-alice",
		Email:     "alice@example.com",
		CreatedAt: time.Now(),
	}
	if err := s.SaveUser(existingUser); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	cfg := &config.Config{SMTPHost: ""}
	h := MagicLinkRequestHandler(s, cfg)

	// WHEN: Bekannte E-Mail
	body := `{"email":"alice@example.com"}`
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: Kein zweiter User angelegt — nur 1 User im Store
	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	ids, _ := s.ListUserIDs()
	if len(ids) != 1 {
		t.Errorf("expected exactly 1 user in store, got %d", len(ids))
	}
	if ids[0] != "existing-alice" {
		t.Errorf("expected existing user ID 'existing-alice', got '%s'", ids[0])
	}
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
		userID:    "m-aabbccdd",
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
	if sessionCookie.MaxAge != 86400 {
		t.Errorf("expected MaxAge 86400, got %d", sessionCookie.MaxAge)
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
		userID:    "m-test0001",
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
		userID:    "m-test0002",
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
		userID:    "m-test0003",
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
		userID:    "m-onetime1",
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
