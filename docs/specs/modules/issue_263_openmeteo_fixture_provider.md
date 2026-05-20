---
entity_id: issue_263_openmeteo_fixture_provider
type: module
created: 2026-05-20
updated: 2026-05-20
status: complete
version: "1.0"
issue: 263
tags: [go, provider, fixture, e2e, testing, openmeteo, playwright]
---

# Issue #263 — OpenMeteo Fixture Provider für E2E-Tests

## Approval

- [ ] Approved

## Purpose

Implementiert einen `FixtureProvider`, der statische `model.Timeseries`-JSON-Daten aus lokalen Fixture-Dateien lädt und damit das Interface `provider.WeatherProvider` erfüllt. Er wird aktiv, wenn die Umgebungsvariable `GZ_TEST_FIXTURE_DIR` gesetzt ist, und verhindert so, dass Playwright-E2E-Tests gegen das echte OpenMeteo-API stoßen und das kostenlose Tageslimit erschöpfen. In der Produktion (Variable nicht gesetzt) bleibt `openmeteo.NewProvider` der exklusive Provider — der FixtureProvider ist niemals geladen.

## Source

- **NEU:** `internal/provider/fixture/provider.go` — `FixtureProvider`-Struct + `NewProvider(dir string)` + `FetchForecast(lat, lon float64, hours int)` Implementierung (~90 LoC)
- **NEU:** `internal/provider/fixture/provider_test.go` — Integrationstests gegen die mitgelieferten Fixture-Dateien (~80 LoC)
- **NEU:** `fixtures/openmeteo/innsbruck.json` — 72 Datenpunkte, Alpine Winterwerte (T=2°C)
- **NEU:** `fixtures/openmeteo/stubai.json` — 72 Datenpunkte, Hochlagen-Werte (T=-5°C)
- **NEU:** `fixtures/openmeteo/zillertal.json` — 72 Datenpunkte, Talwerte (T=1°C)
- **EDIT:** `internal/config/config.go` — +1 Feld `TestFixtureDir string`
- **EDIT:** `cmd/server/main.go` — Provider-Selektion: FixtureProvider wenn `cfg.TestFixtureDir != ""`, sonst OpenMeteoProvider
- **EDIT:** `frontend/e2e/global.setup.ts` — 3 Test-Locations seeden + Teardown am Start
- **EDIT:** `frontend/e2e/start-preview.sh` — `.env.e2e` nach `.env` einlesen wenn vorhanden
- **NEU:** `.env.e2e` — `GZ_TEST_FIXTURE_DIR=fixtures/openmeteo` (committed, keine Secrets)
- **NEU:** `scripts/refresh-openmeteo-fixtures.sh` — Fixture-Dateien gegen lokalen Server mit echtem Provider neu generieren (~50 LoC)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherProvider` interface (`internal/provider/provider.go`) | intern | Definiert `FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error)` — FixtureProvider muss dieses Interface erfüllen |
| `model.Timeseries` (`internal/model/forecast.go`) | intern | Daten-Struct für den Rückgabewert; Fixture-JSON wird direkt in diesen Typ deserialisiert |
| `model.ForecastDataPoint` (`internal/model/forecast.go`) | intern | Einzelner Stundenpunkt im `Timeseries.Data`-Slice; alle Scoring-relevanten Felder müssen befüllt sein |
| `openmeteo.NewProvider` (`internal/provider/openmeteo/provider.go`) | intern | Bleibt der Default-Provider in Produktion; FixtureProvider ersetzt ihn nur bei gesetzter `TestFixtureDir` |
| `Config.TestFixtureDir` (`internal/config/config.go`) | intern | Neues Konfigurationsfeld; wird via `envconfig:"TEST_FIXTURE_DIR"` aus der Umgebung gelesen |
| `cmd/server/main.go` | intern | Einzige Stelle für Provider-Selektion; liest `cfg.TestFixtureDir` und instanziiert den richtigen Provider |
| `encoding/json` (Go-Stdlib) | extern | Deserialisierung der Fixture-JSON-Dateien in `model.Timeseries` |
| `math` (Go-Stdlib) | extern | Squared-Euclidean-Distanz-Berechnung für die Nearest-Location-Suche |
| `time` (Go-Stdlib) | extern | Re-Stamping aller Timestamps auf `time.Now().UTC().Truncate(24*time.Hour)` mit 1h-Inkrementen |
| `os` (Go-Stdlib) | extern | Lesen der Fixture-Dateien via `os.ReadFile` |
| `frontend/e2e/global.setup.ts` | intern | Seedet die 3 Test-Locations mit stabilen IDs; setzt GZ_TEST_FIXTURE_DIR voraus wenn Playwright läuft |
| `.env.e2e` | intern | Committed Environment-File (keine Secrets) mit `GZ_TEST_FIXTURE_DIR=fixtures/openmeteo` |

## Implementation Details

### §1 `internal/config/config.go` — Neues Feld

Einzige Änderung: ein Feld am Ende des `Config`-Structs ergänzen:

```go
TestFixtureDir string `envconfig:"TEST_FIXTURE_DIR" default:""`
```

Kein Default-Wert außer dem leeren String — ist die Variable nicht gesetzt, ist das Feld `""`, was in `main.go` als "kein Fixture-Modus" interpretiert wird.

### §2 `internal/provider/fixture/provider.go` — FixtureProvider

**Registry:** Hardcodierte Slice mit 3 Test-Locations und ihren relativen Datei-Namen:

```go
type fixtureLocation struct {
    Name string
    Lat  float64
    Lon  float64
    File string  // z.B. "innsbruck.json"
}

