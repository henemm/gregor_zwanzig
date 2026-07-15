package scheduler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Issue #1120: probeDataWritable prüft non-destruktiv, ob vorhandene
// Trip-Dateien schreibbar sind (Gegenmassnahme zu #1066).

func TestProbeDataWritable_NotWritable(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignoriert DAC-Permission-Checks")
	}
	tmpDir := t.TempDir()
	tripDir := filepath.Join(tmpDir, "users", "u", "briefings")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	tripFile := filepath.Join(tripDir, "t.json")
	if err := os.WriteFile(tripFile, []byte(`{}`), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}
	if err := os.Chmod(tripFile, 0444); err != nil {
		t.Fatalf("chmod: %v", err)
	}

	err := probeDataWritable(tmpDir)
	if err == nil {
		t.Fatal("expected error for non-writable file, got nil")
	}
	if !strings.Contains(err.Error(), tripFile) {
		t.Fatalf("expected error to mention path %q, got %q", tripFile, err.Error())
	}
}

func TestProbeDataWritable_Writable(t *testing.T) {
	tmpDir := t.TempDir()
	tripDir := filepath.Join(tmpDir, "users", "u", "briefings")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	tripFile := filepath.Join(tripDir, "t.json")
	content := []byte(`{"id":"trip1"}`)
	if err := os.WriteFile(tripFile, content, 0644); err != nil {
		t.Fatalf("write: %v", err)
	}
	before, err := os.Stat(tripFile)
	if err != nil {
		t.Fatalf("stat before: %v", err)
	}

	if err := probeDataWritable(tmpDir); err != nil {
		t.Fatalf("expected nil for writable file, got %v", err)
	}

	after, err := os.Stat(tripFile)
	if err != nil {
		t.Fatalf("stat after: %v", err)
	}
	if !before.ModTime().Equal(after.ModTime()) {
		t.Fatalf("mtime changed: before=%v after=%v", before.ModTime(), after.ModTime())
	}
	gotContent, err := os.ReadFile(tripFile)
	if err != nil {
		t.Fatalf("read after: %v", err)
	}
	if string(gotContent) != string(content) {
		t.Fatalf("content changed: got %q, want %q", gotContent, content)
	}
}

func TestProbeDataWritable_NoFiles(t *testing.T) {
	tmpDir := t.TempDir()
	if err := probeDataWritable(tmpDir); err != nil {
		t.Fatalf("expected nil for empty dataDir, got %v", err)
	}
}

func TestProbeDataWritable_NonExistentDir(t *testing.T) {
	tmpDir := t.TempDir()
	nonExistent := filepath.Join(tmpDir, "does-not-exist")
	if err := probeDataWritable(nonExistent); err != nil {
		t.Fatalf("expected nil for non-existent dataDir, got %v", err)
	}
}

// Issue #1120 Fix-Runde 1 (F001): filepath.Glob verschluckt Verzeichnis-
// Lesefehler still (liefert leere Liste + err==nil). Verliert briefings/ das
// Leserecht (#1066-Sweep-Variante), muss die Probe das als error melden,
// nicht als false-positives "ok".
//
// Issue #1250 Scheibe 7a Adversary F002 (bleibender Regressionstest): seit
// dem Cutover ist briefings/ der echte Schreibort (war trips/ davor) --
// dieser Test beweist, dass probeDataWritable ein read-only briefings/
// weiterhin korrekt als Fehler erkennt (nicht mehr das inzwischen
// stillgelegte trips/).
func TestProbeDataWritable_UnreadableBriefingsDir(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignoriert DAC-Permission-Checks")
	}
	tmpDir := t.TempDir()
	tripDir := filepath.Join(tmpDir, "users", "u", "briefings")
	if err := os.MkdirAll(tripDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	tripFile := filepath.Join(tripDir, "t.json")
	if err := os.WriteFile(tripFile, []byte(`{}`), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}
	if err := os.Chmod(tripDir, 0000); err != nil {
		t.Fatalf("chmod: %v", err)
	}
	t.Cleanup(func() {
		_ = os.Chmod(tripDir, 0755)
	})

	err := probeDataWritable(tmpDir)
	if err == nil {
		t.Fatal("expected error for unreadable trips dir, got nil")
	}
	if !strings.Contains(err.Error(), tripDir) {
		t.Fatalf("expected error to mention path %q, got %q", tripDir, err.Error())
	}
}

// User-Verzeichnis ohne briefings/-Unterordner ist kein Fehlerfall (User hat
// schlicht noch keine Trips angelegt).
func TestProbeDataWritable_UserWithoutTripsDir(t *testing.T) {
	tmpDir := t.TempDir()
	userDir := filepath.Join(tmpDir, "users", "u")
	if err := os.MkdirAll(userDir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := probeDataWritable(tmpDir); err != nil {
		t.Fatalf("expected nil for user without trips dir, got %v", err)
	}
}
