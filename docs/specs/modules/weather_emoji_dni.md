---
entity_id: weather_emoji_dni
type: bugfix
created: 2026-02-18
updated: 2026-02-18
status: draft
version: "1.0"
tags: [weather, emoji, dni, display]
---

# Weather Emoji: DNI-basierte Ableitung

## Approval

- [ ] Approved

## Purpose

Fuegt eine **neue parallele Metrik "Sonnenschein (DNI)"** hinzu, die als zusaetzliche Spalte
neben der bestehenden Cloud%-Spalte angezeigt wird. Nutzt Direct Normal Irradiance (DNI)
als primaere Quelle fuer die Emoji-Ableitung. Loest das Cirrus-Problem: duenne hohe Wolken
zaehlen bei Cloud% als "bedeckt" obwohl volle Sonneneinstrahlung durchkommt (Beispiel GR221
Mallorca: Cloud=☁️ bei 800 W/m² DNI, Sun=☀️). Mond-Emoji nachts statt Sonnen-Emoji.

Die bestehenden Cloud%-Emojis bleiben UNVERAENDERT. DNI ist eine ZUSAETZLICHE Metrik,
konfigurierbar ueber den MetricCatalog und die Wetter-Metriken-UI.

## Source

- **File:** `src/services/weather_metrics.py`
- **Identifier:** `get_weather_emoji()` (neue Modul-Level-Funktion)

### Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `src/app/models.py` | Neue Felder: `wmo_code`, `is_day`, `dni_wm2` in ForecastDataPoint; `dominant_wmo_code`, `dni_avg_wm2` in SegmentWeatherSummary |
| `src/providers/openmeteo.py` | `direct_normal_irradiance`, `is_day` zur hourly-Liste; `wmo_code` speichern statt verwerfen |
| `src/services/weather_metrics.py` | Zentrale `get_weather_emoji()` + Hilfsfunktionen; Aggregation in `compute_basis_metrics()` und `aggregate_stage()` |
| `src/app/metric_catalog.py` | Neue MetricDefinition `sunshine` (dp_field=`dni_wm2`, col_key=`sunshine`, default_enabled=True) |
| `src/output/renderers/trip_report.py` | `_fmt_val()` Handler fuer key `"sunshine"` → `get_weather_emoji()`; hidden fields `_is_day`, `_dni_wm2`, `_wmo_code` im row dict |

### Bestehende Funktionen (werden konsolidiert)

| Funktion | Datei:Line | Schwellen | Wird ersetzt durch |
|----------|------------|-----------|-------------------|
| `get_weather_symbol()` | weather_metrics.py:174 | 20/50/80% | Legacy-Wrapper um `get_weather_emoji()` |
| `_cloud_to_emoji()` | trip_report_scheduler.py:656 | 10/30/70/90% | Direkter Aufruf `get_weather_emoji()` |
| `_format_clouds()` | compact_summary.py:127 | 20/40/60/80% | Direkter Aufruf `get_weather_emoji()` |
| `_fmt_val()` cloud-case | trip_report.py:555 | 10/30/70/90% | Direkter Aufruf `get_weather_emoji()` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ForecastDataPoint` | model | Traegt neue Felder `wmo_code`, `is_day`, `dni_wm2` |
| `SegmentWeatherSummary` | model | Traegt neue Felder `dominant_wmo_code`, `dni_avg_wm2` |
| `openmeteo` provider | provider | Liefert `direct_normal_irradiance`, `is_day`, `weather_code` |
| `WeatherMetricsService` | service | `compute_basis_metrics()` und `aggregate_stage()` berechnen aggregierte Werte |

## Implementation Details

### Entscheidungsbaum (Prioritaet)

```
1. WMO Niederschlagscode vorhanden (>= 45)?
   └── JA: Niederschlags-Emoji (🌧️/❄️/⛈️/🌫️)
   └── NEIN: weiter zu 2.

2. is_day == 0 (Nacht)?
   └── JA: Nacht-Emoji basierend auf Cloud% (🌙/🌙☁️/☁️)
   └── NEIN: weiter zu 3.

3. is_day == 1 UND dni_wm2 verfuegbar?
   └── JA: DNI-basiertes Tag-Emoji (☀️/🌤️/⛅/🌥️/☁️)
   └── NEIN: weiter zu 4.

4. Fallback: Cloud%-basiertes Emoji (☀️/🌤️/⛅/🌥️/☁️)
   (greift wenn is_day unbekannt ODER dni_wm2 fehlt)
```

### Neue Felder in Models

```python
# ForecastDataPoint (src/app/models.py) — 3 neue Optional-Felder:
wmo_code: Optional[int] = None        # WMO weather code (0-99)
is_day: Optional[int] = None           # 1=Tag, 0=Nacht (von OpenMeteo)
dni_wm2: Optional[float] = None        # Direct Normal Irradiance (W/m²)

