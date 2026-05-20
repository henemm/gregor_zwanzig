# Context: Bug #269 — Mobile Trip-Detail-Tabs klippen/überläuft

## Request Summary
Auf Viewports < 900 px (z.B. 375 × 667) werden die 6 Tabs in TripTabs.svelte abgeschnitten und der lange Tab-Label „Etappen & Wegpunkte" bricht auf 2 Zeilen um. Ziel: Horizontal scrollbarer Pill-Scroller, alle Tabs erreichbar, Desktop (≥ 900 px) unverändert.

## Related Files

| Datei | Relevanz |
|-------|---------|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Haupt-Komponente — enthält `.trip-tabs-list` und `.trip-tab-trigger`; hier ist die Ursache |
| `frontend/src/routes/trips/[id]/+page.svelte` | Einziger Mount-Point von TripTabs |
| `frontend/src/app.css` | Definiert `@custom-variant mobile` (max-width: 899px) und `desktop` (min-width: 900px); Design-Token-Quelle |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | Referenz für `desktop:hidden`-Pattern (Issue #267) |

## Ursache (klar aus Code-Review)

In `TripTabs.svelte` Style-Block:
```css
:global(.trip-tabs-list) {
  display: flex;
  border-bottom: 1px solid var(--g-border, #ddd);
  /* FEHLT: overflow-x: auto; white-space: nowrap; */
}
:global(.trip-tab-trigger) {
  /* FEHLT: white-space: nowrap; flex-shrink: 0; */
}
```
→ Kein Breakpoint, kein `nowrap`, kein horizontales Scrolling.

## Existierende Mobile-Patterns

- `@custom-variant mobile { @media (max-width: 899px) }` und `desktop { @media (min-width: 900px) }` in `app.css`
- `BottomNav.svelte`: nutzt `class="... desktop:hidden"` (Tailwind Custom Variant)
- `EtappenStrip.svelte`: `class="flex flex-row gap-2 overflow-x-auto pb-2"` — einfaches horizontal-scroll Flex
- `app.css:153`: `.mobile-scroll-pad` — reserviert bereits Platz für Bottom-Nav beim Scrollen

## Design-System-Referenz

- `--g-accent` (`#c45a2a`) für aktiven Tab-Underline — bereits implementiert
- `--g-surface-2` für Pill-Hintergründe (optional, wenn Pills statt Underline-Tabs)
- `--g-radius-pill: 99rem` für Pills (Design-System, noch nicht in TripTabs genutzt)
- Issue #269 nennt "Pill-Scroller" als gewünschtes Muster

## Lösung (Scope)

Nur CSS-Änderung in `TripTabs.svelte`:
1. `.trip-tabs-list` auf Mobile: `overflow-x: auto; white-space: nowrap` + Scrollbar verstecken
2. `.trip-tab-trigger` auf Mobile: `white-space: nowrap; flex-shrink: 0`
3. Desktop (≥ 900 px): identisches Verhalten wie heute (kein Wrap möglich, da Labels kurz genug)

**Optional:** Pill-Optik (gefüllter Hintergrund statt nur Underline) für Mobile — erhöht visuelles Feedback des aktiven Tabs.

## Dependencies

- `bits-ui` `Tabs`-Primitive: rendert `role="tablist"` mit `:global()`-CSS-Klassen
- Keine Backend-Abhängigkeit
- Keine anderen Komponenten abhängig von `.trip-tabs-list`/`.trip-tab-trigger`

## Risks & Considerations

- `:global()` CSS in Svelte beeinflusst alle Elemente mit diesen Klassen — sicherstellen, dass Klassennamen eindeutig sind (✓ sind sie)
- Scrollbar auf Mobile-Browsern ausblenden ohne Funktionalität zu verlieren: `-webkit-scrollbar: none` + `scrollbar-width: none`
- `scroll-snap-type: x mandatory` + `scroll-snap-align: start` an Triggern — verbessert Touch-Scrolling
