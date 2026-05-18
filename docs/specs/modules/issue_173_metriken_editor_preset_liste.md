---
entity_id: issue_173_metriken_editor_preset_liste
type: module
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
issue: 173
tags: [frontend, sveltekit, weather-config, trip-detail, metrics, presets, epic-138, ui-component, issue-173]
---

# Issue #173 — Metriken-Editor: Preset-Liste

## Approval

- [ ] Approved

## Purpose

`WeatherMetricsTab` bietet bislang nur ein Dropdown-Feld zur Preset-Auswahl — eine UX, die die verfügbaren Presets nicht kommuniziert und dem User keine Orientierung über Name, Metriken-Anzahl oder aktiv angewendetes Preset gibt. Dieses Issue führt eine neue `PresetRow`-Komponente ein, die alle 7 Standard-Presets als klickbare Zeilen mit Name, Metrik-Anzahl und builtin-Badge darstellt, das bisher aktive Preset visuell hervorhebt und das Template-Dropdown vollständig ersetzt.

## Source

- **NEU:** `frontend/src/lib/components/trip-detail/PresetRow.svelte`
  — Eigenständige Svelte-Komponente, dargestellt als klickbare Zeile pro Preset
- **MODIFY:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
  — Template-Dropdown entfernen, `<section class="presets-section">` mit PresetRow-Loop einbauen
- **NEU:** `frontend/src/lib/components/trip-detail/PresetRow.test.ts`
  — Unit-Tests für PresetRow-Rendering und Interaktivität
- **MODIFY:** `frontend/e2e/epic-138-metriken-editor.spec.ts`
  — E2E-Tests für PresetRow-Liste und Klick-Interaktion

> Alle Änderungen liegen ausschließlich in der Frontend-Schicht (`frontend/src/`). Kein Backend-Code wird verändert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/templates` | Go-API-Endpunkt (Proxy) | Liefert die 7 Standard-Presets mit `{id, label, metrics[]}` — Datenquelle für PresetRow-Liste |
| `trip.display_config.preset_name` | Trip-Feld (Frontend-State) | Bestimmt das aktiv hervorgehobene Preset; wird von `WeatherMetricsTab` als `selectedTemplate` verwaltet (Issue #206, bereits implementiert) |
| `WeatherMetricsTab.svelte` | Svelte-Komponente | Parent-Container; hält `templates`, `selectedTemplate` und `enabledMap` als Rune-State; bindet `onSelect`-Callback |
| `selectedTemplate` / `$effect` | Svelte-Rune-State in `WeatherMetricsTab` | Reagiert auf Template-Wechsel und aktualisiert `enabledMap` — PresetRow schreibt in diese Variable via `onSelect` |
| Design-System-Tokens | CSS-Variablen | `var(--g-accent)`, `var(--g-border)`, `var(--g-surface)`, `var(--g-ink-faint)` — Pflicht für konsistentes Styling (siehe `docs/reference/design_system.md`) |

## Implementation Details

### 1. `PresetRow.svelte` — Neue Komponente (~70 LoC)

Props-Interface:

```typescript
interface Props {
    id: string;           // Template-Key, z.B. "wandern"
    label: string;        // Lesbarer Name, z.B. "Wandern"
    metricCount: number;  // Länge des metrics-Arrays
    isActive: boolean;    // true wenn selectedTemplate === id
    onSelect: (id: string) => void;  // Callback an WeatherMetricsTab
}
let { id, label, metricCount, isActive, onSelect }: Props = $props();
```

Markup:

```svelte
<div
    class="preset-row"
    class:active={isActive}
    role="button"
    tabindex="0"
    data-testid="weather-metrics-preset-row-{id}"
    onclick={() => onSelect(id)}
    onkeydown={(e) => e.key === 'Enter' && onSelect(id)}