# SegmentWeatherSummary (src/app/models.py) — 2 neue Optional-Felder:
dominant_wmo_code: Optional[int] = None  # Schwerster WMO-Code im Segment
dni_avg_wm2: Optional[float] = None      # Durchschnittliche DNI (nur Tagesstunden)
```

### OpenMeteo Provider

Neue Parameter in der hourly-Liste (`src/providers/openmeteo.py`):
```python
"direct_normal_irradiance",
"is_day",
```

`weather_code` wird bereits gefetcht — neu: im ForecastDataPoint speichern statt verwerfen:
```python
wmo_code=get_int("weather_code", i),              # NEU: speichern
is_day=get_int("is_day", i),                       # NEU
dni_wm2=get_val("direct_normal_irradiance", i),    # NEU
```

Falls AROME HD `direct_normal_irradiance` oder `is_day` nicht liefert, bleiben die Felder
`None` — das bestehende Metric-Availability-Probe-System (WEATHER-05a) erkennt dies automatisch.
`get_weather_emoji()` faellt dann auf Cloud%-Fallback zurueck (Stufe 4 im Entscheidungsbaum).

### Zentrale Emoji-Funktion

Alle Konstanten und Funktionen auf Modul-Level in `src/services/weather_metrics.py`:

```python
# --- Schwellenwerte ---

# DNI (W/m²) — basierend auf WMO Sunshine-Definition (DNI > 120)
_DNI_FULL_SUN = 600
_DNI_MOSTLY_SUNNY = 300
_DNI_PARTLY_SUNNY = 120

# Cloud% (einheitlich fuer alle Fallback-Stellen)
_CLOUD_CLEAR = 20
_CLOUD_MOSTLY_CLEAR = 40
_CLOUD_PARTLY_CLOUDY = 70
_CLOUD_MOSTLY_CLOUDY = 90

# --- WMO-Code Mappings ---

# Niederschlags- und Sondercodes → Emoji (Vorrang vor DNI/Cloud)
_WMO_PRECIP_EMOJI: dict[int, str] = {
    45: "🌫️", 48: "🌫️",                    # Fog
    51: "🌦️", 53: "🌦️", 55: "🌧️",        # Drizzle
    56: "🌧️", 57: "🌧️",                    # Freezing drizzle
    61: "🌧️", 63: "🌧️", 65: "🌧️",        # Rain
    66: "🌨️", 67: "🌨️",                    # Freezing rain
    71: "❄️", 73: "❄️", 75: "❄️", 77: "❄️", # Snow
    80: "🌦️", 81: "🌧️", 82: "🌧️",        # Rain showers
    85: "🌨️", 86: "🌨️",                    # Snow showers
    95: "⛈️", 96: "⛈️", 99: "⛈️",          # Thunderstorm
}

# Severity-Ranking fuer Aggregation (hoechster Wert gewinnt, bei Gleichstand: max() nimmt erstes)
_WMO_SEVERITY: dict[int, int] = {
    0: 0, 1: 1, 2: 2, 3: 3,
    45: 10, 48: 11,
    51: 20, 53: 21, 55: 22, 56: 23, 57: 24,
    61: 30, 63: 31, 65: 32, 66: 33, 67: 34,
    71: 35, 73: 36, 75: 37, 77: 38,
    80: 40, 81: 41, 82: 42, 85: 43, 86: 44,
    95: 50, 96: 51, 99: 52,
}

# --- Funktionen ---

def get_weather_emoji(
    *,
    is_day: Optional[int] = None,
    dni_wm2: Optional[float] = None,
    wmo_code: Optional[int] = None,
    cloud_pct: Optional[int] = None,
) -> str:
    """Zentrale Wetter-Emoji-Funktion. Single Source of Truth."""
    # 1. WMO Niederschlag/Fog/Gewitter hat IMMER Vorrang
    if wmo_code is not None and wmo_code in _WMO_PRECIP_EMOJI:
        return _WMO_PRECIP_EMOJI[wmo_code]
    # 2. Nacht
    if is_day is not None and is_day == 0:
        return _night_emoji(cloud_pct)
    # 3. Tag mit DNI
    if is_day == 1 and dni_wm2 is not None:
        return _dni_emoji(dni_wm2)
    # 4. Fallback (is_day unbekannt oder DNI fehlt)
    return _cloud_pct_emoji(cloud_pct)


def _night_emoji(cloud_pct: Optional[int]) -> str:
    """Nacht-Emoji basierend auf Bewoelkung."""
    if cloud_pct is None or cloud_pct < 40:
        return "🌙"
    if cloud_pct < 80:
        return "🌙☁️"
    return "☁️"


