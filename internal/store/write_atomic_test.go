package store

import (
	"bytes"
	"os"
	"path/filepath"
	"sync"
	"testing"
)

// Issue #1395 Scheibe 1: writeFileLogged schreibt atomar (tmp-Datei + rename in
// DERSELBEN Verzeichnis-Ebene). Ein Leser darf nie eine halb geschriebene Datei
// sehen -- sonst gehoert ein Fingerabdruck zu keinem gueltigen Zustand.

const atomicPayloadSize = 256 * 1024

// Ein Leser sieht waehrend vieler Schreibvorgaenge immer einen VOLLSTAENDIGEN,
// in sich einheitlichen Stand -- nie eine abgeschnittene oder gemischte Datei.
func TestWriteFileLogged_ReaderNeverSeesPartialFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "big.json")
	payload := func(b byte) []byte { return bytes.Repeat([]byte{b}, atomicPayloadSize) }

	if err := writeFileLogged(path, payload('a')); err != nil {
		t.Fatalf("setup: %v", err)
	}

	stop := make(chan struct{})
	var bad []string
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		for {
			select {
			case <-stop:
				return
			default:
			}
			data, err := os.ReadFile(path)
			if err != nil {
				bad = append(bad, "Lesefehler: "+err.Error())
				return
			}
			if len(data) != atomicPayloadSize {
				bad = append(bad, "abgeschnittene Datei gelesen")
				return
			}
			if !bytes.Equal(data, payload(data[0])) {
				bad = append(bad, "gemischter Inhalt zweier Staende gelesen")
				return
			}
		}
	}()

	for i := 0; i < 150; i++ {
		if err := writeFileLogged(path, payload(byte('a'+i%2))); err != nil {
			close(stop)
			wg.Wait()
			t.Fatalf("write %d: %v", i, err)
		}
	}
	close(stop)
	wg.Wait()

	if len(bad) > 0 {
		t.Errorf("Leser sah einen ungueltigen Zwischenzustand: %v", bad)
	}
}

// Schlaegt der Schreibvorgang fehl, bleibt die alte Datei unversehrt und es
// bleiben keine Reste im Verzeichnis liegen.
func TestWriteFileLogged_FailureKeepsOldFileAndLeavesNoLeftovers(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "trip.json")
	if err := os.WriteFile(path, []byte(`{"alt":true}`), 0644); err != nil {
		t.Fatalf("setup: %v", err)
	}
	if err := os.Chmod(dir, 0555); err != nil {
		t.Fatalf("chmod dir: %v", err)
	}
	defer func() { _ = os.Chmod(dir, 0755) }()

	if err := writeFileLogged(path, []byte(`{"neu":true}`)); err == nil {
		t.Fatal("erwarte Fehler beim Schreiben in ein nicht beschreibbares Verzeichnis")
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("alte Datei nicht mehr lesbar: %v", err)
	}
	if string(data) != `{"alt":true}` {
		t.Errorf("alte Datei wurde beschaedigt: %q", string(data))
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}
	if len(entries) != 1 {
		names := []string{}
		for _, e := range entries {
			names = append(names, e.Name())
		}
		t.Errorf("erwarte genau die Zieldatei im Verzeichnis, bekam %v", names)
	}
}

// Der ersetzte Stand traegt weiterhin 0644, und es bleibt keine tmp-Datei
// liegen (sonst wuerde ein *.json-Glob spaeter Muell einsammeln).
func TestWriteFileLogged_SuccessKeeps0644AndNoLeftovers(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "trip.json")
	for i := 0; i < 3; i++ {
		if err := writeFileLogged(path, []byte(`{"a":1}`)); err != nil {
			t.Fatalf("write: %v", err)
		}
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if info.Mode().Perm() != 0644 {
		t.Errorf("erwarte Rechte 0644, bekam %v", info.Mode().Perm())
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}
	if len(entries) != 1 {
		t.Errorf("erwarte genau eine Datei im Verzeichnis, bekam %d", len(entries))
	}
}
