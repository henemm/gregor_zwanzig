# Context: Issue #392 — organisms.jsx ↔ #331/#364-Editor abgleichen

## Request Summary
Claude Design Session #16 hat `organisms.jsx` im Design-Sandbox mit den Production-Werten aus `metricsEditor.ts` abgeglichen (25 Metriken, korrekte IDs, Channel-Budgets). Jetzt soll die relevante Produkt-Implementierung erfolgen: Code-Duplikation entfernen und die `/metrics-editor`-Design-Screen auf die Organism-API migrieren.

## Was Claude Design getan hat (Session #16)
1. `organisms.jsx` neu kalibriert: 25 Metriken (war 15), Production-IDs (snake_case statt camelCase), `PRIMARY_SLOTS=5` (war 6), `CHANNEL_BUDGET email∞/telegram7/signal5/sms0` (war telegram8/signal6)
2. Neue Komponente `MetricCheckbox` (simple Tap-Row, kein HorizonChip-Ballast) für MetricOffShelf/Quick-Selector
3. Kanonische Namen: `WeatherMetricsTab`, `MetricGroup`, `ChannelPreviewBlock` (Legacy-Aliase behalten)
4. `docs/atomic-design-inventory.md` aktualisiert (Drift-Tabelle, ARCHIV-Eintrag)

## Befund: Produktion-Duplikate

| Symbol | Definition in metricsEditor.ts | Nochmal inline in |
|--------|-------------------------------|-------------------|
| `CATEGORY_LABELS` | ❌ FEHLT | `WeatherMetricsTab.svelte:35-41`, `WeatherConfigDialog.svelte:32-40` |
| `CATEGORY_ORDER` | ✅ `export const CATEGORY_ORDER` (Zeile 47) | `WeatherMetricsTab.svelte:42`, `WeatherConfigDialog.svelte:40` |
| `INDICATOR_MAP` | ✅ `export const INDICATOR_MAP` (Zeile 29) | `WeatherMetricsTab.svelte:45-58` |
| `indicatorCapable` | ✅ `export function indicatorCapable` (Zeile 59) | `WeatherMetricsTab.svelte:59-61` |

**Hauptproblem:** `CATEGORY_LABELS` fehlt ganz in `metricsEditor.ts` — muss dort hinzugefügt und exported werden. Dann können beide Svelte-Dateien importieren statt inline zu definieren.

**Kleindrift:** `winter`-Label divergiert: Design `"Winter"` vs. Produktion `"Winter / Schnee"` → Produktion gewinnt.

## Related Files
| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | Kanonische Quelle — `CATEGORY_LABELS` fehlt hier |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Definiert 4 Symbole inline statt zu importieren |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Definiert `CATEGORY_LABELS` + `CATEGORY_ORDER` inline |
| `frontend/src/lib/components/trip-detail/BucketSectionOff.svelte` | Empfängt `categoryLabels` als Prop (korrekt), kein Inline |
| `frontend/src/lib/components/trip-detail/MetricGroup.svelte` | Empfängt `categoryLabels` als Prop (korrekt) |
| `/tmp/design_392/gregor-zwanzig/project/organisms.jsx` | Design-Quelle (zur Referenz; kein Prod-File) |

## Scope (Minimal-Implementierung)

**Schritt 1 — `metricsEditor.ts` erweitern:**
- `CATEGORY_LABELS` als `export const` hinzufügen (direkt nach `CATEGORY_ORDER`)
- Wert: `{ temperature: 'Temperatur', wind: 'Wind', precipitation: 'Niederschlag', atmosphere: 'Atmosphäre', winter: 'Winter / Schnee' }` (Produktion-Label, nicht Design-Label "Winter")

**Schritt 2 — `WeatherMetricsTab.svelte` bereinigen:**
- `CATEGORY_LABELS`, `CATEGORY_ORDER`, `INDICATOR_MAP`, `indicatorCapable` aus Inline-Definitionen entfernen
- Stattdessen aus `metricsEditor.ts` importieren

**Schritt 3 — `WeatherConfigDialog.svelte` bereinigen:**
- `CATEGORY_LABELS`, `CATEGORY_ORDER` Inline-Definitionen entfernen
- Stattdessen aus `metricsEditor.ts` importieren

## Out of Scope
- `MetricCheckbox` (simple Version für Quick-Selector) — kein aktueller Konsument, Folge-Issue
- `PRESETS` — von API geladen, kein Static-Fallback in Produktion nötig
- `METRIC_CATALOG` static — Produktion lädt via `/api/metrics`, kein Hardcode
- Design-Sandbox `screen-metrics-editor.jsx` Migration — pure Design-Arbeit

## Dependencies
- `metricsEditor.ts` exportiert: `INDICATOR_MAP` ✅, `CATEGORY_ORDER` ✅, `indicatorCapable` ✅ → wird durch CATEGORY_LABELS-Export ergänzt
- `WeatherMetricsTab.svelte` und `WeatherConfigDialog.svelte` importieren bereits aus `metricsEditor.ts` (je 1+ Imports vorhanden)

## Risks & Considerations
- **Regression-Risiko niedrig**: rein additiver Export in metricsEditor.ts + Import-Umstellung in 2 Dateien. Keine Logik-Änderung.
- **winter-Label**: Produktion sagt "Winter / Schnee", Design sagt "Winter". Produktion gewinnt — NICHT auf Design-Wert angleichen.
- **Test-Coverage**: `metricsEditor.test.ts` testet keine Labels → kein Test-Update nötig. Svelte-Component-Tests nicht vorhanden.
