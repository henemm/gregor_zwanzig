package model

import "time"

// Invite ist ein Admin-Einladungslink (Issue #2519). Gespeichert wird nur der
// SHA-256-Hash des Tokens, nie der Klartext. Der Datensatz gehoert keinem
// Nutzer, darum liegt er global in data/invites.json.
type Invite struct {
	ID        string     `json:"id"`
	TokenHash string     `json:"token_hash"`
	Tier      string     `json:"tier"`
	Note      string     `json:"note"`
	CreatedAt time.Time  `json:"created_at"`
	CreatedBy string     `json:"created_by"`
	UsedBy    string     `json:"used_by,omitempty"`
	UsedAt    *time.Time `json:"used_at,omitempty"`
	RevokedAt *time.Time `json:"revoked_at,omitempty"`
}

// Status: "open", "used" oder "revoked".
func (i Invite) Status() string {
	switch {
	case i.UsedBy != "":
		return "used"
	case i.RevokedAt != nil:
		return "revoked"
	default:
		return "open"
	}
}
