# Context: Issue #397 — Zeitzonen-Bug Segment-Header vs. Tabelle

## Request Summary

Die angezeigte Segmentzeit im E-Mail-Header (z.B. "8–10 Uhr") weicht von den Uhrzeiten in der darunter liegenden Wetter-Tabelle ab (z.B. "10, 11, 12 Uhr"). Ursache: Segment-Header zeigen UTC-Zeit, Tabellen-Zeilen zeigen lokale Zeit.

## Root Cause

Alle Renderer verwenden `.strftime('%H:%M')` direkt auf `segment.start_time` und `segment.end_time`, welche als UTC gespeichert sind (`TripSegment.start_time: datetime  # UTC!`). Die Tabellen-Zeilen werden jedoch via `local_hour(dp.ts, tz)` in lokaler Zeitzone angezeigt. Für CEST (UTC+2) entsteht dadurch ein 2-Stunden-Versatz.

## Betroffene Dateien

| Datei | Zeilen | Problem |
|-------|--------|---------|
| `src/output/renderers/email/html.py` | 236-237, 249-250, 285 | `seg.start_time.strftime('%H:%M')` → UTC |
| `src/output/renderers/email/plain.py` | 174, 176, 183 | `seg.start_time.strftime('%H:%M')` → UTC |
| `src/output/renderers/narrow.py` | 184-185 | `seg.start_time.strftime('%H:%M')` → UTC, `local_fmt` nicht importiert |
| `src/output/renderers/email/helpers.py` | ~521-523 (`build_segment_label`) | `strftime('%H:%M')` ohne tz, kein `tz`-Parameter |

## Existierende korrekte Lösung (Muster)

`local_fmt(dt, tz)` aus `utils/timezone.py` konvertiert UTC-datetime korrekt in lokale Zeit. **Bereits korrekt genutzt** für: Dämmerungszeiten, Sonnenauf/-untergang, Confidenz-Hints (alle Renderer).

## Fix-Plan

1. In `html.py`, `plain.py`, `narrow.py`: `seg.start_time.strftime('%H:%M')` → `local_fmt(seg.start_time, tz)`, `seg.end_time.strftime('%H:%M')` → `local_fmt(seg.end_time, tz)`
2. In `narrow.py`: `from utils.timezone import local_fmt` hinzufügen
3. In `helpers.py`: `build_segment_label(change, segments)` um `tz: ZoneInfo` erweitern; `strftime` durch `local_fmt` ersetzen
4. Aufrufer in `html.py` (Zeile 372) und `plain.py` (Zeile 160): `tz=tz` übergeben

## Nicht betroffen

- `extract_hourly_rows` in helpers.py: Filter `start_h <= dp.ts.hour <= end_h` ist intern UTC-konsistent → korrekte Datenpunkte werden eingeschlossen, kein Bug
- `report_date = segments[0].segment.start_time.strftime("%d.%m.%Y")` — Datum (kein Zeitversatz bei reinem Datum für diese Breiten relevant)

## Existierende Patterns

- `utils/timezone.py` → `local_fmt(dt, tz)`, `local_hour(dt, tz)`, `tz_for_coords(lat, lon)`
- Alle Renderer haben bereits `tz: ZoneInfo` als Parameter

## Abhängigkeiten

- Upstream: `segment_weather.py` speichert Zeiten als UTC (korrekt)
- Downstream: `build_segment_label` in helpers.py wird von html.py + plain.py aufgerufen
