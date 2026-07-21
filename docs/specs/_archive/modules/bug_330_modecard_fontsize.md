---
entity_id: bug_330_modecard_fontsize
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [design-system, css-tokens, frontend, ap-017, bugfix, area-alerts]
---

# Bug 330 — Hardcodierte font-sizes in ModeCard.svelte → --g-text-* Tokens

## Approval

- [ ] Approved

## Purpose

`ModeCard.svelte` (Alert-Modus-Auswahl im AlertRulesEditor) enthält 5 hardcodierte `font-size`-Werte und verstößt damit gegen das Design-System-Anti-Pattern AP-017 ("Drift in der Schrift-Skala"). Dieser Fix ersetzt alle 5 Werte durch die entsprechenden `--g-text-*` Tokens aus `app.css`. Da alle Ist-Werte exakt auf vorhandene Pixel-Tokens abbilden, bleibt das sichtbare Layout pixelgenau identisch.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** 1 Datei, ~5 LoC, reine Token-Substitution ohne Logik-Änderung

### Betroffene Datei

| Datei | Art der Änderung |
|---|---|
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | 5 `font-size`-Literale → `--g-text-*` Token |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` (Z. 109–117) | Upstream | Definiert `--g-text-*` Tokens (Single Source of Truth); alle referenzierten Tokens bereits vorhanden |
| `docs/design-system/ANTI-PATTERNS.md` (AP-017) | Referenz | Regel "Drift in der Schrift-Skala" |
| `docs/design-system/TOKENS.md` (Z. 82–90) | Referenz | Typografie-Skala-Tabelle |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Vorbild | Nutzt bereits `font-size: var(--g-text-sm)` ohne Hex/px-Fallback |

## Implementation Details

### Ersetzungstabelle (auf Basis der tatsächlichen Ist-Werte)

Die Issue-Tabelle nennt ungenaue Ausgangswerte. Maßgeblich sind die echten Werte aus der Datei — alle bilden **exakt** auf Pixel-Tokens ab (rem-Basis 16px):

```diff
# .eyebrow (Z. 105)
- font-size: 0.6875rem;   →  font-size: var(--g-text-xs);   /* 11px == 11px */

# .title (Z. 112)
- font-size: 0.9375rem;   →  font-size: var(--g-text-md);   /* 15px == 15px */

# .description (Z. 115)
- font-size: 0.8125rem;   →  font-size: var(--g-text-sm);   /* 13px == 13px */

# .example (Z. 120)
- font-size: 11px;        →  font-size: var(--g-text-xs);   /* 11px == 11px */

# .field-count-badge (Z. 131)
- font-size: 0.6875rem;   →  font-size: var(--g-text-xs);   /* 11px == 11px */
```

Keine Fallback-Werte hinzufügen (`, #hex` / `, 11px`) — konsistent mit AP-007-Cleanup (#277/#323): Tokens sind in `app.css` garantiert definiert.

### Umsetzungsreihenfolge

1. Alle 5 `font-size`-Stellen im `<style>`-Block ersetzen (mechanisch)
2. TypeScript/Svelte-Compile prüfen: `npm run build` in `frontend/`

## Expected Behavior

- **Input:** `ModeCard.svelte` mit 5 hardcodierten `font-size`-Literalen
- **Output:** Dieselbe Datei mit 5 `font-size: var(--g-text-*)` Token-Referenzen
- **Side effects:** Keine. Layout pixelgenau identisch (Token-Werte == Ist-Werte). Keine Props, API oder Logik betroffen.

## Acceptance Criteria

- **AC-1:** Given der Quelltext in `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` / When `grep -E 'font-size:\s*[0-9]'` auf die Datei ausgeführt wird / Then ist die Trefferanzahl 0 (keine numerischen font-size-Literale mehr)
  - Test: `tests/tdd/test_bug_330_modecard_fontsize.py::test_no_hardcoded_font_sizes`

- **AC-2:** Given der `<style>`-Block der Komponente / When nach `font-size: var(--g-text-` gesucht wird / Then existieren genau 5 Token-Referenzen mit den Tokens `--g-text-xs` (3×), `--g-text-sm` (1×), `--g-text-md` (1×)
  - Test: `tests/tdd/test_bug_330_modecard_fontsize.py::test_font_sizes_use_correct_tokens`

- **AC-3:** Given die Alarmregeln-Modus-Auswahl im Browser auf Staging / When die drei Modus-Karten (Absolut/Änderung/Beides) vor/nach visuell verglichen werden / Then sind keine sichtbaren Layout- oder Schriftgrößen-Unterschiede erkennbar (Tokens hatten identische px-Werte)
  - Test: Manuell-visuell auf Staging (kein automatisierter Screenshot-Diff)

## Known Limitations

- AC-3 (visueller Vergleich) ist ohne automatisierten Screenshot-Diff nicht maschinell verifizierbar — manuelle Sichtprüfung bzw. Playwright-Screenshot gegen Staging genügt
- Issue-Titel nennt "AP-010e"; relevant ist tatsächlich **AP-017** in ANTI-PATTERNS.md (Naming-Diskrepanz ohne inhaltlichen Effekt)

## Changelog

- 2026-05-22: Initial spec created (Bug #330, AP-017 Schrift-Skala-Drift)
