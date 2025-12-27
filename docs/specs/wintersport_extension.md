---
entity_id: wintersport_extension
type: feature
created: 2025-12-27
updated: 2025-12-27
status: draft
version: "1.0"
tags: [wintersport, snow, avalanche, skiing]
---

# Wintersport-Erweiterung

## Approval

- [x] Approved (2025-12-27)

## Purpose

Erweiterung von Gregor Zwanzig um wintersport-relevante Daten: Schneelage, Lawinenwarnung, und alpine Wetterbedingungen. Zielgruppe: Skitouren, Freerider, Winterwanderer.

---

## 1. Datenquellen-Analyse

### 1.1 GeoSphere Austria (Primaer fuer Oesterreich)

| Endpunkt | Typ | Daten | Relevanz |
|----------|-----|-------|----------|
| `nwp-v1-1h-2500m` | Forecast | Neuschnee, Schneefallgrenze, Wind, Temp | HIGH |
| `snowgrid_cl-v2-1d-1km` | Historical | Aktuelle Schneehoehe, SWE | HIGH |
| `nowcast-v1-15min-1km` | Nowcast | Niederschlagstyp (Schnee/Regen) | MEDIUM |
| `tawes-v1-10min` | Realtime | Stationsmessungen | LOW |

**API-Basis:** `https://dataset.api.hub.geosphere.at/v1/`

**Verfuegbare Schnee-Parameter:**
- `snow_acc` - Neuschnee akkumuliert (kg/m²)
- `snowlmt` - Schneefallgrenze (m)
- `snow_depth` - Gesamtschneehoehe (m)
- `swe_tot` - Schneewasseraequivalent (kg/m²)
- `pt` - Niederschlagstyp (rain/snow/mix)

**Abdeckung:** Oesterreich, 1-2.5km Aufloesung


### 1.2 SLF Schweiz (Primaer fuer Schweiz)

| Endpunkt | Typ | Daten | Relevanz |
|----------|-----|-------|----------|
| `/public/api/imis/measurements` | Realtime | Schnee, Wind, Temp | HIGH |
| `/public/api/imis/daily-snow` | Daily | Tagesschnee | HIGH |
| `aws.slf.ch/api/bulletin/caaml` | Bulletin | Lawinenlagebericht | HIGH |
| `aws.slf.ch/api/warningregion` | GeoJSON | Warnregionen | MEDIUM |

**API-Basis:** `https://measurement-api.slf.ch/`

**Verfuegbare Schnee-Parameter:**
- `HS` - Schneehoehe gesamt (cm)
- `HN_1D` - Neuschnee 24h (cm)
- `TSS_30MIN_MEAN` - Schneeoberflaechen-Temperatur
- `TS0/25/50/100` - Schneetemperaturen in Tiefe

**Abdeckung:** Schweiz, ~180 IMIS-Stationen, Lizenz: CC BY 4.0


### 1.3 Euregio Lawinen.report (Tirol/Suedtirol/Trentino)

| Endpunkt | Format | Daten |
|----------|--------|-------|
| `static.avalanche.report/bulletins/latest/{lang}.json` | JSON | Lawinenlagebericht |
| CAAML v5/v6 | XML | Standardisierter Lawinenbericht |

**Verfuegbare Daten:**
- Gefahrenstufe (1-5) pro Region und Hoehenzone
- Lawinenprobleme (Neuschnee, Triebschnee, Altschnee, Nassschnee, Gleitschnee)
- Gueltigkeit (validTime)
- Gefahrenbeschreibung

**Abdeckung:** Tirol (AT), Suedtirol (IT), Trentino (IT)

---

## 2. Datenmodell-Erweiterung

### 2.1 Neue Felder in NormalizedTimeseries.data[]

