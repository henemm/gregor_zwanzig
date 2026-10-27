package config

// TDD RED — Mengen-Quoten je Tier (S5, Issue #2482). Spec:
// docs/specs/modules/mengen_quoten_je_tier.md — AC-10 / AC-14
// (Ausnahme-Liste GZ_QUOTA_EXEMPT_USER_IDS, Default leer).
//
// RED-Signal: Config.QuotaExemptUserIDs existiert nicht (Uebersetzungsfehler).

import (
	"os"
	"testing"
)

func TestLoad_ReadsQuotaExemptUserIDsFromEnv(t *testing.T) {
	os.Clearenv()
	t.Setenv("GZ_USER_ID", "ops")
	t.Setenv("GZ_QUOTA_EXEMPT_USER_IDS", "default, tester")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unerwarteter Fehler: %v", err)
	}
	if cfg.QuotaExemptUserIDs != "default, tester" {
		t.Errorf("QuotaExemptUserIDs: erwartet %q, bekommen %q", "default, tester", cfg.QuotaExemptUserIDs)
	}
}

// Produktion bleibt leer: ohne Env ist niemand ausgenommen, und die
// Ausnahme-Liste macht niemanden zum Admin.
func TestLoad_QuotaExemptUserIDsDefaultsEmpty(t *testing.T) {
	os.Clearenv()
	t.Setenv("GZ_USER_ID", "ops")
	t.Setenv("GZ_QUOTA_EXEMPT_USER_IDS", "")
	os.Unsetenv("GZ_QUOTA_EXEMPT_USER_IDS")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unerwarteter Fehler: %v", err)
	}
	if cfg.QuotaExemptUserIDs != "" {
		t.Errorf("erwartet leere QuotaExemptUserIDs ohne Env, bekommen %q", cfg.QuotaExemptUserIDs)
	}
	if cfg.AdminUserIDs != "" {
		t.Errorf("Ausnahme-Liste darf AdminUserIDs nicht beruehren, bekommen %q", cfg.AdminUserIDs)
	}
}
