package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
)

// testRegisterCfg liefert eine Config, deren SMTPHost gesetzt ist, damit der
// (nicht-Test-User-)Dispatch-Zweig in RegisterHandler betreten wird. Der
// tatsächliche SMTP-Dial wird in Dispatch-beobachtenden Tests über
// sendVerificationMailFn ersetzt (kein echter Netz-Zugriff).
func testRegisterCfg() config.Config {
	return config.Config{
		PublicHost: "https://gregor20.henemm.com",
		SMTPHost:   "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x",
	}
}

// TDD RED: Tests for auth handlers — must FAIL until implemented.

func TestRegisterHandlerSuccess(t *testing.T) {
	// GIVEN: Empty store
	s := newTestStore(t)

	// Dispatch-Seam stummschalten, damit kein echter SMTP-Dial in der
	// Goroutine passiert — dieser Test prüft nur die 201-Antwort.
	// Der Stub signalisiert über einen gepufferten Channel, damit der Test
	// auf den asynchronen Fire-and-Forget-Dispatch warten kann, BEVOR der
	// defer den Stub zurücksetzt (sonst Data-Race gegen die Goroutine).
	calls := make(chan struct{}, 1)
	origSend := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- struct{}{}
		return nil
	}
	defer func() { sendVerificationMailFn = origSend }()

	h := RegisterHandler(s, bcrypt.MinCost, testRegisterCfg())

	// WHEN: Registering a new user
	body := `{"username":"alice","password":"geheim123","email":"alice@beispiel.de"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 201 with user ID
	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["id"] != "alice" {
		t.Errorf("expected id 'alice', got '%s'", resp["id"])
	}

	// AND: user.json exists
	userFile := filepath.Join(s.DataDir, "users", "alice", "user.json")
	if _, err := os.Stat(userFile); os.IsNotExist(err) {
		t.Error("user.json should be created")
	}

	// AND: auf den asynchronen Dispatch warten, bevor der defer den Stub
	// zurücksetzt — verhindert das Rennen gegen die Dispatch-Goroutine.
	select {
	case <-calls:
	case <-time.After(2 * time.Second):
		t.Fatal("expected dispatch goroutine to invoke sendVerificationMailFn within 2s")
	}
}

func TestRegisterHandlerDuplicateUser(t *testing.T) {
	// GIVEN: User already exists
	s := newTestStore(t)
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{"id":"alice"}`), 0644)

	h := RegisterHandler(s, bcrypt.MinCost, testRegisterCfg())

	// WHEN: Registering same username
	body := `{"username":"alice","password":"geheim123","email":"alice@beispiel.de"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 409 Conflict
	if w.Code != 409 {
		t.Fatalf("expected 409, got %d: %s", w.Code, w.Body.String())
	}
}

func TestRegisterHandlerShortUsername(t *testing.T) {
	s := newTestStore(t)
	h := RegisterHandler(s, bcrypt.MinCost, testRegisterCfg())

	body := `{"username":"ab","password":"geheim123","email":"ab@beispiel.de"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for short username, got %d", w.Code)
	}
}