```
# Schnee-Felder (alle optional, null wenn nicht verfuegbar)
snow_depth_cm: float        # Gesamtschneehoehe [cm]
snow_new_24h_cm: float      # Neuschnee letzte 24h [cm]
snow_new_acc_cm: float      # Neuschnee akkumuliert seit Forecast-Start [cm]
snowfall_limit_m: int       # Schneefallgrenze [m]
swe_kgm2: float             # Schneewasseraequivalent [kg/m²]
precip_type: enum           # {RAIN, SNOW, MIXED, FREEZING_RAIN, null}

# Zusaetzliche Wintersport-relevante Felder
freezing_level_m: int       # Nullgradgrenze [m]
wind_chill_c: float         # Gefuehlte Temperatur [°C]
visibility_m: int           # Sichtweite [m] (optional)
```

### 2.2 Neues separates DTO: AvalancheReport

```json
{
  "meta": {
    "provider": "SLF" | "EUREGIO" | "ZAMG",
    "region_id": "AT-07",
    "region_name": "Tirol",
    "valid_from": "2025-12-27T17:00Z",
    "valid_to": "2025-12-28T17:00Z",
    "published": "2025-12-27T16:00Z"
  },
  "danger": {
    "level": 3,                          # 1-5 (European Avalanche Danger Scale)
    "level_text": "erheblich",           # gering/maessig/erheblich/gross/sehr gross
    "elevation_above_m": 2000,           # Hoehengrenze (optional)
    "level_below": 2,                    # Stufe unterhalb (optional)
    "trend": "increasing" | "steady" | "decreasing"
  },
  "problems": [
    {
      "type": "new_snow" | "wind_slab" | "persistent_weak" | "wet_snow" | "gliding_snow",
      "aspects": ["N", "NE", "E", "NW"],
      "elevation_from_m": 2000,
      "elevation_to_m": 3000
    }
  ],
  "snowpack": {
    "structure": "unfavorable" | "moderate" | "favorable",
    "description": "..."
  }
}
```

### 2.3 Erweiterung Provider-Enum

```
Provider: MOSMIX | MET | NOWCASTMIX | GEOSPHERE | SLF | EUREGIO
```

---

## 3. Neue Provider-Module

### 3.1 GeoSphere Provider

**File:** `src/providers/geosphere.py`

**Endpunkte:**
1. NWP Forecast: `/grid/forecast/nwp-v1-1h-2500m`
2. Snowgrid: `/grid/historical/snowgrid_cl-v2-1d-1km`
3. Nowcast: `/grid/forecast/nowcast-v1-15min-1km`

**Mapping:**
```
snow_acc (kg/m²) -> snow_new_acc_cm (÷10, approx)
snowlmt (m) -> snowfall_limit_m
t2m (°C) -> t2m_c
u10m/v10m (m/s) -> wind10m_kmh (sqrt(u²+v²) × 3.6)
ugust/vgust (m/s) -> gust_kmh (sqrt(u²+v²) × 3.6)
pt -> precip_type
snow_depth (m) -> snow_depth_cm (× 100)
```

### 3.2 SLF Provider

**File:** `src/providers/slf.py`

**Endpunkte:**
1. Messdaten: `measurement-api.slf.ch/public/api/imis/measurements`
2. Tagesschnee: `measurement-api.slf.ch/public/api/imis/daily-snow`
3. Lawinenbulletin: `aws.slf.ch/api/bulletin/caaml`

**Mapping:**
```
HS (cm) -> snow_depth_cm
HN_1D (cm) -> snow_new_24h_cm
VW_30MIN_MEAN (m/s) -> wind10m_kmh (× 3.6)
VW_30MIN_MAX (m/s) -> gust_kmh (× 3.6)
TA_30MIN_MEAN (°C) -> t2m_c
```

### 3.3 Euregio Avalanche Provider

**File:** `src/providers/euregio_avalanche.py`

**Endpunkt:** `static.avalanche.report/bulletins/latest/{lang}.json`

**Output:** AvalancheReport DTO

---

## 4. Risk Engine Erweiterung

### 4.1 Neue Risiko-Typen

