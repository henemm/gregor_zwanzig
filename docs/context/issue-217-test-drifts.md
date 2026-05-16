# Context: Issue #217 — Test-Drifts `locations.spec.ts` + `trips.spec.ts`

## Request Summary

Zwei pre-existing Test-Drifts aus der Button-Migration (#215) aufgefunden:
1. **`locations.spec.ts`** (5 Failures) — Tests suchen Button `'Neue Location'`,
   Source rendert `'Neuer Ort'` (Terminologie-Update).
2. **`trips.spec.ts`** (2 Failures) — Tests verwenden alte Wizard-Selectoren
   (`[data-testid="trip-wizard"]`, `wizard-next`, `wizard-save`), die der neue
   Wizard nicht hat. Tests sind redundant zu 8 dedizierten Wizard-Test-Dateien.

## Related Files

| Datei | Zeilen | Inhalt |
|-------|--------|--------|
| `frontend/e2e/locations.spec.ts` | 21, 27, 37, 122 | 4 Stellen mit `'Neue Location'` |
| `frontend/src/routes/locations/+page.svelte` | 101 | `<Btn>Neuer Ort</Btn>` (aktueller Stand) |
| `frontend/e2e/trips.spec.ts` | 25-37, 39-74 | 2 Tests mit alten Wizard-Selectoren |
| `frontend/e2e/trip-wizard-*.spec.ts` (8 Files) | — | Dedizierte Wizard-Coverage (neuer Wizard) |

## Existing Patterns

- **Dialog-Title bleibt `'Neue Location'`** (`+page.svelte:176`) — Locations-Form-Dialog
  zeigt `'Neue Location'` als Title beim Create-Modus. UI-Konvention: Button-Action
  ist neuer Begriff (`'Neuer Ort'`), Dialog-Header verwendet alten Begriff. Tests
  prüfen Button-Action (via `getByRole('button')`), nicht Dialog-Title.
- **Wizard-Tests in `trip-wizard-*.spec.ts`** sind die kanonische Coverage seit Epic #136.

## Dependencies

- **Issue #190** (alter Wizard entfernen): wird `trips.spec.ts` ohnehin obsolet machen
  bzgl. der entfernten Wizard-Tests; wir nehmen das vorweg.

## Risks & Considerations

- **Locations-Fix:** 4-Zeilen-Replace, geringes Risiko.
- **Trips-Wizard-Tests entfernen:** Coverage bleibt erhalten via
  `trip-wizard-step1/2/3/4.spec.ts`, `trip-wizard-shell.spec.ts`. Keine
  Test-Lücke.
- **Idempotenz:** Die zu entfernenden Tests laufen aktuell rot — Entfernen
  verbessert das Bild.

## Scope

2 Files, ~50 LoC entfernt + 4 LoC ersetzt = netto ~-46 LoC.
