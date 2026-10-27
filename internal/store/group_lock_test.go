package store

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-4 (#2158): Altformat (Ort mit Legacy-Gruppen-Text, keine groups.json).
// Mehrere GETs (LoadGroups, Migration schreibt groups.json UND backfillt
// group_id) laufen gleichzeitig mit Gruppen-Schreibern (SaveGroup). Ohne
// Gruppen-Sperre um die Migration ueberschreibt die Migration eines GET die
// neue Gruppe des Schreibers wieder. Beide Wirkungen muessen erhalten sein,
// und es darf nicht haengen (Frist -> Fehler).
func TestGroupLock_GetMitMigrationUndSaveGroup_BeideWirkungen(t *testing.T) {
	const iterationen = 120
	const leser, schreiber = 4, 4
	schlecht := 0
	for it := 0; it < iterationen; it++ {
		s := New(t.TempDir(), "u1")
		alpen := "Alpen"
		if err := s.SaveLocation(model.Location{ID: "o1", Name: "O1", Lat: 47, Lon: 11, Group: &alpen}); err != nil {
			t.Fatalf("seed: %v", err)
		}

		start := make(chan struct{})
		var wg sync.WaitGroup
		for i := 0; i < leser; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				<-start
				_, _ = s.LoadGroups()
			}()
		}
		for i := 0; i < schreiber; i++ {
			i := i
			wg.Add(1)
			go func() {
				defer wg.Done()
				<-start
				_ = s.SaveGroup(model.Group{ID: fmt.Sprintf("neu-%d", i), Name: fmt.Sprintf("Neu %d", i), Order: 10 + i})
			}()
		}
		close(start)
		done := make(chan struct{})
		go func() { wg.Wait(); close(done) }()
		select {
		case <-done:
		case <-time.After(20 * time.Second):
			t.Fatalf("Durchlauf %d: GET-Migration und Schreiber nicht fertig -- Verklemmung?", it)
		}

		gs, err := s.LoadGroups()
		if err != nil {
			t.Fatalf("laden: %v", err)
		}
		have := map[string]bool{}
		for _, g := range gs {
			have[g.ID] = true
		}
		bad := !have["alpen"]
		for i := 0; i < schreiber; i++ {
			if !have[fmt.Sprintf("neu-%d", i)] {
				bad = true
			}
		}
		loc, _ := s.LoadLocation("o1")
		if loc == nil || loc.GroupID == nil || *loc.GroupID != "alpen" {
			bad = true // Backfill der Migration verloren
		}
		if bad {
			schlecht++
		}
	}
	if schlecht > 0 {
		t.Errorf("Migration/Schreiber: Wirkung verloren in %d von %d Durchlaeufen", schlecht, iterationen)
	}
}
