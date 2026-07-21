---
entity_id: issue_323_hex_fallbacks_cleanup
type: bugfix
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [design-system, css-tokens, frontend, ap-007, bugfix]
---

# Issue 323 — AP-007 Restdrift: Hex-Fallbacks in SmsPhoneFrame + profileSignature bereinigen

## Approval

- [ ] Approved

## Purpose

Zwei Dateien (`SmsPhoneFrame.svelte` und `profileSignature.ts`) wurden beim AP-007-Sweep in Issue #277 ausgelassen und enthalten weiterhin Hex-Farbliterale, die gegen das Design-System-Anti-Pattern AP-007 verstoßen. Dieser Fix bereinigt die verbleibenden 14 CSS-Hex-Stellen in `SmsPhoneFrame.svelte` sowie das funktionslose `accentFallback`-Feld in `profileSignature.ts` einschließlich aller abhängigen Test-Assertions und der einzigen UI-Anzeige in der Design-Preview-Route.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** 4 Dateien, ~35 LoC, reine Bereinigung ohne Logik-Änderungen

### Betroffene Dateien

| Datei | Art der Änderung |
|---|---|
| `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` | 14 Hex-Literale → Token oder CSS-Keyword |
| `frontend/src/lib/utils/profileSignature.ts` | `accentFallback`-Feld + 4 Hex-Werte entfernen |
| `frontend/src/lib/utils/profileSignature.test.ts` | 15 `accentFallback`-Assertions + `HEX_PATTERN` entfernen |
| `frontend/src/routes/_design/+page.svelte` | Zeile 158: `{sig.accentFallback}` entfernen |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | Upstream | Definiert alle `--g-*` Token (Single Source of Truth); alle referenzierten Tokens bereits vorhanden |
| `docs/design-system/ANTI-PATTERNS.md` | Referenz | Regel AP-007 mit Grep-Kommando |
| `docs/specs/modules/issue_277_css_variable_fallbacks.md` | Referenz | Vorherige Bereinigung (26 Komponenten) — gleiche Ersetzungslogik |
| `docs/specs/modules/issue_238_profile_signatures.md` | Abgelöst | AC-3/AC-5 forderten `accentFallback` mit Hex — Bug #323 hat Priorität |

## Implementation Details

### SmsPhoneFrame.svelte — Ersetzungstabelle

```diff
# Fallbacks bei definierten Token entfernen
- color: var(--g-ink, #1a1a18);          →  color: var(--g-ink);
- background: var(--g-warning, #c8882a); →  background: var(--g-warning);
- background: var(--g-paper, #f6f4ee);   →  background: var(--g-paper);
- color: var(--g-ink-faint, #9c9a90);    →  color: var(--g-ink-faint);
- color: var(--g-ink-muted, #5c5a52);    →  color: var(--g-ink-muted);

# Standalone Hex → Token
- background: #1a1a18;  →  background: var(--g-ink);
- color: #b03a2e;       →  color: var(--g-danger);   /* Token: #b33a2a — 2 Hex-Steps Differenz, korrekte Semantik */

# Standalone Hex → CSS-Keyword (kein Token für reines Schwarz)
- background: #000;     →  background: black;
```

Alle 7 betroffenen CSS-Regeln auf Zeilen 76–108 — kein JavaScript-Code betroffen.

### profileSignature.ts — accentFallback entfernen

```diff
# Typ-Definition
  export interface ProfileSignature {
    id: string;
    label: string;
-   accentFallback: string;
  }

# SIGNATURES-Konstante: accentFallback-Einträge aus allen 4 Profil-Objekten entfernen
# (GR20, KHW, Stubaier, Allgemein — je ein Hex-Wert: #4a7fb5, #3a7d44, #c45a2a, #6b675c)
```

Begründung: `accentFallback` wurde nie funktional genutzt — Mail-Rendering erfolgt Python-seitig. Das Feld war ein Überbleibsel aus Spec #238 AC-3/AC-5.

### profileSignature.test.ts — Assertions entfernen

