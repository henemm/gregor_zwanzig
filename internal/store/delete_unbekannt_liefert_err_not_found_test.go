package store

// Issue #2815 (Spec fix_2815_delete_fremd_404.md): die Loeschfunktionen des
// Stores melden "nicht vorhanden" per Sentinel ErrNotFound, damit der Handler
// 404 statt 204 antworten kann. Kaputte Dateien bleiben loeschbar (fail-open).
// Echtes Dateisystem in t.TempDir(), kein Mock.

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-8 (Store): kaputte, nicht als JSON lesbare Trip-Datei -> nil, Datei weg.
func TestDeleteTrip_KaputteDateiWirdGeloescht_2815(t *testing.T) {
	s := New(t.TempDir(), "u-2815")
	dir := s.briefingsDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(dir, "kaputt.json")
	if err := os.WriteFile(p, []byte("{kein json"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := s.DeleteTrip("kaputt"); err != nil {
		t.Fatalf("kaputte Datei muss loeschbar bleiben, err=%v", err)
	}
	if _, err := os.Stat(p); !os.IsNotExist(err) {
		t.Fatalf("kaputte Datei muss entfernt sein (stat err=%v)", err)
	}
}

// AC-10 (Store): kaputte Ortsdatei -> nil, Datei weg.
func TestDeleteLocation_KaputteDateiWirdGeloescht_2815(t *testing.T) {
	s := New(t.TempDir(), "u-2815")
	dir := s.LocationsDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(dir, "kaputt.json")
	if err := os.WriteFile(p, []byte("{kein json"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := s.DeleteLocation("kaputt"); err != nil {
		t.Fatalf("kaputte Ortsdatei muss loeschbar bleiben, err=%v", err)
	}
	if _, err := os.Stat(p); !os.IsNotExist(err) {
		t.Fatalf("kaputte Ortsdatei muss entfernt sein (stat err=%v)", err)
	}
}

// DeleteGroupLocked/DeleteGroup: unbekannte Gruppen-ID -> ErrNotFound, und
// groups.json wird dabei NICHT umgeschrieben (kein saveGroups).
func TestDeleteGroup_UnbekannteIDLiefertErrNotFoundOhneUmschreiben_2815(t *testing.T) {
	s := New(t.TempDir(), "u-2815")
	s.ProvisionUserDirs("u-2815")
	if err := s.SaveGroup(model.Group{ID: "ski", Name: "Ski", Order: 0}); err != nil {
		t.Fatal(err)
	}
	gf := s.groupsFile()
	alt := time.Now().Add(-time.Hour).Truncate(time.Second)
	if err := os.Chtimes(gf, alt, alt); err != nil {
		t.Fatal(err)
	}
	before, err := os.ReadFile(gf)
	if err != nil {
		t.Fatal(err)
	}

	if err := s.DeleteGroup("gibt-es-nicht"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("DeleteGroup(unbekannt): erwartet ErrNotFound, bekommen %v", err)
	}
	unlock := s.LockGroups()
	err = s.DeleteGroupLocked("gibt-es-nicht")
	unlock()
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("DeleteGroupLocked(unbekannt): erwartet ErrNotFound, bekommen %v", err)
	}

	st, err := os.Stat(gf)
	if err != nil {
		t.Fatal(err)
	}
	if !st.ModTime().Equal(alt) {
		t.Errorf("groups.json wurde umgeschrieben (mtime %v, erwartet %v)", st.ModTime(), alt)
	}
	after, _ := os.ReadFile(gf)
	if string(after) != string(before) {
		t.Errorf("groups.json veraendert:\nvorher %s\nnachher %s", before, after)
	}

	// Gegenprobe: bekannte Gruppe -> nil.
	if err := s.DeleteGroup("ski"); err != nil {
		t.Fatalf("DeleteGroup(ski): %v", err)
	}
}
