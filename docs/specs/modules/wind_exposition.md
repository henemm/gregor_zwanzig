---
entity_id: wind_exposition
type: module
created: 2026-02-18
updated: 2026-02-18
status: draft
version: "1.0"
tags: [risk, wind, gpx, elevation, exposition, service]
---

# F7: Wind-Exposition (Grat-Erkennung) v1.0

## Approval

- [x] Approved

## Purpose

Erkennt aus dem GPX-Hoehenprofil exponierte Gratabschnitte und warnt bei starkem Wind.
Grate sind per Definition exponiert: hohe Lage, wenig Windschatten, Absturzgefahr.
Wenn auf einem Gratabschnitt starker Wind vorhergesagt wird, eskaliert der Wind-Risk
um eine Stufe (MODERATE→HIGH) oder erzeugt einen neuen Risk (LOW→MODERATE).

### Kernidee

Ein **Grat** ist ein laengerer Abschnitt nahe einer erkannten Gipfel-/Pass-Region
mit hoher Exposition (steile Flanken beidseitig). Die Erkennung basiert auf:

1. **Existing**: `elevation_analysis.detect_waypoints()` findet GIPFEL und PASS
2. **Neu**: Fuer jeden Segment wird geprueft ob er durch eine exponierte Zone verlaeuft
3. **Neu**: RiskEngine Rule 9 (WIND_EXPOSITION) wird basierend auf Position + Wind getriggert

## Source

- **File:** `src/services/wind_exposition.py`
- **Identifier:** `WindExpositionService`
- **Integration:** `src/services/risk_engine.py` — Rule 9

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `elevation_analysis` | core | Erkennt Gipfel/Pass aus GPX |
| `risk_engine` | service | F8 RiskEngine fuer Rule-Integration |
| `models` | DTOs | GPXTrack, SegmentWeatherData, Risk, RiskType |
| `metric_catalog` | config | Wind-Thresholds fuer Exposition |

## Data Model

### Neues DTO: `ExposedSection`

```python
@dataclass
class ExposedSection:
    """An exposed ridge/pass section on the track."""
    start_km: float          # Distance from start where exposure begins
    end_km: float            # Distance from start where exposure ends
    max_elevation_m: float   # Highest point in section
    exposition_type: str     # "GRAT" | "PASS"
```

### Neuer RiskType

```python
class RiskType(str, Enum):
    ...
    WIND_EXPOSITION = "wind_exposition"  # NEU
```

## Implementation Details

### 1) WindExpositionService

```python
class WindExpositionService:
    """Detects exposed ridge sections from GPX elevation profile."""

    def detect_exposed_sections(
        self,
        track: GPXTrack,
        radius_km: float = 0.3,
        min_elevation_m: float = 2000.0,
    ) -> list[ExposedSection]:
        """
        Find exposed sections near detected peaks/passes.

        Algorithm:
        1. Run detect_waypoints() on the track
        2. For each GIPFEL/PASS waypoint above min_elevation_m:
           - Create ExposedSection from (waypoint_km - radius_km) to (waypoint_km + radius_km)
        3. Merge overlapping sections
        4. Return sorted by start_km

        Args:
            track: GPX track with elevation data
            radius_km: How far around each peak counts as exposed (default 0.3km = 300m)
            min_elevation_m: Minimum elevation for a peak to count as exposed

        Returns:
            List of ExposedSection, sorted by start_km, merged if overlapping
        """
```

### 2) RiskEngine Integration (Rule 9)

In `risk_engine.py`, neue Methode + Aufruf in `assess_segment()`:

```python
def assess_segment(
    self,
    segment: SegmentWeatherData,
    exposed_sections: list[ExposedSection] | None = None,  # NEU
) -> RiskAssessment:
    ...
    # Rule 9: Wind Exposition (if segment overlaps exposed section)
    if exposed_sections:
        self._check_wind_exposition(agg, segment, exposed_sections, risks)
    ...
```

```python
def _check_wind_exposition(
    self,
    agg: SegmentWeatherSummary,
    segment: SegmentWeatherData,
    exposed_sections: list[ExposedSection],
    risks: list[Risk],
) -> None:
    """Rule 9: Escalate wind risk if segment crosses exposed section.

    Logic:
    - Check if segment distance range overlaps any ExposedSection
    - If overlap AND wind >= 30 km/h: MODERATE
    - If overlap AND wind >= 50 km/h: HIGH
    - Thresholds are LOWER than normal wind thresholds (exposed = more dangerous)
    """
```

### 3) Schwellwerte

Exponierte Abschnitte haben **niedrigere** Wind-Schwellwerte als normal:

