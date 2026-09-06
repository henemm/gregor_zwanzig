package config

import "errors"

// defaultSessionSecret ist das im Repo oeffentlich stehende Platzhalter-Secret.
const defaultSessionSecret = "dev-secret-change-me"

// minSessionSecretLen ist die Mindestlaenge fuer ein individuelles Secret.
const minSessionSecretLen = 32

// ValidateSessionSecret prueft, ob das Session-Secret fuer den Produktivbetrieb
// taugt.
//
// Issue #2139: Mit dem unveraenderten Default-Secret kann jede Person ein
// gueltiges Session-Cookie fuer eine beliebige user_id selbst signieren. Der
// Aufrufer (cmd/server/main.go) beendet den Prozess beim Start, statt unsicher
// weiterzulaufen.
//
// Ausnahme: Ist TestFixtureDir gesetzt, laeuft der Prozess im CI-E2E-Stack
// (frontend/e2e/ci-stack.sh) bewusst ohne GZ_SESSION_SECRET.
func ValidateSessionSecret(cfg *Config) error {
	if cfg.TestFixtureDir != "" {
		return nil
	}
	if cfg.SessionSecret == "" {
		return errors.New("GZ_SESSION_SECRET ist nicht gesetzt")
	}
	if cfg.SessionSecret == defaultSessionSecret {
		return errors.New("GZ_SESSION_SECRET traegt noch das Default-Literal")
	}
	if len(cfg.SessionSecret) < minSessionSecretLen {
		return errors.New("GZ_SESSION_SECRET ist kuerzer als 32 Zeichen")
	}
	return nil
}
