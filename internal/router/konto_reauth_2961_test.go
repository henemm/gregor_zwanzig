package router

// Issue #2961 (GA3, ADR-0115): sicherheitsrelevante Kontoaenderungen verlangen
// einen frischen Nachweis (Passwort oder Code an die bisherige Adresse), der
// 10 Minuten fuer genau diese Sitzung gilt. Geprueft im verdrahteten Router —
// dort, wo die Sperre wirkt.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func bestaetigterNutzerMitPasswort(t *testing.T, s *store.Store, id string) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(routerPasswort), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt: %v", err)
	}
	jetzt := time.Now().UTC()
	kontoVollSchreiben(t, s, model.User{
		ID: id, Email: id + "@beispiel.de", PasswordHash: string(hash),
		CreatedAt: jetzt, EmailVerifiedAt: &jetzt,
	})
	if err := s.AddSession(id, sessionIDFor(id)); err != nil {
		t.Fatalf("AddSession %s: %v", id, err)
	}
}

// anfrageMitSitzung schickt eine Anfrage mit einer bestimmten Sitzungskennung.
func anfrageMitSitzung(r http.Handler, secret, method, pfad, body, userID, sessionID string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, pfad, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: authmw.SignSessionWithID(userID, sessionID, secret)})
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func fehlerCode(t *testing.T, w *httptest.ResponseRecorder) string {
	t.Helper()
	var body struct {
		Code string `json:"code"`
	}
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	return body.Code
}

func TestKontoaenderung_AdresswechselOhneNachweis_403(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "")
	bestaetigterNutzerMitPasswort(t, s, "anke")

	w := kontoAnfrage(r, secret, http.MethodPut, "/api/auth/profile", `{"mail_to":"neu-anke@beispiel.de"}`, "anke")
	if w.Code != http.StatusForbidden || fehlerCode(t, w) != "reauth_required" {
		t.Fatalf("Adresswechsel ohne Nachweis: erwartet 403 reauth_required, bekommen %d: %s", w.Code, w.Body.String())
	}
	if u, _ := s.LoadUser("anke"); u.PendingContactAddress != "" || u.MailTo != "" {
		t.Errorf("ohne Nachweis darf nichts geschrieben werden: pending=%q mail_to=%q", u.PendingContactAddress, u.MailTo)
	}
	w = kontoAnfrage(r, secret, http.MethodPut, "/api/auth/profile", `{"email":"login-neu@beispiel.de"}`, "anke")
	if w.Code != http.StatusForbidden || fehlerCode(t, w) != "reauth_required" {
		t.Fatalf("Kennungswechsel ohne Nachweis: erwartet 403 reauth_required, bekommen %d: %s", w.Code, w.Body.String())
	}
	// Angehaengte Daten hinter dem JSON-Objekt aendern nichts an der Pruefung.
	w = kontoAnfrage(r, secret, http.MethodPut, "/api/auth/profile", `{"mail_to":"neu-anke@beispiel.de"} {}`, "anke")
	if w.Code == http.StatusOK {
		t.Fatalf("Rumpf mit angehaengten Daten darf den Nachweis nicht umgehen: %d %s", w.Code, w.Body.String())
	}
	// Schluessel in anderer Schreibweise sind fuer Go-JSON dasselbe Feld.
	w = kontoAnfrage(r, secret, http.MethodPut, "/api/auth/profile", `{"MAIL_TO":"neu-anke@beispiel.de"}`, "anke")
	if w.Code != http.StatusForbidden || fehlerCode(t, w) != "reauth_required" {
		t.Fatalf("Schreibweise des Schluessels: erwartet 403 reauth_required, bekommen %d: %s", w.Code, w.Body.String())
	}
	if u, _ := s.LoadUser("anke"); u.PendingContactAddress != "" || u.MailTo != "" {
		t.Errorf("ohne Nachweis darf nichts geschrieben werden: pending=%q mail_to=%q", u.PendingContactAddress, u.MailTo)
	}
}

