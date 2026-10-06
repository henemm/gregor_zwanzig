package store

import "sync"

// Prozessinterne Sperren je Nutzer fuer Orte, Gruppen und Metrik-Vorlagen
// (Issue #2158, ADR-0083). Paketebene aus demselben Grund wie briefing_lock.go
// (WithUser liefert je Anfrage eine Kopie). Python schreibt diese Dateien
// nicht, darum genuegt der Prozess-Mutex (kein flock).
//
// Lock-Reihenfolge (verbindlich): Quota -> Gruppen/Vorlagen -> Ort ->
// Briefing-Mutex -> Datei-flock. DeleteGroup darf nach der Gruppen-Sperre Orte
// sperren, nie umgekehrt.
type keyedLocks struct {
	mu      sync.Mutex
	entries map[string]*keyedEntry
}

type keyedEntry struct {
	mu   sync.Mutex
	refs int
}

func (k *keyedLocks) lock(key string) func() {
	k.mu.Lock()
	if k.entries == nil {
		k.entries = map[string]*keyedEntry{}
	}
	e, ok := k.entries[key]
	if !ok {
		e = &keyedEntry{}
		k.entries[key] = e
	}
	e.refs++
	k.mu.Unlock()

	e.mu.Lock()
	var once sync.Once
	return func() {
		once.Do(func() {
			e.mu.Unlock()
			k.mu.Lock()
			e.refs--
			if e.refs == 0 {
				delete(k.entries, key)
			}
			k.mu.Unlock()
		})
	}
}

var (
	locationLocks     keyedLocks
	groupLocks        keyedLocks
	metricPresetLocks keyedLocks
)

// LockLocation sperrt den Ort <UserID, id> ueber den ganzen Lese-Aendern-
// Schreib-Zyklus. Verschiedene Nutzer/Orte blockieren sich nicht.
// gz-store-scope-required: baut den Sperrschluessel direkt aus s.UserID, ohne requireUser aufzurufen
func (s *Store) LockLocation(id string) func() {
	return locationLocks.lock(s.UserID + "\x00" + id)
}

// LockGroups sperrt groups.json des Nutzers (inkl. Migration beim Lesen).
// Nicht wiedereintrittsfaehig: darunter nur die *Locked-Varianten benutzen.
// gz-store-scope-required: baut den Sperrschluessel direkt aus s.UserID, ohne requireUser aufzurufen
func (s *Store) LockGroups() func() {
	return groupLocks.lock(s.UserID)
}

// LockMetricPresets sperrt metric_presets.json des Nutzers.
// gz-store-scope-required: baut den Sperrschluessel direkt aus s.UserID, ohne requireUser aufzurufen
func (s *Store) LockMetricPresets() func() {
	return metricPresetLocks.lock(s.UserID)
}
