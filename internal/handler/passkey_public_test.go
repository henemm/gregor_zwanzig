package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED — Issue #466 Passkey V2: Public passwordless registration.
// Mock-free: reuses testAuthenticator (ECDSA-P-256, "none" attestation) from passkey_test.go.
// All tests MUST FAIL while the handlers return 501 (stub phase).

// -----------------------------------------------------------------------------
// AC-1: Begin success — valid username + email, user does not exist
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicBegin_Success(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	body := []byte(`{"username":"newuser","email":"new@example.com"}`)
	req := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	h := PasskeyRegisterPublicBeginHandler(s, wa, cs)
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-1: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("AC-1: cannot decode response: %v", err)
	}
	if resp.PublicKey.Challenge == "" {
		t.Errorf("AC-1: expected non-empty challenge in publicKey")
	}

	// No user must have been persisted at this point.
	if s.UserExists("newuser") {
		t.Errorf("AC-1: user must NOT be persisted after Begin")
	}
}

// -----------------------------------------------------------------------------
// AC-2: Begin fails when username already exists → 409
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicBegin_UserExists(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	// Seed an existing user.
	if err := s.SaveUser(model.User{ID: "alice", PasswordHash: "hash", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("seed user: %v", err)
	}

	body := []byte(`{"username":"alice","email":"alice@example.com"}`)
	req := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(body))
	w := httptest.NewRecorder()

	h := PasskeyRegisterPublicBeginHandler(s, wa, cs)
	h.ServeHTTP(w, req)

	if w.Code != http.StatusConflict {
		t.Fatalf("AC-2: expected 409, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "user_already_exists") {
		t.Errorf("AC-2: expected error=user_already_exists in body, got: %s", w.Body.String())
	}
}

// -----------------------------------------------------------------------------
// AC-3: Begin fails for invalid username (too short / too long) → 400
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicBegin_InvalidUsername(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	h := PasskeyRegisterPublicBeginHandler(s, wa, cs)

	cases := []struct {
		name     string
		username string
	}{
		{"too_short", "ab"},
		{"too_long", strings.Repeat("x", 51)},
		{"empty", ""},
		{"invalid_chars", "alice boss"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			body, _ := json.Marshal(map[string]string{"username": tc.username, "email": "ok@example.com"})
			req := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(body))
			w := httptest.NewRecorder()
			h.ServeHTTP(w, req)
			if w.Code != http.StatusBadRequest {
				t.Fatalf("AC-3 [%s]: expected 400, got %d: %s", tc.name, w.Code, w.Body.String())
			}
			if !strings.Contains(w.Body.String(), "validation_failed") {
				t.Errorf("AC-3 [%s]: expected validation_failed in body", tc.name)
			}
		})
	}
}

// -----------------------------------------------------------------------------
// AC-4: Begin fails for invalid email (no @) → 400
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicBegin_InvalidEmail(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	cases := []struct {
		name  string
		email string
	}{
		{"no_at", "noemail"},
		{"empty", ""},
	}

	h := PasskeyRegisterPublicBeginHandler(s, wa, cs)
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			body, _ := json.Marshal(map[string]string{"username": "validuser", "email": tc.email})
			req := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(body))
			w := httptest.NewRecorder()
			h.ServeHTTP(w, req)
			if w.Code != http.StatusBadRequest {
				t.Fatalf("AC-4 [%s]: expected 400, got %d: %s", tc.name, w.Code, w.Body.String())
			}
			if !strings.Contains(w.Body.String(), "validation_failed") {
				t.Errorf("AC-4 [%s]: expected validation_failed in body", tc.name)
			}
		})
	}
}

// -----------------------------------------------------------------------------
// AC-5: Full roundtrip — valid attestation → user created without PasswordHash,
//        gz_session cookie set, HTTP 201
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicRoundtrip_Success(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	// Step 1: Begin
	beginBody := []byte(`{"username":"passwordless","email":"pw@example.com"}`)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(beginBody))
	beginW := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW, beginReq)

	if beginW.Code != http.StatusOK {
		t.Fatalf("AC-5 begin: expected 200, got %d: %s", beginW.Code, beginW.Body.String())
	}

	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("AC-5 begin: cannot decode response: %v", err)
	}

	// Step 2: Authenticator creates attestation for the challenge
	auth := newTestAuthenticator(t, rpID, origin)
	finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)

	// Step 3: Finish
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
	finishW := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret).ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusCreated {
		t.Fatalf("AC-5 finish: expected 201, got %d: %s", finishW.Code, finishW.Body.String())
	}

	// User must exist without PasswordHash.
	user, err := s.LoadUser("passwordless")
	if err != nil || user == nil {
		t.Fatalf("AC-5: user not found after registration: %v", err)
	}
	if user.PasswordHash != "" {
		t.Errorf("AC-5: PasswordHash must be empty for passwordless user, got %q", user.PasswordHash)
	}
	if user.Email != "pw@example.com" {
		t.Errorf("AC-5: expected email pw@example.com, got %q", user.Email)
	}
	if len(user.PasskeyCredentials) != 1 {
		t.Fatalf("AC-5: expected 1 PasskeyCredential, got %d", len(user.PasskeyCredentials))
	}

	// gz_session cookie must be set.
	var sess *http.Cookie
	for _, c := range finishW.Result().Cookies() {
		if c.Name == "gz_session" {
			sess = c
			break
		}
	}
	if sess == nil {
		t.Fatalf("AC-5: expected gz_session cookie, none found")
	}
	if !sess.HttpOnly {
		t.Errorf("AC-5: gz_session must be HttpOnly")
	}
	if sess.SameSite != http.SameSiteLaxMode {
		t.Errorf("AC-5: expected SameSite=Lax, got %v", sess.SameSite)
	}
	if sess.MaxAge != 86400 {
		t.Errorf("AC-5: expected MaxAge=86400, got %d", sess.MaxAge)
	}
	if !strings.HasPrefix(sess.Value, "passwordless.") {
		t.Errorf("AC-5: session value should start with 'passwordless.', got %q", sess.Value)
	}
}

