package store

import (
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// F-3 (#2158): der Migrations-Backfill (group_id am Ort) nimmt die
// Orts-Sperre. Haelt jemand den Ort von aussen, wartet LoadGroups; nach der
// Freigabe sind Migration UND die Ortsaenderung des Halters erhalten.
func TestGroupLock_MigrationBackfill_WartetAufOrtsSperre(t *testing.T) {
	s := New(t.TempDir(), "u1")
	alpen := "Alpen"
	if err := s.SaveLocation(model.Location{ID: "o1", Name: "O1", Lat: 47, Lon: 11, Group: &alpen}); err != nil {
		t.Fatal(err)
	}
	unlock := s.LockLocation("o1")
	done := make(chan struct{})
	go func() { _, _ = s.LoadGroups(); close(done) }()
	select {
	case <-done:
		unlock()
		t.Fatal("Backfill lief trotz gehaltener Orts-Sperre durch -- Sperre fehlt")
	case <-time.After(300 * time.Millisecond):
	}
	l, _ := s.LoadLocation("o1")
	l.Name = "Geaendert"
	if err := s.SaveLocation(*l); err != nil {
		t.Fatal(err)
	}
	unlock()
	select {
	case <-done:
	case <-time.After(10 * time.Second):
		t.Fatal("LoadGroups nach Freigabe nicht fertig")
	}
	got, _ := s.LoadLocation("o1")
	if got == nil || got.Name != "Geaendert" || got.GroupID == nil {
		t.Fatalf("Endstand: %+v", got)
	}
}
