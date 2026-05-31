---
entity_id: bug_482_stage_badge_color
type: bugfix
created: 2026-05-31
updated: 2026-05-31
status: draft
version: "1.0"
tags: [bugfix, frontend, wizard, pill, color, accent, issue-482]
---

<!-- Issue #482 — Trip-Wizard Step 2: Etappen-Badge zeigt Blau statt Orange (tone="info" statt tone="accent") -->

# Bug #482 — Etappen-Badge im Trip-Wizard Step 2 hat falsche Farbe (Blau statt Orange)

## Approval

- [ ] Approved

## Purpose

`StageRow.svelte` rendert die Etappen-Nummer-Pill (z.B. "E1", "E2") mit `tone="info"`, was den blauen Token `--g-info: #2a6cb3` verwendet. Laut Design-Handoff und der Wizard-Redesign-Spec (`issue_300_wizard_redesign.md`) müssen Etappen-Elemente die orange Akzentfarbe `--g-accent: #c45a2a` tragen. Der Fix ersetzt `tone="info"` durch `tone="accent"` in einer einzigen Zeile.

## Source

- **Datei:** `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte`
- **Zeile:** 77
- **Schicht:** Frontend — SvelteKit-Komponente (Trip-Wizard Step 2)

```svelte
<!-- Vorher (buggy): -->
<Pill tone="info">{formatStageNumber(nonPauseIndex)}</Pill>

<!-- Nachher (korrekt): -->
<Pill tone="accent">{formatStageNumber(nonPauseIndex)}</Pill>
```

## Estimated Scope

- **LoC:** 1
- **Files:** 1
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/atoms/Pill.svelte` | Atom-Komponente | Rendert die Pill; akzeptiert `tone`-Prop; kein Change nötig |
| `frontend/src/app.css` | CSS-Token | Definiert `--g-accent: #c45a2a` (orange) und `--g-info: #2a6cb3` (blau); kein Change nötig |
| `docs/specs/modules/issue_300_wizard_redesign.md` | Design-Spec | Legt orange als Akzentfarbe für Etappen-Elemente fest |

## Implementation Details

Einzige Änderung in `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte`, Zeile 77:

```svelte
<!-- Vorher: -->
<Pill tone="info">{formatStageNumber(nonPauseIndex)}</Pill>

<!-- Nachher: -->
<Pill tone="accent">{formatStageNumber(nonPauseIndex)}</Pill>
```

Keine weiteren Änderungen. `Pill.svelte` unterstützt `tone="accent"` bereits — kein Umbau der Komponente erforderlich. Keine Import-Änderungen.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/components/trip-wizard/steps/StageRow.svelte` | 0 (1 Zeile ersetzt) | ja |
| **Gesamt** | **1 Zeile geändert** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** Trip-Wizard Step 2 mit mindestens einer Etappe (kein Pausentag)
- **Output:** Etappen-Nummer-Pill (z.B. "E1", "E2") wird in orange (`--g-accent: #c45a2a`) dargestellt
- **Vorher (buggy):** Pill erscheint blau (`--g-info: #2a6cb3`)
- **Side effects:** Keine. Pausentage verwenden die Pill-Komponente nicht mit `nonPauseIndex` — kein Impact auf andere Zeilen.

## Acceptance Criteria

- **AC-1:** Given der Trip-Wizard ist auf Step 2 (Etappen) geöffnet und mindestens eine Etappe ist vorhanden / When die Etappenliste gerendert wird / Then hat die Etappen-Nummer-Pill (z.B. "E1") die CSS-Farbe `--g-accent` (#c45a2a, orange) und nicht `--g-info` (#2a6cb3, blau)
  - Test: (populated after /tdd-red)

- **AC-2:** Given `StageRow.svelte` enthält die Pill-Zeile / When der Quellcode geprüft wird / Then lautet das Attribut `tone="accent"` und nicht `tone="info"`
  - Test: (populated after /tdd-red)

## Known Limitations

- Betrifft ausschließlich Etappen-Badges (nicht Pausentag-Zeilen, die keine nummerierte Pill zeigen).
- Kein visueller Regressionstest im CI-Setup — Verifikation erfolgt manuell via Playwright-Screenshot gegen Staging.

## Out of Scope

- Änderungen an `Pill.svelte` oder `app.css`
- Andere `tone="info"`-Verwendungen im Wizard (separates Audit)
- Farbkalibrierung des Accent-Tokens selbst

## Changelog

- 2026-05-31: Initial spec erstellt. Ein-Zeilen-Fix: `tone="info"` → `tone="accent"` in StageRow.svelte:77. Behebt falschen blauen Badge im Trip-Wizard Step 2 (Issue #482, SOLL-IST-Audit Finding M-10).
