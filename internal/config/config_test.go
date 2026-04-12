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
