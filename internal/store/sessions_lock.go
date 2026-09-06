package store

import "sync"

// Sperre je Nutzer fuer die Gaesteliste gueltiger Anmeldungen (Issue #2129).
// Vorbild und Begruendung wie briefing_lock.go: sie liegt auf PAKET-Ebene und
// nicht als Feld im Store, weil WithUser eine flache Kopie zurueckgibt -- eine
// Sperre im Struct waere pro Kopie eine andere und damit wirkungslos. Es laeuft
// genau ein gregor-api-Prozess je Umgebung, darum reicht eine prozessinterne
// Sperre.
//
// Der Schluessel ist die uebergebene Nutzerkennung, NICHT s.UserID: die
// Gaesteliste wird aus der Middleware und aus oeffentlichen Endpunkten heraus
// bearbeitet, wo der Store noch nicht auf den Nutzer eingeengt ist.
var (
	sessionLocksMu sync.Mutex
	sessionLocks   = map[string]*sessionLock{}
)

type sessionLock struct {
	mu   sync.Mutex
	refs int
}

// lockSessions sperrt die Gaesteliste eines Nutzers und liefert die
// Freigabe-Funktion. Der Aufrufer haelt die Sperre ueber den GANZEN
// Lese-Aendern-Schreib-Zyklus (defer unlock()).
func lockSessions(userId string) func() {
	sessionLocksMu.Lock()
	entry, ok := sessionLocks[userId]
	if !ok {
		entry = &sessionLock{}
		sessionLocks[userId] = entry
	}
	entry.refs++
	sessionLocksMu.Unlock()

	entry.mu.Lock()

	var once sync.Once
	return func() {
		once.Do(func() {
			entry.mu.Unlock()
			sessionLocksMu.Lock()
			entry.refs--
			if entry.refs == 0 {
				delete(sessionLocks, userId)
			}
			sessionLocksMu.Unlock()
		})
	}
}
