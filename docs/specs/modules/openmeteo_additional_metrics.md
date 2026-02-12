---
entity_id: openmeteo_additional_metrics
type: module
created: 2026-02-12
updated: 2026-02-12
status: draft
version: "2.0"
tags: [openmeteo, provider, metrics, catalog, aggregation, formatter]
---

# OpenMeteo: Zusaetzliche Metriken (Vollstaendige Pipeline-Integration)

## Approval

- [ ] Approved

## Purpose

4 OpenMeteo-Metriken (`visibility_m`, `pop_pct`, `cape_jkg`, `freezing_level_m`) vollstaendig in die Pipeline integrieren. Phase 1 (v1.0) hat Provider-Fetch und MetricCatalog-Registrierung abgedeckt. Phase 2 (v2.0) schliesst die fehlende Aggregation, Change Detection und Formatter-Formatierung ab.

**Ist-Zustand nach v1.0:**
- Provider fetcht alle 4 Metriken ✓
- MetricCatalog hat alle 4 registriert ✓
- Weather Config Dialog zeigt alle 4 ✓
- Stuendliche Email-Tabellen zeigen Rohwerte ✓
- `visibility_m` und `freezing_level_m` sind bereits voll aggregiert ✓

**Problem (v2.0):**
- `pop_pct` und `cape_jkg` werden NICHT aggregiert → fehlen in `SegmentWeatherSummary`
- Change Detection hat keine Thresholds fuer `pop_max_pct` und `cape_max_jkg`
- `_fmt_val()` im Formatter hat keine spezifische Formatierung fuer die 4 neuen col_keys → Rohwerte statt formatierte Anzeige

## Source

- **Files:**
  - `src/app/models.py` (MODIFY) - 2 neue Felder in SegmentWeatherSummary
  - `src/services/weather_metrics.py` (MODIFY) - 2 Compute-Methoden + Validation
  - `src/services/weather_change_detection.py` (MODIFY) - 2 Threshold-Eintraege
  - `src/formatters/trip_report.py` (MODIFY) - 4 Formatter-Cases in _fmt_val

## Dependencies

### Upstream Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ForecastDataPoint` | DTO | Felder `visibility_m`, `pop_pct`, `cape_jkg`, `freezing_level_m` existieren bereits |
| `MetricCatalog` | Registry | Definiert Aggregationen (pop=max, cape=max) |
| `SegmentWeatherSummary` | DTO | Ziel fuer aggregierte Werte |
| `WeatherMetricsService` | Service | Berechnet Aggregationen |

### Downstream Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherChangeDetectionService` | Service | Erkennt Aenderungen fuer pop/cape |
| `TripReportFormatter._fmt_val()` | Formatter | Formatiert Zellwerte fuer Email |
| Weather Config Dialog | WebUI | Keine Aenderung noetig (kataloggesteuert) |

## Implementation Details

### Phase 1: Provider + Catalog (v1.0 - ERLEDIGT)

Provider-Fetch und MetricCatalog-Registrierung sind bereits implementiert:
- `src/providers/openmeteo.py`: 4 Parameter in HOURLY_PARAMS + Parsing
- `src/app/metric_catalog.py`: 4 MetricDefinition-Eintraege

### Phase 2: Pipeline-Integration (v2.0 - DIESES TICKET)

#### 2.1 SegmentWeatherSummary: 2 neue Felder

**Datei:** `src/app/models.py`, nach Zeile 311 (`freezing_level_m`)

```python
# Additional metrics (OpenMeteo)
pop_max_pct: Optional[int] = None
cape_max_jkg: Optional[float] = None
```

**Begruendung:** `visibility_min_m` und `freezing_level_m` existieren bereits in SegmentWeatherSummary. Nur `pop_pct` und `cape_jkg` fehlen.

#### 2.2 WeatherMetricsService: 2 Compute-Methoden

**Datei:** `src/services/weather_metrics.py`

**Neue Methoden (nach `_compute_freezing_level`, Zeile 834):**