func TestKontoaenderung_ProfilOhneAdressaenderungBrauchtKeinenNachweis(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "")
	bestaetigterNutzerMitPasswort(t, s, "olga")
	// Die Konto-Seite schickt mail_to bei jedem Speichern mit — unveraendert
	// (auch in anderer Schreibweise) ist das keine Adressaenderung.
	w := kontoAnfrage(r, secret, http.MethodPut, "/api/auth/profile",
		`{"display_name":"Alice","mail_to":"","email":" OLGA@beispiel.de "}`, "olga")
	if w.Code != http.StatusOK {
		t.Fatalf("Profil ohne Adressaenderung: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

func TestKontoaenderung_NachweisGiltZehnMinutenFuerDieseSitzung(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "")
	bestaetigterNutzerMitPasswort(t, s, "alice")
	bestaetigterNutzerMitPasswort(t, s, "bob")
	if err := s.AddSession("alice", "zweites-geraet"); err != nil {
		t.Fatal(err)
	}

	if w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/reauth", `{"password":"falsch"}`, "alice"); w.Code != http.StatusForbidden || fehlerCode(t, w) != "wrong_password" {
		t.Fatalf("falsches Passwort: erwartet 403 wrong_password, bekommen %d: %s", w.Code, w.Body.String())
	}
	if w := kontoAnfrage(r, secret, http.MethodPut, "/api/auth/profile", `{"mail_to":"neu-alice@beispiel.de"}`, "alice"); w.Code != http.StatusForbidden {
		t.Fatalf("falsches Passwort darf keinen Nachweis ergeben, bekommen %d", w.Code)
	}

	w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/reauth", `{"password":"`+routerPasswort+`"}`, "alice")
	if w.Code != http.StatusOK {
		t.Fatalf("Nachweis mit Passwort: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), `"valid_until"`) {
		t.Errorf("Antwort nennt die Gueltigkeit nicht: %s", w.Body.String())
	}

	// Mehrere Aenderungen direkt hintereinander ohne erneute Abfrage.
	if w := kontoAnfrage(r, secret, http.MethodPut, "/api/auth/profile", `{"mail_to":"neu-alice@beispiel.de"}`, "alice"); w.Code != http.StatusOK {
		t.Fatalf("Adresswechsel mit Nachweis: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if w := kontoAnfrage(r, secret, http.MethodDelete, "/api/auth/passkey/credentials/AQID", "", "alice"); w.Code != http.StatusOK {
		t.Fatalf("Passkey entfernen mit Nachweis: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if u, _ := s.LoadUser("alice"); u.PendingContactAddress != "neu-alice@beispiel.de" {
		t.Errorf("Adresswechsel wurde nicht angenommen: pending=%q", u.PendingContactAddress)
	}

	// Andere Sitzung desselben Nutzers: kein Nachweis.
	w = anfrageMitSitzung(r, secret, http.MethodPut, "/api/auth/profile", `{"mail_to":"dritte@beispiel.de"}`, "alice", "zweites-geraet")
	if w.Code != http.StatusForbidden || fehlerCode(t, w) != "reauth_required" {
		t.Errorf("Nachweis gilt nur fuer die eigene Sitzung: erwartet 403, bekommen %d: %s", w.Code, w.Body.String())
	}
	// Anderer Nutzer: kein Nachweis.
	w = kontoAnfrage(r, secret, http.MethodPut, "/api/auth/profile", `{"mail_to":"neu-bob@beispiel.de"}`, "bob")
	if w.Code != http.StatusForbidden || fehlerCode(t, w) != "reauth_required" {
		t.Errorf("Nachweis von alice gilt nicht fuer bob: erwartet 403, bekommen %d: %s", w.Code, w.Body.String())
	}
	if u, _ := s.LoadUser("bob"); u.PendingContactAddress != "" {
		t.Errorf("bobs Konto darf nicht geaendert sein: pending=%q", u.PendingContactAddress)
	}
}

func TestKontoaenderung_PasskeyHinzufuegenUndEntfernenBrauchenNachweis(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "")
	bestaetigterNutzerMitPasswort(t, s, "pia")
	for _, a := range []struct{ method, pfad, body string }{
		{http.MethodPost, "/api/auth/passkey/register/begin", `{}`},
		{http.MethodPost, "/api/auth/passkey/register/finish", `{}`},
		{http.MethodDelete, "/api/auth/passkey/credentials/AQID", ""},
	} {
		w := kontoAnfrage(r, secret, a.method, a.pfad, a.body, "pia")
		if w.Code != http.StatusForbidden || fehlerCode(t, w) != "reauth_required" {
			t.Errorf("%s %s ohne Nachweis: erwartet 403 reauth_required, bekommen %d: %s", a.method, a.pfad, w.Code, w.Body.String())
		}
	}
	if w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/reauth", `{"password":"`+routerPasswort+`"}`, "pia"); w.Code != http.StatusOK {
		t.Fatalf("Nachweis: %d %s", w.Code, w.Body.String())
	}
	if w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/passkey/register/begin", `{}`, "pia"); w.Code != http.StatusOK {
		t.Errorf("Passkey-Anlage mit Nachweis: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

func TestKontoaenderung_NachweisEndpunkteBrauchenAnmeldung(t *testing.T) {
	r, _, secret, _ := adminTestRouter(t, "")
	for _, pfad := range []string{"/api/auth/reauth", "/api/auth/reauth/code"} {
		if w := kontoAnfrage(r, secret, http.MethodPost, pfad, `{"password":"x"}`, ""); w.Code != http.StatusUnauthorized {
			t.Errorf("%s ohne Cookie: erwartet 401, bekommen %d", pfad, w.Code)
		}
	}
}

// Eine frische Anmeldung ist selbst ein Nachweis: 10 Minuten lang braucht
// die NEUE Sitzung keinen weiteren; eine aeltere Sitzung desselben Nutzers
// gewinnt dadurch nichts.
func TestKontoaenderung_FrischeAnmeldungGiltAlsNachweis(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "")
	bestaetigterNutzerMitPasswort(t, s, "lena")

	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", strings.NewReader(`{"username":"lena","password":"`+routerPasswort+`"}`))
	req.Header.Set("Content-Type", "application/json")
	lw := httptest.NewRecorder()
	r.ServeHTTP(lw, req)
	if lw.Code != http.StatusOK {
		t.Fatalf("Login: %d %s", lw.Code, lw.Body.String())
	}
	var cookie *http.Cookie
	for _, c := range lw.Result().Cookies() {
		if c.Name == "gz_session" {
			cookie = c
		}
	}
	if cookie == nil {
		t.Fatal("kein Sitzungs-Cookie")
	}
	put := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(`{"mail_to":"neu-lena@beispiel.de"}`))
	put.Header.Set("Content-Type", "application/json")
	put.AddCookie(cookie)
	pw := httptest.NewRecorder()
	r.ServeHTTP(pw, put)
	if pw.Code != http.StatusOK {
		t.Fatalf("Adresswechsel direkt nach der Anmeldung: erwartet 200, bekommen %d: %s", pw.Code, pw.Body.String())
	}
	// Die vorher bestehende Sitzung (sess-lena) hat keinen Nachweis.
	w := kontoAnfrage(r, secret, http.MethodPut, "/api/auth/profile", `{"mail_to":"dritte-lena@beispiel.de"}`, "lena")
	if w.Code != http.StatusForbidden || fehlerCode(t, w) != "reauth_required" {
		t.Fatalf("aeltere Sitzung: erwartet 403 reauth_required, bekommen %d: %s", w.Code, w.Body.String())
	}
}
