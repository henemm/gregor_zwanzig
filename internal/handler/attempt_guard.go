package handler

// Fehlversuchsbremse je Schluessel (Issue #2961, ADR-0113). Ein Versuch wird
// VOR dem Vergleich gezaehlt (Reserve), damit gleichzeitige Anfragen den
// Zaehler nicht ueberholen koennen. Gezaehlt wird im GLEITENDEN Fenster:
// hoechstens max Versuche in jedem Intervall der Laenge window (kein
// Ruecksetzen an einem festen Fensterrand). Der max-te Versuch loest eine
// Sperre von lockFor aus. Ein erfolgreicher Versuch setzt den Schluessel
// zurueck (Success).

import (
	"sync"
	"time"
)

type attemptEntry struct {
	attempts    []time.Time // Zeitpunkte der Versuche im Fenster, aufsteigend
	lockedUntil time.Time
}

type attemptGuard struct {
	mu      sync.Mutex
	max     int
	window  time.Duration
	lockFor time.Duration
	entries map[string]*attemptEntry
	now     func() time.Time
}

func newAttemptGuard(max int, window, lockFor time.Duration) *attemptGuard {
	return &attemptGuard{max: max, window: window, lockFor: lockFor,
		entries: map[string]*attemptEntry{}, now: time.Now}
}

// pruneLocked entfernt Versuche, die aelter als das Fenster sind.
func (g *attemptGuard) pruneLocked(e *attemptEntry, now time.Time) {
	i := 0
	for i < len(e.attempts) && now.Sub(e.attempts[i]) >= g.window {
		i++
	}
	e.attempts = e.attempts[i:]
}

// Reserve zaehlt einen Versuch fuer key und meldet, ob er stattfinden darf.
// false heisst: gesperrt oder Kontingent erschoepft — der Aufrufer vergleicht
// dann NICHT.
func (g *attemptGuard) Reserve(key string) bool {
	g.mu.Lock()
	defer g.mu.Unlock()
	now := g.now()
	e := g.entries[key]
	if e == nil {
		e = &attemptEntry{}
		g.entries[key] = e
	}
	g.pruneLocked(e, now)
	if now.Before(e.lockedUntil) || len(e.attempts) >= g.max {
		return false
	}
	e.attempts = append(e.attempts, now)
	if len(e.attempts) >= g.max {
		// Der max-te Versuch laeuft noch; alles danach ist gesperrt.
		e.lockedUntil = now.Add(g.lockFor)
	}
	return true
}

// Success setzt key nach einem gelungenen Versuch zurueck.
func (g *attemptGuard) Success(key string) {
	g.mu.Lock()
	defer g.mu.Unlock()
	delete(g.entries, key)
}

// gc entfernt Eintraege ohne Versuche im Fenster und ohne laufende Sperre.
func (g *attemptGuard) gc() {
	g.mu.Lock()
	defer g.mu.Unlock()
	now := g.now()
	for k, e := range g.entries {
		g.pruneLocked(e, now)
		if len(e.attempts) == 0 && !now.Before(e.lockedUntil) {
			delete(g.entries, k)
		}
	}
}

func (g *attemptGuard) reset() {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.entries = map[string]*attemptEntry{}
	g.now = time.Now
}

func (g *attemptGuard) setNow(f func() time.Time) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.now = f
}

func (g *attemptGuard) count(key string) int {
	g.mu.Lock()
	defer g.mu.Unlock()
	if e := g.entries[key]; e != nil {
		return len(e.attempts)
	}
	return 0
}

// magicFailGuard zaehlt Fehlversuche der Code-Anmeldung je Zieladresse.
var magicFailGuard = newAttemptGuard(5, 15*time.Minute, 15*time.Minute)
