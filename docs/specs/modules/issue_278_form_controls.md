---
entity_id: issue_278_form_controls
type: module
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [frontend, svelte5, ui-primitive, checkbox, select, design-system, issue-278]
---

<!-- Issue #278 — Gebrandete Form-Controls: Checkbox & Select UI-Primitive -->

# Issue #278 — Gebrandete Form-Controls: Checkbox & Select UI-Primitive

## Approval

- [ ] Approved

## Zweck

Zwei neue Svelte-5-UI-Primitive (`Checkbox.svelte`, `Select.svelte`) ersetzen alle nativen `<input type="checkbox">` und `<select>`-Elemente im Frontend durch konsistent gebrandete Komponenten auf Basis des Design-Systems (Design-Tokens aus `app.css`). Der Wechsel beseitigt system-blaue Browser-Defaults in Checkboxen und uneinheitliche System-Chevrons in Dropdowns und setzt stattdessen die Palette `--g-ink` / `--g-paper` / `--g-accent` durch — ohne bestehende Playwright-Tests zu brechen, da `data-testid`-Attribute und native Element-Semantik erhalten bleiben.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code betroffen.

## Quelle / Source

**Neue Dateien:**
- `frontend/src/lib/components/ui/checkbox/Checkbox.svelte` — neue UI-Primitive
- `frontend/src/lib/components/ui/checkbox/index.ts` — Re-Export
- `frontend/src/lib/components/ui/select/Select.svelte` — neue UI-Primitive
- `frontend/src/lib/components/ui/select/index.ts` — Re-Export

**Migrierte Dateien (Checkboxen — 11 Dateien):**
- `frontend/src/routes/trips/+page.svelte` — 7 Checkboxen
- `frontend/src/lib/components/edit/EditWeatherSection.svelte` — 1 Checkbox
- `frontend/src/lib/components/edit/EditReportConfigSection.svelte` — 9 Checkboxen (Playwright-testids)
- `frontend/src/lib/components/trip-wizard/steps/ReportRow.svelte` — 1 Checkbox
- `frontend/src/lib/components/trip-wizard/steps/ChannelToggle.svelte` — 1 Checkbox
- `frontend/src/lib/components/compare/LocationsRail.svelte` — 4 Checkboxen (kein Label-Text)
- `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` — 2 Checkboxen
- `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` — 1 Checkbox
- `frontend/src/lib/components/SubscriptionForm.svelte` — 7 Checkboxen
- `frontend/src/lib/components/WeatherConfigDialog.svelte` — 1 Checkbox
- `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` — 1 Checkbox

**Migrierte Dateien (Selects — 10 Dateien):**
- `frontend/src/routes/trips/+page.svelte` — 2 Selects
- `frontend/src/routes/compare/+page.svelte` — 1 Select
- `frontend/src/routes/weather/+page.svelte` — 2 Selects
- `frontend/src/lib/components/LocationForm.svelte` — 1 Select
- `frontend/src/lib/components/SubscriptionForm.svelte` — 4 Selects
- `frontend/src/lib/components/WeatherConfigDialog.svelte` — 1 Select
- `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` — 3 Selects
- `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte` — 1 Select
- `frontend/src/lib/components/compare/PresetHeader.svelte` — 4 Selects
- `frontend/src/lib/components/edit/EditWeatherSection.svelte` — 1 Select

**NICHT ändern:**
- `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` — bereits eigene Custom-Implementierung mit `<button role="checkbox">`, bleibt unverändert

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Datei | Single Source of Truth für Design-Tokens (`--g-ink`, `--g-paper`, `--g-accent`, `--g-ink-faint`, `--g-ink-muted`, `--g-radius-xs`, `--g-radius-sm`, `--g-text-sm`, `--g-font-ui`, `--g-s-2`) |
| Svelte 5 (`$props()`, `$bindable()`) | Framework | Reaktive Props-API und bindbare Werte für `checked` (Checkbox) und `value` (Select) |
| Playwright | Test-Framework | `data-testid`-Forwarding auf native Elemente muss erhalten bleiben; `selectOption()` setzt natives `<select bind:value>` voraus |
| `frontend/src/lib/components/ui/input/input.svelte` | Svelte-Komponente | Referenz-Implementierung für den `...restProps`-Pattern im `ui/`-Verzeichnis |