>
    <span class="badge" data-testid="weather-metrics-preset-row-{id}-badge">builtin</span>
    <span class="name" data-testid="weather-metrics-preset-row-{id}-name">{label}</span>
    <span class="count" data-testid="weather-metrics-preset-row-{id}-count">{metricCount} Metriken</span>
    {#if isActive}
        <span class="active-marker" data-testid="weather-metrics-preset-row-{id}-active">✓</span>
    {/if}
</div>
```

Styling (CSS-Custom-Properties des Design-Systems):

```css
.preset-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 1rem;
    border: 1px solid var(--g-border);
    border-radius: 4px;
    cursor: pointer;
    background: var(--g-surface);
}
.preset-row.active {
    border-color: var(--g-accent);
    background-color: color-mix(in srgb, var(--g-accent) 8%, var(--g-surface));
}
.badge {
    font-size: 0.75rem;
    padding: 0.1rem 0.4rem;
    border: 1px solid var(--g-border);
    border-radius: 3px;
    color: var(--g-ink-faint);
    flex-shrink: 0;
}
.name {
    flex: 1;
    font-weight: 500;
}
.count {
    font-size: 0.875rem;
    color: var(--g-ink-faint);
    flex-shrink: 0;
}
.active-marker {
    color: var(--g-accent);
    font-weight: 600;
    flex-shrink: 0;
}
```

### 2. `WeatherMetricsTab.svelte` — Integration (~25 LoC Änderung)

**Entfernen** (Template-Dropdown, Zeilen ~161–176):

```svelte
<!-- ENTFERNT: -->
{#if templates.length > 0}
    <div class="template-row">
        <label for="metrics-tpl-sel" class="template-label">Template</label>
        <select id="metrics-tpl-sel" data-testid="weather-metrics-tab-template" ...>
            ...
        </select>
    </div>
{/if}
```

**Ersetzen durch** PresetRow-Sektion, einzufügen oberhalb von `.categories`:

```svelte
<script lang="ts">
    import PresetRow from './PresetRow.svelte';
</script>

{#if templates.length > 0}
    <section class="presets-section" data-testid="weather-metrics-preset-list">
        {#each templates as t}
            <PresetRow
                id={t.id}
                label={t.label}
                metricCount={t.metrics.length}
                isActive={selectedTemplate === t.id}
                onSelect={(id) => { selectedTemplate = id; }}
            />
        {/each}
    </section>
{/if}
```

Styling für den Container:

```css
.presets-section {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-bottom: 1.25rem;
}
```

Der bestehende `$effect`, der auf `selectedTemplate`-Änderungen reagiert und `enabledMap` aktualisiert, bleibt unverändert — er wird durch den `onSelect`-Callback wie bisher getriggert.

### 3. `PresetRow.test.ts` — Unit-Tests (~60 LoC)

Zu testende Fälle (kein Mocking):
- PresetRow rendert mit `label`, `metricCount` und Badge-Text korrekt
- `class:active` ist gesetzt, wenn `isActive === true`
- `class:active` fehlt, wenn `isActive === false`
- `active-marker`-Element ist nur sichtbar, wenn `isActive === true`
- `onSelect`-Callback wird mit der korrekten `id` aufgerufen, wenn die Row geklickt wird
- Keyboard-Interaktion: Enter-Taste triggert `onSelect`

### 4. `epic-138-metriken-editor.spec.ts` — E2E-Erweiterung (~80 LoC)

Neue Testfälle in Playwright:
- Preset-Liste wird gerendert mit genau 7 Rows (`data-testid="weather-metrics-preset-list"`)
- Jede Row zeigt Name, Metrik-Anzahl und builtin-Badge
- Klick auf Row `wandern` setzt das Preset, Metriken-Checkboxen aktualisieren sich auf 9 aktive
- Active-Marker erscheint auf der geklickten Row nach Klick
- Template-Dropdown `data-testid="weather-metrics-tab-template"` existiert nicht mehr (prüft Entfernung)
- Kein Preset aktiv (frischer Load ohne `preset_name`): Alle Rows ohne active-Klasse

## Expected Behavior

- **Input:** `WeatherMetricsTab` lädt Templates von `/api/templates` (7 Objekte mit `{id, label, metrics[]}`). `selectedTemplate` enthält den aktiven Template-Key aus `trip.display_config.preset_name` (leer wenn kein Preset gesetzt).
- **Output:** Alle 7 Presets werden als klickbare PresetRow-Zeilen dargestellt. Das Preset mit `id === selectedTemplate` erhält `class:active`, alle anderen nicht. Klick auf eine Row ruft `onSelect(id)` auf, was `selectedTemplate` in `WeatherMetricsTab` schreibt und via `$effect` die `enabledMap` aktualisiert.
- **Side effects:** Das Template-Dropdown (`<select id="metrics-tpl-sel">`) wird entfernt — bestehende E2E-Tests, die `data-testid="weather-metrics-tab-template"` ansprechen, müssen auf `weather-metrics-preset-list` umgestellt werden.

## Acceptance Criteria

- **AC-1:** Given der WeatherMetricsTab ist geöffnet und `/api/templates` liefert 7 Presets
  When die Seite geladen wird
  Then werden alle 7 Presets als einzelne PresetRow-Zeilen im Container `data-testid="weather-metrics-preset-list"` angezeigt.
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine PresetRow wird gerendert
  When Name, Metrik-Anzahl und Badge inspiziert werden
  Then zeigt die Row den lesbaren Preset-Namen, die korrekte Zahl der Metriken (z.B. "9 Metriken") und den Text "builtin" als Badge.
  - Test: (populated after /tdd-red)

- **AC-3:** Given der User klickt auf die PresetRow "Wandern"
  When der Klick verarbeitet wird
  Then wird `selectedTemplate = "wandern"` gesetzt, der `$effect` aktualisiert `enabledMap` auf die 9 Wandern-Metriken, und die "Wandern"-Row erhält `class:active`.
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Trip hat `display_config.preset_name = "skitouren"` gespeichert
  When der WeatherMetricsTab initialisiert wird (`initMaps()` setzt `selectedTemplate = "skitouren"`)
  Then ist die "Skitouren"-PresetRow mit `class:active` hervorgehoben und alle anderen Rows sind ohne active-Klasse.
  - Test: (populated after /tdd-red)

- **AC-5:** Given das Template-Dropdown (`<select id="metrics-tpl-sel">`) war in WeatherMetricsTab vorhanden
  When der geänderte WeatherMetricsTab gerendert wird
  Then existiert kein Element mit `data-testid="weather-metrics-tab-template"` mehr im DOM.
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein Trip hat kein `preset_name` in `display_config` (frischer Trip oder Bestands-Trip ohne Preset)
  When der WeatherMetricsTab geöffnet wird
  Then ist keine PresetRow mit `class:active` hervorgehoben — alle 7 Rows sind gleichwertig dargestellt.
  - Test: (populated after /tdd-red)

## Out of Scope

- **Benutzerdefinierte Presets** (speichern, löschen, umbenennen) — Templates sind codebasiert; keine Admin-Oberfläche.
- **Beschreibungs-Text pro Preset** — Backend hat kein Description-Feld; MVP zeigt nur Name + Metrik-Anzahl.
- **Backend-Änderungen** — `/api/templates` liefert bereits die benötigten Daten; kein neues Feld.
- **rightColumn.ts `TEMPLATE_LABELS`-Cleanup** — Die redundante Map bleibt als Fallback erhalten; Konsolidierung ist separates Refactoring-Issue.

## Risiken & Implementierungshinweise

| Risiko | Auswirkung | Gegenmaßnahme |
|--------|------------|---------------|
| Bestehende E2E-Tests referenzieren `data-testid="weather-metrics-tab-template"` | Tests brechen nach Dropdown-Entfernung | Tests in `epic-138-metriken-editor.spec.ts` auf neue `data-testid`-Werte umstellen (Teil dieses Issues) |
| `color-mix()` CSS-Funktion nicht in allen Browsern verfügbar | Active-Hintergrund nicht sichtbar in alten Browsern | Fallback via `opacity` oder feste Farbe; Zielgruppe nutzt moderne Desktop-Browser (kein Mobile-Zwang) |
| `isActive`-Berechnung basiert auf `selectedTemplate`, nicht auf tatsächlichem Metriken-Vergleich | Manuelle Metrik-Änderung nach Preset-Auswahl zeigt Preset weiter als aktiv | Spec-Entscheidung: Active-Highlight ist Auswahl-Indikator, kein Metriken-Vergleich — konsistent mit Issue #206 |

## Files to Change

| # | Datei | Schicht | Aktion | LoC (netto) |
|---|-------|---------|--------|-------------|
| 1 | `frontend/src/lib/components/trip-detail/PresetRow.svelte` | Frontend | NEU — Komponente mit Props, Markup, CSS | ~70 |
| 2 | `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Frontend | MODIFY — Dropdown entfernen, PresetRow-Sektion einbauen | ~25 |
| 3 | `frontend/src/lib/components/trip-detail/PresetRow.test.ts` | Frontend/Test | NEU — Unit-Tests | ~60 |
| 4 | `frontend/e2e/epic-138-metriken-editor.spec.ts` | Frontend/Test | MODIFY — E2E-Tests ergänzen | ~80 |

**Gesamt:** ~235 LoC, 4 Dateien, kein Backend

## Known Limitations

- `isBuiltin` ist als Prop in der PresetRow-Interface vorbereitet, wird im MVP jedoch immer als `true` übergeben (alle 7 Templates sind Standard-Presets). Der Badge zeigt daher immer "builtin". Das Prop bleibt für spätere benutzerdefinierte Presets erhalten.
- Der Active-State basiert auf `selectedTemplate === id` — wird ein Preset ausgewählt und anschließend manuell eine Metrik-Checkbox geändert, bleibt das Preset optisch aktiv, obwohl die Metrik-Auswahl abweicht. Dieses Verhalten ist gewünscht (Auswahl-Indikator, kein Live-Vergleich).

## Changelog

- 2026-05-18: Initial spec für Issue #173 (Metriken-Editor: Preset-Liste). PresetRow als eigenständige Svelte-Komponente mit klickbarer Interaktion, Template-Dropdown-Entfernung, 6 Acceptance Criteria (AC-N-Format), Risiken und Out-of-Scope klar abgegrenzt.
