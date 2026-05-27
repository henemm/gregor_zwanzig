---
entity_id: issue_415_mobile_metrics_view
type: module
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [frontend, svelte, mobile, metrics, overlay, trip-detail, issue-415]
---

# Issue #415 — Mobile Wetter-Metriken-Tab: Full-Screen-Overlay

## Approval

- [ ] Approved

## Purpose

Erstellt die Komponente `WeatherMetricsMobileView.svelte`, die auf Viewports ≤ 899px als
Full-Screen-Overlay (z-Index 150) über dem regulären `WeatherMetricsTab` erscheint und dem
User eine touch-optimierte Oberfläche zum Konfigurieren von Briefing-Metriken bietet: Preset-Auswahl
per horizontaler Pill-Leiste, Kategorie-Akkordeon (Single-Open) mit iOS-Toggles pro Metrik und
einen fixierten Footer mit "Übernehmen"- und "Reset"-Aktionen.

Das Overlay ist nötig, weil der bestehende Bucket-Editor im `WeatherMetricsTab` für Desktop
(Drag-Drop, Roh/Indikator-Pills, HorizonChips) auf Mobile weder bedienbar noch lesbar ist — das
Overlay ersetzt ihn auf Small-Screens vollständig, ohne die Desktop-Ansicht zu verändern.

## Source

- **Files:**
  - `frontend/src/lib/components/trip-detail/WeatherMetricsMobileView.svelte` (NEU, ~225 LoC)
  - `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (EDIT, ~33 LoC Änderung)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/components/mobile/MSwitch.svelte` | Svelte-Komponente (vorhanden) | iOS-Toggle pro Metrik-Zeile (Props: `checked`, `onchange`) |
| `frontend/src/lib/components/mobile/MIcon.svelte` | Svelte-Komponente (vorhanden) | Chevron-Icons im Akkordeon-Header (`kind: 'chevron-down' \| 'chevron-up' \| 'back'`) |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Svelte-Komponente (vorhanden) | "Als eigen sp."-Dialog für eigene Preset-Benennung |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | TypeScript-Utility (vorhanden) | `autoAssign()`, `CATEGORY_ORDER`, `CATEGORY_LABELS`, `move()`, Typ `Buckets` |

## Scope

**Nur Frontend.** Kein Go-Backend-Endpoint geändert. Kein Python-Backend betroffen.

**Out of Scope (explizit ausgeschlossen):**
- HorizonChips auf Mobile — erscheinen nicht im Overlay
- Roh/Indikator-Toggle auf Mobile — erscheint nicht im Overlay
- Dirty-Warning-Dialog beim Preset-Wechsel auf Mobile — Mobile ruft `onSelectPreset` direkt auf
- Multi-Expand-Akkordeon — Single-Open (jeweils nur eine Kategorie offen)
- Änderungen am Desktop-Bucket-Editor in `WeatherMetricsTab`

## Implementation Details

### 1. `WeatherMetricsMobileView.svelte` (NEU, ~225 LoC)

**Props-Interface:**
```typescript
interface Props {
  trip: Trip;
  catalog: MetricCatalog;
  templates: Template[];          // { id, label, metrics: string[] }
  userPresets: MetricPreset[];
  buckets: Buckets;               // { primary: string[], secondary: string[], off: string[] }
  friendlyMap: Record<string, boolean>;
  metricById: Record<string, MetricEntry>;
  selectedTemplate: string;
  savedSnapshot: string;
  isDirty: boolean;
  saving: boolean;
  onToggleMetric: (id: string, active: boolean) => void;
  onSelectPreset: (id: string) => void;
  onSave: () => void;
  onDiscard: () => void;
  onClose: () => void;
  onOpenSavePresetDialog: () => void;
}
```

**Interner State:**
```typescript
let openCat = $state(CATEGORY_ORDER[0]); // Single-Open Akkordeon
```