var testLocations = []fixtureLocation{
    {"Innsbruck", 47.2692, 11.4041, "innsbruck.json"},
    {"Stubai",    47.1015, 11.2958, "stubai.json"},
    {"Zillertal", 47.2190, 11.8767, "zillertal.json"},
}
```

**Struct:**

```go
type FixtureProvider struct {
    dir string  // absoluter oder relativer Pfad zum fixtures/-Verzeichnis
}

func NewProvider(dir string) *FixtureProvider {
    return &FixtureProvider{dir: dir}
}
```

**`FetchForecast`-Implementierung — 4 Schritte:**

1. **Nearest-Location-Suche:** Iteriert über `testLocations`, berechnet für jeden Eintrag `dLat*dLat + dLon*dLon` (keine Wurzel nötig). Wählt den Eintrag mit der kleinsten Summe.

2. **Datei lesen:** `os.ReadFile(filepath.Join(f.dir, nearest.File))` — gibt Fehler zurück wenn die Datei nicht existiert. Kein Caching: jeder `FetchForecast`-Aufruf liest frisch von Disk (Thread-Safety durch Verzicht auf shared mutable state).

3. **Deserialisierung:** `json.Unmarshal(data, &ts)` in eine lokale `model.Timeseries`-Variable.

4. **Re-Stamping:** Iteriert über `ts.Data` mit Index `i`, setzt:
   ```go
   ts.Data[i].Time = time.Now().UTC().Truncate(24*time.Hour).Add(time.Duration(i) * time.Hour)
   ```
   Dies verankert alle Zeitstempel am aktuellen UTC-Tag ohne die Fixtures je anfassen zu müssen.

5. **Truncation:** Gibt `ts.Data[:hours]` zurück (Cap auf `len(ts.Data)` wenn `hours > len`). Die Engine ruft stets mit `hours=72` auf; Fixtures haben genau 72 Punkte.

6. **Rückgabe:** `&ts, nil`

**Interface-Erfüllung:** `FixtureProvider` trägt keine `*`-Methode sondern Pointer-Receiver auf `FetchForecast` — identisch zu `openmeteo.Provider`. Compiler-Check via:
```go
var _ provider.WeatherProvider = (*FixtureProvider)(nil)
```

### §3 `cmd/server/main.go` — Provider-Selektion

Bestehende Instanziierung von `openmeteo.NewProvider(...)` wird in eine Bedingung eingebettet. Der neue Block ersetzt die bisherige einzelne Zeile:

```go
var weatherProvider provider.WeatherProvider
if cfg.TestFixtureDir != "" {
    weatherProvider = fixture.NewProvider(cfg.TestFixtureDir)
    log.Printf("[fixture] FixtureProvider aktiv — dir: %s", cfg.TestFixtureDir)
} else {
    weatherProvider = openmeteo.NewProvider(cfg.OpenMeteoBaseURL)
}
```

Der Log-Eintrag macht den Fixture-Modus beim Serverstart sichtbar und verhindert versehentliches Aktivieren in Produktion.

### §4 Fixture-JSON-Format

Alle drei Fixture-Dateien folgen exakt der `model.Timeseries`-JSON-Struktur:

```json
{
  "timezone": "Europe/Vienna",
  "meta": {
    "provider": "FIXTURE",
    "model": "fixture",
    "grid_res_km": 0
  },
  "data": [
    {
      "time": "2026-01-01T00:00:00Z",
      "t2m_c": 2.0,
      "wind10m_kmh": 15.0,
      "gust_kmh": 22.0,
      "precip_1h_mm": 0.1,
      "visibility_m": 9000,
      "cloud_total_pct": 40,
      "cape_jkg": 0,
      "uv_index": 1.2,
      "thunder_level": 0,
      "wmo_code": 2,
      "snow_depth_cm": 10.0,
      "dni_wm2": 250.0,
      "is_day": 1
    }
    ...
  ]
}
```

**Feldabdeckung:** Alle 13 Scoring-relevanten Felder müssen in jedem Datenpunkt vorhanden sein (`t2m_c`, `wind10m_kmh`, `gust_kmh`, `precip_1h_mm`, `visibility_m`, `cloud_total_pct`, `cape_jkg`, `uv_index`, `thunder_level`, `wmo_code`, `snow_depth_cm`, `dni_wm2`, `is_day`). Fehlende Felder würden Scoring-Profile mit Nullwerten befüllen und das Ranking verfälschen.

**Differenzierung der 3 Dateien:**

| Datei | T (°C) | Wind (km/h) | Schnee (cm) | Profil-Verwendung |
|-------|--------|-------------|-------------|-------------------|
| `innsbruck.json` | +2 | 15 | 5 | Hauptstandort Tal |
| `stubai.json` | -5 | 20 | 45 | Hochlage, Wintersport |
| `zillertal.json` | +1 | 18 | 8 | Tal mit mehr Wind |

Die 3 Dateien müssen messbar unterschiedliche Scores in mindestens einem Profil liefern, damit AC-1 (nicht-gleiche Scores bei Compare) testbar ist.

### §5 `internal/provider/fixture/provider_test.go` — Tests (keine Mocks)

**Test 1 — FetchForecast nahe Innsbruck:** Ruft `FetchForecast(47.27, 11.40, 72)` auf. Prüft: kein Fehler, genau 72 Datenpunkte, `ts.Data[0].Time` liegt heute (UTC) zwischen 00:00 und 01:00.

**Test 2 — FetchForecast nahe Stubai:** Ruft `FetchForecast(47.10, 11.30, 72)` auf. Prüft: nearest = Stubai (T2m_c == -5.0 für Index 0).

**Test 3 — Timestamp-Re-Stamping:** Ruft zweimal `FetchForecast` auf mit 1-Sekunden-Abstand. Prüft: `ts.Data[0].Time.Day()` == `time.Now().UTC().Day()` — der Tag-Anker ist stabil. Prüft außerdem `ts.Data[1].Time.Sub(ts.Data[0].Time) == time.Hour`.

**Test 4 — Thread-Safety:** Startet 10 Goroutinen, die gleichzeitig `FetchForecast` aufrufen. Prüft: kein Panic, alle 10 Ergebnisse haben `len(ts.Data) == 72`. (Race-Detector via `go test -race` deckt Datenwettbewerbe auf.)

**Test 5 — Ungültiges Verzeichnis:** Ruft `NewProvider("/nonexistent/path").FetchForecast(47.27, 11.40, 72)` auf. Prüft: Fehler ist nicht nil, Rückgabe ist nil.

### §6 `frontend/e2e/global.setup.ts` — Locations seeden

Am Anfang von `globalSetup` (vor anderen Setup-Schritten): DELETE aller Locations mit den IDs `e2e-loc-innsbruck`, `e2e-loc-stubai`, `e2e-loc-zillertal` via `DELETE /api/locations/{id}` (Fehler 404 ignorieren). Danach 3 POST-Requests gegen `POST /api/locations`:

```ts
const testLocations = [
  { id: "e2e-loc-innsbruck", name: "Innsbruck (E2E)", lat: 47.2692, lon: 11.4041 },
  { id: "e2e-loc-stubai",    name: "Stubai (E2E)",    lat: 47.1015, lon: 11.2958 },
  { id: "e2e-loc-zillertal", name: "Zillertal (E2E)", lat: 47.2190, lon: 11.8767 },
];
```

IDs werden als Teil des POST-Body übergeben (wenn die API Custom-IDs unterstützt) oder aus der Response entnommen und in `process.env` für die Tests gespeichert.

### §7 `frontend/e2e/start-preview.sh` — `.env.e2e` einlesen

Direkt nach dem bestehenden `source .env` (sofern vorhanden):

```bash
[ -f .env.e2e ] && source .env.e2e
```

Diese 3 Zeichen genügen, damit `GZ_TEST_FIXTURE_DIR` gesetzt ist wenn der Server für Playwright-Tests gestartet wird. Die Zeile muss VOR dem `go run`/`./gregor-api`-Aufruf stehen.

### §8 `scripts/refresh-openmeteo-fixtures.sh` — Fixture-Refresh

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8090}"
OUT_DIR="fixtures/openmeteo"

declare -A LOCATIONS=(
  ["innsbruck"]="47.2692,11.4041"
  ["stubai"]="47.1015,11.2958"
  ["zillertal"]="47.2190,11.8767"
)

mkdir -p "$OUT_DIR"

for name in "${!LOCATIONS[@]}"; do
  IFS=',' read -r lat lon <<< "${LOCATIONS[$name]}"
  echo "Fetching $name (lat=$lat, lon=$lon)..."
  curl -fsSL "${BASE_URL}/api/forecast?lat=${lat}&lon=${lon}&hours=72" \
    -o "${OUT_DIR}/${name}.json"
  echo "  -> ${OUT_DIR}/${name}.json aktualisiert"
done

echo "Alle 3 Fixture-Dateien aktualisiert."
```

