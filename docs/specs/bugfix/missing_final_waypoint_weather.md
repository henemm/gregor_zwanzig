---
entity_id: missing_final_waypoint_weather
type: bugfix
created: 2026-02-16
updated: 2026-02-16
version: "1.0"
status: draft
severity: MEDIUM
tags: [trip-report, waypoints, segments, formatter, weather-data]
---

# Bugfix: Letzter Waypoint fehlt in Trip-Report → Kein Wetter am Zielort

## Approval

- [ ] Approved for implementation

## Symptom

Trip-Reports zeigen kein Wetter für den letzten Waypoint einer Etappe.

**Beispiel: GR221 Mallorca — Tag 2 (Deià → Sóller)**

Waypoints:
- G1: Deià (Start, 08:00)
- G2: Coll de Sóller (Zwischenpunkt, 10:30)
- G3: Sóller (Ziel, 12:00)

Erwartete Segmente:
- Segment 1: Deià → Coll de Sóller (08:00-10:30)
- Segment 2: Coll de Sóller → Sóller (10:30-12:00)

**Tatsächliches Verhalten:**

Trip-Report zeigt nur Wetter für:
- Deià (G1, Segment 1 Start)
- Coll de Sóller (G2, Segment 2 Start)

**Fehlendes Wetter:**
- Sóller (G3, Zielort) — kein Wetter sichtbar

**Business Impact:**
- Wanderer weiß nicht, wie das Wetter am Zielort wird
- Fehlende Info für Ankunftsplanung (z.B. Gewitter bei Ankunft?)
- Inconsistenz: Nacht-Tabelle nutzt letzten Waypoint als Referenz, aber Tags-Wetter fehlt

## Root Cause

Das System erstellt aus N Waypoints N-1 Segmente. Jedes Segment fragt nur Wetter am `start_point` ab, der `end_point` des letzten Segments wird ignoriert.

### Problem 1: Segment-Erzeugung ohne Ziel-Segment

```python
# src/services/trip_report_scheduler.py:365-441
def _convert_trip_to_segments(self, trip, target_date, default_start):
    segments = []
    for i in range(len(waypoints) - 1):  # N-1 Segmente!
        wp1 = waypoints[i]
        wp2 = waypoints[i + 1]
        segment = TripSegment(
            segment_id=i + 1,
            start_point=GPXPoint(...wp1...),
            end_point=GPXPoint(...wp2...),  # wp2 nur als Geometrie!
            ...
        )
        segments.append(segment)
    return segments  # Letzter Waypoint nur als end_point des letzten Segments
```

**Konsequenz:**
- 3 Waypoints → 2 Segmente (G1→G2, G2→G3)
- G3 ist nur `end_point` von Segment 2, nie `start_point` eines Segments

### Problem 2: segment_weather.py fragt nur start_point ab

```python
# src/services/segment_weather.py:116-123
location = Location(
    latitude=segment.start_point.lat,
    longitude=segment.start_point.lon,
    name=f"Segment {segment.segment_id}",
    ...
)
timeseries = self._provider.fetch_forecast(location, ...)
```

**Konsequenz:**
- Segment 1: Wetter an G1 (Deià) ✓
- Segment 2: Wetter an G2 (Coll de Sóller) ✓
- G3 (Sóller): Nie abgefragt ✗

### Problem 3: Nacht-Wetter nutzt end_point, aber Tags-Wetter nicht

```python
# src/services/trip_report_scheduler.py:474-501
def _fetch_night_weather(self, trip, segments):
    last_seg = segments[-1]
    night_location = Location(
        latitude=last_seg.end_point.lat,  # Nutzt end_point!
        longitude=last_seg.end_point.lon,
        name="Night Forecast",
        ...
    )
```

**Konsequenz:** Inconsistenz zwischen Tags-Wetter (fehlt G3) und Nacht-Wetter (nutzt G3).

## Design

### Zweistufige Lösung

**Fix 1:** Ziel-Segment erzeugen in `trip_report_scheduler.py`
**Fix 2:** Formatter rendert Ziel-Segment speziell (nicht als "Segment N+1")

Bestehende Segmente bleiben **unverändert** → keine Breaking Changes.

### Fix 1: Ziel-Segment in _convert_trip_to_segments()

Nach der bestehenden Segment-Schleife ein zusätzliches Ziel-Segment erzeugen:

