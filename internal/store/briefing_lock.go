package store

import "sync"

// Sperre je Nutzer+Briefing (Issue #1395 Scheibe 1).
//
// Sie liegt auf PAKET-Ebene und NICHT als Feld im Store: WithUser gibt eine
// flache Kopie des Stores zurueck (store.go), pro HTTP-Anfrage entsteht also
// eine eigene Instanz -- eine Sperre im Struct waere pro Kopie eine andere und
// damit wirkungslos. Es laeuft genau ein gregor-api-Prozess je Umgebung, darum
// reicht eine prozessinterne Sperre (kein Datei-Lock noetig).
//
// Wachstum: jeder Eintrag ist referenzgezaehlt und verschwindet, sobald ihn
// niemand mehr haelt oder darauf wartet. Die Tabelle traegt also nur die
// GERADE aktiven Briefings, nie eine Historie geloeschter Touren.
var (
	briefingLocksMu sync.Mutex
	briefingLocks   = map[string]*briefingLock{}
)

type briefingLock struct {
	mu   sync.Mutex
	refs int
}

// LockBriefing sperrt <UserID, id> und liefert die Freigabe-Funktion. Der
// Aufrufer haelt die Sperre ueber den GANZEN Lese-Pruef-Schreib-Zyklus
// (defer unlock()). Nutzer-Trennung steckt im Schluessel: gleiche Briefing-ID
// bei verschiedenen Nutzern sind verschiedene Sperren.
func (s *Store) LockBriefing(id string) func() {
	// \x00 als Trenner: kommt in UserID/ID nicht vor, verhindert Kollisionen
	// wie ("ab","c") vs. ("a","bc").
	key := s.UserID + "\x00" + id

	briefingLocksMu.Lock()
	entry, ok := briefingLocks[key]
	if !ok {
		entry = &briefingLock{}
		briefingLocks[key] = entry
	}
	entry.refs++
	briefingLocksMu.Unlock()

	entry.mu.Lock()

	var once sync.Once
	return func() {
		once.Do(func() {
			entry.mu.Unlock()
			briefingLocksMu.Lock()
			entry.refs--
			if entry.refs == 0 {
				delete(briefingLocks, key)
			}
			briefingLocksMu.Unlock()
		})
	}
}
