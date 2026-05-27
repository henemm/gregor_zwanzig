# Context: Issue #415 — Mobile Metriken: Akkordeon + Toggle-Controls + fixierter Footer

## Request Summary
Der Wetter-Metriken-Tab zeigt auf Mobile nur eine vertikale Preset-Button-Liste ohne Metriken-Konfiguration. Laut SOLL-Audit (Finding B-10) fehlen: Akkordeon pro Kategorie, iOS-artige Toggles pro Metrik, horizontale Preset-Pills mit Zähler und ein fixierter Footer mit "Reset" + "N übernehmen".

## SOLL vs. IST

**SOLL** (`claude-code-handoff/soll-audit-2026-05-27/soll-screenshots/mobile-m-metrics.png`):
- Full-Screen-Overlay ohne Bottom-Nav
- Mini-Header: Back-Pfeil + Breadcrumb "KHW 4D3 · BRIEFING-SPALTEN" + "Abbrechen" button
- "PRESET WÄHLEN" Eyebrow + horizontale scrollbare Preset-Pills mit Zähler
- Aktiver Preset: Name + "N von 26 Metriken aktiv" + "Als eigen sp." Button
- Akkordeon-Gruppen: "Temperatur / 2 von 5 aktiv" + Chevron (aufklappbar)
- Innere Toggle-Zeilen: Metrik-Name + Einheit + iOS-Toggle (on/off)
- Fixierter Footer: "Reset" (Ghost) + "N übernehmen" (Primary schwarz)

