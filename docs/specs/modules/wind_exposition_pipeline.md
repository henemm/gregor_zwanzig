---
entity_id: wind_exposition_pipeline
type: module
created: 2026-02-18
updated: 2026-02-18
status: draft
version: "1.0"
tags: [pipeline, wind, exposition, integration, risk]
---

# F7b: Pipeline-Integration Wind-Exposition v1.0

## Approval

- [x] Approved

## Purpose

Verbindet `WindExpositionService` (F7) mit der Report-Pipeline, sodass RiskEngine Rule 9
(`WIND_EXPOSITION`) waehrend der Report-Generierung tatsaechlich feuert.

Aktuell existieren alle Komponenten (Service, Rule, Labels), aber kein Aufrufer uebergibt
`exposed_sections` — das Feature ist wirkungslos. Dieses Modul schliesst die Luecke durch
drei koordinierte Aenderungen an Scheduler und Formattern.

## Source

- **Geaendert:** `src/services/trip_report_scheduler.py` — berechnet kumulative Distanz und ruft `WindExpositionService` auf
- **Geaendert:** `src/formatters/trip_report.py` — nimmt `exposed_sections` entgegen und reicht sie an `_determine_risk()` weiter
- **Geaendert:** `src/formatters/sms_trip.py` — nimmt `exposed_sections` entgegen und reicht sie an `_detect_risk()` weiter

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WindExpositionService` | service (F7) | Erkennt exponierte Abschnitte aus Segment-Daten |
| `RiskEngine.assess_segment()` | service (F8) | Bewertet Risiken, akzeptiert bereits `exposed_sections` |
| `ExposedSection` | DTO (models.py) | Beschreibt einen exponierten Grat-/Pass-Abschnitt |
| `GPXPoint.distance_from_start_km` | DTO-Feld | Kumulierte Distanz — muss vom Scheduler gesetzt werden |
| `TripSegment` | DTO | Segment mit start_point/end_point (traegt distance-Felder) |

## Root-Cause-Analyse

### Warum feuert Rule 9 nie?

Die RiskEngine-Methode `assess_segment(segment, exposed_sections=None)` prueft
`exposed_sections` nur wenn der Parameter nicht `None` ist. Keiner der drei Aufruforte
uebergibt ihn:

```
trip_report_scheduler._send_trip_report()
    → format_email(segments=...) — kein exposed_sections
        → _determine_risk(segment)
            → engine.assess_segment(segment)  — exposed_sections=None → Rule 9 schweigt
```

### Weiteres Problem: distance_from_start_km = 0.0

Der Scheduler erstellt `GPXPoint`-Instanzen ohne `distance_from_start_km` zu setzen
(verwendet den Default `0.0`). Damit kann `WindExpositionService.detect_exposed_from_segments()`
keine sinnvollen `ExposedSection(start_km, end_km)`-Objekte erzeugen. Alle Segmente haetten
`start_km = 0.0, end_km = segment.distance_km`, was zu falschen Overlap-Checks fuehrt.

## Implementation Details

### 1) trip_report_scheduler.py — Kumulative Distanz + Exposition-Detection

**In `_convert_trip_to_segments()`** — kumulierte Distanz auf GPXPoints setzen:

```python
def _convert_trip_to_segments(self, trip, target_date):
    ...
    cumulative_dist_km = 0.0  # NEU: kumulierte Distanz tracken

    for i in range(len(waypoints) - 1):
        wp1 = waypoints[i]
        wp2 = waypoints[i + 1]
        ...
        dist_km = _haversine_km(wp1.lat, wp1.lon, wp2.lat, wp2.lon)

        segment = TripSegment(
            ...
            start_point=GPXPoint(
                lat=wp1.lat,
                lon=wp1.lon,
                elevation_m=float(elev1),
                distance_from_start_km=cumulative_dist_km,  # NEU
            ),
            end_point=GPXPoint(
                lat=wp2.lat,
                lon=wp2.lon,
                elevation_m=float(elev2),
                distance_from_start_km=cumulative_dist_km + round(dist_km, 1),  # NEU
            ),
            ...
        )
        cumulative_dist_km += round(dist_km, 1)  # NEU: akkumulieren
        segments.append(segment)
    ...
```

**In `_send_trip_report()`** — Exposition ermitteln und an Formatter uebergeben:

```python
def _send_trip_report(self, trip, report_type):
    ...
    segments = self._convert_trip_to_segments(trip, target_date)
    ...

    # NEU: Wind-Exposition ermitteln (nach Segment-Erstellung, vor format_email)
    from services.wind_exposition import WindExpositionService
    try:
        exposed = WindExpositionService().detect_exposed_from_segments(segments)
    except Exception as e:
        logger.warning(f"Wind exposition detection failed for {trip.id}: {e}")
        exposed = []

    # 7. Format report (exposed_sections NEU)
    report = self._formatter.format_email(
        segments=segment_weather,
        ...
        exposed_sections=exposed,  # NEU
    )
    ...
