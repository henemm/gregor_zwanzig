package store

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
)

// BriefingFingerprint liefert den Inhalts-Fingerabdruck der Briefing-Datei
// briefings/<id>.json (Issue #1395 Scheibe 1). Gilt fuer Trip UND Ortsvergleich
// -- beide liegen in derselben Datei-Ebene (briefingsDir).
//
// Der Stempel kommt bewusst aus den BYTES AUF PLATTE und nicht aus einem
// geladenen Objekt:
//   - LoadTrip/LoadComparePreset heilen beim Lesen in-memory (healTripSlotTimes,
//     SyncAlertRules, normalizeLoadedComparePreset) OHNE Rueckschreiben --
//     ein Fingerabdruck ueber das geladene Objekt entspraeche nicht der Datei.
//   - Der Python-Kern schreibt dieselben Dateien (src/app/loader.py) und bewahrt
//     unbekannte Felder; ein nur von Go gepflegter Versionszaehler IM Dokument
//     waere nach jedem Python-Schreibvorgang still falsch.
//
// Fehlt die Datei, ist das kein Fehler, sondern der gueltige Zustand "es gibt
// hier noch keinen Stand" -> leerer Fingerabdruck, nil-Fehler. Aufrufer
// unterscheiden damit "kein Dokument" von "Dokument mit Stand X", ohne
// os.IsNotExist selbst auswerten zu muessen.
func (s *Store) BriefingFingerprint(id string) (string, error) {
	data, err := os.ReadFile(filepath.Join(s.briefingsDir(), id+".json"))
	if err != nil {
		if os.IsNotExist(err) {
			return "", nil
		}
		return "", err
	}
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:]), nil
}
