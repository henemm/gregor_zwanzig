package store

import (
	"log"

	"github.com/henemm/gregor-api/internal/model"
)

// AddressCollisionCount ist das Ergebnis des Kollisionszählers (Issue #2147
// Scheibe C, Spec google_login_adress_verknuepfung.md AC-16/AC-17).
type AddressCollisionCount struct {
	Addresses int // normalisierte Adressen, die mehr als ein echtes Konto hält
	Accounts  int // verschiedene echte Konten, die mindestens eine davon halten
}

// CountAddressCollisions zählt Bestandsduplikate: eine normalisierte Adresse
// gilt als von einem Konto gehalten, wenn sie in email ODER mail_to steht
// (kreuzweise). Testkonten zählen nicht (forEachRealAccount), leere Adressen
// nie. Ein Lesefehler liefert einen Fehler statt einer falschen Zahl.
func (s *Store) CountAddressCollisions() (AddressCollisionCount, error) {
	holders := map[string]map[string]bool{}
	if err := s.forEachRealAccount(func(u *model.User) {
		for _, a := range []string{NormalizeEmailAddress(u.Email), NormalizeEmailAddress(u.MailTo)} {
			if a == "" {
				continue
			}
			if holders[a] == nil {
				holders[a] = map[string]bool{}
			}
			holders[a][u.ID] = true
		}
	}); err != nil {
		return AddressCollisionCount{}, err
	}
	var count AddressCollisionCount
	accounts := map[string]bool{}
	for _, ids := range holders {
		if len(ids) < 2 {
			continue
		}
		count.Addresses++
		for id := range ids {
			accounts[id] = true
		}
	}
	count.Accounts = len(accounts)
	return count, nil
}

// LogAddressCollisions protokolliert den Zählerstand beim Serverstart. Nur
// Zahlen — nie Adressen oder Kontokennungen, auch nicht im Fehlerfall (der
// Lesefehler nennt den Dateipfad und damit die Kontokennung). Fail-soft: der
// Start läuft in jedem Fall weiter.
func (s *Store) LogAddressCollisions() {
	count, err := s.CountAddressCollisions()
	if err != nil {
		log.Printf("address collisions: scan failed — no count available")
		return
	}
	log.Printf("address collisions: %d address(es) held by more than one account, %d account(s) affected",
		count.Addresses, count.Accounts)
}
