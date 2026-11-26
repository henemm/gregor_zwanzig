# svelte-check-Baseline Waisen S3 (#3385)

Spec: docs/specs/modules/rework_3385_waisen_s3.md (AC-8). Befehl (aus frontend/):
`npm run check -- --output machine` (= `svelte-kit sync && svelte-check --tsconfig ./tsconfig.json`).

## vorher

- Datum: 2026-11-26
- Stand: Branch rework-3385-waisen-s3, HEAD 67e4bda11 plus RED-Teständerungen (noch keine Datei gelöscht)
- Ergebnis: `COMPLETED 2241 FILES 32 ERRORS 71 WARNINGS 50 FILES_WITH_PROBLEMS`
- Fehler: 32
- Warnungen: 71

Keiner der 32 Fehler liegt in einer der 7 S3-Dateien oder in den geänderten Testdateien
(waisen_waechter.test.ts, trip_pfad_altfeld_loeschnachweis_3297.test.ts,
hub_geteilte_felder_cooldown_quiet_konsistent.test.ts, was_steht_wo_karte.test.ts).
Eine der 71 Warnungen liegt in einer S3-Datei (`VTLaufzeitVergleich.svelte` 26:37, state_referenced_locally);
sie entfällt mit der Löschung.

## nachher

(nach der Löschung eintragen; beide Zahlen dürfen nicht steigen)
