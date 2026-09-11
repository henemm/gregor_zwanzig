package handler_test

// TDD RED — Issue #2304 (S1 aus #2271/#2146, Epic #2138): staging-only
// Testweg, der ein Verifikations-Token ohne Mailversand herausgibt.
// Spec: docs/specs/modules/email_verify_vorbereitung_2304.md — AC-9..AC-12.
//
// Alles vier Nachweise laufen gegen den ECHTEN Router (neueVerifyUmgebung2304
// aus verify_resend_test.go, selbes Testpaket): sowohl die
// GZ_ENV-Registrierungsbedingung (router.go:215-Muster) als auch die
// Anmeldepflicht (internal/middleware/auth.go) wirken NUR dort. Ein direkter
// Handler-Aufruf würde beide Zusicherungen am Wirkort verfehlen.
//
// 🔴 Warum in jedem dieser Tests eine POSITIVKONTROLLE steht: "Route fehlt"
// und "Route ist korrekt abgeriegelt" sehen von außen identisch aus — 404
// bzw. 401, in beiden Fällen kein Token. Ohne den Gegenbeweis, dass derselbe
// Pfad unter der richtigen Lage ANTWORTET und ein Token liefert, wären AC-9
// und AC-12 auch dann grün, wenn der Endpunkt unter `/api/debug/` läge und
// damit pauschal öffentlich wäre (middleware/auth.go:61-63).

import (
	"encoding/json"
	"net/http"
	"os"
	"testing"
	"time"
)

// stagingTokenPfad2304 — der Testweg. Er liegt bewusst NICHT unter
// `/api/debug/`, `/api/internal/` oder `/api/webhooks/telegram/`: diese drei
// Präfixe befreit die AuthMiddleware pauschal von der Anmeldepflicht
// (internal/middleware/auth.go:61-63). Er gehört auch NICHT in die
// Public-Allowlist. Der exakte Eintrag `/api/auth/verify-email` deckt diesen
// Unterpfad nicht mit ab — die Anmeldepflicht greift also.
const stagingTokenPfad2304 = "/api/auth/verify-email/staging-token"

// tokenAusAntwort liest das Klartext-Token aus der Antwort des Testwegs.
func tokenAusAntwort(t *testing.T, rumpf []byte) string {
	t.Helper()
	var antwort struct {
		Token string `json:"token"`
	}
	if err := json.Unmarshal(rumpf, &antwort); err != nil {
		t.Fatalf("Antwort des Staging-Testwegs ist kein lesbares JSON (%q): %v", string(rumpf), err)
	}
	if antwort.Token == "" {
		t.Fatalf("Antwort des Staging-Testwegs enthält kein Feld \"token\": %q", string(rumpf))
	}
	return antwort.Token
}

// AC-9: ohne gesetztes GZ_ENV (Produktionslage) antwortet der Testweg 404 und
// erzeugt kein Token — mit GZ_ENV=staging antwortet derselbe Pfad sehr wohl.
func TestStagingTokenwegExistiertNurUnterGzEnvStaging_AC9(t *testing.T) {
	const uid = "rosa2304"

	// --- Produktionslage: GZ_ENV ist NICHT gesetzt.
	t.Setenv("GZ_ENV", "platzhalter") // registriert die Wiederherstellung
	os.Unsetenv("GZ_ENV")

	prod := neueVerifyUmgebung2304(t)
	prod.konto2304(t, uid, "rosa@beispiel.de", "rosa-empfang@beispiel.de", nil)
	wProd := prod.post(t, stagingTokenPfad2304, `{"username":"`+uid+`"}`, prod.anmeldeCookie(t, uid))

	if wProd.Code != http.StatusNotFound {
		t.Errorf("AC-9: ohne GZ_ENV muss der Testweg 404 liefern, bekommen %d: %s",
			wProd.Code, wProd.Body.String())
	}
	if tok, _ := prod.store.LoadVerificationToken(uid); tok != nil {
		t.Errorf("AC-9: ohne GZ_ENV darf kein Verifikations-Token entstehen — es liegt einer für %q", uid)
	}

	// --- Positivkontrolle: derselbe Pfad, dieselbe Anfrage, GZ_ENV=staging.
	// Ohne sie wäre AC-9 auch dann grün, wenn es den Endpunkt nirgends gäbe.
	t.Setenv("GZ_ENV", "staging")
	stg := neueVerifyUmgebung2304(t)
	stg.konto2304(t, uid, "rosa@beispiel.de", "rosa-empfang@beispiel.de", nil)
	wStg := stg.post(t, stagingTokenPfad2304, `{"username":"`+uid+`"}`, stg.anmeldeCookie(t, uid))

	if wStg.Code != http.StatusOK {
		t.Fatalf("AC-9 Positivkontrolle: mit GZ_ENV=staging muss %s mit 200 antworten, bekommen %d: %s",
			stagingTokenPfad2304, wStg.Code, wStg.Body.String())
	}
	if tok := tokenAusAntwort(t, wStg.Body.Bytes()); tok == "" {
		t.Fatal("AC-9 Positivkontrolle: kein Token in der Staging-Antwort")
	}
	if tok, _ := stg.store.LoadVerificationToken(uid); tok == nil {
		t.Error("AC-9 Positivkontrolle: mit GZ_ENV=staging muss ein Token im Speicher liegen")
	}
}

