package store

import (
	"log"
	"strings"

	"github.com/henemm/gregor-api/internal/model"
)

// AddressResolution ist das Ergebnis von ResolveAddressOwner (Issue #2147).
type AddressResolution int

const (
	AddressFree      AddressResolution = iota // kein Inhaber
	AddressOwned                              // genau ein Konto, siehe ResolveAddressOwner
	AddressAmbiguous                          // keine eindeutige Zuordnung möglich
)

// NormalizeEmailAddress ist die einzige Normalisierungsquelle für
// E-Mail-Adressen (TrimSpace + ToLower).
func NormalizeEmailAddress(s string) string {
	return strings.ToLower(strings.TrimSpace(s))
}

// EffectiveContactAddress: mail_to, ersatzweise email (normalisiert).
// Exportiert (Issue #2147 Scheibe B1), damit die Magic-Link-Uebernahme-
// Nachpruefung in internal/handler dieselbe Definition nutzt statt einer
// zweiten Ableitung.
func EffectiveContactAddress(u *model.User) string {
	if c := NormalizeEmailAddress(u.MailTo); c != "" {
		return c
	}
	return NormalizeEmailAddress(u.Email)
}

// HasLoginCredentials meldet, ob u sich ohne Magic-Link anmelden kann
// (Passwort, Passkey oder Google). Exportiert (Issue #2147 Scheibe B1) fuer
// dieselbe Nachpruefung wie EffectiveContactAddress.
func HasLoginCredentials(u *model.User) bool {
	return u.PasswordHash != "" || len(u.PasskeyCredentials) > 0 || u.OAuthSub != ""
}

// forEachRealAccount laedt jedes Nicht-Testkonto und ruft fn auf. Bricht
// sofort mit Fehler ab (fail-closed), wenn ListUserIDs oder LoadUser
// fehlschlaegt — von ResolveAddressOwner und IsAddressTakenByOtherAccount
// geteilt (Issue #2147 Scheibe B1).
func (s *Store) forEachRealAccount(fn func(*model.User)) error {
	ids, err := s.ListUserIDs()
	if err != nil {
		return err
	}
	for _, id := range ids {
		// Issue #2152: Testkonto-Status aus dem geladenen Profil (Flag oder
		// Fixture-ID), nicht aus dem Namen — das Laden steht deshalb VOR der
		// Klassifikation. Folge (bewusst): eine unlesbare user.json bricht auch
		// dann ab, wenn das Konto frueher per Namen uebersprungen worden waere.
		// Was sich nicht lesen laesst, laesst sich nicht als Testkonto einstufen;
		// fail-closed ist hier richtig, weil eine uebersehene Zeile die
		// Adress-Eindeutigkeit kippen wuerde (Issue #2147 Scheibe B1).
		u, err := s.LoadUser(id)
		if err != nil {
			return err
		}
		if u == nil || model.IsTestAccount(u) {
			continue
		}
		fn(u)
	}
	return nil
}

// ResolveAddressOwner ordnet eine Adresse genau einem Konto zu (Issue #2147,
// Spec magic_link_adress_eindeutigkeit.md). Inhaber = Nicht-Testkonto mit
// email ODER mail_to == X; bestätigter Inhaber = EmailVerifiedAt gesetzt UND X
// ist seine wirksame Kontaktadresse. Ein unlesbares Konto bricht mit Fehler ab
// (fail-closed), statt still eine Zuordnung zu verfälschen.
// gz-store-scope-exempt: sucht kontouebergreifend nach dem Inhaber einer Adresse
func (s *Store) ResolveAddressOwner(address string) (*model.User, AddressResolution, error) {
	x := NormalizeEmailAddress(address)
	if x == "" {
		return nil, AddressAmbiguous, nil
	}
	var owners, confirmed []*model.User
	if err := s.forEachRealAccount(func(u *model.User) {
		if NormalizeEmailAddress(u.Email) != x && NormalizeEmailAddress(u.MailTo) != x {
			return
		}
		owners = append(owners, u)
		if u.EmailVerifiedAt != nil && EffectiveContactAddress(u) == x {
			confirmed = append(confirmed, u)
		}
	}); err != nil {
		return nil, AddressAmbiguous, err
	}
	switch {
	case len(confirmed) == 1:
		return confirmed[0], AddressOwned, nil
	case len(confirmed) == 0 && len(owners) == 0:
		return nil, AddressFree, nil
	case len(confirmed) == 0 && len(owners) == 1 &&
		EffectiveContactAddress(owners[0]) == x && !HasLoginCredentials(owners[0]):
		return owners[0], AddressOwned, nil
	}
	// Nie die Adresse und nie Kontokennungen protokollieren — nur Anzahlen
	// (Issue #2147 Scheibe C, AC-11).
	log.Printf("address resolution: ambiguous — %d owner account(s), %d confirmed",
		len(owners), len(confirmed))
	return nil, AddressAmbiguous, nil
}

// IsAddressTakenByOtherAccount meldet, ob address (normalisiert) bereits von
// irgendeinem anderen, echten Konto in email ODER mail_to getragen wird
// (Issue #2147 Scheibe B1, Spec adress_eindeutigkeit_schreibpfade.md).
// excludeUserID schliesst das eigene Konto aus (leer bei der Registrierung,
// da es noch kein eigenes Konto gibt). Eine leere Adresse ist nie belegt.
// Ein Lesefehler bricht fail-closed ab, statt eine falsche Freigabe zu geben.
// gz-store-scope-exempt: prueft kontouebergreifend, das eigene Konto kommt als Parameter
func (s *Store) IsAddressTakenByOtherAccount(address, excludeUserID string) (bool, error) {
	x := NormalizeEmailAddress(address)
	if x == "" {
		return false, nil
	}
	taken := false
	if err := s.forEachRealAccount(func(u *model.User) {
		if u.ID == excludeUserID {
			return
		}
		if NormalizeEmailAddress(u.Email) == x || NormalizeEmailAddress(u.MailTo) == x {
			taken = true
		}
	}); err != nil {
		return false, err
	}
	return taken, nil
}