```json
{
  "risks": [
    {"type": "avalanche", "level": "high", "danger_level": 4, "problems": ["wind_slab"]},
    {"type": "snowfall", "level": "moderate", "amount_cm": 30, "from": "18:00Z"},
    {"type": "freezing_rain", "level": "high", "from": "06:00Z"},
    {"type": "poor_visibility", "level": "moderate", "visibility_m": 50},
    {"type": "wind_chill", "level": "high", "feels_like_c": -25}
  ]
}
```

### 4.2 Schwellenwerte (konfigurierbar)

| Risiko | LOW | MODERATE | HIGH |
|--------|-----|----------|------|
| Lawinenstufe | 1-2 | 3 | 4-5 |
| Neuschnee 24h | <10cm | 10-30cm | >30cm |
| Gefuehlte Temp | >-10°C | -10 bis -20°C | <-20°C |
| Sichtweite | >200m | 50-200m | <50m |
| Boeenspitzen | <50km/h | 50-80km/h | >80km/h |

---

## 5. SMS-Token Erweiterung

Neue Tokens fuer Wintersport:

```
SN{cm}         # Schneehoehe gesamt
SN24{cm}       # Neuschnee 24h
SFL{m}         # Schneefallgrenze
AV{1-5}        # Lawinenstufe
WC{temp}       # Wind Chill
```

**Beispiel:**
```
Arlberg: D-5 N-12 SN180 SN24+25 SFL1800 AV3 W45@12 G78@14 WC-22
```

---

## 6. Implementierungs-Reihenfolge

1. **Phase 1: Datenmodell**
   - api_contract.md erweitern
   - JSON-Schema aktualisieren
   - DTOs in Python definieren

2. **Phase 2: GeoSphere Provider**
   - NWP Forecast Integration
   - Snowgrid Integration
   - Unit Tests

3. **Phase 3: SLF Provider**
   - IMIS Stationsdaten
   - Lawinenbulletin (CAAML)
   - Unit Tests

4. **Phase 4: Euregio Provider**
   - JSON-Bulletin Parser
   - Region-Mapping
   - Unit Tests

5. **Phase 5: Risk Engine**
   - Neue Risiko-Typen
   - Schwellenwert-Konfiguration
   - Unit Tests

6. **Phase 6: Formatter**
   - SMS-Tokens
   - E-Mail-Template Erweiterung

---

## 7. Abhaengigkeiten

| Abhaengigkeit | Zweck |
|---------------|-------|
| httpx | Async HTTP Client |
| pydantic | DTO Validierung |
| lxml | CAAML XML Parsing (SLF) |

---

## 8. Entscheidungen (PO-Feedback)

| Frage | Entscheidung |
|-------|--------------|
| Priorisierung | **Oesterreich zuerst** |
| Lawinen-DTO | **Separates Objekt** (nicht in NormalizedTimeseries) |
| Stationsauswahl | **Interpolation** (nicht naechste Station) |
| Caching | TBD - Schneegrid 1x taeglich |

---

## 9. Modell-Uebersicht GeoSphere

| Modell | Resource ID | Aufloesung | Forecast | Update | Beschreibung |
|--------|-------------|------------|----------|--------|--------------|
| **AROME** | `nwp-v1-1h-2500m` | 2.5 km | 60h | 3h | Hochaufloesendes Alpenmodell |
| **NOWCAST** | `nowcast-v1-15min-1km` | 1 km | 3h | 15min | Kurzfrist mit Niederschlagstyp |
| **ENSEMBLE** | `ensemble-v1-1h-2500m` | 2.5 km | 60h | - | 16-Member Probabilistik |
| **INCA** | `inca-v1-1h-1km` | 1 km | - | 1h | Analyse (historisch) |
| **SNOWGRID** | `snowgrid_cl-v2-1d-1km` | 1 km | - | 1d | Schneehoehe/SWE |

**Empfehlung:** AROME (NWP) als Primaer-Forecast, NOWCAST fuer Kurzfrist-Updates, SNOWGRID fuer aktuelle Schneehoehe.

---

## Changelog

- 2025-12-27: Initial spec created after analysis
- 2025-12-27: PO-Feedback eingearbeitet (AT first, separates Lawinen-DTO, Interpolation)
