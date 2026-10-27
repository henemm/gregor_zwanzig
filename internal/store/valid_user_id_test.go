package store

import "testing"

// TDD RED — Issue #2140 Scheibe 1, AC-13. SPEC:
// docs/specs/modules/fix_2140_pfad_traversal_nutzer_kennung.md
//
// Bewusst in einer EIGENEN Datei (siehe pathsafe_test.go, Kopf-Kommentar):
// store.ValidUserID existiert noch nicht (pathsafe.go ist NEU laut Spec) —
// dieser Test erzeugt heute einen Compile-Fehler fuer das gesamte Paket
// "internal/store". Das ist das erwartete RED fuer AC-13; er wird getrennt
// von pathsafe_test.go (AC-11/AC-12, rein verhaltensbasiert) ausgefuehrt,
// damit deren Assertion-Fehlschläge sichtbar bleiben.
func TestValidUserID_AcceptsExistingBestandUserIDs_AC13(t *testing.T) {
	cases := []string{"default", "henning", "steffi", "validator-issue110"}
	for _, id := range cases {
		if !ValidUserID(id) {
			t.Errorf("AC-13: ValidUserID(%q) expected true, got false", id)
		}
	}
}
