package handler

import (
	"bytes"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/fxamacker/cbor/v2"

	"github.com/go-webauthn/webauthn/protocol"
	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED — Issue #450 Passkey/WebAuthn V1 Add-on.
// Mock-free: ECDSA-P-256 test authenticator constructs real attestation/assertion
// objects that the go-webauthn library verifies cryptographically. The handler
// stubs currently return 501 → every test below must FAIL with the expected
// status mismatch (this is the desired RED state).

// -----------------------------------------------------------------------------
// Test Authenticator — ECDSA-P-256, "none" attestation format
// -----------------------------------------------------------------------------

type testAuthenticator struct {
	rpID    string
	origin  string
	privKey *ecdsa.PrivateKey
	credID  []byte
	aaguid  []byte
}

func newTestAuthenticator(t *testing.T, rpID, origin string) *testAuthenticator {
	t.Helper()
	priv, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatalf("ecdsa keygen: %v", err)
	}
	credID := make([]byte, 32)
	if _, err := rand.Read(credID); err != nil {
		t.Fatalf("rand credID: %v", err)
	}
	return &testAuthenticator{
		rpID:    rpID,
		origin:  origin,
		privKey: priv,
		credID:  credID,
		aaguid:  make([]byte, 16), // zero AAGUID (none-format authenticator)
	}
}

// cosePublicKey returns the CBOR-encoded COSE_Key for the EC2 public key.
func (a *testAuthenticator) cosePublicKey(t *testing.T) []byte {
	t.Helper()
	x := a.privKey.PublicKey.X.Bytes()
	y := a.privKey.PublicKey.Y.Bytes()
	// pad to 32 bytes
	x = leftPad(x, 32)
	y = leftPad(y, 32)
	// COSE_Key map with int keys (canonical CTAP2 encoding):
	// 1 (kty)  = 2 (EC2)
	// 3 (alg)  = -7 (ES256)
	// -1 (crv) = 1 (P-256)
	// -2 (x)   = x-coord
	// -3 (y)   = y-coord
	m := map[int]interface{}{
		1:  2,
		3:  -7,
		-1: 1,
		-2: x,
		-3: y,
	}
	enc, err := cbor.CTAP2EncOptions().EncMode()
	if err != nil {
		t.Fatalf("cbor enc mode: %v", err)
	}
	out, err := enc.Marshal(m)
	if err != nil {
		t.Fatalf("cbor marshal cose key: %v", err)
	}
	return out
}

// buildAuthenticatorData constructs the binary authenticator data blob.
// withAttested=true → includes AttestedCredentialData (registration case).
func (a *testAuthenticator) buildAuthenticatorData(t *testing.T, withAttested bool, signCount uint32) []byte {
	t.Helper()
	rpidHash := sha256.Sum256([]byte(a.rpID))

	var flags byte
	flags |= 0x01 // UP (user present)
	flags |= 0x04 // UV (user verified)
	if withAttested {
		flags |= 0x40 // AT (attested credential data included)
	}

	buf := &bytes.Buffer{}
	buf.Write(rpidHash[:])
	buf.WriteByte(flags)
	scBuf := make([]byte, 4)
	binary.BigEndian.PutUint32(scBuf, signCount)
	buf.Write(scBuf)

	if withAttested {
		buf.Write(a.aaguid) // 16 bytes
		credLen := make([]byte, 2)
		binary.BigEndian.PutUint16(credLen, uint16(len(a.credID)))
		buf.Write(credLen)
		buf.Write(a.credID)
		buf.Write(a.cosePublicKey(t))
	}
	return buf.Bytes()
}

// makeAttestationResponse constructs the JSON body the browser would POST to
// /register/finish: { id, rawId, type, response: { clientDataJSON, attestationObject } }.
func (a *testAuthenticator) makeAttestationResponse(t *testing.T, challengeB64URL string) []byte {
	t.Helper()
	clientData := map[string]interface{}{
		"type":      "webauthn.create",
		"challenge": challengeB64URL,
		"origin":    a.origin,
	}
	clientDataJSON, err := json.Marshal(clientData)
	if err != nil {
		t.Fatalf("clientData marshal: %v", err)
	}

	authData := a.buildAuthenticatorData(t, true, 0)

	// AttestationObject CBOR: { fmt: "none", attStmt: {}, authData: <bytes> }
	attObj := map[string]interface{}{
		"fmt":      "none",
		"attStmt":  map[string]interface{}{},
		"authData": authData,
	}
	enc, _ := cbor.CTAP2EncOptions().EncMode()
	attObjBytes, err := enc.Marshal(attObj)
	if err != nil {
		t.Fatalf("attObj marshal: %v", err)
	}

	credIDB64 := base64.RawURLEncoding.EncodeToString(a.credID)
	body := map[string]interface{}{
		"id":    credIDB64,
		"rawId": credIDB64,
		"type":  "public-key",
		"response": map[string]interface{}{
			"clientDataJSON":    base64.RawURLEncoding.EncodeToString(clientDataJSON),
			"attestationObject": base64.RawURLEncoding.EncodeToString(attObjBytes),
		},
	}
	out, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("body marshal: %v", err)
	}
	return out
}

// makeAssertionResponse signs an assertion for the given challenge and returns
// the JSON body for /login/finish.
func (a *testAuthenticator) makeAssertionResponse(t *testing.T, challengeB64URL string, signCount uint32) []byte {
	t.Helper()
	clientData := map[string]interface{}{
		"type":      "webauthn.get",
		"challenge": challengeB64URL,
		"origin":    a.origin,
	}
	clientDataJSON, err := json.Marshal(clientData)
	if err != nil {
		t.Fatalf("clientData marshal: %v", err)
	}
	clientDataHash := sha256.Sum256(clientDataJSON)

	authData := a.buildAuthenticatorData(t, false, signCount)

	// Signature over authData || sha256(clientDataJSON), ASN.1 DER encoded.
	signedPayload := append([]byte{}, authData...)
	signedPayload = append(signedPayload, clientDataHash[:]...)
	digest := sha256.Sum256(signedPayload)
	sig, err := ecdsa.SignASN1(rand.Reader, a.privKey, digest[:])
	if err != nil {
		t.Fatalf("ecdsa sign: %v", err)
	}

	credIDB64 := base64.RawURLEncoding.EncodeToString(a.credID)
	body := map[string]interface{}{
		"id":    credIDB64,
		"rawId": credIDB64,
		"type":  "public-key",
		"response": map[string]interface{}{
			"clientDataJSON":    base64.RawURLEncoding.EncodeToString(clientDataJSON),
			"authenticatorData": base64.RawURLEncoding.EncodeToString(authData),
			"signature":         base64.RawURLEncoding.EncodeToString(sig),
			"userHandle":        base64.RawURLEncoding.EncodeToString([]byte("placeholder")),
		},
	}
	out, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("body marshal: %v", err)
	}
	return out
}