```python
def _compute_pop(self, timeseries: NormalizedTimeseries) -> Optional[int]:
    """Compute precipitation probability MAX. Returns pop_max_pct."""
    pop_vals = [dp.pop_pct for dp in timeseries.data if dp.pop_pct is not None]
    return round(max(pop_vals)) if pop_vals else None

def _compute_cape(self, timeseries: NormalizedTimeseries) -> Optional[float]:
    """Compute CAPE MAX. Returns cape_max_jkg."""
    cape_vals = [dp.cape_jkg for dp in timeseries.data if dp.cape_jkg is not None]
    return max(cape_vals) if cape_vals else None
```

**`compute_extended_metrics()` erweitern (Zeile 761):**

```python
# Bestehend:
freezing_level = self._compute_freezing_level(timeseries)
# NEU:
pop_max = self._compute_pop(timeseries)
cape_max = self._compute_cape(timeseries)
```

**SegmentWeatherSummary-Instanziierung erweitern (nach Zeile 781):**

```python
freezing_level_m=freezing_level,
# NEU:
pop_max_pct=pop_max,
cape_max_jkg=cape_max,
```

**Aggregation-Config erweitern (nach Zeile 789):**

```python
"freezing_level_m": "avg",
# NEU:
"pop_max_pct": "max",
"cape_max_jkg": "max",
```

**Plausibilitaets-Validation erweitern (`_validate_extended_plausibility`):**

```python
if summary.pop_max_pct is not None:
    if not (0 <= summary.pop_max_pct <= 100):
        self._debug.add(
            f"WARNING: pop_max_pct={summary.pop_max_pct}% out of plausible range (0..100)"
        )

if summary.cape_max_jkg is not None:
    if not (0 <= summary.cape_max_jkg <= 5000):
        self._debug.add(
            f"WARNING: cape_max_jkg={summary.cape_max_jkg} J/kg out of plausible range (0..5000)"
        )
```

**Docstring aktualisieren:** "5 extended" → "7 extended" (+ pop, cape)

#### 2.3 Change Detection: 2 Threshold-Eintraege

**Datei:** `src/services/weather_change_detection.py`, `__init__` Methode

**`_thresholds`-Dict erweitern (nach Zeile 71):**

```python
"freezing_level_m": 200,
# NEU:
"pop_max_pct": 20,       # ±20% Aenderung in Regenwahrscheinlichkeit
"cape_max_jkg": 500.0,   # ±500 J/kg Aenderung in Gewitterenergie
```

Keine weiteren Code-Aenderungen noetig - `detect_changes()` iteriert bereits ueber alle numerischen Felder von `SegmentWeatherSummary` via `dataclasses.fields()`.

#### 2.4 Formatter: _fmt_val fuer 4 neue col_keys

**Datei:** `src/formatters/trip_report.py`, Methode `_fmt_val()` (Zeile 252-285)

**Einfuegen vor Zeile 285 (`return str(val)`):**

```python
if key == "pop":
    s = f"{val:.0f}"
    if html and val is not None and val >= 80:
        return f'<span style="background:#e3f2fd;color:#1565c0;padding:2px 4px;border-radius:3px">{s}</span>'
    return s
if key == "cape":
    s = f"{val:.0f}"
    if html and val is not None and val >= 1000:
        return f'<span style="background:#fff9c4;color:#f57f17;padding:2px 4px;border-radius:3px">{s}</span>'
    return s
if key == "visibility":
    if val >= 10000:
        s = f"{val / 1000:.0f}k"
    elif val >= 1000:
        s = f"{val / 1000:.1f}k"
    else:
        s = f"{val:.0f}"
    if html and val is not None and val < 500:
        return f'<span style="background:#fff3e0;color:#e65100;padding:2px 4px;border-radius:3px">{s}</span>'
    return s
if key == "freeze_lvl":
    return f"{val:.0f}"
```

**Formatierungsregeln:**

| col_key | Format | Einheit | HTML-Highlighting |
|---------|--------|---------|-------------------|
| `pop` | Integer | % (implizit, Spaltenheader "Pop") | >= 80%: blau |
| `cape` | Integer | J/kg (implizit) | >= 1000: gelb/orange (Gewitterwarnung) |
| `visibility` | `>=10km: "10k"`, `>=1km: "1.5k"`, `<1km: "500"` | m/km | < 500m: orange (Sichtwarnung) |
| `freeze_lvl` | Integer | m (implizit) | kein Highlighting |

