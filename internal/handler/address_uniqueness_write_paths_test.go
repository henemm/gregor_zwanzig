package handler

// TDD RED — Issue #2147 Scheibe B1 (+ #2311, Epic #2138): Adress-Eindeutigkeit
// an den Schreibpfaden Registrierung, oeffentliche Passkey-Registrierung und
// Profil-Update.
// Spec: docs/specs/modules/adress_eindeutigkeit_schreibpfade.md — AC-1..AC-11,
// AC-13, AC-14 (AC-12 in magic_link_takeover_recheck_test.go, AC-15/AC-16 im
// Frontend).
//
// Geprueft wird am WIRKORT: echte HTTP-Handler (RegisterHandler,
// PasskeyRegisterPublicBeginHandler/FinishHandler, UpdateProfileHandler) gegen
// einen echten store.Store auf t.TempDir(). Kein Mock-Theater. Reihenfolge:
// zwei verschiedene Nutzer je Pfad, wo die Spec das verlangt.
//
// Wiederverwendete Helfer aus magic_link_address_ownership_test.go (gleiches
// Paket): newTestStore, speichereKonto, kontenAnzahl, rohesKonto, jetztBestaetigt,
// eindeutigCfg, eindeutigSecret, ladeKonto. Neue Helfer tragen das Praefix
// "schreibpfad", um Namenskollisionen mit Scheibe A auszuschliessen.

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// --- Hilfen (Praefix schreibpfad, siehe Kopfkommentar) ------------------------

const schreibpfadPasswort = "geheimnis-genug-lang1"

func schreibpfadRegistrieren(s *store.Store, cfg config.Config, username, email string) *httptest.ResponseRecorder {
	body := fmt.Sprintf(`{"username":%q,"password":%q,"email":%q}`, username, schreibpfadPasswort, email)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	RegisterHandler(s, bcrypt.MinCost, cfg).ServeHTTP(w, req)
	return w
}

func schreibpfadProfilAktualisieren(s *store.Store, cfg config.Config, userID, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	w := httptest.NewRecorder()
	UpdateProfileHandler(s, cfg).ServeHTTP(w, req)
	return w
}

func schreibpfadFehlerCode(w *httptest.ResponseRecorder) string {
	var body map[string]string
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	return body["error"]
}

func schreibpfadChallengeAnzahl(cs *ChallengeStore) int {
	n := 0
	cs.m.Range(func(_, _ any) bool { n++; return true })
	return n
}

// schreibpfadAdresseHalterAnzahl zaehlt, wie viele Konten (gleich welchen
// Bestaetigungsstands) X in email ODER mail_to tragen — die Zieleigenschaft
// der Belegt-Pruefung, unabhaengig vom internen Implementierungsweg.
func schreibpfadAdresseHalterAnzahl(t *testing.T, s *store.Store, adresse string) int {
	t.Helper()
	x := store.NormalizeEmailAddress(adresse)
	ids, err := s.ListUserIDs()
	if err != nil {
		t.Fatalf("ListUserIDs: %v", err)
	}
	n := 0
	for _, id := range ids {
		u, err := s.LoadUser(id)
		if err != nil || u == nil {
			continue
		}
		if store.NormalizeEmailAddress(u.Email) == x || store.NormalizeEmailAddress(u.MailTo) == x {
			n++
		}
	}
	return n
}

// --- AC-1 ---------------------------------------------------------------------

// AC-1: freie Adresse, roh mit Gross-/Kleinschreibung und Randleerzeichen ->
// Konto wird angelegt, email/mail_to sind normalisiert gespeichert.
func TestRegistrierungSpeichertNormalisierteAdresse_AC1(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	const username = "neuling-ac1"

	w := schreibpfadRegistrieren(s, cfg, username, " Foo@X.De ")

	if w.Code != http.StatusCreated {
		t.Fatalf("AC-1: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	u := ladeKonto(t, s, username)
	if u.Email != "foo@x.de" || u.MailTo != "foo@x.de" {
		t.Errorf("AC-1: erwartet normalisiert foo@x.de in beiden Feldern, bekommen email=%q mail_to=%q",
			u.Email, u.MailTo)
	}
}

// --- AC-2 ---------------------------------------------------------------------

// AC-2: ein anderes, echtes Konto traegt die Adresse bereits (einmal ueber
// email, einmal ueber mail_to) -> 409 email_taken, kein neues Konto, keine
// Verifikationsmail.
func TestRegistrierungWeistBelegteAdresseAb_AC2(t *testing.T) {
	faelle := []struct {
		name           string
		halterEmail    string
		halterMailTo   string
		versuchAdresse string
	}{
		{"ueber-email", "kollision-ac2-email@beispiel.de", "halter-eigen-ac2@beispiel.de", "Kollision-AC2-Email@Beispiel.de"},
		{"ueber-mail-to", "halter-eigen2-ac2@beispiel.de", "kollision-ac2-mailto@beispiel.de", "kollision-ac2-mailto@beispiel.de"},
	}
	for i, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			cfg := config.Config{}
			halterID := fmt.Sprintf("halter-ac2-%d", i)
			speichereKonto(t, s, model.User{ID: halterID, Email: f.halterEmail, MailTo: f.halterMailTo})
			vorAnzahl := kontenAnzahl(t, s)
			neuerName := fmt.Sprintf("neuling-ac2-%d", i)

			w := schreibpfadRegistrieren(s, cfg, neuerName, f.versuchAdresse)

			if w.Code != http.StatusConflict || schreibpfadFehlerCode(w) != "email_taken" {
				t.Fatalf("AC-2/%s: erwartet 409 email_taken, bekommen %d: %s", f.name, w.Code, w.Body.String())
			}
			if n := kontenAnzahl(t, s); n != vorAnzahl {
				t.Errorf("AC-2/%s: es darf kein neues Konto entstehen, Kontenzahl %d statt %d", f.name, n, vorAnzahl)
			}
			if s.UserExists(neuerName) {
				t.Errorf("AC-2/%s: Kennung %q darf nicht existieren", f.name, neuerName)
			}
			if tok, err := s.LoadVerificationToken(neuerName); err != nil || tok != nil {
				t.Errorf("AC-2/%s: keine Verifikationsmail — es darf kein Token entstanden sein (tok=%v err=%v)",
					f.name, tok, err)
			}
		})
	}
}

// --- AC-3 ---------------------------------------------------------------------

