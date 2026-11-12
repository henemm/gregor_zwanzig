package handler_test

// TDD RED — Issue #2194 (Epic #2138): E-Mail-Adresse als Login-Identifier.
// Spec: docs/specs/modules/email_login_identifier.md — AC-1, AC-2, AC-4, AC-5,
// AC-6, AC-15 und die @-Weiche des Staging-Testwegs (staging_verify_token).
//
// Alle Nachweise laufen gegen den ECHTEN Produktions-Router
// (neueVerifyUmgebung2304 aus verify_resend_test.go): Rate-Limiter,
// AuthMiddleware und Routen-Registrierung sind mit im Bild. Jeder Test baut
// eine eigene Umgebung — die IP-Limiter gelten je Router-Instanz.
//
// Der Rumpf bleibt {"username": <Kennung>, "password": ...}: die Kennung ist
// entweder eine Konto-ID (ohne "@") oder eine E-Mail-Adresse (mit "@").
//
// Benutzt NUR bestehende Symbole (kein undefined:), damit der Paket-Testbuild
// heute kompiliert und die Tests am VERHALTEN scheitern.
//
// Kein Mock: echte bcrypt-Hashes, echter Store auf t.TempDir().

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
)

const profilPfad2194 = "/api/auth/profile"

type kontoSpec2194 struct {
	id, email, mailTo, passwort string
	bestaetigt, testkonto       bool
}

func (e *verifyUmgebung2304) konto2194(t *testing.T, k kontoSpec2194) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(k.passwort), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt %q: %v", k.id, err)
	}
	u := model.User{
		ID: k.id, Email: k.email, MailTo: k.mailTo, DisplayName: "Konto " + k.id,
		PasswordHash: string(hash), CreatedAt: time.Now(), IsTestUser: k.testkonto,
	}
	if u.MailTo == "" {
		u.MailTo = k.email
	}
	if k.bestaetigt {
		jetzt := time.Now().UTC()
		u.EmailVerifiedAt = &jetzt
	}
	if err := e.store.SaveUser(u); err != nil {
		t.Fatalf("SaveUser %q: %v", k.id, err)
	}
	if err := e.store.ProvisionUserDirs(k.id); err != nil {
		t.Fatalf("ProvisionUserDirs %q: %v", k.id, err)
	}
}

func (e *verifyUmgebung2304) login2194(t *testing.T, kennung, passwort string) *httptest.ResponseRecorder {
	t.Helper()
	rumpf, _ := json.Marshal(map[string]string{"username": kennung, "password": passwort})
	return e.post(t, loginPfad2271, string(rumpf), nil)
}

func antwortID2194(t *testing.T, w *httptest.ResponseRecorder) string {
	t.Helper()
	var a struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &a); err != nil {
		t.Fatalf("Antwort ist kein JSON (%q): %v", w.Body.String(), err)
	}
	return a.ID
}

// sitzungFuer2194 verlangt ein gz_session-Cookie, das an uid gebunden ist
// (Format {userId}.{sessionId}.{ts}.{sig}).
func sitzungFuer2194(t *testing.T, w *httptest.ResponseRecorder, uid, fall string) *http.Cookie {
	t.Helper()
	c := sitzungsmerkmal2271(w)
	if c == nil {
		t.Fatalf("%s: kein gz_session-Cookie gesetzt", fall)
	}
	if !strings.HasPrefix(c.Value, uid+".") {
		t.Fatalf("%s: Cookie muss an Konto %q gebunden sein, Wert beginnt mit %q", fall, uid,
			strings.SplitN(c.Value, ".", 2)[0])
	}
	return c
}