func TestRegisterHandlerShortPassword(t *testing.T) {
	s := newTestStore(t)
	h := RegisterHandler(s, bcrypt.MinCost, testRegisterCfg())

	body := `{"username":"alice","password":"short","email":"alice@beispiel.de"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for short password, got %d", w.Code)
	}
}

// -----------------------------------------------------------------------------
// Issue #1226 — E-Mail-Pflichtfeld + Verifikations-Dispatch bei Registrierung
// -----------------------------------------------------------------------------

// AC-1: Request ohne email-Feld → 400 "validation failed", kein Konto angelegt.
func TestRegisterHandler_MissingEmail_AC1(t *testing.T) {
	s := newTestStore(t)
	h := RegisterHandler(s, bcrypt.MinCost, testRegisterCfg())

	body := `{"username":"alice","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("AC-1: expected 400 for missing email, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["error"] != "validation failed" {
		t.Errorf("AC-1: expected error 'validation failed', got %q", resp["error"])
	}
	if s.UserExists("alice") {
		t.Errorf("AC-1: no account must be created when email is missing")
	}
}

// AC-2: Request mit email ohne "@" → 400 mit eigenem Fehlercode "invalid_email",
// kein Konto angelegt.
func TestRegisterHandler_InvalidEmail_AC2(t *testing.T) {
	s := newTestStore(t)
	h := RegisterHandler(s, bcrypt.MinCost, testRegisterCfg())

	body := `{"username":"alice","password":"geheim123","email":"nicht-valide"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("AC-2: expected 400 for invalid email, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["error"] != "invalid_email" {
		t.Errorf("AC-2: expected error 'invalid_email' (getrennt von 'validation failed'), got %q", resp["error"])
	}
	if s.UserExists("alice") {
		t.Errorf("AC-2: no account must be created when email is invalid")
	}
}

// AC-3: gültige email → Konto mit gesetzter Email angelegt UND genau ein
// Verifikations-Dispatch mit der registrierten Adresse.
// Hinweis (Abweichung vom Test-Vorschlag): RegisterHandler setzt — wie schon vor
// #1226 — KEIN Session-Cookie (unverändertes Bestandsverhalten, in den
// Implementation Details nicht vorgesehen); geprüft wird 201 + Konto + Dispatch.
func TestRegisterHandler_ValidEmailTriggersDispatch_AC3(t *testing.T) {
	s := newTestStore(t)

	type observedCall struct{ to string }
	calls := make(chan observedCall, 4)
	origSend := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- observedCall{to: to}
		return nil
	}
	defer func() { sendVerificationMailFn = origSend }()

	h := RegisterHandler(s, bcrypt.MinCost, testRegisterCfg())
	body := `{"username":"alice","password":"geheim123","email":"user@beispiel.de"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("AC-3: expected 201, got %d: %s", w.Code, w.Body.String())
	}
	user, err := s.LoadUser("alice")
	if err != nil || user == nil {
		t.Fatalf("AC-3: account must exist after registration: %v", err)
	}
	if user.Email != "user@beispiel.de" {
		t.Errorf("AC-3: expected user.Email 'user@beispiel.de', got %q", user.Email)
	}

	select {
	case c := <-calls:
		if c.to != "user@beispiel.de" {
			t.Errorf("AC-3: expected dispatch to 'user@beispiel.de', got %q", c.to)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("AC-3: expected exactly one dispatch call within 2s, none observed")
	}
	select {
	case extra := <-calls:
		t.Errorf("AC-3: expected exactly ONE dispatch call, extra observed: %+v", extra)
	default:
	}
}

// AC-7: reservierte Test-Domain foo@example.com → Konto wird trotzdem angelegt
// UND der Dispatch läuft normal (kein Domain-Guard bei der Registrierung).
func TestRegisterHandler_ReservedTestDomainStillDispatches_AC7(t *testing.T) {
	s := newTestStore(t)

	type observedCall struct{ to string }
	calls := make(chan observedCall, 4)
	origSend := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- observedCall{to: to}
		return nil
	}
	defer func() { sendVerificationMailFn = origSend }()

	h := RegisterHandler(s, bcrypt.MinCost, testRegisterCfg())
	body := `{"username":"charlie","password":"geheim123","email":"foo@example.com"}`
	req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("AC-7: expected 201, got %d: %s", w.Code, w.Body.String())
	}
	if !s.UserExists("charlie") {
		t.Errorf("AC-7: account must be created even for reserved test domain")
	}

	select {
	case c := <-calls:
		if c.to != "foo@example.com" {
			t.Errorf("AC-7: expected dispatch to 'foo@example.com' (no domain guard), got %q", c.to)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("AC-7: expected exactly one dispatch call within 2s, none observed")
	}
}

// AC-8: zwei Nutzer registrieren sich unabhängig → jeder hat sein eigenes,
// isoliertes Verifikations-Token und der Dispatch enthält ausschließlich die
// eigene Adresse (keine Cross-User-Vermischung).
func TestRegisterHandler_TwoUsersNoCrossContamination_AC8(t *testing.T) {
	s := newTestStore(t)

	type observedCall struct{ to string }
	calls := make(chan observedCall, 8)
	origSend := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- observedCall{to: to}
		return nil
	}
	defer func() { sendVerificationMailFn = origSend }()

	h := RegisterHandler(s, bcrypt.MinCost, testRegisterCfg())

	cases := []struct{ username, email string }{
		{"anna", "anna@beispiel.de"},
		{"bernd", "bernd@beispiel.de"},
	}
	for _, tc := range cases {
		body := `{"username":"` + tc.username + `","password":"geheim123","email":"` + tc.email + `"}`
		req := httptest.NewRequest("POST", "/api/auth/register", strings.NewReader(body))
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		if w.Code != 201 {
			t.Fatalf("AC-8: expected 201 for %s, got %d: %s", tc.username, w.Code, w.Body.String())
		}
	}

	// Jeder Nutzer hat sein eigenes Token unter seinem userId.
	tokAnna, err := s.LoadVerificationToken("anna")
	if err != nil || tokAnna == nil {
		t.Fatalf("AC-8: anna must have her own verification token: %v", err)
	}
	tokBernd, err := s.LoadVerificationToken("bernd")
	if err != nil || tokBernd == nil {
		t.Fatalf("AC-8: bernd must have his own verification token: %v", err)
	}
	if tokAnna.TokenHash == tokBernd.TokenHash {
		t.Errorf("AC-8: tokens of anna and bernd must not be identical (cross-user leak)")
	}

	// Genau zwei Dispatch-Aufrufe, jeder mit der jeweils eigenen Adresse — keiner
	// mit der Adresse des anderen Nutzers.
	seen := map[string]bool{}
	for i := 0; i < 2; i++ {
		select {
		case c := <-calls:
			seen[c.to] = true
		case <-time.After(2 * time.Second):
			t.Fatalf("AC-8: expected two dispatch calls, only saw %d", i)
		}
	}
	if !seen["anna@beispiel.de"] || !seen["bernd@beispiel.de"] {
		t.Errorf("AC-8: each user's own address must be dispatched, saw: %v", seen)
	}
	if len(seen) != 2 {
		t.Errorf("AC-8: expected exactly two distinct recipients, got: %v", seen)
	}
}

