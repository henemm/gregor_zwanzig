# Spec: Issue #808 — Briefing-Mail "Sonne 0 min" & Abstiegs-Symbol

**Issue:** #808  
**Erstellt:** 2026-06-19  
**Status:** Spec (zur Freigabe)

## Problem

Zwei Bugs in der Briefing-Mail:

1. **Hauptbug:** Metriken-Überblick zeigt "Sonne 0 min" obwohl Stunden-Tabelle ☀️/🌤️ zeigt.
2. **Nebenbefund:** Segment-Header nutzt ↑ auch für Abstiegssegmente.

## Root Cause

**Bug 1:** `_pill_for_metric()` in `helpers.py:1068-1072` liest `dp._sunny_hours` via `hasattr()` von `ForecastDataPoint`-Objekten. Das Attribut existiert dort nie (nur in Row-Dicts). → `hasattr()` immer `False` → Summe 0.0 → "Sonne 0 min".

**Bug 2:** `plain.py:209` und `html.py:341` nutzen hartkodierts `↑` unabhängig von der Höhenrichtung.

## Acceptance Criteria

**AC-1:** Gegeben ein Briefing-Segment mit Sonnenschein-Datenpunkten (dni_wm2 > 0), wenn `build_metrics_summary_pills(["sunshine"], ...)` aufgerufen wird, dann enthält das Ergebnis eine Pille mit "Sonne X min" und X > 0.

**AC-2:** Gegeben ein Briefing-Segment mit ausschließlich bewölkten Datenpunkten (keine DNI, cloud_total_pct=100), wenn `build_metrics_summary_pills(["sunshine"], ...)` aufgerufen wird, dann ist die Sunshine-Pille abwesend (return None, nicht "Sonne 0 min").

**AC-3:** Gegeben ein Abstiegssegment (end_elevation < start_elevation), wenn die Briefing-Mail (Plain-Text oder HTML) gerendert wird, dann zeigt der Segment-Header ↓ statt ↑ vor den Elevationsangaben.

**AC-4:** Gegeben ein Aufstiegssegment (end_elevation >= start_elevation), wenn die Briefing-Mail gerendert wird, dann zeigt der Segment-Header weiterhin ↑.

## Technische Änderungen

### Fix Bug 1 — `helpers.py`

```python
# ALT (defekt):
if metric_id == "sunshine":
    total = sum(
        (dp._sunny_hours if hasattr(dp, "_sunny_hours") else 0.0)
        for dp in all_dps
    )
    return (f"Sonne {int(round(total * 60))} min", _PILL_NEUTRAL_TONE)

# NEU (korrekt):
if metric_id == "sunshine":
    from services.weather_metrics import WeatherMetricsService
    total = WeatherMetricsService.calculate_sunny_hours(all_dps)
    if not all_dps or total == 0:
        return None
    return (f"Sonne {int(round(total * 60))} min", _PILL_NEUTRAL_TONE)
```

### Fix Bug 2 — `plain.py` und `html.py`

```python
# In beiden Dateien: e_elev und s_elev sind bereits berechnet
elev_arrow = "↑" if e_elev >= s_elev else "↓"
# Dann {elev_arrow} statt hartem ↑
```

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `src/output/renderers/email/helpers.py` | `_pill_for_metric()` sunshine-Branch: `calculate_sunny_hours()` direkt |
| `src/output/renderers/email/plain.py` | Segment-Header: `↑/↓` je nach Richtung |
| `src/output/renderers/email/html.py` | Segment-Header: `↑/↓` je nach Richtung |
| `tests/tdd/test_issue_808_sonne_pill.py` | Neue TDD-Tests für AC-1 bis AC-4 |

## Scope

**Backend-only** (Python, keine Frontend-Änderungen, kein Go). E2E-Scope: `full-stack` (Mail-Validator nach Staging-Versand).

## LoC-Schätzung

~30 LoC Änderungen + ~60 LoC Tests = ~90 LoC gesamt (unter 250-Limit).