def _dni_emoji(dni_wm2: float) -> str:
    """Tag-Emoji basierend auf Direct Normal Irradiance."""
    if dni_wm2 >= _DNI_FULL_SUN:        return "☀️"
    if dni_wm2 >= _DNI_MOSTLY_SUNNY:     return "🌤️"
    if dni_wm2 >= _DNI_PARTLY_SUNNY:     return "⛅"
    if dni_wm2 > 0:                      return "🌥️"
    return "☁️"


def _cloud_pct_emoji(cloud_pct: Optional[int]) -> str:
    """Fallback-Emoji aus Cloud% (einheitliche Schwellen)."""
    if cloud_pct is None:                        return "?"
    if cloud_pct < _CLOUD_CLEAR:                 return "☀️"
    if cloud_pct < _CLOUD_MOSTLY_CLEAR:          return "🌤️"
    if cloud_pct < _CLOUD_PARTLY_CLOUDY:         return "⛅"
    if cloud_pct < _CLOUD_MOSTLY_CLOUDY:         return "🌥️"
    return "☁️"
```

### Aggregation

In `WeatherMetricsService.compute_basis_metrics()`:
```python
# Dominant WMO: schwerster Code im Segment
codes = [dp.wmo_code for dp in data if dp.wmo_code is not None]
summary.dominant_wmo_code = max(codes, key=lambda c: _WMO_SEVERITY.get(c, 0)) if codes else None

# DNI Tagesdurchschnitt: nur is_day==1 Stunden
day_dni = [dp.dni_wm2 for dp in data if dp.is_day == 1 and dp.dni_wm2 is not None]
summary.dni_avg_wm2 = (sum(day_dni) / len(day_dni)) if day_dni else None
```

In `aggregate_stage()`:
```python
# dominant_wmo_code: schwerster ueber alle Segmente
wmo_codes = [s.dominant_wmo_code for s in summaries if s.dominant_wmo_code is not None]
result.dominant_wmo_code = max(wmo_codes, key=lambda c: _WMO_SEVERITY.get(c, 0)) if wmo_codes else None

# dni_avg_wm2: gewichteter Durchschnitt ueber Segmente
dni_vals = [s.dni_avg_wm2 for s in summaries if s.dni_avg_wm2 is not None]
result.dni_avg_wm2 = (sum(dni_vals) / len(dni_vals)) if dni_vals else None
```

### Legacy Wrapper

`get_weather_symbol()` bleibt fuer Abwaertskompatibilitaet, delegiert an neue Funktion:
```python
@staticmethod
def get_weather_symbol(cloud_total_pct, precip_mm, temp_c, **kwargs) -> str:
    """Legacy wrapper — delegiert an get_weather_emoji()."""
    return get_weather_emoji(
        is_day=kwargs.get('is_day'),
        dni_wm2=kwargs.get('dni_wm2'),
        wmo_code=kwargs.get('wmo_code'),
        cloud_pct=cloud_total_pct,
    )
```

### Caller-Updates

Jeder bisherige Caller wird auf `get_weather_emoji()` umgestellt:

**`format_hourly_cell()` in weather_metrics.py:**
```python
symbol = get_weather_emoji(
    is_day=getattr(dp, 'is_day', None),
    dni_wm2=getattr(dp, 'dni_wm2', None),
    wmo_code=getattr(dp, 'wmo_code', None),
    cloud_pct=dp.cloud_total_pct,
)
```

**`_build_stage_trend()` in trip_report_scheduler.py:**
```python
dominant_wmo = compute_dominant_wmo(all_day_points)  # Hilfsfunktion
dni_avg = compute_dni_day_avg(all_day_points)          # Hilfsfunktion
cloud_emoji = get_weather_emoji(
    is_day=1,
    dni_wm2=dni_avg,
    wmo_code=dominant_wmo,
    cloud_pct=stage_summary.cloud_avg_pct,
)
```

**`_format_clouds()` in compact_summary.py:**
```python
emoji = get_weather_emoji(
    wmo_code=summary.dominant_wmo_code,
    dni_wm2=summary.dni_avg_wm2,
    is_day=1,
    cloud_pct=summary.cloud_avg_pct,
)
```

**`_fmt_val()` cloud-case in trip_report.py:**
```python
if key == "cloud" and use_friendly:
    return get_weather_emoji(cloud_pct=int(val))
