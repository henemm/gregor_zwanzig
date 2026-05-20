---
entity_id: bug_226_dni_wmo_passthrough
type: bugfix
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [bugfix, weather-metrics, segment-summary, dni, wmo-code, issue-226]
---

<!-- Issue #226 — compute_extended_metrics(): dominant_wmo_code + dni_avg_wm2 nicht in Extended-Summary kopiert -->

# Issue #226 — Bug-Fix: compute_extended_metrics() verliert dominant_wmo_code + dni_avg_wm2

## Approval

- [ ] Approved

## Zweck

`compute_extended_metrics()` in `src/services/weather_metrics.py` baut ein neues `SegmentWeatherSummary` per expliziter Feldliste. Dabei werden `dominant_wmo_code` (dominantes Wetter-Symbol) und `dni_avg_wm2` (Tageshelligkeit) nicht aus dem `basis_summary` kopiert — beide bleiben `None`. Die Stage-Level-Aggregation (`aggregate_stage_summary()`) kann dadurch `dominant_wmo_code` nicht aggregieren, weil das Feld leer ist. Bug ist seit Commit `d92af39` latent.

## Quelle / Source

**Geänderte Datei:**
- `src/services/weather_metrics.py` Z. 907–950 — `compute_extended_metrics()`: zwei Felder zum Kopier-Block hinzufügen

**Neue Test-Datei:**
- `tests/tdd/test_bug_226_dni_wmo_passthrough.py`

**NICHT ändern:** Specs `weather_emoji_dni.md` und `risk_engine.md` v2.0 beschreiben das korrekte Verhalten bereits; `aggregate_stage_summary()` ist korrekt implementiert und braucht keinen Fix.

> **Schicht-Hinweis:** Ausschließlich Python-Backend-Layer (`src/services/`). Kein Frontend, kein Go-API betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/weather_metrics.py` | Python-Modul | Enthält `compute_basis_metrics()` (setzt die Felder) und `compute_extended_metrics()` (kopiert sie nicht vollständig) |
| `app.models.SegmentWeatherSummary` | Dataclass | Hält `dominant_wmo_code: Optional[int]` und `dni_avg_wm2: Optional[float]` |
| `tests/unit/test_weather_metrics.py` | Unit-Tests | `TestWeatherMetricsServiceExtendedKnownValues.basis_summary`-Fixture setzt diese Felder nicht — Regressions-Test braucht eigene Fixture oder explizite Werte |

## Implementation Details

### Fix in `compute_extended_metrics()` (Z. 907–950)

Im `SegmentWeatherSummary(...)` Konstruktor-Aufruf nach `visibility_min_m=basis_summary.visibility_min_m` einfügen:

```python
# Felder aus compute_basis_metrics() die bisher fehlten (Issue #226)
dominant_wmo_code=basis_summary.dominant_wmo_code,
dni_avg_wm2=basis_summary.dni_avg_wm2,
```

Die `aggregation_config` für beide Felder wird bereits korrekt via `**basis_summary.aggregation_config`-Spread übernommen — kein Änderungsbedarf dort.

## Acceptance Criteria

**AC-1:** Given ein `basis_summary` mit `dominant_wmo_code=80` / When `compute_extended_metrics(timeseries, basis_summary)` aufgerufen wird / Then gibt das zurückgegebene `SegmentWeatherSummary` `dominant_wmo_code == 80` zurück.
- Test: (populated after /tdd-red)

**AC-2:** Given ein `basis_summary` mit `dni_avg_wm2=250.0` / When `compute_extended_metrics(timeseries, basis_summary)` aufgerufen wird / Then gibt das zurückgegebene `SegmentWeatherSummary` `dni_avg_wm2 == 250.0` zurück.
- Test: (populated after /tdd-red)

**AC-3:** Given ein `basis_summary` mit `dominant_wmo_code=None` und `dni_avg_wm2=None` (Standardfall) / When `compute_extended_metrics()` aufgerufen wird / Then bleiben beide Felder `None` (kein Regression in der bestehenden Null-Behandlung).
- Test: (populated after /tdd-red)

## Known Limitations

- Kein Impact auf Renderer, die direkt auf `timeseries.data` zugreifen (Mehrheit der aktuellen Pfade)
- Stage-Level-Aggregation für `dominant_wmo_code` bleibt ohne Etappen-Daten im `basis`-Pfad leer — liegt außerhalb dieses Fixes

## Changelog

- 2026-05-20: Spec erstellt (Adversary-Finding aus Issue #121, außerhalb des #121-Scopes)
