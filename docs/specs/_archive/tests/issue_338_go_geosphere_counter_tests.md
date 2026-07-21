---
entity_id: issue_338_go_geosphere_counter_tests
type: tests
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [tests, observability, open-meteo, api-limit, diagnostics, golang, geosphere, issue-338]
parent: issue_338_go_geosphere_counter
phase: phase5_tdd_red
---

# Issue #338 (Erweiterung) — Go + Geosphere Abruf-Erfassung (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer die vollstaendige Abruf-Erfassung aus
`docs/specs/modules/issue_338_go_geosphere_counter.md`. Jeder Test mappt 1:1 auf
ein Acceptance Criterion der Parent-Spec. Ergaenzt den Zaehler aus Commit
bd8e1e2 um den Go-Provider und den Python-`GeoSphereProvider`.

Parent-Spec: `docs/specs/modules/issue_338_go_geosphere_counter.md` v1.0

## Source

- **File (Python):** `tests/tdd/test_issue_338_go_geosphere_counter.py` (NEU —
  Geosphere-Clouds-Pfad, Konsolidierungs-Regression der 6 alten Tests,
  Auswertungs-Skript-Aggregation, call_log-Vertrag)
- **File (Go):** `internal/provider/openmeteo/calllog_test.go` (NEU —
  httptest-Server 429-Pfad und Fail-Soft-Verhalten)

## Test Inventory

### Python (`tests/tdd/test_issue_338_go_geosphere_counter.py`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `test_ac2_geosphere_clouds_logs_source_geosphere_clouds` | AC-2 | Echter `GeoSphereProvider._fetch_openmeteo_clouds`-Aufruf (Alpenkoordinaten, 429 erlaubt) protokolliert eine JSONL-Zeile mit `source == "geosphere_clouds"`. |
| `test_ac3_existing_six_tests_still_green` | AC-3 | Die 6 bestehenden Tests aus `tests/tdd/test_bug_338_openmeteo_call_counter.py` bleiben nach der call_log-Konsolidierung gruen (Sub-Prozess-Exit 0). |
| `test_ac4_analyze_aggregates_python_and_go_sources` | AC-4 | `scripts/analyze_openmeteo_calls.py` liest `openmeteo_calls.jsonl` + `openmeteo_calls_go.jsonl`, aggregiert beide gemeinsam und weist `go_*`- und Python-Quellen aus. |
| `test_call_log_module_exposes_api_and_marker_order` | AC-2 (Vertrag) | `providers.call_log` exportiert `log_api_call`, `resolve_call_source`, `DIAGNOSTICS_PATH`, `_CALL_SOURCE_MARKERS`; der `geosphere_clouds`-Marker steht ganz oben. |

### Go (`internal/provider/openmeteo/calllog_test.go`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `TestCallLog_FetchForecast429_AppendsGoForecastLine` | AC-1 | `FetchForecast` gegen einen `httptest.NewServer` (liefert 429) haengt eine JSONL-Zeile an `openmeteo_calls_go.jsonl` mit `status=429`, `source == "go_forecast"`, `endpoint` ohne Query. |
| `TestCallLog_UnwritableTarget_IsSwallowed` | AC-5 | Nicht-beschreibbares Diagnose-Ziel: `logAPICall` schluckt den Fehler (kein Panic), `doRequest`/`FetchForecast` liefern unveraendert. |

## Implementation Details

Tests folgen dem No-Mocks-Pattern des Projekts:
- Python: echter `GeoSphereProvider`-Aufrufpfad, echter
  `api.open-meteo.com`-Request (429 erlaubt). JSONL-Pfad-Isolation via
  `providers.call_log.DIAGNOSTICS_PATH`-Umkonfiguration auf `tmp_path`
  (Konfiguration, kein Mock).
- Go: `httptest.NewServer` ist ein ECHTER lokaler HTTP-Server (kein Mock);
  Diagnose-Pfad via Paket-Variable `diagnosticsGoPath` auf `t.TempDir` umgelenkt.
- AC-5/AC-3 (Fail-Soft) nutzen ein echtes nicht-beschreibbares Ziel (Pfad unter
  einer Datei).
- Keine `Mock()`, `patch()`, `MagicMock`.

In RED-Phase schlagen alle Tests fehl, weil `src/providers/call_log.py`,
`internal/provider/openmeteo/calllog.go`, die Geosphere-Instrumentierung und die
analyze-Skript-Erweiterung noch nicht existieren.

## Expected Behavior

- **Input:** Echte Innsbruck-/Alpenkoordinaten; vorbereitete JSONL-Fixtures;
  lokaler httptest-Server.
- **Output:** Assertions ueber JSONL-Zeilen-Felder, `source`-Werte, Fail-Soft
  und Skript-Ausgabe.
- **Side effects:** Echte OpenMeteo-Requests (429 erlaubt, da Limit erschoepft);
  Schreibvorgaenge ausschliesslich in `tmp_path` / `t.TempDir`.

## Acceptance Criteria

- **AC-T1:** Given die Test-Dateien existieren und Implementierung fehlt /
  When die scoped Test-Suites laufen / Then schlagen alle neuen Tests fehl
  (RED-Phase erfolgreich).

- **AC-T2:** Given GREEN-Phase abgeschlossen / When die scoped Test-Suites
  laufen / Then alle neuen Tests gruen, die 6 alten Tests bleiben gruen, keine
  Mocks.

## Known Limitations

- AC-2-Test macht einen echten Wetter-API-Call (429 ist hier ein valider,
  erwuenschter Pfad — der Zaehler muss auch 429 protokollieren).
- Go-Quelle nur grob (`go_forecast`/`go_uv`), siehe Parent-Spec.

## Changelog

- 2026-05-23: Initial — Test-Manifest fuer Issue #338 (Erweiterung: Go + Geosphere).
