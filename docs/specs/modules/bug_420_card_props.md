---
entity_id: bug_420_card_props
type: bugfix
created: 2026-05-27
updated: 2026-05-28
status: active
version: "1.0"
tags: [bugfix, frontend, atoms, design-system, card, issue-420]
---

<!-- Issue #420 — atoms/Card.svelte ignoriert padding und accent Props -->

# Bug #420 — atoms/Card.svelte: `padding` und `accent` Props werden ignoriert

## Approval

- [x] Approved

## Purpose

`atoms/Card.svelte` delegiert alle Props blind via `{...props}` an `ui/card/card.svelte`, das weder `padding` noch `accent` als deklarierte Props kennt — beide landen in `restProps` und werden als HTML-Attribute auf dem `<div>` abgelegt, ohne visuellen Effekt. Zudem ist `py-4` (= 16 px) in `ui/card/card.svelte` hardcoded (Tailwind-Klasse), was ein individuelles Padding über Props von außen verhindert. `atoms/Card.svelte` wird deshalb in eine eigenständige Komponente umgewandelt, die ihr eigenes `<div>` rendert und die Design-Token-Vorgaben aus `docs/design-requests/issue_15_atomic_design/spec/atoms.jsx` vollständig umsetzt — ohne Delegation an `ui/card/card.svelte`.

## Source

- **Datei (geändert):** `frontend/src/lib/components/atoms/Card.svelte`
- **Datei (Workaround entfernt):** `frontend/src/routes/+page.svelte` (Zeile 117)
- **Datei (Tests ergänzt):** `frontend/src/lib/components/atoms/atoms.test.ts`
- **Identifier:** `Card` (Svelte-Komponente, atoms-Schicht)

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/lib/`, `frontend/src/routes/`). Python-Backend und Go-API sind nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/design-requests/issue_15_atomic_design/spec/atoms.jsx` | Design-Vorlage | Kanonische JSX-Referenz: `padding=20`, `accent=false`, Border-Logik, `--g-card`/`--g-rule`/`--g-accent`/`--g-r-3`/`--g-shadow-1` |
| `frontend/src/app.css` | CSS-Datei | Single Source of Truth für Design-Tokens: `--g-card`, `--g-rule`, `--g-accent`, `--g-r-3`, `--g-shadow-1` |
| `frontend/src/lib/components/ui/card/card.svelte` | Referenz (unverändert) | Compound-Primitive; bleibt unangetastet — atoms/Card delegiert nach diesem Fix NICHT mehr dorthin |
| `frontend/src/lib/components/atoms/index.ts` | Re-Export | Exportiert `Card` aus der atoms-Schicht; keine Änderung nötig (Name bleibt gleich) |
| `frontend/src/routes/+page.svelte` | Aufrufer | Zeile 117: Workaround `class="!p-0"` + `style="border-left: 3px solid var(--g-accent)"` wird durch `padding={0} accent={true}` ersetzt |

## Implementation Details

### 1. `atoms/Card.svelte` — eigenständige Neuimplementierung

Der bestehende Wrapper-Code wird vollständig ersetzt. Die neue Komponente deklariert `padding` und `accent` explizit als typisierte Props und rendert ihr eigenes `<div>` mit Inline-Style für variable Werte und Design-Tokens für stabile Werte:

```svelte
<script lang="ts">
  // Issue #420 — eigenständige Implementierung gemäß atoms.jsx-Vorlage.
  // Delegiert NICHT mehr an ui/card/card.svelte.
  import type { Snippet } from 'svelte';

  let {
    children,
    padding = 20,
    accent = false,
    class: className,
    ...restProps
  }: {
    children?: Snippet;
    padding?: number;
    accent?: boolean;
    class?: string;
    [key: string]: unknown;
  } = $props();
</script>

<div
  data-slot="card"
  class={className}
  style:background="var(--g-card)"
  style:border-radius="var(--g-r-3)"
  style:box-shadow="var(--g-shadow-1)"
  style:overflow="hidden"
  style:padding="{padding}px"
  style:border-left={accent ? '3px solid var(--g-accent)' : '1px solid var(--g-rule)'}
  {...restProps}
>
  {@render children?.()}
</div>
```

