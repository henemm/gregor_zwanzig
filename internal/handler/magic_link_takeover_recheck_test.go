package handler

// TDD RED — Issue #2147 Scheibe B1 (F003-Nachschaerfung), AC-12: die
// Magic-Link-Uebernahme eines zugangslosen, unbestaetigten Kontos muss das
// frisch geladene Konto ERNEUT pruefen, bevor die Uebernahme gespeichert
// wird — nicht nur einmal laden und blind fortfahren.
// Spec: docs/specs/modules/adress_eindeutigkeit_schreibpfade.md §4, AC-12.
//
// Test-Naht (noch nicht vorhanden, siehe auth_magic.go:214-235):
// Paket-Variable `magicLinkBeforeTakeoverReload func(userID string)`, im
// Normalbetrieb nil. Diese Datei referenziert das Symbol bewusst, BEVOR es
// existiert — der Compile-Fehler IST der RED-Nachweis fuer AC-12
// (docs/artifacts/fix-2147-b-adress-eindeutig/test-red-takeover-compile.txt).
// Package-Zugehoerigkeit wie magic_link_address_ownership_test.go: der
// Uebernahmepfad haengt am paketprivaten otpStore/resolveMagicLinkAccount.
//
// Solange diese Datei im Paket liegt, kompiliert `internal/handler` NICHT —
// sie gehoert waehrend anderer Test-/Build-Laeufe in den Scratchpad
// (siehe red-notizen.md) und erst zur Implementierung zurueck ins Repo.

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
)

// AC-12 Fall 1: zwischen Zuordnung und Neuladen erhaelt das Konto einen Passkey.
func TestMagicLinkUebernahmePruefteErneutBeiZugangsdatenZwischenzeit_AC12(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	cfg := eindeutigCfg()
	const uid = "u-zwischenzeit-ac12"
	const adresse = "zwischenzeit-ac12@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: adresse, MailTo: adresse})

	orig := magicLinkBeforeTakeoverReload
	magicLinkBeforeTakeoverReload = func(userID string) {
		if userID != uid {
			return
		}
		u, err := s.LoadUser(userID)
		if err != nil || u == nil {
			t.Fatalf("AC-12: Zwischenzeit-Laden fehlgeschlagen: %v", err)
		}
		u.PasskeyCredentials = []model.WebAuthnCredential{{
			ID: []byte{1, 2, 3}, PublicKey: []byte{4, 5, 6}, AttestationType: "none",
		}}
		if err := s.SaveUser(*u); err != nil {
			t.Fatalf("AC-12: Zwischenzeit-Speichern fehlgeschlagen: %v", err)
		}
	}
	t.Cleanup(func() { magicLinkBeforeTakeoverReload = orig })

	w := einloesen(s, cfg, adresse, anfordern(t, s, cfg, adresse))

	pruefeNeutraleAbweisung(t, "AC-12/passkey", w)
	nachher := ladeKonto(t, s, uid)
	if nachher.EmailVerifiedAt != nil {
		t.Errorf("AC-12/passkey: email_verified_at darf NICHT gesetzt sein")
	}
	if len(nachher.PasskeyCredentials) != 1 {
		t.Errorf("AC-12/passkey: der zwischenzeitlich angelegte Passkey darf nicht verschwinden")
	}
}

// AC-12 Fall 2: zwischen Zuordnung und Neuladen aendert sich die Kontaktadresse.
func TestMagicLinkUebernahmePruefteErneutBeiAdressWechselZwischenzeit_AC12(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	cfg := eindeutigCfg()
	const uid = "u-adresswechsel-ac12"
	const adresse = "adresswechsel-ac12@beispiel.de"
	const andereAdresse = "andere-ac12@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: adresse, MailTo: adresse})

	orig := magicLinkBeforeTakeoverReload
	magicLinkBeforeTakeoverReload = func(userID string) {
		if userID != uid {
			return
		}
		u, err := s.LoadUser(userID)
		if err != nil || u == nil {
			t.Fatalf("AC-12: Zwischenzeit-Laden fehlgeschlagen: %v", err)
		}
		u.MailTo = andereAdresse
		u.Email = andereAdresse
		if err := s.SaveUser(*u); err != nil {
			t.Fatalf("AC-12: Zwischenzeit-Speichern fehlgeschlagen: %v", err)
		}
	}
	t.Cleanup(func() { magicLinkBeforeTakeoverReload = orig })

	w := einloesen(s, cfg, adresse, anfordern(t, s, cfg, adresse))

	pruefeNeutraleAbweisung(t, "AC-12/adresswechsel", w)
	nachher := ladeKonto(t, s, uid)
	if nachher.EmailVerifiedAt != nil {
		t.Errorf("AC-12/adresswechsel: email_verified_at darf nach der abgewiesenen Uebernahme nicht gesetzt sein")
	}
	if nachher.MailTo != andereAdresse || !strings.Contains(nachher.MailTo, "andere-ac12") {
		t.Errorf("AC-12/adresswechsel: die zwischenzeitliche Adressaenderung darf nicht rueckgaengig gemacht werden, mail_to=%q",
			nachher.MailTo)
	}
}

