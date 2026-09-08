package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED — Issue #2130: die RP-ID muss dort stimmen, wo sie wirkt — im JSON,
// das der Browser bekommt.
// Spec: docs/specs/modules/passkey_rp_konfiguration.md (AC-1, AC-3)
//
// RED-Zustand: Kompilierfehler, weil config.NewWebAuthn(*config.Config) noch
// nicht existiert.
//
// Bewusst OHNE newTestWebAuthn(t, rpID, origin): genau dieses Selbstbauen der
// Konfiguration ist der Grund, warum die 31 bestehenden Passkey-Tests grün
// blieben, während Produktion drei Monate rpId "localhost" gesendet hat. Hier
// läuft die echte Kette config.Load() -> config.NewWebAuthn() -> Handler ->
// Antwort-JSON.

// withPasskeyEnv leert die Prozess-Umgebung, setzt die übergebenen Variablen und
// stellt den Ausgangszustand nach dem Test vollständig wieder her.
func withPasskeyEnv(t *testing.T, vars map[string]string) {
	t.Helper()
	saved := os.Environ()
	t.Cleanup(func() {
		os.Clearenv()
		for _, kv := range saved {
			if i := strings.IndexByte(kv, '='); i > 0 {
				os.Setenv(kv[:i], kv[i+1:])
			}
		}
	})
	os.Clearenv()
	for k, v := range vars {
		os.Setenv(k, v)
	}
}

// webAuthnAusEchterKonfiguration baut die WebAuthn-Instanz so, wie sie der
// laufende Server baut: aus config.Load() ohne handgesetzte RP-Werte.
func webAuthnAusEchterKonfiguration(t *testing.T, publicHost string) *webauthn.WebAuthn {
	t.Helper()
	withPasskeyEnv(t, map[string]string{"GZ_PUBLIC_HOST": publicHost})

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	wa, err := config.NewWebAuthn(cfg)
	if err != nil {
		t.Fatalf("config.NewWebAuthn: %v", err)
	}
	return wa
}

// -----------------------------------------------------------------------------
// AC-1: rpId in der Antwort von /discoverable/begin
// -----------------------------------------------------------------------------

func TestDiscoverableBeginSendetAbgeleiteteRPID(t *testing.T) {
	// GIVEN: Server-Konfiguration mit GZ_PUBLIC_HOST, ohne explizite RP-Variablen
	wa := webAuthnAusEchterKonfiguration(t, "https://gregor20.henemm.com")
	cs := NewChallengeStore()

	// WHEN: ein Client POST /api/auth/passkey/discoverable/begin aufruft
	h := PasskeyLoginDiscoverableBeginHandler(wa, cs)
	req := httptest.NewRequest("POST", "/api/auth/passkey/discoverable/begin", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-1: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	// THEN: publicKey.rpId trägt den Hostanteil von PublicHost, nicht "localhost"
	var resp struct {
		PublicKey struct {
			RPID string `json:"rpId"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("AC-1: Antwort ist kein gültiges JSON: %v — %s", err, w.Body.String())
	}
	if resp.PublicKey.RPID != "gregor20.henemm.com" {
		t.Errorf("AC-1: erwartet rpId %q im publicKey der Antwort, bekommen %q (Antwort: %s)",
			"gregor20.henemm.com", resp.PublicKey.RPID, w.Body.String())
	}
}

// AC-1: derselbe Weg für den klassischen Login mit Benutzernamen — auch dort
// bekommt der Browser die abgeleitete RP-ID.
func TestLoginBeginSendetAbgeleiteteRPID(t *testing.T) {
	wa := webAuthnAusEchterKonfiguration(t, "https://gregor20.henemm.com")
	s := newTestStore(t)
	cs := NewChallengeStore()

	// Platzhalter-Credential: /login/begin braucht nur eine nicht-leere Liste,
	// um eine allowCredentials-Antwort zu bilden. Kryptografisch geprüft wird
	// hier nichts — gelesen wird ausschliesslich die rpId der Begin-Antwort.
	user := model.User{ID: "alice", PasswordHash: "hash", CreatedAt: time.Now()}
	user.PasskeyCredentials = []model.WebAuthnCredential{{
		ID:        []byte("test-credential-id"),
		PublicKey: []byte("test-public-key"),
		CreatedAt: time.Now(),
	}}
	if err := s.SaveUser(user); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	body := []byte(`{"username":"alice"}`)
	req := httptest.NewRequest("POST", "/api/auth/passkey/login/begin", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	PasskeyLoginBeginHandler(s, wa, cs).ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-1: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	var resp struct {
		PublicKey struct {
			RPID string `json:"rpId"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("AC-1: Antwort ist kein gültiges JSON: %v — %s", err, w.Body.String())
	}
	if resp.PublicKey.RPID != "gregor20.henemm.com" {
		t.Errorf("AC-1: erwartet rpId %q, bekommen %q (Antwort: %s)",
			"gregor20.henemm.com", resp.PublicKey.RPID, w.Body.String())
	}
}

// -----------------------------------------------------------------------------
// AC-3 (Kern-Anteil): residentKey im tatsächlich gesendeten JSON
// -----------------------------------------------------------------------------

// /register/begin muss global residentKey "preferred" senden.
func TestRegisterBeginSendetResidentKeyPreferred(t *testing.T) {
	wa := webAuthnAusEchterKonfiguration(t, "https://gregor20.henemm.com")
	s := newTestStore(t)
	cs := NewChallengeStore()

	if err := s.SaveUser(model.User{ID: "alice", PasswordHash: "hash", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	req := authedRequest("POST", "/api/auth/passkey/register/begin", "alice", nil)
	w := httptest.NewRecorder()
	PasskeyRegisterBeginHandler(s, wa, cs).ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	got := residentKeyAusAntwort(t, w.Body.Bytes())
	if got != "preferred" {
		t.Errorf("AC-3: /register/begin muss residentKey %q senden, bekommen %q (Antwort: %s)",
			"preferred", got, w.Body.String())
	}
}

// /register/public/begin muss residentKey "required" senden — ohne auffindbares
// Credential hätte ein passwortloser Nutzer keinen Wiedereinstieg.
func TestRegisterPublicBeginSendetResidentKeyRequired(t *testing.T) {
	wa := webAuthnAusEchterKonfiguration(t, "https://gregor20.henemm.com")
	s := newTestStore(t)
	cs := NewChallengeStore()

	body := []byte(`{"username":"neuernutzer","email":"neu@example.com"}`)
	req := httptest.NewRequest("POST", "/api/auth/passkey/register/public/begin", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	got := residentKeyAusAntwort(t, w.Body.Bytes())
	if got != "required" {
		t.Errorf("AC-3: /register/public/begin muss residentKey %q senden, bekommen %q (Antwort: %s)",
			"required", got, w.Body.String())
	}
}

// residentKeyAusAntwort liest den tatsächlich gesendeten Wert aus dem JSON —
// nicht, ob irgendeine Funktion aufgerufen wurde.
func residentKeyAusAntwort(t *testing.T, body []byte) string {
	t.Helper()
	var resp struct {
		PublicKey struct {
			AuthenticatorSelection struct {
				ResidentKey string `json:"residentKey"`
			} `json:"authenticatorSelection"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(body, &resp); err != nil {
		t.Fatalf("Antwort ist kein gültiges JSON: %v — %s", err, string(body))
	}
	return resp.PublicKey.AuthenticatorSelection.ResidentKey
}
