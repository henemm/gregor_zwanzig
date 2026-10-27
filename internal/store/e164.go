package store

// E.164-Formatpruefung — Issue #2406. Platzierung wie NormalizeEmailAddress
// (address_owner.go): generische Adress-/Nummern-Validatoren leben im
// store-Paket, damit Handler und Store dieselbe Quelle benutzen.

import "regexp"

// e164Muster: fuehrendes "+", danach eine Ziffer 1-9 (keine fuehrende Null)
// und 7 bis 14 weitere Ziffern — insgesamt 8 bis 15 Ziffern, wie von der
// ITU-T-Empfehlung E.164 vorgegeben. Kein Leerzeichen, kein Bindestrich: die
// Nummer wird so gespeichert, wie sie an seven.io geht.
var e164Muster = regexp.MustCompile(`^\+[1-9]\d{7,14}$`)

// IsValidE164 meldet, ob s eine Rufnummer in E.164-Schreibweise ist.
func IsValidE164(s string) bool {
	return e164Muster.MatchString(s)
}
