---
entity_id: rework_1215_dead_code_scheibe3
type: module
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.1"
tags: [cleanup, dead-code, go, compare-engine]
---

<!-- Issue #1215 — Scheibe 3 von 3 (letzte): Toten Code entfernen (Go-Compare-Engine + PresetHeader) -->

# Toten Code entfernen — Scheibe 3 (Go-Compare-Engine + PresetHeader)

## Approval

- [ ] Approved

## Purpose

Produktions-tote Go-Compare-Engine entfernen. Der produktive Orts-Vergleich
läuft komplett über den Python-Pfad
(`scheduler_dispatch_service` → `comparison_engine`); die Go-Route
`POST /api/compare/run` hat keinen einzigen Aufrufer (Nginx-Access-Log-Prüfung
über alle 15 Log-Dateien inkl. Staging: 0 Treffer). Die Go-Scoring-Logik hätte
zudem eine fachlich falsche Regel (temp_max höher=besser) — würde sie je aktiv
werden, lieferte sie falsche Ergebnisse. Letzte Scheibe von 3 (Scheibe 1 =
Python/Root, Scheibe 2 = Frontend-Wizard, beide abgeschlossen und live).

## Source

- **File:** `internal/compare/` (`cache.go`, `engine.go`, `scoring.go`,
  `types.go`, `score_toggle_test.go`, `scoring_test.go`) — **Go-API**,
  komplettes Paket wird gelöscht (1.517 LoC)
- **File:** `internal/handler/compare_run.go` + `compare_run_test.go` —
  **Go-API**, werden gelöscht (609 LoC)
- **File:** `internal/router/router.go` — Zeile 12 (Import `internal/compare`),
  Zeile 28 (`CompareEngine *compare.Engine` im `Deps`-Struct), Zeile 159
  (Route `r.Post("/api/compare/run", ...)`) — **Go-API**, werden entfernt
- **File:** `cmd/server/main.go` — Zeile 12 (Import `internal/compare`), Zeile
  76 (`compareEngine := compare.New(s, weatherProvider)`), Zeile 91
  (`CompareEngine: compareEngine` im `Deps`-Literal) — **Go-API**, werden
  entfernt
- **File:** `internal/compare/types.go` Zeilen 6-29 (`ActivityProfile`-Typ, 4
  `Profile*`-Konstanten, `validProfiles`, `IsValidProfile`) — **Go-API**,
  zieht VOR der Löschung nach `internal/model/activity_profile.go` um (echter
  Nutzer: Preset-CRUD)
- **File:** `internal/model/compare_preset.go` Zeilen 7-8 (Kommentar zum
  vermiedenen Import-Zyklus) — **Go-API**, wird nach dem Umzug angepasst
- **File:** `internal/handler/compare_preset.go` Zeilen 24, 66 (Import +
  Nutzung von `compare.IsValidProfile`/`compare.ActivityProfile`) —
  **Go-API**, wird auf `model.*` umgestellt
- **File:** `frontend/src/lib/components/compare/PresetHeader.svelte` —
  **Frontend**, wird gelöscht (0 Svelte/TS-Importer außerhalb von
  Struktur-Tests)
