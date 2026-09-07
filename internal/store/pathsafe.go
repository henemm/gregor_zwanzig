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

// Pfad-Traversal-Sperre fuer ENTITAETS-Kennungen (Issue #2140, Scheibe 2):
// Trip, Ort, Ortsvergleichs-Preset.
//
// Bewusst KEINE ASCII-Whitelist wie bei Nutzer-Kennungen, sondern eine reine
// Pfadsegment-Pruefung: im Bestand liegen aktive Orte mit Diakritika
// (hochfuegen, pollenca, muehlbach ...), deren Kennung das Frontend absichtlich
// mit Umlauten bildet. Eine Whitelist wuerde sie unerreichbar machen. Der
// Ausbruch entsteht bei Entitaets-Kennungen ausschliesslich ueber einen
// Pfad-Trenner im Wert — jede Store-Methode joint nur id+".json", nie einen
// rohen Verzeichnis-Join.
//
// Gelesen: erstes Zeichen weder "." noch Trenner noch NUL (deckt "", ".",
// "..", ".hidden", "/x" ab), alle weiteren Zeichen kein Trenner und kein NUL.
// ValidEntityIDRe ist die KANONISCHE Go-Quelle; der Python-Kern haelt mit
// app.loader.VALID_ENTITY_ID_RE dagegen (Paritaetstest
// tests/unit/test_entity_id_pattern_parity.py).
var ValidEntityIDRe = regexp.MustCompile(`^[^./\\\x00][^/\\\x00]*$`)

// ErrInvalidEntityID meldet eine Entitaets-Kennung, die kein einzelnes,
// sicheres Pfadsegment ist — analog ErrInvalidUserID bewusst ein eigener
// Fehler und kein stilles "nicht gefunden".
var ErrInvalidEntityID = errors.New("invalid entity id")

// ValidEntityID prueft, ob eine Entitaets-Kennung ein sicheres Pfadsegment ist.
func ValidEntityID(id string) bool {
	return ValidEntityIDRe.MatchString(id)
}
