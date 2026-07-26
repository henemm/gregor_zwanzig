package store

import (
	"sync"
	"testing"
	"time"
)

// Issue #1395 Scheibe 1: prozessweite Sperre je Nutzer+Briefing. Es laeuft
// genau ein gregor-api-Prozess je Umgebung, darum reicht eine In-Prozess-Sperre.

// Nebenlaeufige Schreiber auf DASSELBE Briefing werden serialisiert. Der
// Zaehler wird bewusst OHNE eigene Synchronisierung angefasst -- unter
// -race schlaegt eine wirkungslose Sperre hier hart auf.
func TestLockBriefing_SerializesSameBriefing(t *testing.T) {
	s := New(t.TempDir(), "u1")
	counter := 0
	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			unlock := s.LockBriefing("t1")
			defer unlock()
			v := counter
			time.Sleep(time.Millisecond)
			counter = v + 1
		}()
	}
	wg.Wait()
	if counter != 16 {
		t.Errorf("erwarte 16 serialisierte Schreibvorgaenge, bekam %d", counter)
	}
}

// blockiert meldet, ob ein LockBriefing-Aufruf innerhalb von wait NICHT
// durchkommt.
//
// Der Wartende laeuft in einer Goroutine, die noch einen Eintrag in der
// PAKETWEITEN Sperrtabelle haelt, solange sie blockiert ist. Sie darf den Test
// deshalb NICHT ueberleben -- sonst sieht ein spaeterer Test (Registry-
// Wachstum) einen Fremd-Eintrag. t.Cleanup wartet darauf, dass sie durch ist;
// Cleanup laeuft nach den defer-Freigaben des Tests, die Sperre ist dann frei.
// Kein Sleep als Synchronisierung -- das verschoebe das Flattern nur.
func blockiert(t *testing.T, s *Store, id string, wait time.Duration) bool {
	t.Helper()
	done := make(chan struct{})
	go func() {
		unlock := s.LockBriefing(id)
		unlock()
		close(done)
	}()
	t.Cleanup(func() {
		select {
		case <-done:
		case <-time.After(10 * time.Second):
			t.Errorf("Wartender auf %q kam nicht durch -- Sperre nie freigegeben?", id)
		}
	})
	select {
	case <-done:
		return false
	case <-time.After(wait):
		return true
	}
}

// Verschiedene Touren blockieren einander nicht.
func TestLockBriefing_DifferentBriefingsDoNotBlock(t *testing.T) {
	s := New(t.TempDir(), "u1")
	unlock := s.LockBriefing("t1")
	defer unlock()

	if blockiert(t, s, "t2", 2*time.Second) {
		t.Error("eine Sperre auf t1 darf t2 nicht blockieren")
	}
}

// Die Falle: WithUser liefert eine FLACHE KOPIE des Stores. Eine Sperre als
// Struct-Feld waere pro Kopie eine andere und damit wirkungslos. Zusaetzlich
// muss die Sperre pro Nutzer getrennt sein (gleiche ID, anderer Nutzer -> frei).
func TestLockBriefing_SharedAcrossStoreCopiesAndScopedPerUser(t *testing.T) {
	base := New(t.TempDir(), "u1")
	unlock := base.WithUser("u1").LockBriefing("t1")

	kopie := base.WithUser("u1")
	if !blockiert(t, kopie, "t1", 300*time.Millisecond) {
		unlock()
		t.Fatal("eine Store-Kopie desselben Nutzers muss auf dieselbe Sperre laufen")
	}
	if blockiert(t, base.WithUser("u2"), "t1", 2*time.Second) {
		unlock()
		t.Fatal("ein anderer Nutzer mit gleicher Briefing-ID darf nicht blockiert werden")
	}

	unlock()
	if blockiert(t, kopie, "t1", 2*time.Second) {
		t.Error("nach dem Freigeben muss die Sperre wieder erreichbar sein")
	}
}

// Die Sperr-Tabelle darf nicht unbegrenzt wachsen: Eintraege verschwinden,
// sobald sie niemand mehr haelt (auch fuer geloeschte Touren).
func TestLockBriefing_RegistryDoesNotGrowUnbounded(t *testing.T) {
	// Ausgangslage: kein Vorgaenger-Test darf noch Sperren halten. Getrennte
	// Meldung, damit ein Fremd-Leck nicht als Fehler DIESER Sperre erscheint.
	if n := registryLen(); n != 0 {
		t.Fatalf("Vorgaenger-Test hat %d Sperren nicht freigegeben", n)
	}
	s := New(t.TempDir(), "u1")
	for i := 0; i < 500; i++ {
		unlock := s.LockBriefing(string(rune('a'+i%26)) + string(rune('a'+i/26)))
		unlock()
	}
	if n := registryLen(); n != 0 {
		t.Errorf("erwarte 0 verbliebene Sperr-Eintraege, bekam %d", n)
	}
}

func registryLen() int {
	briefingLocksMu.Lock()
	defer briefingLocksMu.Unlock()
	return len(briefingLocks)
}
