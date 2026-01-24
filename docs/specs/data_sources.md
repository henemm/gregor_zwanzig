---
entity_id: data_sources
type: reference
created: 2025-12-31
updated: 2025-12-31
status: approved
version: "1.0"
tags: [provider, api, data-governance]
owner: henning
---

# Datenquellen-Spezifikation

## Governance

**WICHTIG: Diese Spec darf NUR durch den Product Owner (Henning) geaendert werden.**

Claude darf KEINE neuen Datenquellen oder Parameter hinzufuegen ohne explizite Genehmigung.
Jede Erweiterung muss zuerst in dieser Spec dokumentiert und genehmigt werden.

---

## Datenquellen-Zuordnung

Diese Tabelle definiert, welche Information aus welcher Quelle bezogen wird.

| Information | Primaere Quelle | Fallback | Region | Bemerkung |
|-------------|-----------------|----------|--------|-----------|
| Temperatur | GeoSphere (t2m) | - | Alpen/AT | |
| Temperatur | Open-Meteo (temperature_2m) | ECMWF | Europa/Global | Regional Models: AROME, ICON-D2, MetNo |
| Wind | GeoSphere (u10m/v10m) | - | Alpen/AT | Berechnet aus U/V-Komponenten |
| Wind | Open-Meteo (wind_speed_10m) | ECMWF | Europa/Global | Regional Models |
| Boeen | GeoSphere (ugust/vgust) | - | Alpen/AT | Berechnet aus U/V-Komponenten |
| Boeen | Open-Meteo (wind_gusts_10m) | ECMWF | Europa/Global | Regional Models |
| Windrichtung | GeoSphere (u10m/v10m) | - | Alpen/AT | Berechnet aus U/V-Komponenten |
| Windrichtung | Open-Meteo (wind_direction_10m) | ECMWF | Europa/Global | Regional Models |
| Niederschlag | GeoSphere (rr_acc) | - | Alpen/AT | Akkumuliert, Differenz = stuendlich |
| Niederschlag | Open-Meteo (precipitation) | ECMWF | Europa/Global | Regional Models |
| Neuschnee | GeoSphere (snow_acc) | - | Alpen/AT | Akkumuliert |
| Schneefallgrenze | GeoSphere (snowlmt) | - | Alpen/AT | |
| Bewoelkung gesamt | GeoSphere (tcc) | - | Alpen/AT | |
| Bewoelkung gesamt | Open-Meteo (cloud_cover) | ECMWF | Europa/Global | Regional Models |
| Wolkenschichten | Open-Meteo (cloud_cover_low/mid/high) | - | Global | Fuer Hochlagen-Logik |
| Luftfeuchtigkeit | GeoSphere (rh2m) | - | Alpen/AT | |
| Luftfeuchtigkeit | Open-Meteo (relative_humidity_2m) | ECMWF | Europa/Global | Regional Models |
| Luftdruck | GeoSphere (sp) | - | Alpen/AT | |
| Luftdruck | Open-Meteo (pressure_msl) | ECMWF | Europa/Global | Regional Models |
| Taupunkt | Open-Meteo (dewpoint_2m) | ECMWF | Europa/Global | Regional Models |
| Wettersymbol | Open-Meteo (weather_code) | - | Europa/Global | WMO-Codes, Thunder-Erkennung |
| Schneehoehe | Bergfex | GeoSphere SNOWGRID | Alpen/AT | Bergfex bevorzugt (aktueller) |
| SWE | GeoSphere SNOWGRID | - | Alpen/AT | Schneewasseraequivalent |
| Sonnenstunden | *Berechnet* | - | - | effective_cloud < 30% |
| Gefuehlte Temp. | *Berechnet* | - | - | Wind Chill Formel |

**Regionen-Codes:**
- `Alpen/AT` = Oesterreich, Alpenraum (GeoSphere bevorzugt)
- `Europa/Global` = Europa (1-7km Regional Models) + Weltweit (40km ECMWF)
  - **Mallorca/Korsika/Westalpen:** AROME (1.3km)
  - **DE/AT/CH/Benelux:** ICON-D2 (2km)
  - **Skandinavien/Baltikum:** MetNo Nordic (1km)
  - **Rest Europa:** ICON-EU (7km)
  - **Global Fallback:** ECMWF IFS (40km) - ZWINGEND verfuegbar
