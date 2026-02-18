---
entity_id: risk_engine
type: module
created: 2025-12-27
updated: 2026-02-18
status: draft
version: "2.0"
tags: [risk, weather, logic, service, daten-layer]
---

# F8: Risk Engine (Daten-Layer) v2.0

## Approval

- [x] Approved

## Purpose

Zentralisiert die verstreute Risk-Assessment-Logik in einen eigenstaendigen Service. Bewertet `SegmentWeatherData` anhand der `MetricCatalog`-Schwellwerte und gibt strukturierte `RiskAssessment`-Objekte zurueck. Reine Daten-Schicht — KEINE Handlungsempfehlungen, KEIN Rendering.

### Problem (v1.0 → v2.0)

Risk-Logik ist aktuell in **4 Dateien verstreut** mit inkonsistenten Schwellwerten:

| Datei | Methode | Problem |
|-------|---------|---------|
| `trip_report.py` | `_determine_risk()` | Risk-Assessment im Formatter (SoC-Verletzung) |
| `trip_report.py` | `_compute_highlights()` | Mischt Datenanalyse + Rendering |
| `sms_trip.py` | `_detect_risk()` | Eigene hardcoded Schwellen (50/70/20) |
| `compact_summary.py` | `_format_wind()` | Wind-Adjektive hardcoded (15/35/60) |

Die DTOs `Risk` und `RiskAssessment` in `models.py` sind **definiert aber nirgends instantiiert**.

### Loesung v2.0

Ein `RiskEngine`-Service der:
1. `SegmentWeatherData` entgegennimmt (Aggregat-Level, nicht Timeseries)
2. Risk-Schwellen aus `MetricCatalog.risk_thresholds` liest
3. `RiskAssessment` mit strukturierten `Risk`-Objekten zurueckgibt
4. Von allen Formattern aufgerufen wird statt eigener Logik

## Source

- **Neu:** `src/services/risk_engine.py` — `class RiskEngine`
- **Aenderung:** `src/formatters/trip_report.py` — `_determine_risk()` delegiert an Engine
- **Aenderung:** `src/formatters/sms_trip.py` — `_detect_risk()` delegiert an Engine
- **Keine Aenderung:** `src/app/models.py` — Risk/RiskAssessment DTOs bleiben wie definiert
- **Keine Aenderung:** `src/app/metric_catalog.py` — risk_thresholds bleiben wie definiert

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| MetricCatalog | Registry | Source-of-Truth fuer risk_thresholds |
| SegmentWeatherData | DTO | Input (enthaelt aggregated: SegmentWeatherSummary) |
| SegmentWeatherSummary | DTO | Aggregierte Metriken pro Segment |
| Risk | DTO | Output — einzelnes Risiko (bereits in models.py definiert) |
| RiskAssessment | DTO | Output — Sammlung von Risiken (bereits in models.py definiert) |
| RiskType | Enum | thunderstorm, rain, wind, wind_chill, poor_visibility, etc. |
| RiskLevel | Enum | LOW, MODERATE, HIGH |
| ThunderLevel | Enum | NONE, MED, HIGH (Sonderbehandlung: enum-basiert, nicht numerisch) |

## Implementation Details

### 1) RiskEngine Service (src/services/risk_engine.py)

```python
class RiskEngine:
    """
    Zentrales Risk-Assessment: SegmentWeatherSummary → RiskAssessment.

    Liest Schwellen aus MetricCatalog. Reine Daten-Schicht,
    kein Rendering, keine Handlungsempfehlungen.
    """

    def assess_segment(self, segment: SegmentWeatherData) -> RiskAssessment:
        """
        Bewertet ein einzelnes Segment.

        Returns:
            RiskAssessment mit 0..N Risk-Objekten, sortiert nach Level (HIGH zuerst).
        """

    def assess_segments(self, segments: list[SegmentWeatherData]) -> list[RiskAssessment]:
        """Convenience: assess_segment() fuer jedes Segment."""

    def get_max_risk_level(self, assessment: RiskAssessment) -> RiskLevel:
        """Hoechstes Risk-Level in einem Assessment (fuer Segment-Coloring)."""
```

### 2) Risk-Assessment-Regeln

Die Engine prueft folgende Metriken in dieser Reihenfolge. Jede Regel erzeugt 0 oder 1 `Risk`-Objekt pro Segment.

**Regel 1: Thunder (enum-basiert)**
```python
if agg.thunder_level_max == ThunderLevel.HIGH:
    → Risk(type=THUNDERSTORM, level=HIGH)
elif agg.thunder_level_max == ThunderLevel.MED:
    → Risk(type=THUNDERSTORM, level=MODERATE)
```