**Hinweise:**
- `style:padding="{padding}px"` — Svelte-Inline-Style-Direktive für variable Werte; überschreibt kein Tailwind-py-*, weil kein Tailwind mehr auf dem Element liegt.
- `style:border-left` — ternärer Ausdruck deckt AC-3 und AC-4 ab.
- `data-slot="card"` bleibt für CSS-Selektoren, die auf dieses Attribut zielen.
- `overflow: hidden` spiegelt das bestehende Verhalten von `ui/card/card.svelte`.

### 2. `frontend/src/routes/+page.svelte` — Workaround entfernen

Zeile 117 aktuell:
```svelte
<Card class="!p-0" style="overflow: hidden; border-left: 3px solid var(--g-accent);">
```

Nach Fix:
```svelte
<Card padding={0} accent={true}>
```

Die inline `overflow: hidden`-Angabe entfällt (ist jetzt festes Verhalten der Komponente).

### 3. `atoms/atoms.test.ts` — AC-Tests ergänzen

Neuer Test-Block am Ende der Datei (Source-Inspection, kein Render, keine Mocks):

```typescript
test('#420 AC-1/AC-5/AC-7: Card deklariert padding+accent als explizite Props, kein restProps-Fallthrough', () => {
  const card = read('Card.svelte');
  assert.ok(/padding.*=.*20|padding\s*\?\s*20/.test(card), 'Card: padding-Prop mit Default 20 fehlt');
  assert.ok(/accent.*=.*false|accent\s*\?\s*false/.test(card), 'Card: accent-Prop mit Default false fehlt');
  // Keine blinde Delegation an ui/card mehr
  assert.ok(!/import.*ui\/card/.test(card), 'Card delegiert noch an ui/card (AC-7 verletzt)');
});

test('#420 AC-3/AC-4: Card border-left nutzt --g-accent (accent=true) vs --g-rule (accent=false)', () => {
  const card = read('Card.svelte');
  assert.ok(/--g-accent/.test(card), 'Card: --g-accent für accent-border fehlt');
  assert.ok(/--g-rule/.test(card), 'Card: --g-rule für Standard-border fehlt');
  assert.ok(/3px solid/.test(card), 'Card: accent-border-Breite 3px fehlt');
});

test('#420 AC-1/AC-2: Card padding als Inline-Style auf dem Root-div', () => {
  const card = read('Card.svelte');
  // Inline-Style muss padding als variable Zuweisung enthalten
  assert.ok(/style:padding|style=".*padding/.test(card), 'Card: padding als Inline-Style fehlt');
});

test('#420 AC-6: +page.svelte Workaround entfernt — kein !p-0 auf Card', () => {
  const page = readFileSync(join(here, '../../../../routes/+page.svelte'), 'utf-8');
  // Workaround-Klasse muss weg sein
  assert.ok(!/<Card[^>]*!p-0/.test(page), '+page.svelte: !p-0-Workaround auf Card noch vorhanden');
  // Workaround border-left inline style muss weg sein
  assert.ok(!/<Card[^>]*border-left:\s*3px solid var\(--g-accent\)/.test(page),
    '+page.svelte: border-left-Workaround auf Card noch vorhanden');
});
```

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `atoms/Card.svelte` | ~+25 / -9 (Vollersatz ~16 netto) | ja |
| `+page.svelte` | ~-1 netto (1 Zeile vereinfacht) | ja |
| `atoms/atoms.test.ts` | ~+25 | ja |
| **Gesamt (zählend)** | **~40** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** `<Card padding={N} accent={true|false}>...</Card>` — Props werden als typisierte Svelte-Props empfangen
- **Output:** Ein `<div data-slot="card">` mit `padding: Npx` als Inline-Style und `border-left: 3px solid var(--g-accent)` (accent=true) bzw. `border-left: 1px solid var(--g-rule)` (accent=false) als Inline-Style
- **Side effects:** `+page.svelte` ist bereinigt (kein `!p-0`, kein inline `border-left`); `ui/card/card.svelte` ist byte-gleich (unangetastet)

