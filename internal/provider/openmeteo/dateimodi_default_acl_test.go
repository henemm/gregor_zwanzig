package openmeteo

// Issue #2624 AC-5: Wetter-Cache und Drift-Journal entstehen mit 0770 (Ordner)
// und 0660 (Datei) -- unabhaengig von der Prozess-Umask (Prod: 0077).

import (
	"os"
	"path/filepath"
	"syscall"
	"testing"
)

func modus(t *testing.T, p string) os.FileMode {
	t.Helper()
	fi, err := os.Stat(p)
	if err != nil {
		t.Fatalf("stat %s: %v", p, err)
	}
	return fi.Mode().Perm()
}

func TestDateimodi_AvailabilityCache_0770_0660_UnterUmask077(t *testing.T) {
	alt := syscall.Umask(0o077)
	defer syscall.Umask(alt)
	dir := filepath.Join(t.TempDir(), "diagnostics")
	p := filepath.Join(dir, "availability.json")
	if err := SaveAvailabilityCache(p, &AvailabilityCache{ProbeDate: "2026-10-27"}); err != nil {
		t.Fatal(err)
	}
	if got := modus(t, dir); got != 0o770 {
		t.Errorf("Cache-Verzeichnis: %#o, erwartet 0770", got)
	}
	if got := modus(t, p); got != 0o660 {
		t.Errorf("Cache-Datei: %#o, erwartet 0660", got)
	}
}

func TestDateimodi_Calllog_0770_0660_UnterUmask077(t *testing.T) {
	alt := syscall.Umask(0o077)
	defer syscall.Umask(alt)
	dir := filepath.Join(t.TempDir(), "diagnostics")
	p := filepath.Join(dir, "openmeteo_calls_go.jsonl")
	old := diagnosticsGoPath
	diagnosticsGoPath = p
	defer func() { diagnosticsGoPath = old }()

	logAPICall("https://api.open-meteo.com/v1/forecast?x=1", 200, "")

	if got := modus(t, dir); got != 0o770 {
		t.Errorf("Journal-Verzeichnis: %#o, erwartet 0770", got)
	}
	if got := modus(t, p); got != 0o660 {
		t.Errorf("Journal-Datei: %#o, erwartet 0660", got)
	}
}