func TestLoginHandlerSuccess(t *testing.T) {
	// GIVEN: A registered user with bcrypt hash
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"alice","password_hash":"`+string(hash)+`","created_at":"2026-04-15T00:00:00Z"}`), 0644)

	secret := "test-secret-32-chars-long-enough"
	h := LoginHandler(s, secret)

	// WHEN: Logging in with correct credentials
	body := `{"username":"alice","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 200 with session cookie
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Check session cookie is set
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
		t.Error("cookie should be HttpOnly")
	}
	if sessionCookie.MaxAge != 86400 {
		t.Errorf("expected MaxAge 86400, got %d", sessionCookie.MaxAge)
	}

	// Check cookie starts with username
	if !strings.HasPrefix(sessionCookie.Value, "alice.") {
		t.Errorf("session cookie should start with 'alice.', got '%s'", sessionCookie.Value[:20])
	}
}

func TestLoginHandlerWrongPassword(t *testing.T) {
	// GIVEN: A registered user
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := filepath.Join(s.DataDir, "users", "alice")
	os.MkdirAll(dir, 0755)
	os.WriteFile(filepath.Join(dir, "user.json"),
		[]byte(`{"id":"alice","password_hash":"`+string(hash)+`"}`), 0644)

	h := LoginHandler(s, "secret")

	// WHEN: Wrong password
	body := `{"username":"alice","password":"falsch!!!"}`
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 401
	if w.Code != 401 {
		t.Fatalf("expected 401, got %d", w.Code)
	}
}

func TestLoginHandlerUserNotFound(t *testing.T) {
	s := newTestStore(t)
	h := LoginHandler(s, "secret")

	body := `{"username":"nobody","password":"geheim123"}`
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 401 {
		t.Fatalf("expected 401 for unknown user, got %d", w.Code)
	}
}

func TestLoginHandlerMalformedJSON(t *testing.T) {
	s := newTestStore(t)
	h := LoginHandler(s, "secret")

	body := `{not valid json`
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for bad JSON, got %d", w.Code)
	}
}
