package config

import "errors"

// minCoreSharedSecretLen ist die Mindestlaenge fuer das gemeinsame Geheimnis
// Go -> Python-Core — dieselbe Schwelle wie beim Session-Secret (#2139).
const minCoreSharedSecretLen = 32

// ValidateCoreSharedSecret prueft, ob das gemeinsame Geheimnis fuer den
// Produktivbetrieb taugt.
//
// Issue #2142: Ohne Geheimnis sendet die Go-API keinen Auth-Header, und der
// Python-Core riegelt ab Scheibe 2 jede Anfrage mit 503 ab. Ein stiller Start
// mit leerem Wert waere also ein Totalausfall, der erst im Betrieb auffiele —
// der Aufrufer (cmd/server/main.go) beendet den Prozess deshalb beim Start.
//
// Ausnahme: Ist TestFixtureDir gesetzt, laeuft der Prozess im CI-E2E-Stack
// (frontend/e2e/ci-stack.sh), der sein Geheimnis selbst mitbringt bzw. ohne
// auskommt.
func ValidateCoreSharedSecret(cfg *Config) error {
	if cfg.TestFixtureDir != "" {
		return nil
	}
	if cfg.CoreSharedSecret == "" {
		return errors.New("GZ_CORE_SHARED_SECRET ist nicht gesetzt")
	}
	if len(cfg.CoreSharedSecret) < minCoreSharedSecretLen {
		return errors.New("GZ_CORE_SHARED_SECRET ist kuerzer als 32 Zeichen")
	}
	return nil
}
