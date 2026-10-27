package store

import (
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// AC-13 (#2158): Sperrdateien (<id>.json.lock) sind Betriebsmittel, keine
// Nutzerdaten. Weder Export-Archiv noch Listen duerfen sie enthalten.
func TestExportLock_ArchivEnthaeltKeineLockDateien(t *testing.T) {
	dir := t.TempDir()
	s := New(dir, "u1")
	base := filepath.Join(dir, "users", "u1")
	for _, sub := range []string{"locations", "briefings"} {
		if err := os.MkdirAll(filepath.Join(base, sub), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	files := map[string]string{
		"locations/o1.json":      `{"id":"o1","name":"O1","lat":47,"lon":11}`,
		"locations/o1.json.lock": "",
		"briefings/t1.json":      `{"id":"t1","name":"T","stages":[]}`,
		"briefings/t1.json.lock": "",
	}
	for name, content := range files {
		if err := os.WriteFile(filepath.Join(base, name), []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}

	var buf bytes.Buffer
	if err := s.ExportUser("u1", &buf); err != nil {
		t.Fatalf("ExportUser: %v", err)
	}
	zr, err := zip.NewReader(bytes.NewReader(buf.Bytes()), int64(buf.Len()))
	if err != nil {
		t.Fatalf("zip: %v", err)
	}
	have := map[string]bool{}
	for _, f := range zr.File {
		have[f.Name] = true
		if strings.HasSuffix(f.Name, ".lock") {
			t.Errorf("Export enthaelt Sperrdatei %q", f.Name)
		}
	}
	// Positivkontrolle: die echten Daten sind weiterhin im Archiv.
	if !have["locations/o1.json"] || !have["briefings/t1.json"] {
		t.Errorf("Export verlor echte Daten: %v", have)
	}
}

// AC-13 (#2158): Listen zaehlen keine Sperrdatei. Regressionswaechter -- die
// Listen filtern heute schon auf *.json; das darf die neue Sperrdatei nicht
// aendern.
func TestExportLock_ListenZaehlenKeineLockDateien(t *testing.T) {
	dir := t.TempDir()
	s := New(dir, "u1")
	if err := s.SaveTrip(p2158Trip("t1", "T")); err != nil {
		t.Fatal(err)
	}
	base := filepath.Join(dir, "users", "u1")
	if err := os.MkdirAll(filepath.Join(base, "locations"), 0o755); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"locations/o1.json", "locations/o1.json.lock", "briefings/t1.json.lock", "briefings/c1.json.lock"} {
		content := ""
		if name == "locations/o1.json" {
			content = `{"id":"o1","name":"O1","lat":47,"lon":11}`
		}
		if err := os.WriteFile(filepath.Join(base, name), []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	if trips, err := s.LoadTrips(); err != nil || len(trips) != 1 {
		t.Errorf("LoadTrips: %d Eintraege (%v), erwartet 1", len(trips), err)
	}
	if locs, err := s.LoadLocations(); err != nil || len(locs) != 1 {
		t.Errorf("LoadLocations: %d Eintraege (%v), erwartet 1", len(locs), err)
	}
	if cps, err := s.LoadComparePresets(); err != nil || len(cps) != 0 {
		t.Errorf("LoadComparePresets: %d Eintraege (%v), erwartet 0", len(cps), err)
	}
}
