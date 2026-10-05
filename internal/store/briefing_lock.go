package store

import (
	"errors"
	"os"
	"path/filepath"
	"sync"
	"syscall"
	"time"
)

// Sperre je Nutzer+Briefing (Issue #1395 Scheibe 1).
//
// Sie liegt auf PAKET-Ebene und NICHT als Feld im Store: WithUser gibt eine
// flache Kopie des Stores zurueck (store.go), pro HTTP-Anfrage entsteht also
// eine eigene Instanz -- eine Sperre im Struct waere pro Kopie eine andere und
// damit wirkungslos. Es laeuft genau ein gregor-api-Prozess je Umgebung, darum
// reicht fuer Go-gegen-Go eine prozessinterne Sperre. Seit ADR-0083 (#2158)
// kommt darunter ein flock auf <id>.json.lock, damit auch der Python-Kern
// (schreibt briefings/ ebenfalls) ausgeschlossen wird.
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

// ErrBriefingLockTimeout: die Datei-Sperre war nach der Frist nicht zu haben.
var ErrBriefingLockTimeout = errors.New("briefing lock timeout")

// briefingLockTimeout ist die Frist fuer den Datei-flock (ADR-0083: ~5 s).
var (
	briefingLockTimeoutMu sync.Mutex
	briefingLockTimeout   = 5 * time.Second
)

// SetBriefingLockTimeout verkuerzt die Frist (Tests) und liefert die
// Rueckstell-Funktion.
func SetBriefingLockTimeout(d time.Duration) (restore func()) {
	briefingLockTimeoutMu.Lock()
	old := briefingLockTimeout
	briefingLockTimeout = d
	briefingLockTimeoutMu.Unlock()
	return func() {
		briefingLockTimeoutMu.Lock()
		briefingLockTimeout = old
		briefingLockTimeoutMu.Unlock()
	}
}

func currentBriefingLockTimeout() time.Duration {
	briefingLockTimeoutMu.Lock()
	defer briefingLockTimeoutMu.Unlock()
	return briefingLockTimeout
}

// briefingLockPath ist der mit Python gemeinsame Sperrdateipfad (ADR-0083).
func (s *Store) briefingLockPath(id string) string {
	return filepath.Join(s.DataDir, "users", s.UserID, "briefings", id+".json.lock")
}

// flockPoll holt LOCK_EX|LOCK_NB im 20-ms-Takt. timeout<=0 wartet unbegrenzt.
func flockPoll(f *os.File, timeout time.Duration) error {
	var deadline time.Time
	if timeout > 0 {
		deadline = time.Now().Add(timeout)
	}
	for {
		err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB)
		if err == nil {
			return nil
		}
		if !errors.Is(err, syscall.EWOULDBLOCK) && !errors.Is(err, syscall.EINTR) {
			return err
		}
		if timeout > 0 && time.Now().After(deadline) {
			return ErrBriefingLockTimeout
		}
		time.Sleep(20 * time.Millisecond)
	}
}

// LockBriefing sperrt <UserID, id> und liefert die Freigabe-Funktion. Der
// Aufrufer haelt die Sperre ueber den GANZEN Lese-Pruef-Schreib-Zyklus
// (defer unlock()). Nutzer-Trennung steckt im Schluessel: gleiche Briefing-ID
// bei verschiedenen Nutzern sind verschiedene Sperren.
//
// Diese Variante wartet auf den Datei-flock OHNE Frist; Handler nutzen
// LockBriefingErr (Frist -> 503).
// gz-store-scope-required: baut den Sperrschluessel direkt aus s.UserID, ohne requireUser aufzurufen
func (s *Store) LockBriefing(id string) func() {
	unlock, err := s.lockBriefing(id, 0)
	if err != nil {
		// Pfad nicht anlegbar (z. B. leerer Nutzer): nur der Prozess-Mutex.
		unlock, _ = s.lockBriefing(id, -1)
	}
	return unlock
}

// LockBriefingErr wie LockBriefing, aber mit Frist (~5 s) fuer den
// Datei-flock. Fristablauf => ErrBriefingLockTimeout, nichts ist gesperrt.
// gz-store-scope-required: baut den Sperrschluessel direkt aus s.UserID, ohne requireUser aufzurufen
func (s *Store) LockBriefingErr(id string) (func(), error) {
	return s.lockBriefing(id, currentBriefingLockTimeout())
}

// lockBriefing: timeout<0 = nur Mutex, 0 = flock unbegrenzt, >0 = mit Frist.
func (s *Store) lockBriefing(id string, timeout time.Duration) (func(), error) {
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
	var lf *os.File
	release := func() {
		once.Do(func() {
			if lf != nil {
				_ = syscall.Flock(int(lf.Fd()), syscall.LOCK_UN)
				lf.Close()
			}
			entry.mu.Unlock()
			briefingLocksMu.Lock()
			entry.refs--
			if entry.refs == 0 {
				delete(briefingLocks, key)
			}
			briefingLocksMu.Unlock()
		})
	}
	if timeout < 0 {
		return release, nil
	}
	f, err := s.openBriefingLockFile(id)
	if err == nil {
		err = flockPoll(f, timeout)
		if err != nil {
			f.Close()
		} else {
			lf = f
		}
	}
	if err != nil {
		release()
		return func() {}, err
	}
	return release, nil
}

func (s *Store) openBriefingLockFile(id string) (*os.File, error) {
	if s.requireUser() != nil || !ValidEntityID(id) {
		return nil, errors.New("briefing lock: ungueltiger Nutzer oder Id")
	}
	path := s.briefingLockPath(id)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return nil, err
	}
	return os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o600)
}
