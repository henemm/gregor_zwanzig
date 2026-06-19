# Context: Issue #808 — Briefing-Mail "Sonne 0 min" trotz sonnniger Stunden

## Request Summary
Im Metriken-Überblick der Briefing-Mail steht "Sonne 0 min", obwohl die Stunden-Tabelle
durchgehend ☀️/🌤️ zeigt. Ursache: falscher Attributzugriff in `_pill_for_metric()`.
Als Nebenbefund nutzt der Segment-Header das ↑-Symbol auch bei Abstiegssegmenten.

## Root Cause — Bug 1 (Hauptbug): "Sonne 0 min"

**Datei:** `src/output/renderers/email/helpers.py:1067-1072`

```python
if metric_id == "sunshine":
    total = sum(
        (dp._sunny_hours if hasattr(dp, "_sunny_hours") else 0.0)
        for dp in all_dps
    )
    return (f"Sonne {int(round(total * 60))} min", _PILL_NEUTRAL_TONE)
```

- `all_dps` enthält `ForecastDataPoint`-Objekte (kommt aus `build_metrics_summary_pills()`)
- `ForecastDataPoint` hat **kein** `_sunny_hours`-Attribut (nur Row-Dicts via `dp_to_row()` haben es)
- `hasattr(dp, "_sunny_hours")` ist **immer `False`** → Summe immer 0.0 → "Sonne 0 min"

**Korrekte Berechnung** existiert bereits als statische Methode:
`WeatherMetricsService.calculate_sunny_hours(data: List[ForecastDataPoint]) -> float`
(`src/services/weather_metrics.py:312-372`)

## Root Cause — Bug 2 (Nebenbefund): Abstiegs-Symbol

**Dateien:**
- `src/output/renderers/email/plain.py:209`
- `src/output/renderers/email/html.py:341`

Beide rendern: `↑{s_elev}m → {e_elev}m` — mit hartem `↑` auch wenn `e_elev < s_elev`
(Abstiegssegment). `TripSegment` hat `ascent_m` und `descent_m` als Felder.

## Bezugsklassen

| Klasse/Methode | Datei | Rolle |
|---|---|---|
| `_pill_for_metric()` | `helpers.py:1060+` | Überblick-Pillen-Rendering; sunshine-Branch ist defekt |
| `build_metrics_summary_pills()` | `helpers.py:1187-1228` | Sammelt `all_dps` als `ForecastDataPoint`-Liste |
| `WeatherMetricsService.calculate_sunny_hours()` | `services/weather_metrics.py:312` | Korrekte Sonnenstunden-Berechnung (DNI + Cloud-Fallback) |
| `TripSegment` | `app/models.py:315+` | Hat `ascent_m`, `descent_m`, `start_point.elevation_m`, `end_point.elevation_m` |
| `plain.py render_plain_text_email()` | `email/plain.py:180+` | Segment-Header mit Elevation-Symbol |
| `html.py` Segment-Header | `email/html.py:335-342` | Gleicher Bug, HTML-Pfad |

## Fix-Ansatz

**Bug 1:** In `_pill_for_metric()` für `sunshine`:
```python
if metric_id == "sunshine":
    from services.weather_metrics import WeatherMetricsService
    total = WeatherMetricsService.calculate_sunny_hours(all_dps)
    if total == 0:
        return None  # Metrik weglassen statt "0 min" zeigen
    return (f"Sonne {int(round(total * 60))} min", _PILL_NEUTRAL_TONE)
```

**Bug 2:** In `plain.py:209` und `html.py:341`:
```python
elev_arrow = "↑" if e_elev >= s_elev else "↓"
# Dann {elev_arrow} statt hartem ↑ verwenden
```

## Existing Tests

- `tests/unit/test_issue_347_sunshine_hours.py` — testet `calculate_sunny_hours()` direkt (grün)
- `tests/tdd/test_issue_664_metrics_summary.py` — testet `build_metrics_summary_pills()`, KEIN sunshine-Test
- `tests/tdd/test_issue_807_reproduction.py` — testet Segment-Fenster-Bug (gust), KEIN sunshine

→ Es gibt **keinen Test** der bestätigt, dass `build_metrics_summary_pills(["sunshine"])` > 0 liefert.

## Risks & Considerations

- `calculate_sunny_hours()` importiert `Settings()` intern bei `settings=None` — im Pill-Kontext OK
- `return None` für total == 0 ist korrekt (keine "0 min"-Pill, Pille fällt weg)
- Der HTML-Renderer hat identischen ↑-Bug — beide Pfade müssen gefixt werden
- Bundle A hat sonst keine weiteren offenen Issues (806/807 bereits erledigt lt. Memory)
