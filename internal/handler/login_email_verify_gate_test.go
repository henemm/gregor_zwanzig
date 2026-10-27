package handler_test

// TDD RED — Issue #2271 (S2 aus #2146/#2304, Epic #2138): Scharfschaltung des
// Login-Gates. Spec: docs/specs/modules/email_verify_scharfschaltung_2271.md —
// AC-1, AC-9, AC-10, AC-11.
//
// Alle vier Nachweise laufen gegen den ECHTEN Router (neueVerifyUmgebung2304
// aus verify_resend_test.go, selbes Testpaket). Drei Gründe, warum ein
// direkter Handler-Aufruf hier zu wenig wäre:
//
//  1. AC-11 misst die Abwesenheit eines Umgebungs-Schalters. Registrierungs-
//     bedingungen wirken in router.go, nicht im Handler.
//  2. AC-10 prüft, dass das beim Passwortwechsel ausgestellte Merkmal
//     anschließend WIRKLICH einen geschützten Endpunkt öffnet — das ist eine
//     Messung an der AuthMiddleware, nicht am Handler-Rückgabewert.
//  3. AC-9 vergleicht drei Antworten byteweise. Nur über denselben Router
//     ist sichergestellt, dass keine Zwischenschicht (Limiter, Middleware)
//     einen der drei Wege anders behandelt.
//
// Kein Mock: echte bcrypt-Hashes, echter Store auf t.TempDir(), echter
// chi-Router mit der Produktions-Verdrahtung.

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
)

const (
	loginPfad2271    = "/api/auth/login"
	passwortPfad2271 = "/api/auth/password"
	profilPfad2271   = "/api/auth/profile"

	// Der Antwort-Vertrag des Gates (Spec "Antwortform"): 403 NACH bestandener
	// Geheimnisprüfung, mit einem Grund, den der rechtmäßige Nutzer versteht.
	gateKoerper2271 = `{"error":"email_not_verified"}`
	// Der unveränderte Vertrag der Abweisungen VOR jeder Geheimnisprüfung.
	// AC-9 sichert zu, dass das Gate diesen nicht anfasst.
	abweisungsKoerper2271 = `{"error":"invalid credentials"}`
)

// kontoMitPasswort2271 legt ein anmeldefähiges Konto an. Die Kennung darf
// weder "test" noch "tdd" enthalten (mail.IsTestUser) — sonst nähme ein
// etwaiger Versand den Google-Zweig.
func kontoMitPasswort2271(t *testing.T, e *verifyUmgebung2304, uid, passwort string, bestaetigt bool) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(passwort), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt für %q: %v", uid, err)
	}
	konto := model.User{
		ID:           uid,
		Email:        uid + "@beispiel.de",
		MailTo:       uid + "@beispiel.de",
		DisplayName:  "Konto " + uid,
		PasswordHash: string(hash),
		CreatedAt:    time.Now(),
	}
	if bestaetigt {
		jetzt := time.Now().UTC()
		konto.EmailVerifiedAt = &jetzt
	}
	if err := e.store.SaveUser(konto); err != nil {
		t.Fatalf("Konto %q anlegen: %v", uid, err)
	}
	if err := e.store.ProvisionUserDirs(uid); err != nil {
		t.Fatalf("ProvisionUserDirs %q: %v", uid, err)
	}
}

// anfrage2271 ergänzt e.post um die übrigen Methoden (AC-10 braucht PUT und
// GET).
func anfrage2271(t *testing.T, e *verifyUmgebung2304, methode, pfad, rumpf string, cookie *http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(methode, pfad, strings.NewReader(rumpf))
	req.Header.Set("Content-Type", "application/json")
	if cookie != nil {
		req.AddCookie(cookie)
	}
	w := httptest.NewRecorder()
	e.router.ServeHTTP(w, req)
	return w
}

// sitzungsmerkmal2271 liefert das gz_session-Cookie der Antwort oder nil.
// Die Abwesenheit ist in drei der vier Nachweise hier der Normalfall, deshalb
// darf die Funktion nicht fatalen.
func sitzungsmerkmal2271(w *httptest.ResponseRecorder) *http.Cookie {
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" {
			return c
		}
	}
	return nil
}

