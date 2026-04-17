package handler

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

type authRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

func RegisterHandler(s *store.Store, bcryptCost int) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req authRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		if len(req.Username) < 3 || len(req.Username) > 50 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}
		if len(req.Password) < 8 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}

		if s.UserExists(req.Username) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(409)
			w.Write([]byte(`{"error":"user already exists"}`))
			return
		}

		hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcryptCost)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		user := model.User{
			ID:           req.Username,
			PasswordHash: string(hash),
			CreatedAt:    time.Now(),
		}
		if err := s.SaveUser(user); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		s.ProvisionUserDirs(req.Username)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(map[string]string{"id": req.Username})
	}
}

func LoginHandler(s *store.Store, secret string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req authRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		user, err := s.LoadUser(req.Username)
		if err != nil || user == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(401)
			w.Write([]byte(`{"error":"invalid credentials"}`))
			return
		}

		if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(401)
			w.Write([]byte(`{"error":"invalid credentials"}`))
			return
		}

		token := middleware.SignSession(req.Username, secret)
		secure := r.Header.Get("X-Forwarded-Proto") == "https" || r.TLS != nil
		http.SetCookie(w, &http.Cookie{
			Name:     "gz_session",
			Value:    token,
			Path:     "/",
			HttpOnly: true,
			SameSite: http.SameSiteLaxMode,
			MaxAge:   86400,
			Secure:   secure,
		})

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"id": req.Username})
	}
}

func DeleteAccountHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		if err := s.DeleteUser(userId); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		// Blacklist session + clear cookie (like logout)
		cookie, err := r.Cookie("gz_session")
		if err == nil && cookie.Value != "" {
			middleware.BlacklistSession(cookie.Value)
		}
		http.SetCookie(w, &http.Cookie{
			Name: "gz_session", Value: "", Path: "/", HttpOnly: true, MaxAge: -1,
		})

		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"deleted"}`))
	}
}

func ForgotPasswordHandler(s *store.Store, bcryptCost int) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Username string `json:"username"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Username == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		// Always return 200 (no user enumeration)
		w.Header().Set("Content-Type", "application/json")

		user, _ := s.LoadUser(req.Username)
		if user == nil {
			w.Write([]byte(`{"status":"ok"}`))
			return
		}

		// Generate random token
		tokenBytes := make([]byte, 32)
		if _, err := rand.Read(tokenBytes); err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}
		token := hex.EncodeToString(tokenBytes)

		// Hash token for storage
		hash, err := bcrypt.GenerateFromPassword([]byte(token), bcryptCost)
		if err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		resetToken := model.PasswordResetToken{
			TokenHash: string(hash),
			ExpiresAt: time.Now().Add(30 * time.Minute),
		}
		s.SaveResetToken(req.Username, resetToken)

		log.Printf("Password reset link: /reset-password?user=%s&token=%s", req.Username, token)

		w.Write([]byte(`{"status":"ok"}`))
	}
}

func ResetPasswordHandler(s *store.Store, bcryptCost int) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Username    string `json:"username"`
			Token       string `json:"token"`
			NewPassword string `json:"new_password"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")

		if len(req.NewPassword) < 8 {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}

		resetToken, err := s.LoadResetToken(req.Username)
		if err != nil || resetToken == nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}

		if time.Now().After(resetToken.ExpiresAt) {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"token expired"}`))
			return
		}

		if err := bcrypt.CompareHashAndPassword([]byte(resetToken.TokenHash), []byte(req.Token)); err != nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}

		// Update password
		user, err := s.LoadUser(req.Username)
		if err != nil || user == nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid token"}`))
			return
		}

		newHash, err := bcrypt.GenerateFromPassword([]byte(req.NewPassword), bcryptCost)
		if err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		user.PasswordHash = string(newHash)
		if err := s.SaveUser(*user); err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		s.DeleteResetToken(req.Username)

		w.Write([]byte(`{"status":"ok"}`))
	}
}

func LogoutHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		cookie, err := r.Cookie("gz_session")
		if err == nil && cookie.Value != "" {
			middleware.BlacklistSession(cookie.Value)
		}

		http.SetCookie(w, &http.Cookie{
			Name:     "gz_session",
			Value:    "",
			Path:     "/",
			HttpOnly: true,
			MaxAge:   -1,
		})

		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	}
}

// profileResponse is the public view of a User (no password_hash).
type profileResponse struct {
	ID             string `json:"id"`
	Email          string `json:"email,omitempty"`
	MailTo         string `json:"mail_to,omitempty"`
	SignalPhone    string `json:"signal_phone,omitempty"`
	TelegramChatID string `json:"telegram_chat_id,omitempty"`
	CreatedAt      string `json:"created_at"`
}

func toProfileResponse(u *model.User) profileResponse {
	return profileResponse{
		ID:             u.ID,
		Email:          u.Email,
		MailTo:         u.MailTo,
		SignalPhone:    u.SignalPhone,
		TelegramChatID: u.TelegramChatID,
		CreatedAt:      u.CreatedAt.Format(time.RFC3339),
	}
}

func GetProfileHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(toProfileResponse(user))
	}
}

func UpdateProfileHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		var update struct {
			Email          *string `json:"email"`
			MailTo         *string `json:"mail_to"`
			SignalPhone    *string `json:"signal_phone"`
			SignalAPIKey   *string `json:"signal_api_key"`
			TelegramChatID *string `json:"telegram_chat_id"`
		}
		if err := json.NewDecoder(r.Body).Decode(&update); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		if update.Email != nil {
			user.Email = *update.Email
		}
		if update.MailTo != nil {
			user.MailTo = *update.MailTo
		}
		if update.SignalPhone != nil {
			user.SignalPhone = *update.SignalPhone
		}
		if update.SignalAPIKey != nil {
			user.SignalAPIKey = *update.SignalAPIKey
		}
		if update.TelegramChatID != nil {
			user.TelegramChatID = *update.TelegramChatID
		}

		if err := s.SaveUser(*user); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(toProfileResponse(user))
	}
}

func ChangePasswordHandler(s *store.Store, bcryptCost int) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		w.Header().Set("Content-Type", "application/json")

		var req struct {
			OldPassword string `json:"old_password"`
			NewPassword string `json:"new_password"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		if len(req.NewPassword) < 8 {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"validation failed"}`))
			return
		}

		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.OldPassword)); err != nil {
			w.WriteHeader(403)
			w.Write([]byte(`{"error":"wrong password"}`))
			return
		}

		newHash, err := bcrypt.GenerateFromPassword([]byte(req.NewPassword), bcryptCost)
		if err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		user.PasswordHash = string(newHash)
		if err := s.SaveUser(*user); err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"internal error"}`))
			return
		}

		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}
}
