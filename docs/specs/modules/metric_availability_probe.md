---
entity_id: metric_availability_probe
type: module
created: 2026-02-16
updated: 2026-02-16
status: draft
version: "1.0"
tags: [provider, weather, open-meteo, probe, availability, cache]
---

# Metric Availability Probe (WEATHER-05a)

## Approval

- [ ] Approved

## Purpose

Periodischer API-Test pro OpenMeteo-Modell, der prueft welche Metriken tatsaechlich
Daten liefern vs. `null`. Ergebnis wird als JSON gecacht (7-Tage TTL) und dient als
Entscheidungsgrundlage fuer den spaeter implementierten Model-Metric-Fallback (WEATHER-05b).

**Kernregel:** Wir wissen nicht zuverlaessig welche Metriken jedes Modell liefert (OpenMeteo-Doku
ist unvollstaendig). Deshalb proben wir es empirisch.

## Erweiterung von

- `docs/specs/modules/provider_openmeteo.md` v1.0 (Regional Model Selection)

## Source

- **File:** `src/providers/openmeteo.py`
- **Identifier:** `OpenMeteoProvider.probe_model_availability()`, `OpenMeteoProvider._load_availability_cache()`, `OpenMeteoProvider._save_availability_cache()`
- **CLI:** `src/app/cli.py` — neues `--probe-models` Argument

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| OpenMeteoProvider | class | Host-Klasse, nutzt REGIONAL_MODELS und _request() |
| REGIONAL_MODELS | const | Liste aller 5 Modelle mit Bounds + Endpoints |
| ForecastDataPoint | dto | Definiert alle moeglichen Metrik-Felder |
| cli.py | module | Einstiegspunkt fuer manuelles --probe-models |
| data/cache/ | directory | Speicherort fuer model_availability.json |

## Implementation Details

### 1. Probe-Methode in OpenMeteoProvider (~40 LOC)

```python
def probe_model_availability(self) -> dict:
    """
    Probt alle REGIONAL_MODELS und speichert Ergebnis im Cache.

    Algorithmus:
    1. Fuer jedes Modell in REGIONAL_MODELS:
       a. Referenz-Koordinate = Mitte der Bounding-Box
       b. API-Call mit ALLEN hourly-Parametern, Zeitraum = morgen (1 Tag)
       c. Response parsen: welche hourly-Arrays haben mind. 1 non-null Wert?
       d. Ergebnis: {"available": [...], "unavailable": [...]}
    2. Ergebnis als JSON speichern
    3. Return: gesamtes Probe-Result dict
    """
```

Referenz-Koordinate pro Modell:

| Modell | Lat | Lon | Begruendung |
|--------|-----|-----|-------------|
| meteofrance_arome | 45.5 | 1.0 | Mitte Frankreich |
| icon_d2 | 49.5 | 10.0 | Mitte Deutschland |
| metno_nordic | 62.5 | 19.0 | Mitte Skandinavien |
| icon_eu | 50.0 | 10.5 | Mitte Europa |
| ecmwf_ifs04 | 0.0 | 0.0 | Aequator/Nullmeridian |

Parameter-Liste fuer Probe (identisch mit fetch_forecast):

```python
PROBE_PARAMS = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m",
    "dewpoint_2m", "pressure_msl", "cloud_cover", "cloud_cover_low",
    "cloud_cover_mid", "cloud_cover_high", "wind_speed_10m",
    "wind_direction_10m", "wind_gusts_10m", "precipitation",
    "weather_code", "visibility", "precipitation_probability",
    "cape", "freezing_level_height", "uv_index",
]
```

Auswertung pro Parameter:

```python
available = []
unavailable = []
for param in PROBE_PARAMS:
    values = hourly.get(param, [])
    has_data = any(v is not None for v in values)
    if has_data:
        available.append(param)
    else:
        unavailable.append(param)
```

### 2. Cache I/O (~25 LOC)

**Cache-Datei:** `data/cache/model_availability.json`

```python
AVAILABILITY_CACHE_PATH = Path("data/cache/model_availability.json")
AVAILABILITY_CACHE_TTL_DAYS = 7

def _load_availability_cache(self) -> Optional[dict]:
    """Laedt Cache, gibt None zurueck wenn abgelaufen oder nicht vorhanden."""
    if not AVAILABILITY_CACHE_PATH.exists():
        return None
    data = json.loads(AVAILABILITY_CACHE_PATH.read_text())
    probe_date = date.fromisoformat(data["probe_date"])
    if (date.today() - probe_date).days >= AVAILABILITY_CACHE_TTL_DAYS:
        return None  # Abgelaufen
    return data

def _save_availability_cache(self, result: dict) -> None:
    """Speichert Probe-Ergebnis als JSON."""
    AVAILABILITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    AVAILABILITY_CACHE_PATH.write_text(json.dumps(result, indent=2))
```