**IST** (`claude-code-handoff/soll-audit-2026-05-27/ist-screenshots/mobile-m-metrics.png`):
- Normaler Trip-Detail-Kontext mit Bottom-Nav sichtbar
- Erklärungs-Text + "Speichern"-Button + vertikale Preset-Button-Liste
- Kein Akkordeon, keine Toggles, kein fixierter Footer

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Haupt-Container — Split Desktop/Mobile hier |
| `frontend/src/lib/components/trip-detail/MetricGroup.svelte` | Kategorie-Gruppe (Desktop) — Muster für Mobile-Akkordeon |
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` | Desktop Metrik-Zeile (komplex mit Buckets/HorizonChips) |
| `frontend/src/lib/components/trip-detail/PresetRow.svelte` | Desktop Preset-Zeile (vertikal) — auf Mobile zu Pill |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | `autoAssign()`, `CATEGORY_LABELS`, `CATEGORY_ORDER` — für Mobile-→-Desktop-Übersetzung |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Rendert WeatherMetricsTab — kein Change nötig |
| `frontend/src/routes/trips/[id]/+page.svelte` | Trip-Detail-Seite — kein Change nötig |
| `frontend/src/routes/+layout.svelte` | Globales Layout — rendert BottomNav (wird durch z-index-Overlay überdeckt) |
| `frontend/src/lib/components/ui/btn/index.js` | Btn-Atom |
| `frontend/src/lib/components/ui/eyebrow/index.js` | Eyebrow-Atom |
| `frontend/src/lib/components/ui/pill/index.js` | Pill-Atom |

## Existing Patterns

- **MetricGroup.svelte**: Zeigt Kategorie-Header mit Zähler — als Akkordeon auf Mobile erweitern
- **autoAssign()** in `metricsEditor.ts`: Übersetzt `string[]` aktiver IDs zu `Buckets` — für "übernehmen"-Logik
- **CATEGORY_LABELS / CATEGORY_ORDER**: `{temperature: 'Temperatur', wind: 'Wind', precipitation: 'Niederschlag', atmosphere: 'Atmosphäre', winter: 'Winter / Schnee'}`, Reihenfolge fest
- **Fixierter Footer**: Pattern existiert noch nicht in Trip-Detail-Tabs. Wizard-Screens haben ähnliches (in `TripWizardShell.svelte`)
- **Bottom-Nav überlagern**: `position: fixed; inset: 0; z-index: 150` überlagert Bottom-Nav (z-index 100)
- **Templates-API**: `GET /api/templates` → `[{id: str, label: str, metrics: [metric_id]}]` (3 Standard-Presets)
- **Catalog-API**: `GET /api/metrics` → `{category: [{id, label, unit, category, default_enabled, has_friendly_format}]}`

## Mobile-spezifisches Datenmodell

Das Mobile-View vereinfacht auf **enabledMap** (`{metric_id: boolean}`) ohne Bucket-Zuweisung:
- Beim Öffnen: aus `buckets.primary + buckets.secondary` → `enabled: true`, `buckets.off` → `enabled: false`
- "Übernehmen": `enabledMap` → aktive IDs → `autoAssign()` → neue `Buckets` → Desktop-State aktualisieren
- "Reset": `enabledMap` aus `savedSnapshot` wiederherstellen
- "Als eigen sp.": Öffnet `SavePresetDialog` (kann aus Mobile-View heraus aufgerufen werden)

## Zähler im Mobile-View
- Pro Kategorie: `activeCount / totalCount` aus enabledMap
- Footer "N übernehmen": N = Summe aller `enabled: true` im enabledMap
- Preset-Pill: Metrik-Zähler aus `template.metrics.length` / `userPreset.metrics.length`

## Dependencies

- **Upstream**: `WeatherMetricsTab` lädt Catalog + Templates + Presets via API und übergibt State
- **Downstream**: Mobile-View gibt durch `onApply({enabledMap, selectedPresetId})` zurück; Tab-Komponente macht daraus Buckets via `autoAssign()` + triggert Save
- **Kein Backend-Change**: Reine Frontend-Komponente

## Implementierungs-Ansatz

1. **Neue Komponente `WeatherMetricsMobileView.svelte`** — full-screen overlay (`position: fixed; inset: 0; z-index: 150; background: var(--g-paper)`)
   - Props: `trip, catalog, templates, userPresets, initialEnabledMap, initialSelectedPreset, activeCountTotal, onApply, onCancel`
   - Lokaler State: `enabledMap`, `selectedPresetId`, `openGroups` (Set mit aufgeklappten Kategorien)
   - Sections: Mini-Header | Preset-Pills | Preset-Info | Akkordeon-Gruppen | Fixierter Footer

2. **`WeatherMetricsTab.svelte` anpassen**:
   - Mobil-State: `showMobileView = $state(false)` — auf Mobile öffnet sich das Overlay
   - Mobile-Trigger: Button oder Tab-Selektion auf Mobile → `showMobileView = true`
   - Wenn `showMobileView`: rendert `WeatherMetricsMobileView` mit aktuellen Daten
   - `onApply`: `buckets = autoAssign(activeIds, catalog)`, `selectedTemplate = id`, optional direkt `handleSave()` aufrufen

3. **CSS für iOS-Toggle** — neues `<input type="checkbox" class="metric-toggle">` mit CSS-Styling
   - Kein neues Atom erforderlich — inline-Styling in `WeatherMetricsMobileView.svelte`

## Risiken

1. **Mobile-Trigger**: Wann öffnet sich das Mobile-Overlay? Optionen:
   - A) Sofort wenn Tab ausgewählt und Viewport ≤ 899px (kein zusätzlicher Klick)
   - B) Auf einem "Bearbeiten"-Button innerhalb des Tabs
   - SOLL zeigt keine Zwischenstufe → Option A (sofortiges Overlay bei Tab-Selektion auf Mobile)

2. **SavePresetDialog auf Mobile**: Falls User "Als eigen sp." tippt, öffnet sich der Dialog. Kein Problem — der Dialog ist bereits `position: fixed`.

3. **Dirty-State-Warnung**: Der Desktop hat eine "Ungespeicherte Änderungen"-Pill. Mobile-View sollte bei "Abbrechen" warnen wenn dirty (oder einfach verwerfen ohne Warnung — SOLL-Screenshot zeigt keine Warnung).

4. **Akkordeon-Default**: Welche Kategorien sind beim Öffnen aufgeklappt? SOLL zeigt "Temperatur" offen, Rest zu. → Default: erste Kategorie aufgeklappt.
