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
	if cfg.UserID != "default" {
		t.Errorf("expected default user ID, got %s", cfg.UserID)
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
