package store

import "sync"

// Sperre je Nutzer fuer die Mengen-Quoten (Issue #2482, Muster briefing_lock.go).
//
// Zaehlen und Speichern einer Neuanlage muessen gemeinsam geschuetzt sein, sonst
// zaehlen zwei parallele Anlagen bei "Grenze minus 1" beide und speichern beide.
// Paket-Ebene statt Struct-Feld aus demselben Grund wie bei LockBriefing
// (WithUser liefert je Anfrage eine Kopie). Prozessintern genuegt: es laeuft
// genau ein gregor-api-Prozess je Umgebung.
//
// Lock-Reihenfolge (Deadlock-Vermeidung): IMMER zuerst LockQuota, danach
// LockBriefing — nie umgekehrt.
var (
	quotaLocksMu sync.Mutex
	quotaLocks   = map[string]*quotaLock{}
)

type quotaLock struct {
	mu   sync.Mutex
	refs int
}

// LockQuota sperrt die Mengen-Quote des Nutzers s.UserID und liefert die
// Freigabe-Funktion. Verschiedene Nutzer blockieren sich nicht.
// gz-store-scope-required: baut den Sperrschluessel direkt aus s.UserID, ohne requireUser aufzurufen
func (s *Store) LockQuota() func() {
	key := s.UserID

	quotaLocksMu.Lock()
	entry, ok := quotaLocks[key]
	if !ok {
		entry = &quotaLock{}
		quotaLocks[key] = entry
	}
	entry.refs++
	quotaLocksMu.Unlock()

	entry.mu.Lock()

	var once sync.Once
	return func() {
		once.Do(func() {
			entry.mu.Unlock()
			quotaLocksMu.Lock()
			entry.refs--
			if entry.refs == 0 {
				delete(quotaLocks, key)
			}
			quotaLocksMu.Unlock()
		})
	}
}
