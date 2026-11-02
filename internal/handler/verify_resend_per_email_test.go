package handler_test

// TDD RED — Issue #2194 (Epic #2138), AC-8: "Bestaetigungsmail erneut senden"
// mit der E-Mail-Adresse. Spec: docs/specs/modules/email_login_identifier.md
//
// Bekannte (unbestaetigte), unbekannte und mehrfach vergebene Adresse liefern
// dieselbe neutrale Antwort; nur das eindeutig gefundene Konto bekommt Token
// und Mail mit Link ?user=<ID>.
//
// Heute sind die Antworten schon gleich (jede "@"-Kennung faellt durch
// ValidUserID) — das RED liegt in der Positivhaelfte. Gemessen am Token
// (dispatchVerificationMail stellt ihn synchron aus) und an der bestehenden
// Naht sendVerificationMailFn (Bruecke ObserveVerificationMailForTest).
//
// Echter Router (neueVerifyUmgebung2304), nur bestehende Symbole.

import (
	"bytes"
	"net/http"
	"strings"
	"testing"
	"time"
)

func TestResendPerEmail_NeutralUndNurEinzeltreffer_AC8_2194(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	aufrufe := beobachteVersand2304(t)

	e.konto2304(t, "olga2194", "olga@beispiel.de", "olga@beispiel.de", nil)
	e.konto2304(t, "paul2194", "doppelt2194@beispiel.de", "paul-empfang@beispiel.de", nil)
	e.konto2304(t, "quirin2194", "doppelt2194@beispiel.de", "quirin-empfang@beispiel.de", nil)

	wBekannt := e.post(t, resendPfad2304, `{"username":"OLGA@beispiel.de"}`, nil)
	wUnbekannt := e.post(t, resendPfad2304, `{"username":"niemand2194@beispiel.de"}`, nil)
	wDoppelt := e.post(t, resendPfad2304, `{"username":"doppelt2194@beispiel.de"}`, nil)

	if wBekannt.Code != http.StatusOK || strings.TrimSpace(wBekannt.Body.String()) != `{"status":"ok"}` {
		t.Fatalf("AC-8: neutrale Antwort erwartet 200 {\"status\":\"ok\"}, bekommen %d %q",
			wBekannt.Code, wBekannt.Body.String())
	}
	for name, w := range map[string][]byte{"unbekannt": wUnbekannt.Body.Bytes(), "doppelt": wDoppelt.Body.Bytes()} {
		if !bytes.Equal(w, wBekannt.Body.Bytes()) {
			t.Errorf("AC-8: Antwort %s %q weicht von der bekannten %q ab", name, w, wBekannt.Body.String())
		}
	}
	if wUnbekannt.Code != wBekannt.Code || wDoppelt.Code != wBekannt.Code {
		t.Errorf("AC-8: Statuscodes weichen ab: bekannt %d, unbekannt %d, doppelt %d",
			wBekannt.Code, wUnbekannt.Code, wDoppelt.Code)
	}

	// Positivhaelfte (RED heute).
	if tok, err := e.store.LoadVerificationToken("olga2194"); err != nil || tok == nil {
		t.Errorf("AC-8: fuer die bekannte Adresse muss ein Bestaetigungs-Token beim Konto olga2194 liegen (err=%v)", err)
	}
	for _, id := range []string{"paul2194", "quirin2194"} {
		if tok, _ := e.store.LoadVerificationToken(id); tok != nil {
			t.Errorf("AC-8: mehrfach vergebene Adresse darf fuer %q kein Token erzeugen", id)
		}
	}

	select {
	case m := <-aufrufe:
		if m.to != "olga@beispiel.de" {
			t.Errorf("AC-8: Bestaetigungsmail muss an olga@beispiel.de gehen, ging an %q", m.to)
		}
		if !strings.Contains(m.msg.PlainBody, "/verify-email?user=olga2194&") {
			t.Errorf("AC-8: Link muss ?user=<ID> tragen:\n%s", m.msg.PlainBody)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("AC-8: binnen 3s keine Bestaetigungsmail fuer die bekannte Adresse beobachtet")
	}
	select {
	case m := <-aufrufe:
		t.Errorf("AC-8: nur der Einzeltreffer bekommt eine Mail, zusaetzlich ging eine an %q", m.to)
	case <-time.After(300 * time.Millisecond):
	}
}