func leftPad(in []byte, n int) []byte {
	if len(in) >= n {
		return in
	}
	out := make([]byte, n)
	copy(out[n-len(in):], in)
	return out
}

// -----------------------------------------------------------------------------
// Helpers for test setup
// -----------------------------------------------------------------------------

func newTestWebAuthn(t *testing.T, rpID, origin string) *webauthn.WebAuthn {
	t.Helper()
	wa, err := webauthn.New(&webauthn.Config{
		RPID:          rpID,
		RPDisplayName: "Gregor Zwanzig Test",
		RPOrigins:     []string{origin},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	return wa
}

// authedRequest wraps a request with a valid auth context (UserID set in context).
func authedRequest(method, target, userID string, body []byte) *http.Request {
	var r *http.Request
	if body == nil {
		r = httptest.NewRequest(method, target, nil)
	} else {
		r = httptest.NewRequest(method, target, bytes.NewReader(body))
	}
	ctx := middleware.ContextWithUserID(r.Context(), userID)
	return r.WithContext(ctx)
}

// -----------------------------------------------------------------------------
// AC-1: Registration Roundtrip
// -----------------------------------------------------------------------------

func TestPasskeyRegisterRoundtrip_Success(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	// GIVEN: existing user without any passkey
	user := model.User{ID: "alice", PasswordHash: "hash", CreatedAt: time.Now()}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("save user: %v", err)
	}

	// Step 1: Begin — get challenge
	beginH := PasskeyRegisterBeginHandler(s, wa, cs)
	beginReq := authedRequest("POST", "/api/auth/passkey/register/begin", "alice", nil)
	beginW := httptest.NewRecorder()
	beginH.ServeHTTP(beginW, beginReq)

	if beginW.Code != 200 {
		t.Fatalf("AC-1 begin: expected 200, got %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("decode begin response: %v", err)
	}
	if beginResp.PublicKey.Challenge == "" {
		t.Fatalf("AC-1 begin: empty challenge in response")
	}

	// Step 2: Authenticator signs → Finish
	auth := newTestAuthenticator(t, rpID, origin)
	finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)

	finishH := PasskeyRegisterFinishHandler(s, wa, cs)
	finishReq := authedRequest("POST", "/api/auth/passkey/register/finish", "alice", finishBody)
	finishW := httptest.NewRecorder()
	finishH.ServeHTTP(finishW, finishReq)

	if finishW.Code != 201 {
		t.Fatalf("AC-1 finish: expected 201, got %d: %s", finishW.Code, finishW.Body.String())
	}

	// Verify persistence: user has exactly 1 credential with our public key
	reloaded, err := s.LoadUser("alice")
	if err != nil || reloaded == nil {
		t.Fatalf("reload user failed: %v", err)
	}
	if len(reloaded.PasskeyCredentials) != 1 {
		t.Fatalf("AC-1 persist: expected 1 credential, got %d", len(reloaded.PasskeyCredentials))
	}
	if !bytes.Equal(reloaded.PasskeyCredentials[0].ID, auth.credID) {
		t.Errorf("AC-1 persist: credID mismatch")
	}

	// F001 / AC-1: Profile endpoint must report has_passkey:true with one
	// entry — and MUST NOT leak the public_key material.
	profileH := GetProfileHandler(s)
	profileReq := authedRequest("GET", "/api/auth/profile", "alice", nil)
	profileW := httptest.NewRecorder()
	profileH.ServeHTTP(profileW, profileReq)
	if profileW.Code != 200 {
		t.Fatalf("AC-1 profile: expected 200, got %d: %s", profileW.Code, profileW.Body.String())
	}
	var profile map[string]interface{}
	if err := json.Unmarshal(profileW.Body.Bytes(), &profile); err != nil {
		t.Fatalf("AC-1 profile decode: %v", err)
	}
	if hp, _ := profile["has_passkey"].(bool); !hp {
		t.Errorf("AC-1 profile: expected has_passkey:true, got %v", profile["has_passkey"])
	}
	passkeys, ok := profile["passkeys"].([]interface{})
	if !ok || len(passkeys) != 1 {
		t.Fatalf("AC-1 profile: expected passkeys[] of length 1, got %v", profile["passkeys"])
	}
	pk, _ := passkeys[0].(map[string]interface{})
	if pk == nil {
		t.Fatalf("AC-1 profile: passkey entry not an object")
	}
	if _, hasPub := pk["public_key"]; hasPub {
		t.Errorf("AC-1 profile: public_key MUST NOT leak in passkey entry")
	}
	if id, _ := pk["id"].(string); id == "" {
		t.Errorf("AC-1 profile: passkey entry missing id")
	}
	if _, hasCreated := pk["created_at"]; !hasCreated {
		t.Errorf("AC-1 profile: passkey entry missing created_at")
	}
	// "label" is omitempty in JSON; absence is fine, but the field name must
	// not be public_key. We only check that label is either absent or a string.
	if v, present := pk["label"]; present {
		if _, isStr := v.(string); !isStr {
			t.Errorf("AC-1 profile: label must be a string when present, got %T", v)
		}
	}
}

// -----------------------------------------------------------------------------
// AC-2: Login Roundtrip → session cookie
// -----------------------------------------------------------------------------

func TestPasskeyLoginRoundtrip_Success(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	// GIVEN: user with one registered passkey (we register via roundtrip first)
	auth := registerForUser(t, s, wa, cs, "alice")

	// Step 1: Login Begin
	beginH := PasskeyLoginBeginHandler(s, wa, cs)
	beginBody := []byte(`{"username":"alice"}`)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/login/begin", bytes.NewReader(beginBody))
	beginW := httptest.NewRecorder()
	beginH.ServeHTTP(beginW, beginReq)

	if beginW.Code != 200 {
		t.Fatalf("AC-2 begin: expected 200, got %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("decode begin response: %v", err)
	}

	// Step 2: Authenticator signs Assertion
	finishBody := auth.makeAssertionResponse(t, beginResp.PublicKey.Challenge, 1)

	finishH := PasskeyLoginFinishHandler(s, wa, cs, secret)
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/login/finish", bytes.NewReader(finishBody))
	finishW := httptest.NewRecorder()
	finishH.ServeHTTP(finishW, finishReq)

	if finishW.Code != 200 {
		t.Fatalf("AC-2 finish: expected 200, got %d: %s", finishW.Code, finishW.Body.String())
	}

	// Verify session cookie shape: alice.<ts>.<hmac> with HttpOnly + MaxAge + Lax
	var sess *http.Cookie
	for _, c := range finishW.Result().Cookies() {
		if c.Name == "gz_session" {
			sess = c
			break
		}
	}
	if sess == nil {
		t.Fatalf("AC-2: expected gz_session cookie")
	}
	if !sess.HttpOnly {
		t.Errorf("AC-2: cookie should be HttpOnly")
	}
	if sess.MaxAge != 86400 {
		t.Errorf("AC-2: expected MaxAge=86400, got %d", sess.MaxAge)
	}
	if sess.SameSite != http.SameSiteLaxMode {
		t.Errorf("AC-2: expected SameSite=Lax, got %v", sess.SameSite)
	}
	if !strings.HasPrefix(sess.Value, "alice.") {
		t.Errorf("AC-2: cookie should start with 'alice.', got %q", sess.Value)
	}
	parts := strings.Split(sess.Value, ".")
	if len(parts) != 3 {
		t.Errorf("AC-2: cookie expected 3 dot-segments, got %d", len(parts))
	}
	// F003 / AC-2: Cookie path must be "/" so the session is sent on all routes.
	if sess.Path != "/" {
		t.Errorf("AC-2 cookie path: expected '/', got %q", sess.Path)
	}
	// Without X-Forwarded-Proto=https or r.TLS, Secure must be false (this
	// request used plain http://). The HTTPS variant is covered by
	// TestPasskeyLoginCookieSecure_OnHTTPS.
	if sess.Secure {
		t.Errorf("AC-2 cookie secure: expected false on plain http request, got true")
	}
}

// -----------------------------------------------------------------------------
// F003 / AC-2: Cookie Secure flag must be set on HTTPS requests
// -----------------------------------------------------------------------------

func TestPasskeyLoginCookieSecure_OnHTTPS(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	auth := registerForUser(t, s, wa, cs, "alice")

	// Login Begin
	beginH := PasskeyLoginBeginHandler(s, wa, cs)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/login/begin",
		bytes.NewReader([]byte(`{"username":"alice"}`)))
	beginW := httptest.NewRecorder()
	beginH.ServeHTTP(beginW, beginReq)
	if beginW.Code != 200 {
		t.Fatalf("F003 begin: expected 200, got %d", beginW.Code)
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	json.Unmarshal(beginW.Body.Bytes(), &beginResp)

	finishBody := auth.makeAssertionResponse(t, beginResp.PublicKey.Challenge, 1)

	// Simulate the Nginx reverse proxy forwarding an HTTPS request: set
	// X-Forwarded-Proto: https. Cookie MUST be Secure=true.
	finishH := PasskeyLoginFinishHandler(s, wa, cs, secret)
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/login/finish",
		bytes.NewReader(finishBody))
	finishReq.Header.Set("X-Forwarded-Proto", "https")
	finishW := httptest.NewRecorder()
	finishH.ServeHTTP(finishW, finishReq)

	if finishW.Code != 200 {
		t.Fatalf("F003 finish: expected 200, got %d: %s", finishW.Code, finishW.Body.String())
	}
	var sess *http.Cookie
	for _, c := range finishW.Result().Cookies() {
		if c.Name == "gz_session" {
			sess = c
			break
		}
	}
	if sess == nil {
		t.Fatalf("F003: expected gz_session cookie")
	}
	if !sess.Secure {
		t.Errorf("F003: expected Secure=true on HTTPS request, got false")
	}
	if sess.Path != "/" {
		t.Errorf("F003: expected Path=/ on HTTPS request, got %q", sess.Path)
	}
}

// -----------------------------------------------------------------------------
// AC-3: Add Passkey preserves all existing user fields
// -----------------------------------------------------------------------------

func TestPasskeyAddPreservesUserFields(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	// GIVEN: User with ALL optional fields populated
	created := time.Date(2026, 4, 15, 10, 0, 0, 0, time.UTC)
	original := model.User{
		ID:             "alice",
		Email:          "alice@example.com",
		PasswordHash:   "$2a$10$existing-hash",
		MailTo:         "alerts@example.com",
		SignalPhone:    "+436601234567",
		SignalAPIKey:   "sk-existing",
		TelegramChatID: "12345",
		CreatedAt:      created,
	}
	if err := s.SaveUser(original); err != nil {
		t.Fatalf("save: %v", err)
	}

	// WHEN: Add a passkey via roundtrip
	registerForUser(t, s, wa, cs, "alice")

	// THEN: All original fields unchanged + 1 passkey
	reloaded, err := s.LoadUser("alice")
	if err != nil || reloaded == nil {
		t.Fatalf("reload: %v", err)
	}
	if reloaded.Email != "alice@example.com" {
		t.Errorf("AC-3: Email changed: %q", reloaded.Email)
	}
	if reloaded.PasswordHash != "$2a$10$existing-hash" {
		t.Errorf("AC-3: PasswordHash changed: %q", reloaded.PasswordHash)
	}
	if reloaded.MailTo != "alerts@example.com" {
		t.Errorf("AC-3: MailTo changed: %q", reloaded.MailTo)
	}
	if reloaded.SignalPhone != "+436601234567" {
		t.Errorf("AC-3: SignalPhone changed: %q", reloaded.SignalPhone)
	}
	if reloaded.SignalAPIKey != "sk-existing" {
		t.Errorf("AC-3: SignalAPIKey changed: %q", reloaded.SignalAPIKey)
	}
	if reloaded.TelegramChatID != "12345" {
		t.Errorf("AC-3: TelegramChatID changed: %q", reloaded.TelegramChatID)
	}
	if !reloaded.CreatedAt.Equal(created) {
		t.Errorf("AC-3: CreatedAt changed: %v vs %v", reloaded.CreatedAt, created)
	}
	if len(reloaded.PasskeyCredentials) != 1 {
		t.Errorf("AC-3: expected exactly 1 passkey, got %d", len(reloaded.PasskeyCredentials))
	}
}

// -----------------------------------------------------------------------------
// AC-4 Teil 1: expired challenge → 400 challenge_expired_or_missing
// -----------------------------------------------------------------------------

func TestPasskeyChallengeExpired_Fails(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	user := model.User{ID: "alice", PasswordHash: "h", CreatedAt: time.Now()}
	s.SaveUser(user)

	// Begin
	beginW := httptest.NewRecorder()
	PasskeyRegisterBeginHandler(s, wa, cs).ServeHTTP(beginW,
		authedRequest("POST", "/api/auth/passkey/register/begin", "alice", nil))
	if beginW.Code != 200 {
		t.Fatalf("setup begin: expected 200, got %d", beginW.Code)
	}

	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	json.Unmarshal(beginW.Body.Bytes(), &beginResp)

	// Forcibly expire the stored entry — simulate "6 minutes later"
	if v, ok := cs.m.Load(beginResp.PublicKey.Challenge); ok {
		entry := v.(*ChallengeEntry)
		entry.ExpiresAt = time.Now().Add(-1 * time.Minute)
		cs.m.Store(beginResp.PublicKey.Challenge, entry)
	}

	// Now Finish should fail with 400 challenge_expired_or_missing
	auth := newTestAuthenticator(t, rpID, origin)
	finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)

	finishW := httptest.NewRecorder()
	PasskeyRegisterFinishHandler(s, wa, cs).ServeHTTP(finishW,
		authedRequest("POST", "/api/auth/passkey/register/finish", "alice", finishBody))

	if finishW.Code != 400 {
		t.Fatalf("AC-4 expired: expected 400, got %d: %s", finishW.Code, finishW.Body.String())
	}
	if !strings.Contains(finishW.Body.String(), "challenge_expired_or_missing") {
		t.Errorf("AC-4 expired: expected error code 'challenge_expired_or_missing', got %s", finishW.Body.String())
	}
}

