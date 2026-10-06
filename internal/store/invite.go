package store

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

var (
	ErrInviteNotFound = errors.New("invite not found")
	ErrInviteUsed     = errors.New("invite already used")
)

// InviteStore haelt die Admin-Einladungslinks (Issue #2519, ADR-0084) in der
// globalen Datei DataDir/invites.json. Eigenstaendiger Typ (nicht *Store):
// eine Einladung gehoert keinem Nutzer. Die Atomaritaet der Einloesung
// gilt innerhalb EINES gregor-api-Prozesses (in-process Mutex).
type InviteStore struct {
	path    string
	mu      sync.Mutex
	invites []model.Invite
}

// NewInviteStore laedt DataDir/invites.json (fehlende Datei = leer).
func NewInviteStore(dataDir string) *InviteStore {
	s := &InviteStore{path: filepath.Join(dataDir, "invites.json")}
	if data, err := os.ReadFile(s.path); err == nil {
		var saved []model.Invite
		if json.Unmarshal(data, &saved) == nil {
			s.invites = saved
		}
	}
	return s
}

func hashInviteToken(token string) string {
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:])
}

func randomInviteString(n int, enc func([]byte) string) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return enc(b), nil
}

// saveLocked schreibt next atomar; der Aufrufer haelt s.mu.
func (s *InviteStore) saveLocked(next []model.Invite) error {
	data, err := json.Marshal(next)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(s.path), 0o755); err != nil {
		return err
	}
	return writeFileAtomic(s.path, data)
}

// commitLocked persistiert next und uebernimmt es nur bei Erfolg.
func (s *InviteStore) commitLocked(next []model.Invite) error {
	if err := s.saveLocked(next); err != nil {
		return fmt.Errorf("invites: %w", err)
	}
	s.invites = next
	return nil
}

func (s *InviteStore) cloneLocked() []model.Invite {
	return append([]model.Invite(nil), s.invites...)
}

// indexByHashLocked: Index der Einladung mit diesem Token-Hash oder -1.
func (s *InviteStore) indexByHashLocked(hash string) int {
	for i := range s.invites {
		if s.invites[i].TokenHash == hash {
			return i
		}
	}
	return -1
}

// Create legt eine offene Einladung an und liefert den Klartext-Token genau
// einmal zurueck.
//
// Globaler Store ohne Nutzerbezug (kein *Store, daher kein Scope-Marker).
func (s *InviteStore) Create(tier, note, createdBy string) (model.Invite, string, error) {
	token, err := randomInviteString(32, base64.RawURLEncoding.EncodeToString)
	if err != nil {
		return model.Invite{}, "", err
	}
	id, err := randomInviteString(6, hex.EncodeToString)
	if err != nil {
		return model.Invite{}, "", err
	}
	inv := model.Invite{
		ID: id, TokenHash: hashInviteToken(token), Tier: tier, Note: note,
		CreatedAt: time.Now().UTC(), CreatedBy: createdBy,
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := s.commitLocked(append(s.cloneLocked(), inv)); err != nil {
		return model.Invite{}, "", err
	}
	return inv, token, nil
}

// List liefert alle Einladungen, neueste zuerst (Kopie).
//
// Globaler Store ohne Nutzerbezug (kein *Store, daher kein Scope-Marker).
func (s *InviteStore) List() []model.Invite {
	s.mu.Lock()
	out := s.cloneLocked()
	s.mu.Unlock()
	sort.SliceStable(out, func(i, j int) bool { return out[i].CreatedAt.After(out[j].CreatedAt) })
	return out
}

// Revoke widerruft eine offene Einladung. Benutzte: ErrInviteUsed, unbekannte:
// ErrInviteNotFound; bereits widerrufene bleiben unveraendert (kein Fehler).
//
// Globaler Store ohne Nutzerbezug (kein *Store, daher kein Scope-Marker).
func (s *InviteStore) Revoke(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	next := s.cloneLocked()
	for i := range next {
		if next[i].ID != id {
			continue
		}
		if next[i].UsedBy != "" {
			return ErrInviteUsed
		}
		if next[i].RevokedAt != nil {
			return nil
		}
		now := time.Now().UTC()
		next[i].RevokedAt = &now
		return s.commitLocked(next)
	}
	return ErrInviteNotFound
}

// Peek liefert die Einladung, wenn der Token zu einer OFFENEN gehoert.
//
// Globaler Store ohne Nutzerbezug (kein *Store, daher kein Scope-Marker).
func (s *InviteStore) Peek(token string) (model.Invite, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if i := s.indexByHashLocked(hashInviteToken(token)); i >= 0 && s.invites[i].Status() == "open" {
		return s.invites[i], true
	}
	return model.Invite{}, false
}

// Redeem reserviert eine offene Einladung fuer userID (used_by/used_at gesetzt
// und persistiert). ok=false: unbekannt, benutzt oder widerrufen. Genau ein
// paralleler Aufrufer gewinnt (Mutex). err: Persistenzfehler, dann bleibt die
// Einladung offen.
//
// Globaler Store ohne Nutzerbezug (kein *Store, daher kein Scope-Marker).
func (s *InviteStore) Redeem(token, userID string) (model.Invite, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	i := s.indexByHashLocked(hashInviteToken(token))
	if i < 0 || s.invites[i].Status() != "open" {
		return model.Invite{}, false, nil
	}
	next := s.cloneLocked()
	now := time.Now().UTC()
	next[i].UsedBy = userID
	next[i].UsedAt = &now
	if err := s.commitLocked(next); err != nil {
		return model.Invite{}, false, err
	}
	return next[i], true, nil
}

// Rollback macht eine Reservierung rueckgaengig (Konto-Anlage scheiterte).
//
// Globaler Store ohne Nutzerbezug (kein *Store, daher kein Scope-Marker).
func (s *InviteStore) Rollback(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	next := s.cloneLocked()
	for i := range next {
		if next[i].ID == id {
			next[i].UsedBy, next[i].UsedAt = "", nil
			return s.commitLocked(next)
		}
	}
	return ErrInviteNotFound
}
