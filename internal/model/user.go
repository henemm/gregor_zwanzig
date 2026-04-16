package model

import "time"

type User struct {
	ID             string    `json:"id"`
	Email          string    `json:"email,omitempty"`
	PasswordHash   string    `json:"password_hash"`
	CreatedAt      time.Time `json:"created_at"`
	MailTo         string    `json:"mail_to,omitempty"`
	SignalPhone    string    `json:"signal_phone,omitempty"`
	SignalAPIKey   string    `json:"signal_api_key,omitempty"`
	TelegramChatID string    `json:"telegram_chat_id,omitempty"`
}

type PasswordResetToken struct {
	TokenHash string    `json:"token_hash"`
	ExpiresAt time.Time `json:"expires_at"`
}
