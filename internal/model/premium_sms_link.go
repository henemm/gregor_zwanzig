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
}