## Implementation Details

### 1. `Checkbox.svelte` — neue UI-Primitive

**Datei:** `frontend/src/lib/components/ui/checkbox/Checkbox.svelte`

**Props:**
```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    checked = $bindable(false),
    disabled = false,
    onchange,
    children,
    ...restProps
  }: {
    checked?: boolean;
    disabled?: boolean;
    onchange?: (e: Event) => void;
    children?: Snippet;
    [key: string]: unknown;
  } = $props();
</script>
```

**Markup-Struktur:**
```svelte
<label class="gz-checkbox" class:disabled>
  <span class="gz-checkbox__box" class:checked>
    <input
      type="checkbox"
      bind:checked
      {disabled}
      {onchange}
      {...restProps}
    />
    {#if checked}
      <svg ...><!-- Checkmark --></svg>
    {/if}
  </span>
  {#if children}
    <span class="gz-checkbox__label">{@render children()}</span>
  {/if}
</label>
```

**CSS-Anforderungen:**
- `.gz-checkbox`: `display: inline-flex; align-items: center; gap: var(--g-s-2); cursor: pointer`
- `.gz-checkbox.disabled`: `opacity: 0.5; cursor: not-allowed`
- `.gz-checkbox__box`: `position: relative; width: 16px; height: 16px; border: 1.5px solid var(--g-ink-faint); border-radius: var(--g-radius-xs); background: var(--g-paper); flex-shrink: 0`
- `.gz-checkbox__box.checked`: `background: var(--g-ink); border-color: var(--g-ink)`
- Nativer `<input>`: `opacity: 0; position: absolute; width: 100%; height: 100%; margin: 0; cursor: inherit` — KEIN `pointer-events: none` (Playwright braucht Events!)
- Focus-Ring: `input:focus-visible + svg, input:focus-visible ~ *` oder per `:focus-within` auf `.gz-checkbox__box`: `outline: 2px solid var(--g-accent); outline-offset: 2px`
- Checkmark-SVG: weißes Häkchen (stroke: white), 10×10px, absolut zentriert in der Box

**Export:** `frontend/src/lib/components/ui/checkbox/index.ts`
```ts
export { default as Checkbox } from './Checkbox.svelte';
```

---

### 2. `Select.svelte` — neue UI-Primitive

**Datei:** `frontend/src/lib/components/ui/select/Select.svelte`

**Props:**
```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    value = $bindable(),
    onchange,
    children,
    ...restProps
  }: {
    value?: unknown;
    onchange?: (e: Event) => void;
    children?: Snippet;
    [key: string]: unknown;
  } = $props();
</script>
```

**Markup-Struktur:**
```svelte
<div class="gz-select">
  <select bind:value {onchange} {...restProps}>
    {@render children?.()}
  </select>
  <svg class="gz-select__chevron" ...><!-- Chevron-Down --></svg>
</div>
```

**CSS-Anforderungen:**
- `.gz-select`: `position: relative; display: inline-block`
- `select`: `appearance: none; width: 100%; padding: ...var(--g-s-2)...; border: 1px solid var(--g-ink-faint); border-radius: var(--g-radius-sm); background: var(--g-paper); font-family: var(--g-font-ui); font-size: var(--g-text-sm); color: var(--g-ink); padding-right: 2rem` (Platz für Chevron)
- `.gz-select__chevron`: `position: absolute; right: var(--g-s-2); top: 50%; transform: translateY(-50%); pointer-events: none; color: var(--g-ink-muted)`
- `select:focus-visible`: `outline: 2px solid var(--g-accent); outline-offset: 2px`

**Kritisch:** `bind:value` MUSS auf dem nativen `<select>` bleiben — Playwright `selectOption()` setzt natives `bind:value` voraus.

**Export:** `frontend/src/lib/components/ui/select/index.ts`
```ts
export { default as Select } from './Select.svelte';
```

---

### 3. Migration — Checkboxen ersetzen

**Pattern für Stellen MIT vorhandenem `<label>`-Wrapper:**

Vorher:
```svelte
<label class="flex items-center gap-2">
  <input type="checkbox" bind:checked={state} />
  Label-Text
</label>
```