**Regel 2: CAPE (Gewitterenergie)**
```python
rt = get_metric("cape").risk_thresholds  # {"medium": 1000, "high": 2000}
if agg.cape_max_jkg >= rt["high"]:
    → Risk(type=THUNDERSTORM, level=HIGH)
elif agg.cape_max_jkg >= rt["medium"]:
    → Risk(type=THUNDERSTORM, level=MODERATE)
```
Wenn Regel 1 schon THUNDERSTORM HIGH ergab: Kein Duplikat. Hoechstes Level gewinnt.

**Regel 3: Wind**
```python
rt = get_metric("wind").risk_thresholds  # {"medium": 50, "high": 70}
if agg.wind_max_kmh > rt["high"]:
    → Risk(type=WIND, level=HIGH, gust_kmh=agg.gust_max_kmh)
elif agg.wind_max_kmh > rt["medium"]:
    → Risk(type=WIND, level=MODERATE, gust_kmh=agg.gust_max_kmh)
```

**Regel 4: Gust (zusaetzlich zu Wind)**
```python
rt = get_metric("gust").risk_thresholds  # {"medium": 50, "high": 70}
if agg.gust_max_kmh > rt["high"]:
    → Risk(type=WIND, level=HIGH, gust_kmh=agg.gust_max_kmh)
elif agg.gust_max_kmh > rt["medium"]:
    → Risk(type=WIND, level=MODERATE, gust_kmh=agg.gust_max_kmh)
```
Wind und Gust erzeugen beide `RiskType.WIND`. Hoechstes Level gewinnt, kein Duplikat.

**Regel 5: Niederschlag**
```python
rt = get_metric("precipitation").risk_thresholds  # {"medium": 20}
if agg.precip_sum_mm > rt["medium"]:
    → Risk(type=RAIN, level=MODERATE, amount_mm=agg.precip_sum_mm)
```

**Regel 6: Regenwahrscheinlichkeit**
```python
rt = get_metric("rain_probability").risk_thresholds  # aktuell leer!
# Nur wenn risk_thresholds definiert sind:
if rt.get("medium") and agg.pop_max_pct >= rt["medium"]:
    → Risk(type=RAIN, level=MODERATE)
```
Aktuell: POP hat KEINE risk_thresholds im Catalog. Das bisherige hardcoded `>= 80` wird in den Catalog migriert: `risk_thresholds={"medium": 80}`.

**Regel 7: Wind-Chill (invertiert)**
```python
rt = get_metric("wind_chill").risk_thresholds  # {"high_lt": -20}
if agg.wind_chill_min_c < rt["high_lt"]:
    → Risk(type=WIND_CHILL, level=HIGH, feels_like_c=agg.wind_chill_min_c)
```

**Regel 8: Sichtweite (invertiert)**
```python
rt = get_metric("visibility").risk_thresholds  # {"high_lt": 100}
if agg.visibility_min_m < rt["high_lt"]:
    → Risk(type=POOR_VISIBILITY, level=HIGH, visibility_m=agg.visibility_min_m)
```

### 3) Deduplizierung

Pro `RiskType` wird nur das hoechste `RiskLevel` behalten. Beispiel: Wenn Wind-Speed MODERATE und Gust HIGH ergibt, bleibt nur `Risk(type=WIND, level=HIGH)`.

```python
def _deduplicate(self, risks: list[Risk]) -> list[Risk]:
    """Pro RiskType nur hoechstes Level behalten."""
    best: dict[RiskType, Risk] = {}
    for risk in risks:
        existing = best.get(risk.type)
        if existing is None or _level_order(risk.level) > _level_order(existing.level):
            best[risk.type] = risk
    return sorted(best.values(), key=lambda r: _level_order(r.level), reverse=True)
```

### 4) Formatter-Migration: trip_report.py

**Vorher:**
```python
def _determine_risk(self, segment: SegmentWeatherData) -> tuple[str, str]:
    # 45 Zeilen eigene Risk-Logik
    agg = segment.aggregated
    if agg.thunder_level_max == ThunderLevel.HIGH:
        return ("high", "⚠️ Thunder")
    # ... weitere Checks ...
    return ("none", "✓ OK")
```

