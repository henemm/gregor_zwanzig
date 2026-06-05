---
entity: issue_577_atoms_sync_v2
type: feature
status: draft
created: 2026-06-05
issue: 577
epic: 575
---

# Spec: Issue #577 — Atoms-Sync mit JSX-Vorlage (Foundation)

## Kontext

Sub-Issue Epic #575 (Design-Fidelity Redo). Foundation-Diff-Strategie: nach
#576 (Tokens) ist #577 die zweite Schicht — die wiederverwendbaren Atom-
Komponenten (Btn, Pill, Card, Eyebrow, Dot, Input, Switch, Segmented, …) gegen
die JSX-Vorlage in `claude-code-handoff/current/jsx/atoms.jsx` abgleichen.

JSX gilt als Wahrheit. SOLL-PNGs sind nur Begleitmaterial.

## Befund

### Btn — 5 Drift-Punkte

JSX-Quelle: `atoms.jsx::Btn` (Z. 126–151). Svelte-Ziel:
`frontend/src/lib/components/ui/btn/Btn.svelte` (Markup) +
`frontend/src/app.css` Z. 222–340 (Styles).

| Attribut | JSX-Wert | Svelte-Wert (app.css) | Drift |
|----------|----------|-----------------------|-------|
| `border-radius` | `var(--g-r-2)` = **4 px** | `var(--g-radius-md)` = **8 px** | +4 px |
| `padding` (sm) | `6px 10px` | `6px 10px` | – |
| `padding` (md) | `9px 14px` | `8px 14px` | −1 px padY |
| `padding` (lg) | `12px 20px` | `10px 18px` | −2 px padY, −2 px padX |
| `font-size` (sm) | `12px` | `var(--g-text-sm)` = `13px` | +1 px |
| `font-size` (md) | `13px` | `var(--g-text-sm)` = `13px` | – |
| `font-size` (lg) | `14px` | `var(--g-text-md)` = `15px` | +1 px |
| `accent`-Variante `color` | `#fff` (rgb(255,255,255)) | `var(--g-paper)` = `#f6f4ee` | Off-White statt Weiß |

### Pill — 1 Drift-Punkt

JSX-Quelle: `atoms.jsx::Pill` (Z. 59–78). Svelte-Ziel: `app.css` Z. 359–372.

| Attribut | JSX | Svelte | Drift |
|----------|-----|--------|-------|
| `padding` | `3px 9px` | `0.125rem 0.5rem` = `2px 8px` | −1 px padY, −1 px padX |

### Card (g-card) — 3 Drift-Punkte

JSX-Quelle: `atoms.jsx::Card` (Z. 81–93). Svelte-Ziel: `app.css` Z. 349–356.

| Attribut | JSX | Svelte | Drift |
|----------|-----|--------|-------|
| `border-radius` | `var(--g-r-3)` = **6 px** | `var(--g-radius-lg)` = **12 px** | +6 px |
| `padding` | `20 px` (default-Prop) | `1rem` = **16 px** | −4 px |
| `border` | `1px solid var(--g-rule)` | _kein expliziter Border_ | Border fehlt |

### Eyebrow — verifizieren

JSX (Z. 49–56): `fontSize 11`, `letterSpacing var(--g-track-caps)`,
`textTransform uppercase`, `color var(--g-ink-3)`, `fontWeight 500`.
Svelte (Z. 439–447): `font-size 11px`, `letter-spacing var(--g-track-caps)`,
`text-transform uppercase`, `color var(--g-ink-muted)`, `font-weight 500`.

`var(--g-ink-3)` und `var(--g-ink-muted)` müssen denselben Effektivwert haben.
Sonst Drift.

## Acceptance Criteria

**AC-1:** Given ein DOM-`<button data-slot="btn">`, when es gerendert ist,
then ist `border-radius` des computed style **4 px** (JSX-Wert `var(--g-r-2)`).

**AC-2:** Given ein `<button data-slot="btn" data-size="md">`, when es
gerendert ist, then ist `padding-top` und `padding-bottom` jeweils **9 px**
(JSX md.padY = 9).

**AC-3:** Given ein `<button data-slot="btn" data-size="lg">`, when es
gerendert ist, then ist `padding` **12 px 20 px** und `font-size` **14 px**.

**AC-4:** Given ein `<button data-slot="btn" data-size="sm">`, when es
gerendert ist, then ist `font-size` **12 px** (JSX-Wert).

**AC-5:** Given ein `<button data-slot="btn" data-variant="accent">`, when es
gerendert ist, then ist `color` `rgb(255, 255, 255)` (JSX-Wert `#fff`).

