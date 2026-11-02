package handler

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler/passkeytest"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
)

// passkeyBeginKontoID liest die im Begin-Schritt erzeugte Konto-ID aus der
// Antwort (Issue #2194, AC-13): publicKey.user.id ist der base64url-kodierte
// WebAuthn-userHandle == user.ID.
func passkeyBeginKontoID(t *testing.T, beginAntwort []byte) string {
	t.Helper()
	var resp struct {
		PublicKey struct {
			User struct {
				ID string `json:"id"`
			} `json:"user"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginAntwort, &resp); err != nil {
		t.Fatalf("Begin-Antwort kein JSON: %v", err)
	}
	roh, err := base64.RawURLEncoding.DecodeString(strings.TrimRight(resp.PublicKey.User.ID, "="))
	if err != nil {
		t.Fatalf("publicKey.user.id %q nicht base64url: %v", resp.PublicKey.User.ID, err)
	}
	id := string(roh)
	if !opakeID2194.MatchString(id) {
		t.Fatalf("Begin-Konto-ID %q passt nicht zu ^u-[0-9a-f]{8}$", id)
	}
	return id
}

// TDD RED — Issue #466 Passkey V2: Public passwordless registration.
// Mock-free: reuses testAuthenticator (ECDSA-P-256, "none" attestation) from passkey_test.go.
// All tests MUST FAIL while the handlers return 501 (stub phase).

// -----------------------------------------------------------------------------
// AC-1: Begin success — valid username + email, user does not exist
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicBegin_Success(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
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

	// No user must have been persisted at this point — weder unter dem
	// Body-username noch unter der in Begin erzeugten ID (Issue #2194).
	if s.UserExists("newuser") {
		t.Errorf("AC-1: user must NOT be persisted after Begin")
	}
	if id := passkeyBeginKontoID(t, w.Body.Bytes()); s.UserExists(id) {
		t.Errorf("AC-1: generated id %q must NOT be persisted after Begin", id)
	}
}

// -----------------------------------------------------------------------------
// AC-2 (umgestellt auf Issue #2194 AC-13): ein vergebener Body-username ist
// kein Konflikt mehr — er wird ignoriert. Begin liefert 200 mit generierter
// ID, das Bestandskonto bleibt byte-genau unberuehrt.
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicBegin_UserExists(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	// Seed an existing user.
	if err := s.SaveUser(model.User{ID: "alice", PasswordHash: "hash", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("seed user: %v", err)
	}
	vorher := rohesKonto(t, s, "alice")

	body := []byte(`{"username":"alice","email":"alice@example.com"}`)
	req := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(body))
	w := httptest.NewRecorder()

	h := PasskeyRegisterPublicBeginHandler(s, wa, cs)
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("#2194 AC-13: Body-username wird ignoriert, expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if id := passkeyBeginKontoID(t, w.Body.Bytes()); id == "alice" {
		t.Errorf("#2194 AC-13: Begin darf die Bestandskennung nicht uebernehmen")
	}
	if nachher := rohesKonto(t, s, "alice"); !bytes.Equal(vorher, nachher) {
		t.Errorf("#2194 AC-13: Bestandskonto alice wurde veraendert")
	}
}

// -----------------------------------------------------------------------------
// AC-3 (umgestellt auf Issue #2194 AC-13): ein ungueltiger Body-username wird
// nicht mehr validiert, sondern ignoriert — 200 mit generierter ID, kein Konto.
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicBegin_InvalidUsername(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
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
			if w.Code != http.StatusOK {
				t.Fatalf("#2194 AC-13 [%s]: username wird ignoriert, expected 200, got %d: %s", tc.name, w.Code, w.Body.String())
			}
			passkeyBeginKontoID(t, w.Body.Bytes()) // prueft ^u-[0-9a-f]{8}$
			if ids, _ := s.ListUserIDs(); len(ids) != 0 {
				t.Errorf("#2194 AC-13 [%s]: Begin darf kein Konto anlegen, vorhanden: %v", tc.name, ids)
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
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
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
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
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
	auth := passkeytest.NewAuthenticator(t, rpID, origin)
	finishBody := auth.MakeAttestationResponse(t, beginResp.PublicKey.Challenge)

	// Step 3: Finish
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
	finishW := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret, config.Config{}).ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusCreated {
		t.Fatalf("AC-5 finish: expected 201, got %d: %s", finishW.Code, finishW.Body.String())
	}

	// User must exist without PasswordHash — unter der generierten ID aus der
	// 201-Antwort, die mit der in Begin gebundenen ID uebereinstimmt (#2194).
	var finishResp struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(finishW.Body.Bytes(), &finishResp); err != nil {
		t.Fatalf("AC-5 finish decode: %v", err)
	}
	if beginID := passkeyBeginKontoID(t, beginW.Body.Bytes()); finishResp.ID != beginID {
		t.Errorf("#2194: Finish-ID %q muss der in Begin gebundenen ID %q gleichen", finishResp.ID, beginID)
	}
	if s.UserExists("passwordless") {
		t.Errorf("#2194: Body-username darf kein Konto benennen")
	}
	user, err := s.LoadUser(finishResp.ID)
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

	// Issue #2271: Das Auto-Login ist entfallen — die Kontoerstellung gelingt,
	// ein Anmelde-Merkmal gibt es erst nach der Bestaetigung der Adresse. Die
	// vormaligen Cookie-Formpruefungen (HttpOnly/SameSite/MaxAge) haben hier
	// keinen Gegenstand mehr; sie bewachen den Passkey-LOGIN-Pfad weiter
	// (passkey_test.go:441, :499).
	for _, c := range finishW.Result().Cookies() {
		if c.Name == "gz_session" {
			t.Errorf("#2271: die oeffentliche Passkey-Registrierung darf kein "+
				"gz_session-Cookie mehr ausstellen, bekommen %q", c.Value)
		}
	}
}

// -----------------------------------------------------------------------------
// Issue #1226 AC-6: Public-Passkey-Finish löst genau einen Verifikations-Dispatch
// mit der im Begin-Schritt übermittelten Adresse aus.
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicFinish_TriggersDispatch_1226_AC6(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	// SMTPHost gesetzt → nicht-Test-User-Zweig ruft beobachtbaren Seam.
	cfg := config.Config{
		PublicHost: "https://gregor20.henemm.com",
		SMTPHost:   "smtp.resend.com", SMTPPort: 587, SMTPUser: "resend", SMTPPass: "re_x",
	}

	type observedCall struct{ to string }
	calls := make(chan observedCall, 4)
	origSend := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		calls <- observedCall{to: to}
		return nil
	}
	defer func() { sendVerificationMailFn = origSend }()

	// Begin — übermittelt username + email.
	beginBody := []byte(`{"username":"pwverify","email":"pwverify@beispiel.de"}`)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(beginBody))
	beginW := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW, beginReq)
	if beginW.Code != http.StatusOK {
		t.Fatalf("AC-6 begin: expected 200, got %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("AC-6 begin decode: %v", err)
	}

	// Finish — echte Attestation über testAuthenticator.
	auth := passkeytest.NewAuthenticator(t, rpID, origin)
	finishBody := auth.MakeAttestationResponse(t, beginResp.PublicKey.Challenge)
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
	finishW := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret, cfg).ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusCreated {
		t.Fatalf("AC-6 finish: expected 201, got %d: %s", finishW.Code, finishW.Body.String())
	}
	// Issue #2194: Konto unter der in Begin erzeugten ID.
	if !s.UserExists(passkeyBeginKontoID(t, beginW.Body.Bytes())) {
		t.Errorf("AC-6: passwordless account must exist after finish")
	}

	select {
	case c := <-calls:
		if c.to != "pwverify@beispiel.de" {
			t.Errorf("AC-6: expected dispatch to 'pwverify@beispiel.de', got %q", c.to)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("AC-6: expected exactly one dispatch call within 2s, none observed")
	}
	select {
	case extra := <-calls:
		t.Errorf("AC-6: expected exactly ONE dispatch call, extra observed: %+v", extra)
	default:
	}
}

// -----------------------------------------------------------------------------
// AC-6: Finish with expired/unknown challenge → 400
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicFinish_ChallengeExpired(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	// Craft a well-formed attestation but without a matching challenge in the store.
	auth := passkeytest.NewAuthenticator(t, rpID, origin)
	body := auth.MakeAttestationResponse(t, "dGhpcyBpcyBhIGZha2UgY2hhbGxlbmdl") // arbitrary b64url

	req := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(body))
	w := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret, config.Config{}).ServeHTTP(w, req)

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
// AC-7: Race — die in Begin erzeugte ID (Issue #2194) wird zwischen Begin und
// Finish belegt → 409, das Konto des anderen wird nicht ueberschrieben.
// -----------------------------------------------------------------------------

func TestPasskeyRegisterPublicFinish_UsernameRace(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := passkeytest.NewWebAuthn(t, rpID, origin)
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
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	json.Unmarshal(beginW.Body.Bytes(), &beginResp)

	// Step 2: Someone else claims the generated id before Finish.
	raced := passkeyBeginKontoID(t, beginW.Body.Bytes())
	if err := s.SaveUser(model.User{ID: raced, PasswordHash: "claimed", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("AC-7: could not claim id: %v", err)
	}
	vorher := rohesKonto(t, s, raced)

	// Step 3: Finish — must reject with 409
	auth := passkeytest.NewAuthenticator(t, rpID, origin)
	finishBody := auth.MakeAttestationResponse(t, beginResp.PublicKey.Challenge)
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
	finishW := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret, config.Config{}).ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusConflict {
		t.Fatalf("AC-7: expected 409, got %d: %s", finishW.Code, finishW.Body.String())
	}
	if !strings.Contains(finishW.Body.String(), "user_already_exists") {
		t.Errorf("AC-7: expected user_already_exists in body, got: %s", finishW.Body.String())
	}
	if nachher := rohesKonto(t, s, raced); !bytes.Equal(vorher, nachher) {
		t.Errorf("AC-7: das zwischenzeitlich angelegte Konto %q wurde ueberschrieben", raced)
	}
}

// Issue #2271: TestPasskeyRegisterPublicFinish_CookieSecureFlag (F004) ist
// ersatzlos entfallen. Nach dem Wegfall des Auto-Logins stellt dieser Weg gar
// kein Cookie mehr aus — der https-Teiltest waere laut rot, der http-Teiltest
// liefe stumm ueber null Cookies und bewachte nichts mehr. Die Secure-Flag-
// Logik bleibt ueber den Passkey-LOGIN-Pfad geprueft
// (passkey_test.go:441 TestPasskeyLoginRoundtrip_Success, :499
// TestPasskeyLoginCookieSecure_OnHTTPS).
