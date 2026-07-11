# Context: rework-1215-scheibe3-go

## Request Summary

Issue #1215, Scheibe 3 (letzte): Produktions-tote Go-Compare-Engine entfernen —
`internal/compare/`, Route `POST /api/compare/run`, Handler, `PresetHeader.svelte`,
`compare-main-stage.spec.ts`. Produktions-Compare läuft komplett über Python
(`scheduler_dispatch_service` → `comparison_engine`). Die Go-Scoring-Logik hätte
zudem FALSCHE Regeln (temp_max höher=besser) — wäre sie je aktiv, wären Ergebnisse falsch.

## Pflicht-Vorprüfung (Issue-Kommentar) — BESTANDEN 2026-07-11

`sudo zgrep -h "compare/run" /var/log/nginx/access.log*` über alle 15 Log-Dateien:
**0 Treffer** — sogar inklusive Staging. Kein Aufrufer, nirgends.

## Verifizierte Befunde (Worktree auf origin/main e677b23e)

### Go-Löschgut

| Was | Umfang |
|---|---|
| `internal/compare/` (cache.go, engine.go, scoring.go, types.go + 2 Testdateien) | 1.517 LoC |
| `internal/handler/compare_run.go` + `compare_run_test.go` | 609 LoC |
| `internal/router/router.go`: Zeile 159 (Route), Zeile 28 (`CompareEngine *compare.Engine` im Deps-Struct), Zeile 12 (Import) | 3 Stellen |
| `cmd/server/main.go`: Zeile 12 (Import), Zeile 76 (`compareEngine := compare.New(s, weatherProvider)`), Zeile 91 (Deps-Eintrag) | 3 Stellen — **prüfen:** wird `weatherProvider` danach noch anderweitig genutzt? Sonst mit entfernen (ungenutzte Variable = Go-Compile-Fehler) |

### Lebender Nutzer — Umzug VOR Löschung (analog Scheibe 2)

`internal/handler/compare_preset.go:24+66` (LIVE Preset-CRUD, Routen 180-186) nutzt
**nur** `compare.IsValidProfile()` + `compare.ActivityProfile`. Umzug:
`ActivityProfile`-Typ + 4 `Profile*`-Konstanten + `validProfiles` + `IsValidProfile`
(types.go Zeilen 6-29) → **neue Datei `internal/model/activity_profile.go`**
(model ist zyklusfrei: compare importierte model, nicht umgekehrt; Kommentar in
`model/compare_preset.go:7-8` zum vermiedenen Import-Zyklus wird damit obsolet → anpassen).
Die restlichen types.go-Typen (CompareRequest, RankingEntry, MatrixEntry, …) sind
nur vom toten Pfad genutzt → löschen.

### Frontend-Löschgut

- `compare/PresetHeader.svelte` — **0 Svelte/TS-Importer** (nirgends importiert);
  einziger UI-Trigger `compare-preset-run-btn` der toten Route lebt hier
- `frontend/e2e/compare-main-stage.spec.ts` — testet ausschließlich den toten
  Run-Button-Flow (#251, alte Hauptbühne) → löschen
- Dateiinhalt-Tests anpassen: `frontend/src/lib/issue_390_compare_atomic_migration.test.ts`
  (liest PresetHeader.svelte in AC-2a/2b/5b-Tests → diese Tests entfernen, Rest bleibt);
  `compare/issue_462.test.ts` (PresetHeader-Eintrag aus MIGRATED_FILES — diesmal in Scope)

### NICHT anfassen

- Preset-CRUD-Handler + Routen 180-186 (LIVE — nur der Import wird auf model umgestellt)
- `SendComparePresetHandler` (Python-Proxy, live)
- RecommendationBanner/CompareMatrix/HourlyMatrix-Komponenten (außerhalb des Issues;
  nur die Spec-Datei stirbt, nicht die Komponenten)
- Python-Compare-Pfad komplett

## Risks & Considerations

1. `go build ./...` + `go vet ./...` müssen grün sein — ungenutzte Imports/Variablen
   (weatherProvider!) sind harte Compile-Fehler
2. Preset-CRUD ist live: nach Umzug Staging-Klick-Test (Preset öffnen/speichern) + 
   `POST /api/compare/run` muss danach 404/405 liefern
3. Go-Tests: `go test ./internal/...` gezielt; compare-Tests verschwinden mit dem Paket
4. Deploy baut Go-Binary neu — Binary-Grep-Nachweis (String-Literal der Route weg)