// AC-3: nur ein Testkonto traegt die Adresse -> reguläre Registrierung
// gelingt normal, das Testkonto blockiert nicht.
func TestRegistrierungIgnoriertTestkontoAlsHalter_AC3(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	const testID = "tg-live-e2e"
	const adresse = "frei-trotz-testkonto-ac3@beispiel.de"
	speichereKonto(t, s, model.User{ID: testID, Email: adresse, MailTo: adresse})
	vorher := rohesKonto(t, s, testID)

	w := schreibpfadRegistrieren(s, cfg, "neuling-ac3", adresse)

	if w.Code != http.StatusCreated {
		t.Fatalf("AC-3: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	if n := kontenAnzahl(t, s); n != 2 {
		t.Errorf("AC-3: erwartet Testkonto + neues Konto, vorhanden: %d", n)
	}
	if string(vorher) != string(rohesKonto(t, s, testID)) {
		t.Errorf("AC-3: Testkonto darf nicht veraendert werden")
	}
}

// --- AC-4 ---------------------------------------------------------------------

// AC-4: Kennung UND Adresse sind beide schon vergeben -> Kennungs-Konflikt hat
// Vorrang (#1517), nicht email_taken.
func TestRegistrierungKennungskonfliktHatVorrangVorAdresskonflikt_AC4(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	const bestehendeKennung = "u-ac4-bestehend"
	const halterID = "u-ac4-halter"
	const adresse = "adresse-ac4@beispiel.de"
	speichereKonto(t, s, model.User{ID: bestehendeKennung, PasswordHash: "irgendein-hash"})
	speichereKonto(t, s, model.User{ID: halterID, Email: adresse, MailTo: adresse})

	w := schreibpfadRegistrieren(s, cfg, bestehendeKennung, adresse)

	if w.Code != http.StatusConflict {
		t.Fatalf("AC-4: erwartet 409, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "user already exists") {
		t.Errorf("AC-4: erwartet Kennungs-Konflikt (user already exists), bekommen: %s", w.Body.String())
	}
	if strings.Contains(w.Body.String(), "email_taken") {
		t.Errorf("AC-4: darf NICHT email_taken melden, bekommen: %s", w.Body.String())
	}
}

// --- AC-5 ---------------------------------------------------------------------

// AC-5: oeffentliche Passkey-Registrierung, Begin-Schritt mit belegter Adresse
// -> 409 email_taken, keine Challenge wird erzeugt.
func TestPasskeyPublicBeginWeistBelegteAdresseAb_AC5(t *testing.T) {
	s := newTestStore(t)
	rpID, origin := "localhost", "http://localhost"
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	const adresse = "adresse-ac5@beispiel.de"
	speichereKonto(t, s, model.User{ID: "halter-ac5", Email: adresse, MailTo: adresse})

	body := fmt.Sprintf(`{"username":"neuling-ac5","email":%q}`, "Adresse-AC5@Beispiel.de")
	req := httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/begin", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(w, req)

	if w.Code != http.StatusConflict || !strings.Contains(w.Body.String(), "email_taken") {
		t.Fatalf("AC-5: erwartet 409 email_taken, bekommen %d: %s", w.Code, w.Body.String())
	}
	if n := schreibpfadChallengeAnzahl(cs); n != 0 {
		t.Errorf("AC-5: es darf keine Challenge erzeugt worden sein, vorhanden: %d", n)
	}
}

// --- AC-6 ---------------------------------------------------------------------

// AC-6: Begin lief mit freier Adresse, zwischen Begin und Finish registriert
// sich jemand anderes erfolgreich mit genau dieser Adresse -> Finish 409
// email_taken, kein Konto, kein Credential.
func TestPasskeyPublicFinishWeistZwischenzeitlichBelegteAdresseAb_AC6(t *testing.T) {
	s := newTestStore(t)
	rpID, origin := "localhost", "http://localhost"
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"
	cfg := config.Config{}
	const ursprungsUsername = "urspruenglich-ac6"
	const adresse = "wettlauf-ac6@beispiel.de"

	beginBody := fmt.Sprintf(`{"username":%q,"email":%q}`, ursprungsUsername, adresse)
	beginReq := httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/begin", strings.NewReader(beginBody))
	beginW := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW, beginReq)
	if beginW.Code != http.StatusOK {
		t.Fatalf("AC-6 begin: erwartet 200, bekommen %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("AC-6 begin decode: %v", err)
	}

	// Ein ANDERES Konto (andere Kennung!) belegt die Adresse zwischen Begin und
	// Finish erfolgreich.
	regW := schreibpfadRegistrieren(s, cfg, "andere-ac6", adresse)
	if regW.Code != http.StatusCreated {
		t.Fatalf("AC-6: die Zwischenzeit-Registrierung muss gelingen, bekommen %d: %s", regW.Code, regW.Body.String())
	}

	auth := newTestAuthenticator(t, rpID, origin)
	finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)
	finishReq := httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
	finishW := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret, cfg).ServeHTTP(finishW, finishReq)

	if finishW.Code != http.StatusConflict || !strings.Contains(finishW.Body.String(), "email_taken") {
		t.Fatalf("AC-6: erwartet 409 email_taken, bekommen %d: %s", finishW.Code, finishW.Body.String())
	}
	if s.UserExists(ursprungsUsername) {
		t.Errorf("AC-6: das urspruengliche Konto darf nicht entstanden sein")
	}
	if n := kontenAnzahl(t, s); n != 1 {
		t.Errorf("AC-6: erwartet genau 1 Konto (die Zwischenzeit-Registrierung), vorhanden: %d", n)
	}
}

// --- AC-7 ---------------------------------------------------------------------

// AC-7: Profil-Update will gleichzeitig display_name und eine belegte Adresse
// aendern -> 409 email_taken, das GESAMTE Profil bleibt unveraendert.
func TestProfilUpdateWeistBelegteAdresseAbUndVerwirftGesamtesUpdate_AC7(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	const nutzerA = "nutzer-a-ac7"
	const nutzerB = "nutzer-b-ac7"
	const besetzt = "besetzt-ac7@beispiel.de"
	speichereKonto(t, s, model.User{ID: nutzerA, Email: "a-alt-ac7@beispiel.de", DisplayName: "Alt-Name", EmailVerifiedAt: jetztBestaetigt()})
	speichereKonto(t, s, model.User{ID: nutzerB, Email: besetzt, MailTo: besetzt})
	vorherA := rohesKonto(t, s, nutzerA)

	body := fmt.Sprintf(`{"display_name":"Neu-Name","email":%q}`, besetzt)
	w := schreibpfadProfilAktualisieren(s, cfg, nutzerA, body)

	if w.Code != http.StatusConflict || schreibpfadFehlerCode(w) != "email_taken" {
		t.Fatalf("AC-7: erwartet 409 email_taken, bekommen %d: %s", w.Code, w.Body.String())
	}
	if string(vorherA) != string(rohesKonto(t, s, nutzerA)) {
		t.Errorf("AC-7: user.json von %q wurde veraendert — erwartet byteidentisch\nvorher:  %s\nnachher: %s",
			nutzerA, vorherA, rohesKonto(t, s, nutzerA))
	}
}