| Metric | Normal (MetricCatalog) | Exponiert |
|--------|----------------------|-----------|
| Wind | medium: 50, high: 70 | medium: 30, high: 50 |
| Gust | medium: 60, high: 80 | medium: 40, high: 60 |

Diese werden als `exposition_risk_thresholds` im MetricCatalog gespeichert:

```python
MetricDefinition(
    id="wind",
    ...
    exposition_risk_thresholds={"medium": 30, "high": 50},
)
```

### 4) Formatter-Anzeige

#### trip_report.py

Neuer Risk-Label in `_RISK_LABELS`:
```python
(RiskType.WIND_EXPOSITION, RiskLevel.HIGH): "⚠️ Exposed Ridge/Storm",
(RiskType.WIND_EXPOSITION, RiskLevel.MODERATE): "⚠️ Exposed Ridge/Wind",
```

#### sms_trip.py

Neuer Label in `_SMS_RISK_LABELS`:
```python
(RiskType.WIND_EXPOSITION, RiskLevel.HIGH): "GratSturm",
(RiskType.WIND_EXPOSITION, RiskLevel.MODERATE): "GratWind",
```

### 5) Pipeline-Integration

In `trip_report_scheduler.py` (oder wo der Report-Flow gestartet wird):

```python
# Before risk assessment:
from services.wind_exposition import WindExpositionService

if trip.has_gpx_track():
    exposition_svc = WindExpositionService()
    exposed = exposition_svc.detect_exposed_sections(trip.gpx_track)
else:
    exposed = None

# Pass to risk engine:
assessment = engine.assess_segment(segment, exposed_sections=exposed)
```

## Expected Behavior

- **Input:** GPXTrack mit Hoehenprofil + SegmentWeatherData mit Wind-Daten
- **Output:** Zusaetzlicher Risk(WIND_EXPOSITION, MODERATE/HIGH) wenn Segment durch exponierten Grat verlaeuft UND Wind >= 30 km/h
- **Side effects:** Keine (reine Daten-Analyse)

### Beispiele

1. **Gipfel auf 2800m, Wind 35 km/h** → Risk(WIND_EXPOSITION, MODERATE)
   - Normal waere kein Wind-Risk (unter 50 km/h Schwelle)
   - Aber exponierter Grat → niedrigere Schwelle → MODERATE

2. **Talabschnitt auf 1200m, Wind 35 km/h** → Kein Risk
   - Nicht exponiert, unter normaler Schwelle

3. **Gipfel auf 1800m, Wind 35 km/h** → Kein Risk
   - Unter min_elevation_m (2000m default)

4. **Gipfel auf 2500m, Wind 55 km/h** → Risk(WIND_EXPOSITION, HIGH) + Risk(WIND, MODERATE)
   - Exponiert + hoher Wind → WIND_EXPOSITION HIGH
   - Normal-Wind-Schwelle (50) auch ueberschritten → WIND MODERATE
   - Deduplication: WIND_EXPOSITION und WIND sind verschiedene RiskTypes, beide bleiben

## Scope

### Phase 1 (dieses Feature)

| Datei | Aenderung | LoC |
|-------|-----------|-----|
| `src/services/wind_exposition.py` | **NEU** — WindExpositionService | ~60 |
| `src/services/risk_engine.py` | Rule 9 + `_check_wind_exposition()` | ~30 |
| `src/app/models.py` | `ExposedSection` DTO + `WIND_EXPOSITION` RiskType | ~10 |
| `src/app/metric_catalog.py` | `exposition_risk_thresholds` fuer wind/gust | ~5 |
| `src/formatters/trip_report.py` | Risk-Labels fuer WIND_EXPOSITION | ~3 |
| `src/formatters/sms_trip.py` | SMS-Labels fuer WIND_EXPOSITION | ~3 |
| `tests/integration/test_wind_exposition.py` | **NEU** — Tests | ~80 |
| **Total** | | **~191** |

### Out of Scope

- Hangneigung-Analyse (zu komplex fuer Phase 1)
- Wind-Richtung vs. Grat-Orientierung (erfordert Wind-Richtungsvektor + Grat-Azimut)
- Dynamische min_elevation_m basierend auf Region (Alpen vs. Mittelgebirge)

## Known Limitations

- **min_elevation_m = 2000m** ist ein sinnvoller Default fuer die Alpen, aber nicht universal
- **radius_km = 0.3** ist eine Approximation; echte Grat-Laenge variiert stark
- Grat-Erkennung basiert auf Gipfeln/Paessen, nicht auf der echten Topografie
- Trips ohne GPX-Track (nur Waypoints) bekommen keine Exposition-Analyse

## Changelog

- 2026-02-18: Initial spec v1.0 created
