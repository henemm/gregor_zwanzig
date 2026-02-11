---
entity_id: email_metrics_filter
type: bugfix
created: 2026-02-10
updated: 2026-02-10
status: done
version: "1.0"
tags: [bugfix, story-3, feature-3.1, email, config, metrics]
---

# Bugfix: Email-Metriken nach User-Config filtern

## Approval

- [x] Approved

## Purpose

Feature 3.1 (Email Trip-Formatter) akzeptiert `trip_config: Optional[TripWeatherConfig]`, nutzt es aber nie. Die Tabellen-Spalten Temp/Wind/Precip sind hardcoded. Laut Story 3 Spec soll die Email nur die vom User konfigurierten Metriken anzeigen.

## Source

- **File:** `src/formatters/trip_report.py`
- **Identifier:** `TripReportFormatter._generate_html()` und `_generate_plain_text()`
- **Problem:** `trip_config` Parameter wird durchgereicht aber ignoriert

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripWeatherConfig` | DTO | models.py:319 — enthält `enabled_metrics: list[str]` |
| `weather_config.py` | UI | Definiert `BASIS_METRICS` / `EXTENDED_METRICS` Mapping |

## Implementation Details

### Metrik-Spalten-Mapping

Die Email-Tabelle hat 3 Wetter-Spalten, die jeweils von bestimmten `enabled_metrics` abhängen:

| Spalte | Angezeigt wenn EINE dieser Metriken aktiv |
|--------|-------------------------------------------|
| Temp | `temp_min_c`, `temp_max_c`, `temp_avg_c` |
| Wind | `wind_max_kmh`, `gust_max_kmh` |
| Precip | `precip_sum_mm` |

Segment, Time, Duration, Risk sind **immer sichtbar** (strukturelle Spalten, nicht konfigurierbar).

### Logik

```python
def _get_visible_columns(self, trip_config: Optional[TripWeatherConfig]) -> dict[str, bool]:
    """Determine which metric columns to show."""
    if not trip_config:
        return {"temp": True, "wind": True, "precip": True}  # Default: alle

    metrics = set(trip_config.enabled_metrics)
    return {
        "temp": bool(metrics & {"temp_min_c", "temp_max_c", "temp_avg_c"}),
        "wind": bool(metrics & {"wind_max_kmh", "gust_max_kmh"}),
        "precip": "precip_sum_mm" in metrics,
    }
```

### HTML-Anpassung

Table-Header und Row-Cells werden conditional gerendert:

```python
columns = self._get_visible_columns(trip_config)

# Header
header = "<th>Segment</th><th>Time</th><th>Duration</th>"
if columns["temp"]:
    header += "<th>Temp</th>"
if columns["wind"]:
    header += "<th>Wind</th>"
if columns["precip"]:
    header += "<th>Precip</th>"
header += "<th>Risk</th>"

# Row (analog)
```

### Plain-Text-Anpassung

Gleiche Logik für `_generate_plain_text()`.

### Summary-Anpassung

Summary-Grid zeigt nur Metriken, deren Spalte sichtbar ist.

## Expected Behavior

- **Input:** `trip_config.enabled_metrics = ["temp_max_c", "precip_sum_mm"]`
- **Output:** Tabelle mit Segment, Time, Duration, Temp, Precip, Risk (KEIN Wind)

- **Input:** `trip_config = None`
- **Output:** Alle Spalten (Default-Verhalten, keine Regression)

## Tests

```python
def test_all_columns_when_no_config():
    """Default: all metric columns shown."""
    report = formatter.format_email(segments, "Trip", "morning", trip_config=None)
    assert "Temp" in report.email_html
    assert "Wind" in report.email_html
    assert "Precip" in report.email_html

def test_filtered_columns_with_config():
    """Only configured metrics shown."""
    config = TripWeatherConfig(trip_id="t", enabled_metrics=["temp_max_c"], updated_at=now)
    report = formatter.format_email(segments, "Trip", "morning", trip_config=config)
    assert "Temp" in report.email_html
    assert "<th>Wind</th>" not in report.email_html
    assert "<th>Precip</th>" not in report.email_html
```

## Scope

- **Dateien geändert:** 1 (`src/formatters/trip_report.py`)
- **Dateien für Tests:** 1 (`tests/unit/test_trip_report_formatter.py`)
- **LoC Änderungen:** ~40 (Produktion) + ~30 (Tests)
- **Keine Seiteneffekte** — Default-Verhalten bleibt identisch

## Known Limitations

- Spalten werden pro Kategorie (Temp/Wind/Precip) ein/ausgeblendet, nicht pro Einzel-Metrik. Das ist beabsichtigt: Eine Tabelle mit 13 möglichen Spalten wäre auf Mobile unleserlich.

## Changelog

- 2026-02-10: Initial spec created