**AC-6:** Given ein `<span data-slot="pill">`, when es gerendert ist, then ist
`padding-top` und `padding-bottom` jeweils **3 px**, `padding-left` und
`padding-right` jeweils **9 px** (JSX-Wert).

**AC-7:** Given ein `<div data-slot="g-card">`, when es gerendert ist, then
ist `border-radius` **6 px** (JSX-Wert `var(--g-r-3)` nach #576).

**AC-8:** Given ein `<div data-slot="g-card">`, when es gerendert ist, then
ist `padding` **20 px** (JSX default-Prop).

**AC-9:** Given ein `<div data-slot="g-card">`, when es gerendert ist, then
ist `border-width` **1 px** und `border-color` der Effektivwert von
`var(--g-rule)` (JSX-Wert `1px solid var(--g-rule)`).

**AC-10:** Given ein `<div data-slot="eyebrow">`, when es gerendert ist, then
ist `color` der computed style `rgb(107, 103, 92)` (= `#6b675c` = JSX-Wert
`var(--g-ink-3)`).

## Implementation-Strategie

Vollständiger Atom-Sweep durch Developer-Agent. Pro Atom JSX-Werte aus
`atoms.jsx` direkt in die zugehörigen Selektoren in `frontend/src/app.css`
schreiben. Markup-Dateien in `frontend/src/lib/components/ui/<atom>/*.svelte`
bleiben strukturell unverändert (Selektor-Hooks `data-slot` / `data-size` /
`data-variant` bleiben).

### Konkrete Änderungen in `app.css`

**Btn-Block (Z. 222–247):**

```css
[data-slot="btn"] {
  ...
  border-radius: var(--g-r-2);   /* statt var(--g-radius-md) */
  ...
}
[data-slot="btn"][data-size="sm"] { padding: 6px 10px; font-size: 12px; min-height: 28px; }
[data-slot="btn"][data-size="md"] { padding: 9px 14px; font-size: 13px; min-height: 32px; }
[data-slot="btn"][data-size="lg"] { padding: 12px 20px; font-size: 14px; min-height: 36px; }
```

**Btn-accent-Variant (Z. 263–270):**

```css
[data-slot="btn"][data-variant="accent"] {
  background-color: var(--g-accent);
  color: #fff;                   /* statt var(--g-paper) */
  border-color: var(--g-accent);
}
```

**Pill-Base (Z. 359–372):**

```css
[data-slot="pill"] {
  ...
  padding: 3px 9px;              /* statt 0.125rem 0.5rem */
  ...
}
```

**g-card-Base (Z. 349–356):**

```css
[data-slot="g-card"] {
  background: var(--g-surface-1);
  border: 1px solid var(--g-rule);
  border-radius: var(--g-r-3);   /* statt var(--g-radius-lg) */
  box-shadow: var(--g-elev-1);
  padding: 20px;                 /* statt 1rem */
  transition: box-shadow 0.15s ease;
}
```

**Eyebrow:** Falls AC-10 RED → `--g-ink-muted` so anpassen dass es identisch
zu `--g-ink-3` ist (oder Eyebrow-Color direkt auf `var(--g-ink-3)` setzen).

### Optionale Sweep-Punkte (Developer-Agent prüft + fixt mit, ohne expliziten AC)

Der Agent durchläuft auch die übrigen Atoms (Dot, Input, Switch, Segmented,
SectionH, KV, AvatarStack, ElevSparkline) und gleicht offensichtliche
Drifts an JSX an. Drifts ohne AC werden NICHT von Tests verifiziert, aber
im Implementation-Bericht dokumentiert.

## Non-Goals

- Markup-Refactor (Svelte-Komponente bleibt strukturell wie sie ist).
- Tailwind-Default-Tokens (`--g-radius-md`, `--g-radius-lg`) anfassen — diese
  sind für `rounded-md`/`rounded-lg`-Klassen reserviert.
- TopoBg, WIcon (SVG-Atoms) — visuell identisch durch JSX-Markup-Übernahme
  in früheren Issues.
- Logo (delegiert via `BrandWordmark`, eigenes Issue).

## Test-Strategie

Playwright computed-style-Tests auf authentifizierter Staging-Seite (gleiches
Pattern wie #576). Test injiziert DOM-Elemente mit den Atom-Selectors und
prüft den effektiven Computed-Style.

Source: `tests/tdd/test_issue_577_atoms_values.py`.
Test-Manifest: `docs/specs/tests/issue_577_atoms_values_tests.md`.
