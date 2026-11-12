package handler

import "sync"

// keyedLock serialisiert Vorgaenge je Schluessel (z. B. je Nutzer), ohne
// unbeteiligte Schluessel zu blockieren (Issue #2961). Eintraege werden
// entfernt, sobald niemand mehr wartet — die Tabelle waechst nicht.
type keyedLock struct {
	mu    sync.Mutex
	locks map[string]*keyedLockEntry
}

type keyedLockEntry struct {
	mu      sync.Mutex
	waiters int
}

func newKeyedLock() *keyedLock {
	return &keyedLock{locks: map[string]*keyedLockEntry{}}
}

// Lock sperrt key und liefert die Freigabe.
func (k *keyedLock) Lock(key string) (unlock func()) {
	k.mu.Lock()
	e := k.locks[key]
	if e == nil {
		e = &keyedLockEntry{}
		k.locks[key] = e
	}
	e.waiters++
	k.mu.Unlock()

	e.mu.Lock()
	return func() {
		e.mu.Unlock()
		k.mu.Lock()
		e.waiters--
		if e.waiters == 0 {
			delete(k.locks, key)
		}
		k.mu.Unlock()
	}
}
