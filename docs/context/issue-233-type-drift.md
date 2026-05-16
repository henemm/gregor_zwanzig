# Context: Issue #233 — Type-Drift `activity_profile` Union

## Request Summary

Drei Stellen, die bei der Issue-#207-Migration auf strukturiertes Typing übersehen wurden:
1. `Location.activity_profile` (types.ts:9) — Union vermisst `'summer_trekking'`.
2. `Subscription.activity_profile` (types.ts:137) — gleiches Muster.
3. Spec-Codeblock `epic_135_step5_right_column.md:78,100,106,111` — zeigt veralteten Pre-#207-Lese-Pfad (`aggregation.activity_profile` mit `Record`-Cast statt `aggregation.profile` via typisiertes `Aggregation`).

Aufgedeckt vom Adversary-Validator während Issue #232 GREEN-Verifikation (Finding F001).

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/types.ts:9` | `Location.activity_profile` — Union erweitern um `'summer_trekking'` |
| `frontend/src/lib/types.ts:137` | `Subscription.activity_profile` — Union erweitern um `'summer_trekking'` |
| `frontend/src/lib/types.ts:68` | Kanonischer Typ `ActivityProfile` (Issue #207) — Referenz, wie es richtig aussieht |
| `docs/specs/modules/epic_135_step5_right_column.md` | §1 Blueprint-Codeblock (Zeilen 78, 100, 106, 111) auf `aggregation.profile` aktualisieren |
| `frontend/src/routes/compare/+page.svelte:732` | Konsument — TS-Error sollte durch Patch verschwinden |
| `frontend/src/lib/components/SubscriptionForm.svelte:44,90` | Liest/schreibt `Subscription.activity_profile` — kein Edit, aber profitiert von erweiterter Union |
| `frontend/src/lib/components/LocationForm.svelte:52,74` | Liest/schreibt `Location.activity_profile` — kein Edit, aber profitiert |
| `docs/specs/modules/activity_profile.md` | Single Source of Truth des kanonischen Enums |

## Existing Patterns

- **Kanonischer Typ existiert bereits:** `ActivityProfile = 'wintersport' | 'wandern' | 'allgemein' | 'summer_trekking'` in `types.ts:68` (Issue #207).
- **Best Practice:** Wo `activity_profile` getypt ist, sollte langfristig der `ActivityProfile`-Alias verwendet werden statt die Union inline zu duplizieren. Issue #233 fordert aber nur Minimal-Patch (Symmetrie zur bestehenden Stelle), kein Refactoring auf den Alias.
- **Trip.aggregation** ist seit #207 typisiert (`aggregation?: Aggregation`); das Pattern `(trip.aggregation as Record<string, unknown>)?.activity_profile` ist obsolet — Spec-Codeblock muss das spiegeln.

## Dependencies

- **Upstream:** Issue #207 (Strukturiertes Typing für Aggregation/WeatherConfig/ReportConfig) — hat den Trip-Pfad migriert.
- **Upstream:** Issue #232 (`rightColumn.ts` summer_trekking-Profil) — hat die Lücke im Trip-Aggregation-Pfad geschlossen.

## Dependents

- `SubscriptionForm.svelte`, `LocationForm.svelte`, `compare/+page.svelte` lesen/schreiben `activity_profile`; der Cast `as Subscription['activity_profile']` (compare/+page.svelte:732 → SubscriptionForm-Prop) ist der konkrete Type-Error den das Issue erwähnt.
- Keine Runtime-Konsumenten des Spec-Codeblocks — reine Doku.

## Existing Specs

- `docs/specs/modules/activity_profile.md` — Single Source of Truth des kanonischen Enums (4 Werte).
- `docs/specs/modules/issue_207_strukturiertes_typing.md` — Migration des `Trip.aggregation`-Pfades.
- `docs/specs/modules/epic_135_step5_right_column.md` — enthält den zu patchenden Blueprint-Codeblock.

## Risks & Considerations

- **Sehr geringer Scope** — 3 Edits, ~4 Zeilen Code + Spec-Patch. Reines Doku-/Type-Alignment.
- **Kein Runtime-Verhalten ändert sich** — nur TypeScript-Compiler sieht mehr.
- **Spec-Patch (§1 Blueprint):** Der Codeblock ist ein illustrativer Snippet, kein laufender Code. Aktualisierung nur, damit zukünftige Leser nicht den Pre-#207-Stand kopieren.
- **Keine neuen Tests nötig** — `rightColumn.test.ts` deckt den Trip-Pfad ab (durch #232 mit `summer_trekking` erweitert). Eine zusätzliche Type-Level-Check-Test könnte erwogen werden (z.B. `tsc --noEmit`-Snapshot), aber das übersteigt den Issue-Scope.
- **Konsistenz-Empfehlung:** Statt Union-Literal könnte man `ActivityProfile`-Alias verwenden — verschoben auf späteres Refactoring, bewusst hier außen vor (Issue beschreibt explizit nur Union-Erweiterung).
