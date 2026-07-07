package handler

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
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
		if !validUsernameRe.MatchString(req.Username) {
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

func ForgotPasswordHandler(s *store.Store, bcryptCost int, cfg config.Config) http.HandlerFunc {
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

		// --- Mail dispatch (Issue #124) ---
		recipient := user.MailTo
		if recipient == "" {
			recipient = user.Email
		}
		if recipient == "" {
			log.Printf("password reset: no email address for user %s — token written but not sent", req.Username)
			w.Write([]byte(`{"status":"ok"}`))
			return
		}

		// Select SMTP config: test users → Gmail, normal users → Resend (cfg.SMTP*)
		var mailCfg mail.MailConfig
		if mail.IsTestUser(req.Username) {
			if cfg.GoogleSMTPHost == "" {
				log.Printf("password reset: Google SMTP not configured, mail not sent for test user %s", req.Username)
				w.Write([]byte(`{"status":"ok"}`))
				return
			}
			mailCfg = mail.MailConfig{
				Host: cfg.GoogleSMTPHost, Port: cfg.GoogleSMTPPort,
				User: cfg.GoogleSMTPUser, Pass: cfg.GoogleSMTPPass,
				From: cfg.GoogleSMTPUser,
			}
		} else {
			if cfg.SMTPHost == "" {
				log.Printf("password reset: SMTP not configured, mail not sent for user %s", req.Username)
				w.Write([]byte(`{"status":"ok"}`))
				return
			}
			mailCfg = mail.MailConfig{
				Host: cfg.SMTPHost, Port: cfg.SMTPPort,
				User: cfg.SMTPUser, Pass: cfg.SMTPPass,
				From: cfg.SMTPFrom,
			}
		}

		msg := mail.BuildResetMail(cfg.PublicHost, req.Username, token)

		// Goroutine with timeout — endpoint must not block on SMTP.
		fallbackCfg := mail.MailConfig{
			Host: cfg.FallbackSMTPHost, Port: 587,
			User: cfg.FallbackSMTPUser, Pass: cfg.FallbackSMTPPass,
		}
		go func(to string, msg mail.Mail, c, fb mail.MailConfig, username string) {
			done := make(chan error, 1)
			go func() { done <- mail.SendWithFallback(c, fb, to, msg) }()
			select {
			case err := <-done:
				if err != nil {
					log.Printf("password reset: mail send failed for %s: %v", username, err)
				}
			case <-time.After(20 * time.Second):
				log.Printf("password reset: mail send timeout (20s) for %s", username)
			}
		}(recipient, msg, mailCfg, fallbackCfg, req.Username)

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

// profileResponse is the public view of a User (no password_hash, no public_key).
// Issue #450 adds the Passkey-summary fields.
type profileResponse struct {
	ID             string                `json:"id"`
	Email          string                `json:"email,omitempty"`
	DisplayName    string                `json:"display_name,omitempty"`
	MailTo         string                `json:"mail_to,omitempty"`
	SmsTo          string                `json:"sms_to,omitempty"`
	TelegramChatID string                `json:"telegram_chat_id,omitempty"`
	Tier           string                `json:"tier"`
	SmsAllowed     bool                  `json:"sms_allowed"`
	// Issue #1071 — offener Level-Änderungs-Antrag. Fehlt im JSON, solange kein
	// Antrag vorliegt (omitempty bzw. nil-Pointer).
	RequestedTier  string                `json:"requested_tier,omitempty"`
	RequestedAt    *time.Time            `json:"requested_at,omitempty"`
	CreatedAt      string                `json:"created_at"`
	HasPasskey     bool                  `json:"has_passkey"`
	Passkeys       []passkeyProfileEntry `json:"passkeys,omitempty"`
}

// passkeyProfileEntry exposes a registered Passkey to the client WITHOUT the
// public key — that material is server-side only.
type passkeyProfileEntry struct {
	ID                string `json:"id"`
	Label             string `json:"label,omitempty"`
	AuthenticatorName string `json:"authenticator_name,omitempty"`
	CreatedAt         string `json:"created_at"`
	LastUsedAt        string `json:"last_used_at,omitempty"`
}

func toProfileResponse(u *model.User) profileResponse {
	passkeys := make([]passkeyProfileEntry, 0, len(u.PasskeyCredentials))
	for _, pc := range u.PasskeyCredentials {
		entry := passkeyProfileEntry{
			ID:                base64.RawURLEncoding.EncodeToString(pc.ID),
			Label:             pc.Label,
			AuthenticatorName: aaguidToName(pc.Authenticator.AAGUID),
			CreatedAt:         pc.CreatedAt.Format(time.RFC3339),
		}
		if !pc.LastUsedAt.IsZero() {
			entry.LastUsedAt = pc.LastUsedAt.Format(time.RFC3339)
		}
		passkeys = append(passkeys, entry)
	}
	// Default-Fallback nur am Lesezeitpunkt — kein Schreibpfad setzt "free"
	// zurück in die user.json (Read-Modify-Write-Prinzip, Issue #1068).
	// Issue #1074: auch ungültige Werte (Tippfehler, Legacy-Daten) normalisieren.
	tier := u.Tier
	if tier != "free" && tier != "standard" && tier != "premium" {
		tier = "free"
	}
	return profileResponse{
		ID:             u.ID,
		Email:          u.Email,
		DisplayName:    u.DisplayName,
		MailTo:         u.MailTo,
		SmsTo:          u.SmsTo,
		TelegramChatID: u.TelegramChatID,
		Tier:           tier,
		SmsAllowed:     model.SmsAllowed(tier),
		RequestedTier:  u.RequestedTier,
		RequestedAt:    u.RequestedAt,
		CreatedAt:      u.CreatedAt.Format(time.RFC3339),
		HasPasskey:     len(u.PasskeyCredentials) > 0,
		Passkeys:       passkeys,
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
			DisplayName    *string `json:"display_name"`
			MailTo         *string `json:"mail_to"`
			SmsTo          *string `json:"sms_to"`
			TelegramChatID *string `json:"telegram_chat_id"`
		}
		if err := json.NewDecoder(r.Body).Decode(&update); err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		if update.DisplayName != nil {
			name := strings.TrimSpace(*update.DisplayName)
			if name == "" {
				user.DisplayName = "" // Fallback auf Login-Name
			} else if utf8.RuneCountInString(name) > 50 || hasControlChars(name) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(400)
				w.Write([]byte(`{"error":"invalid display_name"}`))
				return
			} else {
				user.DisplayName = name
			}
		}

		if update.Email != nil {
			user.Email = *update.Email
		}
		if update.MailTo != nil {
			user.MailTo = *update.MailTo
		}
		if update.SmsTo != nil {
			user.SmsTo = *update.SmsTo
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

// hasControlChars reports whether s contains any Unicode control character
// (incl. newlines/tabs) — disallowed in a display name (Issue #642).
func hasControlChars(s string) bool {
	for _, r := range s {
		if unicode.IsControl(r) {
			return true
		}
	}
	return false
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

// effectiveTier normalisiert den gespeicherten Tier-Wert am Lesezeitpunkt auf
// free/standard/premium — identischer Fallback wie in toProfileResponse().
func effectiveTier(tier string) string {
	if tier != "free" && tier != "standard" && tier != "premium" {
		return "free"
	}
	return tier
}

// RequestTierChangeHandler nimmt einen Level-Änderungs-Antrag entgegen (Issue
// #1071). Der Antrag wird per Read-Modify-Write in der user.json vermerkt
// (requested_tier/requested_at) und löst asynchron eine Benachrichtigungsmail
// an den PO aus. Das effektive tier-Feld bleibt unverändert — die Freigabe
// erfolgt weiterhin manuell durch den PO.
func RequestTierChangeHandler(s *store.Store, cfg config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userId := middleware.UserIDFromContext(r.Context())
		w.Header().Set("Content-Type", "application/json")

		user, err := s.LoadUser(userId)
		if err != nil || user == nil {
			w.WriteHeader(404)
			w.Write([]byte(`{"error":"not_found"}`))
			return
		}

		var req struct {
			RequestedTier string `json:"requested_tier"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		if req.RequestedTier != "free" && req.RequestedTier != "standard" && req.RequestedTier != "premium" {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"invalid_tier"}`))
			return
		}

		currentTier := effectiveTier(user.Tier)
		if req.RequestedTier == currentTier {
			w.WriteHeader(400)
			w.Write([]byte(`{"error":"already_current_tier"}`))
			return
		}

		now := time.Now()
		user.RequestedTier = req.RequestedTier
		user.RequestedAt = &now
		if err := s.SaveUser(*user); err != nil {
			w.WriteHeader(500)
			w.Write([]byte(`{"error":"store_error"}`))
			return
		}

		// Erst nach erfolgreichem Save antworten — Mail beeinflusst die Response nie.
		w.Write([]byte(`{"status":"ok"}`))

		if cfg.PoEmail == "" {
			log.Printf("tier-change: PO_EMAIL not configured — request stored for %s but no mail sent", userId)
			return
		}
		if cfg.SMTPHost == "" {
			log.Printf("tier-change: SMTP not configured — request stored for %s but no mail sent", userId)
			return
		}

		mailCfg := mail.MailConfig{
			Host: cfg.SMTPHost, Port: cfg.SMTPPort,
			User: cfg.SMTPUser, Pass: cfg.SMTPPass,
			From: cfg.SMTPFrom,
		}
		fallbackCfg := mail.MailConfig{
			Host: cfg.FallbackSMTPHost, Port: 587,
			User: cfg.FallbackSMTPUser, Pass: cfg.FallbackSMTPPass,
		}
		msg := mail.BuildTierChangeRequestMail(userId, currentTier, req.RequestedTier)

		// Goroutine mit Timeout — der Endpoint darf nicht auf SMTP blockieren.
		go func(to string, msg mail.Mail, c, fb mail.MailConfig, username string) {
			done := make(chan error, 1)
			go func() { done <- mail.SendWithFallback(c, fb, to, msg) }()
			select {
			case err := <-done:
				if err != nil {
					log.Printf("tier-change: mail send failed for %s: %v", username, err)
				}
			case <-time.After(20 * time.Second):
				log.Printf("tier-change: mail send timeout (20s) for %s", username)
			}
		}(cfg.PoEmail, msg, mailCfg, fallbackCfg, userId)
	}
}
