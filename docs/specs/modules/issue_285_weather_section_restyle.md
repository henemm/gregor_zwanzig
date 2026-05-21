---
entity_id: issue_285_weather_section_restyle
type: module
created: 2026-05-21
updated: 2026-05-21
status: draft
version: "1.0"
tags: [frontend, design-system, edit-weather-section, weather-config-dialog, segmented-control, ui-restyle, css-tokens, svelte, issue-285]
---

# Issue #285 — EditWeatherSection + WeatherConfigDialog: Full Restyle against Brand Tokens

## Approval

- [ ] Approved

## Purpose

`EditWeatherSection.svelte` und `WeatherConfigDialog.svelte` verwenden im Roh/Indikator-Toggle noch Tailwind-Klassen (`bg-primary`, `text-primary-foreground`) statt der Brand-Token des Design-Systems. Dieses Modul entfernt alle verbleibenden Tailwind-Reste aus beiden Komponenten, führt eine neue wiederverwendbare `Segmented.svelte`-Komponente ein, die den Toggle als Single Segmented Control rendert, und bereinigt Kategorie-Überschriften sowie Zeilen-Hover-Styles in `EditWeatherSection` auf die etablierten CSS-Token-Muster.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code ist betroffen.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** 5 Dateien

### Betroffene Dateien

| Datei | Aktion |
|-------|--------|
| `frontend/src/lib/components/ui/segmented/Segmented.svelte` | Neu erstellen (~35 LoC) |
| `frontend/src/lib/components/ui/segmented/index.ts` | Neu erstellen (~1 LoC) |
| `frontend/src/app.css` | CSS-Block für `[data-slot="segmented"]` hinzufügen (~22 LoC) |
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | Roh/Indikator-Toggle, Kategorie-Überschriften, Row-Hover patchen (netto -6 LoC) |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Roh/Indikator-Toggle patchen (netto -8 LoC) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Datei (vorhanden) | Single Source of Truth für Design-Token; erhält neuen `[data-slot="segmented"]`-CSS-Block nach dem globalen Btn/Pill-Muster |
| `frontend/src/lib/components/ui/segmented/Segmented.svelte` | Svelte-Komponente (neu) | Rendert einen Segmented Control mit Options-Array; ersetzt den Tailwind-Toggle in EditWeatherSection und WeatherConfigDialog |
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | Svelte-Komponente (vorhanden) | Empfängt Segmented-Komponente statt Tailwind-Toggle; Kategorie-Überschriften und Row-Hover werden auf Token umgestellt |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Svelte-Komponente (vorhanden) | Empfängt Segmented-Komponente statt Tailwind-Toggle |

## Implementation Details

### 1. `app.css` — Segmented Control CSS-Block

Nach den bestehenden `[data-slot="pill"]`-Regeln einfügen (globales Muster wie Btn/Pill — für Wiederverwendung in ModeCard.svelte):

```css
[data-slot="segmented"] {
  display: inline-flex;
  border: 1px solid var(--g-ink-faint);
  border-radius: var(--g-radius-sm);
  overflow: hidden;
  font-family: var(--g-font-data);
  font-size: var(--g-text-xs);
}
[data-slot="segmented-item"] {
  padding: 3px 10px;
  background: transparent;
  color: var(--g-ink-muted);
  cursor: pointer;
  border: none;
  line-height: 1.4;
  transition: background 0.1s, color 0.1s;
}
[data-slot="segmented-item"]:not(:last-child) {
  border-right: 1px solid var(--g-ink-faint);
}
[data-slot="segmented-item"][data-active="true"] {
  background: var(--g-ink);
  color: var(--g-paper);
}
[data-slot="segmented-item"][data-active="false"]:hover {
  background: var(--g-surface-2);
}
```

### 2. `Segmented.svelte` — Neue Komponente

Datei `frontend/src/lib/components/ui/segmented/Segmented.svelte` neu erstellen:

```svelte
<script lang="ts">
  type Option = { value: string; label: string };

  let {
    options,
    selected,
    onselect
  }: {
    options: Option[];
    selected: string;
    onselect: (v: string) => void;
  } = $props();
</script>

<div data-slot="segmented">
  {#each options as opt}
    <button
      type="button"
      data-slot="segmented-item"
      data-active={opt.value === selected ? "true" : "false"}
      onclick={() => onselect(opt.value)}
    >{opt.label}</button>
  {/each}
</div>
```

### 3. `index.ts` — Re-Export

```typescript
export { default } from './Segmented.svelte';
```

### 4. `EditWeatherSection.svelte` — Drei Stellen patchen

**Import ergänzen:**

