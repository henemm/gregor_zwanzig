# Context: Issue #667 — Telegram-Drilldown auf Etappenfenster beschnitten

## Request Summary
Der mit #654 ausgelieferte stündliche Single-Metric-Drilldown (`/hg`, `dd_*_today/tomorrow`)
liefert faktisch nur die Stunden des **Etappen-Reisefensters** statt der in der Spec
zugesagten **≤12 h**, weil `weather_snapshot.py::_serialize_segment` die persistierte
Stundenreihe beim Speichern auf `[segment.start_time, segment.end_time]` beschneidet.

## Root Cause
| Datei:Zeile | Befund |
|-------------|--------|
| `src/services/weather_snapshot.py:163-179` (origin/main) | `_serialize_segment` clippt `seg.timeseries.data` auf `[start_time, end_time]` (`if p.ts < start or p.ts > end: continue`) **beim Speichern**. |
| `src/services/segment_weather.py:160-189` | `SegmentWeatherData.timeseries` wird **bewusst ungefiltert** (volle 24h-Tagesreihe) gehalten — Kommentar: „Unfiltered timeseries is kept for table display". Der Clip wirft genau das wieder weg. `aggregated` wird separat aus dem gefilterten Stundenfenster (`filtered_ts`) berechnet. |
| `src/services/weather_extractor.py:91-148` | `drilldown(trip_id, metric, from_time, hours=12)` windowt `[start, start+12h)` — kann aber nur lesen, was persistiert wurde. |

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/weather_snapshot.py` | **Kern-Fix.** Clip in `_serialize_segment` entfernen → volle Stundenreihe persistieren. |
| `src/services/weather_extractor.py` | Datenleser `drilldown()` — unverändert, profitiert vom Fix. |
| `src/services/segment_weather.py` | Belegt die Absicht (volle Reihe halten). Unverändert. |
| `src/services/weather_change_detection.py` | Alert-Pipeline liest NUR `aggregated` (separat persistiert) → unberührt. |
| `tests/tdd/test_weather_extractor.py` | Mock-freies Test-Muster für drilldown/snapshot. |

## Existing Patterns
- Snapshot-Persistenz: `aggregated` (Summary) und `hourly` (Stundenreihe) sind **getrennte** JSON-Keys pro Segment. `aggregated` wird NIE aus `hourly` neu berechnet beim Laden.
- `drilldown()` sammelt über ALLE Segmente, dedupliziert/sortiert nach `ts`, windowt dann `[from_time, from_time+hours)`.

## Dependencies
- **Upstream:** #654 (Drilldown-Renderer, live), #652 (`drilldown()`-Datenschicht, live).
- **Downstream:** keine — additive Erweiterung der persistierten Daten.

## Risks & Considerations
- **Round-trip-sicher / additiv:** Es ändert sich kein Feld-Set, nur die Anzahl persistierter Stundenpunkte steigt. Bestehende (geclippte) Snapshots bleiben ladbar; der Scheduler regeneriert Snapshots regelmäßig → forward-looking, keine Datenmigration nötig.
- **Alert-Pipeline unberührt:** liest nur `aggregated`.
- **Snapshot-Größe:** mehr Stundenpunkte pro Segment (volle ~24h statt Etappenfenster) → moderat größere JSON-Dateien. Akzeptabel.
- **Test-Maskierung vermeiden:** RED-Test MUSS ein **realistisch schmales** Segmentfenster (z. B. 4h) mit 12h Untergrund-Daten verwenden, damit der Clip nachweisbar beißt (Gegenmuster zum #654-Test mit 11h-Segment).
- **Backend-only:** kein Frontend, kein Pixel-Gate. E2E = Verhaltenstest gegen Staging-Klon.
