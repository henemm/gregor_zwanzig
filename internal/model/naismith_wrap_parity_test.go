package model

// Issue #1667 S2 — Paritaet der HH:MM-Formatierung (Go-Seite).
//
// Spec: docs/specs/modules/fix_1667_s2_naismith_wrap.md
//
// AC-1: Eigenschaftsnachweis der Inertheit ueber den vollen Minutenbereich
//       0..1439 gegen die alte Klemmformel als lokale Referenz.
// AC-3: Randfaelle 1439/1440/1441/2879 gegen die GEMEINSAME JSON-Fixture
//       tests/fixtures/naismith_hhmm_wrap.json, die auch der Python- und der
//       TS-Test lesen -- keine drei gespiegelten Listen.
//
// Pfadanker: os.Getwd()-Aufstieg bis zum Verzeichnis mit go.mod (genau eine im
// Repo), Vorbild internal/mail/recipient_parity_test.go::findRepoRoot. NICHT
// runtime.Caller(0) -- liefert unter -trimpath einen modulrelativen Pfad und
// bricht still. Keine feste ../../-Kette (Pfadregel #1409).

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

const maxWrapRootAscent = 6

func wrapRepoRoot(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("wrapRepoRoot: os.Getwd() fehlgeschlagen: %v", err)
	}
	for i := 0; i < maxWrapRootAscent; i++ {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	t.Fatalf("wrapRepoRoot: kein go.mod innerhalb von %d Ebenen ueber %q gefunden — "+
		"Pfadanker verloren, die Paritaets-Fixture ist nicht auffindbar.",
		maxWrapRootAscent, dir)
	return ""
}

type wrapFall struct {
	ID           string `json:"id"`
	TotalMin     int    `json:"total_min"`
	ExpectedHHMM string `json:"expected_hhmm"`
	Kommentar    string `json:"kommentar"`
}

func wrapFaelle(t *testing.T) []wrapFall {
	t.Helper()
	pfad := filepath.Join(wrapRepoRoot(t), "tests", "fixtures", "naismith_hhmm_wrap.json")
	roh, err := os.ReadFile(pfad)
	if err != nil {
		t.Fatalf("Paritaets-Fixture %q nicht lesbar: %v", pfad, err)
	}
	var daten struct {
		Faelle []wrapFall `json:"faelle"`
	}
	if err := json.Unmarshal(roh, &daten); err != nil {
		t.Fatalf("Paritaets-Fixture %q nicht parsebar: %v", pfad, err)
	}
	return daten.Faelle
}

// referenzKlemme ist die ALTE Formel (min(m, 1439)) als lokale Referenz fuer
// AC-1. Bewusst hier hinterlegt statt aus dem Produktivcode gelesen: nach dem
// Fix existiert sie dort nicht mehr, der Inertheits-Nachweis braucht sie aber
// weiterhin als Vergleichsmassstab.
func referenzKlemme(totalMin int) string {
	m := totalMin
	if m > 24*60-1 {
		m = 24*60 - 1
	}
	return fmt.Sprintf("%02d:%02d", m/60, m%60)
}

// TestWrapFixtureTraegtDieVierRandfaelle: ohne diese Zusicherung koennte eine
// leere Fixture-Liste TestFormatHHMM_ParitaetRandfaelle still auf null Faelle
// schrumpfen lassen und "nichts geprueft" als gruen ausgeben.
func TestWrapFixtureTraegtDieVierRandfaelle(t *testing.T) {
	faelle := wrapFaelle(t)
	want := map[int]bool{1439: true, 1440: true, 1441: true, 2879: true}
	if len(faelle) != len(want) {
		t.Fatalf("Fixture traegt %d Faelle, erwartet %d", len(faelle), len(want))
	}
	for _, f := range faelle {
		if !want[f.TotalMin] {
			t.Fatalf("unerwarteter Randfall total_min=%d (%s)", f.TotalMin, f.ID)
		}
		delete(want, f.TotalMin)
	}
}

// TestFormatHHMM_NormalbereichBitIdentisch prueft AC-1: fuer JEDE Minute
// 0..1439 liefert formatHHMM denselben String wie die alte Klemme — der
// Alltagsfall (Start <= ~14:00) bleibt bit-identisch.
func TestFormatHHMM_NormalbereichBitIdentisch(t *testing.T) {
	for m := 0; m < 24*60; m++ {
		got := formatHHMM(m)
		want := referenzKlemme(m)
		if got != want {
			t.Fatalf("formatHHMM(%d) = %q, alte Klemmformel = %q — Normalbereich "+
				"muss unveraendert bleiben", m, got, want)
		}
	}
}

// TestFormatHHMM_ParitaetRandfaelle prueft AC-3 gegen dieselbe JSON-Fixture,
// die der Python- und der TS-Test lesen.
func TestFormatHHMM_ParitaetRandfaelle(t *testing.T) {
	for _, f := range wrapFaelle(t) {
		got := formatHHMM(f.TotalMin)
		if got != f.ExpectedHHMM {
			t.Errorf("total_min=%d (%s): formatHHMM = %q, want %q — %s",
				f.TotalMin, f.ID, got, f.ExpectedHHMM, f.Kommentar)
		}
	}
}