// -----------------------------------------------------------------------------
// AC-4 Teil 2: replay (Take is destructive) → 2nd call fails
// -----------------------------------------------------------------------------

func TestPasskeyChallengeReplay_Fails(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	user := model.User{ID: "alice", PasswordHash: "h", CreatedAt: time.Now()}
	s.SaveUser(user)

	// Begin
	beginW := httptest.NewRecorder()
	PasskeyRegisterBeginHandler(s, wa, cs).ServeHTTP(beginW,
		authedRequest("POST", "/api/auth/passkey/register/begin", "alice", nil))
	if beginW.Code != 200 {
		t.Fatalf("setup begin: expected 200, got %d", beginW.Code)
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	json.Unmarshal(beginW.Body.Bytes(), &beginResp)

	auth := newTestAuthenticator(t, rpID, origin)
	finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)

	// First Finish — should succeed (201)
	finish1 := httptest.NewRecorder()
	PasskeyRegisterFinishHandler(s, wa, cs).ServeHTTP(finish1,
		authedRequest("POST", "/api/auth/passkey/register/finish", "alice", finishBody))
	if finish1.Code != 201 {
		t.Fatalf("AC-4 replay setup: first finish expected 201, got %d: %s", finish1.Code, finish1.Body.String())
	}

	// Second Finish with SAME challenge — must fail (Take consumed it)
	finish2 := httptest.NewRecorder()
	PasskeyRegisterFinishHandler(s, wa, cs).ServeHTTP(finish2,
		authedRequest("POST", "/api/auth/passkey/register/finish", "alice", finishBody))
	if finish2.Code != 400 {
		t.Fatalf("AC-4 replay: 2nd finish expected 400, got %d: %s", finish2.Code, finish2.Body.String())
	}
}