```diff
# HEX_PATTERN Konstante entfernen (wird nur für accentFallback-Checks gebraucht)
- const HEX_PATTERN = /^#[0-9a-fA-F]{3,6}$/;

# assertShape-Helper: accentFallback-Zeile entfernen
- expect(sig.accentFallback).toMatch(HEX_PATTERN);

# Alle 15 accentFallback-Assertions entfernen (eine pro Profil-Objekt × Testfälle)
```

### _design/+page.svelte — Anzeige entfernen

```diff
- <span>{sig.accentFallback}</span>   /* Zeile 158 */
```

### Umsetzungsreihenfolge

1. `profileSignature.ts` — Typ-Feld + Hex-Werte entfernen
2. `profileSignature.test.ts` — `HEX_PATTERN` + alle `accentFallback`-Assertions entfernen
3. `_design/+page.svelte` Z. 158 — `{sig.accentFallback}` entfernen
4. `SmsPhoneFrame.svelte` — alle 14 Hex-Stellen ersetzen (mechanisch, Zeilen 76–108)
5. TypeScript-Compile prüfen: `npm run build` in `frontend/`

## Expected Behavior

- **Input:** 4 Dateien mit Hex-Farbliteralen bzw. `accentFallback`-Feld
- **Output:** Dieselben Dateien ohne Hex-Literale; `accentFallback` vollständig entfernt
- **Side effects:** `SmsPhoneFrame` sieht visuell identisch aus (Tokens hatten gleiche Werte). Warning-Text-Farbe ändert sich minimal: `#b67700` (bisheriger undokumentierter Fallback) → `#c8882a` (Token `--g-warning`) — leicht heller, gleiche Semantik.

## Acceptance Criteria

- **AC-1:** Given der Quelltext in `frontend/src/lib/components/preview/SmsPhoneFrame.svelte` / When `grep -E '#[0-9a-fA-F]{3,6}'` auf die Datei ausgeführt wird / Then ist die Trefferanzahl 0 (keine Hex-Literale mehr)
  - Test: `tests/tdd/test_issue_323_hex_fallbacks.py::test_smsphoneframe_no_hex_literals`

- **AC-2:** Given der Quelltext in `frontend/src/lib/utils/profileSignature.ts` / When `grep -E '#[0-9a-fA-F]{3,6}'` auf die Datei ausgeführt wird / Then ist die Trefferanzahl 0 (keine Hex-Literale mehr)
  - Test: `tests/tdd/test_issue_323_hex_fallbacks.py::test_profile_signature_no_hex_literals`

- **AC-3:** Given die SmsPhoneFrame-Komponente im Browser auf Staging / When ein SMS-Preview visuell verglichen wird (vor/nach) / Then sind keine sichtbaren Farbunterschiede erkennbar (Tokens hatten identische Werte)
  - Test: Manuell-visuell auf Staging (kein automatisierter Screenshot-Diff)

- **AC-4:** Given das Frontend nach dem Entfernen von `accentFallback` / When alle Dateien geprüft werden / Then enthält weder `profileSignature.ts` noch irgendeine produktive `.svelte`-Datei noch `accentFallback`-Referenzen
  - Test: `tests/tdd/test_issue_323_hex_fallbacks.py::test_accent_fallback_field_removed_from_type`, `test_accent_fallback_not_used_in_design_page`, `test_accent_fallback_not_used_in_any_productive_component`

## Known Limitations

- AC-3 (visueller Vergleich) ist ohne automatisierten Screenshot-Diff nicht maschinell verifizierbar — manuelle Sichtprüfung oder Playwright-Screenshot gegen Staging genügt
- `#b67700` (Warning-Text-Fallback in SmsPhoneFrame Z. 104) weicht vom Token `--g-warning: #c8882a` ab — der Unterschied ist gering, aber bei Staging-Vergleich zu prüfen
- `_design/+page.svelte` ist eine interne Design-Preview-Route ohne Produktions-Nutzer — das Entfernen von `{sig.accentFallback}` hat keinen funktionalen Impact

## Changelog

- 2026-05-22: Initial spec created (Issue #323, AP-007 Restdrift)
