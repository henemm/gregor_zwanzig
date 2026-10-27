// Package fsmode haelt die Dateimodi fuer alles, was die Go-API im
// Datenbaum anlegt (Issue #2624). Unter einer Default-ACL begrenzt der bei
// der Anlage uebergebene Modus die ACL-Maske; 0755/0644 nahmen der
// Dienstgruppe das Schreibrecht. Reines Blatt-Paket: importiert nur die
// Standardbibliothek, damit kein Importzyklus entstehen kann.
package fsmode

import (
	"errors"
	"io/fs"
	"os"
	"path/filepath"
)

const (
	// DirMode fuer neu angelegte Verzeichnisse.
	DirMode os.FileMode = 0o770
	// FileMode fuer neu geschriebene Dateien.
	FileMode os.FileMode = 0o660
)

// MkdirAll legt path samt fehlender Eltern an und setzt NUR die dabei neu
// entstandenen Verzeichnisse explizit auf DirMode -- unabhaengig von der
// Prozess-Umask (Prod: 0077). Bereits bestehende Verzeichnisse bleiben
// unangetastet (Bestand 0755, Spec AC-7).
func MkdirAll(path string) error {
	var missing []string
	for p := filepath.Clean(path); ; {
		if _, err := os.Stat(p); err == nil || !errors.Is(err, fs.ErrNotExist) {
			break
		}
		missing = append(missing, p)
		parent := filepath.Dir(p)
		if parent == p {
			break
		}
		p = parent
	}
	if err := os.MkdirAll(path, DirMode); err != nil {
		return err
	}
	for _, d := range missing {
		if err := os.Chmod(d, DirMode); err != nil {
			return err
		}
	}
	return nil
}

// OpenFile oeffnet path mit flag (O_CREATE wird ergaenzt). Entsteht die
// Datei dabei neu, wird sie explizit auf FileMode gesetzt (umask-unabhaengig);
// eine bestehende Datei behaelt ihren Modus.
func OpenFile(path string, flag int) (*os.File, error) {
	f, err := os.OpenFile(path, flag|os.O_CREATE|os.O_EXCL, FileMode)
	if err == nil {
		if err := f.Chmod(FileMode); err != nil {
			f.Close()
			return nil, err
		}
		return f, nil
	}
	if !errors.Is(err, fs.ErrExist) {
		return nil, err
	}
	return os.OpenFile(path, flag|os.O_CREATE, FileMode)
}