// -----------------------------------------------------------------------------
// AC-5: Rate limit — 31st request → 429 + Retry-After
// -----------------------------------------------------------------------------

func TestPasskeyLoginRateLimit_Triggers(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	user := model.User{ID: "alice", PasswordHash: "h", CreatedAt: time.Now()}
	s.SaveUser(user)

	// AC-5 requires the begin endpoint to actually SUCCEED (200) until the
	// limit triggers. That only happens once the user has at least one
	// registered passkey — without it the handler short-circuits to 401
	// "invalid_credentials".
	registerForUser(t, s, wa, cs, "alice")

	// Wrap the login-begin handler with the same limiter the production main.go would.
	limiter := middleware.NewIPRateLimiter(30, time.Hour)
	wrapped := limiter.Middleware(PasskeyLoginBeginHandler(s, wa, cs))

	// 30 requests — each must reach the handler with HTTP 200 (Begin succeeded)
	// and explicitly NOT be 429. A 501 from a stub handler is ALSO a failure
	// (means the real handler is not implemented yet).
	for i := 0; i < 30; i++ {
		req := httptest.NewRequest("POST", "/api/auth/passkey/login/begin",
			bytes.NewReader([]byte(`{"username":"alice"}`)))
		req.RemoteAddr = "10.0.0.1:1234"
		w := httptest.NewRecorder()
		wrapped.ServeHTTP(w, req)
		if w.Code != 200 {
			t.Fatalf("AC-5: req %d expected 200 (begin succeeded), got %d: %s",
				i+1, w.Code, w.Body.String())
		}
	}

	// 31st request — must be 429 with Retry-After header
	req := httptest.NewRequest("POST", "/api/auth/passkey/login/begin",
		bytes.NewReader([]byte(`{"username":"alice"}`)))
	req.RemoteAddr = "10.0.0.1:1234"
	w := httptest.NewRecorder()
	wrapped.ServeHTTP(w, req)

	if w.Code != 429 {
		t.Fatalf("AC-5: expected 429 on 31st request, got %d", w.Code)
	}
	if w.Header().Get("Retry-After") == "" {
		t.Errorf("AC-5: expected Retry-After header on 429")
	}
}

