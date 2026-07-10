package mail

import "testing"

// TDD GREEN — Issue #1219 Scheibe 1: Resend-Allowlist auf E-Mail-
// Verifikation umstellen. Spec: docs/specs/modules/fix_1219_email_verify.md
// (AC-1..AC-4, AC-7 Go-Hälfte).
//
// Go-Pendant zu tests/tdd/test_resend_verified_allowlist.py. Testet
// loadResendAllowlist()/isReservedTestDomain() direkt (package-intern).
// Fixtures ausschließlich in t.TempDir() — die echten data/users/ werden
// nie angefasst.

// AC-1: ein neutral benanntes Profil (kein "test"/"tdd" im Namen, entkommt
// also der abgelösten Namens-Heuristik) OHNE email_verified_at wird
// ausgeschlossen — der ursprüngliche Bug-Fall.
func TestLoadResendAllowlist_ExcludesUnverifiedNeutralProfile_AC1(t *testing.T) {
	dataDir := t.TempDir()
	writeUserProfileFixture(t, dataDir, "e2e-758", "e2e-758@example.com")

	allowlist := loadResendAllowlist(dataDir)
	if allowlist["e2e-758@example.com"] {
		t.Errorf("AC-1: unverifiziertes Profil darf nicht in der Allowlist landen, war: %v", allowlist)
	}
}

// AC-2: dasselbe unverifizierte Profil mit einer NICHT reservierten Domain
// wird ALLEIN wegen des fehlenden email_verified_at blockiert.
func TestLoadResendAllowlist_ExcludesUnverifiedNonReservedDomain_AC2(t *testing.T) {
	dataDir := t.TempDir()
	writeUserProfileFixture(t, dataDir, "e2e-758-gmail", "e2e-758@gmail.com")

	allowlist := loadResendAllowlist(dataDir)
	if allowlist["e2e-758@gmail.com"] {
		t.Errorf("AC-2: unverifiziertes Profil mit nicht-reservierter Domain darf nicht in der Allowlist landen, war: %v", allowlist)
	}
}

// AC-3 (Regressionsschutz): ein verifiziertes Profil mit echter, nicht
// reservierter Domain bleibt erlaubt.
func TestLoadResendAllowlist_IncludesVerifiedRealDomain_AC3(t *testing.T) {
	dataDir := t.TempDir()
	writeVerifiedUserProfileFixture(t, dataDir, "real-user", "real@gmail.com")

	allowlist := loadResendAllowlist(dataDir)
	if !allowlist["real@gmail.com"] {
		t.Errorf("AC-3: verifiziertes Profil mit echter Domain muss in der Allowlist landen, war: %v", allowlist)
	}
}

// AC-4: ein verifiziertes Profil mit RESERVIERTER Test-Domain wird IMMER
// blockiert, unabhängig vom Verifikationsstatus.
func TestLoadResendAllowlist_ExcludesVerifiedReservedDomain_AC4(t *testing.T) {
	for _, addr := range []string{
		"foo@example.com", "foo@example.net", "foo@example.org",
		"foo@x.test", "foo@x.invalid", "foo@x.localhost", "foo@x.example",
	} {
		dataDir := t.TempDir()
		writeVerifiedUserProfileFixture(t, dataDir, "reserved-fixture", addr)

		allowlist := loadResendAllowlist(dataDir)
		if allowlist[addr] {
			t.Errorf("AC-4: reservierte Domain %q darf trotz email_verified_at nicht in der Allowlist landen, war: %v", addr, allowlist)
		}
	}
}

// AC-4: isReservedTestDomain() direkt geprüft (Helper-Ebene).
func TestIsReservedTestDomain_AC4(t *testing.T) {
	reserved := []string{
		"foo@example.com", "foo@example.net", "foo@example.org",
		"foo@x.test", "foo@x.invalid", "foo@x.localhost", "foo@x.example",
		"FOO@EXAMPLE.COM",
	}
	for _, addr := range reserved {
		if !isReservedTestDomain(addr) {
			t.Errorf("isReservedTestDomain(%q) = false, want true", addr)
		}
	}
	notReserved := []string{"foo@gmail.com", "foo@henemm.com"}
	for _, addr := range notReserved {
		if isReservedTestDomain(addr) {
			t.Errorf("isReservedTestDomain(%q) = true, want false", addr)
		}
	}
}

// AC-7 (Go-Hälfte): die drei Kernfälle liefern konsistente Verdikte —
// Pendant zu TestAC7PythonVerdictsForThreeCoreCases in
// test_resend_verified_allowlist.py.
func TestLoadResendAllowlist_VerdictMatrix_AC7(t *testing.T) {
	cases := []struct {
		mailTo      string
		verified    bool
		expectAllow bool
	}{
		{"case-unverified@gmail.com", false, false},
		{"case-real@gmail.com", true, true},
		{"case-reserved@example.com", true, false},
	}
	for _, c := range cases {
		dataDir := t.TempDir()
		if c.verified {
			writeVerifiedUserProfileFixture(t, dataDir, "case-fixture", c.mailTo)
		} else {
			writeUserProfileFixture(t, dataDir, "case-fixture", c.mailTo)
		}
		allowlist := loadResendAllowlist(dataDir)
		got := allowlist[c.mailTo]
		if got != c.expectAllow {
			t.Errorf("AC-7: %q (verified=%v) => allowed=%v, want %v", c.mailTo, c.verified, got, c.expectAllow)
		}
	}
}

// Adversary Runde 1 — F002: Reserved-Domain-Bypass über Bare-TLD ohne
// Subdomain-Label und Trailing-Dot-FQDN. Symmetrie zu Python
// TestF002ReservedDomainBypassEdgeCases.
func TestIsReservedTestDomain_F002EdgeCases(t *testing.T) {
	reserved := []string{
		"user@localhost", "user@test", "user@invalid", "user@example",
		"user@example.com.",
		"user@example.com..", // F003: mehrfacher Trailing-Dot — Paritaet zu Python rstrip(".")
		"user@localhost..",
	}
	for _, addr := range reserved {
		if !isReservedTestDomain(addr) {
			t.Errorf("F002/F003: isReservedTestDomain(%q) = false, want true", addr)
		}
	}

	// F002-Gegentest: legitime Domains, die eine reservierte TLD nur als
	// Substring enthalten, dürfen NICHT fälschlich gesperrt werden.
	legit := []string{"x@mytest.de", "x@example.company"}
	for _, addr := range legit {
		if isReservedTestDomain(addr) {
			t.Errorf("F002: isReservedTestDomain(%q) = true, want false (legitime Domain)", addr)
		}
	}
}
