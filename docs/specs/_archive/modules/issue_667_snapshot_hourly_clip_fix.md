---
entity_id: issue_667_snapshot_hourly_clip_fix
type: module
created: 2026-06-08
updated: 2026-06-08
status: live
version: "1.0"
tags: [telegram, drilldown, weather-snapshot, persistence, bugfix, epic-639]
---

# #667 — Snapshot-Stundenreihe nicht aufs Etappenfenster beschneiden

## Approval

- [x] Approved (PO 'go' 2026-06-08)

## Purpose

Behebt eine stille Unter-Lieferung des Telegram-Drilldowns (#654): Beim Speichern
eines Wetter-Snapshots wird die persistierte Stundenreihe pro Segment auf das
**Etappen-Reisefenster** `[segment.start_time, segment.end_time]` beschnitten.
Dadurch kann `WeatherExtractor.drilldown(..., hours=12)` faktisch nur die Stunden
der Etappe liefern statt der zugesagten ≤12 h — obwohl die volle Tagesreihe (24 h)
in `SegmentWeatherData.timeseries` bewusst aufgehoben wird.

Der Fix entfernt den Beschneidungs-Block in `_serialize_segment`, sodass die volle
(ohnehin geholte) Stundenreihe persistiert wird. Additiv, round-trip-sicher.

## Source

- **File:** `src/services/weather_snapshot.py`
  - In `_serialize_segment`: den Stunden-Clip `if p.ts < start or p.ts > end: continue`
    (samt `start`/`end`-Bindung an das Segmentfenster) entfernen. Alle Punkte aus
    `seg.timeseries.data` werden serialisiert.
- **File (read-only, Beleg):** `src/services/segment_weather.py` — hält `timeseries`
  ungefiltert (volle 24 h, „kept for table display"); `aggregated` wird getrennt aus
  dem gefilterten Etappenfenster berechnet und separat persistiert.
- **File (read-only, profitiert):** `src/services/weather_extractor.py` — `drilldown()`
  unverändert.

## Behaviour

### Persistenz
- `_serialize_segment` schreibt **alle** Stundenpunkte aus `seg.timeseries.data` in
  den `hourly`-Key (keine Fensterbeschränkung mehr).
- Der `aggregated`-Key bleibt unverändert (wird weiterhin aus dem Etappenfenster
  berechnet, kommt aus `seg.aggregated`, nicht aus `hourly`).

### Kompatibilität
- **Laden:** Bestehende (bereits geclippte) Snapshots laden unverändert fehlerfrei —
  weniger Punkte sind ein gültiger Spezialfall, kein Crash.
- **Feld-Set:** unverändert (gleiche Hourly-Felder), nur mehr Zeilen.
- **Alert-Pipeline:** `weather_change_detection.py` liest ausschließlich `aggregated`
  → bit-identisches Verhalten.

### Wirkung auf Drilldown
- `drilldown(from_time=<jetzt>, hours=12)` liefert nun bis zu 12 h Stundenpunkte,
  auch wenn das Etappenfenster schmaler ist (z. B. 4 h Gehzeit).

## Acceptance Criteria

**AC-1:** Given ein gespeicherter Snapshot, dessen Segment ein **schmales**
Reisefenster (z. B. 4 h) hat, dessen zugrundeliegende `timeseries` aber 12 h+
Stundenpunkte enthält, When der Snapshot gespeichert und neu geladen wird, Then
enthält die geladene Stundenreihe **alle** Punkte (≥ 12), nicht nur die ~4 innerhalb
des Etappenfensters.

**AC-2:** Given ein solcher Snapshot und Eingang `/hg` (bzw. Query-Key
`dd_thunder_today`) zu einer Zeit am Fensteranfang, When der Bot antwortet, Then
enthält die Drilldown-Antwort Stundenzeilen, die **über das schmale Etappenfenster
hinausreichen** (deutlich mehr `🕐`-Zeilen als die ~4 Etappenstunden, bis zu 12 h).

**AC-3:** Given derselbe Snapshot, When er gespeichert und neu geladen wird, Then ist
die `aggregated`-Zusammenfassung des Segments **unverändert** gegenüber vor dem Fix
(der Clip betraf nie `aggregated`; Aggregation/Alerts bleiben bit-identisch).

**AC-4:** Given ein **alt** gespeicherter Snapshot mit bereits geclippter
(schmaler) Stundenreihe, When er nach dem Fix geladen wird, Then lädt er fehlerfrei
ohne Exception (round-trip-Abwärtskompatibilität).

## Dependencies

- `WeatherExtractor.drilldown()` (#652 ✅), Telegram-Drilldown-Renderer (#654 ✅).
- Kein Downstream-Change nötig.

## Out of Scope

- Änderungen an `weather_extractor.py`, `trip_command_processor.py` oder der
  Telegram-Formatierung — der Renderer ist bereits korrekt, ihm fehlten nur die Daten.
- Rückwirkende Migration alter Snapshots (Scheduler regeneriert sie regelmäßig).