// --- AC-8 ---------------------------------------------------------------------

// AC-8 (Regressionswaechter, gewollt gruen im Altcode: die neue Pruefung
// greift nur bei tatsaechlicher Adressaenderung — genau das prueft dieser
// Test, ohne dass es dafuer eine neue Sperre braucht): Bestandsduplikat, kein
// Adresswechsel -> Speichern gelingt normal.
func TestProfilUpdateOhneAdressAenderungBlockiertNieBeiBestandsduplikat_AC8(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	const dupAdresse = "dup-ac8@beispiel.de"
	speichereKonto(t, s, model.User{ID: "dup-x-ac8", Email: dupAdresse})
	speichereKonto(t, s, model.User{ID: "dup-y-ac8", Email: dupAdresse})

	w := schreibpfadProfilAktualisieren(s, cfg, "dup-x-ac8", `{"display_name":"Neuer Name AC8"}`)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-8: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// --- AC-9 ---------------------------------------------------------------------

// AC-9 (Regressionswaechter, gewollt gruen im Altcode): mail_to auf leer
// setzen gelingt immer.
func TestProfilUpdateMailToLeerenGelingtImmer_AC9(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	speichereKonto(t, s, model.User{ID: "leer-ac9", MailTo: "leer-ac9-adresse@beispiel.de"})

	w := schreibpfadProfilAktualisieren(s, cfg, "leer-ac9", `{"mail_to":""}`)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-9: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if u := ladeKonto(t, s, "leer-ac9"); u.MailTo != "" {
		t.Errorf("AC-9: mail_to muss leer sein, ist %q", u.MailTo)
	}
}

// TestProfilUpdateMailToLeerenMachtUngepruefteEmailNichtBestaetigtWirksam:
// Regressionswaechter (PO-Korrektur nach Spec-Freigabe, Sicherheitsrueckschritt
// sonst) — ein bestaetigtes mail_to zu leeren darf die nie bestaetigte email
// NICHT als bestaetigte wirksame Kontaktadresse erscheinen lassen, sonst
// fuehrte ResolveAddressOwner sie faelschlich als bestaetigt. Leeren bleibt
// erlaubt (AC-9, Antwort 200). Seit Issue #2147 Scheibe B2 (AC-4) wird dafuer
// nicht mehr die Bestaetigung zurueckgesetzt: mail_to bleibt bis zum
// Bestaetigungslink stehen, die Aenderung wartet als ausstehend auf email.
func TestProfilUpdateMailToLeerenMachtUngepruefteEmailNichtBestaetigtWirksam(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	speichereKonto(t, s, model.User{
		ID: "leer-reset", Email: "b@beispiel.de", MailTo: "a@beispiel.de",
		EmailVerifiedAt: jetztBestaetigt(),
	})

	w := schreibpfadProfilAktualisieren(s, cfg, "leer-reset", `{"mail_to":""}`)

	if w.Code != http.StatusOK {
		t.Fatalf("erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	u := ladeKonto(t, s, "leer-reset")
	if u.EmailVerifiedAt != nil && store.EffectiveContactAddress(u) == "b@beispiel.de" {
		t.Errorf("die nie bestaetigte email wurde durch das Leeren bestaetigt wirksam (mail_to=%q)", u.MailTo)
	}
	if u.MailTo != "a@beispiel.de" {
		t.Errorf("B2/AC-4: mail_to muss bis zur Bestaetigung stehen bleiben, ist %q", u.MailTo)
	}
	if u.PendingContactAddress != "b@beispiel.de" || u.PendingContactField != "mail_to" {
		t.Errorf("B2/AC-4: das Leeren muss als ausstehend auf email warten, pending=%q field=%q",
			u.PendingContactAddress, u.PendingContactField)
	}
}

// --- AC-10 --------------------------------------------------------------------

// AC-10 (Regressionswaechter, gewollt gruen im Altcode): die eigene zweite
// Adresse uebernehmen bleibt erlaubt, obwohl die Zieladresse "belegt" ist —
// naemlich vom eigenen Konto.
func TestProfilUpdateEigeneZweitadresseUebernehmenBleibtErlaubt_AC10(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	speichereKonto(t, s, model.User{ID: "eigen-ac10", Email: "eigen-a-ac10@beispiel.de", MailTo: "eigen-b-ac10@beispiel.de"})

	w := schreibpfadProfilAktualisieren(s, cfg, "eigen-ac10", `{"mail_to":"eigen-a-ac10@beispiel.de"}`)

	if w.Code != http.StatusOK {
		t.Fatalf("AC-10: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	u := ladeKonto(t, s, "eigen-ac10")
	if u.Email != "eigen-a-ac10@beispiel.de" || u.MailTo != "eigen-a-ac10@beispiel.de" {
		t.Errorf("AC-10: beide Felder muessen jetzt gleich sein, email=%q mail_to=%q", u.Email, u.MailTo)
	}
}

// --- AC-11 --------------------------------------------------------------------

// AC-11: zwei Konten wollen gleichzeitig ihre Adresse auf die des jeweils
// anderen aendern -> keine Verklemmung, beide Antworten kommen eindeutig
// (200 oder 409) innerhalb der Testfrist zurueck.
//
// Hinweis (gewollt gruen moeglich): ohne jede Adress-Sperre kann es heute
// nicht verklemmen — der Nachweis traegt vor allem als kuenftiger
// Deadlock-Waechter, sobald B1 eine Sperre mit fester Lock-Reihenfolge
// einfuehrt (siehe red-notizen.md).
func TestProfilTauschGleichzeitigKeineVerklemmung_AC11(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	const nutzerA, nutzerB = "tausch-a-ac11", "tausch-b-ac11"
	const adresseA, adresseB = "adresse-a-ac11@beispiel.de", "adresse-b-ac11@beispiel.de"
	speichereKonto(t, s, model.User{ID: nutzerA, Email: adresseA, EmailVerifiedAt: jetztBestaetigt()})
	speichereKonto(t, s, model.User{ID: nutzerB, Email: adresseB, EmailVerifiedAt: jetztBestaetigt()})

	reqA := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(fmt.Sprintf(`{"email":%q}`, adresseB)))
	reqA = reqA.WithContext(middleware.ContextWithUserID(reqA.Context(), nutzerA))
	reqB := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(fmt.Sprintf(`{"email":%q}`, adresseA)))
	reqB = reqB.WithContext(middleware.ContextWithUserID(reqB.Context(), nutzerB))
	wA, wB := httptest.NewRecorder(), httptest.NewRecorder()

	fertig := make(chan struct{})
	go func() {
		start := make(chan struct{})
		var wg sync.WaitGroup
		wg.Add(2)
		go func() { defer wg.Done(); <-start; UpdateProfileHandler(s, cfg).ServeHTTP(wA, reqA) }()
		go func() { defer wg.Done(); <-start; UpdateProfileHandler(s, cfg).ServeHTTP(wB, reqB) }()
		close(start)
		wg.Wait()
		close(fertig)
	}()

	select {
	case <-fertig:
	case <-time.After(5 * time.Second):
		t.Fatalf("AC-11: kein Ergebnis innerhalb 5s — Verdacht auf Verklemmung")
	}

	gueltig := func(code int) bool { return code == http.StatusOK || code == http.StatusConflict }
	if !gueltig(wA.Code) || !gueltig(wB.Code) {
		t.Errorf("AC-11: beide Antworten muessen 200 oder 409 sein, bekommen A=%d %q / B=%d %q",
			wA.Code, wA.Body.String(), wB.Code, wB.Body.String())
	}
}

// --- AC-13 (F004 — die Sperre muss tragend sein) -------------------------------

// AC-13a: zwei gleichzeitige Registrierungen auf dieselbe, zu Beginn freie
// Adresse -> am Ende traegt genau EIN Konto die Adresse. Ohne Sperre schlaegt
// das schon in Runde 1 fehl (kein Lock im Altcode => beide Registrierungen
// gelingen).
func TestRegistrierungRaceAufFreieAdresseErgibtGenauEinenHalter_AC13(t *testing.T) {
	const runden = 200
	const adresse = "wettlauf-register-ac13@beispiel.de"
	cfg := config.Config{}
	for i := 0; i < runden; i++ {
		s := newTestStore(t)
		h := RegisterHandler(s, bcrypt.MinCost, cfg)
		unameA := fmt.Sprintf("wettlauf-a%d-ac13", i)
		unameB := fmt.Sprintf("wettlauf-b%d-ac13", i)
		bodyA := fmt.Sprintf(`{"username":%q,"password":%q,"email":%q}`, unameA, schreibpfadPasswort, adresse)
		bodyB := fmt.Sprintf(`{"username":%q,"password":%q,"email":%q}`, unameB, schreibpfadPasswort, adresse)
		reqA := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(bodyA))
		reqB := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(bodyB))
		wA, wB := httptest.NewRecorder(), httptest.NewRecorder()

		start := make(chan struct{})
		var wg sync.WaitGroup
		wg.Add(2)
		go func() { defer wg.Done(); <-start; h.ServeHTTP(wA, reqA) }()
		go func() { defer wg.Done(); <-start; h.ServeHTTP(wB, reqB) }()
		close(start)
		wg.Wait()

		erfolge := 0
		if wA.Code == http.StatusCreated {
			erfolge++
		}
		if wB.Code == http.StatusCreated {
			erfolge++
		}
		halter := schreibpfadAdresseHalterAnzahl(t, s, adresse)
		if erfolge != 1 || halter != 1 {
			t.Fatalf("AC-13a (Runde %d/%d): erwartet 1 Erfolg + 1 Adress-Halter, bekommen Erfolge=%d Halter=%d "+
				"(A=%d %q / B=%d %q)", i+1, runden, erfolge, halter, wA.Code, wA.Body.String(), wB.Code, wB.Body.String())
		}
	}
}

// AC-13b: Registrierung UND Profil-Update zielen gleichzeitig auf dieselbe,
// zu Beginn freie Adresse.
func TestRegistrierungGegenProfilUpdateRaceErgibtGenauEinenHalter_AC13(t *testing.T) {
	const runden = 200
	const adresse = "wettlauf-mix-ac13@beispiel.de"
	cfg := config.Config{}
	for i := 0; i < runden; i++ {
		s := newTestStore(t)
		bestandUID := fmt.Sprintf("bestand%d-ac13", i)
		speichereKonto(t, s, model.User{ID: bestandUID, Email: fmt.Sprintf("alt%d-ac13@beispiel.de", i)})
		regUID := fmt.Sprintf("neuling%d-ac13", i)

		regBody := fmt.Sprintf(`{"username":%q,"password":%q,"email":%q}`, regUID, schreibpfadPasswort, adresse)
		regReq := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(regBody))
		regW := httptest.NewRecorder()

		profReq := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(fmt.Sprintf(`{"email":%q}`, adresse)))
		profReq = profReq.WithContext(middleware.ContextWithUserID(profReq.Context(), bestandUID))
		profW := httptest.NewRecorder()

		start := make(chan struct{})
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			<-start
			RegisterHandler(s, bcrypt.MinCost, cfg).ServeHTTP(regW, regReq)
		}()
		go func() {
			defer wg.Done()
			<-start
			UpdateProfileHandler(s, cfg).ServeHTTP(profW, profReq)
		}()
		close(start)
		wg.Wait()

		erfolge := 0
		if regW.Code == http.StatusCreated {
			erfolge++
		}
		if profW.Code == http.StatusOK {
			erfolge++
		}
		halter := schreibpfadAdresseHalterAnzahl(t, s, adresse)
		if erfolge != 1 || halter != 1 {
			t.Fatalf("AC-13b (Runde %d/%d): erwartet 1 Erfolg + 1 Adress-Halter, bekommen Erfolge=%d Halter=%d "+
				"(Register=%d %q / Profil=%d %q)", i+1, runden, erfolge, halter,
				regW.Code, regW.Body.String(), profW.Code, profW.Body.String())
		}
	}
}