# cloud_low/mid/high bleiben bei _cloud_pct_emoji()
```

### Emoji-Uebersicht

| Emoji | Bedeutung | Quelle |
|-------|-----------|--------|
| ☀️ | Volle Sonne | DNI >= 600 oder Cloud < 20% |
| 🌤️ | Leicht bewoelkt | DNI >= 300 oder Cloud < 40% |
| ⛅ | Teilweise sonnig | DNI >= 120 oder Cloud < 70% |
| 🌥️ | Stark bewoelkt | DNI > 0 oder Cloud < 90% |
| ☁️ | Bedeckt | DNI = 0 oder Cloud >= 90% |
| 🌙 | Klare Nacht | is_day=0, Cloud < 40% |
| 🌙☁️ | Wolkige Nacht | is_day=0, Cloud 40-80% |
| 🌫️ | Nebel | WMO 45, 48 |
| 🌦️ | Leichter Regen/Schauer | WMO 51, 53, 80 |
| 🌧️ | Regen | WMO 55-57, 61-65, 81-82 |
| 🌨️ | Schneeregen | WMO 66-67, 85-86 |
| ❄️ | Schneefall | WMO 71-77 |
| ⛈️ | Gewitter | WMO 95, 96, 99 |

### Legend-Strings (E-Mail/UI)

```
Tag:   ☀️ sonnig | 🌤️ leicht bewoelkt | ⛅ wolkig | 🌥️ stark bewoelkt | ☁️ bedeckt
Nacht: 🌙 klar | 🌙☁️ wolkig | ☁️ bedeckt
Wetter: 🌫️ Nebel | 🌦️ Schauer | 🌧️ Regen | 🌨️ Schneeregen | ❄️ Schnee | ⛈️ Gewitter
```

## Expected Behavior

- **Input:** ForecastDataPoint mit is_day, dni_wm2, wmo_code, cloud_total_pct
- **Output:** Einzelnes Emoji-String
- **Aggregiert:** dominant_wmo + dni_day_avg + cloud_avg_pct → gleiches Emoji-Schema

### Vergleich Vorher/Nachher (GR221 Mallorca, 20. Feb Cirrus-Szenario)

| Zeit | Cloud% | High% | DNI W/m² | is_day | VORHER | NACHHER |
|------|--------|-------|----------|--------|--------|---------|
| 12:00 | 97% | 97% | 811 | 1 | ☁️ | ☀️ |
| 13:00 | 100% | 100% | 796 | 1 | ☁️ | ☀️ |
| 14:00 | 95% | 95% | 724 | 1 | ☁️ | ☀️ |
| 15:00 | 69% | 69% | 643 | 1 | 🌥️ | ☀️ |
| 16:00 | 44% | 44% | 547 | 1 | ⛅ | 🌤️ |
| 21:00 | 0% | 0% | 0 | 0 | ☀️ | 🌙 |

### Fallback-Szenarien

| Szenario | is_day | DNI | WMO | Cloud% | Ergebnis |
|----------|--------|-----|-----|--------|----------|
| Regen tagsüber | 1 | 50 | 61 | 100% | 🌧️ (WMO Vorrang) |
| Regen nachts | 0 | 0 | 63 | 100% | 🌧️ (WMO Vorrang) |
| Nebel | 1 | 10 | 45 | 100% | 🌫️ (WMO Vorrang) |
| Sonne, kein Provider-DNI | 1 | None | 0 | 15% | ☀️ (Cloud%-Fallback) |
| Nacht klar | 0 | 0 | 0 | 5% | 🌙 (Nacht) |
| Nacht bewoelkt | 0 | 0 | 3 | 85% | ☁️ (Nacht bedeckt) |
| is_day unbekannt | None | None | None | 60% | ⛅ (Cloud%-Fallback) |

## Known Limitations

1. **DNI nur von OpenMeteo** — andere Provider (Geosphere, MET) liefern kein DNI.
   `get_weather_emoji()` faellt automatisch auf Cloud%-Fallback zurueck (Stufe 4).
2. **AROME HD** hat weniger Variablen — falls `direct_normal_irradiance` oder `is_day`
   nicht verfuegbar, bleiben Felder `None`. Bestehender Metric-Availability-Probe (WEATHER-05a)
   erkennt dies. Cloud%-Fallback greift automatisch.
3. **Aggregiertes DNI** (Etappen-Durchschnitt) kann bei wechselhaftem Wetter eine mittlere
   Klasse zeigen. Der `dominant_wmo_code` ergaenzt dies fuer Niederschlags-Erkennung.
4. **WMO Severity Tie-Breaking:** Bei gleicher Severity greift Pythons `max()` — deterministisch,
   aber nicht garantiert der "richtigere" Code. In der Praxis irrelevant, da alle Codes im
   `_WMO_SEVERITY`-Dict einzigartige Werte haben.

## Changelog

- 2026-02-18: Initial spec created
- 2026-02-18: v1.0 — Fog-Codes (45,48) hinzugefuegt, Entscheidungsbaum praezisiert,
  Fallback-Szenarien dokumentiert, Aggregation in compute_basis_metrics/aggregate_stage spezifiziert
