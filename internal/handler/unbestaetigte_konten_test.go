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
// hinterlaesst: unbestaetigt, mit Passwort, Passkey, Bestaetigungstoken und
// leeren Standardverzeichnissen — ohne Nutzinhalte.
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
	if err := s.ProvisionUserDirs(id); err != nil {
		t.Fatal(err)
	}
}

// mitNutzinhalt legt eine Nutzdatei in den Kontoordner (hier einen Ort).
func mitNutzinhalt(t *testing.T, s *store.Store, id string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(s.UserDir(id), "locations", "ort.json"), []byte(`{"id":"ort"}`), 0o600); err != nil {
		t.Fatal(err)
	}
}

// ablageEintraege liefert die Namen in der Ablage (leer, wenn es sie nicht gibt).
func ablageEintraege(t *testing.T, s *store.Store) []string {
	t.Helper()
	e, err := os.ReadDir(s.AblagePfad())
	if err != nil && !os.IsNotExist(err) {
		t.Fatal(err)
	}
	var namen []string
	for _, x := range e {
		namen = append(namen, x.Name())
	}
	return namen
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
		t.Error("das unbestaetigte Konto muss samt Zugangsdaten und Passkeys aus users/ verschwunden sein")
	}
	if a := ablageEintraege(t, s); len(a) != 1 || !strings.HasPrefix(a[0], "u-vorweg-") {
		t.Errorf("der Ordner muss in die Ablage verschoben, nicht geloescht sein: %v", a)
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

	unbestaetigteAnmeldung(t, s, "u-reif-voll", "voll@beispiel.de", jetzt.Add(-49*time.Hour), vor25h)
	mitNutzinhalt(t, s, "u-reif-voll")

	if n := reapUnconfirmedAccounts(s, jetzt); n != 2 {
		t.Errorf("erwartet 2 verschobene Konten, bekommen %d", n)
	}
	for _, weg := range []string{"u-reif-a", "u-reif-b"} {
		if s.UserExists(weg) {
			t.Errorf("%s muss aus users/ verschwunden sein", weg)
		}
	}
	if a := ablageEintraege(t, s); len(a) != 2 {
		t.Errorf("beide reifen Konten muessen in der Ablage liegen: %v", a)
	}
	for _, bleibt := range []string{"u-frisch", "u-altbestand", "u-test", "u-bestaetigt", "u-ohnetoken", "u-reif-voll"} {
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

// Bestandsdaten bleiben erhalten: ein unbestaetigtes Konto MIT Nutzinhalt
// wird weder ersetzt noch geraeumt, und sein Ordner bleibt byte-gleich.
func TestUnbestaetigt_NichtLeererOrdnerBleibtUnangetastet(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now()
	unbestaetigteAnmeldung(t, s, "u-voll", "voll-reg@beispiel.de", jetzt.Add(-49*time.Hour), jetzt.Add(-25*time.Hour))
	mitNutzinhalt(t, s, "u-voll")

	if w := registrieren(s, "voll-reg@beispiel.de", "eigenes-pw-123"); w.Code != http.StatusConflict {
		t.Fatalf("nicht leeres Konto: Registrierung erwartet 409, bekommen %d: %s", w.Code, w.Body.String())
	}
	if n := reapUnconfirmedAccounts(s, jetzt); n != 0 {
		t.Fatalf("nicht leeres Konto darf der Reaper nicht anfassen, verschoben: %d", n)
	}
	if !s.UserExists("u-voll") || len(ablageEintraege(t, s)) != 0 {
		t.Fatal("nicht leeres Konto muss in users/ bleiben, Ablage leer")
	}
	if b, err := os.ReadFile(filepath.Join(s.UserDir("u-voll"), "locations", "ort.json")); err != nil || string(b) != `{"id":"ort"}` {
		t.Fatalf("Nutzinhalt veraendert: %q %v", b, err)
	}
}

// Die Ablage wird nach 30 Tagen (injizierte Uhr) endgueltig entfernt, vorher
// nicht; Zurueckschieben stellt das Konto wieder her; kein Leser sieht sie.
func TestAblage_DreissigTageZurueckholbarUndUnsichtbar(t *testing.T) {
	s := newTestStore(t)
	jetzt := time.Now()
	unbestaetigteAnmeldung(t, s, "u-ablage-a", "ablage-a@beispiel.de", jetzt.Add(-49*time.Hour), jetzt.Add(-25*time.Hour))
	unbestaetigteAnmeldung(t, s, "u-ablage-b", "ablage-b@beispiel.de", jetzt.Add(-49*time.Hour), jetzt.Add(-25*time.Hour))
	if n := reapUnconfirmedAccounts(s, jetzt); n != 2 {
		t.Fatalf("erwartet 2 verschobene Konten, bekommen %d", n)
	}

	// Unsichtbar fuer Nutzerliste und Adress-Eindeutigkeit.
	ids, _ := s.ListUserIDs()
	for _, id := range ids {
		if strings.HasPrefix(id, "u-ablage") || strings.HasPrefix(id, ".") {
			t.Errorf("Ablage taucht in der Nutzerliste auf: %v", ids)
		}
	}
	if taken, err := s.IsAddressTakenByOtherAccount("ablage-a@beispiel.de", ""); err != nil || taken {
		t.Errorf("Ablage darf keine Adresse halten: %v %v", taken, err)
	}

	// Zurueckholen: Ordner unter der Kennung nach users/ zurueckschieben.
	var quelle string
	for _, n := range ablageEintraege(t, s) {
		if strings.HasPrefix(n, "u-ablage-a-") {
			quelle = filepath.Join(s.AblagePfad(), n)
		}
	}
	if err := os.Rename(quelle, s.UserDir("u-ablage-a")); err != nil {
		t.Fatal(err)
	}
	if u, err := s.LoadUser("u-ablage-a"); err != nil || u == nil || u.Email != "ablage-a@beispiel.de" || u.PasswordHash == "" {
		t.Fatalf("zurueckgeschobenes Konto nicht wiederhergestellt: %+v %v", u, err)
	}
	// Ein zurueckgeholtes, weiter unbestaetigtes Konto wuerde der Reaper erneut
	// verschieben; hier bestaetigt der Inhaber danach seine Adresse.
	bestaetigt := jetzt.UTC()
	if _, err := s.UpdateUser("u-ablage-a", func(u *model.User) error { u.EmailVerifiedAt = &bestaetigt; return nil }); err != nil {
		t.Fatal(err)
	}

	// 29 Tage: bleibt; 31 Tage: endgueltig entfernt.
	if n, err := s.PurgeAblage(jetzt.Add(29 * 24 * time.Hour)); err != nil || n != 0 {
		t.Fatalf("vor 30 Tagen darf nichts entfernt werden: %d %v", n, err)
	}
	reapUnconfirmedAccounts(s, jetzt.Add(31*24*time.Hour))
	if a := ablageEintraege(t, s); len(a) != 0 {
		t.Fatalf("nach 30 Tagen muss die Ablage leer sein: %v", a)
	}
	if !s.UserExists("u-ablage-a") {
		t.Fatal("das zurueckgeholte Konto darf vom Aufraeumen nicht betroffen sein")
	}
}