Das Script läuft gegen den lokalen Server **ohne** `GZ_TEST_FIXTURE_DIR` gesetzt — nur so liefert `/api/forecast` echte OpenMeteo-Daten. Der Endpunkt `/api/forecast?lat=...&lon=...&hours=72` muss existieren und `model.Timeseries`-JSON zurückgeben.

### §9 LoC-Schätzung

| Datei | Inhalt | LoC |
|-------|--------|-----|
| `internal/provider/fixture/provider.go` | FixtureProvider + Registry + FetchForecast | ~90 |
| `internal/provider/fixture/provider_test.go` | 5 Testfälle | ~80 |
| `fixtures/openmeteo/innsbruck.json` | 72 Datenpunkte | ~150 |
| `fixtures/openmeteo/stubai.json` | 72 Datenpunkte | ~150 |
| `fixtures/openmeteo/zillertal.json` | 72 Datenpunkte | ~150 |
| `internal/config/config.go` | +1 Feld | +1 |
| `cmd/server/main.go` | Provider-Selektion | +10 |
| `frontend/e2e/global.setup.ts` | Seed-Logik | +30 |
| `frontend/e2e/start-preview.sh` | .env.e2e einlesen | +3 |
| `.env.e2e` | 1 Zeile | +1 |
| `scripts/refresh-openmeteo-fixtures.sh` | Refresh-Script | ~50 |
| **Summe Code (ohne JSON-Fixtures)** | | **~265 LoC** |

