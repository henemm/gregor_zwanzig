package store

import (
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// BestaetigungspflichtSeit: Konten, die ab diesem Zeitpunkt entstanden sind,
// durchlaufen die Bestaetigung der Adresse als Pflicht (ADR-0066, 2026-09-12).
// Aeltere unbestaetigte Konten sind Bestand (Nachtrag #2304) und werden von
// den Regeln fuer unbestaetigte Anmeldungen (Issue #2961, ADR-0115) nie
// erfasst — weder ersetzt noch geloescht.
var BestaetigungspflichtSeit = time.Date(2026, 9, 12, 0, 0, 0, 0, time.UTC)

// IsUnconfirmedSignup meldet eine unbestaetigte Anmeldung unter der
// Bestaetigungspflicht (Issue #2961, GA2): kein Testkonto, keine bestaetigte
// Adresse, keine ausstehende Adressaenderung, angelegt ab
// BestaetigungspflichtSeit und mit Bestaetigungstoken (tok != nil). Im
// Zweifel nein.
func IsUnconfirmedSignup(u *model.User, tok *model.EmailVerificationToken) bool {
	return u != nil && tok != nil && !model.IsTestAccount(u) && u.EmailVerifiedAt == nil &&
		u.PendingContactAddress == "" && !u.CreatedAt.IsZero() && !u.CreatedAt.Before(BestaetigungspflichtSeit)
}

// ReplaceableAddressHolders liefert die Konten, die address (normalisiert, in
// email ODER mail_to) halten, und ob ALLE davon unbestaetigte Anmeldungen
// (IsUnconfirmedSignup) mit leerem Kontoordner (IsAccountDirPristine)
// sind — nur dann darf eine neue Registrierung sie
// ersetzen (Issue #2961, GA2a). Testkonten zaehlen wie bei
// IsAddressTakenByOtherAccount nicht. Ein Lesefehler bricht ab (fail-closed).
// gz-store-scope-exempt: sucht kontouebergreifend nach den Inhabern einer Adresse
func (s *Store) ReplaceableAddressHolders(address string) ([]*model.User, bool, error) {
	x := NormalizeEmailAddress(address)
	if x == "" {
		return nil, false, nil
	}
	var holders []*model.User
	allReplaceable := true
	var loadErr error
	if err := s.forEachRealAccount(func(u *model.User) {
		if NormalizeEmailAddress(u.Email) != x && NormalizeEmailAddress(u.MailTo) != x {
			return
		}
		holders = append(holders, u)
		tok, err := s.LoadVerificationToken(u.ID)
		if err != nil {
			loadErr = err
		}
		if !IsUnconfirmedSignup(u, tok) {
			allReplaceable = false
			return
		}
		// Bestandsdaten bleiben erhalten: nur ein Ordner ohne Nutzinhalte
		// darf ersetzt werden (IsAccountDirPristine).
		if leer, perr := s.IsAccountDirPristine(u.ID); perr != nil || !leer {
			allReplaceable = false
		}
	}); err != nil {
		return nil, false, err
	}
	if loadErr != nil {
		return nil, false, loadErr
	}
	return holders, allReplaceable && len(holders) > 0, nil
}
