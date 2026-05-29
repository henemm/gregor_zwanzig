package handler

// Magic Link / OTP Login per E-Mail (Issue #449).
// Spec: docs/specs/modules/issue_449_magic_link.md
//
// Two endpoints:
//   POST /api/auth/magic-link        — request a 6-digit code via e-mail
//   POST /api/auth/magic-link/verify — exchange a valid code for a session cookie
//
// The OTP-Store is a package-level sync.Map (key: normalized e-mail,
// value: *otpEntry). TTL is 15 minutes; max 3 wrong attempts per entry.
// New users are provisioned automatically with ID format "m-{8hex}".

import (
	"crypto/rand"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// otpEntry is the per-email record stored in otpStore. attempts is mutated
// in place via the pointer — never re-Store the entry.
type otpEntry struct {
	code      string
	userID    string
	expiresAt time.Time
	attempts  int32
}

// otpStore holds active OTP challenges, keyed by lower-cased trimmed e-mail.
var otpStore sync.Map

// MagicLinkRequestHandler returns the HTTP handler for POST /api/auth/magic-link.
// Always responds 200 (no user enumeration); generates a 6-digit OTP, stores it
// with a 15-min TTL, and dispatches the OTP-mail asynchronously (10s timeout).
func MagicLinkRequestHandler(s *store.Store, cfg *config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var req struct {
			Email string `json:"email"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || strings.TrimSpace(req.Email) == "" {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		normalizedEmail := strings.ToLower(strings.TrimSpace(req.Email))

		// Find existing user or create a new magic-link account.
		user, err := s.FindUserByEmail(normalizedEmail)
		if err != nil {
			log.Printf("magic-link: FindUserByEmail error: %v", err)
			w.Write([]byte(`{"status":"ok"}`))
			return
		}
		if user == nil {
			user, err = createMagicLinkUser(s, normalizedEmail)
			if err != nil {
				log.Printf("magic-link: createMagicLinkUser error: %v", err)
				w.Write([]byte(`{"status":"ok"}`))
				return
			}
		}

		// Generate 6-digit OTP via crypto/rand.
		var b [4]byte
		if _, err := rand.Read(b[:]); err != nil {
			log.Printf("magic-link: rand.Read error: %v", err)
			w.Write([]byte(`{"status":"ok"}`))
			return
		}
		code := fmt.Sprintf("%06d", binary.BigEndian.Uint32(b[:])%1_000_000)

		otpStore.Store(normalizedEmail, &otpEntry{
			code:      code,
			userID:    user.ID,
			expiresAt: time.Now().Add(15 * time.Minute),
			attempts:  0,
		})

		// Dispatch e-mail in background goroutine with 10s timeout.
		if cfg.SMTPHost == "" {
			log.Printf("magic-link: SMTP not configured, skipping email to %s", normalizedEmail)
		} else {
			mailCfg := mail.MailConfig{
				Host: cfg.SMTPHost,
				Port: cfg.SMTPPort,
				User: cfg.SMTPUser,
				Pass: cfg.SMTPPass,
				From: cfg.SMTPFrom,
			}
			msg := mail.BuildMagicLinkMail(code)
			go func(to string, m mail.Mail, c mail.MailConfig) {
				done := make(chan error, 1)
				go func() { done <- mail.Send(c, to, m) }()
				select {
				case err := <-done:
					if err != nil {
						log.Printf("magic-link: mail send failed for %s: %v", to, err)
					}
				case <-time.After(10 * time.Second):
					log.Printf("magic-link: mail send timeout (10s) for %s", to)
				}
			}(normalizedEmail, msg, mailCfg)
		}

		w.Write([]byte(`{"status":"ok"}`))
	}
}

// MagicLinkVerifyHandler returns the HTTP handler for POST /api/auth/magic-link/verify.
// Validates code + TTL + attempt-counter, then issues a signed gz_session cookie.
func MagicLinkVerifyHandler(s *store.Store, cfg *config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")

		var req struct {
			Email string `json:"email"`
			Code  string `json:"code"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		normalizedEmail := strings.ToLower(strings.TrimSpace(req.Email))
		if normalizedEmail == "" || req.Code == "" {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid request"}`))
			return
		}

		val, ok := otpStore.Load(normalizedEmail)
		if !ok {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid_or_expired_code"}`))
			return
		}
		entry := val.(*otpEntry)

		// Max-attempts gate runs BEFORE code comparison so leaked/correct
		// codes cannot be exploited after the limit is reached.
		if atomic.LoadInt32(&entry.attempts) >= 3 {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"max_attempts_exceeded"}`))
			return
		}

		// TTL gate.
		if time.Now().After(entry.expiresAt) {
			otpStore.Delete(normalizedEmail)
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid_or_expired_code"}`))
			return
		}

		// Code comparison — increment attempts on miss.
		if entry.code != req.Code {
			atomic.AddInt32(&entry.attempts, 1)
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid_or_expired_code"}`))
			return
		}

		// Success: single-use → delete entry, sign session, set cookie.
		otpStore.Delete(normalizedEmail)
		token := middleware.SignSession(entry.userID, cfg.SessionSecret)
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
		json.NewEncoder(w).Encode(map[string]string{"id": entry.userID})
	}
}

// createMagicLinkUser provisions a new user with ID format "m-{8hex}".
// Tries up to 3 random IDs before giving up (collision is extremely unlikely).
func createMagicLinkUser(s *store.Store, email string) (*model.User, error) {
	for attempt := 0; attempt < 3; attempt++ {
		idBytes := make([]byte, 4)
		if _, err := rand.Read(idBytes); err != nil {
			return nil, err
		}
		id := fmt.Sprintf("m-%s", hex.EncodeToString(idBytes))
		if s.UserExists(id) {
			continue
		}
		user := model.User{
			ID:        id,
			Email:     email,
			CreatedAt: time.Now(),
		}
		if err := s.SaveUser(user); err != nil {
			return nil, err
		}
		if err := s.ProvisionUserDirs(id); err != nil {
			return nil, err
		}
		return &user, nil
	}
	return nil, fmt.Errorf("could not generate unique user ID after 3 attempts")
}
