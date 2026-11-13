package handler

// Issue #2961 (GA2, ADR-0115): unbestaetigte Konten.
// (a) Eine Registrierung fuer eine Adresse, die nur ein UNBESTAETIGTES Konto
//     haelt, ersetzt dieses Konto vollstaendig; ein bestaetigtes Konto bleibt
//     "Adresse vergeben".
// (b) Der Reaper loescht unbestaetigte Konten, deren Bestaetigungstoken seit
//     mehr als 24 Stunden abgelaufen ist — nie Bestandskonten von vor der
//     Bestaetigungspflicht, nie Testkonten, nie Konten ohne Token.

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
	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// unbestaetigteAnmeldung legt ein Konto an, wie es eine Registrierung
// hinterlaesst: unbestaetigt, mit Passwort, Passkey und Bestaetigungstoken.
func unbestaetigteAnmeldung(t *testing.T, s *store.Store, id, adresse string, angelegt, tokenAblauf time.Time) {
	t.Helper()
	h, _ := bcrypt.GenerateFromPassword([]byte("fremdes-pw-123"), bcrypt.MinCost)
	if err := s.SaveUser(model.User{ID: id, Email: adresse, MailTo: adresse, PasswordHash: string(h),
		PasskeyCredentials: []model.WebAuthnCredential{{ID: []byte("pk-" + id)}}, CreatedAt: angelegt}); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveVerificationToken(id, model.EmailVerificationToken{TokenHash: "x", ExpiresAt: tokenAblauf, Address: adresse}); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(s.UserDir(id), "trips.json"), []byte(`[]`), 0o600); err != nil {
		t.Fatal(err)
	}
}

func registrieren(s *store.Store, adresse, passwort string) *httptest.ResponseRecorder {
	w := httptest.NewRecorder()
	RegisterHandler(s, bcrypt.MinCost, config.Config{}).ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/register",
		strings.NewReader(`{"password":"`+passwort+`","email":"`+adresse+`"}`)))
	return w
}