// --- AC-14 ---------------------------------------------------------------------

// AC-14: das Lesen einer fremden Kontodatei schlaegt waehrend der
// Belegt-Pruefung fehl (beschaedigte user.json) -> 500, nichts wird
// gespeichert, die geprueft Adresse steht nicht im Klartext im Log.
func TestRegistrierungMitUnlesbaremFremdkontoIstFailClosed_AC14(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	const defektID = "defekt-ac14-konto"
	dir := s.UserDir(defektID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	if err := os.WriteFile(dir+"/user.json", []byte("{das ist kein json"), 0644); err != nil {
		t.Fatalf("beschaedigte user.json schreiben: %v", err)
	}
	const adresse = "geprueft-ac14@beispiel.de"
	const neuerName = "neuling-ac14"

	var mitschnitt strings.Builder
	log.SetOutput(&logWriter{&mitschnitt})
	w := schreibpfadRegistrieren(s, cfg, neuerName, adresse)
	log.SetOutput(os.Stderr)

	if w.Code != http.StatusInternalServerError {
		t.Fatalf("AC-14: erwartet 500, bekommen %d: %s", w.Code, w.Body.String())
	}
	if s.UserExists(neuerName) {
		t.Errorf("AC-14: bei einem 500 darf kein Konto entstehen")
	}
	protokoll := strings.ToLower(mitschnitt.String())
	if strings.Contains(protokoll, "geprueft-ac14") {
		t.Errorf("AC-14: das Server-Log nennt die Adresse im Klartext: %q", mitschnitt.String())
	}
}

// --- F008 (Adversary-Finding, MEDIUM) -------------------------------------------

// F008: die Vorgaenger-Fassung dieses Tests (F001) verliess sich auf die
// zufaellige Map-Iterationsreihenfolge allein und fing eine entfernte
// sort.Strings(addrs)-Sortierung nur zeitglücksabhaengig (empirisch ~37 % in
// 8 Wiederholungen). Diese Fassung erzwingt die Kollisionslage stattdessen
// ueber die Test-Naht profileUpdateAfterFirstAddressLock (auth.go,
// wirkungslos wenn nil): jede Seite wartet dort — NACHDEM sie ihre erste
// Adresssperre genommen hat — auf eine Barriere, die erst freigibt, wenn auch
// die andere Seite ihre erste Sperre haelt (Notausgang 300ms).
//
// Mit sort.Strings(addrs) waehlen beide Seiten dieselbe erste Adresse: die
// unterlegene Seite blockiert schon im nativen Mutex von LockEmailAddress und
// erreicht die Naht gar nicht erst -> die Barriere bekommt nie zwei
// Ankuenfte, laeuft nach 300ms ab, beide Seiten laufen normal weiter (kein
// Fangschluss moeglich, weil identische Sperrreihenfolge algorithmisch
// deadlockfrei ist).
//
// Ohne Sortierung waehlt jede Seite ihre eigene, von der Map-Iteration
// zufaellig bestimmte Reihenfolge unter denselben vier Adressen. Mit
// Wahrscheinlichkeit 3/4 unterscheiden sich die ersten Adressen beider
// Seiten; die Barriere zwingt dann BEIDE Seiten, synchron in den Versuch zu
// laufen, die jeweils naechste (von der anderen Seite bereits gehaltene)
// Adresse zu sperren -> klassisches AB-BA-Verklemmungsmuster, garantiert,
// weil keine Seite vor vollstaendigem Erwerb aller vier Sperren etwas
// wieder freigibt. n unabhaengige Runden mit frischen Adressen je Runde
// druecken die Durchrutschquote auf (1/4)^n; bei n=20 also < 1e-11.
func TestProfilTauschZweiAdressenGleichzeitigOhneVerklemmung_F008(t *testing.T) {
	t.Cleanup(func() { profileUpdateAfterFirstAddressLock = nil })

	const runden = 20
	cfg := config.Config{}
	for i := 0; i < runden; i++ {
		s := newTestStore(t)
		nutzerA := fmt.Sprintf("zweisperre-a%d-f008", i)
		nutzerB := fmt.Sprintf("zweisperre-b%d-f008", i)
		a1 := fmt.Sprintf("a1-%d-f008@beispiel.de", i)
		a2 := fmt.Sprintf("a2-%d-f008@beispiel.de", i)
		b1 := fmt.Sprintf("b1-%d-f008@beispiel.de", i)
		b2 := fmt.Sprintf("b2-%d-f008@beispiel.de", i)
		speichereKonto(t, s, model.User{ID: nutzerA, Email: a1, MailTo: a2})
		speichereKonto(t, s, model.User{ID: nutzerB, Email: b1, MailTo: b2})

		// A tauscht auf B's Adressen, B tauscht auf A's Adressen — beide
		// Seiten muessen dieselben vier Adressen sperren, jeweils in ihrer
		// eigenen (bei fehlender Sortierung: zufaelligen) Reihenfolge.
		bodyA := fmt.Sprintf(`{"email":%q,"mail_to":%q}`, b1, b2)
		bodyB := fmt.Sprintf(`{"email":%q,"mail_to":%q}`, a1, a2)
		reqA := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(bodyA))
		reqA = reqA.WithContext(middleware.ContextWithUserID(reqA.Context(), nutzerA))
		reqB := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(bodyB))
		reqB = reqB.WithContext(middleware.ContextWithUserID(reqB.Context(), nutzerB))
		wA, wB := httptest.NewRecorder(), httptest.NewRecorder()

		// Barriere: genau zwei Ankuenfte loesen sofort aus, sonst Notausgang
		// nach 300ms (deckt den Fall ab, dass nur eine Seite die Naht ueberhaupt
		// erreicht — s.o., sortierter Normalfall).
		var angekommen int32
		barriere := make(chan struct{})
		profileUpdateAfterFirstAddressLock = func(_ string) {
			if atomic.AddInt32(&angekommen, 1) == 2 {
				close(barriere)
			}
			select {
			case <-barriere:
			case <-time.After(300 * time.Millisecond):
			}
		}

		fertig := make(chan struct{})
		go func() {
			start := make(chan struct{})
			var wg sync.WaitGroup
			wg.Add(2)
			go func() { defer wg.Done(); <-start; UpdateProfileHandler(s, cfg).ServeHTTP(wA, reqA) }()
			go func() { defer wg.Done(); <-start; UpdateProfileHandler(s, cfg).ServeHTTP(wB, reqB) }()
			close(start)
			wg.Wait()
			close(fertig)
		}()

		select {
		case <-fertig:
		case <-time.After(2 * time.Second):
			t.Fatalf("F008 (Runde %d/%d): kein Ergebnis innerhalb 2s NACH erzwungener "+
				"Erst-Sperr-Barriere — Verklemmung (fehlende Sortierung der Adress-Sperrreihenfolge). "+
				"Keine weitere Runde auf diesen Adressen — Test bricht sofort ab.", i+1, runden)
		}

		gueltig := func(code int) bool { return code == http.StatusOK || code == http.StatusConflict }
		if !gueltig(wA.Code) || !gueltig(wB.Code) {
			t.Fatalf("F008 (Runde %d/%d): beide Antworten muessen 200 oder 409 sein, bekommen A=%d %q / B=%d %q",
				i+1, runden, wA.Code, wA.Body.String(), wB.Code, wB.Body.String())
		}

		// Selbstpruefung der Naht: ohne genau zwei Ankuenfte an der Barriere
		// wurde die erzwungene Kollisionslage NICHT hergestellt — der Test
		// wuerde dann nichts mehr bewachen (z.B. wenn die Naht versehentlich
		// erst nach der zweiten statt nach der ersten Sperre feuert).
		if got := atomic.LoadInt32(&angekommen); got != 2 {
			t.Fatalf("F008 (Runde %d/%d): Naht feuerte %d mal statt 2 — die erzwungene "+
				"Kollisionslage wurde nicht hergestellt, der Test bewacht nichts", i+1, runden, got)
		}
	}
}