```

Hinweis: `detect_exposed_from_segments()` benoetigt die `TripSegment`-Liste (vor dem
Weather-Fetch), nicht die `SegmentWeatherData`-Liste. Reihenfolge im bestehenden Ablauf:
Segmente erstellen → Exposition berechnen → Wetter fetchen → Report formatieren.

### 2) trip_report.py — exposed_sections entgegennehmen und weiterreichen

**`format_email()` Signatur erweitern:**

```python
def format_email(
    self,
    segments: list[SegmentWeatherData],
    ...
    exposed_sections: Optional[list[ExposedSection]] = None,  # NEU
) -> TripReport:
    ...
    self._exposed_sections = exposed_sections  # NEU: speichern fuer _determine_risk
    ...
```

**`_determine_risk()` mit exposed_sections aufrufen:**

```python
def _determine_risk(self, segment: SegmentWeatherData) -> tuple[str, str]:
    engine = RiskEngine()
    assessment = engine.assess_segment(
        segment,
        exposed_sections=getattr(self, '_exposed_sections', None),  # NEU
    )
    ...
```

**Import ergaenzen** (am Dateianfang):

```python
from app.models import (
    ...
    ExposedSection,  # NEU
    ...
)
```

### 3) sms_trip.py — exposed_sections entgegennehmen und weiterreichen

**`format_sms()` Signatur erweitern:**

```python
def format_sms(
    self,
    segments: list[SegmentWeatherData],
    max_length: int = 160,
    exposed_sections: Optional[list[ExposedSection]] = None,  # NEU
) -> str:
    ...
    self._exposed_sections = exposed_sections  # NEU
    ...
```

**`_detect_risk()` mit exposed_sections aufrufen:**

```python
def _detect_risk(self, seg_data: SegmentWeatherData) -> tuple[Optional[str], Optional[str]]:
    engine = RiskEngine()
    assessment = engine.assess_segment(
        seg_data,
        exposed_sections=getattr(self, '_exposed_sections', None),  # NEU
    )
    ...
```

**Import ergaenzen** (am Dateianfang):

```python
from app.models import (
    ...
    ExposedSection,  # NEU
    ...
)
```

### Datenfluss nach der Implementierung

```
_convert_trip_to_segments()
    GPXPoint.distance_from_start_km gesetzt (kumuliert)
        ↓
WindExpositionService.detect_exposed_from_segments(segments)
    prueft start_point.elevation_m >= 2000m
    setzt ExposedSection(start_km, end_km) korrekt
        ↓
format_email(..., exposed_sections=exposed)
    self._exposed_sections = exposed
        ↓
_determine_risk(segment)
    engine.assess_segment(segment, exposed_sections=self._exposed_sections)
        ↓
