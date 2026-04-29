---
entity_id: wintersport_profile_consolidation
type: module
created: 2026-04-28
updated: 2026-04-28
status: draft
version: "1.0"
tags: [output, pipeline, refactor, epic-render-pipeline, wintersport]
epic: render-pipeline-consolidation (#96)
phase: β4
---

# Wintersport Profile Consolidation

**Status:** DRAFT
**Epic:** [#96 Render-Pipeline-Konsolidierung](https://github.com/henemm/gregor_zwanzig/issues/96)
**Phase:** β4

## Approval

- [ ] Approved

## §1 Zweck

`src/formatters/wintersport.py` (`WintersportFormatter`, 240 LoC) wird **ersatzlos eliminiert**.
Die zwei produktiven Aufrufer in `src/app/cli.py` (Compact-SMS-Pfad und Long-Report-Pfad)
werden auf die in β1+β3 etablierte Pipeline migriert:

```
DailyForecast/NormalizedForecast
        │
        ├──► build_token_line(profile="wintersport")     (β1)
        │           │
        │           ├──► render_sms(token_line)          (β3) ─► SMS ≤160 Zeichen
        │           └──► render_text_report(token_line, …) (NEU β4) ─► Long-Report (Plain-ASCII)
```

Wintersport ist nach β4 **kein eigener Formatter-Zweig mehr**, sondern ein Profile-Flag
(`Literal["wintersport"]`) in der zentralen Pipeline. Das öffnet die Tür für weitere
Sportarten (Bergsteigen, Klettern, MTB) als zusätzliche `Profile`-Werte ohne neue
Renderer-Dateien (siehe §A6).

**Hard Constraints (User-Vorgabe 2026-04-28):**

1. **Keine Information geht verloren.** Alle Inhalte aus `format_compact()` und `format()`
   müssen in den neuen Pfaden weiterhin produzierbar sein (Compact: AV/WC/SFL/SN/SN24+ +
   Standard-Forecast-Tokens; Long-Report: Header, Zusammenfassung, Wegpunkt-Details,
   Lawinenregionen).
2. **Architektur muss erweiterbar sein.** Neue Sportarten ergänzen das `Profile`-Literal +
   Token-Set; sie führen **nicht** zu neuen Dateien unter `src/output/renderers/`.

## §2 Scope

### In-Scope

- Ersatzlose Löschung von `src/formatters/wintersport.py` und der Re-Export-Zeile in
  `src/formatters/__init__.py`.
- Migration `src/app/cli.py:223–225` (Compact) auf `build_token_line(profile="wintersport")`
  + `render_sms()`.
- Migration `src/app/cli.py:228` (Long-Report) auf eine neue Pipeline-Funktion
  `render_text_report(token_line, …)` (siehe §4 / §6).
- Expliziter Adapter `_trip_result_to_normalized()` für die Typ-Impedanz zwischen
  `TripForecastResult`/`AggregatedSummary` und `NormalizedForecast`/`DailyForecast`
  (siehe §5).
- Migration / Streichung der Tests in `tests/test_formatters.py`
  (`TestWintersportFormatter`-Klasse).
- Validation des Goldens `tests/golden/sms/arlberg-winter-morning.txt` gegen die
  migrierte Compact-Pipeline (bit-identisch — der Golden ist heute bereits gegen
  `build_token_line(profile="wintersport")` eingefroren, siehe β1-Spec).

### Out-of-Scope (ausdrücklich verschoben)

- Provider-Befüllung von `DailyForecast.avalanche_level` (eigenes Issue; β4 testet mit
  Fixture-Daten).
- Harmonisierung der Doppel-Enums `app.trip.ActivityProfile` (`WINTERSPORT |
  SUMMER_TREKKING | CUSTOM`) und `app.user.LocationActivityProfile` (`WINTERSPORT |
  WANDERN | ALLGEMEIN`) — beide Enums werden weder konsolidiert noch verschoben.
- Web-UI Wintersport-Scoring in `src/web/compare.py`.
- Integration weiterer Sportarten — β4 etabliert nur die Erweiterungspunkte; neue Profile
  (Bergsteigen, Klettern, MTB) sind eigene Issues.
- Refactor `compare_subscription.py` (β5).

## §3 Datenmodell-Änderungen

### §3.1 Profile-Literal bleibt unverändert

`src/output/tokens/dto.py::Profile` bleibt:

```python
Profile = Literal["standard", "wintersport"]
```

Der Wert `"wintersport"` ist seit β1 etabliert. β4 fügt **kein** neues Literal hinzu —
neue Sportarten werden in eigenen Issues an der Pipeline ergänzt (siehe §A6).

### §3.2 Keine neuen DTOs

`DailyForecast` enthält bereits seit β1 alle Wintersport-Felder
(`avalanche_level`, `wind_chill_c`, `snowfall_limit_m`, `snow_depth_cm`,
`snow_new_24h_cm`). Keine Änderungen am DTO.

### §3.3 Adapter-Datenstruktur (intern, kein DTO)

`_trip_result_to_normalized()` produziert ein `NormalizedForecast`-Objekt. Die Funktion
ist intern in `src/output/adapters/trip_result.py` (NEU), exportiert nicht öffentlich.
Sie ist deterministisch und pure (keine Side Effects, keine I/O).

## §4 Verträge / API

### §4.1 Compact-Pfad (CLI `--compact`)

```python
# Adapter (intern, NEU)
def _trip_result_to_normalized(result: TripForecastResult) -> NormalizedForecast: ...

# Pipeline-Aufruf in cli.py
forecast = _trip_result_to_normalized(result)
config   = _wintersport_default_config()                  # MetricSpec-Liste, β4-Helper
token_line = build_token_line(
    forecast,
    config,
    report_type=settings.report_type,                     # "morning" | "evening"
    stage_name=result.trip.name,
    profile="wintersport",
)
body    = render_sms(token_line, max_length=160)
subject = body                                            # wie bisher: Compact-Body == Subject
```

### §4.2 Long-Report-Pfad (CLI default, kein `--compact`)

Ein neuer Renderer-Eintrittspunkt wird unter `src/output/renderers/text_report/` etabliert:

```python
# src/output/renderers/text_report/__init__.py (NEU)
def render_text_report(
    token_line: TokenLine,
    *,
    waypoint_details: list[WaypointDetail],   # rein Daten, keine SegmentWeatherData
    summary_rows: list[tuple[str, str]],       # ("Temperatur", "-15.0 bis -5.0°C") etc.
    avalanche_regions: tuple[str, ...] = (),
    report_type: ReportType,
    trip_name: str,
    trip_date: str,                            # ISO-Date als String
) -> str:
    """Long-Report im Plain-ASCII-Format mit Header, Zusammenfassung, Wegpunkten.

    Pure function. Output ist deterministisch.
    """
```

`WaypointDetail` ist eine kleine, lokale `@dataclass(frozen=True)` mit Feldern
`id`, `name`, `elevation_m`, `time_window`, `lines: tuple[str, …]` — keine Domain-DTOs.
Der Adapter (CLI) baut sie aus `WaypointForecast`.

### §4.3 Designentscheidung: neuer `render_text_report` statt Erweiterung von `render_email`

| Option | Bewertung |
|---|---|
| `render_email(profile="wintersport")` erweitern | **Verworfen.** `render_email` produziert (HTML, Plain) aus `SegmentWeatherData` — eine Trip-Stage-Struktur, die der Wintersport-CLI-Pfad nicht hat. Wintersport-Long-Report hat keine HTML-Form, keine Etappen-Tabellen, keine Highlights-Sektion. Eine Erweiterung würde `render_email` aufblähen mit Wintersport-spezifischer Verzweigungslogik und gegen §A5 der β3-Spec verstoßen ("Render-Module bleiben pure Templates"). |
| Neuer Pfad `render_text_report(...)` | **Gewählt.** Klarer Vertrag, eigener Output-Typ (`str`, kein Tuple), eigener Daten-Vertrag (waypoint-orientiert statt segment-orientiert). Bleibt unter `src/output/renderers/`, also im Pipeline-Geviert. Einfach um neue Profile erweiterbar (§A6). |

**Begründung:** Die Daten-Form unterscheidet sich grundlegend (Etappen mit `SegmentWeatherData` vs. Trip-Wegpunkte mit Time-Windows). `render_email` ist ein E-Mail-Channel-Renderer, nicht ein Plain-Text-Long-Report-Renderer. Die symmetrische Erweiterung `render_text_report` ist die saubere Trennung zwischen Channel und Format.

### §4.4 Public-API-Bruch

`from formatters.wintersport import WintersportFormatter` ist **nach β4 unmöglich**.
Grep zeigt nur CLI- und Test-Importer; kein externer Service oder Workflow nutzt die
Klasse. Es wird **kein Adapter-Stub** zurückgelassen (Constraint: "Keine Adapter-Stubs"
aus dem Task-Briefing).

## §5 Prozesse / Workflows

### §5.1 Typ-Impedanz als Kern-Implementierungsarbeit

`format_compact()` / `format()` konsumieren heute `TripForecastResult` →
`AggregatedSummary` (waypoint-aggregierte Min/Max-Werte mit `source_waypoint`).

`build_token_line()` braucht `NormalizedForecast` → `DailyForecast` (tagesbezogene
hourly-Samples + Single-Value-Felder).

**Adapter-Verantwortung:**

| Quell-Feld (`AggregatedSummary`/`WaypointForecast`) | Ziel-Feld (`DailyForecast`) | Aggregations-Regel |
|---|---|---|
| `summary.temp_min.value` | `temp_min_c` | direkt |
| `summary.temp_max.value` | `temp_max_c` | direkt |
| `summary.snow_depth.value` | `snow_depth_cm` | direkt |
| `summary.snow_new.value` | `snow_new_24h_cm` | direkt |
| `summary.snowfall_limit.value` | `snowfall_limit_m` | direkt |
| `summary.wind_chill.value` | `wind_chill_c` | direkt |
| `summary.precipitation.value` (mm gesamt) | `rain_hourly` | als Single-Sample bei Stunde 12 (Default-Stunde, da `AggregatedSummary` keine Stunde kennt) |
| `summary.wind.value` | `wind_hourly` | als Single-Sample bei Stunde 12 |
| `summary.gust.value` | `gust_hourly` | als Single-Sample bei Stunde 12 |
| (keine Quelle) | `pop_hourly` / `thunder_hourly` | leer (`()`), Tokens werden zu `PR-` / `TH:-` |
| (kein direktes Feld) | `avalanche_level` | aus `result.trip.avalanche_regions` ableiten ist **nicht** möglich; Adapter setzt `None`. **Out-of-Scope-Notiz:** Provider-Befüllung folgt in eigenem Issue. |

**Konsequenz:** Hourly-Tokens (R/PR/W/G) erscheinen mit Stunde `@12` als Default-Anker.
Das ist **eine bewusste Vereinfachung** — `AggregatedSummary` enthält keine Stunde, nur
Min/Max-Werte. Das alte `WintersportFormatter.format_compact()` zeigt diese Tokens
*ohne* Stunde (`W45`, `R0.2`); die migrierte Pipeline zeigt `W45@12(...)` etc. Dieser
Unterschied wird vom Golden-Vergleich in §A3 gefangen — entweder Golden bleibt bit-
identisch (Adapter mappt korrekt) oder Golden wird kontrolliert neu eingefroren.

**Hinweis zum existierenden Golden:** `tests/golden/sms/arlberg-winter-morning.txt`
ist **bereits gegen `build_token_line(profile="wintersport")` mit synthetischer
NormalizedForecast eingefroren** (β1 §Golden-Master-Tests, Profil 4). Der Test
verwendet nicht den Adapter `_trip_result_to_normalized`; er nutzt direkt einen
synthetischen `NormalizedForecast`. β4 behält diesen Test unverändert grün und ergänzt
einen separaten Test, der den Adapter-Pfad (`_trip_result_to_normalized`) gegen einen
äquivalenten Golden prüft (siehe §A3).

### §5.2 Workflow Compact-Pfad

1. CLI lädt Trip via `load_trip(args.trip)`.
2. `TripForecastService.get_trip_forecast(trip)` liefert `TripForecastResult`.
3. **NEU:** `forecast = _trip_result_to_normalized(result)` (Adapter §5.1).
4. **NEU:** `config = _wintersport_default_config()` produziert die Standard-`MetricSpec`-
   Liste für Wintersport (alle Wintersport-Tokens enabled, keine Friendly-Form).
5. **NEU:** `token_line = build_token_line(forecast, config, report_type=…,
   stage_name=trip.name, profile="wintersport")`.
6. **NEU:** `body = render_sms(token_line, max_length=160)`; `subject = body`.
7. `channel.send(subject, body)`.

### §5.3 Workflow Long-Report-Pfad

1. Schritt 1–5 wie Compact-Pfad.
2. **NEU:** `waypoint_details = [_waypoint_to_detail(wf) for wf in result.waypoint_forecasts]`
   (Adapter, intern in `src/output/adapters/trip_result.py`).
3. **NEU:** `summary_rows = _summary_to_rows(result.summary)` — produziert die
   formatierten Zeilen (`("Temperatur", "-15.0 bis -5.0°C (Gipfel)")`) wie heute
   `WintersportFormatter._format_summary` sie produziert.
4. **NEU:** `body = render_text_report(token_line, waypoint_details=…, summary_rows=…,
   avalanche_regions=trip.avalanche_regions, report_type=settings.report_type,
   trip_name=trip.name, trip_date=str(trip.start_date))`.
5. `subject = f"GZ {settings.report_type.title()} - {trip.name}"` (unverändert wie
   heute).
6. `channel.send(subject, body)`.

## §6 Architektur-Diagramm (Soll-Zustand nach β4)

```
┌────────────────────────────────────────────────────────────────────┐
│                          src/app/cli.py                            │
│                                                                    │
│   _run_trip_report(args, settings, provider, debug)                │
│           │                                                        │
│           ├── result = TripForecastService(...).get_trip_forecast │
│           │                                                        │
│           ├── forecast = _trip_result_to_normalized(result)        │
│           │   (NEU: src/output/adapters/trip_result.py)            │
│           │                                                        │
│           ├── token_line = build_token_line(forecast, config,      │
│           │       profile="wintersport", report_type=...)          │
│           │   (β1 unverändert)                                     │
│           │                                                        │
│           ├── if args.compact:                                     │
│           │       body = render_sms(token_line, max_length=160)    │
│           │       (β3 unverändert)                                 │
│           │                                                        │
│           └── else:                                                │
│                   waypoint_details = [_waypoint_to_detail(wf) ...] │
│                   summary_rows     = _summary_to_rows(summary)     │
│                   body = render_text_report(token_line, ...)       │
│                   (NEU: src/output/renderers/text_report/)         │
│                                                                    │
│   ───────── ENTFERNT: from formatters.wintersport import ... ────  │
└────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────┐
│ src/output/renderers/                │
│   ├── email/    (β3 unverändert)     │
│   ├── sms/      (β3 unverändert)     │
│   └── text_report/   ⬅ NEU β4        │
│        └── __init__.py               │
│            render_text_report(...)   │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ src/output/adapters/  ⬅ NEU β4       │
│   └── trip_result.py                 │
│        _trip_result_to_normalized    │
│        _waypoint_to_detail           │
│        _summary_to_rows              │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ ── ENTFERNT ──                       │
│ src/formatters/wintersport.py        │
│ (240 LoC, ersatzlos)                 │
└──────────────────────────────────────┘
```

## §7 Fehlerbehandlung

| Bedingung | Verhalten |
|---|---|
| `result.summary` enthält ausschließlich `None`-Werte (alle `AggregatedValue.value is None`) | Adapter produziert `NormalizedForecast` mit `DailyForecast()`-Defaults; `build_token_line` erzeugt Null-Form-Tokens (`N-`, `D-`, …). Kein Exception. |
| `result.waypoint_forecasts == []` | `_waypoint_to_detail` liefert leere Liste; `render_text_report` schreibt "WEGPUNKT-DETAILS" mit leerer Body-Sektion. |
| `result.trip.avalanche_regions == ()` | Block "LAWINENREGIONEN" wird komplett weggelassen (analog heute). |
| `forecast.days == ()` | `build_token_line` wirft `ValueError` (β1-Vertrag). Adapter garantiert mindestens einen `DailyForecast` (auch leer befüllt) — Aufrufer-Fehler. |
| `args.compact` und `report_type=alert` | Out-of-Scope für β4 (Alert-Pfad ist eigene Code-Bahn, siehe `format_alert_sms`-Diskussion in β3-Spec §A4). |

## §8 Tests

Pflicht-Test-Manifest: `docs/specs/tests/wintersport_profile_consolidation_tests.md`
(Schwester-Spec, parallel verfasst).

### §8.1 Unit-Tests

| Test | Asserts |
|---|---|
| `tests/unit/test_trip_result_adapter.py::adapter_produces_normalized_forecast` | `_trip_result_to_normalized(result)` liefert `NormalizedForecast` mit `temp_min_c`, `temp_max_c`, `wind_chill_c`, `snow_depth_cm`, `snow_new_24h_cm`, `snowfall_limit_m` aus `summary` befüllt |
| `tests/unit/test_trip_result_adapter.py::adapter_handles_all_none_summary` | All-None-Summary → DailyForecast-Defaults, kein Exception |
| `tests/unit/test_trip_result_adapter.py::adapter_pure_function` | Zwei Aufrufe mit identischem `result` → identische `NormalizedForecast` (Determinismus) |
| `tests/unit/test_renderers_text_report.py::renders_header_summary_waypoints` | Output enthält Trip-Name (UPPERCASE), Datum, "ZUSAMMENFASSUNG", "WEGPUNKT-DETAILS" |
| `tests/unit/test_renderers_text_report.py::renders_avalanche_block_when_regions` | `avalanche_regions=("AT-7",)` → Block "LAWINENREGIONEN" enthält `AT-7` |
| `tests/unit/test_renderers_text_report.py::omits_avalanche_block_when_empty` | `avalanche_regions=()` → kein "LAWINENREGIONEN"-Block |
| `tests/unit/test_renderers_text_report.py::pure_function` | Zwei Aufrufe mit identischen Inputs → bit-identische Strings |

### §8.2 Golden-Tests

| Test | Asserts |
|---|---|
| `tests/golden/sms/test_sms_golden.py::golden_arlberg_winter_morning` (vorhanden) | unverändert grün — direkter `build_token_line(profile="wintersport")` Pfad bleibt von β4 unberührt |
| `tests/golden/text_report/test_text_report_golden.py::golden_stubaier_skitour_evening` (NEU) | `render_text_report(...)` Output bit-identisch zu `tests/golden/text_report/stubaier-skitour-evening.txt` (Snippet-Erwartungen aus heutigem `WintersportFormatter.format()`-Output abgeleitet, ggf. um Token-Zeile am Anfang ergänzt) |

### §8.3 Integration / CLI

| Test | Asserts |
|---|---|
| `tests/test_formatters.py` | **Komplette Streichung** der `TestWintersportFormatter`-Klasse. Datei kann leer werden (oder ganz gelöscht — Phase 5 entscheidet). |
| `tests/integration/test_cli_wintersport.py::cli_compact_uses_pipeline` (NEU) | CLI mit `--trip <wintersport.json> --compact` produziert Output, der durch `render_sms` gegangen ist (Format-Assertion: `Stage:` Prefix, kein `T-15/-5`-Legacy-Form) |
| `tests/integration/test_cli_wintersport.py::cli_long_report_contains_all_sections` (NEU) | CLI ohne `--compact` produziert Output mit `ZUSAMMENFASSUNG`, `WEGPUNKT-DETAILS`, ggf. `LAWINENREGIONEN`, plus Token-Zeile (Soll-Snippets dokumentiert) |

### §8.4 Adversary-Test

Verifikation: Implementation-Validator-Agent erhält den Auftrag,
- den Adapter mit Edge-Case-Inputs zu brechen (alle-None, einzelne `None`-Felder, sehr
  große Werte, negative Höhen),
- den Long-Report-Renderer mit leeren Wegpunkten und ungültigem `report_type` zu testen,
- zu prüfen, dass `WintersportFormatter` nirgends mehr importiert wird (`grep -r
  WintersportFormatter src tests` liefert null Treffer).

## §9 Akzeptanzkriterien (β4-Phase)

### §A1 — `wintersport.py` ist gelöscht

- `src/formatters/wintersport.py` existiert nach β4 **nicht mehr** im Repo.
- Kein Adapter-Stub, kein leeres Modul, kein Re-Export. `git ls-files | grep
  formatters/wintersport.py` ist leer.

### §A2 — `formatters/__init__.py` exportiert `WintersportFormatter` nicht mehr

- `__all__` enthält `WintersportFormatter` nicht mehr.
- Die Datei `src/formatters/__init__.py` enthält keine `import`-Zeile zu
  `wintersport`. Sie kann komplett geleert werden, falls keine anderen Exports nötig
  sind.

### §A3 — Compact-Pfad bit-identisch gegen Golden

- Der bestehende Golden-Test
  `tests/golden/sms/test_sms_golden.py::test_golden_arlberg_winter_morning` bleibt
  **unverändert grün**. (Dieser Test geht direkt durch `build_token_line` ohne den
  Adapter.)
- **Neuer Test:** Ein Integration-Test prüft, dass der CLI-Compact-Pfad
  (`_trip_result_to_normalized` + `build_token_line` + `render_sms`) gegen einen
  äquivalenten synthetischen Trip ein Output liefert, das die Wintersport-Tokens
  enthält (`AV…`, `SN…`, `WC…`, `SFL…`, `SN24+…`) und ≤160 Zeichen ist.

### §A4 — Long-Report-Pfad: alle Wintersport-Informationen verfügbar

- Output von `render_text_report(...)` enthält für einen Wintersport-Trip mit
  `avalanche_regions=("AT-7",)` und Wegpunkten mit `wind_chill_c=-28`, `wind=45`,
  `gust=70`:
  - **Header:** Trip-Name in UPPERCASE, `start_date`, `report_type` als Titel.
  - **Zusammenfassung:** Temperatur-Bereich, Wind Chill, Wind, Böen, Niederschlag,
    Neuschnee, Schneehöhe, Schneefallgrenze, Sicht, Bewölkung — analog heutiger
    `_format_summary()`.
  - **Wegpunkt-Details:** je `Waypoint` ID, Name, Höhe in `m`, Time-Window, Werte aus
    `ForecastDataPoint[0]`.
  - **Lawinenregionen:** Liste mit der Notiz "(Lawinendaten noch nicht implementiert)"
    (wie heute — Out-of-Scope für β4).
  - **Token-Zeile (NEU):** Am Anfang oder Ende des Reports steht das
    `render_sms(token_line)`-Output als Wintersport-Token-Zeile. **Dies ist neu
    gegenüber heute** (`WintersportFormatter.format()` zeigt keine Token-Zeile) und ist
    eine bewusste Anreicherung, weil sie die Pipeline-SSOT manifest macht. Phase 5
    entscheidet die Position (oben/unten); Spec lässt das offen.
- **Snippet-Tests:** drei dedizierte Asserts (`assert "ZUSAMMENFASSUNG" in body`,
  `assert "AT-7" in body`, `assert "Wind Chill" in body or "WC" in body`) sichern den
  Inhalts-Erhalt.

### §A5 — `render_text_report` akzeptiert Profile-Param implizit über TokenLine

- `render_text_report(token_line, …)` arbeitet **profile-agnostisch**: das `Profile`
  steckt bereits in der `token_line` (über die `category="wintersport"`-Tokens, die
  `build_token_line` injiziert hat). Der Renderer fragt **nicht** nach `profile`.
- Konsequenz: Eine Erweiterung um Bergsteigen / Klettern / MTB ändert
  `_wintersport(...)` (oder fügt ein paralleles `_climbing(...)` hinzu) in
  `src/output/tokens/builder.py` — **ohne** dass `render_text_report` angefasst wird.

### §A6 — Profile-Erweiterbarkeit dokumentiert

- Die Spec dokumentiert in §6 und §A5, wie eine neue Sportart integriert wird:
  1. Neuen `Profile`-Wert ergänzen: `Profile = Literal["standard", "wintersport",
     "climbing"]`.
  2. Neue Token-Funktion `_climbing(day, by_sym, rt) -> list[Token]` in
     `src/output/tokens/builder.py` schreiben.
  3. In `build_token_line` Branch ergänzen: `if profile == "climbing":
     tokens.extend(_climbing(today, by_sym, report_type))`.
  4. Tokens in `POSITIONAL` und `PRIORITY` registrieren.
  5. **Keine** neue Datei unter `src/output/renderers/`.
- Ein Doc-Beispiel in der Spec selbst (siehe §11.2) demonstriert das Vorgehen.

### §A7 — LoC-Budget

- Netto **−90 LoC oder besser**, gemessen über `git diff --stat HEAD~1`.
  - Streichungen: `wintersport.py` (−240), `formatters/__init__.py`-Eintrag (−2),
    `tests/test_formatters.py::TestWintersportFormatter` (~−170 inkl. Fixture).
  - Hinzu: `_trip_result_to_normalized` + Helper (~+80), `render_text_report` (~+100),
    neue Tests (~+150).
  - Erwartung: Saldo **−80 bis −120 LoC**. Phase 5 misst exakt.

## §10 Implementierungs-Reihenfolge

(Phase 5/6, hier nur Reihenfolge — kein Code-Inhalt; siehe Test-Spec für RED-Plan.)

1. RED: Test-Manifest aus
   `docs/specs/tests/wintersport_profile_consolidation_tests.md` umsetzen, alle Tests
   schreiben (Adapter, Renderer, CLI-Integration). Tests fehlen oder fail-by-import.
2. GREEN-Schritt 1: `src/output/adapters/trip_result.py` schreiben
   (`_trip_result_to_normalized`, `_waypoint_to_detail`, `_summary_to_rows`,
   `_wintersport_default_config`). Unit-Tests grün.
3. GREEN-Schritt 2: `src/output/renderers/text_report/__init__.py` schreiben.
   Renderer-Unit-Tests + Golden grün.
4. GREEN-Schritt 3: `src/app/cli.py` umstellen (Imports, Pipeline-Aufrufe).
   Integration-Tests grün.
5. GREEN-Schritt 4: `src/formatters/wintersport.py` löschen,
   `src/formatters/__init__.py` aufräumen, `tests/test_formatters.py` löschen
   oder leeren.
6. Adversary-Validation (Implementation-Validator-Agent).
7. Validation: `python3 .claude/validate.py`, `uv run pytest`, E2E-Test (CLI-Aufruf
   mit echtem Wintersport-Trip).

## §11 Migrationsstrategie

### §11.1 Big-Bang-Streichung statt Adapter-Stub

Anders als β2 / β3, die Adapter-Patterns für Public-API-Stabilität nutzen, wird
`WintersportFormatter` **ersatzlos entfernt**. Begründung:

- Grep `from formatters.wintersport` im gesamten Repo (Production + Tests) liefert
  ausschließlich Treffer in `src/app/cli.py`, `src/formatters/__init__.py` und
  `tests/test_formatters.py` — alle drei werden in β4 angefasst.
- Es gibt keinen externen Service / Workflow / Skript, der die Klasse importiert.
- Die β1/β2/β3-Adapter dienten der Kompatibilität mit ~87 bestehenden Formatter-Tests.
  Solche Test-Last existiert für `WintersportFormatter` nicht (9 Tests, alle in einer
  Datei, alle migrierbar oder löschbar).

Das Task-Briefing ist explizit: "Keine Adapter-Stubs". β4 folgt dieser Vorgabe.

### §11.2 Erweiterung um neue Sportart (Doc-Beispiel)

Beispiel: Bergsteigen mit zusätzlichen Tokens `FRZ` (Frostgrenze) und `EXP` (Exposition).

```python
# 1. Profile-Literal erweitern
# src/output/tokens/dto.py
Profile = Literal["standard", "wintersport", "alpinism"]

# 2. Token-Funktion in builder.py
def _alpinism(day, by_sym, rt):
    pairs = [("FRZ", day.frost_limit_m), ("EXP", day.exposure_score)]
    out = []
    for sym, val in pairs:
        if not _visible(by_sym.get(sym), rt) or val is None: continue
        out.append(Token(sym, render_int(val), "alpinism", PRIORITY[sym]))
    return out

# 3. Branch in build_token_line
if profile == "alpinism":
    tokens.extend(_alpinism(today, by_sym, report_type))

# 4. POSITIONAL/PRIORITY registrieren — fertig.
```

`render_sms`, `render_email`, `render_text_report` bleiben unverändert. Bergsteigen
fließt automatisch durch dieselbe Pipeline.

### §11.3 Existierende `arlberg-winter-morning.txt`-Golden

Bleibt unverändert. Der zugehörige Test in `test_sms_golden.py` baut die
`NormalizedForecast` direkt aus synthetischen `DailyForecast`-Werten — er touchiert den
Adapter nicht. β4 ergänzt einen separaten Adapter-Test mit eigenen Fixtures.

## §12 Risiken

1. **Adapter-Daten-Verlust durch Aggregations-Mismatch.** `AggregatedSummary` ist
   waypoint-aggregiert, `DailyForecast` ist tagesbasiert. Zeitstempel werden verloren
   (nur Stunde `@12` als Default). **Mitigation:** Snippet-Tests in §A4 prüfen
   Inhaltserhalt; Token-Zeilen-Test prüft, dass alle Wintersport-Tokens erscheinen.
   Die Stunde `@12` ist akzeptable Vereinfachung, weil das alte
   `WintersportFormatter.format_compact()` ohnehin keine Stunde lieferte.
2. **`avalanche_level` in `AggregatedSummary` nicht vorhanden.** Adapter setzt `None`,
   `AV`-Token fehlt im Output. **Mitigation:** Out-of-Scope dokumentiert; Provider-
   Befüllung in eigenem Issue. Test mit Fixture, die `avalanche_level` direkt in
   `DailyForecast` injiziert, deckt den positiven Fall ab.
3. **Long-Report-Format-Drift gegen heutige Plain-ASCII-Form.** `render_text_report`
   muss Header-Stil, Separatoren, Sektion-Reihenfolge und Wegpunkt-Layout
   reproduzieren. **Mitigation:** Plain-ASCII-Golden (§A4) und Snippet-Asserts
   (`ZUSAMMENFASSUNG`, `WEGPUNKT-DETAILS`, `AT-7`). Jede strukturelle Abweichung
   knallt im Golden-Vergleich.
4. **`render_text_report` als neue Datei verwässert Pipeline-Klarheit.** β3 etablierte
   `email/` und `sms/` als Channel-Renderer; `text_report/` ist semantisch eher ein
   Format-Renderer. **Mitigation:** Klare Doku in der Spec; falls in einer späteren
   Phase `text_report` zum E-Mail-Plain-Body wandert, ist der Refactor lokal.
5. **Big-Bang-Löschung bricht externe Importer.** **Mitigation:** Vor der Löschung
   `grep -r "from formatters.wintersport" src tests scripts` mit null Treffern
   bestätigen.

## §13 Out-of-Scope (verschoben)

Siehe §2 In-Scope/Out-of-Scope-Block. Insbesondere:

- Provider-Befüllung von `DailyForecast.avalanche_level` (eigenes Issue).
- Doppel-Enum-Harmonisierung `ActivityProfile` ↔ `LocationActivityProfile`.
- Web-UI Wintersport-Scoring in `compare.py`.
- `compare_subscription.py` Migration (β5).

## §14 Referenzen

| Quelle | Bezug |
|---|---|
| `docs/specs/_template.md` | Template-Struktur |
| `docs/specs/modules/output_token_builder.md` v1.1 | β1, liefert `build_token_line` und `Profile`-Literal |
| `docs/specs/modules/output_subject_filter.md` v1.0 | β2, Subject-Filter (β4 unberührt) |
| `docs/specs/modules/output_channel_renderers.md` v1.0 | β3, Vorbild-Struktur und `render_sms`/`render_email`-Verträge |
| `docs/reference/sms_format.md` v2.0 §3.6 | SSOT für Wintersport-Tokens |
| `docs/specs/wintersport_extension.md` | Alt — überholt durch β4 |
| `docs/specs/tests/wintersport_profile_consolidation_tests.md` | Test-Manifest (Schwester-Spec) |
| `docs/context/beta4-wintersport-consolidation.md` | Phase-1-Kontext-Output |
| GitHub Issue #96 | Epic Render-Pipeline-Konsolidierung |

## Changelog

- 2026-04-28: Initial spec for β4 Wintersport-Profile-Konsolidierung. Designentscheidung:
  neuer `render_text_report(...)` Pipeline-Zweig (statt Erweiterung von `render_email`),
  expliziter Adapter `_trip_result_to_normalized` für Typ-Impedanz,
  ersatzlose Löschung von `WintersportFormatter` (kein Adapter-Stub).
