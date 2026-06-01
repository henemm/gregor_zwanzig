# Context: Issue #520 — Organisms-Barrel vervollständigen

## Request Summary
Das Organisms-Barrel `organisms/index.ts` exportiert nur 4 von mindestens 9 Design-Organisms.
Fünf bereits fertige Svelte-Komponenten (WeatherMetricsTab, ChannelPreviewBlock, ChannelPreviewCard,
MetricGroup, MetricCheckbox) fehlen als Re-Exports — Consumer importieren sie direkt aus `trip-detail/`.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/organisms/index.ts` | Barrel — wird erweitert (5 neue Exports) |
| `frontend/src/lib/components/organisms/organisms.test.ts` | Smoke-Tests — wird erweitert |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Organism-Quelle; importiert KEINE `ui/` |
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | Organism-Quelle; importiert `$lib/components/ui/card/index.js` ⚠️ C2-Verstoß |
| `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte` | Organism-Quelle; importiert KEINE `ui/` |
| `frontend/src/lib/components/trip-detail/MetricGroup.svelte` | Organism-Quelle; importiert KEINE `ui/` |
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` | Organism-Quelle; importiert `$lib/components/ui/horizon-chip/index.js` ⚠️ C2-Verstoß |
| `docs/design-system/COMPONENTS.md` | Organisms-Sektion (Zeile 151–168) wird aktualisiert |
| `docs/specs/modules/epic_471_organisms_layer.md` | Ursprungs-Spec — zeigt Muster und Constraints |

## Existing Patterns
- **Barrel-Pattern** (Epic #471): Physische `.svelte`-Dateien bleiben in Feature-Ordnern, `organisms/index.ts`
  enthält nur Re-Exports. Kein Move.
- **Issue #475-Muster**: Bei `ui/`-Verstößen in Organisms → separates Folge-Issue für Migration (C3 schützt
  die Svelte-Files vor Änderungen in diesem Issue).
- **Source-Inspection-Tests** (node:test, keine Mocks): `organisms.test.ts` prüft per Regex auf Dateisystem,
  nicht per Runtime-Render.

## Constraints (aus Issue #520)
- **C1:** Keine physischen Datei-Moves — nur Barrel-Exports in `organisms/index.ts`
- **C2:** Organisms importieren nur aus `atoms/`, `molecules/` oder anderen `organisms/` (nie `ui/`)
  → **ChannelPreviewBlock** und **MetricCheckbox** verstoßen, bleiben aber unberührt (C3)
- **C3:** Keine API-Änderungen an Svelte-Komponenten — nur neue Re-Exports

## C2-Abweichungen (offen, out-of-scope für #520)
| Komponente | Verstoß | Folge-Issue nötig |
|---|---|---|
| `ChannelPreviewBlock.svelte` | `import * as Card from '$lib/components/ui/card/index.js'` | Ja (analog zu #475) |
| `MetricCheckbox.svelte` | `import { HorizonChip } from '$lib/components/ui/horizon-chip/index.js'` | Ja — HorizonChip existiert NUR in `ui/`, kein Atom-Export |

## Dependencies
- **Upstream:** `trip-detail/*.svelte` (Quellen bleiben unverändert)
- **Downstream:** Consumer (TripTabs, WeatherMetricsTab intern) importieren derzeit direkt aus `trip-detail/`;
  keine Pflicht-Migration laut AC-2

## Existing Specs
- `docs/specs/modules/epic_471_organisms_layer.md` — Ursprungs-Spec für Organisms-Schicht (Epic #471)

## Scope-Klarstellung: PresetRail
`PresetRow.svelte` existiert in `trip-detail/`. Ein eigenständiges `PresetRail.svelte` (Sidebar-Liste)
existiert nicht. AC enthält keine Anforderung dafür → out-of-scope für #520.

## Risks & Considerations
- Smoke-Tests für ChannelPreviewBlock/MetricCheckbox testen nur den Import (Export-Existenz), nicht
  die C2-Konformität — das ist korrekt, weil diese Regel für diese Komponenten bewusst ausgesetzt ist.
- `organisms.test.ts` enthält bereits den AC-2-Check für TripHeader, TripWizardShell, AlertRulesEditor.
  Die neuen Exports dürfen KEINEN AC-2-Check bekommen, solange die C2-Verstöße offen sind.
- HorizonChip ist NICHT im Atoms-Barrel — eine zukünftige Migration muss zuerst einen Atom anlegen.