- `Global` = Weltweit verfuegbar

---

## Genehmigte Datenquellen

### 1. GeoSphere Austria (Primaer)

**API:** https://dataset.api.hub.geosphere.at/v1

**Genehmigte Endpunkte:**

| Endpunkt | Zweck | Status |
|----------|-------|--------|
| `/timeseries/forecast/nwp-v1-1h-2500m` | AROME Wettervorhersage | approved |
| `/timeseries/historical/snowgrid_cl-v2-1d-1km` | Schneehoehe/SWE | approved |
| `/timeseries/forecast/nowcast-v1-15min-1km` | Kurzfrist-Prognose | approved |

**Genehmigte Parameter (AROME NWP):**

| Parameter | Feld in ForecastDataPoint | Status |
|-----------|---------------------------|--------|
| t2m | t2m_c | approved |
| u10m, v10m | wind10m_kmh (berechnet) | approved |
| ugust, vgust | gust_kmh (berechnet) | approved |
| rr_acc | precip_1h_mm | approved |
| tcc | cloud_total_pct | approved |
| sp | pressure_msl_hpa | approved |
| r2m | humidity_pct | approved |
| snow_acc | snow_new_acc_cm | approved |

**Genehmigte Parameter (SNOWGRID):**

| Parameter | Feld in ForecastDataPoint | Status |
|-----------|---------------------------|--------|
| snow_depth | snow_depth_cm | approved |
| swe | swe_kgm2 | approved |

---

### 2. Open-Meteo (Regional Models Provider)

**API:** https://api.open-meteo.com/v1/forecast

**Status:** Genehmigt als Primaer-Provider fuer Europa + Global Fallback (2026-01-24)

**ACHTUNG:** Open-Meteo darf NUR fuer explizit genehmigte Parameter verwendet werden!

**Genehmigte Parameter (Cloud Layers):**

| Parameter | Feld in ForecastDataPoint | Genehmigt am | Status |
|-----------|---------------------------|--------------|--------|
| cloud_cover_low | cloud_low_pct | 2025-12-28 | approved |
| cloud_cover_mid | cloud_mid_pct | 2025-12-28 | approved |
| cloud_cover_high | cloud_high_pct | 2025-12-28 | approved |

**Genehmigte Parameter (Wetter-Daten - Regional Models):**

| Parameter | Feld in ForecastDataPoint | Genehmigt am | Status |
|-----------|---------------------------|--------------|--------|
| temperature_2m | t2m_c | 2026-01-24 | approved |
| relative_humidity_2m | humidity_pct | 2026-01-24 | approved |
| dewpoint_2m | dewpoint_c | 2026-01-24 | approved |
| pressure_msl | pressure_msl_hpa | 2026-01-24 | approved |
| cloud_cover | cloud_total_pct | 2026-01-24 | approved |
| wind_speed_10m | wind10m_kmh | 2026-01-24 | approved |
| wind_direction_10m | wind_direction_deg | 2026-01-24 | approved |
| wind_gusts_10m | gust_kmh | 2026-01-24 | approved |
| precipitation | precip_1h_mm | 2026-01-24 | approved |
| weather_code | symbol | 2026-01-24 | approved |
| models | - | 2026-01-24 | approved |

**Genehmigte Modelle:**
- `meteofrance_arome` - AROME France & Balearen (1.3km)
- `icon_d2` - ICON-D2 Deutschland/Alpen (2km)
- `metno_nordic` - MetNo Nordic Skandinavien (1km)
- `icon_eu` - ICON-EU Europa (7km)
- `ecmwf_ifs04` - ECMWF IFS Global (40km) - ZWINGENDER Fallback

**Approval-Bedingung:** Fuer ALLE Regionen MUSS ein Modell ausgewaehlt sein (ECMWF global garantiert Abdeckung).

**NICHT genehmigte Parameter (Beispiele):**

| Parameter | Status | Bemerkung |
|-----------|--------|-----------|
| sunshine_duration | REJECTED | Abgelehnt am 2025-12-31 |
| direct_radiation | NOT APPROVED | - |
| snowfall | NOT APPROVED | Verwende GeoSphere SNOWGRID |
| snow_depth | NOT APPROVED | Verwende GeoSphere/Bergfex |

