package handler

import (
	"sync"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"
)

// ChallengeEntry holds a pending WebAuthn ceremony state between Begin and Finish.
// Issue #450 — V1 Add-on.
type ChallengeEntry struct {
	SessionData webauthn.SessionData
	UserID      string
	Email       string // public register/begin; empty for auth-protected flows
	ExpiresAt   time.Time
}

// ChallengeStore is an in-memory sync.Map keyed by base64url-encoded challenge.
// 5-Min TTL, restart-volatile (acceptable per spec — user retries).
type ChallengeStore struct {
	m sync.Map
}

func NewChallengeStore() *ChallengeStore {
	cs := &ChallengeStore{}
	go cs.gc()
	return cs
}

// Put stores a pending challenge entry.
func (cs *ChallengeStore) Put(challenge string, entry *ChallengeEntry) {
	cs.m.Store(challenge, entry)
}

// Take atomically loads and deletes a challenge entry. Returns (nil, false)
// if the challenge is unknown OR expired. Deletion is destructive even when
// expired — replay attempts on the same challenge therefore also fail.
func (cs *ChallengeStore) Take(challenge string) (*ChallengeEntry, bool) {
	v, ok := cs.m.LoadAndDelete(challenge)
	if !ok {
		return nil, false
	}
	e := v.(*ChallengeEntry)
	if time.Now().After(e.ExpiresAt) {
		return nil, false
	}
	return e, true
}

func (cs *ChallengeStore) gc() {
	for range time.Tick(time.Minute) {
		now := time.Now()
		cs.m.Range(func(k, v any) bool {
			if now.After(v.(*ChallengeEntry).ExpiresAt) {
				cs.m.Delete(k)
			}
			return true
		})
	}
}