**Abgeleitete Werte:**
```typescript
// enabledMap aus buckets ableiten — kein separater State
const enabledMap = $derived(
  Object.fromEntries(
    [...buckets.primary, ...buckets.secondary].map(id => [id, true])
  )
);

// Aktiver Preset-Count pro Kategorie
function activeCatCount(cat: string): number {
  return (catalog.categories[cat]?.metrics ?? [])
    .filter(id => enabledMap[id]).length;
}

// Gesamtzahl aktiver Metriken für Footer-Button
const totalActive = $derived(
  buckets.primary.length + buckets.secondary.length
);
```

**Overlay-Struktur (von oben nach unten):**

1. **Mini-Header (sticky):**
   - `<MIcon kind="back" />` — ruft `onClose()` auf
   - Breadcrumb: `"{trip.name} · BRIEFING-SPALTEN"` (uppercase via CSS)
   - "Abbrechen"-Button (`Btn variant="ghost"`) — ruft `onClose()` auf (keine Verwerfung)

2. **Preset-Strip (horizontal scrollable):**
   - Alle Templates + User-Presets als Pills
   - Aktive Pill: orange gefüllt (`data-active` + CSS auf `--g-accent`)
   - Inaktive Pills: Outline-Stil
   - Pill-Label: `"{preset.label} / {preset.metrics.length}"`
   - Click: `onSelectPreset(preset.id)` — kein Dirty-Check auf Mobile

3. **Preset-Info-Zeile:**
   - `"{selectedTemplateName} / {totalActive} von {totalMetrics} Metriken aktiv"`
   - "Als eigen sp."-Button (`Btn variant="ghost"`) — ruft `onOpenSavePresetDialog()` auf

4. **Scrollbarer Mittelteil (Akkordeon-Gruppen):**
   - Iteration über `CATEGORY_ORDER`
   - Akkordeon-Header: `"{CATEGORY_LABELS[cat]} / {activeCatCount(cat)} von {catTotal} aktiv"` + `<MIcon kind={openCat === cat ? 'chevron-up' : 'chevron-down'} />`
   - Klick auf Header: `openCat = (openCat === cat ? '' : cat)` (Toggle, Single-Open)
   - Erste Kategorie (`CATEGORY_ORDER[0]`) initial aufgeklappt
   - Aufgeklappter Inhalt: Zeile pro Metrik mit Label + Einheit + `<MSwitch checked={enabledMap[id]} onchange={(e) => onToggleMetric(id, e.target.checked)} />`
   - Keine HorizonChips, keine Roh/Indikator-Pills

5. **Fixierter Footer (sticky bottom):**
   - "Reset" (`Btn variant="ghost"`) — ruft `onDiscard()` + `onClose()` auf
   - "N übernehmen" (`Btn variant="primary"`, schwarz) — ruft `onSave()` + `onClose()` auf; N = `totalActive`
   - Padding-Bottom: `max(var(--g-s-3), env(safe-area-inset-bottom))`

**CSS-Overlay:**
```css
.mobile-overlay {
  position: fixed;
  inset: 0;
  z-index: 150; /* über BottomNav z-50, über TopAppBar z-60 */
  background: var(--g-paper);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.overlay-scroll {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.mobile-footer {
  padding: var(--g-s-3);
  padding-bottom: max(var(--g-s-3), env(safe-area-inset-bottom));
  display: flex;
  gap: var(--g-s-2);
  border-top: 1px solid var(--g-ink-faint);
  background: var(--g-paper);
}
```

Alle Spacing-Werte via `--g-s-*` Tokens, keine Magic-Pixel-Werte, keine Hex-Farbliterale.

### 2. Glue-Code in `WeatherMetricsTab.svelte` (EDIT, ~33 LoC)

**Neuer State:**
```typescript
let showMobileView = $state(false);
```

**`onToggleMetric`-Handler (wird auch an Overlay übergeben):**
```typescript
function onToggleMetric(id: string, active: boolean) {
  const from = buckets.primary.includes(id) ? 'primary'
             : buckets.secondary.includes(id) ? 'secondary' : 'off';
  const to = active ? 'secondary' : 'off';
  if (from !== to) buckets = move(buckets, id, from, to);
  if (selectedTemplate) selectedTemplate = '';
}
```

