package config

import (
	"os"
	"testing"
)

func TestLoadDefaults(t *testing.T) {
	// GIVEN: No env vars set
	os.Clearenv()

	// WHEN: Loading config
	cfg, err := Load()

	// THEN: Defaults are applied
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != "8090" {
		t.Errorf("expected default port 8090, got %s", cfg.Port)
	}
	if cfg.PythonCoreURL != "http://localhost:8000" {
		t.Errorf("expected default python URL, got %s", cfg.PythonCoreURL)
	}
	if cfg.DataDir != "data" {
		t.Errorf("expected default data dir, got %s", cfg.DataDir)
	}
	if cfg.UserID != "" {
		t.Errorf("expected empty user ID (Issue #2151 Scheibe B, kein stiller default-Rueckfall), got %q", cfg.UserID)
	}
}

// TestConfigUserIDDefaultsEmpty prueft AC-4 gezielt und unabhaengig von
// TestLoadDefaults: ohne gesetzte GZ_USER_ID ist cfg.UserID ein leerer Text,
// nicht mehr automatisch "default" (Issue #2151 Scheibe B).
func TestConfigUserIDDefaultsEmpty(t *testing.T) {
	os.Clearenv()
	t.Setenv("GZ_AUTH_PASS", "irrelevant-fuer-diesen-test")
	os.Unsetenv("GZ_USER_ID")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.UserID != "" {
		t.Errorf("erwartet leere Nutzerkennung ohne GZ_USER_ID, bekommen: %q", cfg.UserID)
	}
}

// Issue #116 — Default-Bind-Adresse muss 127.0.0.1 sein, damit das Backend
// nicht direkt aus dem Internet erreichbar ist (Nginx als einziger Eintrittspunkt).
func TestLoadDefaults_HostIsLocalhost(t *testing.T) {
	// GIVEN: No env vars set
	os.Clearenv()

	// WHEN: Loading config
	cfg, err := Load()

	// THEN: Host defaults to 127.0.0.1
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Host != "127.0.0.1" {
		t.Errorf("expected default host 127.0.0.1, got %q", cfg.Host)
	}
}

// Issue #116 — Override via GZ_HOST muss funktionieren (Container/Sonderfälle).
func TestLoadFromEnv_HostOverride(t *testing.T) {
	// GIVEN: GZ_HOST is set
	os.Clearenv()
	os.Setenv("GZ_HOST", "0.0.0.0")
	defer os.Clearenv()

	// WHEN: Loading config
	cfg, err := Load()

	// THEN: Host is overridden
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Host != "0.0.0.0" {
		t.Errorf("expected host 0.0.0.0, got %q", cfg.Host)
	}
}

func TestLoadFromEnv(t *testing.T) {
	// GIVEN: Custom env vars with GZ_ prefix
	os.Clearenv()
	os.Setenv("GZ_PORT", "9090")
	os.Setenv("GZ_PYTHON_CORE_URL", "http://python:8000")
	os.Setenv("GZ_DATA_DIR", "/tmp/testdata")
	os.Setenv("GZ_USER_ID", "testuser")
	defer os.Clearenv()

	// WHEN: Loading config
	cfg, err := Load()

	// THEN: Env vars override defaults
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != "9090" {
		t.Errorf("expected port 9090, got %s", cfg.Port)
	}
	if cfg.PythonCoreURL != "http://python:8000" {
		t.Errorf("expected custom python URL, got %s", cfg.PythonCoreURL)
	}
	if cfg.DataDir != "/tmp/testdata" {
		t.Errorf("expected custom data dir, got %s", cfg.DataDir)
	}
	if cfg.UserID != "testuser" {
		t.Errorf("expected custom user ID, got %s", cfg.UserID)
	}
}

// Issue #2147 Scheibe B2 (AC-16): der Resend-Guard liest die Betreiber-Adresse
// ueber PoEmailFromEnv — sie muss in jedem Fall (Variable fehlt, gesetzt,
// leer gesetzt) mit Config.PoEmail aus Load uebereinstimmen, sonst driftet
// der Default zwischen Tier-Antrag-Versand und Empfaenger-Guard.
func TestPoEmailFromEnvGleichLoad(t *testing.T) {
	t.Setenv("GZ_PO_EMAIL", "")
	for _, fall := range []struct {
		name  string
		setze func()
	}{
		{"variable fehlt", func() { os.Unsetenv("GZ_PO_EMAIL") }},
		{"variable gesetzt", func() { os.Setenv("GZ_PO_EMAIL", "betreiber@beispiel.de") }},
		{"variable leer", func() { os.Setenv("GZ_PO_EMAIL", "") }},
	} {
		fall.setze()
		cfg, err := Load()
		if err != nil {
			t.Fatalf("%s: Load: %v", fall.name, err)
		}
		if got := PoEmailFromEnv(); got != cfg.PoEmail {
			t.Errorf("%s: PoEmailFromEnv()=%q, Load().PoEmail=%q", fall.name, got, cfg.PoEmail)
		}
	}
	os.Unsetenv("GZ_PO_EMAIL")
	if cfg, _ := Load(); cfg.PoEmail != DefaultPoEmail {
		t.Errorf("default-Tag von Config.PoEmail (%q) weicht von DefaultPoEmail (%q) ab", cfg.PoEmail, DefaultPoEmail)
	}
}
