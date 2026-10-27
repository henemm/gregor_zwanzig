package handler

// TDD RED: Issue #2285 AC-5 (Dach-Epic #1374)
// # doc-compliance-test
//
// Spec: docs/specs/modules/fix_2285_compare_put_merge_kernel.md
//
// Nach dem Umbau soll der Vier-Kanal-Feld-Merge fuer AlertChannelThresholds
// (Email/Telegram/Sms/PremiumSms) als "== nil"-Enumeration ausschliesslich
// in trip.go stehen -- der Compare-PUT deckt das Sub-Objekt generisch ueber
// mergeConfigMap ab. Heutiger Stand: compare_preset.go schreibt denselben
// Vier-Kanal-Merge noch explizit aus (RED).
//
// Ausfuehrung:
//   go test ./internal/handler/... -run TestAlertChannelThresholdsMergeLocation -v

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

var alertChannelThresholdsNilPattern = regexp.MustCompile(
	`AlertChannelThresholds\.(Email|Telegram|Sms|PremiumSms)\s*==\s*nil`,
)

func TestAlertChannelThresholdsMergeLocation_OnlyInTripGo(t *testing.T) {
	entries, err := os.ReadDir(".")
	if err != nil {
		t.Fatalf("ReadDir(.): %v", err)
	}

	hits := map[string]int{}
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if filepath.Ext(name) != ".go" || strings.HasSuffix(name, "_test.go") {
			continue
		}
		content, err := os.ReadFile(name)
		if err != nil {
			t.Fatalf("ReadFile(%s): %v", name, err)
		}
		n := len(alertChannelThresholdsNilPattern.FindAllIndex(content, -1))
		if n > 0 {
			hits[name] = n
		}
	}

	if hits["trip.go"] == 0 {
		t.Errorf("trip.go sollte den Schwellen-Feld-Merge tragen, aber 0 Treffer gefunden")
	}
	for name, n := range hits {
		if name == "trip.go" {
			continue
		}
		t.Errorf("AC-5: %s traegt einen duplizierten Schwellen-Feld-Merge (%d Treffer) -- nach dem Umbau soll nur trip.go Treffer haben", name, n)
	}
}
