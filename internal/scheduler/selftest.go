package scheduler

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
)

// probeDataWritable prüft non-destruktiv, ob die vorhandenen Trip-Dateien unter
// data/users/*/briefings/*.json schreibbar sind (Issue #1250 Scheibe 7a
// Cutover, Adversary F002: der echte Schreibort nach dem Cutover -- war
// trips/ davor). Öffnet jede Datei mit O_WRONLY
// (KEIN O_TRUNC, KEIN O_CREATE) und schließt sofort — ändert weder Inhalt noch
// mtime, verlangt aber kernelseitig dieselbe Schreibberechtigung wie der reale
// os.WriteFile-Pfad (internal/store/write.go). Reproduziert das #1066-EACCES.
//
// BEWUSST kein filepath.Glob: Glob verschluckt laut Doku alle
// Verzeichnis-Lesefehler (liefert nur ErrBadPattern) — verliert z.B.
// users/<id>/briefings/ das Leserecht (#1066-Sweep-Variante), liefert Glob
// still eine leere Liste statt eines Fehlers. Stattdessen wird jede Ebene
// per os.ReadDir traversiert und Lesefehler != ErrNotExist als Probe-Fehler
// gewertet.
func probeDataWritable(dataDir string) error {
	usersDir := filepath.Join(dataDir, "users")
	userEntries, err := os.ReadDir(usersDir)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil // keine Daten vorhanden, kein False Alarm (AC-3)
		}
		return fmt.Errorf("users-Verzeichnis nicht lesbar: %s: %w", usersDir, err)
	}

	var failed []string
	var totalFiles int
	for _, ue := range userEntries {
		if !ue.IsDir() {
			continue
		}
		tripsDir := filepath.Join(usersDir, ue.Name(), "briefings")
		tripEntries, err := os.ReadDir(tripsDir)
		if err != nil {
			if errors.Is(err, fs.ErrNotExist) {
				continue // User ohne briefings/-Verzeichnis, ok
			}
			failed = append(failed, fmt.Sprintf("%s (%v)", tripsDir, err))
			continue
		}
		for _, te := range tripEntries {
			if te.IsDir() || !strings.HasSuffix(te.Name(), ".json") {
				continue
			}
			totalFiles++
			p := filepath.Join(tripsDir, te.Name())
			f, err := os.OpenFile(p, os.O_WRONLY, 0)
			if err != nil {
				failed = append(failed, fmt.Sprintf("%s (%v)", p, err))
				continue
			}
			f.Close()
		}
	}

	if len(failed) > 0 {
		// Pfade sind interne Server-Pfade, kein Nutzer-Inhalt (nie gelesen).
		shown := failed
		if len(shown) > 5 {
			shown = shown[:5]
		}
		return fmt.Errorf("data/ nicht schreibbar: %d Problem(e): %s",
			len(failed), strings.Join(shown, "; "))
	}
	return nil
}