- **File:** `frontend/e2e/compare-main-stage.spec.ts` — **Frontend (E2E)**,
  wird gelöscht (testet ausschließlich den toten Run-Button-Flow, #251)
- **File:** `frontend/src/lib/issue_390_compare_atomic_migration.test.ts` —
  **Frontend**, nur die 3 PresetHeader-Tests (AC-2a, AC-2b, AC-5b) werden
  entfernt, Rest bleibt
- **File:** `frontend/src/lib/components/compare/issue_462.test.ts` —
  **Frontend**, `PresetHeader.svelte`-Eintrag wird aus `MIGRATED_FILES`
  entfernt
- **File:** `frontend/src/lib/components/shared/__tests__/legacy_wizard_removed.test.ts`
  — **Frontend**, Zeile 131 (Assertion „PresetHeader-Eintrag entfernt — der
  gehört zu Scheibe 3!") wird angepasst, da genau das jetzt in dieser Scheibe
  passiert (Fund während Recherche, s. Dependencies)

> **PFLICHT — Schicht-Hinweis:** Go-API-Änderungen betreffen ausschließlich
> `cmd/server/`, `internal/` (Production-API Port 8090); Frontend-Änderungen
> ausschließlich `frontend/src/...` (SvelteKit).

## Estimated Scope

- **LoC:** ca. -2.130 netto (Löschung: 1.517 LoC `internal/compare/` + 609 LoC
  `compare_run.go`+Test + `PresetHeader.svelte` + `compare-main-stage.spec.ts`,
  abzüglich ~24 LoC Umzug nach `internal/model/activity_profile.go`, die als
  Verschiebung nicht netto zählen, plus kleinere Test-Kürzungen)
- **Files:** 1 neue Datei (`internal/model/activity_profile.go`), 6
  Go-Dateien komplett gelöscht (`internal/compare/*`), 2 weitere Go-Dateien
  komplett gelöscht (`compare_run.go` + Test), 2 Go-Dateien editiert
  (`router.go`, `main.go`), 2 Go-Dateien mit Import-Umstellung
  (`compare_preset.go`, `model/compare_preset.go`-Kommentar), 2
  Frontend-Dateien komplett gelöscht (`PresetHeader.svelte`,
  `compare-main-stage.spec.ts`), 3 Frontend-Testdateien gekürzt/angepasst
  (`issue_390_compare_atomic_migration.test.ts`, `issue_462.test.ts`,
  `legacy_wizard_removed.test.ts`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/compare_preset.go` (Zeilen 24, 66, Preset-CRUD-Routen 180-186 in `router.go`) | Go-Handler | LIVE — einziger echter Nutzer von `compare.IsValidProfile`/`compare.ActivityProfile`; Import zieht auf `internal/model` um, Verhalten bleibt identisch |
| `internal/model/compare_preset.go` (Zeilen 7-8) | Go-Modell | Kommentar erklärt bisher den Import-Zyklus-Grund für string-Speicherung von `Profil` — wird nach dem Umzug angepasst (Zyklus existiert nicht mehr, `model` bleibt aber weiterhin string-basiert für Rückwärtskompatibilität der Persistenz) |
| `internal/router/router.go` (Zeilen 121, `WeatherProvider`-Feld) | Go-Router | `deps.WeatherProvider` wird weiterhin von `handler.ForecastHandler` genutzt — **bleibt unverändert**, nur `CompareEngine`-Feld + Route entfernt |
| `cmd/server/main.go` (Zeile 47-59, `weatherProvider`-Variable) | Go-Main | `weatherProvider` bleibt nach Entfernen von `compareEngine := compare.New(s, weatherProvider)` weiterhin genutzt (`WeatherProvider: weatherProvider` im `Deps`-Literal, Zeile 88) — **keine ungenutzte Variable**, nichts zusätzlich zu entfernen |
| `frontend/src/lib/components/shared/__tests__/legacy_wizard_removed.test.ts` (Zeile 128-132, Test „AC-8") | Frontend-Test | Aus Scheibe 2 (bereits live, Commit `d7703708`) — asserted bisher explizit, dass der `PresetHeader`-Eintrag in `issue_462.test.ts` **bleibt** ("der gehört zu Scheibe 3!"). Diese Scheibe macht genau das jetzt — die Assertion muss umgedreht werden, sonst bricht ein bereits lebender Test |
| `frontend/src/lib/components/compare/RecommendationBanner.svelte`, `CompareMatrix.svelte`, `HourlyMatrix.svelte` | Svelte-Komponenten | Explizit **NICHT** Teil dieser Scheibe — bleiben unverändert, auch wenn sie thematisch neben `PresetHeader` liegen |
| Python-Compare-Pfad (`scheduler_dispatch_service`, `comparison_engine`) | Python-Core | Explizit **NICHT** Teil dieser Scheibe — läuft komplett unabhängig vom Go-Pfad, produktiver Versandweg |
| `internal/handler/proxy.go` (`CompareProxyHandler`, Route `GET /api/compare` Zeile 158) | Go-Handler | Bleibt unverändert — Proxy auf den Python-Pfad, unabhängig vom toten Go-`compare`-Paket |

## Implementation Details

### 1. Umzug zuerst (vor der Löschung)

`internal/compare/types.go` Zeilen 6-29 (`ActivityProfile`-Typ, 4
`Profile*`-Konstanten, `validProfiles`-Map, `IsValidProfile`-Funktion) →
neue Datei `internal/model/activity_profile.go`, Package `model`:

```go
package model

// ActivityProfile enumerates the supported scoring profiles for a compare run.
type ActivityProfile string

const (
	ProfileWintersport    ActivityProfile = "WINTERSPORT"
	ProfileAlpineTour     ActivityProfile = "ALPINE_TOURING"
	ProfileSummerTrekking ActivityProfile = "SUMMER_TREKKING"
	ProfileAllgemein      ActivityProfile = "ALLGEMEIN"
)

var validProfiles = map[ActivityProfile]bool{
	ProfileWintersport:    true,
	ProfileAlpineTour:     true,
	ProfileSummerTrekking: true,
	ProfileAllgemein:      true,
}

// IsValidProfile reports whether p is a recognised profile value.
func IsValidProfile(p ActivityProfile) bool {
	return validProfiles[p]
}
```

`internal/handler/compare_preset.go` umstellen:
- Zeile 24 Import `"github.com/henemm/gregor-api/internal/compare"` entfernen
  (bereits `"github.com/henemm/gregor-api/internal/model"` importiert, Zeile
  26 — kein neuer Import nötig)
- Zeile 66:
  `compare.IsValidProfile(compare.ActivityProfile(normalizeProfile(p.Profil)))`
  → `model.IsValidProfile(model.ActivityProfile(normalizeProfile(p.Profil)))`

`internal/model/compare_preset.go` Zeilen 7-8 Kommentar anpassen: der
bisherige Grund („kein Import von internal/compare, um Zyklus zu vermeiden")
entfällt, da `internal/compare` nach dieser Scheibe nicht mehr existiert.
Neuer Kommentar hält fest, dass `Profil` weiterhin als `string` persistiert
wird (Persistenzformat unverändert, Validierung via `model.IsValidProfile()`
im Handler).

Die restlichen Typen in `types.go` (`CompareRequest`, `CompareTag`,
`RankingEntry`, `MatrixEntry`, `StundenVerlaufHour`, `StundenVerlaufEntry`,
`CompareResult`) haben außerhalb des toten Pfads keine Nutzer → sie sterben
mit dem restlichen Paket in Schritt 2.

### 2. Go löschen per Commit

- `internal/compare/` komplett: `cache.go`, `engine.go`, `scoring.go`,
  `types.go` (nach Umzug der 4 Symbole in Schritt 1), `score_toggle_test.go`,
  `scoring_test.go`
- `internal/handler/compare_run.go` + `internal/handler/compare_run_test.go`
- `internal/router/router.go`:
  - Zeile 12: Import `"github.com/henemm/gregor-api/internal/compare"`
    entfernen
  - Zeile 28: `CompareEngine *compare.Engine` aus dem `Deps`-Struct entfernen
  - Zeile 159: `r.Post("/api/compare/run", handler.CompareRunHandler(deps.CompareEngine))`
    entfernen
  - Alle übrigen Routen (u.a. Zeilen 180-186 Preset-CRUD, Zeile 158
    `GET /api/compare` Proxy) bleiben unverändert
- `cmd/server/main.go`:
  - Zeile 12: Import `"github.com/henemm/gregor-api/internal/compare"`
    entfernen
  - Zeile 76: `compareEngine := compare.New(s, weatherProvider)` entfernen
  - Zeile 91: `CompareEngine: compareEngine,` aus dem `router.Deps`-Literal
    entfernen
  - `weatherProvider` (Zeilen 47-59) bleibt bestehen — wird weiterhin über
    `WeatherProvider: weatherProvider` (Zeile 88) an `router.Deps` gereicht
    und von `handler.ForecastHandler` genutzt; **keine zusätzliche Löschung
    nötig**, da die Variable nach Entfernen von Zeile 76 nicht ungenutzt wird

### 3. Frontend löschen/anpassen per Commit

- `frontend/src/lib/components/compare/PresetHeader.svelte` löschen (0
  Svelte/TS-Importer im Produktivcode — einziger UI-Trigger
  `compare-preset-run-btn` der toten Route lebt hier)
- `frontend/e2e/compare-main-stage.spec.ts` löschen (testet ausschließlich den
  toten Run-Button-Flow, #251, alte Hauptbühne)
- `frontend/src/lib/issue_390_compare_atomic_migration.test.ts`: nur die 3
  Tests `'AC-2a: PresetHeader.svelte importiert Field aus molecules'`,
  `'AC-2b: PresetHeader.svelte verwendet <Field label=…> für die
  Einstellungsfelder'`, `'AC-5b: PresetHeader.svelte enthält keine rohen
  Label-Klassen mehr (text-sm font-medium auf <label>)'` entfernen; alle
  anderen Tests der Datei bleiben unverändert bestehen
- `frontend/src/lib/components/compare/issue_462.test.ts`: den
  `PresetHeader.svelte`-Eintrag (`{ path: join(COMPARE_DIR,
  'PresetHeader.svelte'), components: ['Btn'] }`) aus `MIGRATED_FILES`
  entfernen; restliche Einträge bleiben
- `frontend/src/lib/components/shared/__tests__/legacy_wizard_removed.test.ts`
  Zeile 128-132 (Test `'AC-8: issue_462.test.ts ohne NewLocationWizard-Eintrag,
  PresetHeader bleibt (Scheibe 3)'`): die Assertion
  `assert.ok(src.includes('PresetHeader'), 'PresetHeader-Eintrag entfernt —
  der gehört zu Scheibe 3!')` umdrehen zu
  `assert.ok(!src.includes('PresetHeader'), ...)`, da diese Scheibe den
  Eintrag jetzt tatsächlich entfernt. Testname/Kommentar entsprechend
  anpassen (kein „Scheibe 3 fehlt noch"-Hinweis mehr). Alle übrigen Tests der
  Datei (AC-1 bis AC-7, AC-10) bleiben unverändert — sie prüfen ausschließlich
  Scheibe-2-Inhalte, die von dieser Scheibe nicht berührt werden.

### 4. Invarianten (nichts tun, nur nachweisen)

- Preset-CRUD-Routen (`router.go` Zeilen 180-186: List/Get/Create/
  Update/Patch-State/Delete/Send) bleiben voll funktionsfähig — nur der
  Import in `compare_preset.go` wechselt von `compare.*` auf `model.*`,
  keine Verhaltensänderung
- `SendComparePresetHandler` (Python-Proxy, Zeile 375+ in
  `compare_preset.go`) bleibt unangetastet
- `RecommendationBanner.svelte`, `CompareMatrix.svelte`,
  `HourlyMatrix.svelte` bleiben bestehen — außerhalb des Scopes dieser
  Scheibe, nur die tote `PresetHeader`-Spec-Datei stirbt, nicht diese
  Komponenten
- Python-Compare-Pfad (`scheduler_dispatch_service` → `comparison_engine`)
  bleibt komplett unberührt
- `GET /api/compare` (Python-Proxy, `CompareProxyHandler`) bleibt unverändert
- `go build ./...` + `go vet ./...` + `go test ./internal/...` bleiben grün
- Frontend-Testsuite (`npm run test`) + Build (`npm run build`) bleiben grün

## Expected Behavior

- **Input:** Bestehender Go-Quellbaum mit totem `internal/compare/`-Paket,
  toter Route `POST /api/compare/run`, sowie Frontend mit
  `PresetHeader.svelte` + zugehörigen Struktur-Tests
- **Output:** `internal/compare/` existiert nicht mehr,
  `internal/handler/compare_run.go` + Test existieren nicht mehr,
  `internal/model/activity_profile.go` existiert neu mit `ActivityProfile`
  + `IsValidProfile`, `internal/handler/compare_preset.go` nutzt
  `model.IsValidProfile`/`model.ActivityProfile`, `router.go`/`main.go` ohne
  `compare`-Import/`CompareEngine`, `PresetHeader.svelte` +
  `compare-main-stage.spec.ts` existieren nicht mehr, Test-Dateien
  entsprechend angepasst
- **Side effects:** `POST /api/compare/run` liefert nach dem Deploy 404 (Route
  existiert nicht mehr im Router). Preset-CRUD (`GET/POST/PUT/PATCH/DELETE
  /api/compare/presets*`) funktioniert unverändert. Kein Import von
  `internal/compare` ist mehr möglich (Compile-Fehler, was erwünscht ist, da
  keine echten Aufrufer mehr existieren)

## Acceptance Criteria

- **AC-1:** Given `internal/compare/types.go` Zeilen 6-29
  (`ActivityProfile`-Typ, 4 `Profile*`-Konstanten, `validProfiles`,
  `IsValidProfile`) sind nach `internal/model/activity_profile.go`
  umgezogen und `internal/handler/compare_preset.go` nutzt `model.*` statt
  `compare.*` / When `go build ./...` und `go vet ./...` ausgeführt werden /
  Then kompiliert das Projekt fehlerfrei, und `internal/model/activity_profile.go`
  existiert mit `ActivityProfile`, den 4 `Profile*`-Konstanten und
  `IsValidProfile`
  - Test: `go build ./... && go vet ./...` Exit 0; `grep -n "func IsValidProfile" internal/model/activity_profile.go` liefert einen Treffer

- **AC-2:** Given `internal/compare/` (alle 6 Dateien) und
  `internal/handler/compare_run.go` + `compare_run_test.go` sind gelöscht /
  When im Repo nach Referenzen auf das Paket gesucht wird / Then existiert
  weder der Ordner `internal/compare/` noch `compare_run.go`/
  `compare_run_test.go`, und kein `.go`-File außerhalb der gelöschten
  Dateien importiert mehr `"github.com/henemm/gregor-api/internal/compare"`
  - Test: `test -d internal/compare` schlägt fehl; `test -f internal/handler/compare_run.go` schlägt fehl; `grep -rl "internal/compare\"" --include=*.go .` liefert keinen Treffer

- **AC-3:** Given `router.go` Zeile 12 (Import), Zeile 28 (`CompareEngine`-Feld)
  und Zeile 159 (Route) sowie `main.go` Zeile 12 (Import), Zeile 76
  (`compareEngine := compare.New(...)`) und Zeile 91 (`CompareEngine:`-Eintrag)
  sind entfernt / When dieser Stand auf Staging deployt wird und
  `POST /api/compare/run` aufgerufen wird / Then liefert die Route 404 oder
  405 (Route existiert nicht mehr im Chi-Router), und die restlichen Routen
  in `router.go` (insbesondere `GET /api/compare` Proxy und die
  Preset-CRUD-Routen 180-186) bleiben registriert und funktionieren
  - Test: `curl -i -X POST https://staging.gregor20.henemm.com/api/compare/run` liefert Status 404/405 nach Deploy

- **AC-4:** Given `weatherProvider` in `cmd/server/main.go` wird nach
  Entfernen von `compareEngine := compare.New(s, weatherProvider)`
  weiterhin über `WeatherProvider: weatherProvider` an `router.Deps`
  gereicht und von `handler.ForecastHandler` genutzt / When `go build ./...`
  ausgeführt wird / Then kompiliert das Projekt ohne „declared and not used"-Fehler
  für `weatherProvider`
  - Test: `go build ./...` Exit 0; `grep -n "WeatherProvider:" cmd/server/main.go` liefert weiterhin einen Treffer

- **AC-5:** Given diese Scheibe ist auf Staging deployt und der Umzug von
  `IsValidProfile`/`ActivityProfile` nach `internal/model` ist live / When
  ein Nutzer im Frontend einen bestehenden Compare-Preset öffnet, das
  Profil-Feld ändert und speichert / Then wird der Preset erfolgreich
  gespeichert (kein Validierungsfehler durch den Umzug), und beim erneuten
  Öffnen zeigt das Profil-Feld den neu gespeicherten Wert
  - Test: Staging-Klick-Test — bestehenden Compare-Preset öffnen, Profil-Feld
    (z.B. von „Allgemein" auf „Wintersport") ändern, speichern, Seite neu
    laden, geänderten Wert bestätigt sehen

- **AC-6:** Given `frontend/src/lib/components/compare/PresetHeader.svelte`
  und `frontend/e2e/compare-main-stage.spec.ts` sind gelöscht / When der
  Frontend-Build und die vitest-Suite laufen / Then existieren beide Dateien
  nicht mehr im Dateisystem, `npm run build` bleibt grün, und kein Code
  referenziert `PresetHeader.svelte` mehr außerhalb bereits angepasster
  Testdateien
  - Test: `test -f frontend/src/lib/components/compare/PresetHeader.svelte` schlägt fehl; `test -f frontend/e2e/compare-main-stage.spec.ts` schlägt fehl; `npm run build` Exit 0

- **AC-7:** Given in `issue_390_compare_atomic_migration.test.ts` sind nur die
  3 PresetHeader-Tests (AC-2a, AC-2b, AC-5b) entfernt / When die vitest-Suite
  läuft / Then laufen alle übrigen Tests der Datei unverändert grün, und
  kein Test der Datei referenziert `PresetHeader.svelte` mehr
  - Test: `grep -n "PresetHeader" frontend/src/lib/issue_390_compare_atomic_migration.test.ts` liefert keinen Treffer; `npm run test` Exit 0

- **AC-8:** Given in `issue_462.test.ts` ist der `PresetHeader.svelte`-Eintrag
  aus `MIGRATED_FILES` entfernt / When der Test ausgeführt wird / Then läuft
  er grün, ohne dass `PresetHeader.svelte` als Datei existieren muss
  - Test: `grep -n "PresetHeader" frontend/src/lib/components/compare/issue_462.test.ts` liefert keinen Treffer; Test läuft grün

- **AC-9:** Given `legacy_wizard_removed.test.ts` (Scheibe 2, bereits live)
  asserted bisher explizit, dass der `PresetHeader`-Eintrag in
  `issue_462.test.ts` bleibt („der gehört zu Scheibe 3!") / When diese
  Scheibe den Eintrag tatsächlich entfernt und die Assertion in
  `legacy_wizard_removed.test.ts` entsprechend umgedreht wird / Then läuft
  `legacy_wizard_removed.test.ts` weiterhin komplett grün (alle AC-1 bis
  AC-10-Tests dieser Datei), ohne dass ein zuvor bestehender Test durch
  diese Scheibe bricht
  - Test: `npm run test -- legacy_wizard_removed` Exit 0; `grep -n "gehört zu Scheibe 3" frontend/src/lib/components/shared/__tests__/legacy_wizard_removed.test.ts` liefert keinen Treffer mehr

- **AC-10:** Given `RecommendationBanner.svelte`, `CompareMatrix.svelte`,
  `HourlyMatrix.svelte` sowie der Python-Compare-Pfad und `GET /api/compare`
  (Proxy) werden von dieser Scheibe nicht angefasst / When diese Scheibe
  umgesetzt ist / Then bleiben alle drei Komponenten-Dateien byteidentisch
  unverändert, `GET /api/compare` liefert nach Deploy weiterhin die
  Python-Proxy-Antwort, und der Python-Versandpfad (Preset-Send,
  Scheduler-Dispatch) funktioniert unverändert
  - Test: `git diff` zu dieser Scheibe zeigt keine Änderung an den 3
    Komponenten-Dateien; `curl -i https://staging.gregor20.henemm.com/api/compare` liefert weiterhin einen Erfolgsstatus (kein 404)

- **AC-11:** Given die deterministische Go-Kern-Testsuite lief vor der
  Änderung grün / When `go test ./internal/...` nach dieser Scheibe erneut
  ausgeführt wird / Then bleibt sie zu 100% grün — insbesondere die
  Preset-CRUD-relevanten Tests in `internal/handler` — ohne dass
  `compare`-Paket-Tests (die mit dem Paket verschwinden) fehlen
  - Test: `go test ./internal/...` Exit 0

## Known Limitations

- Der Fund, dass `legacy_wizard_removed.test.ts` (Scheibe 2) eine Assertion
  enthält, die den `PresetHeader`-Eintrag als „gehört zu Scheibe 3" erwartet,
  wurde erst während der Recherche zu dieser Scheibe entdeckt — die
  Umkehrung dieser Assertion (AC-9) ist notwendiger Teil dieser Scheibe,
  nicht optional, sonst bricht ein bereits lebender Test.
- Die restlichen Typen in `internal/compare/types.go`
  (`CompareRequest`, `CompareTag`, `RankingEntry`, `MatrixEntry`,
  `StundenVerlaufHour`, `StundenVerlaufEntry`, `CompareResult`) werden
  ersatzlos gelöscht — sie sind ausschließlich vom toten `compare_run`-Pfad
  genutzt, kein Umzug nötig.
- Diese Scheibe ist die letzte von 3 (Issue #1215 Wartbarkeits-Audit
  2026-07); nach Abschluss ist kein weiterer Dead-Code-Abbau aus diesem
  Audit-Strang offen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Löschung toten Codes (0 produktive Aufrufer,
  Access-Log-verifiziert) plus ein Import-Umzug ohne Verhaltensänderung
  (`IsValidProfile` bleibt fachlich identisch) — kein ADR-würdiger
  Entscheidungsraum. Der Package-Umzug löst zudem einen zuvor dokumentierten
  Import-Zyklus-Workaround auf (Kommentar in `model/compare_preset.go`), was
  die Architektur vereinfacht statt sie zu ändern.

## Changelog

- 2026-07-11: Initial spec erstellt — Issue #1215, Scheibe 3 (letzte)
- 2026-07-11: v1.1 — Umsetzungs-Befund: Schwesterdatei
  `frontend/src/lib/components/compare/__tests__/issue_390_atomic_migration.test.ts`
  las ebenfalls PresetHeader.svelte (5 Tests) und fehlte in der Source-Liste;
  identisch zur gelisteten Datei behandelt (nur PresetHeader-Tests + ungenutzte
  Pfad-Konstante entfernt, Rest unverändert). Keine AC-Aufweichung.
