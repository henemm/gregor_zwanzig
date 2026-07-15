package store

// Issue #1250 Scheibe 2 — "Pause-Konvergenz": additives Feld PausedAt am
// ComparePreset, Dual-Write mit der Alt-Semantik schedule=="manual".
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md, AC-7.
//
// Adversary-Runde 1 (F001 CRITICAL / F002 MEDIUM) korrigierte das Design:
// NormalizeComparePreset laeuft auch auf dem LESE-Pfad (LoadComparePresets,
// kein Write-Back) — ein time.Now()-SET dort wuerde paused_at bei jedem GET
// driften lassen, ohne je persistiert zu werden. Deshalb:
//   - NormalizeComparePreset traegt NUR noch die deterministische Loeschung
//     (schedule!="manual" -> paused_at=nil), keine Zeit, driftfrei ueberall.
//   - MaterializePausedAt (injizierte Zeit, testbar) setzt paused_at NUR auf
//     dem Schreib-Pfad (Handler PUT/POST mit time.Now().UTC()).
//
// KEINE Mocks: direkter Aufruf der echten Store-Funktionen.

import (
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// AC-7: schedule=="manual" ohne PausedAt -> MaterializePausedAt setzt PausedAt
// auf die injizierte (feste, deterministische) Zeit.
func TestMaterializePausedAt_ManualScheduleSetsPausedAt(t *testing.T) {
	fixedTime := time.Date(2026, 7, 15, 10, 0, 0, 0, time.UTC)
	p := &model.ComparePreset{
		ID:       "cp-manual-no-paused-at",
		Schedule: "manual",
		PausedAt: nil,
	}

	MaterializePausedAt(p, fixedTime)

	if p.PausedAt == nil {
		t.Fatal("expected PausedAt gesetzt fuer schedule==\"manual\", war nil")
	}
	if !p.PausedAt.Equal(fixedTime) {
		t.Errorf("expected PausedAt == injizierte Zeit %v, war %v", fixedTime, *p.PausedAt)
	}
	if p.Schedule != "manual" {
		t.Errorf("expected schedule unveraendert \"manual\", war %q (Dual-Write: schedule bleibt bestehen)", p.Schedule)
	}
}

// Entpausen: schedule != "manual" mit gesetztem PausedAt -> Normalize loescht PausedAt.
// Deterministisch (kein time.Now() involviert) — bleibt auf NormalizeComparePreset,
// das lief schon vor dem Adversary-Fix korrekt und ist vom F001-Fix nicht betroffen.
func TestNormalizeComparePreset_NonManualScheduleClearsPausedAt(t *testing.T) {
	existing := time.Date(2026, 7, 1, 12, 0, 0, 0, time.UTC)
	p := &model.ComparePreset{
		ID:       "cp-daily-with-paused-at",
		Schedule: "daily",
		PausedAt: &existing,
	}

	NormalizeComparePreset(p)

	if p.PausedAt != nil {
		t.Errorf("expected PausedAt==nil nach Entpausen (schedule!=\"manual\"), war %v", *p.PausedAt)
	}
}

// Regressionstest F001 (CRITICAL): NormalizeComparePreset laeuft auch auf dem
// Lese-Pfad (LoadComparePresets) OHNE Write-Back. Zweimaliger Aufruf auf ein
// manual-Preset OHNE paused_at darf KEINEN Zeitstempel erfinden — sonst
// driftet paused_at bei jedem GET, ohne je persistiert zu werden.
func TestNormalizeComparePreset_ManualWithoutPausedAt_NoDriftOnRepeatedLoad(t *testing.T) {
	p := &model.ComparePreset{
		ID:       "cp-manual-never-materialized",
		Schedule: "manual",
		PausedAt: nil,
	}

	NormalizeComparePreset(p)
	if p.PausedAt != nil {
		t.Fatalf("expected PausedAt==nil nach 1. Normalize (Lese-Pfad darf keine Zeit erfinden), war %v", *p.PausedAt)
	}

	NormalizeComparePreset(p)
	if p.PausedAt != nil {
		t.Fatalf("expected PausedAt==nil nach 2. Normalize (kein Drift bei wiederholtem Load), war %v", *p.PausedAt)
	}
}

// Zeitstempel-Stabilitaet: ein bereits gesetzter PausedAt darf bei
// wiederholtem MaterializePausedAt NICHT ueberschrieben werden (sonst
// springt die Pausierungszeit bei jedem unrelated Save).
func TestMaterializePausedAt_ExistingPausedAtNotOverwritten(t *testing.T) {
	t1 := time.Date(2026, 6, 1, 8, 0, 0, 0, time.UTC)
	t2 := time.Date(2026, 7, 15, 10, 0, 0, 0, time.UTC)
	p := &model.ComparePreset{
		ID:       "cp-manual-existing-paused-at",
		Schedule: "manual",
		PausedAt: &t1,
	}

	MaterializePausedAt(p, t2)

	if p.PausedAt == nil {
		t.Fatal("expected PausedAt weiterhin gesetzt, war nil")
	}
	if !p.PausedAt.Equal(t1) {
		t.Errorf("expected PausedAt unveraendert %v, war %v — MaterializePausedAt darf einen bestehenden Zeitstempel nicht ueberschreiben", t1, *p.PausedAt)
	}
}
