package handler

// Issue #2961 (GA2/GA3, ADR-0115): Passwort-Reset entfernt auf Wunsch (Vorgabe:
// ja) alle anderen Zugangswege — Passkeys und Google-Verknuepfung — und
// leert die Sitzungen. Bei einem UNBESTAETIGTEN Konto immer, unabhaengig von
// der Auswahl. Die Hinweis-Mail nennt, was entfernt wurde.

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func kontoMitZugangswegen(t *testing.T, s *store.Store, id, adresse string, bestaetigt bool) string {
	t.Helper()
	u := model.User{
		ID: id, Email: adresse, CreatedAt: time.Now(), PasswordHash: "alt",
		PasskeyCredentials: []model.WebAuthnCredential{{ID: []byte("pk1-" + id)}, {ID: []byte("pk2-" + id)}},
		OAuthProvider:      "google", OAuthSub: "sub-" + id,
	}
	if bestaetigt {
		jetzt := time.Now().UTC()
		u.EmailVerifiedAt = &jetzt
	}
	if err := s.SaveUser(u); err != nil {
		t.Fatal(err)
	}
	if err := s.AddSession(id, "sitzung-"+id); err != nil {
		t.Fatal(err)
	}
	token := "reset-token-" + id
	h, _ := bcrypt.GenerateFromPassword([]byte(token), bcrypt.MinCost)
	if err := s.SaveResetToken(id, model.PasswordResetToken{TokenHash: string(h), ExpiresAt: time.Now().Add(time.Hour)}); err != nil {
		t.Fatal(err)
	}
	return token
}

func zuruecksetzen(s *store.Store, id, token, zusatz string) *httptest.ResponseRecorder {
	body := `{"username":"` + id + `","token":"` + token + `","new_password":"ganz-neues-pw"` + zusatz + `}`
	w := httptest.NewRecorder()
	ResetPasswordHandler(s, bcrypt.MinCost).ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/reset-password", strings.NewReader(body)))
	return w
}

func TestReset_EntferntStandardmaessigAndereZugangswege(t *testing.T) {
	post := hinweisPostausgang(t, nil)
	s := newTestStore(t)
	tokenA := kontoMitZugangswegen(t, s, "reset-zw-a", "zw-a@beispiel.de", true)
	kontoMitZugangswegen(t, s, "reset-zw-b", "zw-b@beispiel.de", true)

	if w := zuruecksetzen(s, "reset-zw-a", tokenA, ""); w.Code != http.StatusOK {
		t.Fatalf("Reset: %d %s", w.Code, w.Body.String())
	}
	a, _ := s.LoadUser("reset-zw-a")
	if len(a.PasskeyCredentials) != 0 || a.OAuthSub != "" || a.OAuthProvider != "" {
		t.Errorf("Vorgabe: Passkeys und Google muessen entfernt sein: %d %q", len(a.PasskeyCredentials), a.OAuthSub)
	}
	if sess, _ := s.LoadSessions("reset-zw-a"); len(sess) != 0 {
		t.Errorf("Sitzungen muessen geleert sein: %v", sess)
	}
	b, _ := s.LoadUser("reset-zw-b")
	if len(b.PasskeyCredentials) != 2 || b.OAuthSub == "" {
		t.Errorf("Konto b darf nicht betroffen sein")
	}
	if sess, _ := s.LoadSessions("reset-zw-b"); len(sess) != 1 {
		t.Errorf("Sitzung von b muss bleiben: %v", sess)
	}

	mails := hinweiseAbwarten(post, 300*time.Millisecond)
	if len(mails) != 1 || mails[0].to != "zw-a@beispiel.de" {
		t.Fatalf("erwartet eine Hinweis-Mail an zw-a, bekommen %+v", mails)
	}
	if !strings.Contains(mails[0].msg.PlainBody, "Passkeys (2)") || !strings.Contains(mails[0].msg.PlainBody, "Google") {
		t.Errorf("Hinweis nennt das Entfernte nicht: %q", mails[0].msg.PlainBody)
	}
}

func TestReset_OhneAuswahlBleibenZugangswegeBeiBestaetigtemKonto(t *testing.T) {
	hinweisPostausgang(t, nil)
	s := newTestStore(t)
	token := kontoMitZugangswegen(t, s, "reset-zw-c", "zw-c@beispiel.de", true)
	if w := zuruecksetzen(s, "reset-zw-c", token, `,"remove_other_access":false`); w.Code != http.StatusOK {
		t.Fatalf("Reset: %d %s", w.Code, w.Body.String())
	}
	c, _ := s.LoadUser("reset-zw-c")
	if len(c.PasskeyCredentials) != 2 || c.OAuthSub != "sub-reset-zw-c" {
		t.Errorf("abgewaehlt: Passkeys und Google bleiben, bekommen %d %q", len(c.PasskeyCredentials), c.OAuthSub)
	}
	if bcrypt.CompareHashAndPassword([]byte(c.PasswordHash), []byte("ganz-neues-pw")) != nil {
		t.Error("neues Passwort nicht gesetzt")
	}
	if sess, _ := s.LoadSessions("reset-zw-c"); len(sess) != 0 {
		t.Errorf("Sitzungen werden immer geleert: %v", sess)
	}
}

func TestReset_UnbestaetigtesKontoVerliertImmerAndereZugangswege(t *testing.T) {
	hinweisPostausgang(t, nil)
	s := newTestStore(t)
	token := kontoMitZugangswegen(t, s, "reset-zw-d", "zw-d@beispiel.de", false)
	if w := zuruecksetzen(s, "reset-zw-d", token, `,"remove_other_access":false`); w.Code != http.StatusOK {
		t.Fatalf("Reset: %d %s", w.Code, w.Body.String())
	}
	d, _ := s.LoadUser("reset-zw-d")
	if len(d.PasskeyCredentials) != 0 || d.OAuthSub != "" {
		t.Errorf("unbestaetigt: andere Zugangswege muessen trotz Abwahl weg sein: %d %q", len(d.PasskeyCredentials), d.OAuthSub)
	}
}
