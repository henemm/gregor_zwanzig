---
entity_id: issue_214_btn_feature_parity
type: context
created: 2026-05-13
issues: [214]
parent: 212
related: [215, 216]
---

# Context: Issue #214 — Btn-Feature-Parität (Phase A der Button-Konsolidierung)

## Request Summary

`Btn` (Design-System-Komponente mit `data-slot`-Pattern) soll alle Features bekommen, die heute die parallele `Button`-Komponente (shadcn/Tailwind-Variante) leistet. Voraussetzung für die Migration der 94 Button-Aufrufstellen in Phase B (#215) und das anschließende Entfernen der alten Komponente in Phase C (#216).

## Ist-Stand (Btn)

**`frontend/src/lib/components/ui/btn/Btn.svelte`:**
- Props: `variant: 'accent' | 'ghost' | 'outline'`, `size: 'sm' | 'md' | 'lg'`, `class`, `ref`, `children`, + HTMLButtonAttributes
- Defaults: `variant='accent'`, `size='md'`
- Rendert nur `<button>` — kein `<a href>`-Support
- Kein Disabled-Styling über CSS
- Kein Icon-Slot

**CSS in `frontend/src/app.css` Z. 127–149:** 3 Variants × 3 Sizes = 9 Kombinationen, plus generische Hover/Focus.

## Ist-Stand (Button — Vergleichs-Quelle, nicht Ziel)

**`frontend/src/lib/components/ui/button/button.svelte`:**
- Variants: `default`, `outline`, `secondary`, `ghost`, `destructive`, `link` (6)
- Sizes: `default`, `xs`, `sm`, `lg`, `icon`, `icon-xs`, `icon-sm`, `icon-lg` (8)
- href-Switch: rendert `<a>` wenn `href`-Prop gesetzt, sonst `<button>`
- Disabled: `disabled:pointer-events-none disabled:opacity-50`
- Icon-Sizing: `[&_svg:not([class*='size-'])]:size-4` (anpassbar pro Size)
- Aria-States: `aria-invalid`, `aria-expanded`, `aria-disabled`
- Tailwind-Variants via `tv()` mit verschachtelten Tailwind-Utility-Klassen

## Soll-Stand (Btn nach Phase A)

**Props-Interface erweitert:**

```typescript
interface BtnProps extends WithElementRef<HTMLButtonAttributes>, Partial<HTMLAnchorAttributes> {
  variant?: 'primary' | 'accent' | 'outline' | 'ghost' | 'destructive' | 'secondary' | 'link';
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'icon' | 'icon-xs' | 'icon-sm' | 'icon-lg';
  href?: string;
  disabled?: boolean;
}
```

**Render-Logik:**
- Wenn `href` gesetzt → `<a>` mit `aria-disabled` falls disabled
- Sonst `<button>` mit `disabled`-Attribut

**CSS (in `app.css`):**
- Alle 7 Variants als `[data-slot="btn"][data-variant="…"]`-Selektoren
- Alle 8 Sizes als `[data-slot="btn"][data-size="…"]`-Selektoren
- Icon-Sizing über Descendant-Selektor `[data-slot="btn"] > svg`
- Disabled-State: `[data-slot="btn"][disabled], [data-slot="btn"][aria-disabled="true"] { … }`

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/ui/btn/Btn.svelte` | EDIT — Props erweitern, href-Switch einbauen |
| `frontend/src/lib/components/ui/btn/index.ts` | EDIT — neue Type-Exports (`BtnVariant`, `BtnSize`, `BtnProps`) |
| `frontend/src/app.css` Z. 127–149 | EDIT — CSS-Block erweitern für neue Variants + Sizes + disabled-State + Icon-Sizing |
| `frontend/src/lib/components/ui/button/button.svelte` | REFERENZ (nicht editieren) — Variants/Sizes/Patterns spicken |
| `frontend/src/routes/_design/+page.svelte` | EDIT — Showcase um alle neuen Variants und Sizes erweitern |
| `frontend/src/lib/components/ui/btn/Btn.test.ts` | NEU — Vitest-Unit-Tests |
| `frontend/e2e/btn-feature-parity.spec.ts` | NEU — Playwright-Smoke-Test im /_design |

## Variant-Mapping (Spec für Phase B)

Soll-Mapping von shadcn-Button-Variants → Btn-Variants:

| Button-Variant | Btn-Variant | Begründung |
|---|---|---|
| `default` | `primary` | shadcn-default ist die „Standard-Aktion" mit dunklem Look (oklch 0.205) — bei uns „primary" mit `--g-ink` als Background |
| `outline` | `outline` | direkt |
| `secondary` | `secondary` | direkt (Background `--g-surface-2`, Text `--g-ink`) |
| `ghost` | `ghost` | direkt |
| `destructive` | `destructive` | direkt (Background mit `--g-danger`-Tint) |
| `link` | `link` | direkt (Text `--g-accent`, Underline-Offset) |

`accent` bleibt der Burnt-Orange-Marken-Variant (für besondere Hauptaktionen wie Wizard-Speichern).

## Size-Mapping (Spec für Phase B)

| Button-Size | Btn-Size | Hinweis |
|---|---|---|
| `default` | `md` | Default in beiden |
| `xs` | `xs` | neu in Btn |
| `sm` | `sm` | existiert |
| `lg` | `lg` | existiert |
| `icon` | `icon` | neu — quadratisch, SVG-only |
| `icon-xs` | `icon-xs` | neu |
| `icon-sm` | `icon-sm` | neu |
| `icon-lg` | `icon-lg` | neu |

## Existing Patterns

- **Data-Slot-CSS in `app.css`:** Bestehende Komponenten (Btn, GCard, Pill, Eyebrow, Dot) nutzen alle dasselbe Pattern. Neue Variants/Sizes konsistent dort einreihen.
- **Tokens:** `--g-accent`, `--g-ink`, `--g-paper`, `--g-surface-0/1/2`, `--g-success`, `--g-warning`, `--g-danger`, `--g-info`, `--g-radius-md`, `--g-text-sm`, `--g-s-*`
- **Snippet-Pattern für `children`:** Svelte 5 `Snippet`-Typing aus `'svelte'`-Import
- **`cn()`-Helper:** Aus `$lib/utils.js` — für conditional class strings

## Dependencies

**Upstream (was wir nutzen):**
- `--g-*` Design-Tokens aus `app.css`
- `cn()`, `WithElementRef` aus `$lib/utils.js`
- Svelte 5 `Snippet`-Type

**Downstream (was uns nutzt nach Phase B):**
- Aktuell nur 8 Aufrufstellen (TripWizardShell, _design)
- Nach Phase B: alle 102 Stellen (existierende 8 + 94 migrierte)

## Risks & Considerations

1. **CSS-Spezifizität:** Die neuen Variants/Sizes-Selektoren müssen die gleiche Spezifizität haben wie die bestehenden, damit Overrides via `class`-Prop weiterhin greifen.
2. **Icon-Sizing:** Bestehende Btn-Aufrufstellen geben Icons via `<svg>` als Child. Das aktuelle CSS hat dafür keine Regel — wir müssen sie ergänzen, ohne die bestehenden 8 Aufrufstellen visuell zu brechen.
3. **`disabled`-Verhalten beim `<a>`-Switch:** Wenn `href` gesetzt UND `disabled` true, sollte der Link nicht navigieren (analog Button: `href={disabled ? undefined : href}` + `aria-disabled` + `tabindex={-1}`).
4. **Tailwind-Klassen via `class`-Prop:** Aufrufer könnten weiter Tailwind-Klassen über `class="text-sm w-full"` mitgeben. Das soll funktionieren — `cn(className)` macht das richtig.
5. **Test-Setup:** Vitest-Test-Setup für Svelte-Komponenten — schauen, ob es schon eines gibt (z.B. für `tripHero.test.ts`). Wahrscheinlich ja.
6. **LoC-Schätzung:**
   - `Btn.svelte`: +20 LoC (Props-Interface + href-Switch)
   - `index.ts`: +3 LoC
   - `app.css`: +50 LoC (CSS-Block ersetzen — 7 Variants × 8 Sizes + Disabled + Icon-Slot)
   - `Btn.test.ts`: +120 LoC
   - `_design/+page.svelte`: +30 LoC (Showcase erweitern)
   - `btn-feature-parity.spec.ts`: +80 LoC
   - **Summe ~300 LoC** — Override 350 vor Phase 6
7. **Existierende Btn-Aufrufer NICHT brechen:** Die 8 bestehenden Aufrufstellen mit `variant='accent'|'ghost'|'outline'` und `size='sm'|'md'|'lg'` müssen unverändert funktionieren.

## Open Decisions for Phase 2

| # | Frage | Empfehlung |
|---|---|---|
| D1 | Btn-`primary`-Variant Farbgebung? | `bg: var(--g-ink)`, `color: var(--g-paper)` — analog shadcn-default (dunkler Look) |
| D2 | Btn-`destructive`-Variant: starker Bg-Fill oder dezenter Tint? | Wie shadcn: dezenter Tint (`bg: rgba(179,58,42,0.10)`, `color: var(--g-danger)`). Klare Warnung ohne Aufdringlichkeit. |
| D3 | Showcase-Erweiterung in `_design`: alle Kombinationen oder Auswahl? | Repräsentative Auswahl (7 Variants × 1 Size + 1 Variant × 8 Sizes), nicht 56 Buttons |
| D4 | Test-Strategie: viele Snapshot-Tests oder gezielte Behavior-Tests? | Behavior-Tests (rendert als `<a>` wenn href, disabled blockiert Click, Variant-Klassen-Attribute korrekt). Keine Pixel-Snapshots. |
