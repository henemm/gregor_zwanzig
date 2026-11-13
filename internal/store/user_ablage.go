package store

// Ablage entfernter unbestaetigter Anmeldungen (Issue #2961, GA2, ADR-0115).
//
// Bestandsdaten bleiben erhalten (CLAUDE.md, #102 / BUG-DATALOSS-GR221): eine
// unbestaetigte Anmeldung wird nie direkt geloescht. Ihr Kontoordner wird per
// Rename (atomar, gleiches Dateisystem, Rechte bleiben) nach
// <DataDir>/.entfernt-unbestaetigt/<kennung>-<UTC-Zeitstempel>/ verschoben und
// erst nach AblageAufbewahrung endgueltig entfernt. Die Ablage liegt AUSSERHALB
// von <DataDir>/users: kein Loader (ListUserIDs, Adress-Eindeutigkeit,
// Scheduler, Python-Core) sieht sie als Nutzer. Zurueckholen = Ordner unter
// seinem Kennungsnamen nach users/ zurueckschieben (Playbook, Betriebs-Backup).

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/henemm/gregor-api/internal/fsmode"
)

// AblageVerzeichnis liegt direkt unter der Datenwurzel, neben users/.
const AblageVerzeichnis = ".entfernt-unbestaetigt"

// AblageAufbewahrung: so lange bleibt ein verschobener Ordner zurueckholbar.
const AblageAufbewahrung = 30 * 24 * time.Hour

const ablageZeitFormat = "20060102T150405Z"

// ErrAccountDirNotPristine: der Kontoordner enthaelt Nutzinhalte.
var ErrAccountDirNotPristine = errors.New("account dir contains user content")

// leererKontoordnerDateien ist die Positivliste dessen, was ein frisch
// registriertes, nie angemeldetes Konto haben darf. Alles andere — weitere
// Dateien, Unterordner mit Inhalt, Verweise — heisst "nicht leer".
var leererKontoordnerDateien = map[string]bool{
	"user.json":               true,
	"sessions.json":           true,
	"email_verification.json": true,
	"password_reset.json":     true,
}

// leererKontoordnerVerzeichnisse: Standardverzeichnisse aus ProvisionUserDirs,
// erlaubt nur, wenn sie selbst leer sind.
var leererKontoordnerVerzeichnisse = map[string]bool{
	"locations": true, "gpx": true, "weather_snapshots": true,
}

// IsAccountDirPristine meldet, ob der Kontoordner nur Dateien der
// Positivliste und leere Standardverzeichnisse enthaelt. Fehler beim Lesen
// gelten als "nicht leer" (Rueckgabe false mit Fehler).
// gz-store-scope-exempt: die Kennung kommt als Parameter id herein, nicht aus s.UserID
func (s *Store) IsAccountDirPristine(id string) (bool, error) {
	if !ValidUserID(id) {
		return false, ErrInvalidUserID
	}
	eintraege, err := os.ReadDir(s.UserDir(id))
	if err != nil {
		return false, err
	}
	for _, e := range eintraege {
		name := e.Name()
		switch {
		case e.Type().IsRegular() && leererKontoordnerDateien[name]:
			continue
		case e.IsDir() && e.Type()&fs.ModeSymlink == 0 && leererKontoordnerVerzeichnisse[name]:
			inhalt, err := os.ReadDir(filepath.Join(s.UserDir(id), name))
			if err != nil {
				return false, err
			}
			if len(inhalt) == 0 {
				continue
			}
		}
		return false, nil
	}
	return true, nil
}

// AblagePfad liefert das Ablage-Verzeichnis der Datenwurzel.
// gz-store-scope-exempt: Pfad der Datenwurzel, nutzerunabhaengig
func (s *Store) AblagePfad() string { return filepath.Join(s.DataDir, AblageVerzeichnis) }

// QuarantineUser verschiebt den Kontoordner eines LEEREN Kontos in die Ablage
// und liefert das Ziel. Unter der Nutzersperre wird die Leere erneut geprueft;
// ein Ordner mit Nutzinhalten bleibt unangetastet (ErrAccountDirNotPristine).
// gz-store-scope-exempt: die Kennung kommt als Parameter id herein, nicht aus s.UserID
func (s *Store) QuarantineUser(id string, now time.Time) (string, error) {
	if !ValidUserID(id) {
		return "", ErrInvalidUserID
	}
	unlock := lockUserJSON(id)
	defer unlock()
	leer, err := s.IsAccountDirPristine(id)
	if err != nil {
		return "", err
	}
	if !leer {
		return "", ErrAccountDirNotPristine
	}
	if err := fsmode.MkdirAll(s.AblagePfad()); err != nil {
		return "", err
	}
	ziel := filepath.Join(s.AblagePfad(), fmt.Sprintf("%s-%s", id, now.UTC().Format(ablageZeitFormat)))
	if _, err := os.Lstat(ziel); err == nil {
		return "", fmt.Errorf("ablage target exists: %w", fs.ErrExist)
	}
	if err := os.Rename(s.UserDir(id), ziel); err != nil {
		return "", err
	}
	return ziel, nil
}

// PurgeAblage entfernt Ablage-Eintraege, deren Zeitstempel im Namen aelter
// als AblageAufbewahrung ist. Eintraege ohne lesbaren Zeitstempel bleiben
// (im Zweifel behalten). Rueckgabe: Anzahl entfernter Eintraege.
// gz-store-scope-exempt: raeumt die kontouebergreifende Ablage ausserhalb von users/
func (s *Store) PurgeAblage(now time.Time) (int, error) {
	eintraege, err := os.ReadDir(s.AblagePfad())
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, err
	}
	entfernt := 0
	for _, e := range eintraege {
		if !e.IsDir() {
			continue
		}
		i := strings.LastIndex(e.Name(), "-")
		if i < 0 {
			continue
		}
		zeit, err := time.Parse(ablageZeitFormat, e.Name()[i+1:])
		if err != nil || now.Sub(zeit) < AblageAufbewahrung {
			continue
		}
		if err := os.RemoveAll(filepath.Join(s.AblagePfad(), e.Name())); err != nil {
			return entfernt, err
		}
		entfernt++
	}
	return entfernt, nil
}