Nachher:
```svelte
<Checkbox bind:checked={state}>Label-Text</Checkbox>
```

Der alte `<label>`-Wrapper entfällt vollständig — `Checkbox` enthält ein eigenes `<label>`.

**Pattern für Stellen OHNE Label-Text (z.B. LocationsRail.svelte):**

```svelte
<Checkbox bind:checked={state} />
```

Das `children`-Snippet ist optional — wenn nicht übergeben, wird kein Label gerendert.

**Pattern für `data-testid`:**

```svelte
<Checkbox bind:checked={state} data-testid="my-checkbox">Label</Checkbox>
```

`data-testid` landet via `...restProps` auf dem nativen `<input>`.

**Import in jeder migrierten Datei ergänzen:**
```ts
import { Checkbox } from '$lib/components/ui/checkbox';
```

---

### 4. Migration — Selects ersetzen

**Standard-Pattern:**

Vorher:
```svelte
<select bind:value={state} class="...tailwind...">
  <option value="a">A</option>
</select>
```

Nachher:
```svelte
<Select bind:value={state} class="...tailwind...">
  <option value="a">A</option>
</Select>
```

**Sonderfall `AlertRuleRow.svelte` — Number-Coercion ohne `bind:value`:**

Ein Select in dieser Datei nutzt `value={draft.threshold} onchange={onThunderChange}` statt `bind:value` (wegen Number-Coercion). Da `onchange` via `...restProps` weitergereicht wird, ist kein Sonderfall in der Komponente nötig — der Aufruf bleibt unverändert:

```svelte
<Select value={draft.threshold} onchange={onThunderChange}>
  ...
</Select>
```

**Import in jeder migrierten Datei ergänzen:**
```ts
import { Select } from '$lib/components/ui/select';
```

---

### 5. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `Checkbox.svelte` (neu) | ~60 | nein (Frontend-Asset) |
| `checkbox/index.ts` (neu) | ~1 | nein |
| `Select.svelte` (neu) | ~50 | nein (Frontend-Asset) |
| `select/index.ts` (neu) | ~1 | nein |
| 21 migrierte Dateien (~320 LoC Netto-Delta) | ~320 | nein (Frontend-Assets) |
| **Gesamt (zählend)** | **0** | **< 250 LoC-Limit** |

Frontend-Assets (`frontend/src/`) zählen nicht gegen das LoC-Limit. Das Limit muss dennoch auf 350 angehoben werden für den Fall, dass zählende Hilfsdateien unerwartet anfallen — per `workflow.py set-field loc_limit_override 350` vor Implementierungsbeginn.

## Expected Behavior

- **Input:** `bind:checked` (Boolean, Checkbox), `bind:value` (beliebig, Select), optionaler `onchange`-Handler, `children`-Snippet, beliebige restProps (inkl. `data-testid`, `disabled`, `class`)
- **Output:** Gerenderte Checkbox-Box (16×16 px, ink-on-paper) bzw. Select-Container mit nativem `<select>` und SVG-Chevron. Visuell: keine System-Blau-Defaults, kein System-Chevron.
- **Side effects:** Keine. Keine Laufzeit-State-Änderungen außerhalb der Komponente. `bind:checked`/`bind:value` synchronisiert den Eltern-State reaktiv. `data-testid` auf nativem Element stellt Playwright-Kompatibilität sicher.

## Acceptance Criteria

- **AC-1:** Given die Checkbox-Komponente unter `frontend/src/lib/components/ui/checkbox/`, When sie mit `bind:checked` und einem `children`-Snippet eingebunden wird, Then rendert sie einen nativen `<input type="checkbox">` mit `opacity: 0` im DOM und eine sichtbare 16×16px-Box mit `--g-ink`-Hintergrund im checked-Zustand
  - Test: (populated after /tdd-red)

- **AC-2:** Given die Select-Komponente unter `frontend/src/lib/components/ui/select/`, When sie mit `bind:value` und `<option>`-Kindern eingebunden wird, Then rendert sie ein natives `<select bind:value>` mit `appearance: none` und einen absolut positionierten SVG-Chevron
  - Test: (populated after /tdd-red)

