package handler

// Issue #2961 (GA10) — Enumeration: Ablauf eines Reset-/Bestaetigungs-Tokens
// wird erst nach dem Vergleich gemeldet; Passkey-Anmeldestart antwortet fuer
// unbekannte Konten und Konten ohne Passkey gleich.
// Spec: docs/specs/modules/security_haertung_2026_11_go_anmeldung.md (AC-28, AC-29).

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"
	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
)

func tokenHash2961(t *testing.T, tok string) string {
	t.Helper()
	h, err := bcrypt.GenerateFromPassword([]byte(tok), bcrypt.MinCost)
	if err != nil {
		t.Fatal(err)
	}
	return string(h)
}

// AC-28: ein falsches Token gegen ein abgelaufenes liefert dieselbe Antwort
// wie gegen ein gueltiges (invalid_token); token_expired erst, wenn das
// Token selbst stimmt.
func TestResetToken_AblaufErstNachVergleich(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "resetnutzer", CreatedAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveResetToken("resetnutzer", model.PasswordResetToken{
		TokenHash: tokenHash2961(t, "das-richtige-token"), ExpiresAt: time.Now().Add(-time.Minute),
	}); err != nil {
		t.Fatal(err)
	}
	h := ResetPasswordHandler(s, bcrypt.MinCost)
	senden := func(tok string) string {
		body := `{"username":"resetnutzer","token":"` + tok + `","new_password":"neues-passwort-1"}`
		w := httptest.NewRecorder()
		h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/reset-password", strings.NewReader(body)))
		return w.Body.String()
	}
	if b := senden("geraten"); !strings.Contains(b, `"invalid_token"`) {
		t.Fatalf("falsches Token gegen abgelaufenes: erwartet invalid_token, bekommen %s", b)
	}
	if b := senden("das-richtige-token"); !strings.Contains(b, `"token_expired"`) {
		t.Fatalf("richtiges, abgelaufenes Token: erwartet token_expired, bekommen %s", b)
	}
}

func TestBestaetigungsToken_AblaufErstNachVergleich(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "verifynutzer", Email: "v@beispiel.de", CreatedAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveVerificationToken("verifynutzer", model.EmailVerificationToken{
		TokenHash: tokenHash2961(t, "das-richtige-token"), ExpiresAt: time.Now().Add(-time.Minute),
		Address: "v@beispiel.de",
	}); err != nil {
		t.Fatal(err)
	}
	h := VerifyEmailHandler(s)
	senden := func(tok string) string {
		body := `{"user":"verifynutzer","token":"` + tok + `"}`
		w := httptest.NewRecorder()
		h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/verify-email", strings.NewReader(body)))
		return w.Body.String()
	}
	if b := senden("geraten"); !strings.Contains(b, `"invalid_token"`) {
		t.Fatalf("falsches Token gegen abgelaufenes: erwartet invalid_token, bekommen %s", b)
	}
	if b := senden("das-richtige-token"); !strings.Contains(b, `"token_expired"`) {
		t.Fatalf("richtiges, abgelaufenes Token: erwartet token_expired, bekommen %s", b)
	}
	if u, _ := s.LoadUser("verifynutzer"); u.EmailVerifiedAt != nil {
		t.Fatal("ein abgelaufenes Token darf nichts bestaetigen")
	}
}

// AC-29: Passkey-Anmeldestart — unbekanntes Konto und Konto ohne Passkey
// antworten byte-gleich.
func TestPasskeyStart_UnbekanntUndOhnePasskeyGleichfoermig(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "ohnepasskey", Email: "op@beispiel.de", CreatedAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	wa, err := webauthn.New(&webauthn.Config{RPID: "localhost", RPDisplayName: "x", RPOrigins: []string{"http://localhost:5173"}})
	if err != nil {
		t.Fatal(err)
	}
	h := PasskeyLoginBeginHandler(s, wa, NewChallengeStore())
	antwort := func(kennung string) (int, string) {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/passkey/login/begin",
			strings.NewReader(`{"username":"`+kennung+`"}`)))
		return w.Code, w.Body.String()
	}
	c1, b1 := antwort("gibtsnicht")
	c2, b2 := antwort("ohnepasskey")
	c3, b3 := antwort("op@beispiel.de")
	c4, b4 := antwort("niemand@beispiel.de")
	if c1 != c2 || b1 != b2 || c3 != c4 || b3 != b4 || c1 != c3 || b1 != b3 {
		t.Fatalf("Antworten unterscheiden sich:\n%d %s\n%d %s\n%d %s\n%d %s", c1, b1, c2, b2, c3, b3, c4, b4)
	}
}
