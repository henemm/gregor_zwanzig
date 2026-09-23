package model

import (
	"time"

	"github.com/go-webauthn/webauthn/protocol"
	"github.com/go-webauthn/webauthn/webauthn"
)

type User struct {
	ID                 string               `json:"id"`
	Email              string               `json:"email,omitempty"`
	PasswordHash       string               `json:"password_hash,omitempty"`
	PasskeyCredentials []WebAuthnCredential `json:"passkey_credentials,omitempty"`
	CreatedAt          time.Time            `json:"created_at"`
	MailTo             string               `json:"mail_to,omitempty"`
	SmsTo              string               `json:"sms_to,omitempty"`
	TelegramChatID     string               `json:"telegram_chat_id,omitempty"`
	OAuthProvider      string               `json:"oauth_provider,omitempty"`
	OAuthSub           string               `json:"oauth_sub,omitempty"`
	DisplayName        string               `json:"display_name,omitempty"`
	Tier               string               `json:"tier,omitempty"`
	// Issue #1071 — offener Level-Änderungs-Antrag. RequestedAt MUSS ein Pointer
	// sein: Go's encoding/json omitempty greift bei time.Time-Structs nicht, ein
	// Zero-Value würde als "0001-01-01T00:00:00Z" serialisiert statt weggelassen.
	RequestedTier string     `json:"requested_tier,omitempty"`
	RequestedAt   *time.Time `json:"requested_at,omitempty"`
	// Issue #1219 Scheibe 1 — Resend-Allowlist-Eignungskriterium. Pointer aus
	// demselben Grund wie RequestedAt: omitempty greift bei time.Time-Structs
	// nicht, ein Zero-Value würde als "0001-01-01T00:00:00Z" serialisiert
	// statt als "fehlt" (unverifiziert).
	EmailVerifiedAt *time.Time `json:"email_verified_at,omitempty"`
	// Issue #1676 Scheibe S1 — Premium-SMS Rueckkanal: von Garmin je Gespraech
	// neu vergebene Rueckadresse. Pointer bei PremiumSmsReplyAt aus demselben
	// Grund wie RequestedAt/EmailVerifiedAt (omitempty greift bei
	// time.Time-Structs nicht).
	PremiumSmsReplyTo string     `json:"premium_sms_reply_to,omitempty"`
	PremiumSmsReplyAt *time.Time `json:"premium_sms_reply_at,omitempty"`
	// Issue #2248 (#2199 Scheibe 3) — das Passkey-Angebot wurde abgewiesen. Der
	// Vermerk gehoert ins Profil, damit er geraeteuebergreifend gilt. Schlichtes
	// bool: "fehlt" und "false" bedeuten beide "nicht abgewiesen", es gibt hier
	// kein Zeitstempel-Nullwert-Problem wie bei RequestedAt.
	PasskeyPromptDismissed bool `json:"passkey_prompt_dismissed,omitempty"`
	// Issue #2147 Scheibe B2 — ausstehende Adressaenderung eines bestaetigten
	// Kontos. Solange sie aussteht, bleiben Email/MailTo auf den alten,
	// bestaetigten Werten; die neue Adresse steht NUR hier (unsichtbar fuer
	// ResolveAddressOwner, Allowlists, Versand). PendingContactField nennt das
	// beim Einloesen zu schreibende Feld ("email"|"mail_to"). Beide fehlen im
	// JSON, solange nichts aussteht (Bestandsdaten laden unveraendert).
	PendingContactAddress string `json:"pending_contact_address,omitempty"`
	PendingContactField   string `json:"pending_contact_field,omitempty"`
	// Issue #2152 — Testkonto-Status als persistiertes Profilfeld (ADR-0072).
	// Einzige Quelle der Wahrheit neben der festen Fixture-ID tg-live-e2e
	// (IsTestAccount); ersetzt die "test"/"tdd"-Namens-Heuristik. omitempty:
	// Bestandsprofile ohne das Feld laden unveraendert als echte Nutzer.
	IsTestUser bool `json:"is_test_user,omitempty"`
	// Issue #2406 (S3 aus #2153) — SMS-Nummer-Verifikation. SmsVerifiedNumber
	// ist die BEWIESENE Nummer, nicht bloss ein Zeitstempel: nur wenn sie mit
	// SmsTo uebereinstimmt, darf eine SMS an das Konto gehen (Wirkstelle
	// src/app/config.py::with_user_profile). PendingSmsTo haelt eine neue
	// Nummer, solange das Konto eine bestaetigte hat — sie wird erst beim
	// Einloesen des Codes nach SmsTo befoerdert. Alle drei omitempty:
	// Bestandsdaten laden unveraendert. SmsVerifiedAt ist ein Pointer aus
	// demselben Grund wie EmailVerifiedAt.
	SmsVerifiedNumber string     `json:"sms_verified_number,omitempty"`
	SmsVerifiedAt     *time.Time `json:"sms_verified_at,omitempty"`
	PendingSmsTo      string     `json:"pending_sms_to,omitempty"`
}