**Mobile-Trigger-Button (nur ≤899px sichtbar):**
```svelte
<button class="mobile-metrics-trigger" onclick={() => showMobileView = true}>
  Metriken konfigurieren ({buckets.primary.length + buckets.secondary.length} aktiv)
</button>
```

**Overlay-Mount (konditional):**
```svelte
{#if showMobileView}
  <WeatherMetricsMobileView
    {trip} {catalog} {templates} {userPresets}
    {buckets} {friendlyMap} {metricById}
    {selectedTemplate} {savedSnapshot} {isDirty} {saving}
    {onToggleMetric}
    onSelectPreset={handleSelectPreset}
    onSave={handleSave}
    onDiscard={handleDiscard}
    onClose={() => showMobileView = false}
    onOpenSavePresetDialog={() => savePresetDialogOpen = true}
  />
{/if}
```

**CSS für Mobile-Trigger (nur auf Mobile sichtbar):**
```css
.mobile-metrics-trigger {
  display: none;
}
@media (max-width: 899px) {
  .mobile-metrics-trigger {
    display: flex;
    /* Brand-Tokens: Pill-Styling mit --g-accent */
  }
}
```

## Expected Behavior

- **Input:** `trip`, `catalog`, `templates`, `userPresets`, `buckets`, `friendlyMap`,
  `metricById`, `selectedTemplate`, `savedSnapshot`, `isDirty`, `saving` — alle aus dem
  bestehenden `WeatherMetricsTab`-State; Callbacks als Props weitergereicht.
- **Output:**
  - Full-Screen-Overlay mit sticky Mini-Header, horizontal scrollbarer Preset-Leiste,
    Preset-Info-Zeile, Akkordeon-Mittelteil und fixiertem Footer
  - `totalActive` (aktive Metriken gesamt) reaktiv im Footer-Button angezeigt
  - Kategorie-Zähler im Akkordeon-Header reaktiv über `activeCatCount(cat)` berechnet
- **Side effects:**
  - `onToggleMetric(id, checked)` → delegiert an `move()` in `WeatherMetricsTab` → mutiert `buckets`
  - `onSelectPreset(id)` → delegiert an bestehenden Handler in `WeatherMetricsTab` (kein Dirty-Dialog)
  - `onSave()` → delegiert an `handleSave()` in `WeatherMetricsTab` → PUT /api/trips/{id}
  - `onDiscard()` → delegiert an `handleDiscard()` → stellt `savedSnapshot` wieder her
  - `onClose()` → setzt `showMobileView = false` im Tab → Overlay unmountet

## Acceptance Criteria

**AC-1:** Given der Wetter-Briefing-Tab ist aktiv auf Viewport ≤ 899px /
When der "Metriken konfigurieren (N aktiv)"-Button geklickt wird /
Then erscheint ein Full-Screen-Overlay (`position: fixed; inset: 0; z-index: 150`) das Bottom-Nav überlagert; das Overlay enthält: sticky Mini-Header (Back-Pfeil + Breadcrumb + Abbrechen-Button), horizontale Preset-Pill-Leiste, Preset-Info-Zeile, Akkordeon-Mittelteil und fixierten Footer mit "Reset"- und "N übernehmen"-Buttons.
  - Test: (populated after /tdd-red)

**AC-2:** Given das Overlay ist geöffnet /
When der User einen Kategorie-Header antippt /
Then klappt diese Kategorie auf (Toggle-Zeilen sichtbar) und die vorher offene Kategorie schließt sich (Single-Open-Modus); Chevron dreht entsprechend (`chevron-up` = offen, `chevron-down` = geschlossen).
  - Test: (populated after /tdd-red)

