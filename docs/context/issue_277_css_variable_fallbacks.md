# Context: Fix dangling CSS variable fallbacks (#277)

## Request Summary

Mehrere Svelte-Komponenten referenzieren CSS-Variablen (`--g-primary`, `--g-border`), die in `app.css` **nicht existieren**. Die Fallback-Hex-Codes zeigen System-Blau (#2563eb) und Neutral-Grau (#e5e7eb) statt der Markenfarben (Burnt Orange #c45a2a, Ink-basierte Ränder). Zusätzlich haben korrekte Token wie `--g-ink-muted`, `--g-ink-faint`, `--g-accent` und `--g-surface-2` obsolete Hex-Fallbacks, die künftige Bugs verbergen würden.

## Token-Mapping

| Verwendet im Code | Status | Korrekter Token |
|---|---|---|
| `--g-primary` | ❌ undefiniert | `--g-accent` (Selected/Active-State) oder `--g-ink` (Primary-Button-Hintergrund) |
| `--g-border` | ❌ undefiniert | `--g-ink-faint` |
| `--g-ink-muted` | ✅ definiert, aber Fallback #6b7280 unnötig | Fallback entfernen |
| `--g-ink-faint` | ✅ definiert, aber Fallback #6b7280 unnötig | Fallback entfernen |
| `--g-surface-2` | ✅ definiert, aber Fallback #f3f4f6 unnötig | Fallback entfernen |
| `--g-accent` | ✅ definiert, aber Fallback #2563eb ist falsch | Fallback entfernen (war System-Blau, nicht Burnt Orange!) |

## Semantische Unterscheidung für --g-primary

- **Selected / Active State** (ModeCard.selected, Focus-Ring): `--g-accent` (Burnt Orange #c45a2a)
- **Primary-Action-Button** (`.btn-primary`, Speichern-Button): `--g-ink` (Ink #1a1a18 — schwarz/Tinte auf Papier, kein Blau)

## Betroffene Dateien — --g-primary (13 Vorkommen)

| Datei | Zeilen | Kontext |
|---|---|---|
| `src/lib/components/briefings-tab/BriefingsTab.svelte` | 77–78 | Button border + background |
| `src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | 292, 294 | `.btn-primary` |
| `src/lib/components/alert-rules-editor/ModeCard.svelte` | 91, 93 | `.mode-card.selected` |
| `src/lib/components/trip-detail/AlertsPreviewCard.svelte` | 76 | Link-Farbe |
| `src/lib/components/alerts-tab/AlertsTab.svelte` | 111–112 | Button border + background |
| `src/lib/components/alerts-tab/AlertPreviewCard.svelte` | 102–103 | Button border + background |
| `src/lib/components/alerts-tab/AlertMetricRow.svelte` | 117, 119 | Toggle-Button |

## Betroffene Dateien — --g-border (29 Vorkommen)

| Datei | Vorkommen |
|---|---|
| `src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | 1 |
| `src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | 5 |
| `src/lib/components/alert-rules-editor/ModeCard.svelte` | 1 |
| `src/lib/components/trip-detail/MetricCheckbox.svelte` | 1 |
| `src/lib/components/alerts-tab/AlertCooldownCard.svelte` | 2 |
| `src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | 2 |
| `src/lib/components/alerts-tab/AlertPreviewCard.svelte` | 1 |
| `src/lib/components/alerts-tab/AlertMetricRow.svelte` | 4 |
| `src/lib/components/alerts-tab/AlertMetricTable.svelte` | 1 |
| `src/lib/components/trip-detail/StageDetailRow.svelte` | 1 |
| `src/lib/components/trip-detail/PreviewCard.svelte` | 1 |
| `src/lib/components/trip-detail/TablePreview.svelte` | 2 |
| `src/lib/components/trip-detail/WeatherMetricsTab.svelte` | 2 |
| `src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | 1 |
| `src/lib/components/trip-detail/BriefingPreviewCard.svelte` | 1 |
| `src/lib/components/trip-detail/AlertsPreviewCard.svelte` | 1 |
| `src/lib/components/trip-detail/PresetRow.svelte` | 2 |
| `src/lib/components/trip-detail/TripTabs.svelte` | 1 |
| `src/lib/components/trip-detail/SavePresetDialog.svelte` | 2 |

## Betroffene Dateien — unnötige Fallbacks bei definierten Token

Zusätzlich: Dateien mit `var(--g-ink-muted, #6b7280)`, `var(--g-ink-faint, #6b7280)`, `var(--g-surface-2, #f3f4f6)`, `var(--g-accent, #2563eb)` — Fallbacks entfernen.

Kritisch: `var(--g-accent, #2563eb)` liefert falschen Fallback (#2563eb = Blau statt Burnt Orange).
Dateien: `BriefingPreviewCard.svelte:103`, `WeatherMetricsPreviewCard.svelte:80`, `PreviewCard.svelte:66`

## Definierte Token in app.css

```css
--g-accent:       #c45a2a;   /* Burnt Orange */
--g-paper:        #f6f4ee;
--g-ink:          #1a1a18;
--g-surface-0:    #f6f4ee;
--g-surface-1:    #edeae1;
--g-surface-2:    #e3dfd4;
--g-ink-muted:    #5c5a52;
--g-ink-faint:    #9c9a90;
--g-ink-strong:   var(--g-ink);
--g-surface-raised: var(--g-surface-1);
```

## Abhängigkeiten

- **Upstream:** `frontend/src/app.css` (Token-Definitionen) — keine Änderung nötig
- **Downstream:** Alle betroffenen Svelte-Komponenten

## Acceptance Criteria (aus Issue)

- `rg "var\(--g-primary" src` → 0 Treffer
- `rg "var\(--g-border" src` → 0 Treffer
- `rg "#2563eb|#e5e7eb|#6b7280|#f3f4f6" src` → 0 Treffer in Komponenten-CSS
- AlertRulesEditor: Speichern-Button ist schwarz/Ink (nicht blau)
- AlertRulesEditor: Selektierte ModeCard-Umrandung ist Burnt Orange (nicht blau)
- Keine Build-Fehler
- Bestehende Tests bestehen

## Risiken

- `--g-primary` hat kontext-abhängige Semantik (Selected vs. Button) → manuell pro Stelle prüfen
- `--g-accent` hatte bisher falschen Fallback #2563eb — visuell jetzt korrekt, aber möglicher Kontrastunterschied
- Breite Änderung (20+ Dateien) — Frontend-Build und visuelle Prüfung zwingend
