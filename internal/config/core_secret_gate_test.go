// TDD-RED fuer Issue #2142 Scheibe 1 (AC-3): Fail-Fast-Gate fuer das gemeinsame
// Geheimnis Go -> Python-Core. Bauform und Schwelle 1:1 aus
// session_secret_gate_test.go (#2139) uebernommen — 32 Zeichen Mindestlaenge,
// Ausnahme TestFixtureDir != "" fuer den isolierten CI-Stack.
package config

import "testing"

// Test 1 (AC-3): kein Secret, kein TestFixtureDir -> Fehler.
func TestValidateCoreSharedSecret_UnsetFails(t *testing.T) {
	cfg := &Config{CoreSharedSecret: "", TestFixtureDir: ""}
	if err := ValidateCoreSharedSecret(cfg); err == nil {
		t.Fatal("expected error for unset GZ_CORE_SHARED_SECRET, got nil")
	}
}

// Test 2 (AC-3): CI-E2E-Ausnahme — TestFixtureDir gesetzt, Secret leer -> nil.
func TestValidateCoreSharedSecret_TestFixtureDirException(t *testing.T) {
	cfg := &Config{CoreSharedSecret: "", TestFixtureDir: "/tmp/fixtures"}
	if err := ValidateCoreSharedSecret(cfg); err != nil {
		t.Fatalf("expected nil for TestFixtureDir exception, got: %v", err)
	}
}

// AC-3, Teil "zu kurzer Wert": Schwelle vom Session-Secret-Gate uebernommen.
func TestValidateCoreSharedSecret_TooShortFails(t *testing.T) {
	cfg := &Config{CoreSharedSecret: "kurz"}
	if err := ValidateCoreSharedSecret(cfg); err == nil {
		t.Fatal("expected error for secret shorter than 32 chars, got nil")
	}
}

func TestValidateCoreSharedSecret_OneBelowMinLengthFails(t *testing.T) {
	cfg := &Config{CoreSharedSecret: "abcdefghijklmnopqrstuvwxyz01234"} // 31 Zeichen
	if err := ValidateCoreSharedSecret(cfg); err == nil {
		t.Fatal("expected error for secret of 31 chars, got nil")
	}
}

func TestValidateCoreSharedSecret_ExactlyMinLengthPasses(t *testing.T) {
	cfg := &Config{CoreSharedSecret: "abcdefghijklmnopqrstuvwxyz012345"} // 32 Zeichen
	if err := ValidateCoreSharedSecret(cfg); err != nil {
		t.Fatalf("expected nil for secret of exactly 32 chars, got: %v", err)
	}
}

func TestValidateCoreSharedSecret_ValidSecretPasses(t *testing.T) {
	cfg := &Config{CoreSharedSecret: "a-genuinely-random-forty-char-secret-1234"}
	if err := ValidateCoreSharedSecret(cfg); err != nil {
		t.Fatalf("expected nil for valid 40-char secret, got: %v", err)
	}
}