// AC-1: Konto ohne bestätigte Adresse, KORREKTES Passwort → 403
// {"error":"email_not_verified"}, kein Session-Cookie.
//
// Der Preis dieser Antwortform ist in der Spec benannt und vom PO freigegeben:
// wer ein geleaktes Passwort ausprobiert, erfährt zusätzlich, dass Konto und
// Passwort stimmen. AC-9 unten sichert die Gegenseite — gegenüber jemandem
// OHNE Passwort entsteht kein neues Leck.
func TestPasswortLoginUnbestaetigtWirdAbgewiesen_AC1(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	const uid = "nora2271"
	const passwort = "geheim12345"
	kontoMitPasswort2271(t, e, uid, passwort, false)

	w := e.post(t, loginPfad2271, `{"username":"`+uid+`","password":"`+passwort+`"}`, nil)

	if w.Code != http.StatusForbidden {
		t.Errorf("AC-1: erwartet 403 für ein unbestätigtes Konto mit korrektem Passwort, bekommen %d: %s",
			w.Code, w.Body.String())
	}
	if got := strings.TrimSpace(w.Body.String()); got != gateKoerper2271 {
		t.Errorf("AC-1: erwarteter Antwortkörper %s, bekommen %q", gateKoerper2271, got)
	}
	if c := sitzungsmerkmal2271(w); c != nil {
		t.Errorf("AC-1: abgewiesene Anmeldung darf kein gz_session-Cookie ausstellen, bekommen %q", c.Value)
	}
}

// AC-9: Drei Anmeldeversuche, die alle NICHT über ein gültiges Geheimnis
// verfügen, sind zeichengleich 401 — das Gate schafft keine neue
// Kontenaufzählung.
//
// Fall (c) ist der eigentliche Wächter über die REIHENFOLGE: Läge das Gate vor
// der Passwortprüfung, lieferte (c) 403 statt 401 und verriete die Existenz
// des Kontos an jemanden, der das Passwort gar nicht kennt.
func TestDreiFehlanmeldungenBleibenZeichengleich_AC9(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	const passwort = "geheim12345"
	kontoMitPasswort2271(t, e, "jana2271", passwort, true)   // bestätigt
	kontoMitPasswort2271(t, e, "milan2271", passwort, false) // unbestätigt

	faelle := []struct {
		name  string
		rumpf string
	}{
		{"a_kein_konto", `{"username":"niemand2271","password":"` + passwort + `"}`},
		{"b_bestaetigt_falsches_passwort", `{"username":"jana2271","password":"falsch12345"}`},
		{"c_unbestaetigt_falsches_passwort", `{"username":"milan2271","password":"falsch12345"}`},
	}

	type antwort struct {
		code        int
		contentType string
		rumpf       []byte
	}
	gesehen := make([]antwort, 0, len(faelle))

	for _, f := range faelle {
		w := e.post(t, loginPfad2271, f.rumpf, nil)
		if w.Code != http.StatusUnauthorized {
			t.Errorf("AC-9/%s: erwartet 401, bekommen %d: %s", f.name, w.Code, w.Body.String())
		}
		if got := strings.TrimSpace(w.Body.String()); got != abweisungsKoerper2271 {
			t.Errorf("AC-9/%s: erwarteter Antwortkörper %s, bekommen %q", f.name, abweisungsKoerper2271, got)
		}
		gesehen = append(gesehen, antwort{
			code:        w.Code,
			contentType: w.Header().Get("Content-Type"),
			rumpf:       w.Body.Bytes(),
		})
	}

	// Paarweise byteweise Gleichheit — nicht nur "alle drei sind 401": eine
	// abweichende Formulierung oder ein abweichender Content-Type wäre
	// ebenfalls ein Unterscheidungsmerkmal.
	for i := 1; i < len(gesehen); i++ {
		if gesehen[i].code != gesehen[0].code {
			t.Errorf("AC-9: Statuscode von %s (%d) weicht von %s (%d) ab",
				faelle[i].name, gesehen[i].code, faelle[0].name, gesehen[0].code)
		}
		if gesehen[i].contentType != gesehen[0].contentType {
			t.Errorf("AC-9: Content-Type von %s (%q) weicht von %s (%q) ab",
				faelle[i].name, gesehen[i].contentType, faelle[0].name, gesehen[0].contentType)
		}
		if !bytes.Equal(gesehen[i].rumpf, gesehen[0].rumpf) {
			t.Errorf("AC-9: Antwortkörper von %s (%q) ist nicht zeichengleich mit %s (%q)",
				faelle[i].name, gesehen[i].rumpf, faelle[0].name, gesehen[0].rumpf)
		}
	}
}

