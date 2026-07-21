---
entity_id: issue_277_css_variable_fallbacks
type: module
created: 2026-05-20
updated: 2026-05-20
status: implemented
version: "1.0"
tags: [design-system, css-tokens, frontend, foundation]
---

# Issue 277 — CSS Variable Fallbacks bereinigen

## Approval

- [x] Approved (2026-05-20)

## Purpose

Mehrere Svelte-Komponenten referenzieren CSS-Variablen (`--g-primary`, `--g-border`), die in `app.css` nicht existieren. Statt der Markenfarben zeigen die Fallbacks System-Blau (#2563eb) und Neutral-Grau (#e5e7eb). Zusätzlich haben korrekte Token unnötige (teils falsche) Fallback-Argumente, die künftige Regressions verbergen.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** ~25 Svelte-Komponenten, reine CSS-Änderungen, kein Logic-Code

### Betroffene Dateien — `--g-primary` → `--g-ink` (Buttons)

| Datei | Zeilen | Ersatz |
|---|---|---|
| `frontend/src/lib/components/briefings-tab/BriefingsTab.svelte` | 77–78 | `--g-ink` |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | 292, 294 | `--g-ink` |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | 111–112 | `--g-ink` |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | 102–103 | `--g-ink` |

### Betroffene Dateien — `--g-primary` → `--g-accent` (Active/Selected/Link)

| Datei | Zeilen | Kontext |
|---|---|---|
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | 91, 93 | `.mode-card.selected` Border + Box-Shadow |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | 76 | `.edit-link` Link-Farbe |
| `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte` | 117, 119 | `.toggle.on` Active-Toggle |

### Betroffene Dateien — `--g-border` → `--g-ink-faint` (alle 29 Vorkommen)

| Datei | Zeilen |
|---|---|
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | 86 |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | 228, 237, 277, 288 |
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | 78 |
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` | 121 |
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | 37, 55 |
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | 67, 81 |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | 84 |
| `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte` | 95, 111, 124, 140 |
| `frontend/src/lib/components/alerts-tab/AlertMetricTable.svelte` | 42 |
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | 161 |
| `frontend/src/lib/components/trip-detail/PreviewCard.svelte` | 50 |
| `frontend/src/lib/components/trip-detail/TablePreview.svelte` | 101, 132 |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | 348, 377 |
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | 50 |
| `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` | 62 |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | 52 |
| `frontend/src/lib/components/trip-detail/PresetRow.svelte` | 40, 64 |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | 129 |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | 185, 226 |

### Betroffene Dateien — unnötige/falsche Fallbacks entfernen

**Kritisch: `var(--g-accent, #2563eb)` → `var(--g-accent)` (Fallback zeigt fälschlich Blau statt Burnt Orange):**
- `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte` Z. 103
- `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` Z. 80
- `frontend/src/lib/components/trip-detail/PreviewCard.svelte` Z. 66

**`var(--g-ink-muted, #6b7280)` → `var(--g-ink-muted)` (Fallback unnötig):**
- `AlertRuleRow.svelte` Z. 250, 266 / `ModeCard.svelte` Z. 107 / `AlertCooldownCard.svelte` Z. 58, 59 / `AlertQuietHoursCard.svelte` Z. 82 / `AlertMetricRow.svelte` Z. 131, 135 / `AlertPreviewCard.svelte` Z. 115 / `AlertRow.svelte` Z. 55

**`var(--g-ink-faint, #6b7280)` → `var(--g-ink-faint)` (Fallback unnötig):**
- `AlertRulesEditor.svelte` Z. 70 / `ModeCard.svelte` Z. 99, 112 / `TripHero.svelte` Z. 66, 71, 89 / `AlertsPreviewCard.svelte` Z. 63 / `StageDetailRow.svelte` Z. 198 / `StageList.svelte` Z. 75 / `BriefingPreviewCard.svelte` Z. 73 / `WeatherMetricsPreviewCard.svelte` Z. 61 / `FullProfile.svelte` Z. 210

**`var(--g-surface-2, #f3f4f6)` → `var(--g-surface-2)` (Fallback unnötig):**
- `AlertRulesEditor.svelte` Z. 92 / `AlertRuleRow.svelte` Z. 297 / `ModeCard.svelte` Z. 88 / `AlertMetricRow.svelte` Z. 130

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | Upstream | Definiert alle `--g-*` Token (Single Source of Truth) |
| `docs/reference/design_system.md` | Referenz | Design-Regeln für Button-Varianten, Border-Semantik |

## Implementation Details

### Semantische Unterscheidung für `--g-primary`

```
--g-primary (UNDEFINIERT) hat zwei Kontexte:

1. Primary-Button (.btn-primary, Speichern-Aktionen):
   → Ersatz: var(--g-ink)       /* #1a1a18 — Tinte auf Papier */
   Begründung: app.css [data-variant="primary"] nutzt --g-ink als Hintergrund.

2. Selected/Active-State (ModeCard.selected, Toggle-on, Links):
   → Ersatz: var(--g-accent)    /* #c45a2a — Burnt Orange */
   Begründung: Aktivierungszustand = Marken-Akzent.
```

### Ersetzungsregeln

```diff
# --g-primary → --g-ink (Buttons)
- background: var(--g-primary, #2563eb);
- border-color: var(--g-primary, #2563eb);
+ background: var(--g-ink);
+ border-color: var(--g-ink);

# --g-primary → --g-accent (Active/Selected)
- border-color: var(--g-primary, #2563eb);
- box-shadow: 0 0 0 1px var(--g-primary, #2563eb) inset;
+ border-color: var(--g-accent);
+ box-shadow: 0 0 0 1px var(--g-accent) inset;

# --g-border → --g-ink-faint (alle Borders)
- border: 1px solid var(--g-border, #e5e7eb);
+ border: 1px solid var(--g-ink-faint);

# Fallbacks bei definierten Token entfernen
- color: var(--g-ink-muted, #6b7280);
+ color: var(--g-ink-muted);

- color: var(--g-accent, #2563eb);   /* Kritisch: falsches Blau! */
+ color: var(--g-accent);
```

### Umsetzungsreihenfolge

1. `--g-primary` Buttons (4 Dateien) — höchste Sichtbarkeit
2. `--g-primary` Active/Selected/Link (3 Dateien)
3. `--g-border` (19 Dateien) — mechanische Suchen-Ersetzen
4. Falsche `--g-accent` Fallbacks (3 Dateien) — Kritisch
5. Unnötige `--g-ink-*` und `--g-surface-2` Fallbacks (restliche Dateien)

## Expected Behavior

- **Input:** Svelte-Komponenten mit CSS-Blöcken, die `--g-primary`, `--g-border` oder Hex-Fallbacks bei definierten Token nutzen
- **Output:** Dieselben Komponenten mit korrekten Token, ohne Fallback-Argumente
- **Side effects:** Sichtbare Farbänderung — Buttons werden schwarz/Ink statt blau; ModeCard-Auswahl und Toggle-Active werden Burnt Orange statt blau; Borders werden Ink-Faint (#9c9a90) statt Neutral-Grau (#e5e7eb)

## Acceptance Criteria

- **AC-1:** Given der Quelltext in `frontend/src/` / When `rg "var\(--g-primary"` ausgeführt wird / Then ist die Trefferanzahl 0
  - Test: (populated after /tdd-red)

- **AC-2:** Given der Quelltext in `frontend/src/` / When `rg "var\(--g-border"` ausgeführt wird / Then ist die Trefferanzahl 0
  - Test: (populated after /tdd-red)

- **AC-3:** Given der Quelltext in `frontend/src/lib/` / When `rg "#2563eb|#e5e7eb|#6b7280|#f3f4f6"` ausgeführt wird / Then ist die Trefferanzahl 0 (keine hartcodierten Design-Hex-Werte in Komponenten-CSS)
  - Test: (populated after /tdd-red)

- **AC-4:** Given der AlertRulesEditor im Browser / When die Seite geladen wird / Then erscheint der Speichern-Button schwarz (#1a1a18, `--g-ink`) und nicht blau (#2563eb)
  - Test: (populated after /tdd-red)

- **AC-5:** Given eine selektierte ModeCard im AlertRulesEditor / When der Selektions-Rahmen betrachtet wird / Then ist die Rahmenfarbe Burnt Orange (#c45a2a, `--g-accent`) und nicht blau (#2563eb)
  - Test: (populated after /tdd-red)

- **AC-6:** Given das Frontend nach dem Build / When `npm run build` ausgeführt wird / Then gibt es 0 Build-Fehler
  - Test: (populated after /tdd-red)

## Known Limitations

- AC-4 und AC-5 sind visuelle Verifikationen ohne automatisierten Test — manuelle Sichtprüfung oder Playwright-Screenshot nötig
- `SavePresetDialog.svelte` und `WeatherMetricsTab.svelte` nutzen bereits `var(--g-accent, #c45a2a)` für Save-Buttons (Fallback korrekt aber redundant) — nur Fallback-Argument entfernen, Token nicht ändern

## Changelog

- 2026-05-20: Implementation completed — 26 Svelte-Komponenten aktualisiert:
  - `--g-primary` → `--g-ink` (4 Button-Dateien) oder `--g-accent` (3 Active/Selected-Dateien)
  - `--g-border` → `--g-ink-faint` (19 Dateien)
  - Falsche/unnötige Hex-Fallbacks entfernt (13 Dateien)
  - Status: VERIFIED
- 2026-05-20: Initial spec created (Issue #277)
