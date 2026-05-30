package handler

// TDD RED — Issue #468 AAGUID-Labels: Profile-Endpoint Tests.
// Tests MUST FAIL: AuthenticatorName field does not exist in passkeyProfileEntry yet.

import (
	"encoding/json"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"
	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// iCloud Keychain AAGUID bytes (fbfc3007-154e-4ecc-8cfb-6ef08c534b35)
var iCloudKeychainAAGUID = []byte{
	0xfb, 0xfc, 0x30, 0x07,
	0x15, 0x4e,
	0x4e, 0xcc,
	0x8c, 0xfb,
	0x6e, 0xf0, 0x8c, 0x53, 0x4b, 0x35,
}

// seedUserWithPasskey speichert einen User mit einem Passkey-Credential über den Store.
func seedUserWithPasskey(t *testing.T, s *store.Store, userID string, aaguid []byte, label string) {
	t.Helper()
	hash, _ := bcrypt.GenerateFromPassword([]byte("pw123"), bcrypt.MinCost)
	cred := model.WebAuthnCredential{
		ID:        []byte{0x01, 0x02, 0x03},
		PublicKey: []byte{0x04, 0x05},
		Authenticator: webauthn.Authenticator{
			AAGUID:    aaguid,
			SignCount: 1,
		},
		CreatedAt: time.Now().UTC(),
		Label:     label,
	}
	u := model.User{
		ID:                 userID,
		PasswordHash:       string(hash),
		PasskeyCredentials: []model.WebAuthnCredential{cred},
		CreatedAt:          time.Now().UTC(),
	}
	if err := s.SaveUser(u); err != nil {
		t.Fatalf("seedUserWithPasskey: %v", err)
	}
}

// AC-1: Profile-Response enthält authenticator_name für bekannte AAGUID
func TestProfileHandler_KnownAAGUID_ReturnsAuthenticatorName(t *testing.T) {
	// GIVEN: User mit einem iCloud-Keychain-Passkey (bekannte AAGUID)
	s := newTestStore(t)
	seedUserWithPasskey(t, s, "aaguid-user", iCloudKeychainAAGUID, "")
	h := GetProfileHandler(s)

	// WHEN: Profil abgerufen wird
	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	ctx := middleware.ContextWithUserID(req.Context(), "aaguid-user")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// THEN: passkeys[0].authenticator_name == "iCloud Keychain"
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	passkeys, ok := resp["passkeys"].([]interface{})
	if !ok || len(passkeys) == 0 {
		t.Fatalf("expected passkeys array, got: %v", resp["passkeys"])
	}
	pk := passkeys[0].(map[string]interface{})
	if pk["authenticator_name"] != "iCloud Keychain" {
		t.Errorf("authenticator_name: got %q, want %q", pk["authenticator_name"], "iCloud Keychain")
	}
}

// AC-2: Zero-AAGUID → authenticator_name fehlt komplett in JSON (omitempty)
func TestProfileHandler_ZeroAAGUID_AuthenticatorNameAbsent(t *testing.T) {
	// GIVEN: User mit einem Passkey mit Zero-AAGUID (alle Bytes = 0x00)
	s := newTestStore(t)
	seedUserWithPasskey(t, s, "zero-aaguid-user", make([]byte, 16), "Mein Gerät")
	h := GetProfileHandler(s)

	// WHEN: Profil abgerufen wird
	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	ctx := middleware.ContextWithUserID(req.Context(), "zero-aaguid-user")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// THEN: authenticator_name darf NICHT im JSON erscheinen (omitempty)
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	passkeys, _ := resp["passkeys"].([]interface{})
	if len(passkeys) == 0 {
		t.Fatalf("expected at least one passkey entry")
	}
	pk := passkeys[0].(map[string]interface{})
	if _, has := pk["authenticator_name"]; has {
		t.Errorf("authenticator_name should be absent for zero AAGUID, got: %v", pk["authenticator_name"])
	}
}

// AC-3: Beide Felder gesetzt → authenticator_name UND label stehen in der Response
func TestProfileHandler_BothAAGUIDAndLabel(t *testing.T) {
	// GIVEN: User mit iCloud-Keychain-Passkey UND User-Label "Büro-Mac"
	s := newTestStore(t)
	seedUserWithPasskey(t, s, "both-fields-user", iCloudKeychainAAGUID, "Büro-Mac")
	h := GetProfileHandler(s)

	// WHEN: Profil abgerufen wird
	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	ctx := middleware.ContextWithUserID(req.Context(), "both-fields-user")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// THEN: Beide Felder müssen in passkeys[0] vorhanden sein
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)

	passkeys, ok := resp["passkeys"].([]interface{})
	if !ok || len(passkeys) == 0 {
		t.Fatalf("expected passkeys array")
	}
	pk := passkeys[0].(map[string]interface{})
	if pk["authenticator_name"] != "iCloud Keychain" {
		t.Errorf("authenticator_name: got %q, want %q", pk["authenticator_name"], "iCloud Keychain")
	}
	if pk["label"] != "Büro-Mac" {
		t.Errorf("label: got %q, want %q", pk["label"], "Büro-Mac")
	}
}

// AC-5: nil-AAGUID (älterer Datensatz ohne AAGUID) → kein Fehler, 200 OK
func TestProfileHandler_NilAAGUID_NoError(t *testing.T) {
	// GIVEN: User mit Passkey der nil AAGUID hat (z.B. alter Datensatz)
	s := newTestStore(t)
	seedUserWithPasskey(t, s, "nil-aaguid-user", nil, "Altes Gerät")
	h := GetProfileHandler(s)

	// WHEN: Profil abgerufen wird
	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	ctx := middleware.ContextWithUserID(req.Context(), "nil-aaguid-user")
	req = req.WithContext(ctx)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	// THEN: 200 ohne Fehler, valides JSON
	if w.Code != 200 {
		t.Fatalf("expected 200 for nil AAGUID, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("invalid JSON in response: %v", err)
	}
}