// -----------------------------------------------------------------------------
// AC-6: Delete credential preserves password_hash
// -----------------------------------------------------------------------------

func TestPasskeyDeleteCredentialPreservesPassword(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	// GIVEN: user with password AND one passkey
	if err := s.SaveUser(model.User{
		ID: "alice", PasswordHash: "$2a$10$keep-me-intact", CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("save: %v", err)
	}
	auth := registerForUser(t, s, wa, cs, "alice")
	credIDB64 := base64.RawURLEncoding.EncodeToString(auth.credID)

	// WHEN: DELETE /api/auth/passkey/credentials/{id}
	delH := PasskeyDeleteCredentialHandler(s)
	delReq := authedRequest("DELETE",
		"/api/auth/passkey/credentials/"+credIDB64, "alice", nil)
	delW := httptest.NewRecorder()
	delH.ServeHTTP(delW, delReq)

	if delW.Code != 200 {
		t.Fatalf("AC-6: expected 200, got %d: %s", delW.Code, delW.Body.String())
	}

	// THEN: No passkeys left + password_hash unchanged
	reloaded, err := s.LoadUser("alice")
	if err != nil || reloaded == nil {
		t.Fatalf("reload: %v", err)
	}
	if len(reloaded.PasskeyCredentials) != 0 {
		t.Errorf("AC-6: expected 0 passkeys after delete, got %d", len(reloaded.PasskeyCredentials))
	}
	if reloaded.PasswordHash != "$2a$10$keep-me-intact" {
		t.Errorf("AC-6: PasswordHash changed: %q", reloaded.PasswordHash)
	}

	// F001 / AC-6: Profile endpoint must now report has_passkey:false and an
	// empty (or absent) passkeys[] array.
	profileH := GetProfileHandler(s)
	profileReq := authedRequest("GET", "/api/auth/profile", "alice", nil)
	profileW := httptest.NewRecorder()
	profileH.ServeHTTP(profileW, profileReq)
	if profileW.Code != 200 {
		t.Fatalf("AC-6 profile: expected 200, got %d: %s", profileW.Code, profileW.Body.String())
	}
	var profile map[string]interface{}
	if err := json.Unmarshal(profileW.Body.Bytes(), &profile); err != nil {
		t.Fatalf("AC-6 profile decode: %v", err)
	}
	if hp, _ := profile["has_passkey"].(bool); hp {
		t.Errorf("AC-6 profile: expected has_passkey:false after delete, got %v", profile["has_passkey"])
	}
	if pks, present := profile["passkeys"]; present {
		// omitempty means absent when empty; if present, must be empty slice.
		arr, _ := pks.([]interface{})
		if len(arr) != 0 {
			t.Errorf("AC-6 profile: expected empty passkeys[] after delete, got %v", pks)
		}
	}
}

// -----------------------------------------------------------------------------
// F002 / Spec error table: DELETE endpoint must enforce the rate limit
// -----------------------------------------------------------------------------

func TestPasskeyDeleteRateLimit_Triggers(t *testing.T) {
	s := newTestStore(t)

	if err := s.SaveUser(model.User{
		ID: "alice", PasswordHash: "h", CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("save: %v", err)
	}

	// Wrap the delete handler with the same limiter the production main.go uses.
	limiter := middleware.NewIPRateLimiter(30, time.Hour)
	wrapped := limiter.Middleware(PasskeyDeleteCredentialHandler(s))

	// Use a credential ID that doesn't exist — the handler still runs (returns
	// 200 with no-op delete). The rate limiter counts BEFORE the handler, so
	// the 31st request must produce 429 regardless of handler outcome.
	credIDB64 := base64.RawURLEncoding.EncodeToString([]byte("nonexistent-cred-id-32-bytes-XXX"))

	for i := 0; i < 30; i++ {
		req := authedRequest("DELETE",
			"/api/auth/passkey/credentials/"+credIDB64, "alice", nil)
		req.RemoteAddr = "10.0.0.2:1234"
		w := httptest.NewRecorder()
		wrapped.ServeHTTP(w, req)
		// Accept any non-429 status — the handler may return 200 (no-op delete),
		// 400 (decode), or 404. The point is the limiter has NOT triggered yet.
		if w.Code == 429 {
			t.Fatalf("F002: req %d unexpectedly 429 — limit triggered too early", i+1)
		}
	}

	// 31st request — must be 429
	req := authedRequest("DELETE",
		"/api/auth/passkey/credentials/"+credIDB64, "alice", nil)
	req.RemoteAddr = "10.0.0.2:1234"
	w := httptest.NewRecorder()
	wrapped.ServeHTTP(w, req)

	if w.Code != 429 {
		t.Fatalf("F002: expected 429 on 31st DELETE, got %d", w.Code)
	}
	if w.Header().Get("Retry-After") == "" {
		t.Errorf("F002: expected Retry-After header on 429")
	}
}

// -----------------------------------------------------------------------------
// F004: WebAuthn finish endpoints must reject oversized bodies (>64 KB)
// -----------------------------------------------------------------------------

func TestPasskeyFinishRejectsOversizedBody(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	if err := s.SaveUser(model.User{
		ID: "alice", PasswordHash: "h", CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("save: %v", err)
	}

	// 70 KB of arbitrary bytes — exceeds the 64 KB cap.
	oversized := bytes.Repeat([]byte("A"), 70*1024)

	// Register Finish: oversized body must be rejected (not 201).
	regH := PasskeyRegisterFinishHandler(s, wa, cs)
	regReq := authedRequest("POST", "/api/auth/passkey/register/finish", "alice", oversized)
	regW := httptest.NewRecorder()
	regH.ServeHTTP(regW, regReq)
	if regW.Code == 201 {
		t.Errorf("F004 register/finish: oversized body should NOT succeed (got 201)")
	}
	// MaxBytesReader returns an error from io.ReadAll → handler writes 400.
	// Some Go versions also surface 413; accept either.
	if regW.Code != 400 && regW.Code != 413 {
		t.Errorf("F004 register/finish: expected 400 or 413, got %d: %s",
			regW.Code, regW.Body.String())
	}

	// Login Finish: oversized body must be rejected (not 200).
	loginH := PasskeyLoginFinishHandler(s, wa, cs, secret)
	loginReq := httptest.NewRequest("POST", "/api/auth/passkey/login/finish",
		bytes.NewReader(oversized))
	loginW := httptest.NewRecorder()
	loginH.ServeHTTP(loginW, loginReq)
	if loginW.Code == 200 {
		t.Errorf("F004 login/finish: oversized body should NOT succeed (got 200)")
	}
	// Login handler maps parse errors to 401 invalid_credentials; MaxBytesReader
	// failure surfaces through the parser as the same generic error.
	if loginW.Code != 401 && loginW.Code != 400 && loginW.Code != 413 {
		t.Errorf("F004 login/finish: expected 401/400/413, got %d: %s",
			loginW.Code, loginW.Body.String())
	}
	// Importantly: no session cookie on failure.
	for _, c := range loginW.Result().Cookies() {
		if c.Name == "gz_session" && c.Value != "" {
			t.Errorf("F004 login/finish: no session cookie allowed on oversized body")
		}
	}
}

// -----------------------------------------------------------------------------
// AC-8: Staging RP-ID cannot be used to log in on Prod RP-ID
// -----------------------------------------------------------------------------

func TestPasskeyStagingRPIDFailsOnProd_RoundtripIsolation(t *testing.T) {
	prodRPID := "gregor20.henemm.com"
	prodOrigin := "https://gregor20.henemm.com"
	stagingRPID := "staging.gregor20.henemm.com"
	stagingOrigin := "https://staging.gregor20.henemm.com"

	s := newTestStore(t)
	waProd := newTestWebAuthn(t, prodRPID, prodOrigin)
	waStaging := newTestWebAuthn(t, stagingRPID, stagingOrigin)
	csProd := NewChallengeStore()
	csStaging := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"

	// User registered with STAGING credentials
	if err := s.SaveUser(model.User{ID: "alice", PasswordHash: "h", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("save: %v", err)
	}
	authStaging := registerForUserAt(t, s, waStaging, csStaging, "alice", stagingRPID, stagingOrigin)

	// Try to LOG IN on PROD instance — must fail (RP-ID mismatch)
	beginW := httptest.NewRecorder()
	PasskeyLoginBeginHandler(s, waProd, csProd).ServeHTTP(beginW,
		httptest.NewRequest("POST", "/api/auth/passkey/login/begin",
			bytes.NewReader([]byte(`{"username":"alice"}`))))
	if beginW.Code != 200 {
		t.Fatalf("AC-8 setup: expected 200 on prod begin, got %d", beginW.Code)
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	json.Unmarshal(beginW.Body.Bytes(), &beginResp)

	// Authenticator built for STAGING signs PROD-issued challenge
	// → assertion's authenticatorData.RPIDHash will be sha256(staging.RPID),
	//   but Prod RP expects sha256(prod.RPID) → library verification fails.
	stagingAuthForProdChallenge := &testAuthenticator{
		rpID:    stagingRPID,
		origin:  stagingOrigin,
		privKey: authStaging.privKey,
		credID:  authStaging.credID,
		aaguid:  make([]byte, 16),
	}
	finishBody := stagingAuthForProdChallenge.makeAssertionResponse(t, beginResp.PublicKey.Challenge, 1)

	finishW := httptest.NewRecorder()
	PasskeyLoginFinishHandler(s, waProd, csProd, secret).ServeHTTP(finishW,
		httptest.NewRequest("POST", "/api/auth/passkey/login/finish",
			bytes.NewReader(finishBody)))

	if finishW.Code != 401 {
		t.Fatalf("AC-8: expected 401 for cross-environment login, got %d: %s",
			finishW.Code, finishW.Body.String())
	}

	// Ensure NO session cookie was set
	for _, c := range finishW.Result().Cookies() {
		if c.Name == "gz_session" && c.Value != "" {
			t.Errorf("AC-8: cookie must NOT be set on failed login, got %q", c.Value)
		}
	}
}

// -----------------------------------------------------------------------------
// Shared helpers for AC-2/3/6/8: register a passkey via real roundtrip
// -----------------------------------------------------------------------------

func registerForUser(t *testing.T, s *store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore, userID string) *testAuthenticator {
	t.Helper()
	return registerForUserAt(t, s, wa, cs, userID, "localhost", "http://localhost")
}

func registerForUserAt(t *testing.T, s *store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore, userID, rpID, origin string) *testAuthenticator {
	t.Helper()

	// Make the helper idempotent: ensure the user record exists so the begin
	// handler doesn't 404. Callers that pre-create the user with custom fields
	// (e.g. AC-3 preservation test) win because SaveUser is a no-op overwrite
	// only when the existing record is empty.
	if existing, _ := s.LoadUser(userID); existing == nil {
		if err := s.SaveUser(model.User{ID: userID, PasswordHash: "h", CreatedAt: time.Now()}); err != nil {
			t.Fatalf("registerForUser seed user: %v", err)
		}
	}

	beginH := PasskeyRegisterBeginHandler(s, wa, cs)
	beginReq := authedRequest("POST", "/api/auth/passkey/register/begin", userID, nil)
	beginW := httptest.NewRecorder()
	beginH.ServeHTTP(beginW, beginReq)
	if beginW.Code != 200 {
		t.Fatalf("registerForUser begin: expected 200, got %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("registerForUser begin decode: %v", err)
	}

	auth := newTestAuthenticator(t, rpID, origin)
	finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)
	finishH := PasskeyRegisterFinishHandler(s, wa, cs)
	finishReq := authedRequest("POST", "/api/auth/passkey/register/finish", userID, finishBody)
	finishW := httptest.NewRecorder()
	finishH.ServeHTTP(finishW, finishReq)
	if finishW.Code != 201 {
		t.Fatalf("registerForUser finish: expected 201, got %d: %s", finishW.Code, finishW.Body.String())
	}
	return auth
}

// silence unused-import vigilance for protocol package — referenced via lib.
var _ = protocol.AuthenticatorTransport("")

// -----------------------------------------------------------------------------
// TDD RED — Issue #467 Discoverable Credentials + Conditional UI
// Handler PasskeyLoginDiscoverableBeginHandler / PasskeyLoginDiscoverableFinishHandler
// do NOT exist yet → build fails (RED state). Tests written against the spec.
// -----------------------------------------------------------------------------

// makeAssertionResponseDiscoverable builds an assertion body for the Discoverable
// flow where userHandle carries the real user ID (not "placeholder").
func (a *testAuthenticator) makeAssertionResponseDiscoverable(t *testing.T, challengeB64URL string, signCount uint32, userID string) []byte {
	t.Helper()
	clientData := map[string]interface{}{
		"type":      "webauthn.get",
		"challenge": challengeB64URL,
		"origin":    a.origin,
	}
	clientDataJSON, err := json.Marshal(clientData)
	if err != nil {
		t.Fatalf("clientData marshal: %v", err)
	}
	clientDataHash := sha256.Sum256(clientDataJSON)

	authData := a.buildAuthenticatorData(t, false, signCount)

	signedPayload := append([]byte{}, authData...)
	signedPayload = append(signedPayload, clientDataHash[:]...)
	digest := sha256.Sum256(signedPayload)
	sig, err := ecdsa.SignASN1(rand.Reader, a.privKey, digest[:])
	if err != nil {
		t.Fatalf("ecdsa sign: %v", err)
	}

	credIDB64 := base64.RawURLEncoding.EncodeToString(a.credID)
	body := map[string]interface{}{
		"id":    credIDB64,
		"rawId": credIDB64,
		"type":  "public-key",
		"response": map[string]interface{}{
			"clientDataJSON":    base64.RawURLEncoding.EncodeToString(clientDataJSON),
			"authenticatorData": base64.RawURLEncoding.EncodeToString(authData),
			"signature":         base64.RawURLEncoding.EncodeToString(sig),
			// Real user ID as userHandle — required by DiscoverableUserHandler
			"userHandle": base64.RawURLEncoding.EncodeToString([]byte(userID)),
		},
	}
	out, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("body marshal: %v", err)
	}
	return out
}

// AC-1: Discoverable Begin liefert HTTP 200 mit "mediation":"conditional"
func TestPasskeyDiscoverableBeginHandler_ReturnsConditionalMediation(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	_ = newTestStore(t) // Begin does not require a populated store
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	h := PasskeyLoginDiscoverableBeginHandler(wa, cs)
	req := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/begin", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Response must contain "mediation":"conditional" at top level.
	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("response not valid JSON: %v", err)
	}
	mediation, ok := resp["mediation"]
	if !ok {
		t.Fatal(`response missing "mediation" field — BeginDiscoverableMediatedLogin must be used, not BeginDiscoverableLogin`)
	}
	if mediation != "conditional" {
		t.Fatalf(`expected "mediation":"conditional", got %q`, mediation)
	}

	// publicKey.challenge must be present
	pk, _ := resp["publicKey"].(map[string]interface{})
	if pk == nil {
		t.Fatal(`response missing "publicKey" field`)
	}
	challenge, _ := pk["challenge"].(string)
	if challenge == "" {
		t.Fatal(`publicKey.challenge is empty`)
	}
}

// AC-1 (Teil 2): ChallengeEntry.UserID muss leer sein nach Begin
func TestPasskeyDiscoverableBeginHandler_ChallengeEntryUserIDIsEmpty(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	_ = newTestStore(t) // store not needed for begin-only test
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	h := PasskeyLoginDiscoverableBeginHandler(wa, cs)
	req := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/begin", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// Extract challenge from response and look up the entry in the store
	var resp map[string]interface{}
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	pk, _ := resp["publicKey"].(map[string]interface{})
	challenge, _ := pk["challenge"].(string)

	entry, ok := cs.Take(challenge)
	if !ok {
		t.Fatal("challenge not found in ChallengeStore after Begin")
	}
	if entry.UserID != "" {
		t.Fatalf("ChallengeEntry.UserID must be empty for Discoverable flow, got %q", entry.UserID)
	}
}

// AC-2: Discoverable Finish — vollständiger Roundtrip setzt Session-Cookie
func TestPasskeyDiscoverableFinishHandler_FullRoundtrip_Success(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret"

	// Register a passkey for alice
	userID := "alice"
	auth := registerForUser(t, s, wa, cs, userID)

	// Discoverable Begin
	beginH := PasskeyLoginDiscoverableBeginHandler(wa, cs)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/begin", nil)
	beginW := httptest.NewRecorder()
	beginH.ServeHTTP(beginW, beginReq)
	if beginW.Code != http.StatusOK {
		t.Fatalf("begin: expected 200, got %d: %s", beginW.Code, beginW.Body.String())
	}

	var beginResp map[string]interface{}
	_ = json.Unmarshal(beginW.Body.Bytes(), &beginResp)
	pk, _ := beginResp["publicKey"].(map[string]interface{})
	challenge, _ := pk["challenge"].(string)

	// Construct assertion with real userHandle = "alice"
	assertionBody := auth.makeAssertionResponseDiscoverable(t, challenge, 1, userID)

	// Discoverable Finish
	finishH := PasskeyLoginDiscoverableFinishHandler(s, wa, cs, secret)
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/finish",
		strings.NewReader(string(assertionBody)))
	finishReq.Header.Set("Content-Type", "application/json")
	finishW := httptest.NewRecorder()
	finishH.ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusOK {
		t.Fatalf("finish: expected 200, got %d: %s", finishW.Code, finishW.Body.String())
	}

	// Session cookie must be set
	setCookie := finishW.Header().Get("Set-Cookie")
	if !strings.Contains(setCookie, "gz_session=") {
		t.Fatalf("expected gz_session cookie, got: %q", setCookie)
	}
	if !strings.Contains(setCookie, "HttpOnly") {
		t.Fatal("gz_session cookie must be HttpOnly")
	}

	// Response body must contain the user ID
	var finishResp map[string]string
	if err := json.Unmarshal(finishW.Body.Bytes(), &finishResp); err != nil {
		t.Fatalf("finish response not valid JSON: %v", err)
	}
	if finishResp["id"] != userID {
		t.Fatalf("expected id=%q, got %q", userID, finishResp["id"])
	}

	// LastUsedAt must be set after successful discoverable login
	reloaded, err := s.LoadUser(userID)
	if err != nil || reloaded == nil {
		t.Fatal("user not found after finish")
	}
	if len(reloaded.PasskeyCredentials) == 0 {
		t.Fatal("no credentials after finish")
	}
	if reloaded.PasskeyCredentials[0].LastUsedAt.IsZero() {
		t.Fatal("LastUsedAt was not updated after discoverable login")
	}
}

// AC-3: Leerer userHandle → 401
func TestPasskeyDiscoverableFinishHandler_EmptyUserHandle_Returns401(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret"

	userID := "alice"
	auth := registerForUser(t, s, wa, cs, userID)

	// Begin
	beginH := PasskeyLoginDiscoverableBeginHandler(wa, cs)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/begin", nil)
	beginW := httptest.NewRecorder()
	beginH.ServeHTTP(beginW, beginReq)
	var beginResp map[string]interface{}
	_ = json.Unmarshal(beginW.Body.Bytes(), &beginResp)
	pk, _ := beginResp["publicKey"].(map[string]interface{})
	challenge, _ := pk["challenge"].(string)

	// Assertion with empty userHandle
	assertionBody := auth.makeAssertionResponseDiscoverable(t, challenge, 1, "")

	finishH := PasskeyLoginDiscoverableFinishHandler(s, wa, cs, secret)
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/finish",
		strings.NewReader(string(assertionBody)))
	finishReq.Header.Set("Content-Type", "application/json")
	finishW := httptest.NewRecorder()
	finishH.ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 for empty userHandle, got %d: %s", finishW.Code, finishW.Body.String())
	}
}

