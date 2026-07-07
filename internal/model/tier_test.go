package model

import "testing"

// TDD RED — Issue #1069: Channel-Gating nach Nutzerlevel (Slice 2, Epic #1067).
//
// SmsAllowed(tier) existiert noch nicht (Compile-Fehler bis zur Implementierung
// von internal/model/tier.go) — das ist der RED-Zustand dieser Datei.
//
// Spec: docs/specs/modules/issue_1069_tier_channel_gating.md

func TestSmsAllowedByTier(t *testing.T) {
	cases := []struct {
		tier string
		want bool
	}{
		{"free", false},
		{"standard", true},
		{"premium", true},
		{"", false},        // Bestandsnutzer ohne Tier-Feld (AC-7)
		{"unknown", false}, // unbekannter Wert darf nicht versehentlich erlauben
	}

	for _, c := range cases {
		got := SmsAllowed(c.tier)
		if got != c.want {
			t.Errorf("SmsAllowed(%q) = %v, want %v", c.tier, got, c.want)
		}
	}
}