**Nachher:**
```python
def _determine_risk(self, segment: SegmentWeatherData) -> tuple[str, str]:
    engine = RiskEngine()
    assessment = engine.assess_segment(segment)
    if not assessment.risks:
        return ("none", "✓ OK")
    top = assessment.risks[0]  # Sortiert: HIGH zuerst
    label = _risk_label(top)   # Emoji + Text aus RiskType
    return (top.level.value, label)
```

`_risk_label()` Mapping (Hilfsfunktion):
```python
_RISK_LABELS = {
    RiskType.THUNDERSTORM: "Thunder",
    RiskType.WIND: "Storm" if level == HIGH else "High Wind",
    RiskType.RAIN: "Heavy Rain",
    RiskType.WIND_CHILL: "Extreme Cold",
    RiskType.POOR_VISIBILITY: "Low Visibility",
}
```

### 5) Formatter-Migration: sms_trip.py

**Vorher:**
```python
def _detect_risk(self, seg_data: SegmentWeatherData) -> tuple[Optional[str], Optional[str]]:
    agg = seg_data.aggregated
    if agg.thunder_level_max == ThunderLevel.HIGH:
        return ("Gewitter", time)
    if agg.wind_max_kmh > 70:          # hardcoded!
        return ("Sturm", time)
    # ...
```

**Nachher:**
```python
def _detect_risk(self, seg_data: SegmentWeatherData) -> tuple[Optional[str], Optional[str]]:
    engine = RiskEngine()
    assessment = engine.assess_segment(seg_data)
    if not assessment.risks:
        return (None, None)
    top = assessment.risks[0]
    label = _SMS_RISK_LABELS.get(top.type, None)
    time = seg_data.segment.start_time.strftime("%Hh")
    return (label, time)
```

### 6) MetricCatalog-Aenderung

Einzige Aenderung: POP bekommt `risk_thresholds`:

```python
MetricDefinition(
    id="rain_probability",
    ...
    risk_thresholds={"medium": 80},  # NEU — bisher hardcoded in trip_report.py
)
```

### 7) Was NICHT in F8 gehoert

| Thema | Warum nicht | Wo stattdessen |
|-------|------------|----------------|
| `_compute_highlights()` | Braucht Timeseries-Scan fuer Zeitfenster → Rendering-Concern | Bleibt im Formatter |
| Wind-Adjektive (compact_summary) | Textgenerierung, nicht Risk-Assessment | Phase 2 oder F7 |
| Terrain-Exposure (F7) | Eigenes Feature, braucht GPX-Analyse | F7 nach F8 |
| Alert-Dispatch | Bereits sauber in AlertProcessor | Bleibt wie ist |
| Change-Detection | Eigene Concern (Delta, nicht Absolut) | Bleibt wie ist |

## Expected Behavior

### Beispiel 1: Sturmboeen + Gewitter

```python
segment.aggregated = SegmentWeatherSummary(
    thunder_level_max=ThunderLevel.HIGH,
    wind_max_kmh=55,
    gust_max_kmh=82,
    precip_sum_mm=8.0,
)

assessment = RiskEngine().assess_segment(segment)
# → RiskAssessment(risks=[
#     Risk(type=THUNDERSTORM, level=HIGH),
#     Risk(type=WIND, level=HIGH, gust_kmh=82),
# ])
```

### Beispiel 2: Maessiger Wind, kein Risiko

```python
segment.aggregated = SegmentWeatherSummary(
    thunder_level_max=ThunderLevel.NONE,
    wind_max_kmh=35,
    gust_max_kmh=42,
    precip_sum_mm=2.0,
)

assessment = RiskEngine().assess_segment(segment)
# → RiskAssessment(risks=[])
```

### Beispiel 3: Invertierte Schwelle (Sichtweite)

```python
segment.aggregated = SegmentWeatherSummary(
    visibility_min_m=50,
)

assessment = RiskEngine().assess_segment(segment)
# → RiskAssessment(risks=[
#     Risk(type=POOR_VISIBILITY, level=HIGH, visibility_m=50),
# ])
```

### Verhalten

- **Kein Risiko:** `RiskAssessment(risks=[])` — leere Liste
- **Mehrere Risiken:** Sortiert nach Level (HIGH zuerst), dann nach Regelreihenfolge
- **Deduplizierung:** Pro RiskType nur hoechstes Level
- **None-Werte:** Metrik mit `None`-Wert wird uebersprungen (kein Risiko)
- **Leere risk_thresholds:** Metrik ohne Schwellen wird uebersprungen
- **Keine Seiteneffekte:** Reine Funktion, kein State, kein I/O

## Affected Files

### Phase 1 (Core Engine + Hauptconsumer)

