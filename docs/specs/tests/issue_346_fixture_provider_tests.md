---
entity_id: issue_346_fixture_provider_tests
type: tests
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [tests, python, provider, fixture, offline, openmeteo, issue-346]
parent: issue_346_fixture_provider_e2e
phase: phase5_tdd_red
---

# Issue #346 — Python Fixture-Provider (Test-Manifest)

## Approval

- [x] Approved

## Purpose

Test-Manifest für den Python-Fixture-Provider aus
`docs/specs/modules/issue_346_fixture_provider_e2e.md`. Jeder Test mappt 1:1 auf
ein Acceptance Criterion der Parent-Spec. Geprüft werden Protocol-Erfüllung,
Provider-Selektion via `GZ_TEST_FIXTURE_DIR`, Prod-Schutz, Offline-Fetch,
Timestamp-Verankerung, der conftest-Mechanismus und der `live`-Marker-Opt-out.

Parent-Spec: `docs/specs/modules/issue_346_fixture_provider_e2e.md` v1.0

## Source

- **File (Python):** `tests/tdd/test_issue_346_fixture_provider.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_fixture_provider_satisfies_protocol` | AC-1 | `FixtureProvider` erfüllt das `@runtime_checkable` `WeatherProvider`-Protocol; `name == "openmeteo"`. |
| `test_ac2_get_provider_returns_fixture_when_env_set` | AC-2 | Bei gesetztem `GZ_TEST_FIXTURE_DIR` liefert `get_provider("openmeteo")` einen `FixtureProvider`. |
| `test_ac3_get_provider_returns_real_when_env_unset` | AC-3 | Ohne `GZ_TEST_FIXTURE_DIR` liefert `get_provider("openmeteo")` den echten `OpenMeteoProvider` (Prod-Schutz). |
| `test_ac4_fetch_forecast_offline_72_points` | AC-4 | `fetch_forecast(location)` liefert ein `NormalizedTimeseries` mit 72 Datenpunkten, offline, mit befülltem `t2m_c`. |
| `test_ac5_timestamps_restamped_to_today` | AC-5 | `data[0].ts` = heute 00:00 UTC, `data[1].ts` = heute 01:00 UTC (Re-Stamping). |
| `test_ac6_preview_renders_without_real_api_call` | AC-6 | `PreviewService.render_email_preview` rendert offline; KEIN `open-meteo`-Eintrag im (umgeleiteten) Diagnose-Log. |
| `test_conftest_sets_fixture_dir_for_normal_tests` | AC-6 | Ein normaler Test läuft automatisch im Fixture-Modus (conftest-autouse setzt `GZ_TEST_FIXTURE_DIR`). |
| `test_ac7_live_marker_disables_fixture_mode` | AC-7 | Ein `@pytest.mark.live`-Test hat `GZ_TEST_FIXTURE_DIR` NICHT gesetzt (echte API erlaubt). |
| `test_f001_whitespace_env_does_not_activate_fixture` | F001 | `GZ_TEST_FIXTURE_DIR="   "` (nur Whitespace) → `get_provider("openmeteo")` liefert den echten `OpenMeteoProvider` (Prod-Schutz via `.strip()`). |
| `test_f002_malformed_fixture_missing_data_raises` | F002 | Fixture-JSON ohne `"data"`-Key → `FixtureProvider.fetch_forecast` wirft `ProviderError` statt stiller 0-Punkte-Timeseries. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Echter `FixtureProvider` gegen die echten `fixtures/openmeteo/*.json`.
- Echter `PreviewService` gegen einen echten Trip aus `data/users` (Skip-Fallback,
  falls kein Trip vorhanden).
- `monkeypatch` wird ausschließlich für ENV-Var-Isolation (`setenv`/`delenv`) und
  Umleitung des Diagnose-Log-Pfads (`DIAGNOSTICS_PATH` → `tmp_path`, etabliertes
  Muster aus `test_bug_338`) genutzt — KEIN `Mock()`, `patch()`, `MagicMock`,
  kein Mocken von Geschäftslogik oder HTTP.

In RED-Phase schlagen die Tests fehl, weil `src/providers/fixture.py`
(`FixtureProvider`), der Fixture-Zweig in `get_provider()` und die conftest-
autouse-Fixture noch nicht existieren.

## Expected Behavior

- **Input:** Echte Alpen-Koordinaten, echte Fixture-Dateien, echter Trip-JSON.
- **Output:** Assertions über Protocol-Erfüllung, Provider-Typ, Datenpunkt-Anzahl,
  Timestamp-Werte, Abwesenheit von Open-Meteo-Calls und ENV-Var-Zustand.
- **Side effects:** Schreibvorgänge ausschließlich in `tmp_path`; ENV-Mutationen
  via `monkeypatch` (automatisch zurückgerollt).

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert und die Implementierung fehlt /
  When `pytest tests/tdd/test_issue_346_fixture_provider.py -v` läuft /
  Then schlagen die Kern-Tests (AC-1/2/4/5/6 + conftest) fehl (RED-Phase erfolgreich).

- **AC-T2:** Given die GREEN-Phase ist abgeschlossen /
  When dieselbe Test-Suite ausgeführt wird /
  Then sind alle Tests grün, ohne Mocks und ohne echten Open-Meteo-Call.

## Known Limitations

- `test_ac3_get_provider_returns_real_when_env_unset` ist bereits in RED grün
  (Prod-Pfad existiert schon) — dient als Regression-Guard gegen versehentliches
  Aktivieren des Fixture-Modus in Produktion.
- `test_ac7_live_marker_disables_fixture_mode` ist in RED grün (nichts setzt die
  Var), wird aber durch den conftest-Opt-out in GREEN verbindlich abgesichert.

## Changelog

- 2026-05-23: Initial — Test-Manifest für Issue #346 (Python-Fixture-Provider).
