package store

import (
	"bytes"
	"errors"
	"log"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// Issue #1066: Store-Schreibfehler werden serverseitig geloggt (Pfad + Ursache),
// statt stumm zurückgegeben zu werden. Echte Dateisystem-Operationen, kein Mock.

// AC-1: Ein fehlgeschlagener Store-Save-Aufruf (SaveTrip auf eine 0444-Datei)
// erzeugt eine Log-Zeile, die sowohl den Dateipfad als auch die zugrundeliegende
// OS-Fehlerursache ("permission denied") enthält.
func TestSaveTrip_WriteFailureLogsPathAndCause(t *testing.T) {
	tmp := t.TempDir()
	s := New(tmp, "logtestuser")

	trip := model.Trip{ID: "log-trip"}

	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("initial SaveTrip should succeed, got error: %v", err)
	}

	path := filepath.Join(s.briefingsDir(), "log-trip.json")
	if err := os.Chmod(path, 0444); err != nil {
		t.Fatalf("failed to chmod trip file read-only: %v", err)
	}
	defer func() {
		_ = os.Chmod(path, 0644)
	}()

	var buf bytes.Buffer
	log.SetOutput(&buf)
	defer log.SetOutput(os.Stderr)

	err := s.SaveTrip(&trip)
	if err == nil {
		t.Fatalf("expected SaveTrip to fail against a read-only file, got nil error")
	}

	logged := buf.String()
	if !strings.Contains(logged, path) {
		t.Errorf("expected log to contain the file path %q, got: %q", path, logged)
	}
	if !strings.Contains(logged, "permission denied") {
		t.Errorf("expected log to contain the write failure cause (%q), got: %q", "permission denied", logged)
	}
}

// AC-2: writeFileLogged liefert bei einem fehlgeschlagenen Schreibvorgang einen
// Fehler ungleich nil, der über %w-Wrapping Pfad-Kontext trägt.
func TestWriteFileLogged_ReturnsWrappedErrorWithPath(t *testing.T) {
	tmp := t.TempDir()
	path := filepath.Join(tmp, "readonly.json")

	if err := os.WriteFile(path, []byte("{}"), 0644); err != nil {
		t.Fatalf("setup write failed: %v", err)
	}
	if err := os.Chmod(path, 0444); err != nil {
		t.Fatalf("chmod failed: %v", err)
	}
	defer func() {
		_ = os.Chmod(path, 0644)
	}()

	var buf bytes.Buffer
	log.SetOutput(&buf)
	defer log.SetOutput(os.Stderr)

	err := writeFileLogged(path, []byte("{}"))
	if err == nil {
		t.Fatal("expected non-nil error for read-only target file")
	}
	if !strings.Contains(err.Error(), path) {
		t.Errorf("expected error to contain path %q, got: %q", path, err.Error())
	}
	if errors.Unwrap(err) == nil {
		t.Error("expected error to wrap the underlying os error (errors.Unwrap == nil)")
	}
}

// AC-3: Ein regulärer Store-Save-Aufruf auf einem schreibbaren Verzeichnis
// erzeugt KEIN Fehler-Log, liefert nil zurück, und der Roundtrip liefert
// strukturell dieselben Daten (kein Dateiinhalt-String-Check).
func TestSaveTrip_SuccessRoundtripNoLog(t *testing.T) {
	tmp := t.TempDir()
	s := New(tmp, "roundtripuser")

	trip := model.Trip{
		ID:   "roundtrip-trip",
		Name: "Roundtrip Trip",
		Stages: []model.Stage{
			{
				ID: "S1", Name: "Day 1", Date: "2026-05-01",
				Waypoints: []model.Waypoint{
					{ID: "W1", Name: "Start", Lat: 47.0, Lon: 11.0, ElevationM: 500},
				},
			},
		},
	}

	var buf bytes.Buffer
	log.SetOutput(&buf)
	defer log.SetOutput(os.Stderr)

	if err := s.SaveTrip(&trip); err != nil {
		t.Fatalf("SaveTrip should succeed on a writable temp dir, got error: %v", err)
	}

	if buf.Len() != 0 {
		t.Errorf("expected empty log buffer on success, got: %q", buf.String())
	}

	loaded, err := s.LoadTrip("roundtrip-trip")
	if err != nil {
		t.Fatalf("LoadTrip failed: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected trip after roundtrip, got nil")
	}
	if loaded.ID != trip.ID || loaded.Name != trip.Name {
		t.Errorf("expected roundtrip trip to match ID/Name, got ID=%q Name=%q", loaded.ID, loaded.Name)
	}
	if len(loaded.Stages) != len(trip.Stages) {
		t.Errorf("expected %d stages after roundtrip, got %d", len(trip.Stages), len(loaded.Stages))
	}
}
