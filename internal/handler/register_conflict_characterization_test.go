package handler

// Issue #2163 Scheibe 1, AC-1 — Charakterisierung (heute gruen, bewusst).
// Spec: docs/specs/modules/auth_haertung_go_2163.md, Abschnitt
// "Bewusst nicht geaendert: Registrierung verraet vergebene Namen und
// E-Mail-Adressen".
//
// Die Registrierungs-Enumeration bleibt als dokumentiertes Restrisiko
// bestehen (#2147 B1). Diese Tests bewachen, dass die 409-Antworten von Konto-
// und Passkey-Registrierung byte-gleich bleiben: Status, Fehlercode und Body
// (Konto-Registrierung schreibt per w.Write ohne Zeilenumbruch, die Passkey-
// Handler per writeJSONError/json.Encoder MIT abschliessendem "\n").
//
// Der zweite Teil von AC-1 (Kommentar an den 409-Stellen) ist eine
// Quelltext-Eigenschaft und wird nach Test-Politik NICHT per Dateiinhalt
// geprueft, sondern im Review.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler/passkeytest"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func seedRegisterConflictUser(t *testing.T, s *store.Store) {
	t.Helper()
	if err := s.SaveUser(model.User{ID: "vergeben", PasswordHash: "x",
		Email: "belegt@example.com", MailTo: "belegt@example.com", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
}

func TestRegisterKonto_VergebenerNameUndEmail_409Unveraendert_AC1(t *testing.T) {
	faelle := []struct {
		name     string
		body     string
		wantBody string
	}{
		// Issue #2194: feste Kennung (und damit Kennungskonflikt) nur fuer Testkonten.
		{"Name vergeben", `{"username":"vergeben","password":"geheim123","email":"neu@example.com","is_test_user":true}`, "{\"code\":\"user_already_exists\",\"detail\":\"Dieser Benutzername ist bereits vergeben.\",\"error\":\"user_already_exists\",\"message\":\"Dieser Benutzername ist bereits vergeben.\"}\n"},
		{"E-Mail vergeben", `{"username":"neuername","password":"geheim123","email":"belegt@example.com"}`, "{\"code\":\"email_taken\",\"detail\":\"Diese E-Mail-Adresse wird bereits verwendet.\",\"error\":\"email_taken\",\"message\":\"Diese E-Mail-Adresse wird bereits verwendet.\"}\n"},
	}
	for _, f := range faelle {
		f := f
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			seedRegisterConflictUser(t, s)
			h := RegisterHandler(s, bcrypt.MinCost, config.Config{PublicHost: "https://test.example.com"})
			req := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(f.body))
			w := httptest.NewRecorder()
			h.ServeHTTP(w, req)
			if w.Code != http.StatusConflict {
				t.Fatalf("AC-1 %s: erwartet 409, bekommen %d: %s", f.name, w.Code, w.Body.String())
			}
			if got := w.Body.String(); got != f.wantBody {
				t.Errorf("AC-1 %s: Body erwartet %q, bekommen %q", f.name, f.wantBody, got)
			}
			if ct := w.Header().Get("Content-Type"); ct != "application/json" {
				t.Errorf("AC-1 %s: Content-Type erwartet application/json, bekommen %q", f.name, ct)
			}
			if s.UserExists("neuername") {
				t.Errorf("AC-1 %s: bei 409 darf kein Konto entstehen", f.name)
			}
			// Issue #2194: der Name benennt kein Konto mehr — nur das geseedete
			// Konto "vergeben" darf existieren.
			if n := kontenAnzahl(t, s); n != 1 {
				t.Errorf("AC-1 %s: bei 409 darf kein Konto entstehen, Konten: %d statt 1", f.name, n)
			}
		})
	}
}

func TestRegisterPasskeyBegin_VergebenerNameUndEmail_409Unveraendert_AC1(t *testing.T) {
	const wantNameBody = "{\"code\":\"user_already_exists\",\"detail\":\"Dieser Benutzername ist bereits vergeben.\",\"error\":\"user_already_exists\",\"message\":\"Dieser Benutzername ist bereits vergeben.\"}\n"
	const wantEmailBody = "{\"code\":\"email_taken\",\"detail\":\"Diese E-Mail-Adresse wird bereits verwendet.\",\"error\":\"email_taken\",\"message\":\"Diese E-Mail-Adresse wird bereits verwendet.\"}\n"

	pruefe := func(t *testing.T, fall string, w *httptest.ResponseRecorder, wantBody string) {
		t.Helper()
		if w.Code != http.StatusConflict {
			t.Fatalf("AC-1 Passkey %s: erwartet 409, bekommen %d: %s", fall, w.Code, w.Body.String())
		}
		if got := w.Body.String(); got != wantBody {
			t.Errorf("AC-1 Passkey %s: Body erwartet %q, bekommen %q", fall, wantBody, got)
		}
		if ct := w.Header().Get("Content-Type"); ct != "application/json" {
			t.Errorf("AC-1 Passkey %s: Content-Type erwartet application/json, bekommen %q", fall, ct)
		}
	}

	// Issue #2194 (AC-13): Begin ignoriert den Body-username und erzeugt die
	// ID selbst. Der Kennungskonflikt ist nur noch im Finish erreichbar — wenn
	// genau diese ID zwischen Begin und Finish belegt wird. Der 409-Body muss
	// dort byte-gleich bleiben.
	t.Run("Name vergeben", func(t *testing.T) {
		s := newTestStore(t)
		seedRegisterConflictUser(t, s)
		rpID, origin := "localhost", "http://localhost"
		wa := passkeytest.NewWebAuthn(t, rpID, origin)
		cs := NewChallengeStore()
		bw := httptest.NewRecorder()
		PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(bw, httptest.NewRequest(http.MethodPost,
			"/api/auth/passkey/register/public/begin", strings.NewReader(`{"username":"vergeben","email":"neu@example.com"}`)))
		if bw.Code != http.StatusOK {
			t.Fatalf("Begin erwartet 200, bekommen %d: %s", bw.Code, bw.Body.String())
		}
		var beginResp struct {
			PublicKey struct {
				Challenge string `json:"challenge"`
			} `json:"publicKey"`
		}
		if err := json.Unmarshal(bw.Body.Bytes(), &beginResp); err != nil {
			t.Fatalf("Begin-Antwort: %v", err)
		}
		belegt := passkeyBeginKontoID(t, bw.Body.Bytes())
		if err := s.SaveUser(model.User{ID: belegt, PasswordHash: "x", CreatedAt: time.Now()}); err != nil {
			t.Fatalf("ID vorab belegen: %v", err)
		}
		auth := passkeytest.NewAuthenticator(t, rpID, origin)
		fw := httptest.NewRecorder()
		PasskeyRegisterPublicFinishHandler(s, wa, cs, "test-secret-32-chars-long-enough", config.Config{}).ServeHTTP(fw,
			httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/finish",
				bytes.NewReader(auth.MakeAttestationResponse(t, beginResp.PublicKey.Challenge))))
		pruefe(t, "Name vergeben", fw, wantNameBody)
	})

	t.Run("E-Mail vergeben", func(t *testing.T) {
		s := newTestStore(t)
		seedRegisterConflictUser(t, s)
		wa := passkeytest.NewWebAuthn(t, "localhost", "http://localhost")
		h := PasskeyRegisterPublicBeginHandler(s, wa, NewChallengeStore())
		req := httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/begin",
			strings.NewReader(`{"username":"neuername","email":"belegt@example.com"}`))
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		pruefe(t, "E-Mail vergeben", w, wantEmailBody)
	})
}