```svelte
import Segmented from '$lib/components/ui/segmented';
```

**Stelle 1 — Roh/Indikator-Toggle (Zeilen 210–222):**

Tailwind-Button-Gruppe entfernen und durch `<Segmented>` ersetzen:

```diff
- <div class="flex rounded-md overflow-hidden border border-border">
-   <button class={displayMode === 'raw' ? 'bg-primary text-primary-foreground ...' : '...'}
-     onclick={() => displayMode = 'raw'}>Roh</button>
-   <button class={displayMode === 'indicator' ? 'bg-primary text-primary-foreground ...' : '...'}
-     onclick={() => displayMode = 'indicator'}>Indikator</button>
- </div>
+ <Segmented
+   options={[{ value: 'raw', label: 'Roh' }, { value: 'indicator', label: 'Indikator' }]}
+   selected={displayMode}
+   onselect={(v) => (displayMode = v)}
+ />
```

**Stelle 2 — Kategorie-Überschriften (Zeile 198):**

Bestehenden Klassen-Eintrag ersetzen durch Scoped CSS:

```diff
- <h4 class="text-sm font-medium text-muted-foreground ...">
+ <h4 class="category-heading">
```

Scoped Style-Block ergänzen:

```css
.category-heading {
  color: var(--g-ink);
  font-size: var(--g-text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--g-ink-faint);
  padding-bottom: 4px;
  margin-bottom: 4px;
}
```

**Stelle 3 — Row-Hover (Zeile 201):**

```diff
- <div class="flex items-center gap-2 hover:bg-muted/50 rounded px-1 py-0.5">
+ <div class="metric-row">
```

Scoped Style-Block ergänzen:

```css
.metric-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 4px;
  min-height: 28px;
  border-radius: var(--g-radius-sm);
}
.metric-row:hover {
  background: var(--g-surface-2);
}
```

### 5. `WeatherConfigDialog.svelte` — Roh/Indikator-Toggle (Zeilen 207–218)

Dieselbe Tailwind-Button-Gruppe wie in EditWeatherSection durch `<Segmented>` ersetzen (identisches Interface):

```diff
- <div class="flex rounded-md overflow-hidden border border-border">
-   <button class={displayMode === 'raw' ? 'bg-primary text-primary-foreground ...' : '...'}
-     onclick={() => displayMode = 'raw'}>Roh</button>
-   <button class={displayMode === 'indicator' ? 'bg-primary text-primary-foreground ...' : '...'}
-     onclick={() => displayMode = 'indicator'}>Indikator</button>
- </div>
+ <Segmented
+   options={[{ value: 'raw', label: 'Roh' }, { value: 'indicator', label: 'Indikator' }]}
+   selected={displayMode}
+   onselect={(v) => (displayMode = v)}
+ />
```

Import analog zu EditWeatherSection ergänzen.

### Umsetzungsreihenfolge

1. `app.css` — Segmented-CSS-Block (keine Abhängigkeiten)
2. `Segmented.svelte` + `index.ts` — Neue Komponente (benötigt Schritt 1 für korrekte Darstellung)
3. `EditWeatherSection.svelte` — Toggle + Überschriften + Hover (benötigt Schritt 2)
4. `WeatherConfigDialog.svelte` — Toggle (benötigt Schritt 2)

### Kritische Nebenbedingungen

Die folgenden Testids MÜSSEN erhalten bleiben — sie werden in bestehenden Playwright-Tests referenziert:

- `data-testid="metric-checkbox-{id}"` — auf den Checkbox-Elementen in EditWeatherSection
- `data-testid="weather-template-select"` — auf dem Select-Element in EditWeatherSection
- `data-testid="edit-weather-section"` — auf dem Wurzel-Element von EditWeatherSection