// AC-3 (Teil 2): Unbekannter userHandle → 401
func TestPasskeyDiscoverableFinishHandler_UnknownUserHandle_Returns401(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret"

	userID := "alice"
	auth := registerForUser(t, s, wa, cs, userID)

	beginH := PasskeyLoginDiscoverableBeginHandler(wa, cs)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/begin", nil)
	beginW := httptest.NewRecorder()
	beginH.ServeHTTP(beginW, beginReq)
	var beginResp map[string]interface{}
	_ = json.Unmarshal(beginW.Body.Bytes(), &beginResp)
	pk, _ := beginResp["publicKey"].(map[string]interface{})
	challenge, _ := pk["challenge"].(string)

	// userHandle points to a user that doesn't exist
	assertionBody := auth.makeAssertionResponseDiscoverable(t, challenge, 1, "does-not-exist")

	finishH := PasskeyLoginDiscoverableFinishHandler(s, wa, cs, secret)
	finishReq := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/finish",
		strings.NewReader(string(assertionBody)))
	finishReq.Header.Set("Content-Type", "application/json")
	finishW := httptest.NewRecorder()
	finishH.ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 for unknown userHandle, got %d: %s", finishW.Code, finishW.Body.String())
	}
}

// AC-4: Challenge-Replay nach erfolgreichem Finish → 401
func TestPasskeyDiscoverableFinishHandler_ChallengeReplay_Returns401(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	s := newTestStore(t)
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret"

	userID := "alice"
	auth := registerForUser(t, s, wa, cs, userID)

	beginH := PasskeyLoginDiscoverableBeginHandler(wa, cs)
	beginReq := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/begin", nil)
	beginW := httptest.NewRecorder()
	beginH.ServeHTTP(beginW, beginReq)
	var beginResp map[string]interface{}
	_ = json.Unmarshal(beginW.Body.Bytes(), &beginResp)
	pk, _ := beginResp["publicKey"].(map[string]interface{})
	challenge, _ := pk["challenge"].(string)

	assertionBody := auth.makeAssertionResponseDiscoverable(t, challenge, 1, userID)
	finishH := PasskeyLoginDiscoverableFinishHandler(s, wa, cs, secret)

	// First call — must succeed
	req1 := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/finish",
		strings.NewReader(string(assertionBody)))
	req1.Header.Set("Content-Type", "application/json")
	w1 := httptest.NewRecorder()
	finishH.ServeHTTP(w1, req1)
	if w1.Code != http.StatusOK {
		t.Fatalf("first finish: expected 200, got %d: %s", w1.Code, w1.Body.String())
	}

	// Second call with same challenge body — ChallengeStore.Take is destructive
	req2 := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/finish",
		strings.NewReader(string(assertionBody)))
	req2.Header.Set("Content-Type", "application/json")
	w2 := httptest.NewRecorder()
	finishH.ServeHTTP(w2, req2)
	if w2.Code != http.StatusUnauthorized {
		t.Fatalf("replay: expected 401, got %d: %s", w2.Code, w2.Body.String())
	}
}

// F004 (Discoverable): oversized body must not be accepted at /discoverable/finish.
func TestPasskeyDiscoverableFinishRejectsOversizedBody(t *testing.T) {
	rpID, origin := "localhost", "http://localhost"
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	s := newTestStore(t)
	secret := "test-secret"

	// 70 KB body — exceeds the 64 KB cap
	oversized := make([]byte, 70*1024)
	for i := range oversized {
		oversized[i] = 'x'
	}

	h := PasskeyLoginDiscoverableFinishHandler(s, wa, cs, secret)
	req := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/finish",
		bytes.NewReader(oversized))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code == http.StatusOK {
		t.Fatalf("oversized body must not return 200, got %d", w.Code)
	}
}
