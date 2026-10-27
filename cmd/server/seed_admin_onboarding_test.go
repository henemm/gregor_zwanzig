package main

// Wächter — Onboarding S2 (Spec docs/specs/modules/onboarding_willkommen_checkliste.md,
// AC-1, zweiter Halbsatz): der Admin-Startnutzer aus dem Serverstart traegt das
// Merkmal "neu eingeladen" (`onboarding_pending`) NICHT. Heute schon gruen;
// bewacht die Mutation "gemeinsamen Anlage-Helfer auch in seedAdminUser
// aufrufen". Gemessen roh auf der Platte (Schluessel fehlt oder ist false).

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

func TestSeedAdminUserIsNotMarkedOnboardingPending(t *testing.T) {
	dir := t.TempDir()
	s := store.New(dir, "admin")
	cfg := &config.Config{UserID: "admin", AuthPass: "secret-pass"}

	var seedErr error
	captureLog(t, func() { seedErr = seedAdminUser(s, cfg) })
	if seedErr != nil {
		t.Fatalf("seedAdminUser: %v", seedErr)
	}

	data, err := os.ReadFile(filepath.Join(dir, "users", "admin", "user.json"))
	if err != nil {
		t.Fatalf("Messaufbau: Seed-Konto nicht angelegt: %v", err)
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("user.json kein JSON: %v", err)
	}
	if v, ok := m["onboarding_pending"]; ok && string(v) != "false" {
		t.Errorf("AC-1: der Admin-Startnutzer traegt onboarding_pending=%s — er ist kein neu Eingeladener", v)
	}
}
