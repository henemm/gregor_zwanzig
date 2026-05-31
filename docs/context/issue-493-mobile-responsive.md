# Context: Issue #493 — feat(#485-E): Mobile-Responsive (Kachel-Stack, 2x2-Grid, MCompareActionSheet)

## Request Summary

Block E des Epic #485: Responsive-Anpassungen für alle Compare-Surfaces (Übersicht + Detail) plus ein neues Bottom-Sheet (`MCompareActionSheet`) für mobile Aktionen. Setzt Blöcke B und C voraus.

## ⚠️ Abhängigkeiten noch nicht erfüllt

| Issue | Titel | Status | Notwendig für |
|-------|-------|--------|---------------|
| #490 (Block B) | CompareGrid (Übersicht → Kachel-Grid) | **OPEN** | Mobile Kachel-Stack auf `/compare` |
| #491 (Block C) | `/compare/[id]` Detail-Seite | **OPEN** | Mobile TopAppBar + 2x2-Grid auf `/compare/[id]` |

`/compare/[id]/+page.svelte` existiert noch nicht — nur `/compare/[id]/edit/+page.svelte`.

**Entscheidung vor Implement nötig:** Entweder werden #490 + #491 im selben Workflow vorab implementiert, oder #493 wird erst nach deren Lieferung angegangen.

## Was zu tun ist (laut Issue-Body)

### 1. `/compare/+page.svelte` — ÄNDERN
- Mobil: vertikaler Kachel-Stack statt Grid (`CompareTile dense`)
- Chevron-Affordanz rechts auf jeder Kachel (Tap → Detail)
- Tap-Target mindestens 44 px

### 2. `/compare/[id]/+page.svelte` — ÄNDERN
- Mobil: TopAppBar mit Back · Name · Stift · ⋯
- `CompareStatusPill` + Kontextzeile unter TopBar
- Monitoring als 2x2-Grid statt horizontalem Streifen
- Setup-Cards: `CompareLocationRow dense`, `CompareIdealRow dense`, `CompareLayoutRow dense`
- ⋯ öffnet `MCompareActionSheet` (Bottom-Sheet)

### 3. `MCompareActionSheet.svelte` — NEU
- Bottom-Sheet mit `compareActions(status)`-Liste (identisch zum Desktop-Kebab)
- Sheet-Zeilen: 52 px Tap-Target

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/compare/+page.svelte` | ÄNDERN: mobiler Kachel-Stack |
| `frontend/src/routes/compare/[id]/+page.svelte` | ÄNDERN (muss erst erstellt werden durch #491) |
| `frontend/src/lib/components/mobile/MCompareActionSheet.svelte` | NEU: Bottom-Sheet |
| `frontend/src/lib/components/mobile/Sheet.svelte` | Basis für Bottom-Sheet (snap: full/half/peek) |
| `frontend/src/lib/components/mobile/TopAppBar.svelte` | Für mobile Detail-Header |
| `frontend/src/lib/components/compare/CompareTile.svelte` | `dense=true` für mobilen Stack |
| `frontend/src/lib/components/compare/CompareStatusPill.svelte` | Status-Badge |
| `frontend/src/lib/components/compare/CompareKebab.svelte` | Desktop-Kebab (Muster für Bottom-Sheet) |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | `compareActions(status)` → `CompareAction[]` |
| `frontend/src/lib/components/compare/CompareLocationRow.svelte` | dense-Variante für Setup-Cards |
| `frontend/src/lib/components/compare/CompareIdealRow.svelte` | dense-Variante für Setup-Cards |
| `frontend/src/lib/components/compare/CompareLayoutRow.svelte` | dense-Variante für Setup-Cards |
| `frontend/src/lib/components/mobile/index.ts` | Export-Barrel für mobile Komponenten |

## Existing Patterns

- **Bottom-Sheet:** `Sheet.svelte` in `mobile/` — Props: `open`, `onClose`, `title`, `eyebrow`, `snap`, `footer`, `children`. Wird nach `mobile/index.ts` exportiert.
- **TopAppBar:** `mobile/TopAppBar.svelte` — Thin-Wrapper auf `ui/sidebar/TopAppBar.svelte`; Props via spread `{...props}` + `mobileMenuOpen` bindable.
- **compareActions:** `subscriptionHelpers.ts` Zeile 107 — `compareActions(status: CompareStatus): CompareAction[]` liefert aktionsabhängige Liste (`{ id, label, danger? }`).
- **dense-Prop:** `CompareTile.svelte` hat bereits `dense=true` implementiert.
- **Tap-Target 44px:** Standard in allen mobilen Primitiven (MBtn, MTab etc.).
- **Kebab-Aktionen:** `CompareKebab.svelte` nutzt DropdownMenu (bits-ui); Bottom-Sheet ist das mobile Äquivalent.

## Dependencies

- **Upstream:** Sheet, TopAppBar, compareActions, CompareTile(dense), CompareStatusPill, CompareLocationRow/IdealRow/LayoutRow
- **Downstream:** nichts — reine Presentation-Layer-Änderung

## Existing Specs

- `docs/specs/modules/issue_488_compare_tile_atoms.md` — Block A: CompareTile, CompareKebab, CompareStatusPill
- `docs/features/epic-438-compare-wizard.md` — Orts-Vergleich Wizard (Überblick)

## Scope

- 1 neue Datei (`MCompareActionSheet.svelte`)
- 2 geänderte Dateien (`+page.svelte` × 2)
- ~130 LoC (laut Issue-Schätzung)

## Risks & Considerations

1. **Abhängigkeits-Blockade:** `/compare/[id]/+page.svelte` existiert nicht — muss vor #493 durch #491 angelegt werden.
2. **Breakpoint-Strategie:** Tailwind `sm:` / `md:` oder CSS `@media`? Projekt nutzt bisher Tailwind-Breakpoints.
3. **CompareGrid vs. Stack:** Übersicht braucht zuerst CompareGrid (#490), dann kann #493 den mobilen Stack hinzufügen.
4. **MCompareActionSheet Export:** Muss nach `mobile/index.ts` exportiert werden.
