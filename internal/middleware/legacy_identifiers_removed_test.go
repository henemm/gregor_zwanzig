package middleware

// TDD RED — Issue #2262: Rückbau des Alt-Format-Übergangs-Zweigs (ADR-0060).
// Spec: docs/specs/modules/session_allowlist.md, AC-20 und AC-23.
//
// # doc-compliance-test
//
// Beide Prüfungen sind Dateiinhalt-Checks (nach CLAUDE.md sonst als
// Verhaltensnachweis verboten), hier ausdrücklich als Ausnahme markiert: sie
// belegen nicht Verhalten, sondern dass ein Rückbau/Vermerk tatsächlich im
// Quelltext bzw. Dokument steht.
//
// Pfade werden relativ zu DIESER Testdatei aufgelöst (runtime.Caller), nicht
// über einen festen Hauptrepo-Pfad — sonst liefert ein Lauf im Worktree ein
// falsches Grün gegen den Hauptcheckout.

import (
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"testing"
)

func repoRootForComplianceTest(t *testing.T) string {
	t.Helper()
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller(0) fehlgeschlagen")
	}
	// internal/middleware/<diese Datei> -> zwei Ebenen hoch zur Repo-Wurzel.
	return filepath.Join(filepath.Dir(thisFile), "..", "..")
}

// AC-20: Nach dem Rückbau liefert die Suche nach den Alt-Bezeichnern keinen
// Treffer außerhalb von Tests. Bewusst NICHT der pauschale Begriff "legacy"
// — der träfe auch unabhängige Vorkommen wie
// legacy_subscription_routes_removed_test.go, die mit diesem Rückbau nichts
// zu tun haben.
func TestLegacyIdentifiers_RemovedFromProductionCode(t *testing.T) {
	root := repoRootForComplianceTest(t)
	pattern := regexp.MustCompile(
		`LegacyRevokedAt|legacy_revoked_at|legacyMaxAgeSeconds|LEGACY_MAX_AGE_SECONDS|` +
			`legacySessionValid|upgradeLegacySession|RevokeLegacySessions`)

	roots := []string{
		filepath.Join(root, "internal"),
		filepath.Join(root, "frontend", "src"),
	}

	var hits []string
	for _, r := range roots {
		_ = filepath.WalkDir(r, func(path string, d os.DirEntry, err error) error {
			if err != nil || d.IsDir() {
				return nil
			}
			name := d.Name()
			if strings.HasSuffix(name, "_test.go") || strings.HasSuffix(name, ".test.ts") {
				return nil // Testdateien dürfen den historischen Fall dokumentieren.
			}
			ext := filepath.Ext(name)
			if ext != ".go" && ext != ".ts" && ext != ".svelte" {
				return nil
			}
			data, readErr := os.ReadFile(path)
			if readErr != nil {
				return nil
			}
			if pattern.Match(data) {
				hits = append(hits, path)
			}
			return nil
		})
	}

	if len(hits) > 0 {
		t.Errorf("AC-20: Alt-Bezeichner noch im Produktivcode gefunden: %v", hits)
	}
}

// AC-23: ADR-0060 trägt nach dem Rückbau einen sichtbaren Erledigt-Vermerk
// mit Datum und Issue-Bezug.
func TestADR0060_TraegtErledigtVermerkFuerRueckbau(t *testing.T) {
	root := repoRootForComplianceTest(t)
	path := filepath.Join(root, "docs", "adr", "0060-dauerhafte-anmeldung-mit-widerrufsliste.md")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ADR-0060 nicht lesbar: %v", err)
	}
	if !strings.Contains(string(data), "#2262") || !strings.Contains(string(data), "erledigt") {
		t.Errorf("AC-23: ADR-0060 trägt noch keinen Erledigt-Vermerk mit Issue-Bezug #2262")
	}
}
