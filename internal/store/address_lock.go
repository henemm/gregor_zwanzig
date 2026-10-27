package store

import "sync"

// Sperre je normalisierter E-Mail-Adresse (Issue #2147): „Adresse auflösen +
// Konto anlegen/ändern" läuft unter EINER Sperre, damit zwei gleichzeitige
// Anmeldewege nicht beide „Adresse frei" sehen. Paketweit wie lockSessions
// (WithUser liefert flache Kopien; ein gregor-api-Prozess je Umgebung), damit
// die späteren Scheiben (Registrierung, Profil, Google) dieselbe Sperre nutzen.
var (
	addressLocksMu sync.Mutex
	addressLocks   = map[string]*sessionLock{}
)

// LockEmailAddress sperrt die Adresse und liefert die Freigabe-Funktion. Der
// Aufrufer übergibt die bereits normalisierte Adresse (NormalizeEmailAddress).
func LockEmailAddress(normalizedAddress string) (unlock func()) {
	addressLocksMu.Lock()
	entry, ok := addressLocks[normalizedAddress]
	if !ok {
		entry = &sessionLock{}
		addressLocks[normalizedAddress] = entry
	}
	entry.refs++
	addressLocksMu.Unlock()

	entry.mu.Lock()

	var once sync.Once
	return func() {
		once.Do(func() {
			entry.mu.Unlock()
			addressLocksMu.Lock()
			entry.refs--
			if entry.refs == 0 {
				delete(addressLocks, normalizedAddress)
			}
			addressLocksMu.Unlock()
		})
	}
}
