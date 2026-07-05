package handler

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

type pendingTelegramToken struct {
	UserID    string    `json:"user_id"`
	ExpiresAt time.Time `json:"expires_at"`
}

// TelegramTokenStore holds pending deep-link tokens for Telegram account
// connection. It replaces the previous package-level state and is created once
// in main.go, then injected into the handlers that need it.
type TelegramTokenStore struct {
	path   string
	tokens map[string]pendingTelegramToken
	mu     sync.Mutex
}

// NewTelegramTokenStore creates a store backed by a JSON file under dataDir.
func NewTelegramTokenStore(dataDir string) *TelegramTokenStore {
	s := &TelegramTokenStore{
		path:   filepath.Join(dataDir, "telegram_tokens.json"),
		tokens: map[string]pendingTelegramToken{},
	}
	s.load()
	return s
}

func (s *TelegramTokenStore) load() {
	data, err := os.ReadFile(s.path)
	if err != nil {
		return // fail-soft: file not yet created
	}
	var saved map[string]pendingTelegramToken
	if err := json.Unmarshal(data, &saved); err != nil {
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	now := time.Now()
	for k, v := range saved {
		if now.Before(v.ExpiresAt) {
			s.tokens[k] = v
		}
	}
}

func (s *TelegramTokenStore) save() {
	s.mu.Lock()
	data, err := json.Marshal(s.tokens)
	s.mu.Unlock()
	if err != nil {
		return
	}
	_ = os.WriteFile(s.path, data, 0600)
}

// CreateToken generates a new one-time deep-link token for userID and returns
// the raw token. Tokens expire after 24 hours.
func (s *TelegramTokenStore) CreateToken(userID string) string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		panic("crypto/rand unavailable: " + err.Error())
	}
	token := hex.EncodeToString(b)
	s.mu.Lock()
	s.tokens[token] = pendingTelegramToken{UserID: userID, ExpiresAt: time.Now().Add(24 * time.Hour)}
	s.mu.Unlock()
	s.save()
	return token
}

// ResolveAndDelete looks up the token, deletes it if found, and returns the
// pending token details. The second return value is false if the token does not
// exist or is expired.
func (s *TelegramTokenStore) ResolveAndDelete(token string) (pendingTelegramToken, bool) {
	s.mu.Lock()
	pt, ok := s.tokens[token]
	if ok {
		delete(s.tokens, token)
	}
	s.mu.Unlock()
	if ok {
		s.save()
	}
	if !ok || time.Now().After(pt.ExpiresAt) {
		return pendingTelegramToken{}, false
	}
	return pt, true
}

// GetTelegramLinkHandler — GET /api/auth/telegram-link
// Generates a one-time deep-link token (24h TTL) for the authenticated user.
func GetTelegramLinkHandler(s *store.Store, ts *TelegramTokenStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		botUsername := os.Getenv("TELEGRAM_BOT_USERNAME")
		if botUsername == "" {
			http.Error(w, "TELEGRAM_BOT_USERNAME not configured", http.StatusInternalServerError)
			return
		}
		user, err := s.LoadUser(userID)
		if err != nil || user == nil {
			http.Error(w, "user not found", http.StatusNotFound)
			return
		}

		token := ts.CreateToken(userID)

		connected := user.TelegramChatID != ""
		suffix := ""
		if connected && len(user.TelegramChatID) >= 3 {
			suffix = "..." + user.TelegramChatID[len(user.TelegramChatID)-3:]
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"link":           "https://t.me/" + botUsername + "?start=" + token,
			"connected":      connected,
			"chat_id_suffix": suffix,
		})
	}
}

// GetTelegramStatusHandler — GET /api/auth/telegram-status
// Returns whether the authenticated user has a linked Telegram chat ID.
func GetTelegramStatusHandler(s *store.Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := middleware.UserIDFromContext(r.Context())
		if userID == "" {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		user, err := s.LoadUser(userID)
		if err != nil || user == nil {
			http.Error(w, "user not found", http.StatusNotFound)
			return
		}
		connected := user.TelegramChatID != ""
		suffix := ""
		if connected && len(user.TelegramChatID) >= 3 {
			suffix = "..." + user.TelegramChatID[len(user.TelegramChatID)-3:]
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"connected":      connected,
			"chat_id_suffix": suffix,
		})
	}
}

// PostTelegramConnectHandler — POST /api/internal/telegram-connect
// Called only by the Python InboundTelegramReader (localhost only).
// Resolves the one-time token to a user_id and saves the chat_id.
func PostTelegramConnectHandler(s *store.Store, ts *TelegramTokenStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		remoteHost := r.RemoteAddr
		if !strings.HasPrefix(remoteHost, "127.0.0.1:") && !strings.HasPrefix(remoteHost, "[::1]:") {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}

		var body struct {
			Token  string `json:"token"`
			ChatID string `json:"chat_id"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.Token == "" || body.ChatID == "" {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}

		pt, ok := ts.ResolveAndDelete(body.Token)
		if !ok {
			http.Error(w, "token invalid or expired", http.StatusUnprocessableEntity)
			return
		}

		user, err := s.LoadUser(pt.UserID)
		if err != nil || user == nil {
			http.Error(w, "user not found", http.StatusNotFound)
			return
		}
		user.TelegramChatID = body.ChatID
		if err := s.SaveUser(*user); err != nil {
			http.Error(w, "save failed", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}
}