func profilID2194(t *testing.T, e *verifyUmgebung2304, c *http.Cookie) (string, string) {
	t.Helper()
	w := anfrage2271(t, e, http.MethodGet, profilPfad2194, "", c)
	if w.Code != http.StatusOK {
		t.Fatalf("GET %s: erwartet 200, bekommen %d: %s", profilPfad2194, w.Code, w.Body.String())
	}
	var p struct {
		ID    string `json:"id"`
		Email string `json:"email"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &p); err != nil {
		t.Fatalf("Profil-Antwort kein JSON: %v", err)
	}
	return p.ID, p.Email
}

// AC-1: Login per E-Mail (andere Schreibweise, Rand-Leerzeichen) => 200,
// Antwort {"id": <Konto-ID>} statt der eingegebenen Adresse, Sitzung gehoert
// dem aufgeloesten Konto.
func TestLoginPerEmailLiefertKontoID_AC1_2194(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	e.konto2194(t, kontoSpec2194{id: "nora2194", email: "nora@beispiel.de", passwort: "nora-passwort-1", bestaetigt: true})

	w := e.login2194(t, "  Nora@Beispiel.DE ", "nora-passwort-1")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-1: Login per E-Mail erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := antwortID2194(t, w); got != "nora2194" {
		t.Errorf("AC-1: Antwort-id muss die Konto-ID %q sein, nicht die Eingabe; bekommen %q", "nora2194", got)
	}
	c := sitzungFuer2194(t, w, "nora2194", "AC-1")
	if id, _ := profilID2194(t, e, c); id != "nora2194" {
		t.Errorf("AC-1: die Sitzung muss das Profil von nora2194 oeffnen, bekommen id=%q", id)
	}
}

// AC-2 — Wächter, heute grün: der ID-Login bleibt unveraendert, auch fuer ein
// Konto ohne hinterlegte E-Mail-Adresse.
func TestLoginPerIDBleibtUnveraendert_AC2_2194(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	e.konto2194(t, kontoSpec2194{id: "alice2194", email: "alice@beispiel.de", passwort: "alice-passwort-1", bestaetigt: true})
	// Bestandskonto ohne email; das Gate (ADR-0066) prueft nur email_verified_at.
	e.konto2194(t, kontoSpec2194{id: "ohnemail2194", passwort: "ohne-passwort-1", bestaetigt: true})

	for _, k := range []struct{ id, pw string }{
		{"alice2194", "alice-passwort-1"},
		{"ohnemail2194", "ohne-passwort-1"},
	} {
		w := e.login2194(t, k.id, k.pw)
		if w.Code != http.StatusOK {
			t.Errorf("AC-2: ID-Login %q erwartet 200, bekommen %d: %s", k.id, w.Code, w.Body.String())
			continue
		}
		if got := antwortID2194(t, w); got != k.id {
			t.Errorf("AC-2: Antwort-id erwartet %q, bekommen %q", k.id, got)
		}
		sitzungFuer2194(t, w, k.id, "AC-2 "+k.id)
	}
}

// AC-4: ein Testkonto ist per E-Mail nicht auffindbar, per ID schon. Damit
// die 401 nicht nur deshalb entsteht, weil es den E-Mail-Pfad gar nicht gibt,
// traegt ein echtes Konto DIESELBE Adresse: der E-Mail-Login muss genau dieses
// echte Konto aufloesen (Testkonto zaehlt nicht als zweiter Treffer).
func TestTestkontoNurPerIDAnmeldbar_AC4_2194(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	const adresse = "geteilt2194@beispiel.de"
	e.konto2194(t, kontoSpec2194{id: "prueflauf2194", email: adresse, passwort: "test-passwort-1", bestaetigt: true, testkonto: true})
	e.konto2194(t, kontoSpec2194{id: "echt2194", email: adresse, passwort: "echt-passwort-1", bestaetigt: true})

	// Testkonto per E-Mail mit seinem richtigen Passwort => 401.
	w := e.login2194(t, adresse, "test-passwort-1")
	if w.Code != http.StatusUnauthorized {
		t.Errorf("AC-4: Testkonto per E-Mail erwartet 401, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := strings.TrimSpace(w.Body.String()); got != abweisungsKoerper2271 {
		t.Errorf("AC-4: erwartet invalid_credentials-Koerper, bekommen %q", got)
	}
	if sitzungsmerkmal2271(w) != nil {
		t.Errorf("AC-4: Testkonto per E-Mail darf keine Sitzung bekommen")
	}

	// Testkonto per ID => 200 (Wächter).
	w = e.login2194(t, "prueflauf2194", "test-passwort-1")
	if w.Code != http.StatusOK {
		t.Errorf("AC-4: Testkonto per ID erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	} else {
		sitzungFuer2194(t, w, "prueflauf2194", "AC-4 ID-Login")
	}

	// Das echte Konto mit derselben Adresse wird per E-Mail aufgeloest.
	w = e.login2194(t, adresse, "echt-passwort-1")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-4: echtes Konto mit derselben Adresse per E-Mail erwartet 200 "+
			"(das Testkonto zaehlt nicht als Treffer), bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := antwortID2194(t, w); got != "echt2194" {
		t.Errorf("AC-4: erwartet Konto echt2194, bekommen %q", got)
	}
	sitzungFuer2194(t, w, "echt2194", "AC-4 E-Mail-Login echtes Konto")
}

// AC-5: Lookup nur ueber email, nie ueber mail_to.
func TestLoginPerMailToFindetKeinKonto_AC5_2194(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	e.konto2194(t, kontoSpec2194{id: "carla2194", email: "a2194@x.de", mailTo: "b2194@x.de", passwort: "carla-passwort-1", bestaetigt: true})

	w := e.login2194(t, "b2194@x.de", "carla-passwort-1")
	if w.Code != http.StatusUnauthorized {
		t.Errorf("AC-5: Login mit mail_to-Adresse erwartet 401, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := strings.TrimSpace(w.Body.String()); got != abweisungsKoerper2271 {
		t.Errorf("AC-5: erwartet invalid_credentials-Koerper, bekommen %q", got)
	}

	w = e.login2194(t, "a2194@x.de", "carla-passwort-1")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-5: Login mit email-Adresse erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := antwortID2194(t, w); got != "carla2194" {
		t.Errorf("AC-5: erwartet Konto carla2194, bekommen %q", got)
	}
}

// AC-6: unbestaetigte Adresse — der E-Mail-Weg sperrt genauso wie der ID-Weg
// (ADR-0066): beide liefern 403 email_not_verified, zeichengleich, ohne Cookie.
// Die ID-Haelfte ist ein Wächter (heute grün).
func TestLoginPerEmailUnbestaetigtGesperrtWieID_AC6_2194(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	e.konto2194(t, kontoSpec2194{id: "ida2194", email: "ida@beispiel.de", passwort: "ida-passwort-1", bestaetigt: false})

	wID := e.login2194(t, "ida2194", "ida-passwort-1")
	if wID.Code != http.StatusForbidden || strings.TrimSpace(wID.Body.String()) != gateKoerper2271 {
		t.Errorf("AC-6 (Wächter): ID-Login unbestaetigt erwartet 403 %s, bekommen %d %q",
			gateKoerper2271, wID.Code, wID.Body.String())
	}

	wMail := e.login2194(t, "ida@beispiel.de", "ida-passwort-1")
	if wMail.Code != wID.Code {
		t.Errorf("AC-6: E-Mail-Login unbestaetigt muss denselben Status wie der ID-Login liefern (%d), bekommen %d: %s",
			wID.Code, wMail.Code, wMail.Body.String())
	}
	if wMail.Body.String() != wID.Body.String() {
		t.Errorf("AC-6: Koerper unterscheiden sich: ID %q, E-Mail %q", wID.Body.String(), wMail.Body.String())
	}
	if sitzungsmerkmal2271(wMail) != nil {
		t.Errorf("AC-6: der E-Mail-Weg darf fuer ein unbestaetigtes Konto keine Sitzung ausstellen")
	}
}

// AC-15: zwei Nutzer, A per E-Mail, B per ID; jede Sitzung sieht nur die
// eigenen Daten; eine fremde Adresse loest nie das andere Konto auf.
func TestZweiNutzerEmailUndIDLoginGetrennt_AC15_2194(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	e.konto2194(t, kontoSpec2194{id: "anja2194", email: "anja@beispiel.de", passwort: "anja-passwort-1", bestaetigt: true})
	e.konto2194(t, kontoSpec2194{id: "bodo2194", email: "bodo@beispiel.de", passwort: "bodo-passwort-1", bestaetigt: true})

	wA := e.login2194(t, "anja@beispiel.de", "anja-passwort-1")
	if wA.Code != http.StatusOK {
		t.Fatalf("AC-15: A per E-Mail erwartet 200, bekommen %d: %s", wA.Code, wA.Body.String())
	}
	cA := sitzungFuer2194(t, wA, "anja2194", "AC-15 A")

	wB := e.login2194(t, "bodo2194", "bodo-passwort-1")
	if wB.Code != http.StatusOK {
		t.Fatalf("AC-15: B per ID erwartet 200, bekommen %d: %s", wB.Code, wB.Body.String())
	}
	cB := sitzungFuer2194(t, wB, "bodo2194", "AC-15 B")

	if id, mail := profilID2194(t, e, cA); id != "anja2194" || mail != "anja@beispiel.de" {
		t.Errorf("AC-15: Sitzung A muss nur A sehen, bekommen id=%q email=%q", id, mail)
	}
	if id, mail := profilID2194(t, e, cB); id != "bodo2194" || mail != "bodo@beispiel.de" {
		t.Errorf("AC-15: Sitzung B muss nur B sehen, bekommen id=%q email=%q", id, mail)
	}

	// Fremde Adresse + eigenes Passwort: A's Adresse mit B's Passwort => 401.
	w := e.login2194(t, "anja@beispiel.de", "bodo-passwort-1")
	if w.Code != http.StatusUnauthorized || sitzungsmerkmal2271(w) != nil {
		t.Errorf("AC-15: A's Adresse mit B's Passwort muss 401 ohne Sitzung liefern, bekommen %d", w.Code)
	}
	// B's Adresse loest B auf, nie A.
	w = e.login2194(t, "bodo@beispiel.de", "bodo-passwort-1")
	if w.Code != http.StatusOK {
		t.Fatalf("AC-15: B per E-Mail erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := antwortID2194(t, w); got != "bodo2194" {
		t.Errorf("AC-15: B's Adresse muss B aufloesen, bekommen %q", got)
	}
}

// @-Weiche des Staging-Testwegs (Spec "Weiche am @", staging_verify_token):
// eine E-Mail-Kennung loest das Konto auf; das Token liegt beim Konto.
func TestStagingTokenwegPerEmail_2194(t *testing.T) {
	t.Setenv("GZ_ENV", "staging")
	// Issue #2961: Testweg nur fuer Admin/Betreiber/Testkonten. Hanna darf kein
	// Testkonto sein (die E-Mail-Weiche loest Testkonten nicht auf, ADR-0105),
	// deshalb ist sie hier das Betreiber-Konto (GZ_AUTH_USER).
	t.Setenv("GZ_AUTH_USER", "hanna2194")
	e := neueVerifyUmgebung2304(t)
	e.konto2194(t, kontoSpec2194{id: "hanna2194", email: "hanna@beispiel.de", passwort: "hanna-passwort-1"})

	w := e.post(t, stagingTokenPfad2304, `{"username":"Hanna@Beispiel.de"}`, e.anmeldeCookie(t, "hanna2194"))
	if w.Code != http.StatusOK {
		t.Fatalf("Staging-Testweg per E-Mail: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if tok := tokenAusAntwort(t, w.Body.Bytes()); tok == "" {
		t.Fatal("Staging-Testweg per E-Mail: kein Token in der Antwort")
	}
	if tok, _ := e.store.LoadVerificationToken("hanna2194"); tok == nil {
		t.Error("Staging-Testweg per E-Mail: das Token muss beim aufgeloesten Konto hanna2194 liegen")
	}
}
