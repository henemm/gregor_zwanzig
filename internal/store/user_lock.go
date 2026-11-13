package store

import "sync"

// Sperre je Nutzer fuer user.json (Issue #2961, GA6, ADR-0115). Jeder
// Lesen-Aendern-Schreiben-Weg auf user.json (SaveUser, UpdateUser, die
// Merge-Setter) laeuft unter ihr. Paketweit wie lockSessions: WithUser liefert
// flache Kopien, ein gregor-api-Prozess je Umgebung, und Go ist der einzige
// Schreiber von user.json (der Python-Core liest nur).
var (
	userLocksMu sync.Mutex
	userLocks   = map[string]*sessionLock{}
)

// lockUserJSON sperrt die user.json eines Nutzers und liefert die Freigabe.
func lockUserJSON(id string) func() {
	userLocksMu.Lock()
	entry, ok := userLocks[id]
	if !ok {
		entry = &sessionLock{}
		userLocks[id] = entry
	}
	entry.refs++
	userLocksMu.Unlock()

	entry.mu.Lock()

	var once sync.Once
	return func() {
		once.Do(func() {
			entry.mu.Unlock()
			userLocksMu.Lock()
			entry.refs--
			if entry.refs == 0 {
				delete(userLocks, id)
			}
			userLocksMu.Unlock()
		})
	}
}