// SmsVerificationCode — Issue #2406. Struktureller Klon von
// EmailVerificationToken: nur der bcrypt-Hash liegt auf Platte, mit Ablauf und
// an die zu beweisende Nummer gebunden. FailedAttempts riegelt Brute-Force auf
// den kurzen Zahlencode ab.
type SmsVerificationCode struct {
	CodeHash       string    `json:"code_hash"`
	ExpiresAt      time.Time `json:"expires_at"`
	Number         string    `json:"number"`
	FailedAttempts int       `json:"failed_attempts,omitempty"`
}

type PasswordResetToken struct {
	TokenHash string    `json:"token_hash"`
	ExpiresAt time.Time `json:"expires_at"`
}

// EmailVerificationToken — Issue #1219 Scheibe 2a-i. Struktureller Klon von
// PasswordResetToken: Hash statt Klartext-Token persistiert, mit Ablauf.
type EmailVerificationToken struct {
	TokenHash string    `json:"token_hash"`
	ExpiresAt time.Time `json:"expires_at"`
	// Issue #2147 Scheibe B2 — die zu beweisende Adresse (normalisiert). Leer
	// bei Alt-Tokens von vor diesem Stand.
	Address string `json:"address,omitempty"`
}

// WebAuthnCredential is the persisted form of a registered Passkey/FIDO2 credential.
// Issue #450 — V1 Add-on.
type WebAuthnCredential struct {
	ID              []byte                   `json:"id"`
	PublicKey       []byte                   `json:"public_key"`
	AttestationType string                   `json:"attestation_type"`
	Transport       []string                 `json:"transport,omitempty"`
	Flags           webauthn.CredentialFlags `json:"flags"`
	Authenticator   webauthn.Authenticator   `json:"authenticator"`
	CreatedAt       time.Time                `json:"created_at"`
	LastUsedAt      time.Time                `json:"last_used_at,omitempty"`
	Label           string                   `json:"label,omitempty"`
}

// WebAuthnID implements webauthn.User.
func (u *User) WebAuthnID() []byte { return []byte(u.ID) }

// WebAuthnName implements webauthn.User.
func (u *User) WebAuthnName() string { return u.ID }

// WebAuthnDisplayName implements webauthn.User.
func (u *User) WebAuthnDisplayName() string { return u.ID }

// WebAuthnCredentials implements webauthn.User: returns all credentials of this user
// in the format the library expects (with Transport converted to []protocol.AuthenticatorTransport).
func (u *User) WebAuthnCredentials() []webauthn.Credential {
	out := make([]webauthn.Credential, 0, len(u.PasskeyCredentials))
	for _, c := range u.PasskeyCredentials {
		out = append(out, webauthn.Credential{
			ID:              c.ID,
			PublicKey:       c.PublicKey,
			AttestationType: c.AttestationType,
			Transport:       toAuthenticatorTransports(c.Transport),
			Flags:           c.Flags,
			Authenticator:   c.Authenticator,
		})
	}
	return out
}

func toAuthenticatorTransports(in []string) []protocol.AuthenticatorTransport {
	if len(in) == 0 {
		return nil
	}
	out := make([]protocol.AuthenticatorTransport, 0, len(in))
	for _, t := range in {
		out = append(out, protocol.AuthenticatorTransport(t))
	}
	return out
}
