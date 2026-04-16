package model

import "time"

type User struct {
	ID           string    `json:"id"`
	Email        string    `json:"email,omitempty"`
	PasswordHash string    `json:"password_hash"`
	CreatedAt    time.Time `json:"created_at"`
}
