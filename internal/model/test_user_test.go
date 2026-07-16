package model

import "testing"

// TestIsTestUserID_CaseParity (Issue #1265 Fix-Loop 1, Adversary-Finding
// F002): der Fixed-ID-Zweig verglich vor dem Fix gegen die UN-lowercased
// Originalvariable — eine Groß-Schreibvariante der Fixture-ID
// (TG-LIVE-E2E) wurde fälschlich als echter User behandelt. Symmetrisch zu
// tests/tdd/test_issue_1013_telegram_test_isolation.py::
// test_central_test_user_predicate_is_case_insensitive_for_fixture_id.
func TestIsTestUserID_CaseParity(t *testing.T) {
	cases := []struct {
		userID string
		want   bool
	}{
		{"test_xyz", true},
		{"tdd-123", true},
		{"tg-live-e2e", true},
		{"TG-LIVE-E2E", true},
		{"Tg-Live-E2e", true},
		{"henning", false},
		{"steffi", false},
		{"admin", false},
		{"default", false},
	}
	for _, c := range cases {
		if got := IsTestUserID(c.userID); got != c.want {
			t.Errorf("IsTestUserID(%q) = %v, want %v", c.userID, got, c.want)
		}
	}
}

// TestIsTestUserIDSubstringOnly_ExcludesFixedFixture dokumentiert, dass der
// substring-only-Helfer (internal/mail-Konsument, Issue #1265 Fix-Loop 1
// Ripple-Fund) den tg-live-e2e-Sonderfall NICHT enthält.
func TestIsTestUserIDSubstringOnly_ExcludesFixedFixture(t *testing.T) {
	if IsTestUserIDSubstringOnly("tg-live-e2e") {
		t.Error("IsTestUserIDSubstringOnly('tg-live-e2e') = true, want false")
	}
	if !IsTestUserIDSubstringOnly("tdd-prod-user") {
		t.Error("IsTestUserIDSubstringOnly('tdd-prod-user') = false, want true")
	}
}