func TestRegistrierung_ErsetztUnbestaetigtesKonto(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now()
	unbestaetigteAnmeldung(t, s, "u-vorweg", "opfer@beispiel.de", jetzt, jetzt.Add(24*time.Hour))
	unbestaetigteAnmeldung(t, s, "u-fremd", "andere@beispiel.de", jetzt, jetzt.Add(24*time.Hour))

	w := registrieren(s, " Opfer@Beispiel.de ", "eigenes-pw-123")
	if w.Code != http.StatusCreated {
		t.Fatalf("Registrierung ueber unbestaetigtes Konto: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	var neu struct {
		ID string `json:"id"`
	}
	_ = json.Unmarshal(w.Body.Bytes(), &neu)
	if neu.ID == "" || neu.ID == "u-vorweg" {
		t.Fatalf("neues Konto erwartet, bekommen %q", neu.ID)
	}
	if s.UserExists("u-vorweg") {
		t.Error("das unbestaetigte Konto muss samt Ordner (Zugangsdaten, Passkeys, Daten) entfernt sein")
	}
	u, _ := s.LoadUser(neu.ID)
	if u == nil || u.Email != "opfer@beispiel.de" || len(u.PasskeyCredentials) != 0 ||
		bcrypt.CompareHashAndPassword([]byte(u.PasswordHash), []byte("eigenes-pw-123")) != nil {
		t.Fatalf("neues Konto mit neuen Zugangsdaten erwartet: %+v", u)
	}
	if tok, _ := s.LoadVerificationToken(neu.ID); tok == nil || tok.Address != "opfer@beispiel.de" {
		t.Errorf("neues Bestaetigungstoken erwartet: %+v", tok)
	}
	if !s.UserExists("u-fremd") {
		t.Error("ein unbeteiligtes unbestaetigtes Konto darf nicht entfernt werden")
	}
}

func TestRegistrierung_BestaetigtesKontoBleibtVergeben(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now().UTC()
	if err := s.SaveUser(model.User{ID: "u-echt", Email: "echt@beispiel.de", CreatedAt: jetzt, EmailVerifiedAt: &jetzt}); err != nil {
		t.Fatal(err)
	}
	if w := registrieren(s, "echt@beispiel.de", "eigenes-pw-123"); w.Code != http.StatusConflict {
		t.Fatalf("bestaetigtes Konto: erwartet 409, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !s.UserExists("u-echt") {
		t.Fatal("bestaetigtes Konto darf nie entfernt werden")
	}
}

func TestRegistrierung_AltbestandOhneBestaetigungspflichtBleibt(t *testing.T) {
	s := newTestStore(t)
	alt := store.BestaetigungspflichtSeit.Add(-24 * time.Hour)
	unbestaetigteAnmeldung(t, s, "u-alt", "alt@beispiel.de", alt, time.Now().Add(time.Hour))
	if err := s.SaveUser(model.User{ID: "u-ohnetoken", Email: "ohnetoken@beispiel.de", CreatedAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	for _, adr := range []string{"alt@beispiel.de", "ohnetoken@beispiel.de"} {
		if w := registrieren(s, adr, "eigenes-pw-123"); w.Code != http.StatusConflict {
			t.Errorf("%s: Konto ausserhalb der Bestaetigungspflicht muss bleiben (409), bekommen %d", adr, w.Code)
		}
	}
	if !s.UserExists("u-alt") || !s.UserExists("u-ohnetoken") {
		t.Fatal("Bestandskonten duerfen nicht entfernt werden")
	}
}

func TestReaper_LoeschtNurAbgelaufeneUnbestaetigteAnmeldungen(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now()
	vor25h := jetzt.Add(-25 * time.Hour)
	unbestaetigteAnmeldung(t, s, "u-reif-a", "reif-a@beispiel.de", jetzt.Add(-49*time.Hour), vor25h)
	unbestaetigteAnmeldung(t, s, "u-reif-b", "reif-b@beispiel.de", jetzt.Add(-49*time.Hour), vor25h)
	unbestaetigteAnmeldung(t, s, "u-frisch", "frisch@beispiel.de", jetzt.Add(-47*time.Hour), jetzt.Add(-23*time.Hour))
	unbestaetigteAnmeldung(t, s, "u-altbestand", "altbestand@beispiel.de", store.BestaetigungspflichtSeit.Add(-time.Hour), vor25h)
	unbestaetigteAnmeldung(t, s, "u-test", "test@beispiel.de", jetzt.Add(-49*time.Hour), vor25h)
	if _, err := s.UpdateUser("u-test", func(u *model.User) error { u.IsTestUser = true; return nil }); err != nil {
		t.Fatal(err)
	}
	bestaetigt := jetzt.UTC()
	unbestaetigteAnmeldung(t, s, "u-bestaetigt", "bestaetigt@beispiel.de", jetzt.Add(-49*time.Hour), vor25h)
	if _, err := s.UpdateUser("u-bestaetigt", func(u *model.User) error { u.EmailVerifiedAt = &bestaetigt; return nil }); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveUser(model.User{ID: "u-ohnetoken", Email: "ohne@beispiel.de", CreatedAt: jetzt.Add(-72 * time.Hour)}); err != nil {
		t.Fatal(err)
	}

	if n := reapUnconfirmedAccounts(s, jetzt); n != 2 {
		t.Errorf("erwartet 2 geloeschte Konten, bekommen %d", n)
	}
	for _, weg := range []string{"u-reif-a", "u-reif-b"} {
		if s.UserExists(weg) {
			t.Errorf("%s muss samt Ordner geloescht sein", weg)
		}
	}
	for _, bleibt := range []string{"u-frisch", "u-altbestand", "u-test", "u-bestaetigt", "u-ohnetoken"} {
		if !s.UserExists(bleibt) {
			t.Errorf("%s darf nicht geloescht werden", bleibt)
		}
	}
}

// GA2d: die Bestaetigungsmail sagt klar, dass sie zu ignorieren ist, wer sich
// nicht selbst registriert hat — in beiden Sprachen.
func TestBestaetigungsmail_NenntFremdausgeloesteRegistrierung(t *testing.T) {
	for lang, erwartet := range map[string]string{
		"de": "nicht selbst bei Gregor 20 registriert",
		"en": "did not sign up for Gregor 20 yourself",
	} {
		m := mail.BuildVerificationMail(i18n.Parse(lang), "https://gz.beispiel.de", "u-x", "tok")
		if !strings.Contains(m.PlainBody, erwartet) || !strings.Contains(m.HTMLBody, "Gregor 20") {
			t.Errorf("%s: Hinweis fehlt in der Bestaetigungsmail: %q", lang, m.PlainBody)
		}
	}
}
