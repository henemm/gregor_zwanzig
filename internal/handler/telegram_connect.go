package handler

import (
	"encoding/json"
	"encoding/hex"
	"crypto/rand"
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

var telegramTokensPath string

func InitTelegramTokenStore(dataDir string) {
	telegramTokensPath = filepath.Join(dataDir, "telegram_tokens.json")
	loadTelegramTokens()
}

func loadTelegramTokens() {
	if telegramTokensPath == "" {
		return
	}
	data, err := os.ReadFile(telegramTokensPath)
	if err != nil {
		return // fail-soft: file not yet created
	}
	var saved map[string]pendingTelegramToken
	if err := json.Unmarshal(data, &saved); err != nil {
		return
	}
	telegramTokensMu.Lock()
	defer telegramTokensMu.Unlock()
	now := time.Now()
	for k, v := range saved {
		if now.Before(v.ExpiresAt) {
			telegramTokens[k] = v
		}
	}
}

func saveTelegramTokens() {
	if telegramTokensPath == "" {
		return
	}
	telegramTokensMu.Lock()
	data, err := json.Marshal(telegramTokens)
	telegramTokensMu.Unlock()
	if err != nil {
		return
	}
	_ = os.WriteFile(telegramTokensPath, data, 0600)
}

var (
	telegramTokens   = map[string]pendingTelegramToken{}
	telegramTokensMu sync.Mutex
)

func newTelegramToken() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		panic("crypto/rand unavailable: " + err.Error())
	}
	return hex.EncodeToString(b)
}

// GetTelegramLinkHandler — GET /api/auth/telegram-link
// Generates a one-time deep-link token (24h TTL) for the authenticated user.
func GetTelegramLinkHandler(s *store.Store) http.HandlerFunc {
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

		token := newTelegramToken()
		telegramTokensMu.Lock()
		telegramTokens[token] = pendingTelegramToken{UserID: userID, ExpiresAt: time.Now().Add(24 * time.Hour)}
		telegramTokensMu.Unlock()
		saveTelegramTokens()

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
func PostTelegramConnectHandler(s *store.Store) http.HandlerFunc {
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

		telegramTokensMu.Lock()
		pt, ok := telegramTokens[body.Token]
		if ok {
			delete(telegramTokens, body.Token)
		}
		telegramTokensMu.Unlock()
		saveTelegramTokens()

		if !ok || time.Now().After(pt.ExpiresAt) {
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