// F004 (Adversary-Finding, MEDIUM): Spec §3 verlangt, dass die ALTE Adresse
// eines geaenderten Profil-Felds mit in die Sperrmenge gehoert — sie wird
// gerade frei. Dieser Test macht das deterministisch beobachtbar ueber die
// vorhandene Test-Naht magicLinkBeforeTakeoverReload: waehrend die
// Magic-Link-Uebernahme eines zugangslosen, unbestaetigten Kontos die Sperre
// auf dessen ALTE (wirksame) Adresse haelt, versucht ein Profil-Update
// desselben Kontos, mail_to von genau dieser alten auf eine neue Adresse zu
// aendern. Haelt das Profil-Update die alte Adresse ebenfalls mit (Spec §3),
// MUSS dieser Aufruf blockieren, bis die Uebernahme fertig ist — er darf
// nicht durchlaufen, waehrend die Uebernahme die Sperre noch haelt. Faellt
// die alte Adresse aus der Sperrmenge (Mutation), braucht das Profil-Update
// nur noch die (freie) neue Adresse zu sperren und laeuft sofort durch, ohne
// auf die Uebernahme zu warten — genau das faengt dieser Test.
func TestProfilAdressWechselWartetAufAlteSperreWaehrendMagicLinkUebernahme_F004(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	magicCfg := eindeutigCfg()
	profilCfg := config.Config{}
	const uid = "u-f004"
	const alteAdresse = "alte-f004@beispiel.de"
	const neueAdresse = "neue-f004@beispiel.de"
	// Email leer -> die wirksame Kontaktadresse ist mail_to (alteAdresse).
	speichereKonto(t, s, model.User{ID: uid, MailTo: alteAdresse})

	ownerResolved := make(chan struct{})
	proceed := make(chan struct{})
	orig := magicLinkBeforeTakeoverReload
	magicLinkBeforeTakeoverReload = func(userID string) {
		if userID != uid {
			return
		}
		close(ownerResolved)
		<-proceed
	}
	t.Cleanup(func() { magicLinkBeforeTakeoverReload = orig })

	code := anfordern(t, s, magicCfg, alteAdresse)
	magicLinkFertig := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		magicLinkFertig <- einloesen(s, magicCfg, alteAdresse, code)
	}()

	select {
	case <-ownerResolved:
	case <-time.After(2 * time.Second):
		t.Fatalf("F004: Magic-Link-Uebernahme hat die Test-Naht nicht erreicht")
	}

	// Waehrend die Uebernahme die Sperre auf die ALTE Adresse haelt, versucht
	// ein Profil-Update, mail_to auf eine neue Adresse zu aendern.
	profilFertig := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		profilFertig <- schreibpfadProfilAktualisieren(s, profilCfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neueAdresse))
	}()

	select {
	case <-profilFertig:
		t.Fatalf("F004: Profil-Update hat NICHT auf die Sperre der alten Adresse gewartet — " +
			"es lief durch, waehrend die Magic-Link-Uebernahme sie noch hielt")
	case <-time.After(150 * time.Millisecond):
		// erwartet: noch blockiert, siehe Funktionskommentar.
	}

	close(proceed)

	var profilW *httptest.ResponseRecorder
	select {
	case profilW = <-profilFertig:
	case <-time.After(2 * time.Second):
		t.Fatalf("F004: Profil-Update kam nach Freigabe der Sperre nicht zu einem Ergebnis")
	}
	if profilW.Code != http.StatusOK {
		t.Errorf("F004: Profil-Update nach Freigabe erwartet 200, bekommen %d: %s", profilW.Code, profilW.Body.String())
	}

	select {
	case <-magicLinkFertig:
	case <-time.After(2 * time.Second):
		t.Fatalf("F004: Magic-Link-Uebernahme kam nicht zu einem Ergebnis")
	}
}