| File | Change | LoC |
|------|--------|-----|
| `src/services/risk_engine.py` | NEU — RiskEngine Service | ~80 |
| `src/formatters/trip_report.py` | `_determine_risk()` delegiert an Engine | ~-20 netto |
| `src/formatters/sms_trip.py` | `_detect_risk()` delegiert an Engine | ~-15 netto |
| `src/app/metric_catalog.py` | POP: risk_thresholds hinzufuegen | ~1 |
| `tests/integration/test_risk_engine.py` | NEU — Tests mit echten Wetterdaten | ~80 |
| **Gesamt Phase 1** | **4 Prod + 1 Test** | **~125 LoC netto** |

### Phase 2 (Spaeter, optional, nicht Teil dieser Spec)

- `src/formatters/compact_summary.py` — Wind-Adjektive aus Catalog
- F7 Integration — TerrainExposure als Kontext fuer RiskEngine

## Test Plan

### Integration Tests (test_risk_engine.py)

- [ ] `test_no_risks_calm_weather`: Ruhiges Wetter → leere RiskAssessment
- [ ] `test_thunder_high`: ThunderLevel.HIGH → Risk(THUNDERSTORM, HIGH)
- [ ] `test_thunder_medium`: ThunderLevel.MED → Risk(THUNDERSTORM, MODERATE)
- [ ] `test_wind_high`: wind_max > 70 → Risk(WIND, HIGH)
- [ ] `test_wind_moderate`: wind_max > 50 → Risk(WIND, MODERATE)
- [ ] `test_gust_overrides_wind`: gust HIGH + wind MODERATE → einmal WIND HIGH
- [ ] `test_precipitation_moderate`: precip > 20mm → Risk(RAIN, MODERATE)
- [ ] `test_visibility_inverted`: visibility < 100m → Risk(POOR_VISIBILITY, HIGH)
- [ ] `test_wind_chill_inverted`: wind_chill < -20 → Risk(WIND_CHILL, HIGH)
- [ ] `test_multiple_risks_sorted`: Thunder + Wind → sortiert HIGH zuerst
- [ ] `test_deduplication`: Wind MODERATE + Gust HIGH → nur WIND HIGH
- [ ] `test_none_values_skipped`: None-Metriken → kein Risiko
- [ ] `test_formatter_uses_engine`: trip_report._determine_risk() nutzt RiskEngine

### E2E Tests

- [ ] Trip-Report senden (Test-Trip) — Risk-Segment korrekt markiert
- [ ] SMS-Alert senden — Risk-Label korrekt

## Acceptance Criteria

- [ ] `RiskEngine.assess_segment()` gibt korrekte RiskAssessment zurueck
- [ ] Alle Schwellen kommen aus MetricCatalog (kein Hardcoding)
- [ ] POP risk_threshold im Catalog definiert (nicht mehr hardcoded 80%)
- [ ] `trip_report._determine_risk()` delegiert an RiskEngine
- [ ] `sms_trip._detect_risk()` delegiert an RiskEngine
- [ ] Deduplizierung: pro RiskType nur hoechstes Level
- [ ] Invertierte Schwellen (high_lt) funktionieren korrekt
- [ ] Bestehende Reports zeigen exakt gleiches Risiko-Verhalten (Backward Compatible)
- [ ] Risk/RiskAssessment DTOs aus models.py werden instantiiert

## Known Limitations

1. **Nur Aggregat-Level:** Engine bewertet SegmentWeatherSummary, nicht Timeseries-Stundenwerte. Zeitliche Details (Gewitter ab 14:00) bleiben im Formatter.
2. **Keine Terrain-Awareness:** Wind-Schwellen sind absolut, nicht exposure-adjusted. Das ist F7.
3. **Regelbasiert:** Kein ML, keine eigene meteorologische Modellierung.
4. **Phase 1 nur:** compact_summary Wind-Adjektive bleiben vorerst hardcoded.

## Erweiterungspunkte (Zukunft)

- **F7:** `assess_segment(segment, terrain_exposure=...)` — Engine senkt Wind-Schwellen bei Exposition
- **F10:** `RiskType.AVALANCHE` — Lawinen-Integration (SLF/EAWS Daten)
- **Per-Trip-Schwellen:** Ueber `UnifiedWeatherDisplayConfig` konfigurierbar

## Changelog

- 2025-12-27: v1.0 — Placeholder-Spec (planned module)
- 2026-02-18: v2.0 — Vollstaendige Spec: RiskEngine Service, Formatter-Migration, MetricCatalog-Integration