LoC-Override auf 300 setzen vor Implementierungsstart: `workflow.py set-field loc_limit_override 300`

## Expected Behavior

- **Input:** `FetchForecast(lat, lon float64, hours int)` — beliebige lat/lon-Koordinaten innerhalb der Alpen (oder beliebig weit entfernt — nearest-Lookup findet immer eine der 3 Locations). `hours` ist stets 72 in Produktionsaufrufen der Engine.
- **Output:** `*model.Timeseries` mit `hours` Datenpunkten. Timestamps beginnen am aktuellen UTC-Tag (00:00 UTC) und schreiten stündlich fort. Feldwerte entsprechen den jeweiligen Fixture-Dateien (Innsbruck/Stubai/Zillertal je nach Nearest-Lookup). Kein Netzwerk-Request.
- **Side effects:**
  - Kein Caching im FixtureProvider selbst — jeder Aufruf liest von Disk. Dies ist bewusst (Thread-Safety, minimale Komplexität; bei 72-Datenpunkt-Files vernachlässigbare I/O-Last).
  - Beim Serverstart mit `GZ_TEST_FIXTURE_DIR != ""` wird ein Log-Eintrag geschrieben; kein anderer Side-Effect auf das System.
  - Wenn `GZ_TEST_FIXTURE_DIR` nicht gesetzt ist: `FixtureProvider` wird nie instanziiert, kein Einfluss auf Laufzeitverhalten.

## Acceptance Criteria