- **AC-3:** Given die vollständig migrierte Codebasis, When `rg 'type="checkbox"' frontend/src` ausgeführt wird, Then finden sich Treffer ausschließlich in `frontend/src/lib/components/ui/checkbox/Checkbox.svelte` — keine nativen Checkboxen in anderen Dateien
  - Test: (populated after /tdd-red)

- **AC-4:** Given die vollständig migrierte Codebasis, When `rg '<select\b' frontend/src` ausgeführt wird, Then finden sich Treffer ausschließlich in `frontend/src/lib/components/ui/select/Select.svelte` — keine nativen Selects in anderen Dateien
  - Test: (populated after /tdd-red)

- **AC-5:** Given eine Checkbox in der Wetter-Konfiguration, den Report-Einstellungen, den Alarmregeln, der Compare-Rail und dem Trip-Edit, When sie im Browser angezeigt wird, Then ist der checked-Hintergrund `var(--g-ink)` (dunkel/schwarz) — kein system-blauer Haken sichtbar
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein Playwright-Test, der `data-testid="some-checkbox"` auf einer migrierten Checkbox verwendet, When Playwright `locator('[data-testid="some-checkbox"]')` aufruft, Then landet der Selektor auf dem nativen `<input type="checkbox">` und Playwright kann `.check()` und `.uncheck()` darauf ausführen
  - Test: (populated after /tdd-red)

- **AC-7:** Given eine gebrandete Checkbox im fokussierten Zustand (Tab-Navigation), When die Checkbox Focus erhält, Then zeigt sie einen `2px`-Ring in `var(--g-accent)` und Space-Taste togglet den checked-State
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein gebrandetes Select im Browser (kein SystemUI-Renderer), When das Select angezeigt wird, Then ist der System-Dropdown-Pfeil durch den SVG-Chevron der Komponente ersetzt (`appearance: none` auf nativem `<select>`)
  - Test: (populated after /tdd-red)

## Known Limitations

- **MetricCheckbox.svelte bleibt unverändert:** Diese Komponente nutzt `<button role="checkbox">` statt `<input type="checkbox">` und hat eine eigene Styling-Logik. Sie wird nicht migriert, um Verhalten und Tests nicht zu destabilisieren.
- **Number-Coercion bei AlertRuleRow-Threshold-Select:** Die neue Select-Komponente übernimmt `onchange` via `restProps`. Die Number-Coercion muss weiterhin im `onchange`-Handler des Aufrufers geschehen (`parseInt(e.target.value)` o. ä.) — die Komponente selbst wandelt `value` nicht um.
- **LocationsRail-Checkboxen ohne Label:** Das `children`-Snippet ist optional — Checkboxen ohne Label-Text rendern nur die Box. Barrierefreiheit dieser Stellen (fehlender `aria-label`) ist Out of Scope für dieses Issue.
- **System-Select auf iOS Safari:** Auf iOS ersetzt iOS das `<select>`-Element trotz `appearance: none` durch ein natives Wheel-Picker-UI. Der SVG-Chevron ist dort kein Block, schadet aber auch nicht. Dieses Verhalten ist iOS-Standard und nicht beeinflussbar.
- **LoC-Override nötig:** Da Frontend-Assets nicht zählen, liegt das effektive LoC-Delta bei 0 — dennoch muss der Override auf 350 gesetzt werden, falls zählende Hilfsdateien entstehen.

## Out of Scope

- Änderungen an `MetricCheckbox.svelte` — bereits korrekt und separat
- Accessibility-Verbesserungen an label-losen Checkboxen (z.B. `aria-label` für LocationsRail)
- Animations/Transitions beim Toggling
- SMS-/E-Mail-Templates — betrifft nur das SvelteKit-Frontend
- Backend-Änderungen jeglicher Art
- Dark-Mode-spezifische Token — werden im Design-System separat behandelt

## Changelog

- 2026-05-20: Initial spec erstellt. Definiert zwei neue Svelte-5-UI-Primitive (Checkbox, Select) und die Migration von 21 Dateien (11 Checkbox-Stellen, 10 Select-Stellen). Playwright-Kompatibilität über natives Element + restProps sichergestellt.