Diese Testids werden durch die Änderungen nicht berührt, da sie auf Checkbox- und Select-Elementen liegen, die von Issue #284 bereits korrekt behandelt wurden.

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/app.css` | +22 | ja |
| `frontend/src/lib/components/ui/segmented/Segmented.svelte` | +35 | ja |
| `frontend/src/lib/components/ui/segmented/index.ts` | +1 | ja |
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | -6 netto | ja |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | -8 netto | ja |
| **Gesamt** | **~+44 netto** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Bestehender `displayMode`-State ('raw' | 'indicator') in EditWeatherSection und WeatherConfigDialog
- **Output (visuell):**
  - Roh/Indikator-Toggle rendert als Single Segmented Control: ein äußerer Border, zwei Zellen nebeneinander, getrennt durch eine Hairline
  - Aktives Segment: `--g-ink`-Hintergrund, `--g-paper`-Textfarbe
  - Inaktives Segment: transparenter Hintergrund, `--g-ink-muted`-Textfarbe
  - Inaktives Segment zeigt `--g-surface-2`-Hover
  - Kategorie-Überschriften in EditWeatherSection erscheinen in `--g-ink`-Farbe mit Hairline-Underline in `--g-ink-faint`
  - Metric-Rows haben `min-height: 28px` und zeigen `--g-surface-2` beim Hover statt `bg-muted/50`
  - Kein Tailwind-Klassen-Anteil (`bg-primary`, `text-primary-foreground`, `hover:bg-muted`, `border-border`) mehr in beiden Komponenten
- **Side effects:** Die Segmented-CSS-Regeln in `app.css` sind global verfügbar — `ModeCard.svelte` kann `Segmented.svelte` in einem späteren Issue ohne neue CSS-Arbeit einbinden

## Acceptance Criteria

**AC-1:** Given `EditWeatherSection.svelte` mit `displayMode = 'raw'` / When die Komponente gerendert wird / Then hat der Roh/Indikator-Toggle kein `bg-primary`- oder `text-primary-foreground`-Attribut im DOM; das aktive Segment hat `data-active="true"` und das inaktive Segment hat `data-active="false"` am `[data-slot="segmented-item"]`-Element.
  - Test: (populated after /tdd-red)

**AC-2:** Given `WeatherConfigDialog.svelte` mit `displayMode = 'indicator'` / When der Dialog gerendert wird / Then hat der Roh/Indikator-Toggle kein `bg-primary`- oder `text-primary-foreground`-Attribut im DOM; das "Indikator"-Segment hat `data-active="true"`, das "Roh"-Segment hat `data-active="false"`.
  - Test: (populated after /tdd-red)

**AC-3:** Given eine Metric-Row in `EditWeatherSection` / When die Zeile im DOM gerendert wird / Then hat die Zeile keine Tailwind-Klasse `hover:bg-muted` und stattdessen `min-height` von 28px; der Quelltext von `EditWeatherSection.svelte` enthält kein `hover:bg-muted`.
  - Test: `grep -c "hover:bg-muted" frontend/src/lib/components/edit/EditWeatherSection.svelte` → `0`

**AC-4:** Given der Quelltext von `EditWeatherSection.svelte` und `WeatherConfigDialog.svelte` / When beide Dateien auf `bg-primary` und `text-primary-foreground` geprüft werden / Then liefern beide `grep`-Aufrufe den Wert `0`.
  - Test: `grep -c "bg-primary\|text-primary-foreground" frontend/src/lib/components/edit/EditWeatherSection.svelte` → `0`; analog für WeatherConfigDialog.svelte

**AC-5:** Given die Testids in `EditWeatherSection.svelte` / When der Quelltext auf `data-testid="metric-checkbox-"`, `data-testid="weather-template-select"` und `data-testid="edit-weather-section"` geprüft wird / Then sind alle drei Testids noch vorhanden — die Änderungen haben sie nicht entfernt.
  - Test: `grep -c "metric-checkbox-\|weather-template-select\|edit-weather-section" frontend/src/lib/components/edit/EditWeatherSection.svelte` → `3`

**AC-6:** Given die neue `Segmented.svelte`-Komponente / When `onselect` mit einem neuen Wert aufgerufen wird (Klick auf inaktives Segment) / Then wechselt `data-active` am geklickten Item auf `"true"` und am vorherigen aktiven Item auf `"false"`, ohne dass die umgebende Komponente einen Reload benötigt.
  - Test: (populated after /tdd-red)

## Known Limitations

- Die `Segmented.svelte`-Komponente unterstützt in v1.0 ausschließlich `string`-Values. Numerische oder boolean Values müssen vom Aufrufer zu Strings konvertiert werden.
- Der CSS-Block für `[data-slot="segmented"]` in `app.css` definiert keine expliziten Dark-Mode-Overrides — die Token `--g-ink`, `--g-paper`, `--g-ink-muted`, `--g-ink-faint`, `--g-surface-2` werden im Projekt derzeit nicht in einem separaten Dark-Mode-Block überschrieben; das ist konsistent mit den anderen globalen Slot-Regeln (Btn, Pill).
- AC-5 (grep-Zähler) prüft das Vorhandensein der Testids als einfachen Textcheck, nicht ob sie semantisch korrekt auf den richtigen DOM-Elementen sitzen. Die Playwright-E2E-Tests (existing) geben hier die finale Sicherheit.

## Changelog

- 2026-05-21: Initial spec created (Issue #285 — EditWeatherSection + WeatherConfigDialog Full Restyle)