```python
# src/services/trip_report_scheduler.py:365-441
def _convert_trip_to_segments(self, trip, target_date, default_start):
    segments = []
    waypoints = trip.waypoints

    # Bestehende Logik: N-1 Segmente (unverändert)
    for i in range(len(waypoints) - 1):
        # ... (Logik bleibt identisch) ...
        segments.append(segment)

    # NEU: Ziel-Segment hinzufügen
    if waypoints:
        last_wp = waypoints[-1]
        second_last_wp = waypoints[-2] if len(waypoints) > 1 else waypoints[-1]

        # Ankunftszeit am Ziel (aus letztem normalen Segment)
        if segments:
            arrival_time = segments[-1].end_time
        else:
            # Edge Case: Nur 1 Waypoint
            if last_wp.time_window:
                arrival_time = datetime.combine(
                    target_date, last_wp.time_window.start, tzinfo=timezone.utc
                )
            else:
                arrival_time = datetime.combine(
                    target_date, default_start, tzinfo=timezone.utc
                )

        # Ziel-Zeitfenster: Ankunft → Ankunft + 2h
        destination_end = arrival_time + timedelta(hours=2)

        # Ziel-Segment: start_point == end_point (Wetter AM Zielort)
        destination_segment = TripSegment(
            segment_id="Ziel",  # String statt int!
            start_point=GPXPoint(
                lat=last_wp.lat,
                lon=last_wp.lon,
                elevation_m=float(last_wp.elevation_m or 0),
            ),
            end_point=GPXPoint(  # Identisch mit start_point
                lat=last_wp.lat,
                lon=last_wp.lon,
                elevation_m=float(last_wp.elevation_m or 0),
            ),
            start_time=arrival_time,
            end_time=destination_end,
            duration_hours=2.0,
            distance_km=0.0,  # Kein Wegstrecke (Punkt)
            ascent_m=0.0,
            descent_m=0.0,
        )
        segments.append(destination_segment)

    return segments
```

**Änderungen:**
- `segment_id` Type: `int` → `int | str` (TripSegment Dataclass anpassen)
- Ziel-Segment hat `segment_id="Ziel"` statt numerisch
- `start_point == end_point` (Wetter an diesem Punkt)
- Zeitfenster: 2h ab Ankunft (für sinnvolle Wetterprognose)
- `distance_km=0.0`, `ascent_m=0.0`, `descent_m=0.0`

**Begründung:**
- Keine Änderung in `segment_weather.py` nötig (start_point wird korrekt abgefragt)
- Bestehende Segmente bleiben identisch (ID 1, 2, 3, ...)
- Ziel-Segment ist additiv (kein Breaking Change)

### Fix 2: TripSegment Dataclass erweitern

```python
# src/app/models.py:276-290
@dataclass
class TripSegment:
    """Single segment of a trip (typically ~2 hours hiking)."""
    segment_id: int | str  # GEÄNDERT: int → int | str (für "Ziel")
    start_point: GPXPoint
    end_point: GPXPoint
    start_time: datetime  # UTC!
    end_time: datetime  # UTC!
    duration_hours: float
    distance_km: float
    ascent_m: float
    descent_m: float
    # Optional fields
    adjusted_to_waypoint: bool = False
    waypoint: Optional["DetectedWaypoint"] = None
```

**Änderung:** `segment_id: int` → `segment_id: int | str`

**Begründung:** Ermöglicht String-IDs wie `"Ziel"` für semantische Klarheit.

**Alternative:** `is_destination: bool = False` Flag hinzufügen
- **Verworfen:** String-ID ist expliziter und benötigt keine Typ-Checks im Formatter

### Fix 3: Formatter rendert Ziel-Segment speziell

#### HTML-Rendering anpassen

```python
# src/formatters/trip_report.py:520-524
# VORHER:
seg_html_parts.append(f"""
<div class="section">
    <h3>Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m</h3>
    {self._render_html_table(rows)}
</div>""")

# NACHHER:
if seg.segment_id == "Ziel":
    # Ziel-Segment: Spezielles Rendering
    seg_html_parts.append(f"""
    <div class="section destination">
        <h3>🏁 Wetter am Ziel: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {s_elev}m</h3>
        {self._render_html_table(rows)}
    </div>""")
else:
    # Normales Segment
    seg_html_parts.append(f"""
    <div class="section">
        <h3>Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m</h3>
        {self._render_html_table(rows)}
    </div>""")
```

#### Plain-Text-Rendering anpassen

```python
# src/formatters/trip_report.py:694-697
# VORHER:
lines.append(f"━━ Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m ━━")

# NACHHER:
if seg.segment_id == "Ziel":
    lines.append(f"━━ 🏁 Wetter am Ziel: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {s_elev}m ━━")
else:
    lines.append(f"━━ Segment {seg.segment_id}: {seg.start_time.strftime('%H:%M')}–{seg.end_time.strftime('%H:%M')} | {seg.distance_km:.1f} km | ↑{s_elev}m → {e_elev}m ━━")
```

#### Highlights anpassen (optional)

Highlights sollen Ziel-Segment als "am Ziel" referenzieren, nicht als "Segment Ziel":

