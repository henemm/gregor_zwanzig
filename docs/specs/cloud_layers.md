---
entity_id: cloud_layers
type: feature
created: 2025-12-28
updated: 2025-12-28
status: approved
version: "1.0"
tags: [provider, clouds, open-meteo, wintersport]
---

# Cloud Layer Heights - Wolkenhoehen nach Schicht

## Approval

- [x] Approved (2025-12-28)

## Purpose

Anzeige von Wolkenhoehen nach Schichten (Low/Mid/High) fuer die Skigebiet-Entscheidung. Use Case: "Lohnt es sich zum Gletscher zu fahren, wenn die Wolken nur bis 2.500m reichen?"

Ventusky zeigt diese Daten bereits - wir wollen sie in Gregor Zwanzig integrieren.

## Source

- **File:** `src/providers/openmeteo.py` (neu)
- **Identifier:** `OpenMeteoProvider` class

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.models.ForecastDataPoint` | dataclass | Erweitern um cloud_low/mid/high |
| `providers.base` | module | WeatherProvider Protocol |
| `httpx` | external | HTTP Client |

## Datenquelle: Open-Meteo (GRATIS)

**API:** https://open-meteo.com/en/docs

**Parameter:**
- `cloud_cover_low` - Wolken bis 3 km Hoehe (%)
- `cloud_cover_mid` - Wolken 3-8 km Hoehe (%)
- `cloud_cover_high` - Wolken ab 8 km Hoehe (%)

**Beispiel-Request:**
```
https://api.open-meteo.com/v1/forecast?
  latitude=47.08&longitude=11.12&
  hourly=cloud_cover_low,cloud_cover_mid,cloud_cover_high&
  timezone=Europe/Vienna
```

## Implementation Details

### 1. ForecastDataPoint erweitern

```python
@dataclass
class ForecastDataPoint:
    # ... existing fields ...

    # Cloud layers (new)
    cloud_low_pct: Optional[int] = None   # 0-100%, bis 3km
    cloud_mid_pct: Optional[int] = None   # 0-100%, 3-8km
    cloud_high_pct: Optional[int] = None  # 0-100%, ab 8km
```

### 2. Neuer Provider (optional)

```python
class OpenMeteoProvider:
    """Open-Meteo API fuer Cloud Layer Daten."""

    def fetch_cloud_layers(
        self, lat: float, lon: float, hours: int = 48
    ) -> List[CloudLayerData]:
        """Fetch low/mid/high cloud cover."""
```

### 3. GeoSphere-Integration (Alternative)

Statt neuem Provider: Open-Meteo Cloud-Daten in `fetch_combined()` mergen.

```python
def fetch_combined(...) -> NormalizedTimeseries:
    # Existing: AROME + SNOWGRID
    ts = self.fetch_nwp_forecast(...)

    # NEW: Enrich with Open-Meteo cloud layers
    cloud_data = self._fetch_openmeteo_clouds(lat, lon)
    for dp in ts.data:
        # Match by timestamp and add cloud layers
        ...
```

## UI-Integration

### Compare-Page
Neue Spalte in Vergleichstabelle:
```
| Location | Score | Wolken (L/M/H) | ... |
|----------|-------|----------------|-----|
| Stubai   |  82   | 80/20/0 %      | ... |
```

### Interpretation fuer User
```
Wolken: 80% Low (bis 3km) / 20% Mid / 0% High
→ Gletscher auf 3.200m vermutlich ueber den Wolken!
```

### E-Mail-Report
```
WOLKENSCHICHTEN:
  Low  (bis 3km):  80%  -> bewoelkt unter 3.000m
  Mid  (3-8km):    20%  -> teilweise bewoelkt
  High (ab 8km):    0%  -> klar

  Empfehlung: Gletscher (3.200m) sollte sonnig sein!
```

## Scoring-Integration

Neuer Score-Faktor basierend auf Location-Hoehe:

```python
def calculate_cloud_score(
    elevation_m: int,
    cloud_low: int,
    cloud_mid: int,
    cloud_high: int,
) -> int:
    """Score basierend auf Wolken relativ zur Hoehe."""
    if elevation_m > 3000:
        # Gletscher: Low clouds egal, nur mid/high zaehlt
        return 100 - (cloud_mid * 0.5 + cloud_high * 0.5)
    elif elevation_m > 2000:
        # Hochalpin: Low clouds teilweise relevant
        return 100 - (cloud_low * 0.3 + cloud_mid * 0.5 + cloud_high * 0.2)
    else:
        # Tal: Alle Wolken relevant
        return 100 - cloud_low
```

## Alternative Datenquellen (recherchiert)

| Provider | Cloud Layer | Cloud Base | Kosten |
|----------|-------------|------------|--------|
| **Open-Meteo** | ✅ L/M/H % | ❌ | **Gratis** |
| Meteomatics | ✅ L/M/H % | ✅ m | Premium (teuer) |
| Tomorrow.io | ✅ | ✅ m | Freemium |
| GeoSphere AROME | ❌ nur tcc | ❌ | Gratis |

**Entscheidung:** Open-Meteo (gratis, ausreichend fuer Use Case)

## Expected Behavior

- **Input:** Location mit Koordinaten und Hoehe
- **Output:** Wolkendecke pro Schicht (Low/Mid/High) in %
- **Side effects:** Zusaetzlicher API-Call zu Open-Meteo

## Known Limitations

- Open-Meteo liefert keine exakte Cloud Base Height in Metern
- Schicht-Grenzen sind fix (3km, 8km) - nicht dynamisch
- Genauigkeit abhaengig vom Wettermodell

## Implementation Scope

**Ticket 1 (MVP):** ~100 LoC
- ForecastDataPoint erweitern
- Open-Meteo Fetch in GeoSphere integrieren
- Anzeige in Compare-Tabelle

**Ticket 2 (Follow-up):**
- Scoring-Integration
- E-Mail-Report Erweiterung
- Eigener OpenMeteoProvider (falls mehr Parameter gewuenscht)

## Changelog

- 2025-12-28: Initial spec created after API research
