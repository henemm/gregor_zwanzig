# Context: rework-3384-waisen-s4

## Request Summary
Scheibe S4 der Waisen-Löschung (#3384, Epic #3122, aus #3366): Gelöscht werden die Frontend-Dateien ohne Produktionsaufrufer aus compare, edit, mobile, utils und WaypointPin. Das ist genau die Gruppe S4 in `BEKANNTE_WAISEN` (laut Wächter 19 Einträge, laut Issue 18; maßgeblich ist die Wächterliste). Mit den Dateien fallen die Tests weg, die nur sie prüfen.

Dazu kommen die Adversary-Findings aus #3383:
- F001: Die Obergrenze wird an die Listenlänge gebunden.
- F002: Die Array-Sperre greift auch für `import.meta.glob<T>([...])`.
- F004: Kommentare, die noch auf `ThresholdMetricRow` verweisen, werden bereinigt.

## Related Files
- Analyse S4: `docs/context/rework-3366-waisen-loeschen.md`.
- Waisen-Wächter: `frontend/src/lib/__tests__/waisen_waechter.test.ts` (`BEKANNTE_WAISEN` Gruppe S4, `OBERGRENZE_WAISEN=26`).
- Lösch-Nachweis: `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts`.
- Python-Tests mit Waisenpfaden: `test_trip_alert_stage_name`, `test_issue_316_docs_cleanup`.
- Doku: `docs/reference/frontend_components.md`.
- Ratschen: BESTAND (`bausteine_waechter_regeln.ts`, 177), `ein_katalog` (430), ink4, Reaktivität, Katalogschlüssel-Verwender, Elementliste.

## Existing Patterns
Vorbild sind #3366 (PR #3386) und #3383 (PR #3387):
- Zahlen werden erst nach dem Löschen gemessen.
- Tests, die auch lebenden Code prüfen, werden umgebaut statt gelöscht.
- Goldens und die Elementliste werden nur mit dem Projektwerkzeug erzeugt.
- Die svelte-check-Baseline wird vor dem Löschen gemessen.

## Risks & Considerations
- `WaypointPin.svelte` ist laut #3383 noch ERHALTEN (`ERHALTEN_3383`). Vor dem Löschen erneut prüfen, ob die Datei Waise ist.
- `EinstellTabelle.svelte` und `.claude/hooks` nicht anfassen. Browser-Specs gehören zu #3374.
