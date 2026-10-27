package handler_test

// TDD RED — Issue #2406: staging-only Testweg fuer den SMS-Bestaetigungscode.
// Spec: docs/specs/modules/sms_nummer_verifikation.md — AC-15 (§5, §7).
//
// Umgebung: sms_verification_test.go (smsUmgebung2406). GZ_ENV wird vor
// router.New gesetzt (t.Setenv) — deshalb laufen diese Tests nicht parallel.
//
// Vertrag der Antwort (Spec §5 nennt nur „Klartext zurueck"): JSON-Objekt mit
// dem Feld `code` (6 Ziffern), Muster StagingVerificationTokenHandler
// (`{"token":…}`).

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
)

func stagingCode2406(t *testing.T, e *smsUmgebung2406, c *http.Cookie, rumpf string) (int, string, string) {
	t.Helper()
	w := e.anfrage(t, http.MethodPost, smsStagingPfad2406, rumpf, c)
	var m map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &m)
	code, _ := m["code"].(string)
	return w.Code, code, w.Body.String()
}

// AC-15a: ohne GZ_ENV=staging existiert die Route nicht (404, keine Code-Datei).
// Gegenprobe im selben Test: mit GZ_ENV=staging liefert derselbe Aufruf den
// Code — sonst waere das 404 heute trivial gruen.
func TestSmsStagingCodeNurInStagingUmgebung(t *testing.T) {
	prod := neueSmsUmgebung2406(t, false)
	const uid = "smsstagprod"
	prod.konto(t, uid, "standard", map[string]any{"pending_sms_to": nummerB2406, "sms_to": nummerA2406, "sms_verified_number": nummerA2406})
	status, _, body := stagingCode2406(t, prod, prod.cookie(t, uid), `{}`)
	if status != http.StatusNotFound {
		t.Errorf("AC-15a: ohne GZ_ENV=staging erwartet 404, bekommen %d: %s", status, body)
	}
	if _, err := os.Stat(prod.codeDateiPfad(uid)); !os.IsNotExist(err) {
		t.Errorf("AC-15a: ohne Staging darf keine sms_verification.json entstehen (err=%v)", err)
	}

	stag := neueSmsUmgebung2406(t, true)
	stag.konto(t, uid, "standard", map[string]any{"pending_sms_to": nummerB2406, "sms_to": nummerA2406, "sms_verified_number": nummerA2406})
	status, code, body := stagingCode2406(t, stag, stag.cookie(t, uid), `{}`)
	if status != http.StatusOK || len(code) != 6 || strings.Trim(code, "0123456789") != "" {
		t.Fatalf("AC-15 Gegenprobe: mit GZ_ENV=staging erwartet 200 und 6-stelligen code, bekommen %d: %s", status, body)
	}
	// Anmeldepflichtig: ohne Sitzung kein Code.
	if s, _, b := stagingCode2406(t, stag, nil, `{}`); s != http.StatusUnauthorized {
		t.Errorf("AC-15/§5: ohne Anmeldung erwartet 401, bekommen %d: %s", s, b)
	}
	// Kein Sendeversuch ueber den Testweg.
	stag.erwarteKeinenVersand(t, "AC-15 Staging-Code")
}

// AC-15b: der Body wird ignoriert — auch mit fremder Kennung im Body gilt der
// Code dem EIGENEN, angemeldeten Konto; das fremde Konto bleibt unberuehrt.
func TestSmsStagingCodeIgnoriertFremdeKennungImBody(t *testing.T) {
	e := neueSmsUmgebung2406(t, true)
	const eigen, fremd = "smsstageigen", "smsstagfremd"
	e.konto(t, eigen, "standard", map[string]any{"sms_to": nummerA2406})
	e.konto(t, fremd, "standard", map[string]any{"sms_to": nummerB2406})

	status, code, body := stagingCode2406(t, e, e.cookie(t, eigen),
		`{"username":"`+fremd+`","user_id":"`+fremd+`"}`)
	if status != http.StatusOK || code == "" {
		t.Fatalf("AC-15b: erwartet 200 mit code, bekommen %d: %s", status, body)
	}
	roh, err := os.ReadFile(e.codeDateiPfad(eigen))
	if err != nil {
		t.Fatalf("AC-15b: Code muss fuer das EIGENE Konto %q entstehen: %v", eigen, err)
	}
	var datei map[string]any
	_ = json.Unmarshal(roh, &datei)
	if feld2406(datei, "number") != nummerA2406 {
		t.Errorf("AC-15b: Code muss an die eigene Nummer %s gebunden sein, gebunden an %q", nummerA2406, feld2406(datei, "number"))
	}
	if _, err := os.Stat(e.codeDateiPfad(fremd)); !os.IsNotExist(err) {
		t.Errorf("AC-15b: fuer das fremde Konto %q darf KEIN Code entstehen (err=%v)", fremd, err)
	}
}

// AC-15c: der gelieferte Code macht den REGULAEREN Bestaetigungsweg erfolgreich
// (der Testweg setzt selbst nichts).
func TestSmsStagingCodeBestaetigtUeberDenRegulaerenWeg(t *testing.T) {
	e := neueSmsUmgebung2406(t, true)
	const uid = "smsstagok"
	bestand := bestaetigtA2406()
	bestand["pending_sms_to"] = nummerB2406
	e.konto(t, uid, "standard", bestand)
	c := e.cookie(t, uid)

	status, code, body := stagingCode2406(t, e, c, `{}`)
	if status != http.StatusOK || code == "" {
		t.Fatalf("AC-15c: Staging-Code erwartet 200 mit code, bekommen %d: %s", status, body)
	}
	if got := feld2406(e.userJSON(t, uid), "sms_verified_number"); got != nummerA2406 {
		t.Fatalf("AC-15c: der Testweg selbst darf nichts bestaetigen — sms_verified_number muss A bleiben, bekommen %q", got)
	}
	w := e.verify(t, c, code)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-15c: POST %s mit dem Staging-Code erwartet 200, bekommen %d: %s", smsVerifyPfad2406, w.Code, w.Body.String())
	}
	u := e.userJSON(t, uid)
	if feld2406(u, "sms_to") != nummerB2406 || feld2406(u, "sms_verified_number") != nummerB2406 {
		t.Errorf("AC-15c: nach Bestaetigung erwartet sms_to=B und sms_verified_number=B — user.json: %v", u)
	}
}
