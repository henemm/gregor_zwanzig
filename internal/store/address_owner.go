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

// effectiveContactAddress: mail_to, ersatzweise email (normalisiert).
func effectiveContactAddress(u *model.User) string {
	if c := NormalizeEmailAddress(u.MailTo); c != "" {
		return c
	}
	return NormalizeEmailAddress(u.Email)
}

func hasLoginCredentials(u *model.User) bool {
	return u.PasswordHash != "" || len(u.PasskeyCredentials) > 0 || u.OAuthSub != ""
}

// ResolveAddressOwner ordnet eine Adresse genau einem Konto zu (Issue #2147,
// Spec magic_link_adress_eindeutigkeit.md). Inhaber = Nicht-Testkonto mit
// email ODER mail_to == X; bestätigter Inhaber = EmailVerifiedAt gesetzt UND X
// ist seine wirksame Kontaktadresse. Ein unlesbares Konto bricht mit Fehler ab
// (fail-closed), statt still eine Zuordnung zu verfälschen.
func (s *Store) ResolveAddressOwner(address string) (*model.User, AddressResolution, error) {
	x := NormalizeEmailAddress(address)
	if x == "" {
		return nil, AddressAmbiguous, nil
	}
	ids, err := s.ListUserIDs()
	if err != nil {
		return nil, AddressAmbiguous, err
	}
	var owners, confirmed []*model.User
	for _, id := range ids {
		if model.IsTestUserID(id) {
			continue
		}
		u, err := s.LoadUser(id)
		if err != nil {
			return nil, AddressAmbiguous, err
		}
		if u == nil || (NormalizeEmailAddress(u.Email) != x && NormalizeEmailAddress(u.MailTo) != x) {
			continue
		}
		owners = append(owners, u)
		if u.EmailVerifiedAt != nil && effectiveContactAddress(u) == x {
			confirmed = append(confirmed, u)
		}
	}
	switch {
	case len(confirmed) == 1:
		return confirmed[0], AddressOwned, nil
	case len(confirmed) == 0 && len(owners) == 0:
		return nil, AddressFree, nil
	case len(confirmed) == 0 && len(owners) == 1 &&
		effectiveContactAddress(owners[0]) == x && !hasLoginCredentials(owners[0]):
		return owners[0], AddressOwned, nil
	}
	// Nie die Adresse protokollieren — nur Kennungen und Anzahl.
	ownerIDs := make([]string, 0, len(owners))
	for _, u := range owners {
		ownerIDs = append(ownerIDs, u.ID)
	}
	log.Printf("address resolution: ambiguous — %d owner account(s), %d confirmed: %v",
		len(owners), len(confirmed), ownerIDs)
	return nil, AddressAmbiguous, nil
}