---

### 3. Bergfex (Scraping - eingeschraenkt)

**URL-Pattern:** https://www.bergfex.at/{resort}/schneebericht/

**Genehmigte Daten:**

| Daten | Status | Bemerkung |
|-------|--------|-----------|
| Schneehoehe (Berg/Tal) | approved | Fallback wenn SNOWGRID fehlt |
| Lifte offen | approved | Informativ |
| Pisten km | approved | Informativ |

---

## Nicht genehmigte Quellen

Die folgenden Quellen sind NICHT genehmigt:

- WeatherAPI.com
- OpenWeatherMap
- Tomorrow.io
- Meteomatics
- Andere nicht explizit gelistete APIs

---

## Aenderungsprotokoll

| Datum | Version | Aenderung | Genehmigt durch |
|-------|---------|-----------|-----------------|
| 2025-12-31 | 1.0 | Initial: GeoSphere, Open-Meteo (cloud layers), Bergfex | Henning |
| 2026-01-24 | 1.1 | Open-Meteo erweitert: Wetter-Parameter + Regional Models (AROME, ICON-D2, MetNo, ECMWF). Bedingung: ZWINGEND Modellauswahl fuer alle Regionen. | Henning |

---

## Prozess fuer neue Datenquellen/Parameter

1. Claude erstellt Antrag in dieser Spec (als "PENDING")
2. Henning prueft und genehmigt/ablehnt
3. Erst nach Genehmigung darf implementiert werden

### Offene Antraege

Keine offenen Antraege.

### Genehmigte Antraege

#### Antrag #1: Open-Meteo Wetter-Parameter (Regional Models)

**Datum:** 2026-01-24
**Status:** ✅ APPROVED (2026-01-24, Henning)
**Antragsteller:** Claude (via User Request)
**Spec:** `docs/specs/modules/provider_openmeteo.md`

**Zusammenfassung:**
Nutzung von Open-Meteo Forecast API mit dynamischer Modellauswahl (`models=` Parameter) fuer Europa-weite Hochaufloesung:
- AROME France (1.3km) fuer Mallorca, Korsika, Westalpen
- ICON-D2 (2km) fuer Deutschland, Oesterreich, Schweiz
- MetNo Nordic (1km) fuer Skandinavien
- ECMWF IFS (40km) als globaler Fallback

**Genehmigte Parameter:**

| Parameter | Feld | Zweck | Einheit |
|-----------|------|-------|---------|
| temperature_2m | t2m_c | Temperatur 2m | °C |
| relative_humidity_2m | humidity_pct | Luftfeuchtigkeit | % |
| dewpoint_2m | dewpoint_c | Taupunkt | °C |
| pressure_msl | pressure_msl_hpa | Luftdruck MSL | hPa |
| cloud_cover | cloud_total_pct | Gesamtbewoelkung | % |
| wind_speed_10m | wind10m_kmh | Windgeschwindigkeit 10m | km/h |
| wind_direction_10m | wind_direction_deg | Windrichtung | 0-360° |
| wind_gusts_10m | gust_kmh | Windboeen | km/h |
| precipitation | precip_1h_mm | Niederschlag stuendlich | mm |
| weather_code | symbol | Wettersymbol (WMO-Code) | - |
| models | - | Modellauswahl | (siehe Spec) |

**Approval-Bedingung:**
- **ZWINGEND:** Fuer ALLE Regionen MUSS ein Modell ausgewaehlt sein
- ECMWF global fallback garantiert vollstaendige Abdeckung

**Begruendung:**
- Einzige API mit Zugriff auf franzoesisches AROME fuer Mallorca/Korsika
- Bessere Qualitaet als GeoSphere fuer nicht-oesterreichische Regionen
- Zielgruppe Weitwanderer (GR20, Skandinavien) profitiert von 1-2km Aufloesung

**Risiko:** Niedrig (etablierte API, Free Tier ausreichend, kein Lock-in)

**Genehmigt durch:** Henning (2026-01-24)

### Abgelehnte Antraege

| Parameter | Quelle | Zweck | Status | Datum |
|-----------|--------|-------|--------|-------|
| sunshine_duration | Open-Meteo | Sonnenstunden-Berechnung | REJECTED | 2025-12-31 |
