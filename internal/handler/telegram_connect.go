package handler

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"path/filepath"
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

// saveLocked persistiert tokens atomar (Temp-Datei + Rename, Issue #2160
// AC-14) und gibt Fehler zurueck. Der Aufrufer haelt s.mu. Scheitert der
// Schreibvorgang, bleibt keine Temp-Datei liegen.
func (s *TelegramTokenStore) saveLocked(tokens map[string]pendingTelegramToken) error {
	data, err := json.Marshal(tokens)
	if err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(s.path), filepath.Base(s.path)+".tmp-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	_, werr := tmp.Write(data)
	if werr == nil {
		werr = tmp.Sync()
	}
	if cerr := tmp.Close(); werr == nil {
		werr = cerr
	}
	if werr == nil {
		werr = os.Rename(tmpName, s.path)
	}
	if werr != nil {
		_ = os.Remove(tmpName)
	}
	return werr
}

// copyTokensLocked liefert eine Kopie der Map ohne die Eintraege, fuer die
// drop true meldet. Der Aufrufer haelt s.mu.
func (s *TelegramTokenStore) copyTokensLocked(drop func(pendingTelegramToken) bool) map[string]pendingTelegramToken {
	out := make(map[string]pendingTelegramToken, len(s.tokens))
	for k, v := range s.tokens {
		if drop == nil || !drop(v) {
			out[k] = v
		}
	}
	return out
}

// IssueToken erzeugt einen neuen Deep-Link-Token (24h TTL) fuer userID und
// persistiert ihn. Scheitert die Persistierung, wird der Token verworfen und
// der Fehler zurueckgegeben (Issue #2160 AC-14) — nie ein ungespeicherter Token.
func (s *TelegramTokenStore) IssueToken(userID string) (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	token := hex.EncodeToString(b)
	s.mu.Lock()
	defer s.mu.Unlock()
	next := s.copyTokensLocked(nil)
	next[token] = pendingTelegramToken{UserID: userID, ExpiresAt: time.Now().Add(24 * time.Hour)}
	if err := s.saveLocked(next); err != nil {
		return "", err
	}
	s.tokens = next
	return token, nil
}

// CreateToken ist der Bestandsweg ohne Fehlerrueckgabe; ein Speicherfehler
// wird geloggt und liefert "" (Produktivcode nutzt IssueToken).
func (s *TelegramTokenStore) CreateToken(userID string) string {
	token, err := s.IssueToken(userID)
	if err != nil {
		log.Printf("telegram tokens: token konnte nicht gespeichert werden: %v", err)
		return ""
	}
	return token
}

// RemoveByUser entfernt alle Tokens von userID und persistiert das Ergebnis
// (Issue #2160 AC-10). Bei Speicherfehler bleibt der Speicherzustand
// unveraendert und der Fehler wird zurueckgegeben.
func (s *TelegramTokenStore) RemoveByUser(userID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	next := s.copyTokensLocked(func(pt pendingTelegramToken) bool { return pt.UserID == userID })
	if len(next) == len(s.tokens) {
		return nil
	}
	if err := s.saveLocked(next); err != nil {
		return err
	}
	s.tokens = next
	return nil
}

// gc entfernt abgelaufene Tokens (Issue #2160 AC-15). Gestartet vom Reaper
// aus cmd/server/main.go, nie aus dem Konstruktor. Speicherfehler werden
// geloggt; abgelaufene Eintraege filtert load() ohnehin.
func (s *TelegramTokenStore) gc(now time.Time) {
	s.mu.Lock()
	defer s.mu.Unlock()
	next := s.copyTokensLocked(func(pt pendingTelegramToken) bool { return !now.Before(pt.ExpiresAt) })
	if len(next) == len(s.tokens) {
		return
	}
	s.tokens = next
	if err := s.saveLocked(next); err != nil {
		log.Printf("telegram tokens: gc konnte nicht speichern: %v", err)
	}
}

// ResolveAndDelete looks up the token, deletes it if found, and returns the
// pending token details. The second return value is false if the token does not
// exist or is expired.
func (s *TelegramTokenStore) ResolveAndDelete(token string) (pendingTelegramToken, bool) {
	s.mu.Lock()
	pt, ok := s.tokens[token]
	if ok {
		delete(s.tokens, token)
		if err := s.saveLocked(s.tokens); err != nil {
			log.Printf("telegram tokens: speichern nach Einloesung fehlgeschlagen: %v", err)
		}
	}
	s.mu.Unlock()
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
		// Issue #2160 AC-10/AC-16: Laden und Token-Ausgabe unter demselben
		// Lock wie die Kontoloeschung — sonst schreibt ein Link-Request, der
		// den Nutzer kurz vor der Kaskade geladen hat, danach noch einen Token
		// fuer einen geloeschten Nutzer. Lock-Reihenfolge: telegramConnectMu
		// vor ts.mu (wie Kaskade und Connect).
		telegramConnectMu.Lock()
		user, err := s.LoadUser(userID)
		if err != nil || user == nil {
			telegramConnectMu.Unlock()
			http.Error(w, "user not found", http.StatusNotFound)
			return
		}
		token, err := ts.IssueToken(userID)
		telegramConnectMu.Unlock()
		if err != nil {
			log.Printf("telegram-link: token not persisted for %s: %v", userID, err)
			http.Error(w, "token store unavailable", http.StatusInternalServerError)
			return
		}

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

// telegramConnectMu serialisiert Kollisionsprüfung und Speichern im
// Connect-Endpunkt (Issue #2141). Wirkt prozessintern — je Umgebung läuft
// genau ein gregor-api-Prozess auf demselben Datenverzeichnis.
var telegramConnectMu sync.Mutex

// PostTelegramConnectHandler — POST /api/internal/telegram-connect
// Called only by the Python InboundTelegramReader (localhost only).
// Resolves the one-time token to a user_id and saves the chat_id.
func PostTelegramConnectHandler(s *store.Store, ts *TelegramTokenStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !requireLocalOnly(w, r) {
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

		// Issue #2141: Eindeutigkeit der Chat-ID. Prüfung UND Speichern laufen
		// unter demselben Lock, sonst könnten zwei gleichzeitige Connects
		// beide an der Prüfung vorbeikommen (TOCTOU). Issue #2160 AC-16: auch
		// der Nutzer wird erst UNTER dem Lock geladen — die Kontoloeschung
		// nimmt denselben Lock, ein Connect danach findet keinen Nutzer und
		// legt den Ordner nicht als Zombie neu an.
		telegramConnectMu.Lock()
		defer telegramConnectMu.Unlock()

		user, err := s.LoadUser(pt.UserID)
		if err != nil || user == nil {
			http.Error(w, "user not found", http.StatusNotFound)
			return
		}

		existing, err := s.FindUserByTelegramChatID(body.ChatID)
		if err != nil {
			http.Error(w, "lookup failed", http.StatusInternalServerError)
			return
		}
		if existing != nil && existing.ID != pt.UserID {
			// Re-Connect desselben Nutzers ist bewusst kein Konflikt.
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]string{"error": "chat_id_already_linked"})
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
