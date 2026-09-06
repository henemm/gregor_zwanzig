package store

import (
	"errors"
	"regexp"
)

// Pfad-Traversal-Sperre fuer Nutzer-Kennungen (Issue #2140, Scheibe 1).
//
// Jede Store-Methode, die aus einer Nutzer-Kennung einen Dateipfad baut,
// prueft sie hier ZUERST. Ohne diese Sperre normalisiert filepath.Join eine
// Kennung wie "../bob" oder "../users/bob" und laesst den Aufrufer aus dem
// eigenen Nutzerverzeichnis ausbrechen — bis hin zum Ueberschreiben oder
// Loeschen fremder Konten (ADR-0003: konsequente Mandantentrennung).
//
// ValidUserIDRe ist die KANONISCHE Go-Quelle des Musters. internal/handler
// (Registrierung, Passkey) haengt daran, statt es zu verdoppeln; der
// Python-Kern haelt mit app.loader.VALID_USER_ID_RE dagegen (Paritaetstest
// tests/unit/test_user_id_pattern_parity.py, #1364).
var ValidUserIDRe = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

// ErrInvalidUserID meldet eine Kennung, die kein einzelnes, sicheres
// Pfadsegment ist. Bewusst ein eigener Fehler und kein stilles "nicht
// gefunden": der Aufrufer soll eine Traversal-Kennung nicht mit einem
// schlicht unbekannten Nutzer verwechseln koennen.
var ErrInvalidUserID = errors.New("invalid user id")

// ValidUserID prueft, ob eine Nutzer-Kennung dem Zulassungsmuster entspricht.
func ValidUserID(id string) bool {
	return ValidUserIDRe.MatchString(id)
}
