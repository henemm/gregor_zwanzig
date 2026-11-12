package store

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// Issue #2961 (Spec security_haertung_2026_11_go_schnittstellen.md AC-22):
// LoadBriefing/SaveBriefing pruefen die Kennung vor dem Pfadbau; ein
// Ausbruch aus dem Nutzerverzeichnis bleibt wirkungslos.
func TestBriefingSubscription_KennungWirdGeprueft(t *testing.T) {
	root := t.TempDir()
	s := New(root, "alice")
	for _, id := range []string{"../../bob/user", "a/b", "", "..", "x?y"} {
		if _, err := s.LoadBriefing(id); !errors.Is(err, ErrInvalidEntityID) {
			t.Errorf("LoadBriefing(%q): erwartet ErrInvalidEntityID, bekam %v", id, err)
		}
		if err := s.SaveBriefing(&model.BriefingSubscription{ID: id, Kind: "route"}); !errors.Is(err, ErrInvalidEntityID) {
			t.Errorf("SaveBriefing(%q): erwartet ErrInvalidEntityID, bekam %v", id, err)
		}
	}
	if _, err := os.Stat(filepath.Join(root, "users", "bob")); !os.IsNotExist(err) {
		t.Fatalf("ausserhalb des Nutzerverzeichnisses ist etwas entstanden: %v", err)
	}
	// Gegenprobe: gueltige Kennung funktioniert weiter.
	if err := s.SaveBriefing(&model.BriefingSubscription{ID: "b-ok", Kind: "route"}); err != nil {
		t.Fatalf("SaveBriefing(b-ok): %v", err)
	}
	if b, err := s.LoadBriefing("b-ok"); err != nil || b == nil {
		t.Fatalf("LoadBriefing(b-ok): %v %v", b, err)
	}
}
