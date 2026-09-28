package config

// TDD RED — Issue #2155 Scheibe S1 (Admin-Rolle), AC-5.
//
// Spec: docs/specs/modules/admin_rolle_s1.md § AC-5
//
// Diese Tests scheitern heute beim Uebersetzen: Config.AdminUserIDs und
// ParseAdminUserIDs existieren noch nicht. Sie pruefen reines Verhalten
// (Eingabe -> Menge), keine Quelltext-Inhalte.

import (
	"os"
	"testing"
)

func istAdmin(m map[string]struct{}, id string) bool {
	_, ok := m[id]
	return ok
}

// AC-5: " alice , ,bob," -> genau alice und bob; Teilstrings, andere Schreibweise
// und die leere Kennung sind KEINE Admins.
func TestParseAdminUserIDs_TrimsAndDropsEmptyEntries(t *testing.T) {
	admins := ParseAdminUserIDs(" alice , ,bob,")

	if len(admins) != 2 {
		t.Fatalf("erwartet genau 2 Admins (alice, bob), bekommen %d: %v", len(admins), admins)
	}
	for _, id := range []string{"alice", "bob"} {
		if !istAdmin(admins, id) {
			t.Errorf("%q muss Admin sein", id)
		}
	}
	for _, id := range []string{"ali", "alice2", "carol", "", " ", "Alice", "ALICE", "bo"} {
		if istAdmin(admins, id) {
			t.Errorf("%q darf KEIN Admin sein (exakter Vergleich, keine Teilstring-Treffer)", id)
		}
	}
}

// Fail-closed: leerer oder nur aus Trennern bestehender Wert ergibt eine leere Menge.
func TestParseAdminUserIDs_EmptyOrOnlySeparators_NobodyIsAdmin(t *testing.T) {
	for _, raw := range []string{"", "   ", ",", " , ,, ", "\t"} {
		admins := ParseAdminUserIDs(raw)
		if len(admins) != 0 {
			t.Errorf("raw=%q: erwartet leere Menge, bekommen %v", raw, admins)
		}
		if istAdmin(admins, "") {
			t.Errorf("raw=%q: die leere Kennung darf nie Admin sein", raw)
		}
	}
}

// AC-5 exakter Vergleich mit gemischter Schreibweise: die Liste wird nicht
// normalisiert. "Alice" in der Liste ist nicht "alice" und umgekehrt.
func TestParseAdminUserIDs_MixedCase_IsExact(t *testing.T) {
	gross := ParseAdminUserIDs("Alice")
	if !istAdmin(gross, "Alice") {
		t.Errorf("Liste \"Alice\": \"Alice\" muss Admin sein, Menge %v", gross)
	}
	if istAdmin(gross, "alice") {
		t.Errorf("Liste \"Alice\": \"alice\" darf KEIN Admin sein, Menge %v", gross)
	}

	klein := ParseAdminUserIDs("alice")
	if istAdmin(klein, "Alice") {
		t.Errorf("Liste \"alice\": \"Alice\" darf KEIN Admin sein, Menge %v", klein)
	}
}

// Ein einzelner Eintrag ohne Komma funktioniert.
func TestParseAdminUserIDs_SingleEntry(t *testing.T) {
	admins := ParseAdminUserIDs("henning")
	if len(admins) != 1 || !istAdmin(admins, "henning") {
		t.Fatalf("erwartet genau {henning}, bekommen %v", admins)
	}
}

// Die Umgebungsvariable GZ_ADMIN_USER_IDS landet in Config.AdminUserIDs
// (Praefix GZ_ + envconfig-Name ADMIN_USER_IDS).
func TestLoad_ReadsAdminUserIDsFromEnv(t *testing.T) {
	os.Clearenv()
	t.Setenv("GZ_ADMIN_USER_IDS", "alice,bob")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unerwarteter Fehler: %v", err)
	}
	if cfg.AdminUserIDs != "alice,bob" {
		t.Fatalf("erwartet AdminUserIDs=%q, bekommen %q", "alice,bob", cfg.AdminUserIDs)
	}
	admins := ParseAdminUserIDs(cfg.AdminUserIDs)
	if !istAdmin(admins, "alice") || !istAdmin(admins, "bob") {
		t.Errorf("alice und bob muessen aus der geladenen Konfiguration Admins sein: %v", admins)
	}
}

// Ohne gesetzte Variable ist niemand Admin (kein stiller Default wie "default" oder GZ_USER_ID).
func TestLoad_AdminUserIDsDefaultsEmpty(t *testing.T) {
	os.Clearenv()
	t.Setenv("GZ_USER_ID", "ops")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("unerwarteter Fehler: %v", err)
	}
	if cfg.AdminUserIDs != "" {
		t.Errorf("erwartet leere AdminUserIDs ohne GZ_ADMIN_USER_IDS, bekommen %q", cfg.AdminUserIDs)
	}
	if istAdmin(ParseAdminUserIDs(cfg.AdminUserIDs), "ops") {
		t.Errorf("GZ_USER_ID darf nicht automatisch Admin machen")
	}
}
