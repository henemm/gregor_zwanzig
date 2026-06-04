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
	TelegramChatID     string               `json:"telegram_chat_id,omitempty"`
	OAuthProvider      string               `json:"oauth_provider,omitempty"`
	OAuthSub           string               `json:"oauth_sub,omitempty"`
}

type PasswordResetToken struct {
	TokenHash string    `json:"token_hash"`
	ExpiresAt time.Time `json:"expires_at"`
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