**AC-3:** Given eine Akkordeon-Kategorie ist aufgeklappt /
When der User einen MSwitch antippt /
Then togglet `checked` des Switches; `onToggleMetric(id, checked)` wird aufgerufen; Kategorie-Zähler "N von M aktiv" im Header aktualisiert sich reaktiv; "N übernehmen"-Button im Footer zeigt neuen Gesamtzähler.
  - Test: (populated after /tdd-red)

**AC-4:** Given das Overlay zeigt horizontale Preset-Pills /
When ein Pill angeklickt wird /
Then wird `onSelectPreset(id)` aufgerufen (ohne Dirty-Warning-Dialog); Toggles in allen Kategorien aktualisieren sich; der angeklickte Pill wird orange gefüllt (`data-active`); Zähler "N von M Metriken aktiv" in der Preset-Info-Zeile aktualisiert sich.
  - Test: (populated after /tdd-red)

**AC-5:** Given der Footer ist sichtbar /
When "N übernehmen" geklickt wird /
Then ruft `onSave()` auf und schließt das Overlay via `onClose()` (setzt `showMobileView = false`).
  - Test: (populated after /tdd-red)

**AC-5b:** Given der Footer ist sichtbar /
When "Reset" geklickt wird /
Then ruft `onDiscard()` auf (stellt `savedSnapshot` wieder her) und schließt das Overlay via `onClose()`.
  - Test: (populated after /tdd-red)

**AC-6:** Given das Overlay ist offen und Änderungen wurden gemacht /
When "Abbrechen" im Mini-Header geklickt wird /
Then schließt sich das Overlay via `onClose()` ohne `onSave()` oder `onDiscard()` aufzurufen; Änderungen bleiben im Tab-State von `WeatherMetricsTab` erhalten bis der User explizit "Reset" wählt.
  - Test: (populated after /tdd-red)

**AC-7:** Given das Gerät hat eine Notch/Home-Indicator-Leiste (iOS iPhone X+) /
When das Overlay geöffnet ist /
Then hat der fixierte Footer `padding-bottom: max(var(--g-s-3), env(safe-area-inset-bottom))` sodass Buttons nicht hinter dem Home-Indicator versteckt werden.
  - Test: (populated after /tdd-red)

**AC-8:** Given der Viewport ist > 899px /
When der Wetter-Briefing-Tab aktiv ist /
Then bleibt der Desktop-Bucket-Editor vollständig unverändert; der Mobile-Trigger-Button ist via CSS `display: none` versteckt; `showMobileView` kann nie `true` werden.
  - Test: (populated after /tdd-red)

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsMobileView.svelte` | NEU — Full-Screen-Overlay (~225 LoC) |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | EDIT — Mobile-Trigger + Overlay-Mount + `showMobileView`-State (~33 LoC) |

Nicht geändert (nur wiederverwendet):
- `frontend/src/lib/components/mobile/MSwitch.svelte`
- `frontend/src/lib/components/mobile/MIcon.svelte`
- `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte`
- `frontend/src/lib/components/trip-detail/metricsEditor.ts`

## LoC Estimate

~258 LoC gesamt: `WeatherMetricsMobileView` ~225, `WeatherMetricsTab`-Änderung ~33.
LoC-Override auf 300 setzen.

## Known Limitations

- Preset-Wechsel auf Mobile löst keinen Dirty-Warning-Dialog aus (der bestehende Dialog hat
  z-Index 100, wäre hinter dem Overlay z-150 unsichtbar). Das ist eine bewusste UX-Entscheidung
  für Mobile — direktes Apply ohne Bestätigung.
- Das Overlay hat keinen Keyboard-Escape-Handler; auf Desktop ist es via CSS nie sichtbar,
  daher kein a11y-Problem. Ein dediziertes Keyboard-Handling kann in einem Follow-up ergänzt
  werden falls das Overlay auch auf Tablet-Breakpoints erscheinen soll.

## Changelog

- 2026-05-27: Initial spec erstellt (Issue #415 — Mobile Wetter-Metriken Full-Screen-Overlay).
