# Context: Issue #488 — CompareTile + CompareStatusPill + CompareKebab + compareActions

## Request Summary

Drei neue Molecule-Komponenten (`CompareTile`, `CompareStatusPill`, `CompareKebab`) und ein Helper `compareActions()` in `subscriptionHelpers.ts` — das Atom-Fundament (Block A) für Epic #485 (Orts-Vergleich Kachel-Grid + Detail + Home-Umbau). Blockiert B/C/D.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/compare/subscriptionHelpers.ts` | ERWEITERN: `compareActions()` hinzufügen; enthält bereits `CompareStatus`, `STATUS_MAP`, `deriveStatusFromPreset` |
| `frontend/src/lib/components/compare/CompareRow.svelte` | Referenz: nutzt `STATUS_MAP` + `Pill` + Lucide-Icons; zeigt bisheriges Aktions-Muster (Inline-Buttons) |
| `frontend/src/lib/components/compare/AutoReportCard.svelte` | Referenz: Kachel-ähnliche Darstellung mit `ui/card` (nutzt `Card.Root/Content`, nicht atoms/Card) |
| `frontend/src/lib/components/molecules/index.ts` | ERWEITERN: alle 3 Komponenten re-exportieren |
| `frontend/src/lib/components/molecules/StagePill.svelte` | Referenz-Molecule: Svelte 5 Props-Muster, state-gesteuert, inline-styles |
| `frontend/src/lib/components/atoms/Card.svelte` | atoms/Card: `accent`, `padding`, `class`, `...restProps`; border-left bei accent |
| `frontend/src/lib/components/atoms/Dot.svelte` | Bridge-Wrapper → `ui/dot/Dot.svelte` |
| `frontend/src/lib/components/atoms/Pill.svelte` | Bridge-Wrapper → `ui/pill/Pill.svelte` |
| `frontend/src/lib/components/atoms/Btn.svelte` | Bridge-Wrapper → `ui/btn/Btn.svelte`; Varianten: ghost/outline/primary; Größen: icon-sm etc. |
| `frontend/src/lib/components/atoms/index.ts` | Re-Export-Barrel aller Atoms |
| `frontend/src/lib/types.ts:445` | `ComparePreset`-Interface (id, name, location_ids, schedule, profil, hour_from, hour_to, empfaenger, letzter_versand) |
| `frontend/src/routes/trips/+page.svelte:403` | **Best-Practice-Referenz für CompareKebab**: `DropdownMenu` (bits-ui) mit `DropdownMenu.Root/Trigger/Content/Item/Separator` + `align="end"` + `sideOffset={4}` |
| `frontend/src/lib/components/compare/__tests__/subscriptionHelpers.test.ts` | Bestehende Tests — Muster für neue `compareActions`-Tests |

## Existing Patterns

- **Molecule-Stil:** Svelte 5, `$props()`, `$derived()`, inline `style:*`-Direktiven (kein `<style>`-Block außer bei komplexen CSS-Klassen), `data-testid` und `data-slot` für Tests
- **DropdownMenu:** `bits-ui` `DropdownMenu.Root/Trigger/Content/Item/Separator` — bereits etabliert in `trips/+page.svelte`. **CompareKebab** soll diese Komponenten intern kapseln.
- **stopPropagation:** Im Trigger-Snippet per `onclick={(e) => e.stopPropagation()}` verhindern, dass Kachel-Klick durchschlägt
- **Status-System:** `CompareStatus = 'active' | 'paused' | 'draft'` + `STATUS_MAP` bereits in `subscriptionHelpers.ts` — `CompareStatusPill` nutzt genau diese Werte
- **atoms/Card accent:** `border-left: 3px solid var(--g-accent)` ist bereits in `Card.svelte` implementiert (Prop `accent=true`). `CompareTile` kann `Card` als Wrapper nutzen oder das Pattern duplizieren.
- **Test-Muster:** Source-Inspection (kein Render, keine Mocks) mit `node:test` + `readFileSync` — identisch zu `molecules.test.ts` und `subscriptionHelpers.test.ts`

## Dependencies

**Upstream (was wir brauchen):**
- `atoms`: `Dot`, `Pill`, `Card`, `Btn` — alle bereits in `atoms/index.ts` vorhanden
- `bits-ui`: `DropdownMenu` — bereits im Projekt (genutzt in `trips/+page.svelte`)
- `@lucide/svelte`: Icons (PauseIcon, SendIcon, EyeIcon, PencilIcon, Trash2Icon, PlayIcon, EllipsisVerticalIcon) — bereits im Projekt
- `subscriptionHelpers.ts`: `CompareStatus`, `STATUS_MAP`, `deriveStatusFromPreset`, `presetLocationsLabel`, `presetScheduleLabel` — alle vorhanden

**Downstream (was uns blockiert):**
- `#485-B` CompareGrid: importiert `CompareTile`
- `#485-C` CompareDetail: importiert `CompareTile` + `CompareKebab`
- `#485-D` Home-Umbau: importiert `CompareTile` + `CompareStatusPill`

## Existing Specs

- `docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md` — Wizard-Kontext
- Keine dedizierte Spec für #488 — Issue-Body ist bereits sehr präzise (AC-1 bis AC-5 vorhanden)

## Design Tokens (relevant)

```
--g-accent:       #c45a2a   (border-left aktiv)
--g-ink-3:        #6b675c   (hover border-color)
--g-ink-4:        #9a958a   (disabled/muted)
--g-card:         #ffffff   (Kachel-Hintergrund)
--g-shadow-1:     leicht    (Default)
--g-shadow-2:     stärker   (Hover)
--g-rule:         #d8d3c2   (Standard-Border)
--g-r-3:          6px       (Standard Card-Radius)
```

## Risks & Considerations

1. **DropdownMenu Portal vs. Overflow:** Das bestehende `bits-ui`-Dropdown rendert ins DOM-Root (Portal) — overflow-hidden auf Eltern-Kacheln schneidet es nicht ab. Kein zusätzliches `portalTarget` nötig (läuft bereits korrekt in `trips/+page.svelte`).
2. **stopPropagation-Timing:** Muss im Trigger-Snippet (`{#snippet child({ props })}`) gesetzt werden, damit der Kachel-`onClick` nicht feuert.
3. **`compareActions` render-agnostisch:** Liefert nur Label + `id`-Strings zurück, keine Svelte-Snippets. Kann direkt in `subscriptionHelpers.ts` ohne Svelte-Kontext implementiert werden.
4. **Draft-Status:** `draft` → nur „Setup fortsetzen" + „Löschen" (keine Pause/Send-Optionen). Muss korrekt aus der `compareActions(status)`-Logik abgeleitet werden.
5. **`sub`-Prop auf `CompareTile`:** Der Issue nennt `sub` als ersten Prop — gemeint ist ein `ComparePreset`-Objekt (nicht `Subscription`). Naming-Konsistenz mit dem Rest des Compare-Stacks (der auf `ComparePreset` umgestellt ist).