// -----------------------------------------------------------------------------
// AC-6: Finish with expired/unknown challenge → 400
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicFinish_ChallengeExpired(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	// Craft a well-formed attestation but without a matching challenge in the store.
	auth := newTestAuthenticator(t, rpID, origin)
	body := auth.makeAttestationResponse(t, "dGhpcyBpcyBhIGZha2UgY2hhbGxlbmdl") // arbitrary b64url

	req := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(body))
	w := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret).ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("AC-6: expected 400, got %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "challenge_expired_or_missing") {
		t.Errorf("AC-6: expected challenge_expired_or_missing in body, got: %s", w.Body.String())
	}
	// No user must have been created.
	if ids, _ := s.ListUserIDs(); len(ids) > 0 {
		t.Errorf("AC-6: no user should be created, found: %v", ids)
	}
}

// -----------------------------------------------------------------------------
// AC-7: Race — username claimed between Begin and Finish → 409
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicFinish_UsernameRace(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	// Step 1: Begin for "raced"
	beginBody := []byte(`{"username":"raced","email":"r@example.com"}`)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(beginBody))
	beginW := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW, beginReq)
	if beginW.Code != http.StatusOK {
		t.Fatalf("AC-7 begin: expected 200, got %d", beginW.Code)
	}

	var beginResp struct {
		PublicKey struct{ Challenge string `json:"challenge"` } `json:"publicKey"`
	}
	json.Unmarshal(beginW.Body.Bytes(), &beginResp)

	// Step 2: Someone else claims the username before Finish.
	if err := s.SaveUser(model.User{ID: "raced", PasswordHash: "claimed", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("AC-7: could not claim username: %v", err)
	}

	// Step 3: Finish — must reject with 409
	auth := newTestAuthenticator(t, rpID, origin)
	finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
	finishW := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret).ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusConflict {
		t.Fatalf("AC-7: expected 409, got %d: %s", finishW.Code, finishW.Body.String())
	}
	if !strings.Contains(finishW.Body.String(), "user_already_exists") {
		t.Errorf("AC-7: expected user_already_exists in body, got: %s", finishW.Body.String())
	}
}

// -----------------------------------------------------------------------------
// F004: Cookie Secure-Flag — false on plain HTTP, true behind HTTPS proxy
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicFinish_CookieSecureFlag(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"

	t.Run("http_not_secure", func(t *testing.T) {
		s := newTestStore(t)
		wa := newTestWebAuthn(t, rpID, origin)
		cs := NewChallengeStore()
		secret := "test-secret-32-chars-long-enough"

		// Begin
		beginBody := []byte(`{"username":"sectest","email":"sec@example.com"}`)
		beginReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(beginBody))
		beginW := httptest.NewRecorder()
		PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW, beginReq)
		if beginW.Code != http.StatusOK {
			t.Fatalf("begin: got %d", beginW.Code)
		}
		var beginResp struct {
			PublicKey struct {
				Challenge string `json:"challenge"`
			} `json:"publicKey"`
		}
		json.Unmarshal(beginW.Body.Bytes(), &beginResp)

		auth := newTestAuthenticator(t, rpID, origin)
		finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)
		finishReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
		// No X-Forwarded-Proto header → Secure must be false
		finishW := httptest.NewRecorder()
		PasskeyRegisterPublicFinishHandler(s, wa, cs, secret).ServeHTTP(finishW, finishReq)
		if finishW.Code != http.StatusCreated {
			t.Fatalf("finish: got %d: %s", finishW.Code, finishW.Body.String())
		}
		for _, c := range finishW.Result().Cookies() {
			if c.Name == "gz_session" && c.Secure {
				t.Errorf("Secure must be false on plain HTTP, got true")
			}
		}
	})

	t.Run("https_secure", func(t *testing.T) {
		s := newTestStore(t)
		wa := newTestWebAuthn(t, rpID, origin)
		cs := NewChallengeStore()
		secret := "test-secret-32-chars-long-enough"

		// Begin
		beginBody := []byte(`{"username":"sectest2","email":"sec2@example.com"}`)
		beginReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(beginBody))
		beginW := httptest.NewRecorder()
		PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW, beginReq)
		if beginW.Code != http.StatusOK {
			t.Fatalf("begin: got %d", beginW.Code)
		}
		var beginResp struct {
			PublicKey struct {
				Challenge string `json:"challenge"`
			} `json:"publicKey"`
		}
		json.Unmarshal(beginW.Body.Bytes(), &beginResp)

		auth := newTestAuthenticator(t, rpID, origin)
		finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)
		finishReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
		finishReq.Header.Set("X-Forwarded-Proto", "https") // → Secure must be true
		finishW := httptest.NewRecorder()
		PasskeyRegisterPublicFinishHandler(s, wa, cs, secret).ServeHTTP(finishW, finishReq)
		if finishW.Code != http.StatusCreated {
			t.Fatalf("finish: got %d: %s", finishW.Code, finishW.Body.String())
		}
		var found bool
		for _, c := range finishW.Result().Cookies() {
			if c.Name == "gz_session" {
				found = true
				if !c.Secure {
					t.Errorf("Secure must be true on HTTPS, got false")
				}
			}
		}
		if !found {
			t.Errorf("gz_session cookie not found")
		}
	})
}