// AC-10: Wer gerade seine E-Mail-Adresse geändert hat (EmailVerifiedAt == nil,
// auth.go:708/713), muss sein Passwort weiter ändern können UND behält dabei
// eine gültige Sitzung.
//
// 🔴 Der Cookie-Teil ist der eigentliche Wächter. ChangePasswordHandler ruft
// issueSession auf (auth.go:999) und leert davor die Gästeliste — liefe das
// Gate dort mit, wäre die Antwort zwar vielleicht noch 200, der Nutzer säße
// aber ohne gültiges Merkmal vor einer Seite, deren Abrufe alle 401 geben. Ein
// reiner Statuscode-Assert ginge genau dann fälschlich grün durch.
func TestPasswortwechselBleibtOhneBestaetigungMoeglich_AC10(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	const uid = "lena2271"
	const altesPasswort = "altes12345"
	const neuesPasswort = "neues67890"
	kontoMitPasswort2271(t, e, uid, altesPasswort, false)

	altesMerkmal := e.anmeldeCookie(t, uid)

	w := anfrage2271(t, e, http.MethodPut, passwortPfad2271,
		`{"old_password":"`+altesPasswort+`","new_password":"`+neuesPasswort+`"}`, altesMerkmal)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-10: der Passwortwechsel muss auch ohne bestätigte Adresse gelingen — "+
			"erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	neuesMerkmal := sitzungsmerkmal2271(w)
	if neuesMerkmal == nil {
		t.Fatal("AC-10: der Passwortwechsel muss ein frisches gz_session-Cookie ausstellen — es gibt keins")
	}
	if neuesMerkmal.Value == altesMerkmal.Value {
		t.Error("AC-10: das ausgestellte Merkmal ist mit dem alten identisch — es wurde keines erneuert")
	}

	// Der Wirknachweis: das neue Merkmal öffnet einen geschützten Endpunkt.
	// Ohne ihn bliebe unbemerkt, dass ClearSessions den Nutzer ausgesperrt hat.
	geschuetzt := anfrage2271(t, e, http.MethodGet, profilPfad2271, "", neuesMerkmal)
	if geschuetzt.Code != http.StatusOK {
		t.Errorf("AC-10: das nach dem Passwortwechsel ausgestellte Merkmal muss %s öffnen — "+
			"bekommen %d: %s", profilPfad2271, geschuetzt.Code, geschuetzt.Body.String())
	}
}

// AC-11: Ohne gesetztes GZ_ENV — der Produktionslage — greift das Gate
// unverändert. Es gibt keinen Umgebungs-Schalter, der es dort abschaltet.
//
// Die Positivkontrolle im selben Test ist Pflicht: "Gate greift" und "der
// Anmeldeweg ist in dieser Umgebung überhaupt kaputt" sähen sonst identisch
// aus. Muster übernommen von S1 AC-9 (staging_verify_token_test.go:51).
func TestGateGreiftOhneGzEnv_AC11(t *testing.T) {
	// t.Setenv registriert die Wiederherstellung, Unsetenv stellt die
	// Produktionslage her (GZ_ENV ist dort gar nicht gesetzt).
	t.Setenv("GZ_ENV", "platzhalter")
	os.Unsetenv("GZ_ENV")

	e := neueVerifyUmgebung2304(t)
	const passwort = "geheim12345"
	kontoMitPasswort2271(t, e, "timo2271", passwort, false) // unbestätigt
	kontoMitPasswort2271(t, e, "rita2271", passwort, true)  // bestätigt

	wGesperrt := e.post(t, loginPfad2271, `{"username":"timo2271","password":"`+passwort+`"}`, nil)
	if wGesperrt.Code != http.StatusForbidden {
		t.Errorf("AC-11: ohne gesetztes GZ_ENV muss das Gate mit 403 greifen, bekommen %d: %s",
			wGesperrt.Code, wGesperrt.Body.String())
	}
	if got := strings.TrimSpace(wGesperrt.Body.String()); got != gateKoerper2271 {
		t.Errorf("AC-11: erwarteter Antwortkörper %s, bekommen %q", gateKoerper2271, got)
	}
	if c := sitzungsmerkmal2271(wGesperrt); c != nil {
		t.Errorf("AC-11: kein gz_session-Cookie bei abgewiesener Anmeldung, bekommen %q", c.Value)
	}

	// Positivkontrolle: derselbe Router, dieselbe Lage, bestätigtes Konto.
	wOffen := e.post(t, loginPfad2271, `{"username":"rita2271","password":"`+passwort+`"}`, nil)
	if wOffen.Code != http.StatusOK {
		t.Fatalf("AC-11 Positivkontrolle: ein bestätigtes Konto muss sich ohne GZ_ENV anmelden können — "+
			"erwartet 200, bekommen %d: %s", wOffen.Code, wOffen.Body.String())
	}
	if c := sitzungsmerkmal2271(wOffen); c == nil {
		t.Error("AC-11 Positivkontrolle: die bestätigte Anmeldung muss ein gz_session-Cookie ausstellen")
	}
}