## Expected Behavior

### Pop-Aggregation in SegmentWeatherSummary
- **Given:** Timeseries mit pop_pct-Werten [20, 45, 80, 60]
- **When:** compute_extended_metrics() aufgerufen
- **Then:** pop_max_pct = 80

### CAPE-Aggregation in SegmentWeatherSummary
- **Given:** Timeseries mit cape_jkg-Werten [100.0, 500.0, 1200.0, 800.0]
- **When:** compute_extended_metrics() aufgerufen
- **Then:** cape_max_jkg = 1200.0

### Formatter: Pop-Formatierung
- **Given:** col_key="pop", val=75
- **When:** _fmt_val("pop", 75, html=False)
- **Then:** "75"
- **When:** _fmt_val("pop", 85, html=True)
- **Then:** `<span style="background:#e3f2fd;...">85</span>`

### Formatter: CAPE-Formatierung
- **Given:** col_key="cape", val=1200
- **When:** _fmt_val("cape", 1200, html=True)
- **Then:** `<span style="background:#fff9c4;...">1200</span>`

### Formatter: Visibility-Formatierung
- **Given:** col_key="visibility", val=48000
- **When:** _fmt_val("visibility", 48000)
- **Then:** "48k"
- **Given:** col_key="visibility", val=1500
- **Then:** "1.5k"
- **Given:** col_key="visibility", val=300, html=True
- **Then:** `<span style="background:#fff3e0;...">300</span>`

### Formatter: Freezing-Level-Formatierung
- **Given:** col_key="freeze_lvl", val=2800
- **When:** _fmt_val("freeze_lvl", 2800)
- **Then:** "2800"

### Change Detection: Pop-Aenderung
- **Given:** Alter Forecast pop_max_pct=30, neuer Forecast pop_max_pct=80
- **When:** detect_changes() aufgerufen
- **Then:** WeatherChange(metric="pop_max_pct", delta=50) erkannt (Threshold=20)

### Change Detection: CAPE-Aenderung
- **Given:** Alter Forecast cape_max_jkg=200, neuer Forecast cape_max_jkg=1500
- **When:** detect_changes() aufgerufen
- **Then:** WeatherChange(metric="cape_max_jkg", delta=1300) erkannt (Threshold=500)

### Plausibilitaets-Validation
- **Given:** pop_max_pct=150 (unmoeglich)
- **When:** _validate_extended_plausibility() aufgerufen
- **Then:** WARNING in DebugBuffer (kein Fehler, nur Warnung)

### Backward-Kompatibilitaet
- **Given:** Bestehender Trip ohne pop/cape in display_config
- **When:** Report generiert
- **Then:** Identischer Output wie vorher (pop/cape default_enabled=False)

## Files to Change

| # | File | Action | LoC |
|---|------|--------|-----|
| 1 | `src/app/models.py` | MODIFY - 2 Felder | ~5 |
| 2 | `src/services/weather_metrics.py` | MODIFY - 2 Methoden + Integration + Validation | ~55 |
| 3 | `src/services/weather_change_detection.py` | MODIFY - 2 Thresholds | ~4 |
| 4 | `src/formatters/trip_report.py` | MODIFY - 4 _fmt_val Cases | ~30 |

**Total:** ~94 LoC, 4 Dateien

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pop/CAPE Werte sind None (Provider liefert nicht) | LOW | Optional-Types, None-Checks ueberall |
| CAPE-Werte extrem hoch (>5000) | LOW | Plausibilitaets-Warnung im DebugBuffer |
| Pop-Verwirrung (0-1 vs 0-100) | MEDIUM | OpenMeteo liefert 0-100, Tests validieren |
| Visibility km/m Anzeige verwirrend | LOW | >=1000m als "Xk" formatieren, Spaltenheader "Vis" |

## Standards Compliance

- Spec-first workflow (dieses Dokument)
- Keine Mocked Tests (echte API-Daten in Tests)
- Safari kompatibel (keine UI-Aenderungen)
- Backward compatible (pop/cape default_enabled=False)

## Changelog

- 2026-02-12: v1.0 - Initial spec (Provider + Catalog)
- 2026-02-12: v2.0 - Pipeline-Integration: Aggregation, Change Detection, Formatter
