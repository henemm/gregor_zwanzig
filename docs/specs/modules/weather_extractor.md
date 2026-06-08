---
entity_id: weather_extractor
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [weather, telegram, snapshot, extractor, epic-639]
---

# Weather Extractor (Snapshot-Datenschicht)

## Approval

- [x] Approved

## Purpose

Schlanke Datenschicht für Ad-Hoc-Wetterabfragen (Epic #639, Teil 3/6). Zieht gezielt
Metriken aus einem vorhandenen Wetter-Snapshot — **ohne** vollen Report-Build — und liefert
strukturierte Werte (vertikale Timeline pro Wegpunkt, stündlicher Single-Metric-Drilldown,
sauberer Leerzustand). **Keine** Telegram-/Channel-Formatierung — die liegt in #653/#654.

## Source

- **File:** `src/services/weather_extractor.py` (neu)
- **Identifier:** `WeatherExtractor` (Klasse), DTOs `TimelinePoint`, `TimelineResult`, `DrilldownPoint`, `DrilldownResult`
- **Erweiterung:** `src/services/weather_snapshot.py` — additive stündliche Reihe (`hourly[]`) pro Segment

**Schicht:** Python-Backend (`src/services/`). Bestätigt per grep: Snapshot-Persistenz und
Naismith-Segmentbau liegen vollständig in Python (`src/services/`, `src/core/`). Keine Go-/
SvelteKit-Beteiligung in dieser Datenschicht.

## Estimated Scope

- **LoC:** ~220–260 (Snapshot-Erweiterung ~45, Extractor + DTOs ~135, Tests ~80)
- **Files:** 2 Produktivdateien (`weather_extractor.py` neu, `weather_snapshot.py` erweitert) + 1 Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherSnapshotService` (`weather_snapshot.py`) | service | Lädt Snapshot; wird additiv um `hourly[]` erweitert |
| `SegmentWeatherData`, `SegmentWeatherSummary`, `TripSegment` (`app.models`) | model | Aggregierte Pro-Segment-Werte + Wegpunkt-Geometrie/Zeiten |
| `ForecastDataPoint`, `NormalizedTimeseries` (`app.models`) | model | Stündliche Reihe für Drilldown |
| `ThunderLevel`, `PrecipType` (`app.models`) | enum | Metrik-Werte mit Enum-Typ |

## Implementation Details

### 1. Snapshot-Erweiterung (additiv, rückwärtskompatibel)

`WeatherSnapshotService.save` schreibt pro Segment zusätzlich `hourly: [...]` — eine
kompakte Liste **aller** `ForecastDataPoint`s aus `seg.timeseries.data` (seit #667 nicht
mehr auf das Segment-Zeitfenster beschnitten). Pro Stundenpunkt werden `ts` (ISO) plus die
metrik-relevanten Felder serialisiert (None ausgelassen, Enums als `.name`). Fehlt
`seg.timeseries` (Provider-Fehler), wird `hourly` weggelassen.

`WeatherSnapshotService.load` rekonstruiert `timeseries` aus `hourly[]`, falls vorhanden;
fehlt der Schlüssel (alte Snapshots), bleibt `timeseries=None` wie bisher. Der aggregierte
Pfad (`aggregated`) bleibt **unverändert** → `trip_alert` unberührt.

### 2. `WeatherExtractor`

```
class WeatherExtractor:
    def __init__(self, user_id: str = "default")     # Mandantentrennung Pflicht

    def timeline(self, trip_id, target_date=None) -> TimelineResult:
        # Snapshot laden. Fehlt er / keine Segmente -> TimelineResult(available=False, message=...)
        # Pro Segment ein TimelinePoint:
        #   arrival_time = segment.end_time (Naismith-Ankunft am Wegpunkt, UTC)
        #   elevation_m  = segment.end_point.elevation_m
        #   label        = str(segment.segment_id)
        #   metrics      = segment.aggregated (SegmentWeatherSummary)
        # Reihenfolge = Segment-Reihenfolge (chronologisch).

    def drilldown(self, trip_id, metric, from_time=None, hours=12) -> DrilldownResult:
        # metric = Feldname auf ForecastDataPoint (z.B. "thunder_level", "precip_rate_mmph").
        # Alle hourly-Punkte aller Segmente sammeln, nach ts sortieren, dedupliziert.
        # Fenster: ts >= from_time (Default: frühester Punkt) und ts < from_time + hours.
        # Pro Stunde ein DrilldownPoint(ts, value=getattr(point, metric, None)).
        # Keine hourly-Daten / Snapshot fehlt -> DrilldownResult(available=False, message=...).
```

### DTOs

```
@dataclass
class TimelinePoint:
    arrival_time: datetime          # UTC, Naismith
    elevation_m: Optional[float]
    label: str
    metrics: SegmentWeatherSummary

@dataclass
class TimelineResult:
    trip_id: str
    target_date: Optional[date]
    points: List[TimelinePoint]
    available: bool
    message: Optional[str] = None   # bei available=False: Klartext-Grund

@dataclass
class DrilldownPoint:
    ts: datetime                    # UTC
    value: Optional[object]         # float | int | ThunderLevel | None

@dataclass
class DrilldownResult:
    trip_id: str
    metric: str
    points: List[DrilldownPoint]
    available: bool
    message: Optional[str] = None
```

## Expected Behavior

- **Input:** `trip_id`, optional `target_date`, `metric`, `from_time`, `hours`; gelesen aus dem persistierten Snapshot des jeweiligen `user_id`.
- **Output:** `TimelineResult` / `DrilldownResult` mit strukturierten Werten (reine Daten, keine Formatierung).
- **Side effects:** keine — reine Lese-Schicht. (Die `save`-Erweiterung schreibt nur zusätzliche Felder beim ohnehin stattfindenden Snapshot-Schreiben.)

## Acceptance Criteria

- **AC-1:** Given ein vorhandener Snapshot mit Naismith-Segmenten, When `timeline(trip_id)` aufgerufen wird, Then liefert das Ergebnis pro Wegpunkt einen Eintrag mit der Naismith-Ankunftszeit (`arrival_time`), der Höhe und den aggregierten Metrikwerten des Segments — ohne dass ein vollständiger Report erzeugt wird.
  - Test: Echten Snapshot über `WeatherSnapshotService.save` mit ≥2 Segmenten (unterschiedliche `end_time`/`elevation`/Temperatur) schreiben, `timeline()` aufrufen, prüfen: Anzahl Punkte == Segmentanzahl, `arrival_time` == jeweilige `segment.end_time`, `metrics.temp_max_c` entspricht dem gespeicherten Segmentwert. Kein Report-Code wird aufgerufen.

- **AC-2:** Given ein Snapshot mit stündlicher Reihe, When `drilldown(trip_id, metric, hours=12)` für eine einzelne Metrik aufgerufen wird, Then liefert das Ergebnis die nach Zeit sortierte stündliche Serie genau dieser Metrik für das Fenster (≤ `hours` Stunden), inklusive in der Summary normalerweise verborgener Metriken (z. B. `thunder_level`).
  - Test: Snapshot mit einem Segment speichern, dessen `timeseries` echte stündliche `ForecastDataPoint`s mit variierendem `thunder_level` enthält; nach `save`+`load` Roundtrip `drilldown(trip_id, "thunder_level", hours=12)` aufrufen; prüfen: Punkte chronologisch sortiert, je Stunde ein `ts`, `value` entspricht dem gespeicherten Stundenwert (Enum erhalten), Fenster respektiert `hours`.

- **AC-3:** Given ein fehlender Snapshot **oder** ein Snapshot ohne stündliche Reihe, When `timeline()` bzw. `drilldown()` aufgerufen wird, Then liefert der Extraktor einen klar erkennbaren Leerzustand (`available=False`, `message` gesetzt, leere `points`) statt einer Exception.
  - Test: (a) `timeline("nicht_existent")` → `available is False`, `points == []`, `message` nicht leer, keine Exception. (b) Alt-Snapshot ohne `hourly[]` (nur aggregiert) speichern, `drilldown(..., "thunder_level")` → `available is False`, leere Punkte, kein Crash.

## Mandantentrennung

`WeatherExtractor(user_id=...)` reicht `user_id` an `WeatherSnapshotService(user_id=...)`
durch — kein `"default"`-Fallback in einem nutzerbezogenen Pfad. Test mit **zwei** Nutzern:
User A hat Snapshot, User B nicht → A bekommt Daten, B bekommt Leerzustand.

## Non-Goals

- Keine Telegram-/Channel-Formatierung, keine Buttons (→ #653/#654).
- Kein erneuter Provider-Fetch, kein Report-Build.
- Kein Schreiben/Verändern von Trip-Daten.
