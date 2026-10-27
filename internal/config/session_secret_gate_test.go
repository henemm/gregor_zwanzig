package config

import "testing"

func TestValidateSessionSecret_DefaultLiteralFails(t *testing.T) {
	cfg := &Config{SessionSecret: "dev-secret-change-me"}
	if err := ValidateSessionSecret(cfg); err == nil {
		t.Fatal("expected error for unchanged default secret, got nil")
	}
}

func TestValidateSessionSecret_TestFixtureDirException(t *testing.T) {
	cfg := &Config{SessionSecret: "", TestFixtureDir: "/tmp/fixtures"}
	if err := ValidateSessionSecret(cfg); err != nil {
		t.Fatalf("expected nil for TestFixtureDir exception, got: %v", err)
	}
}

func TestValidateSessionSecret_TooShortFails(t *testing.T) {
	cfg := &Config{SessionSecret: "kurz"}
	if err := ValidateSessionSecret(cfg); err == nil {
		t.Fatal("expected error for secret shorter than 32 chars, got nil")
	}
}

func TestValidateSessionSecret_ExactlyMinLengthPasses(t *testing.T) {
	cfg := &Config{SessionSecret: "abcdefghijklmnopqrstuvwxyz012345"} // 32 Zeichen
	if err := ValidateSessionSecret(cfg); err != nil {
		t.Fatalf("expected nil for secret of exactly 32 chars, got: %v", err)
	}
}

func TestValidateSessionSecret_OneBelowMinLengthFails(t *testing.T) {
	cfg := &Config{SessionSecret: "abcdefghijklmnopqrstuvwxyz01234"} // 31 Zeichen
	if err := ValidateSessionSecret(cfg); err == nil {
		t.Fatal("expected error for secret of 31 chars, got nil")
	}
}

func TestValidateSessionSecret_ValidSecretPasses(t *testing.T) {
	cfg := &Config{SessionSecret: "a-genuinely-random-forty-char-secret-1234"}
	if err := ValidateSessionSecret(cfg); err != nil {
		t.Fatalf("expected nil for valid 40-char secret, got: %v", err)
	}
}
