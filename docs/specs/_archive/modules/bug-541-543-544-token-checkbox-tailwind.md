---
entity_id: bug-541-543-544-token-checkbox-tailwind
type: bugfix
created: 2026-06-02
updated: 2026-06-02
status: approved
version: "1.0"
tags: [frontend, svelte, tokens, checkbox, tailwind, bug-541, bug-543, bug-544]
---

# Spec: Bug #541 + #543 + #544 — Token-Cleanup, native Checkboxen, Tailwind-Rest

## Approval

- [x] Approved

## Purpose

Drei chirurgische Frontend-Fixes aus dem retrospektiven Adversary-Audit (#510): native Checkboxen auf Atomic-Komponente migrieren, Tailwind-Residual entfernen, veraltete Farb-Token-Aliasse vollständig durch kanonische Namen ersetzen.

## Hintergrund

Drei rückwirkend gefundene Regressions aus dem retrospektiven Adversary-Audit (#510, Gruppe B):
- #543: Atomic-Migration unvollständig — native Checkboxen in zwei Wizard-Schritten
- #544: Tailwind-Residual in WeatherConfigDialog nach Token-Migration #285
- #541: Alte Token-Aliasse (`--g-good`/`--g-warn`/`--g-bad`) noch nicht aus 35 Komponenten entfernt, obwohl #519 die kanonischen Namen eingeführt hat

## Acceptance Criteria

**AC-1:** `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` enthält keinen `<input type="checkbox">` mehr — stattdessen `<Checkbox>` aus `$lib/components/ui/checkbox`

**AC-2:** `frontend/src/lib/components/trip-wizard/steps/Step5Reports.svelte` enthält keinen `<input type="checkbox">` mehr — alle vier nativen Checkboxen sind durch `<Checkbox>` ersetzt

**AC-3:** `tests/tdd/test_issue_278_form_controls.py::test_ac3_no_native_checkboxes_outside_component` läuft grün durch

**AC-4:** `frontend/src/lib/components/WeatherConfigDialog.svelte` enthält keine Tailwind-Klasse `hover:bg-muted/50` mehr; Hover-Verhalten nutzt `var(--g-surface-2)` als CSS-Variable

**AC-5:** `grep -rn "var(--g-good)\|var(--g-warn)\|var(--g-bad)" frontend/src/` liefert keine Treffer mehr (alle CSS-Variablen-Referenzen umgestellt)

**AC-6:** Die drei Brücken-Aliasse (`--g-success: var(--g-good)`, `--g-warning: var(--g-warn)`, `--g-danger: var(--g-bad)`) sind aus `frontend/src/app.css` entfernt

**AC-7:** Die Token-Definitionen in `app.css` heißen jetzt `--g-success`, `--g-warning`, `--g-danger` direkt (mit unverändertem Hex-Wert); `--g-good`, `--g-warn`, `--g-bad` existieren nicht mehr in `app.css`

**AC-8:** Alle bestehenden Kontrast- und Guard-Tests (`uv run pytest tests/tdd/`) laufen grün durch

## Scope

**Nicht in diesem Fix:**
- JS-Objekt-Keys wie `good:`, `warn:`, `bad:` in `atoms/Switch.svelte` — das sind interne Variablennamen, keine CSS-Tokens
- Änderungen an Backend-Code oder Python-Dateien
- Neue Features oder Verhaltensänderungen

## Implementierungsreihenfolge

1. #543 — Step3Weather + Step5Reports: native Checkboxen ersetzen
2. #544 — WeatherConfigDialog: Tailwind-Klasse ersetzen
3. #541 — Token-Rename in 35 Svelte-Dateien + app.css (erst alle Vorkommen, dann Aliasse löschen)

## Technische Details

### #543 — Checkbox-Migration

`<Checkbox>` API:
```svelte
<Checkbox
  checked={...}
  {disabled}
  {onchange}
>Label-Text</Checkbox>
```

Die Chip-Checkboxen in Step5Reports (channelChips-Snippet, Zeile ~170) sind in custom `<label class="chip">` eingebettet — Checkbox-Komponente als kontrollierten Input ohne children verwenden, das äußere Chip-Label bleibt.

### #544 — Tailwind-Klasse ersetzen

`WeatherConfigDialog.svelte:225`:
```
hover:bg-muted/50  →  entfernen
```
Stattdessen scoped CSS in der `<style>`-Sektion:
```css
.metric-row:hover { background: var(--g-surface-2); }
```

### #541 — Token-Rename

Mapping:
- `var(--g-good)` → `var(--g-success)`
- `var(--g-warn)` → `var(--g-warning)`
- `var(--g-bad)` → `var(--g-danger)`

In app.css zusätzlich:
- `--g-good: #3d6b3a` → `--g-success: #3d6b3a`
- `--g-warn: #c08a1a` → `--g-warning: #c08a1a`
- `--g-bad: #a83232` → `--g-danger: #a83232`
- Pill/Dot-Regeln (app.css Zeilen ~370, 371, 383, 455, 456) ebenfalls umbenennen
- Bridge-Aliasse (Zeilen 73–75) danach entfernen