// AC-10: der Testweg liefert ein Token, setzt email_verified_at aber NICHT
// selbst — erst der reguläre Verifikations-Endpunkt tut das.
func TestStagingTokenwegSetztBestaetigungNichtSelbst_AC10(t *testing.T) {
	t.Setenv("GZ_ENV", "staging")
	e := neueVerifyUmgebung2304(t)

	const uid = "clara2304"
	e.konto2304(t, uid, "clara@beispiel.de", "clara-empfang@beispiel.de", nil)

	w := e.post(t, stagingTokenPfad2304, `{"username":"`+uid+`"}`, e.anmeldeCookie(t, uid))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-10: erwartet 200 vom Staging-Testweg, bekommen %d: %s", w.Code, w.Body.String())
	}
	token := tokenAusAntwort(t, w.Body.Bytes())

	// Reihenfolge-Nachweis, erste Hälfte: unmittelbar nach dem Staging-Aufruf
	// ist NICHTS bestätigt.
	user, err := e.store.LoadUser(uid)
	if err != nil || user == nil {
		t.Fatalf("AC-10: Konto nicht ladbar: %v", err)
	}
	if user.EmailVerifiedAt != nil {
		t.Fatalf("AC-10: der Staging-Testweg darf email_verified_at NICHT selbst setzen, "+
			"es steht aber bereits auf %v", user.EmailVerifiedAt)
	}

	// Zweite Hälfte: erst der echte Einlöse-Endpunkt setzt das Feld.
	wEinloesen := e.post(t, verifyPfad2304, `{"user":"`+uid+`","token":"`+token+`"}`, nil)
	if wEinloesen.Code != http.StatusOK {
		t.Fatalf("AC-10: der reguläre Endpunkt %s muss das gelieferte Token annehmen, "+
			"bekommen %d: %s", verifyPfad2304, wEinloesen.Code, wEinloesen.Body.String())
	}
	user, err = e.store.LoadUser(uid)
	if err != nil || user == nil {
		t.Fatalf("AC-10: Konto nach der Einlösung nicht ladbar: %v", err)
	}
	if user.EmailVerifiedAt == nil {
		t.Error("AC-10: nach erfolgreicher Einlösung muss email_verified_at gesetzt sein")
	}
}