RiskEngine Rule 9: WIND_EXPOSITION feuert wenn Overlap + Wind >= 30 km/h
```

### Kein SMS-Caller vorhanden

Die SMS-Formatierung (`SMSTripFormatter.format_sms()`) wird aktuell vom Scheduler
nicht aufgerufen — SMS ist noch nicht in der Report-Pipeline integriert. Trotzdem wird
`sms_trip.py` erweitert (future-proof), damit es konsistent mit `trip_report.py` bleibt
wenn SMS-Support ergaenzt wird.

## Expected Behavior

- **Input:** Normale Trip-Report-Anfrage (morning/evening), kein API-Change nach aussen
- **Output:** Wenn ein Segment durch einen Punkt >= 2000m fuehrt UND Wind >= 30 km/h:
  - E-Mail: Risk-Zelle zeigt "Exposed Ridge/Wind" bzw. "Exposed Ridge/Storm"
  - SMS: Risk-Label zeigt "GratWind" bzw. "GratSturm"
- **Side effects:** Keine — reine Datenverarbeitung, kein I/O ausser dem bestehenden E-Mail-Versand

### Beispiel-Szenario

Trip mit Segment durch einen Gipfel auf 2400m, Wind 35 km/h:

**Vorher (aktuell):**
- `engine.assess_segment(seg)` — `exposed_sections=None` → Rule 9 nie geprueft
- Risk: "✓ OK" (kein Wind-Risk, da 35 < 50 km/h Normalschwelle)

**Nachher (nach F7b):**
- `engine.assess_segment(seg, exposed_sections=[ExposedSection(start_km=8.2, end_km=8.8, ...)])`
- Segment overlaps ExposedSection → Rule 9 aktiv → Wind 35 >= 30 km/h Expositions-Schwelle
- Risk: "Exposed Ridge/Wind" (MODERATE)

### Edge Cases

| Situation | Verhalten |
|-----------|-----------|
| Alle Waypoints unter 2000m | `exposed = []` → `assess_segment(seg, exposed_sections=[])` → Rule 9 nicht getriggert |
| `WindExpositionService` wirft Exception | `exposed = []` (nach catch) → kein WIND_EXPOSITION Risk |
| `exposed_sections=None` vs `[]` | RiskEngine prueft `if exposed_sections:` → `None` und `[]` verhalten sich identisch (kein Rule 9) |
| Destination-Segment ("Ziel") | Wird wie normale Segmente behandelt — hat `distance_from_start_km` vom letzten Waypoint |

## Scope

| Datei | Aenderung | Geschaetzte LoC |
|-------|-----------|-----------------|
| `src/services/trip_report_scheduler.py` | Kumulative Distanz + Exposition-Call + exposed_sections an format_email | ~15 |
| `src/formatters/trip_report.py` | Signatur-Erweiterung + `self._exposed_sections` + an assess_segment | ~8 |
| `src/formatters/sms_trip.py` | Signatur-Erweiterung + `self._exposed_sections` + an assess_segment | ~8 |
| `tests/integration/test_wind_exposition_pipeline.py` | NEU — Integration-Tests | ~60 |
| **Total** | | **~91** |

### Out of Scope

- SMS-Caller im Scheduler (SMS-Pipeline existiert noch nicht)
- Aenderungen an `RiskEngine` oder `WindExpositionService` — beide sind bereits korrekt implementiert
- Aenderungen an Risk-Labels — bereits in `_RISK_LABELS` und `_SMS_RISK_LABELS` vorhanden
- `detect_exposed_sections(track)` (GPX-Track-Variante) — nicht noetig, Scheduler hat keinen GPXTrack

## Test Plan

### Integration Tests (test_wind_exposition_pipeline.py)

- [ ] `test_cumulative_distance_set`: Nach `_convert_trip_to_segments()` haben GPXPoints korrekte `distance_from_start_km` (monoton steigend, erster = 0.0)
- [ ] `test_exposed_sections_passed_to_engine`: Segment auf 2400m + Wind 35 km/h → `WIND_EXPOSITION` Risk in E-Mail-Report
- [ ] `test_no_exposition_below_threshold`: Alle Segmente unter 2000m → kein `WIND_EXPOSITION` Risk
- [ ] `test_low_wind_no_exposition_risk`: Segment auf 2400m + Wind 25 km/h → kein `WIND_EXPOSITION` Risk (unter 30 km/h Schwelle)
- [ ] `test_exposition_moderate_risk`: Wind 35 km/h + exponiertes Segment → `WIND_EXPOSITION MODERATE`
- [ ] `test_exposition_high_risk`: Wind 55 km/h + exponiertes Segment → `WIND_EXPOSITION HIGH`
- [ ] `test_sms_formatter_accepts_exposed_sections`: `format_sms(segments, exposed_sections=...)` → kein TypeError
- [ ] `test_sms_grat_wind_label`: Exponiertes Segment + Wind >= 30 → SMS-Label "GratWind"
- [ ] `test_exposition_service_exception_handled`: Wenn WindExpositionService Fehler wirft → Report wird trotzdem generiert (kein WIND_EXPOSITION Risk)

## Acceptance Criteria

- [ ] `GPXPoint.distance_from_start_km` wird in `_convert_trip_to_segments()` kumuliert gesetzt (nicht mehr immer 0.0)
- [ ] `WindExpositionService.detect_exposed_from_segments()` wird in `_send_trip_report()` aufgerufen
- [ ] `format_email()` akzeptiert `exposed_sections` Parameter
- [ ] `format_sms()` akzeptiert `exposed_sections` Parameter
- [ ] Exponiertes Segment (>= 2000m) mit Wind >= 30 km/h erzeugt `WIND_EXPOSITION MODERATE` Risk
- [ ] Exponiertes Segment (>= 2000m) mit Wind >= 50 km/h erzeugt `WIND_EXPOSITION HIGH` Risk
- [ ] Nicht-exponiertes Segment (< 2000m) erzeugt kein `WIND_EXPOSITION` Risk
- [ ] Fehler in WindExpositionService werden abgefangen — Report wird dennoch generiert
- [ ] Alle bestehenden Tests weiterhin gruen (keine Regression)

## Known Limitations

- **Nur Segment-basierte Erkennung:** Verwendet `detect_exposed_from_segments()`, nicht die GPX-Track-Variante mit `detect_waypoints()`. Das bedeutet: Ein Segment ist exponiert wenn sein hoechster Punkt >= 2000m. Kurzfristige Gipfel innerhalb eines langen Talsegments koennen uebersehen werden.
- **min_elevation_m = 2000m hardcoded:** Derzeit kein Override per Trip-Konfiguration.
- **Destination-Segment "Ziel":** Repraesentiert einen Punkt (keine Strecke). Die kumulative Distanz am Ziel wird korrekt gesetzt, aber das Segment hat `distance_km = 0.0`. Exposition-Check basiert trotzdem auf Elevation, was korrekt ist.
- **SMS-Aufrufer fehlt:** `format_sms()` wird derzeit nicht vom Scheduler aufgerufen, daher sind die SMS-Aenderungen nur Future-proofing.

## Changelog

- 2026-02-18: v1.0 — Initial spec created