// --- F002 (Adversary-Finding, HIGH) — AC-14-Analogtests fuer Profil und Passkey ----

// F002/Profil: Lesefehler bei einem fremden Konto waehrend der Belegt-Pruefung
// eines Profil-Updates -> 500, nichts gespeichert, kein Klartext im Log.
// Subtests fuer beide betroffenen Codezweige (email UND mail_to).
func TestProfilUpdateMitUnlesbaremFremdkontoIstFailClosed_F002(t *testing.T) {
	faelle := []struct {
		name string
		body func(adresse string) string
	}{
		{"email", func(a string) string { return fmt.Sprintf(`{"email":%q}`, a) }},
		{"mail_to", func(a string) string { return fmt.Sprintf(`{"mail_to":%q}`, a) }},
	}
	for i, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := newTestStore(t)
			cfg := config.Config{}
			uid := fmt.Sprintf("profil-f002-%d", i)
			speichereKonto(t, s, model.User{
				ID:     uid,
				Email:  fmt.Sprintf("alt-f002-%d@beispiel.de", i),
				MailTo: fmt.Sprintf("altmt-f002-%d@beispiel.de", i),
			})
			vorher := rohesKonto(t, s, uid)

			defektID := fmt.Sprintf("defekt-f002-%d", i)
			dir := s.UserDir(defektID)
			if err := os.MkdirAll(dir, 0755); err != nil {
				t.Fatalf("MkdirAll: %v", err)
			}
			if err := os.WriteFile(dir+"/user.json", []byte("{das ist kein json"), 0644); err != nil {
				t.Fatalf("beschaedigte user.json schreiben: %v", err)
			}
			adresse := fmt.Sprintf("geprueft-f002-%d@beispiel.de", i)

			var mitschnitt strings.Builder
			log.SetOutput(&logWriter{&mitschnitt})
			w := schreibpfadProfilAktualisieren(s, cfg, uid, f.body(adresse))
			log.SetOutput(os.Stderr)

			if w.Code != http.StatusInternalServerError {
				t.Fatalf("F002/Profil/%s: erwartet 500, bekommen %d: %s", f.name, w.Code, w.Body.String())
			}
			if string(vorher) != string(rohesKonto(t, s, uid)) {
				t.Errorf("F002/Profil/%s: bei 500 darf NICHTS gespeichert werden — user.json muss byteidentisch bleiben", f.name)
			}
			protokoll := strings.ToLower(mitschnitt.String())
			if strings.Contains(protokoll, fmt.Sprintf("geprueft-f002-%d", i)) {
				t.Errorf("F002/Profil/%s: das Server-Log nennt die Adresse im Klartext: %q", f.name, mitschnitt.String())
			}
		})
	}
}