// AC-11: bei einem bereits bestätigten Konto bleibt der bestehende Zeitstempel
// nach einem Staging-Aufruf WERTGLEICH — geprüft wird der Wert, nicht bloß
// "irgendein Wert ist gesetzt".
func TestStagingTokenwegLaesstBestehendenZeitstempelUnveraendert_AC11(t *testing.T) {
	t.Setenv("GZ_ENV", "staging")
	e := neueVerifyUmgebung2304(t)

	const uid = "doris2304"
	bestaetigt := time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)
	e.konto2304(t, uid, "doris@beispiel.de", "doris-empfang@beispiel.de", &bestaetigt)

	// Ausgangswert aus dem Speicher lesen (nach JSON-Roundtrip), nicht die
	// lokale Variable — verglichen wird, was tatsächlich auf der Platte steht.
	vorher, err := e.store.LoadUser(uid)
	if err != nil || vorher == nil || vorher.EmailVerifiedAt == nil {
		t.Fatalf("AC-11 Ausgangslage: Konto muss mit gesetztem email_verified_at vorliegen: %v", err)
	}
	wertVorher := *vorher.EmailVerifiedAt

	w := e.post(t, stagingTokenPfad2304, `{"username":"`+uid+`"}`, e.anmeldeCookie(t, uid))

	// Positivkontrolle: der Aufruf hat wirklich stattgefunden und ein Token
	// geliefert. Ohne sie wäre "Zeitstempel unverändert" trivial erfüllt,
	// solange der Endpunkt fehlt.
	if w.Code != http.StatusOK {
		t.Fatalf("AC-11 Positivkontrolle: der Staging-Testweg muss auch für ein bereits "+
			"bestätigtes Konto mit 200 antworten, bekommen %d: %s", w.Code, w.Body.String())
	}
	if tok := tokenAusAntwort(t, w.Body.Bytes()); tok == "" {
		t.Fatal("AC-11 Positivkontrolle: kein Token in der Antwort")
	}

	nachher, err := e.store.LoadUser(uid)
	if err != nil || nachher == nil {
		t.Fatalf("AC-11: Konto nach dem Aufruf nicht ladbar: %v", err)
	}
	if nachher.EmailVerifiedAt == nil {
		t.Fatalf("AC-11: email_verified_at wurde entfernt — vorher %v", wertVorher)
	}
	if !nachher.EmailVerifiedAt.Equal(wertVorher) {
		t.Errorf("AC-11: bestehender Zeitstempel wurde überschrieben: vorher %v, nachher %v",
			wertVorher, *nachher.EmailVerifiedAt)
	}
}

// AC-12: ohne gültiges Anmelde-Merkmal wird der Testweg mit 401 abgewiesen und
// es entsteht kein Token.
//
// Dieser Test bewacht die Präfix-Falle: läge der Pfad unter `/api/debug/`,
// `/api/internal/` oder `/api/webhooks/telegram/`, gäbe die AuthMiddleware ihn
// pauschal frei (middleware/auth.go:61-63) — der anonyme Aufruf lieferte dann
// 200 samt Token. Die Positivkontrolle mit Merkmal trennt diesen Fall von
// "die Route existiert gar nicht": beides ergäbe sonst denselben Befund.
func TestStagingTokenwegVerlangtAnmeldung_AC12(t *testing.T) {
	t.Setenv("GZ_ENV", "staging")
	e := neueVerifyUmgebung2304(t)

	const uid = "erik2304"
	e.konto2304(t, uid, "erik@beispiel.de", "erik-empfang@beispiel.de", nil)

	// --- ohne Cookie
	wAnonym := e.post(t, stagingTokenPfad2304, `{"username":"`+uid+`"}`, nil)
	if wAnonym.Code != http.StatusUnauthorized {
		t.Errorf("AC-12: anonymer Aufruf von %s muss 401 liefern, bekommen %d: %s — "+
			"liegt der Pfad unter /api/debug/, /api/internal/ oder /api/webhooks/telegram/, "+
			"befreit die AuthMiddleware ihn pauschal von der Anmeldepflicht",
			stagingTokenPfad2304, wAnonym.Code, wAnonym.Body.String())
	}
	if tok, _ := e.store.LoadVerificationToken(uid); tok != nil {
		t.Errorf("AC-12: nach dem abgewiesenen Aufruf darf kein Token für %q existieren", uid)
	}

	// --- Positivkontrolle: dieselbe Anfrage MIT gültigem Merkmal.
	wAngemeldet := e.post(t, stagingTokenPfad2304, `{"username":"`+uid+`"}`, e.anmeldeCookie(t, uid))
	if wAngemeldet.Code != http.StatusOK {
		t.Fatalf("AC-12 Positivkontrolle: mit gültigem Merkmal muss %s mit 200 antworten, "+
			"bekommen %d: %s (sonst misst der 401 oben nur eine fehlende Route)",
			stagingTokenPfad2304, wAngemeldet.Code, wAngemeldet.Body.String())
	}
	if tok := tokenAusAntwort(t, wAngemeldet.Body.Bytes()); tok == "" {
		t.Fatal("AC-12 Positivkontrolle: kein Token in der Antwort")
	}
	if tok, _ := e.store.LoadVerificationToken(uid); tok == nil {
		t.Error("AC-12 Positivkontrolle: nach dem angemeldeten Aufruf muss ein Token im Speicher liegen")
	}
}
