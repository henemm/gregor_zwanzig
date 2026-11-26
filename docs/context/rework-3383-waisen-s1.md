# Context: rework-3383-waisen-s1

## Request Summary
Scheibe S1 der Waisen-Löschung (#3383, Epic #3122, aus #3366). Gelöscht werden 15 Frontend-Dateien ohne Produktionsaufrufer: weather-metrics-tab, trip-detail, reportConfigDirty und GrundauswahlLeerHinweis, jeweils samt der Tests, die nur sie prüfen. Dazu kommt Finding F001 aus #3366: Der Selbstnachweis des Waisen-Wächters deckt bisher weder dynamischen Import noch `import.meta.glob`, `new URL(...)` oder `routes/`-Tests als Wurzel ab.

## Related Files
- Die vollständige Analyse mit Dateiliste S1, betroffenen Tests, Prüfständen f9/f10 und Ratschen steht in `docs/context/rework-3366-waisen-loeschen.md`, Abschnitte S1 und Analysis.
- Waisen-Wächter: `frontend/src/lib/__tests__/waisen_waechter.test.ts` (`BEKANNTE_WAISEN`, Gruppe S1, `OBERGRENZE_WAISEN=40`).
- Lösch-Nachweis: `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts`. Darin steht `outlookFriendlyCapability.ts` noch in `ERHALTEN`; die Datei wird mit S1 gelöscht und wechselt nach `GELOESCHT`.
- Ratschen:
  - `bausteine_waechter_regeln.ts` (BESTAND 184)
  - `tests/unit/ein_katalog_ausnahmen.json` und `test_ein_katalog_eine_verarbeitung_ratsche.py` (HOECHSTSTAND 433; laut Analyse betreffen S1 und S4 die 5 Einträge)
  - ink4
  - Reaktivitäts-Wächter
  - Katalogschlüssel-Verwender-Test

## Existing Patterns
Vorbild ist #3366 (PR #3386):
- Zahlen erst nach dem Löschen messen.
- Tests umbauen, wenn sie auch lebenden Code prüfen.
- Goldens nur mit dem Projektwerkzeug neu erzeugen.

## Risks & Considerations
- Die Prüfstände f9/f10 werden von vielen lebenden Tests genutzt. Nur die Teile zu den Waisen dürfen entfallen.
- Zahlenratschen hängen aneinander. Wie bei #3366 gilt: Die Obergrenze des Wächters sinkt um genau die gelöschte Zahl.
- `EinstellTabelle.svelte` gehört nicht zur Scheibe und wird nicht angefasst; daran arbeitet eine andere Sitzung.