```python
# src/formatters/trip_report.py:261, 323, 333
# VORHER:
f"Segment {seg_data.segment.segment_id}"

# NACHHER:
"am Ziel" if seg_data.segment.segment_id == "Ziel" else f"Segment {seg_data.segment.segment_id}"
```

**Beispiel-Output:**
```
Highlights:
  ⚡ Gewitter möglich ab 12:15 (am Ziel, >800m)
  💨 Böen bis 76 km/h (Segment 2, 10:00)
```

## Affected Files

| Datei | Änderung | LOC |
|-------|----------|-----|
| `src/app/models.py` | TripSegment.segment_id Type: `int` → `int \| str` | ~1 |
| `src/services/trip_report_scheduler.py` | Ziel-Segment erzeugen in `_convert_trip_to_segments()` | ~40 |
| `src/formatters/trip_report.py` | Ziel-Segment speziell rendern (HTML + Text + Highlights) | ~15 |
| `tests/unit/test_trip_report_formatter_v2.py` | Test für Ziel-Segment (NEU) | ~35 |
| **Gesamt** | | **~91 LOC** |

**Keine Änderungen in:**
- `src/services/segment_weather.py` — Logik bleibt identisch (start_point wird abgefragt)
- `src/app/loader.py` — Waypoint-Parsing bleibt identisch
- `src/providers/openmeteo.py` — API-Calls bleiben identisch

## Test Plan

### Automatisiert (NEUE Tests in test_trip_report_formatter_v2.py)

**Test 1: test_destination_segment_has_final_waypoint_weather**
```python
def test_destination_segment_has_final_waypoint_weather():
    """Verify destination segment shows weather at final waypoint location."""
    segments = create_test_segments_with_destination()  # 3 waypoints → 2 normal + 1 destination

    # Verify segment IDs
    assert len(segments) == 3
    assert segments[0].segment_id == 1
    assert segments[1].segment_id == 2
    assert segments[2].segment_id == "Ziel"

    # Verify destination segment geography
    dest_seg = segments[2]
    assert dest_seg.start_point.lat == dest_seg.end_point.lat
    assert dest_seg.start_point.lon == dest_seg.end_point.lon
    assert dest_seg.distance_km == 0.0
    assert dest_seg.ascent_m == 0.0

    # Verify destination segment time window
    assert dest_seg.start_time == segments[1].end_time  # Starts at arrival
    assert (dest_seg.end_time - dest_seg.start_time).total_seconds() == 7200  # 2h
```

**Test 2: test_formatter_renders_destination_segment_specially**
```python
def test_formatter_renders_destination_segment_specially():
    """Verify destination segment has special rendering in HTML and text."""
    formatter = TripReportFormatter()
    segments = create_test_segments_with_destination()
    report = formatter.format_email(segments, "Test Trip", "morning")

    # HTML: Ziel-Segment hat spezielle Überschrift
    assert "🏁 Wetter am Ziel" in report.html_body
    assert '<div class="section destination">' in report.html_body

    # Plain Text: Ziel-Segment hat spezielle Überschrift
    assert "🏁 Wetter am Ziel" in report.plain_text_body

    # Normale Segmente behalten Standard-Format
    assert "Segment 1:" in report.html_body
    assert "Segment 2:" in report.html_body
```

**Test 3: test_highlights_reference_destination_correctly**
```python
def test_highlights_reference_destination_correctly():
    """Verify highlights reference destination segment as 'am Ziel' not 'Segment Ziel'."""
    formatter = TripReportFormatter()
    segments = create_test_segments_with_destination()
    # Inject thunder forecast at destination
    thunder_forecast = {
        "segments": [
            {"segment_id": "Ziel", "level": ThunderLevel.POSSIBLE, "time": "12:15"}
        ]
    }
    report = formatter.format_email(
        segments, "Test Trip", "morning", thunder_forecast=thunder_forecast
    )

    # Highlight soll "am Ziel" sagen, nicht "Segment Ziel"
    assert "am Ziel" in report.html_body
    assert "Segment Ziel" not in report.html_body
```

**Test 4: test_single_waypoint_trip_gets_destination_segment**
```python
def test_single_waypoint_trip_gets_destination_segment():
    """Edge Case: Trip mit nur 1 Waypoint bekommt trotzdem Ziel-Segment."""
    trip = create_single_waypoint_trip()  # Nur 1 Waypoint
    scheduler = TripReportScheduler()
    segments = scheduler._convert_trip_to_segments(trip, date.today(), time(8, 0))

    # Erwartung: 1 Ziel-Segment
    assert len(segments) == 1
    assert segments[0].segment_id == "Ziel"
    assert segments[0].start_point.lat == segments[0].end_point.lat
```

