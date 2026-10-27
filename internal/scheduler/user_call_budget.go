package scheduler

// Fix #2149 Scheibe B — In-Flight-Register je (jobID, userID): haelt Nutzer-
// aufrufe, deren Wartebudget abgelaufen ist, die aber im Hintergrund noch
// weiterlaufen. Bewusst NICHT persistiert (ein Marker aus einem Vorprozess
// ist nach einem Neustart bedeutungslos, Spec Abschnitt 2 / AC-14).
//
// Lock-Reihenfolge: userCallBudget.mu wird nie gemeinsam mit s.mu oder
// userState.mu gehalten.
//
// Spec: docs/specs/modules/fix_2149_scheduler_budget_teilb.md

import (
	"sync"
	"time"
)

// callToken identifiziert eine einzelne Ausloesung eines Nutzeraufrufs.
type callToken uint64

type inFlightEntry struct {
	token    callToken
	resultCh chan error
	started  time.Time
	timer    *time.Timer // Alarm-Deckel; nil bei Briefing-Jobs (Spec Abschnitt 3)
}

// userCallBudget ist das In-Flight-Register (Spec Abschnitt 2).
type userCallBudget struct {
	mu    sync.Mutex
	state map[string]map[string]*inFlightEntry // [jobID][userID]
	next  callToken
}

func newUserCallBudget() *userCallBudget {
	return &userCallBudget{state: make(map[string]map[string]*inFlightEntry)}
}

// Begin legt den Eintrag fuer einen frisch gestarteten Aufruf an und vergibt
// einen neuen, monoton steigenden Token. Ist callCap > 0, startet im selben
// Moment der Deckel: laeuft er ab, bevor das Ergebnis abgeholt wurde, wird der
// Marker ohne jede Buchung freigegeben und onCap aufgerufen.
func (b *userCallBudget) Begin(jobID, userID string, resultCh chan error, callCap time.Duration, onCap func()) callToken {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.next++
	tok := b.next
	byUser, ok := b.state[jobID]
	if !ok {
		byUser = make(map[string]*inFlightEntry)
		b.state[jobID] = byUser
	}
	entry := &inFlightEntry{token: tok, resultCh: resultCh, started: time.Now()}
	if callCap > 0 {
		// Der Token-Vergleich in Finish macht eine doppelte Freigabe sicher:
		// feuert der Deckel, waehrend TryHarvest/Finish den Eintrag schon
		// entfernt (timer.Stop() liefert dann false), findet der Callback den
		// Token nicht mehr und bucht/loggt nichts. Nicht entfernen.
		entry.timer = time.AfterFunc(callCap, func() {
			if b.Finish(jobID, userID, tok) && onCap != nil {
				onCap()
			}
		})
	}
	byUser[userID] = entry
	return tok
}

// IsInFlight meldet, ob fuer (jobID, userID) noch ein Marker aktiv ist.
func (b *userCallBudget) IsInFlight(jobID, userID string) bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	_, ok := b.state[jobID][userID]
	return ok
}

// TryHarvest liest nicht-blockierend ein inzwischen fertiges Spaetergebnis des
// aktuell hinterlegten Aufrufs. Bei Erfolg wird der Marker entfernt und der
// Deckel gestoppt.
func (b *userCallBudget) TryHarvest(jobID, userID string) (error, bool) {
	b.mu.Lock()
	defer b.mu.Unlock()
	entry, ok := b.state[jobID][userID]
	if !ok {
		return nil, false
	}
	select {
	case err := <-entry.resultCh:
		b.removeLocked(jobID, userID, entry)
		return err, true
	default:
		return nil, false
	}
}

// Finish entfernt den Eintrag nur, wenn token noch der aktuell hinterlegte
// ist. Rueckgabe: ob entfernt wurde (= Token war aktuell).
func (b *userCallBudget) Finish(jobID, userID string, token callToken) bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	entry, ok := b.state[jobID][userID]
	if !ok || entry.token != token {
		return false
	}
	b.removeLocked(jobID, userID, entry)
	return true
}

// Count liefert die Zahl der aktuell aktiven Marker eines Jobs.
func (b *userCallBudget) Count(jobID string) int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return len(b.state[jobID])
}

func (b *userCallBudget) removeLocked(jobID, userID string, entry *inFlightEntry) {
	if entry.timer != nil {
		entry.timer.Stop()
	}
	delete(b.state[jobID], userID)
}