## Acceptance Criteria

**AC-1:** Given `atoms/Card.svelte` mit `padding={32}` / When die Komponente gerendert wird / Then ist `padding: 32px` als Inline-Style auf dem Root-`<div>` gesetzt, nicht als HTML-Attribut oder Tailwind-Klasse.
- Test: `atoms.test.ts` — `#420 AC-1/AC-2: Card padding als Inline-Style auf dem Root-div`

**AC-2:** Given `atoms/Card.svelte` mit `padding={0}` / When die Komponente gerendert wird / Then ist `padding: 0px` als Inline-Style gesetzt — kein residuales Padding durch hardcoded Tailwind-Klassen.
- Test: `atoms.test.ts` — `#420 AC-1/AC-2: Card padding als Inline-Style auf dem Root-div` (Source-Inspection beweist: kein `py-4` mehr auf dem Element)

**AC-3:** Given `atoms/Card.svelte` mit `accent={true}` / When die Komponente gerendert wird / Then ist `border-left: 3px solid var(--g-accent)` als Inline-Style auf dem Root-`<div>` gesetzt.
- Test: `atoms.test.ts` — `#420 AC-3/AC-4: Card border-left`

**AC-4:** Given `atoms/Card.svelte` ohne `accent`-Prop (Default) / When die Komponente gerendert wird / Then ist `border-left: 1px solid var(--g-rule)` als Inline-Style gesetzt — kein Accent-Border als Default.
- Test: `atoms.test.ts` — `#420 AC-3/AC-4: Card border-left`

**AC-5:** Given `atoms/Card.svelte` ohne `padding`-Prop / When die Komponente gerendert wird / Then ist der Default-Wert 20 px wirksam (`padding: 20px` im gerenderten Inline-Style).
- Test: `atoms.test.ts` — `#420 AC-1/AC-5/AC-7: Card deklariert padding+accent als explizite Props`

**AC-6:** Given `frontend/src/routes/+page.svelte` nach dem Fix / When die Datei auf den früheren Workaround geprüft wird / Then enthält das `<Card>`-Element weder `class="!p-0"` noch `style="...border-left: 3px solid var(--g-accent)"` — beides ist durch `padding={0} accent={true}` ersetzt.
- Test: `atoms.test.ts` — `#420 AC-6: +page.svelte Workaround entfernt`

**AC-7:** Given `atoms/Card.svelte` nach dem Fix / When der Quelltext analysiert wird / Then sind `padding: number` und `accent: boolean` als explizit deklarierte typisierte Props vorhanden, und es gibt keinen `import`-Verweis auf `ui/card` (keine Delegation mehr).
- Test: `atoms.test.ts` — `#420 AC-1/AC-5/AC-7: Card deklariert padding+accent als explizite Props`

## Known Limitations

- **Tailwind-Klassen auf Card:** Da die neue Komponente kein Tailwind mehr für `padding` verwendet, funktionieren etwaige `class="p-*"`-Overrides von außen weiterhin über `className` und Tailwind — allerdings würden sie mit dem Inline-Style konkurrieren (Inline gewinnt bei gleicher Eigenschaft). Aufrufer sollten für Padding ausschließlich die `padding`-Prop verwenden.
- **`ui/card/card.svelte` bleibt parallel:** Die Compound-Primitive (`ui/card/`) mit ihrer reicheren Struktur (Header, Footer, Content-Slots) bleibt vollständig erhalten und wird für komplexere Card-Layouts weiter verwendet. `atoms/Card` deckt nur den einfachen Flat-Container-Fall ab.

## Out of Scope

- Änderungen an `ui/card/card.svelte` oder anderen Compound-Primitiven
- Migration weiterer Aufrufer, die `ui/card` direkt importieren
- Neue Props jenseits von `padding` und `accent` (z. B. `size`)

## Changelog

- 2026-05-27: Initial spec erstellt. Behebt Bug #420: atoms/Card.svelte ignoriert padding+accent Props durch Delegation an ui/card; eigenständige Neuimplementierung gemäß atoms.jsx-Vorlage; Workaround in +page.svelte:117 entfernt.
