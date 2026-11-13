package model

// Verknuepfungs-Code fuer den Premium-SMS-Rueckkanal — Issue #2154 Scheibe A.
//
// Der Nutzer liest den Code in seinem Konto ab und schickt ihn per inReach
// einmalig mit. Gespeichert wird ausschliesslich der bcrypt-Hash; der Klartext
// existiert nur im Antwortkoerper des Erzeugungs-Aufrufs (Spec D1/D2). Eigene
// Datei je Nutzer (premium_sms_link.json), Vorbild PasswordResetToken.

import "time"

// PremiumSmsLinkCode ist der gespeicherte Verknuepfungs-Code eines Nutzers.
type PremiumSmsLinkCode struct {
	CodeHash  string    `json:"code_hash"`
	CreatedAt time.Time `json:"created_at"`
	// CodeFormat (ADR-0116, Issue #2961): Gestalt des Codes, aus dem Hash nicht
	// ableitbar. Fehlt bei Bestandsdateien (= altes, kuerzeres Format).
	CodeFormat int `json:"code_format,omitempty"`
}

// PremiumSmsLinkCodeFormatLang: "XX" + 5 Buchstaben + 3 Ziffern (ADR-0116).
const PremiumSmsLinkCodeFormatLang = 2

// LegacyFormat meldet einen Code im alten, kuerzeren Format.
func (c PremiumSmsLinkCode) LegacyFormat() bool {
	return c.CodeFormat < PremiumSmsLinkCodeFormatLang
}