**Test 5: test_night_weather_location_matches_destination**
```python
def test_night_weather_location_matches_destination():
    """Verify night weather uses same location as destination segment."""
    trip = create_test_trip()
    scheduler = TripReportScheduler()
    segments = scheduler._convert_trip_to_segments(trip, date.today(), time(8, 0))

    # Hole Nacht-Wetter-Location
    night_location = scheduler._get_night_location(trip, segments)

    # Muss mit Ziel-Segment übereinstimmen
    dest_seg = segments[-1]  # Letztes Segment = Ziel
    assert night_location.latitude == dest_seg.start_point.lat
    assert night_location.longitude == dest_seg.start_point.lon
```

### Manuell (Regressionsprüfung)

- [ ] Trip mit 3 Waypoints → E-Mail zeigt 3 Wetterblöcke (Segment 1, Segment 2, Ziel)
- [ ] Ziel-Segment hat Icon 🏁 und keine Distanz/Höhenmeter
- [ ] Highlights referenzieren Ziel korrekt ("am Ziel" statt "Segment Ziel")
- [ ] Nacht-Tabelle nutzt gleichen Ort wie Ziel-Segment
- [ ] Trip mit 1 Waypoint → E-Mail zeigt nur Ziel-Segment

## Edge Cases

| Szenario | Komponente | Verhalten nach Fix |
|----------|------------|-------------------|
| Trip mit 1 Waypoint | `_convert_trip_to_segments()` | 1 Ziel-Segment, start_time aus waypoint.time_window |
| Trip mit 2 Waypoints | `_convert_trip_to_segments()` | 1 normales Segment + 1 Ziel-Segment |
| Trip mit N Waypoints | `_convert_trip_to_segments()` | N-1 normale Segmente + 1 Ziel-Segment |
| Letzter Waypoint ohne time_window | `_convert_trip_to_segments()` | Ankunftszeit aus letztem normalen Segment (end_time) |
| Highlight referenziert Ziel | `_compute_highlights()` | "am Ziel" statt "Segment Ziel" |
| Nacht-Wetter-Location | `_fetch_night_weather()` | Nutzt Ziel-Segment.start_point (identisch mit bisherigem end_point) |
| segment_weather.py Query | `query_segment_weather()` | Ziel-Segment start_point wird abgefragt → korrekt |
| Segment-ID in Logs | `logger.info()` | "Segment Ziel" erscheint in Logs (kein Problem) |

## Known Limitations

### Ziel-Segment hat 2h Zeitfenster (nicht bis Tagesende)

**Grund:**
- OpenMeteo API liefert nur sinnvolle Prognosen in kurzen Fenstern
- 2h reicht für Ankunfts-Wetter (Gewitter? Regen? Temperatur?)

**Akzeptabel:**
- Wanderer braucht primär Wetter zur Ankunftszeit
- Nacht-Wetter deckt späteren Abend/Nacht ab

### Ziel-Segment ist additiv (nicht retroaktiv)

**Bestehende Trips:**
- Bereits generierte Reports haben noch kein Ziel-Segment
- Nächster Report-Durchlauf erzeugt Ziel-Segment automatisch

**Akzeptabel:**
- Kein Datenmigrations-Bedarf (Trips werden täglich neu generiert)

### segment_id Type-Change kann Legacy-Code brechen

**Risiko:**
- Code der `segment_id` als `int` annimmt (z.B. `segment_id + 1`)
- Muss mit `int | str` umgehen oder Type-Check einbauen

**Mitigation:**
- Grep nach `segment_id` in Codebase (bereits erledigt: nur Formatter betroffen)
- Formatter nutzt `segment_id` nur für String-Formatierung (kein Problem)

## Acceptance Criteria

- [ ] Trip mit 3 Waypoints erzeugt 2 normale Segmente + 1 Ziel-Segment
- [ ] Ziel-Segment hat `segment_id="Ziel"` (String)
- [ ] Ziel-Segment `start_point == end_point` (letzter Waypoint)
- [ ] Ziel-Segment Zeitfenster: Ankunft → Ankunft + 2h
- [ ] E-Mail HTML zeigt "🏁 Wetter am Ziel" statt "Segment Ziel"
- [ ] E-Mail Plain-Text zeigt "🏁 Wetter am Ziel"
- [ ] Highlights referenzieren Ziel als "am Ziel"
- [ ] Nacht-Wetter nutzt gleiche Location wie Ziel-Segment
- [ ] Test `test_destination_segment_has_final_waypoint_weather` grün
- [ ] Test `test_formatter_renders_destination_segment_specially` grün
- [ ] Test `test_highlights_reference_destination_correctly` grün
- [ ] Test `test_single_waypoint_trip_gets_destination_segment` grün
- [ ] Test `test_night_weather_location_matches_destination` grün
- [ ] Bestehende Tests bleiben grün (keine Regression)

## Changelog

- 2026-02-16: v1.0 Bugfix-Spec erstellt (missing_final_waypoint_weather)
