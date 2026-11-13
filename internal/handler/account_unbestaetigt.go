package handler

// Unbestaetigte Anmeldungen (Issue #2961, GA2, ADR-0115). Wer eine fremde
// Adresse registriert, ohne sie bestaetigen zu koennen, darf damit weder die
// Adresse blockieren noch Zugangsdaten fuer das spaetere Konto des echten
// Inhabers hinterlegen:
//   (a) eine neue Registrierung fuer dieselbe Adresse ersetzt solche Konten
//       vollstaendig (replaceUnconfirmedHolders);
//   (b) der Reaper loescht sie, wenn ihr Bestaetigungstoken seit mehr als 24
//       Stunden abgelaufen ist (reapUnconfirmedAccounts).
// Was als unbestaetigte Anmeldung gilt, entscheidet store.IsUnconfirmedSignup
// (konservativ: Bestand von vor der Bestaetigungspflicht, Testkonten und
// Konten ohne Token sind nie betroffen).

import (
	"log"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

// unconfirmedGrace: so lange nach Ablauf des Bestaetigungstokens bleibt eine
// unbestaetigte Anmeldung noch stehen.
const unconfirmedGrace = 24 * time.Hour

// replaceUnconfirmedHolders entfernt alle Konten, die address halten, wenn
// ALLE davon unbestaetigte Anmeldungen sind, und meldet true. Sonst bleibt
// alles unveraendert (false). Der Aufrufer haelt LockEmailAddress(address).
func replaceUnconfirmedHolders(s *store.Store, address string) (bool, error) {
	holders, all, err := s.ReplaceableAddressHolders(address)
	if err != nil || !all {
		return false, err
	}
	for _, u := range holders {
		if err := deleteAccountCascade(s, nil, u); err != nil {
			return false, err
		}
	}
	log.Printf("register: %d unbestaetigte Anmeldung(en) fuer die Adresse ersetzt", len(holders))
	return true, nil
}

// addressFreeForSignup: Adresse frei oder nur von unbestaetigten Anmeldungen
// gehalten (Vorpruefung ohne Aenderung, z. B. Passkey-Registrierung Schritt 1).
func addressFreeForSignup(s *store.Store, address string) (bool, error) {
	taken, err := s.IsAddressTakenByOtherAccount(address, "")
	if err != nil {
		return false, err
	}
	if !taken {
		return true, nil
	}
	_, all, err := s.ReplaceableAddressHolders(address)
	return all && err == nil, err
}

// reapUnconfirmedAccounts loescht unbestaetigte Anmeldungen, deren Token seit
// mehr als unconfirmedGrace abgelaufen ist, samt Kontoordner. Jede Loeschung
// laeuft unter der Adress-Sperre und prueft frisch nach. Rueckgabe: Anzahl.
func reapUnconfirmedAccounts(s *store.Store, now time.Time) int {
	ids, err := s.ListUserIDs()
	if err != nil {
		log.Printf("reaper: Kontoliste nicht lesbar: %v", err)
		return 0
	}
	geloescht := 0
	for _, id := range ids {
		if reapOneUnconfirmed(s, id, now) {
			geloescht++
		}
	}
	if geloescht > 0 {
		log.Printf("reaper: %d unbestaetigte Anmeldung(en) geloescht", geloescht)
	}
	return geloescht
}

func reapOneUnconfirmed(s *store.Store, id string, now time.Time) bool {
	reif := func() (bool, string) {
		u, err := s.LoadUser(id)
		if err != nil || u == nil {
			return false, ""
		}
		tok, err := s.LoadVerificationToken(id)
		if err != nil || !store.IsUnconfirmedSignup(u, tok) || now.Before(tok.ExpiresAt.Add(unconfirmedGrace)) {
			return false, ""
		}
		return true, store.EffectiveContactAddress(u)
	}
	ok, addr := reif()
	if !ok {
		return false
	}
	if addr != "" {
		unlock := store.LockEmailAddress(addr)
		defer unlock()
	}
	if ok, _ = reif(); !ok {
		return false
	}
	u, err := s.LoadUser(id)
	if err != nil || u == nil {
		return false
	}
	if err := deleteAccountCascade(s, nil, u); err != nil {
		log.Printf("reaper: unbestaetigte Anmeldung %s nicht geloescht: %v", id, err)
		return false
	}
	return true
}
