---
entity_id: issue_418_segmented_api
type: module
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [frontend, design-system, atomic, segmented, api-compatibility]
---

# Issue #418 — Segmented.svelte API-Alignment mit Katalog

## Approval

- [ ] Approved

## Purpose

`Segmented.svelte` weicht in seiner öffentlichen Prop-Schnittstelle vom Design-System-Katalog (`COMPONENTS.md`) ab: der Katalog spezifiziert `items`/`value`/`onChange`, die Implementierung verwendet `options`/`selected`/`onselect`. Durch eine Alias-Strategie werden beide APIs gleichzeitig unterstützt, sodass der Katalog-konforme SOLL-API-Pfad nutzbar wird, ohne dass bestehende Aufrufer geändert werden müssen. Zusätzlich fehlt der `size`-Prop, der konsistente Größenvarianten (`sm`/`md`) über das Komponenten-System ermöglicht.

## Source

- **File:** `frontend/src/lib/components/ui/segmented/Segmented.svelte`
- **Identifier:** `Segmented` (Svelte-Komponente)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | Upstream | Nimmt `[data-size="sm"]`/`[data-size="md"]`-Regeln auf; bestehende `[data-slot="segmented-item"]`-Baseline bleibt erhalten |
| `docs/design-system/COMPONENTS.md` | Referenz | SOLL-API-Spezifikation für `Segmented` (items/value/onChange/size) |
| `frontend/src/routes/_design/+page.svelte` | Konsument | Design-System-Showcase; erhält Demo-Instanz mit SOLL-API |
| `frontend/src/lib/components/trip-detail/WeatherConfigDialog.svelte` | Konsument (bestehend) | Nutzt IST-API (`options`/`selected`/`onselect`) — darf unverändert bleiben |
| `frontend/src/routes/archiv/+page.svelte` | Konsument (bestehend) | Nutzt IST-API — darf unverändert bleiben |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Konsument (bestehend) | Nutzt IST-API — darf unverändert bleiben |

## Implementation Details

### 1. Alias-Props in `Segmented.svelte`

Im `$props()`-Block werden beide API-Varianten als optionale Props deklariert. Drei `$derived`-Werte lösen zur Laufzeit auf:

```svelte
<script lang="ts">
  let {
    // SOLL-API (Katalog)
    items,
    value,
    onChange,
    size,
    // IST-API (bestehend, Alias)
    options,
    selected,
    onselect,
    // gemeinsame Props
    ...rest
  }: {
    items?: Array<{ id: string; label: string; badge?: number }>;
    value?: string;
    onChange?: (id: string) => void;
    size?: 'sm' | 'md';
    options?: Array<{ value: string; label: string; badge?: number }>;
    selected?: string;
    onselect?: (value: string) => void;
  } = $props();

  // Normalisierung: SOLL-API hat Vorrang, IST-API als Fallback
  const resolvedItems = $derived(
    items
      ? items.map(i => ({ value: i.id, label: i.label, badge: i.badge }))
      : (options ?? [])
  );
  const resolvedValue = $derived(value ?? selected ?? '');
  const resolvedChange = $derived(onChange
    ? (v: string) => onChange(v)
    : (onselect ?? (() => {}))
  );
</script>
```

### 2. `size`-Prop auf Container-Element

Das Wurzel-Element (`[data-slot="segmented"]`) erhält `data-size` nur wenn `size` explizit übergeben wurde, damit bestehende Aufrufer ohne `size`-Prop ihr Basis-Padding behalten:

```svelte
<div data-slot="segmented" data-size={size ?? undefined} ...>
```

### 3. CSS-Größenvarianten in `app.css`

Neue Regeln analog zum `Btn`/`Dot`-Muster — nach dem bestehenden `[data-slot="segmented-item"]`-Block einfügen:

```css
[data-slot="segmented"][data-size="sm"] [data-slot="segmented-item"] {
  padding: 2px 8px;
  font-size: var(--g-text-xs);
}

[data-slot="segmented"][data-size="md"] [data-slot="segmented-item"] {
  padding: 4px 12px;
  font-size: var(--g-text-sm);
}
```