**AC-1:** Given `GZ_TEST_FIXTURE_DIR=fixtures/openmeteo` ist gesetzt, When der Go-Server startet und `POST /api/compare/run` mit Locations nahe Innsbruck, Stubai und Zillertal aufgerufen wird, Then gibt die Compare-Engine ein `CompareResult` mit 3 Rows und nicht-null Scores zurück — ohne einen einzigen HTTP-Request an api.open-meteo.com zu stellen.
  - Test: (populated after /tdd-red)

**AC-2:** Given der FixtureProvider ist aktiv, When `FetchForecast` aufgerufen wird, Then sind alle zurückgegebenen Timestamps am aktuellen UTC-Tag verankert (erster Punkt = heute 00:00 UTC, zweiter = heute 01:00 UTC, usw.) — unabhängig davon, wann die Fixture-Dateien zuletzt neu generiert wurden.
  - Test: (populated after /tdd-red)

**AC-3:** Given der FixtureProvider ist aktiv und 3 Test-Locations sind via `global.setup.ts` geseedет, When die Playwright-E2E-Tests in `compare-main-stage.spec.ts` (AC-1 bis AC-4 dieses Specs) laufen, Then bestehen alle 4 Tests ohne OpenMeteo-API-Hits und ohne HTTP-429-Fehler.
  - Test: (populated after /tdd-red)

**AC-4:** Given `GZ_TEST_FIXTURE_DIR` ist NICHT gesetzt (Produktions-Default), When der Go-Server startet, Then wird ausschließlich `openmeteo.NewProvider` verwendet — `fixture.NewProvider` wird nie aufgerufen, kein Fixture-Log-Eintrag erscheint.
  - Test: (populated after /tdd-red)

**AC-5:** Given das Refresh-Script `scripts/refresh-openmeteo-fixtures.sh` gegen einen lokalen Server ohne `GZ_TEST_FIXTURE_DIR` ausgeführt wird, When das Script abgeschlossen ist, Then enthalten alle 3 Fixture-Dateien in `fixtures/openmeteo/` aktuelle OpenMeteo-Daten im `model.Timeseries`-JSON-Format mit mindestens 72 Datenpunkten.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Nur 3 Test-Locations:** Der FixtureProvider kennt ausschließlich Innsbruck, Stubai und Zillertal. E2E-Tests, die Locations außerhalb dieser 3 Koordinaten verwenden, erhalten Daten der geographisch nächstliegenden Fixture-Location — die Werte sind dann semantisch falsch (z.B. Tiroler Alpinwerte für eine Test-Location in Hamburg). Solche Tests müssen explizit mit den 3 seeded Test-Locations arbeiten.
- **Fixture-Datei-Format muss mit `model.Timeseries` synchron bleiben:** Wenn `model.Timeseries` neue Pflichtfelder erhält oder Feldnamen umbenennt, müssen die 3 JSON-Dateien manuell aktualisiert werden (oder via Refresh-Script neu generiert). Es gibt keinen automatischen Kompatibilitäts-Check.
- **Kein Caching im FixtureProvider:** Jeder `FetchForecast`-Aufruf liest von Disk. Bei sehr vielen parallelen Goroutinen (z.B. 50+ Locations in einem Compare) könnte die I/O-Last messbar werden. Im E2E-Kontext (3 Locations) ist das unkritisch.
- **`/api/forecast`-Endpunkt muss für Refresh-Script existieren:** Das Refresh-Script ruft `GET /api/forecast?lat=...&lon=...&hours=72` auf. Wenn dieser Endpunkt nicht existiert oder ein anderes Format zurückgibt, schlägt das Script fehl. Die Kompatibilität mit `model.Timeseries` muss manuell sichergestellt werden.
- **`global.setup.ts` Custom-IDs:** Die stabile Seedung mit IDs `e2e-loc-innsbruck` etc. setzt voraus, dass `POST /api/locations` Custom-IDs im Request-Body akzeptiert oder dass die API-Response-IDs persistent sind. Falls die API UUIDs auto-generiert, muss das Setup die IDs aus der Response speichern und in `process.env` oder einer Shared-Fixture-Datei für die Tests bereitstellen.

## Changelog

- 2026-05-20: Initial spec — Issue #263. FixtureProvider für E2E-Tests (OpenMeteo-Rate-Limit-Schutz): nearest-location-Lookup, Timestamp-Re-Stamping, 3 Fixture-Dateien (Innsbruck/Stubai/Zillertal), Config-Feld + main.go-Selektion, global.setup.ts-Seedung, .env.e2e, Refresh-Script. ~265 LoC (ohne JSON-Fixtures), LoC-Override auf 300 erforderlich.