**Cache-Schema:**

```json
{
  "probe_date": "2026-02-16",
  "models": {
    "meteofrance_arome": {
      "available": ["temperature_2m", "wind_speed_10m", "cape", "..."],
      "unavailable": ["precipitation_probability", "..."]
    },
    "icon_d2": { "available": [...], "unavailable": [...] },
    "metno_nordic": { "available": [...], "unavailable": [...] },
    "icon_eu": { "available": [...], "unavailable": [...] },
    "ecmwf_ifs04": { "available": [...], "unavailable": [...] }
  }
}
```

### 3. CLI-Kommando (~15 LOC)

```python
# In create_parser():
parser.add_argument(
    "--probe-models",
    action="store_true",
    help="Probe all OpenMeteo models for metric availability and update cache",
)

# In main():
if args.probe_models:
    from providers.openmeteo import OpenMeteoProvider
    provider = OpenMeteoProvider()
    result = provider.probe_model_availability()
    for model_id, info in result["models"].items():
        print(f"  {model_id}: {len(info['available'])} available, {len(info['unavailable'])} unavailable")
    sys.exit(0)
```

## Expected Behavior

### Szenario 1: Erste Probe (kein Cache vorhanden)

- **Input:** `python -m src.app.cli --probe-models`
- **Output:**
  ```
  Probing 5 OpenMeteo models...
    meteofrance_arome: 17 available, 2 unavailable
    icon_d2: 16 available, 3 unavailable
    metno_nordic: 15 available, 4 unavailable
    icon_eu: 18 available, 1 unavailable
    ecmwf_ifs04: 19 available, 0 unavailable
  Cache saved: data/cache/model_availability.json
  ```
- **Side Effects:** 5 API-Calls an OpenMeteo, Cache-Datei geschrieben

### Szenario 2: Cache vorhanden und gueltig

- **Input:** `provider._load_availability_cache()`
- **Output:** Dict mit Probe-Ergebnis
- **Side Effects:** Keine API-Calls

### Szenario 3: Cache abgelaufen (>7 Tage)

- **Input:** `provider._load_availability_cache()`
- **Output:** `None`
- **Side Effects:** Keine (Caller entscheidet ob neu geprobt wird)

### Szenario 4: API-Fehler bei einzelnem Modell

- **Input:** Probe-Call fuer icon_d2 schlaegt fehl (503)
- **Output:** Modell wird uebersprungen, Rest wird geprobt
- **Side Effects:** Warning geloggt, Cache enthaelt nur erfolgreiche Modelle

## Testplan

| # | Test | Typ | Assertion |
|---|------|-----|-----------|
| 1 | probe_model_availability gibt dict mit 5 Modellen zurueck | Integration | `len(result["models"]) == 5` |
| 2 | Jedes Modell hat available + unavailable Listen | Integration | Keys vorhanden, Listen nicht leer |
| 3 | Cache wird geschrieben nach Probe | Integration | `AVAILABILITY_CACHE_PATH.exists()` |
| 4 | Cache wird geladen wenn gueltig | Unit | `_load_availability_cache()` gibt dict zurueck |
| 5 | Cache gibt None bei abgelaufenem TTL | Unit | `_load_availability_cache()` gibt None zurueck |
| 6 | Cache gibt None wenn nicht vorhanden | Unit | `_load_availability_cache()` gibt None zurueck |
| 7 | API-Fehler bei einzelnem Modell crasht nicht | Integration | Ergebnis hat <5 Modelle, kein Exception |
| 8 | ECMWF hat alle 19 Parameter verfuegbar | Integration | `len(ecmwf["available"]) == 19` |

## Known Limitations

- Probe testet nur Referenz-Koordinate pro Modell, nicht alle Regionen
  (Metrik-Verfuegbarkeit kann regional variieren — unwahrscheinlich aber moeglich)
- Cache ist global, nicht pro User oder Trip
- Probe macht 5 API-Calls gleichzeitig (koennte Rate-Limits triggern bei Free Tier)
  → v2.0: Sequentiell mit kurzer Pause
- Keine automatische Probe bei Server-Start in Phase A (kommt mit Phase B)

## Changelog

- 2026-02-16: Initial spec created (WEATHER-05a, Phase A)
