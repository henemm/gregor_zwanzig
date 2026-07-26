package store

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
)

// writeFileLogged schreibt data nach path und loggt einen Schreibfehler
// serverseitig mit Pfad + Ursache (Issue #1066). Der Rückgabefehler trägt
// via %w Pfad-Kontext; die HTTP-Schicht gibt weiterhin nur generisch
// store_error zurück (kein Pfad-Leak an den Client).
//
// Seit Issue #1395 Scheibe 1 ATOMAR (tmp-Datei + rename), statt os.WriteFile:
// ein gleichzeitiger Leser (Python-Kern, Scheduler, zweiter Request) sah sonst
// den O_TRUNC-Zwischenzustand, also eine halb geschriebene Datei -- ein
// Inhalts-Fingerabdruck darauf gehoerte zu keinem gueltigen Stand.
func writeFileLogged(path string, data []byte) error {
	if err := writeFileAtomic(path, data); err != nil {
		log.Printf("store: write %s failed: %v", path, err)
		return fmt.Errorf("write %s: %w", path, err)
	}
	return nil
}

// writeFileAtomic schreibt in eine tmp-Datei IM ZIELVERZEICHNIS (gleiche
// Dateisystem-Ebene -- sonst waere rename kein atomarer Wechsel, sondern
// Kopieren) und tauscht sie per os.Rename ein. Rechte bleiben 0644
// (os.CreateTemp legt 0600 an, darum explizit vor dem Umbenennen setzen --
// umask-unabhaengig). Der tmp-Name beginnt mit "." und endet NICHT auf
// ".json", damit ein Rest niemals von den *.json-Scans (LoadTrips,
// LoadComparePresets, Python-Loader) eingesammelt wird. Auf jedem Fehlerpfad
// wird die tmp-Datei entfernt; die bisherige Zieldatei bleibt unversehrt.
func writeFileAtomic(path string, data []byte) error {
	f, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".tmp-*")
	if err != nil {
		return err
	}
	tmp := f.Name()
	if _, err := f.Write(data); err != nil {
		f.Close()
		os.Remove(tmp)
		return err
	}
	if err := f.Close(); err != nil {
		os.Remove(tmp)
		return err
	}
	if err := os.Chmod(tmp, 0644); err != nil {
		os.Remove(tmp)
		return err
	}
	if err := os.Rename(tmp, path); err != nil {
		os.Remove(tmp)
		return err
	}
	return nil
}