// F002/PasskeyBegin: dieselbe Belegt-Pruefung laeuft auch im Begin-Schritt der
// oeffentlichen Passkey-Registrierung — ein Lesefehler dabei muss ebenfalls
// fail-closed sein, ohne dass eine Challenge erzeugt wird.
func TestPasskeyPublicBeginMitUnlesbaremFremdkontoIstFailClosed_F002(t *testing.T) {
	s := newTestStore(t)
	rpID, origin := "localhost", "http://localhost"
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()

	const defektID = "defekt-f002-begin"
	dir := s.UserDir(defektID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	if err := os.WriteFile(dir+"/user.json", []byte("{das ist kein json"), 0644); err != nil {
		t.Fatalf("beschaedigte user.json schreiben: %v", err)
	}
	const adresse = "geprueft-f002-begin@beispiel.de"

	var mitschnitt strings.Builder
	log.SetOutput(&logWriter{&mitschnitt})
	body := fmt.Sprintf(`{"username":"neuling-f002-begin","email":%q}`, adresse)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/begin", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(w, req)
	log.SetOutput(os.Stderr)

	if w.Code != http.StatusInternalServerError {
		t.Fatalf("F002/PasskeyBegin: erwartet 500, bekommen %d: %s", w.Code, w.Body.String())
	}
	if n := schreibpfadChallengeAnzahl(cs); n != 0 {
		t.Errorf("F002/PasskeyBegin: bei 500 darf keine Challenge erzeugt worden sein, vorhanden: %d", n)
	}
	protokoll := strings.ToLower(mitschnitt.String())
	if strings.Contains(protokoll, "geprueft-f002-begin") {
		t.Errorf("F002/PasskeyBegin: das Server-Log nennt die Adresse im Klartext: %q", mitschnitt.String())
	}
}

// F002/PasskeyFinish: die im Begin-Schritt hinterlegte Adresse wird im
// Finish-Schritt erneut geprueft — erscheint zwischenzeitlich ein unlesbares
// fremdes Konto, muss das ebenfalls fail-closed sein, ohne dass ein Konto
// oder Credential entsteht.
func TestPasskeyPublicFinishMitUnlesbaremFremdkontoIstFailClosed_F002(t *testing.T) {
	s := newTestStore(t)
	rpID, origin := "localhost", "http://localhost"
	wa := newTestWebAuthn(t, rpID, origin)
	cs := NewChallengeStore()
	secret := "test-secret-32-chars-long-enough"
	cfg := config.Config{}
	const username = "urspruenglich-f002-finish"
	const adresse = "geprueft-f002-finish@beispiel.de"

	beginBody := fmt.Sprintf(`{"username":%q,"email":%q}`, username, adresse)
	beginReq := httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/begin", strings.NewReader(beginBody))
	beginW := httptest.NewRecorder()
	PasskeyRegisterPublicBeginHandler(s, wa, cs).ServeHTTP(beginW, beginReq)
	if beginW.Code != http.StatusOK {
		t.Fatalf("F002/PasskeyFinish Begin: erwartet 200, bekommen %d: %s", beginW.Code, beginW.Body.String())
	}
	var beginResp struct {
		PublicKey struct {
			Challenge string `json:"challenge"`
		} `json:"publicKey"`
	}
	if err := json.Unmarshal(beginW.Body.Bytes(), &beginResp); err != nil {
		t.Fatalf("F002/PasskeyFinish Begin decode: %v", err)
	}

	// Zwischenzeitlich erscheint ein unlesbares fremdes Konto.
	const defektID = "defekt-f002-finish"
	dir := s.UserDir(defektID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	if err := os.WriteFile(dir+"/user.json", []byte("{das ist kein json"), 0644); err != nil {
		t.Fatalf("beschaedigte user.json schreiben: %v", err)
	}

	auth := newTestAuthenticator(t, rpID, origin)
	finishBody := auth.makeAttestationResponse(t, beginResp.PublicKey.Challenge)

	var mitschnitt strings.Builder
	log.SetOutput(&logWriter{&mitschnitt})
	finishReq := httptest.NewRequest(http.MethodPost, "/api/auth/passkey/register/public/finish", bytes.NewReader(finishBody))
	finishW := httptest.NewRecorder()
	PasskeyRegisterPublicFinishHandler(s, wa, cs, secret, cfg).ServeHTTP(finishW, finishReq)
	log.SetOutput(os.Stderr)

	if finishW.Code != http.StatusInternalServerError {
		t.Fatalf("F002/PasskeyFinish: erwartet 500, bekommen %d: %s", finishW.Code, finishW.Body.String())
	}
	if s.UserExists(username) {
		t.Errorf("F002/PasskeyFinish: bei 500 darf kein Konto entstanden sein")
	}
	protokoll := strings.ToLower(mitschnitt.String())
	if strings.Contains(protokoll, "geprueft-f002-finish") {
		t.Errorf("F002/PasskeyFinish: das Server-Log nennt die Adresse im Klartext: %q", mitschnitt.String())
	}
}

// --- F003 (Adversary-Finding, MEDIUM) ------------------------------------------

// F003: eine geaenderte Adresse wird auch am Profil-Pfad normalisiert
// gespeichert (nicht nur bei der Registrierung, AC-1) — Gross-/Kleinschreibung
// und Randleerzeichen fallen weg, fuer email UND mail_to.
func TestProfilUpdateSpeichertNormalisierteAdresse_F003(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	speichereKonto(t, s, model.User{ID: "profil-f003", Email: "alt-f003@beispiel.de", MailTo: "altmt-f003@beispiel.de"})

	w := schreibpfadProfilAktualisieren(s, cfg, "profil-f003", `{"email":" Neu@X.De ","mail_to":" Zwei@Y.De "}`)

	if w.Code != http.StatusOK {
		t.Fatalf("F003: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	u := ladeKonto(t, s, "profil-f003")
	if u.Email != "neu@x.de" {
		t.Errorf("F003: email muss normalisiert gespeichert sein, ist %q", u.Email)
	}
	if u.MailTo != "zwei@y.de" {
		t.Errorf("F003: mail_to muss normalisiert gespeichert sein, ist %q", u.MailTo)
	}
}

// --- F005 (Adversary-Finding, MEDIUM) — dritte Race-Paarung aus Spec Section 5 ----

// F005: Spec Section 5 (F004 "die Sperre muss tragend sein") nennt drei
// Race-Paarungen: Registrierung/Registrierung (AC-13a), Registrierung/Profil
// (AC-13b) und Profil/Profil — letztere fehlte im Testfile. Zwei verschiedene
// Konten aendern per Profil-Update gleichzeitig ihre Adresse auf dieselbe,
// anfangs freie Zieladresse -> zusammen darf nur genau ein Konto sie tragen.
func TestProfilUpdateRaceAufFreieAdresseErgibtGenauEinenHalter_F005(t *testing.T) {
	const runden = 200
	const zieladresse = "wettlauf-profil-f005@beispiel.de"
	cfg := config.Config{}
	for i := 0; i < runden; i++ {
		s := newTestStore(t)
		uidA := fmt.Sprintf("profilrace-a%d-f005", i)
		uidB := fmt.Sprintf("profilrace-b%d-f005", i)
		speichereKonto(t, s, model.User{ID: uidA, Email: fmt.Sprintf("alt-a%d-f005@beispiel.de", i)})
		speichereKonto(t, s, model.User{ID: uidB, Email: fmt.Sprintf("alt-b%d-f005@beispiel.de", i)})

		reqA := httptest.NewRequest(http.MethodPut, "/api/auth/profile",
			strings.NewReader(fmt.Sprintf(`{"email":%q}`, zieladresse)))
		reqA = reqA.WithContext(middleware.ContextWithUserID(reqA.Context(), uidA))
		reqB := httptest.NewRequest(http.MethodPut, "/api/auth/profile",
			strings.NewReader(fmt.Sprintf(`{"email":%q}`, zieladresse)))
		reqB = reqB.WithContext(middleware.ContextWithUserID(reqB.Context(), uidB))
		wA, wB := httptest.NewRecorder(), httptest.NewRecorder()

		start := make(chan struct{})
		var wg sync.WaitGroup
		wg.Add(2)
		go func() { defer wg.Done(); <-start; UpdateProfileHandler(s, cfg).ServeHTTP(wA, reqA) }()
		go func() { defer wg.Done(); <-start; UpdateProfileHandler(s, cfg).ServeHTTP(wB, reqB) }()
		close(start)
		wg.Wait()

		erfolge := 0
		if wA.Code == http.StatusOK {
			erfolge++
		}
		if wB.Code == http.StatusOK {
			erfolge++
		}
		halter := schreibpfadAdresseHalterAnzahl(t, s, zieladresse)
		if erfolge != 1 || halter != 1 {
			t.Fatalf("F005 (Runde %d/%d): erwartet 1 Erfolg + 1 Adress-Halter, bekommen Erfolge=%d Halter=%d "+
				"(A=%d %q / B=%d %q)", i+1, runden, erfolge, halter, wA.Code, wA.Body.String(), wB.Code, wB.Body.String())
		}
	}
}

// logWriter adaptiert strings.Builder auf io.Writer (kein externer Import noetig).
type logWriter struct{ b *strings.Builder }

func (w *logWriter) Write(p []byte) (int, error) { return w.b.Write(p) }

// --- F006 (Adversary-Finding, Fix-Loop) — Reload muss WIRKEN, nicht nur da sein ----

// TestProfilUpdateBehaeltZwischenzeitAenderungDankFrischemReload_F006: der
// Adversary fand, dass der Reload in UpdateProfileHandler (auth.go, "Read-
// Modify-Write: das eigene Konto FRISCH laden") kommentarlos entfernbar ist,
// ohne dass ein Test rot wird. Dieser Test macht die TOCTOU-Absicherung (Spec
// §3, Zeile 107-111) am WIRKORT beobachtbar: zwischen dem urspruenglichen
// Laden (Funktionsanfang) und dem Neuladen INNERHALB der Adress-Sperre
// schreibt eine zweite, unabhaengige Anfrage (kein Adressfeld, deshalb ohne
// Sperre moeglich) den display_name desselben Kontos. Die aktuelle Anfrage
// aendert NUR die E-Mail-Adresse — display_name ist in ihrem Request-Body gar
// nicht enthalten. Ohne frischen Reload speichert sie trotzdem den VERALTETEN
// display_name aus ihrem eigenen Anfangs-Load zurueck und macht die
// Zwischenzeit-Aenderung ungeschehen (Datenverlust). Zwei Nutzer: das
// betroffene Konto und ein unbeteiligtes Bystander-Konto, das unberuehrt
// bleiben muss.
func TestProfilUpdateBehaeltZwischenzeitAenderungDankFrischemReload_F006(t *testing.T) {
	t.Cleanup(func() { profileUpdateBeforeFreshReload = nil })
	s := newTestStore(t)
	cfg := config.Config{}
	const uid = "reload-f006"
	const bystanderUID = "bystander-f006"
	const alteAdresse = "alt-reload-f006@beispiel.de"
	const neueAdresse = "neu-reload-f006@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: alteAdresse, DisplayName: "Alt-Name-F006"})
	speichereKonto(t, s, model.User{ID: bystanderUID, Email: "bystander-f006@beispiel.de"})
	vorherBystander := rohesKonto(t, s, bystanderUID)

	profileUpdateBeforeFreshReload = func(userID string) {
		if userID != uid {
			return
		}
		u, err := s.LoadUser(userID)
		if err != nil || u == nil {
			t.Fatalf("F006: Zwischenzeit-Laden fehlgeschlagen: %v", err)
		}
		u.DisplayName = "Zwischenzeit-Name-F006"
		if err := s.SaveUser(*u); err != nil {
			t.Fatalf("F006: Zwischenzeit-Speichern fehlgeschlagen: %v", err)
		}
	}

	w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"email":%q}`, neueAdresse))

	if w.Code != http.StatusOK {
		t.Fatalf("F006: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	nachher := ladeKonto(t, s, uid)
	if nachher.Email != neueAdresse {
		t.Errorf("F006: email muss normalisiert die neue Adresse tragen, ist %q", nachher.Email)
	}
	if nachher.DisplayName != "Zwischenzeit-Name-F006" {
		t.Errorf("F006: der zwischenzeitlich gesetzte display_name darf NICHT durch einen veralteten "+
			"Stand ueberschrieben werden — ist %q, erwartet \"Zwischenzeit-Name-F006\"", nachher.DisplayName)
	}
	if string(vorherBystander) != string(rohesKonto(t, s, bystanderUID)) {
		t.Errorf("F006: das Bystander-Konto darf nicht veraendert werden")
	}
}

// --- F007 (Adversary-Finding, Fix-Loop) — addrSet-Dedup verhindert Selbst-Verklemmung ----

// TestProfilUpdateEmailUndMailToAufDieselbeNeueAdresseVerklemmtNicht_F007: die
// Sperrmenge in UpdateProfileHandler wird ueber eine Map (addrSet) gebildet,
// bevor sie sortiert und der Reihe nach gesperrt wird. Setzt eine Anfrage
// email UND mail_to im selben Aufruf auf DIESELBE neue (bislang freie)
// Adresse, taucht diese Adresse ohne die Map-Dedup ZWEIMAL in der Sperrliste
// auf — store.LockEmailAddress nutzt einen nicht-reentranten sync.Mutex
// (address_lock.go), ein zweiter Lock-Aufruf auf dieselbe Adresse IM SELBEN
// Goroutine haengt fuer immer. Kein bestehender Test schickt email UND
// mail_to gleichzeitig auf denselben neuen Wert. Der Handler laeuft in einer
// Goroutine mit explizitem Timeout, damit ein Scheitern den Testlauf nicht
// blockiert (t.Fatal statt Haengenbleiben).
func TestProfilUpdateEmailUndMailToAufDieselbeNeueAdresseVerklemmtNicht_F007(t *testing.T) {
	s := newTestStore(t)
	cfg := config.Config{}
	const uid = "dedup-f007"
	const neueAdresse = "gemeinsam-neu-f007@beispiel.de"
	speichereKonto(t, s, model.User{
		ID: uid, Email: "alt-email-f007@beispiel.de", MailTo: "alt-mailto-f007@beispiel.de",
	})

	body := fmt.Sprintf(`{"email":%q,"mail_to":%q}`, neueAdresse, neueAdresse)
	fertig := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		fertig <- schreibpfadProfilAktualisieren(s, cfg, uid, body)
	}()

	var w *httptest.ResponseRecorder
	select {
	case w = <-fertig:
	case <-time.After(2 * time.Second):
		t.Fatalf("F007: kein Ergebnis innerhalb 2s — Verdacht auf Selbst-Verklemmung " +
			"(email und mail_to sperren dieselbe neue Adresse zweimal)")
	}

	if w.Code != http.StatusOK {
		t.Fatalf("F007: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	nachher := ladeKonto(t, s, uid)
	if nachher.Email != neueAdresse || nachher.MailTo != neueAdresse {
		t.Errorf("F007: email und mail_to muessen beide normalisiert die neue Adresse tragen, "+
			"email=%q mail_to=%q", nachher.Email, nachher.MailTo)
	}
}
