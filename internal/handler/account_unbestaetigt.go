package handler

// Unbestaetigte Anmeldungen (Issue #2961, GA2, ADR-0115). Wer eine fremde
// Adresse registriert, ohne sie bestaetigen zu koennen, darf damit weder die
// Adresse blockieren noch Zugangsdaten fuer das spaetere Konto des echten
// Inhabers hinterlegen:
//   (a) eine neue Registrierung fuer dieselbe Adresse ersetzt solche Konten
//       (replaceUnconfirmedHolders);
//   (b) der Reaper raeumt sie, wenn ihr Bestaetigungstoken seit mehr als 24
//       Stunden abgelaufen ist (reapUnconfirmedAccounts).
// Was als unbestaetigte Anmeldung gilt, entscheidet store.IsUnconfirmedSignup
// (konservativ: Bestand von vor der Bestaetigungspflicht, Testkonten und
// Konten ohne Token sind nie betroffen). Bestandsdaten bleiben erhalten: nur
// ein Kontoordner OHNE Nutzinhalte (store.IsAccountDirPristine) wird behandelt,
// und auch der wird nicht geloescht, sondern in die Ablage verschoben
// (store.QuarantineUser) und erst nach 30 Tagen endgueltig entfernt.

import (
	"errors"
	"log"
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// unconfirmedGrace: so lange nach Ablauf des Bestaetigungstokens bleibt eine
// unbestaetigte Anmeldung noch stehen.
const unconfirmedGrace = 24 * time.Hour

// quarantineUnconfirmed raeumt die prozessinternen Reste (Login-Codes,
// Lösch-/Nachweis-Codes) und verschiebt den Kontoordner in die Ablage.
// Telegram-Tokens kann ein nie angemeldetes Konto nicht haben.
func quarantineUnconfirmed(s *store.Store, u *model.User, now time.Time) error {
	if _, err := s.QuarantineUser(u.ID, now); err != nil {
		return err
	}
	removeLoginOTPs(u.Email, u.MailTo, u.PendingContactAddress)
	deleteCodeStore.Delete(u.ID)
	reauthCodeStore.Delete(u.ID)
	return nil
}

// maskiereKennung kuerzt eine Kontokennung fuer Warn-Logzeilen.
func maskiereKennung(id string) string {
	if len(id) <= 4 {
		return "***"
	}
	return id[:4] + "***"
}

// ersetzungsAbstand: eine Adresse, deren unbestaetigte Anmeldung ersetzt
// wurde, kann fruehestens danach erneut ersetzt werden (Bremse je Zieladresse,
// sonst koennten sich zwei Registrierungen beliebig oft gegenseitig verdraengen).
const ersetzungsAbstand = time.Hour

var ersetzungen = struct {
	sync.Mutex
	letzte map[string]time.Time
}{letzte: map[string]time.Time{}}

func ersetzenErlaubt(address string, now time.Time) bool {
	ersetzungen.Lock()
	defer ersetzungen.Unlock()
	for a, t := range ersetzungen.letzte { // klein halten
		if now.Sub(t) >= ersetzungsAbstand {
			delete(ersetzungen.letzte, a)
		}
	}
	t, ok := ersetzungen.letzte[address]
	return !ok || now.Sub(t) >= ersetzungsAbstand
}

func merkeErsetzung(address string, now time.Time) {
	ersetzungen.Lock()
	defer ersetzungen.Unlock()
	ersetzungen.letzte[address] = now
}

// planUnconfirmedReplacement prueft OHNE etwas zu aendern, ob eine
// Registrierung die Halter von address verdraengen darf: alle Halter sind
// leere unbestaetigte Anmeldungen und die Bremse je Zieladresse laesst es zu.
// Der Aufrufer haelt LockEmailAddress(address).
func planUnconfirmedReplacement(s *store.Store, address string, now time.Time) ([]*model.User, bool, error) {
	holders, all, err := s.ReplaceableAddressHolders(address)
	if err != nil || !all {
		return nil, false, err
	}
	if !ersetzenErlaubt(address, now) {
		return nil, false, nil
	}
	return holders, true, nil
}

// verdraengeUnbestaetigte verschiebt die geplanten Halter in die Ablage —
// erst unmittelbar vor der Kontoanlage, nachdem alle Pruefungen bestanden
// sind. Die Rueckgabe holt sie zurueck, falls die Anlage danach scheitert.
// Scheitert ein Verschieben, sind die bereits verschobenen schon zurueck.
func verdraengeUnbestaetigte(s *store.Store, holders []*model.User, now time.Time) (zurueck func(), err error) {
	type verschoben struct{ id, ziel string }
	var erledigt []verschoben
	zurueck = func() {
		for _, v := range erledigt {
			if rerr := s.RestoreFromAblage(v.id, v.ziel); rerr != nil {
				log.Printf("register: verdraengte Anmeldung %s nicht zurueckgeholt: %v", maskiereKennung(v.id), rerr)
			}
		}
	}
	for _, u := range holders {
		ziel, qerr := s.QuarantineUser(u.ID, now)
		if qerr != nil {
			zurueck()
			return nil, qerr
		}
		removeLoginOTPs(u.Email, u.MailTo, u.PendingContactAddress)
		deleteCodeStore.Delete(u.ID)
		reauthCodeStore.Delete(u.ID)
		erledigt = append(erledigt, verschoben{u.ID, ziel})
	}
	return zurueck, nil
}

// istVerdraengenAbgelehnt: das Verschieben scheiterte, weil sich ein Halter
// inzwischen veraendert hat — fachlich „Adresse vergeben“, kein Serverfehler.
func istVerdraengenAbgelehnt(err error) bool {
	return errors.Is(err, store.ErrAccountDirNotPristine) || errors.Is(err, store.ErrNotUnconfirmedSignup)
}

// addressFreeForSignup: Adresse frei oder nur von leeren unbestaetigten
// Anmeldungen gehalten, die ersetzt werden duerfen (Vorpruefung ohne
// Aenderung, Passkey-Registrierung Schritt 1).
func addressFreeForSignup(s *store.Store, address string) (bool, error) {
	taken, err := s.IsAddressTakenByOtherAccount(address, "")
	if err != nil {
		return false, err
	}
	if !taken {
		return true, nil
	}
	_, ok, err := planUnconfirmedReplacement(s, store.NormalizeEmailAddress(address), time.Now())
	return ok && err == nil, err
}

// reapUnconfirmedAccounts verschiebt leere unbestaetigte Anmeldungen, deren
// Token seit mehr als unconfirmedGrace abgelaufen ist, in die Ablage und
// entfernt Ablage-Eintraege, die aelter als 30 Tage sind. Nicht leere Ordner
// bleiben mit Warn-Logzeile stehen. Rueckgabe: Anzahl verschobener Konten.
func reapUnconfirmedAccounts(s *store.Store, now time.Time) int {
	ids, err := s.ListUserIDs()
	if err != nil {
		log.Printf("reaper: Kontoliste nicht lesbar: %v", err)
		return 0
	}
	verschoben := 0
	for _, id := range ids {
		if reapOneUnconfirmed(s, id, now) {
			verschoben++
		}
	}
	if verschoben > 0 {
		log.Printf("reaper: %d unbestaetigte Anmeldung(en) in die Ablage verschoben", verschoben)
	}
	if n, err := s.PurgeAblage(now); err != nil {
		log.Printf("reaper: Ablage nicht vollstaendig geraeumt: %v", err)
	} else if n > 0 {
		log.Printf("reaper: %d Ablage-Eintrag/-Eintraege nach 30 Tagen entfernt", n)
	}
	return verschoben
}

// reaperVorZweiterPruefung ist eine Test-Naht (im Betrieb nil): feuert unter
// der Adress-Sperre vor der zweiten Pruefung, um eine Zwischenzeit-Aenderung
// (z. B. Bestaetigung) einzuspielen.
var reaperVorZweiterPruefung func(id string)

func reapOneUnconfirmed(s *store.Store, id string, now time.Time) bool {
	reif := func() (*model.User, bool) {
		u, err := s.LoadUser(id)
		if err != nil || u == nil {
			return nil, false
		}
		tok, err := s.LoadVerificationToken(id)
		if err != nil || !store.IsUnconfirmedSignup(u, tok) || now.Before(tok.ExpiresAt.Add(unconfirmedGrace)) {
			return nil, false
		}
		return u, true
	}
	u, ok := reif()
	if !ok {
		return false
	}
	if addr := store.EffectiveContactAddress(u); addr != "" {
		unlock := store.LockEmailAddress(addr)
		defer unlock()
	}
	if reaperVorZweiterPruefung != nil {
		reaperVorZweiterPruefung(id)
	}
	if u, ok = reif(); !ok {
		return false
	}
	err := quarantineUnconfirmed(s, u, now)
	switch {
	case errors.Is(err, store.ErrAccountDirNotPristine):
		log.Printf("reaper: WARNUNG unbestaetigte Anmeldung %s hat Nutzinhalte — bleibt stehen", maskiereKennung(id))
		return false
	case err != nil:
		log.Printf("reaper: unbestaetigte Anmeldung %s nicht verschoben: %v", maskiereKennung(id), err)
		return false
	}
	return true
}