### 4. COMPONENTS.md — API-Dokumentation aktualisieren

Die Katalog-Einträge für `Segmented` werden so umformuliert, dass IST-API (`options`/`selected`/`onselect`) als primäre API erscheint und SOLL-API (`items`/`value`/`onChange`) als unterstützter Alias ausgewiesen wird. Kein Entfernen bestehender Einträge.

### 5. Design-System-Showcase — SOLL-API-Demo

In `_design/+page.svelte` wird eine zweite `<Segmented>`-Instanz mit der SOLL-API eingefügt, damit die Katalog-konforme Variante im Showcase sichtbar und testbar ist:

```svelte
<Segmented
  items={[
    { id: 'a', label: 'Option A' },
    { id: 'b', label: 'Option B', badge: 3 },
  ]}
  value="a"
  onChange={(id) => console.log('selected:', id)}
  size="sm"
/>
```

## Expected Behavior

- **Input (SOLL-API):** `items` (Array mit `id`-Schlüssel), `value` (aktiver Wert), `onChange` (Callback mit `id`), optional `size="sm"|"md"`
- **Input (IST-API / Alias):** `options` (Array mit `value`-Schlüssel), `selected` (aktiver Wert), `onselect` (Callback mit `value`), kein `size`
- **Output:** Gerenderte Segment-Leiste, Klick auf Item ruft den jeweils aufgelösten Callback mit dem Item-Schlüssel auf
- **Side effects:** Bei fehlendem `size`-Prop kein `data-size`-Attribut am Container — Basis-Padding aus bestehendem CSS bleibt exakt erhalten; kein visueller Rückschritt für bestehende Aufrufer

## Acceptance Criteria

**AC-1:** Given eine `<Segmented>`-Instanz mit SOLL-API (`items`, `value`, `onChange`) / When ein Item angeklickt wird / Then wird `onChange` mit dem `id`-Wert des geklickten Items aufgerufen und das Item als aktiv dargestellt.
- Test: (populated after /tdd-red)

**AC-2:** Given die vier bestehenden Aufrufer (`WeatherConfigDialog.svelte` 2x, `archiv/+page.svelte`, `TripTabs.svelte`) mit IST-API (`options`, `selected`, `onselect`) / When `Segmented.svelte` mit den Alias-Props gerendert wird / Then funktioniert die Auswahl identisch wie vor dem Change — kein visueller Rückschritt, kein JS-Fehler.
- Test: (populated after /tdd-red)

**AC-3:** Given eine `<Segmented>`-Instanz mit `size="sm"` / When die Komponente gerendert wird / Then hat der Container das Attribut `data-size="sm"` und `[data-slot="segmented-item"]` hat `padding: 2px 8px` und `font-size: var(--g-text-xs)`.
- Test: (populated after /tdd-red)

**AC-4:** Given eine `<Segmented>`-Instanz ohne `size`-Prop / When die Komponente gerendert wird / Then hat der Container kein `data-size`-Attribut und `[data-slot="segmented-item"]` rendert mit unverändertem Basis-Padding (CSS-Regression ausgeschlossen).
- Test: (populated after /tdd-red)

**AC-5:** Given `docs/design-system/COMPONENTS.md` nach dem Update / When der `Segmented`-Abschnitt gelesen wird / Then ist die IST-API (`options`/`selected`/`onselect`) als primäre API dokumentiert und die SOLL-API (`items`/`value`/`onChange`) als unterstützter Alias ausgewiesen.
- Test: (populated after /tdd-red)

## Known Limitations

- `onChange` in der SOLL-API übergibt den `id`-Wert; `onselect` in der IST-API übergibt den `value`-Wert — bei der Alias-Auflösung sind diese semantisch identisch, da `resolvedItems` `id` auf `value` mapped. Aufrufer, die beide Props gleichzeitig übergeben, bekommen `onChange` (SOLL-API hat Vorrang).
- `size`-Prop ohne CSS-Variante (z.B. `size="lg"`) wird ignoriert — `data-size` wird gesetzt, hat aber keine entsprechende CSS-Regel. Erweiterung bleibt Folge-Issue.

## Changelog

- 2026-05-27: Initial spec created (Issue #418)
