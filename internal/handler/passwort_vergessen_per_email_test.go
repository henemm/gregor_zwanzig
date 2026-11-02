package handler

// TDD RED — Issue #2194 (Epic #2138), AC-7: "Passwort vergessen" mit einer
// E-Mail-Adresse. Spec: docs/specs/modules/email_login_identifier.md
//
// Bekannte, unbekannte und doppelt vergebene Adresse liefern dieselbe neutrale
// Antwort; NUR bei genau einem Treffer entsteht ein Reset-Token fuer das
// aufgeloeste Konto und geht die Mail mit Link ?user=<ID> raus.
//
// Heute sind die Antworten bereits gleich (jede "@"-Kennung faellt durch
// ValidUserID in den neutralen Zweig) — das RED liegt deshalb in der
// Positivhaelfte: Token und Mail fuer den Einzeltreffer. Gemessen wird
// deterministisch am Token (SaveResetToken laeuft synchron vor dem Versand)
// und an der bestehenden Versand-Naht sendResetMailFn (kein SMTP-Dial).
//
// Echter Handler, echter Store in t.TempDir(); nur bestehende Symbole.

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
)

type resetMail2194 struct {
	to  string
	msg mail.Mail
}

func TestPasswortVergessenPerEmail_NeutralUndNurEinzeltrefferBekommtMail_AC7_2194(t *testing.T) {
	s := newTestStore(t)
	for _, k := range []struct{ id, email string }{
		{"lena2194", "lena@beispiel.de"},
		{"mia2194", "doppelt2194@beispiel.de"},
		{"nils2194", "Doppelt2194@beispiel.de"},
	} {
		hash, _ := bcrypt.GenerateFromPassword([]byte("altes-passwort-1"), bcrypt.MinCost)
		if err := s.SaveUser(model.User{ID: k.id, Email: k.email, MailTo: k.email,
			PasswordHash: string(hash), CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %q: %v", k.id, err)
		}
	}

	versand := make(chan resetMail2194, 8)
	orig := sendResetMailFn
	sendResetMailFn = func(_, _ mail.MailConfig, to string, msg mail.Mail) error {
		versand <- resetMail2194{to: to, msg: msg}
		return nil
	}
	t.Cleanup(func() { sendResetMailFn = orig })

	cfg := config.Config{
		SMTPHost: "smtp.beispiel.invalid", SMTPPort: 587, SMTPUser: "u", SMTPPass: "p",
		SMTPFrom: "gregor_zwanzig@henemm.com", PublicHost: "https://example.com",
	}
	h := ForgotPasswordHandler(s, bcrypt.MinCost, cfg)
	rufe := func(kennung string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodPost, "/api/auth/forgot-password",
			strings.NewReader(`{"username":"`+kennung+`"}`))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w
	}

	wBekannt := rufe(" Lena@Beispiel.de ")
	wUnbekannt := rufe("niemand2194@beispiel.de")
	wDoppelt := rufe("doppelt2194@beispiel.de")

	for name, w := range map[string]*httptest.ResponseRecorder{
		"unbekannt": wUnbekannt, "doppelt": wDoppelt,
	} {
		if w.Code != wBekannt.Code || !bytes.Equal(w.Body.Bytes(), wBekannt.Body.Bytes()) {
			t.Errorf("AC-7: Antwort %s (%d %q) weicht von der bekannten (%d %q) ab",
				name, w.Code, w.Body.String(), wBekannt.Code, wBekannt.Body.String())
		}
	}
	if wBekannt.Code != http.StatusOK || wBekannt.Body.String() != wantForgotNeutralBod {
		t.Errorf("AC-7: neutrale Antwort erwartet 200 %s, bekommen %d %q",
			wantForgotNeutralBod, wBekannt.Code, wBekannt.Body.String())
	}

	// Positivhaelfte (RED heute): Token fuer das eindeutig aufgeloeste Konto.
	if tok, err := s.LoadResetToken("lena2194"); err != nil || tok == nil {
		t.Errorf("AC-7: fuer die bekannte Adresse muss ein Reset-Token beim Konto lena2194 liegen (err=%v)", err)
	}
	// Doppelt vergebene Adresse: fuer keines der beiden Konten ein Token.
	for _, id := range []string{"mia2194", "nils2194"} {
		if tok, _ := s.LoadResetToken(id); tok != nil {
			t.Errorf("AC-7: doppelt vergebene Adresse darf fuer %q kein Reset-Token erzeugen", id)
		}
	}

	select {
	case m := <-versand:
		if m.to != "lena@beispiel.de" {
			t.Errorf("AC-7: Reset-Mail muss an lena@beispiel.de gehen, ging an %q", m.to)
		}
		if !strings.Contains(m.msg.PlainBody, "/reset-password?user=lena2194&") {
			t.Errorf("AC-7: Reset-Link muss ?user=<ID> tragen (nicht die Adresse):\n%s", m.msg.PlainBody)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("AC-7: binnen 3s keine Reset-Mail fuer die bekannte Adresse beobachtet")
	}
	select {
	case m := <-versand:
		t.Errorf("AC-7: nur der Einzeltreffer bekommt eine Mail, zusaetzlich ging eine an %q", m.to)
	case <-time.After(300 * time.Millisecond):
	}
}
