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
| Wind | GeoSphere (u10m/v10m) | - | Alpen/AT | Berechnet aus U/V-Komponenten |
| Boeen | GeoSphere (ugust/vgust) | - | Alpen/AT | Berechnet aus U/V-Komponenten |
| Windrichtung | GeoSphere (u10m/v10m) | - | Alpen/AT | Berechnet aus U/V-Komponenten |
| Niederschlag | GeoSphere (rr_acc) | - | Alpen/AT | Akkumuliert, Differenz = stuendlich |
| Neuschnee | GeoSphere (snow_acc) | - | Alpen/AT | Akkumuliert |
| Schneefallgrenze | GeoSphere (snowlmt) | - | Alpen/AT | |
| Bewoelkung gesamt | GeoSphere (tcc) | - | Alpen/AT | |
| Wolkenschichten | Open-Meteo | - | Global | Fuer Hochlagen-Logik (low/mid/high) |
| Luftfeuchtigkeit | GeoSphere (rh2m) | - | Alpen/AT | |
| Luftdruck | GeoSphere (sp) | - | Alpen/AT | |
| Schneehoehe | Bergfex | GeoSphere SNOWGRID | Alpen/AT | Bergfex bevorzugt (aktueller) |
| SWE | GeoSphere SNOWGRID | - | Alpen/AT | Schneewasseraequivalent |
| Sonnenstunden | *Berechnet* | - | - | effective_cloud < 30% |
| Gefuehlte Temp. | *Berechnet* | - | - | Wind Chill Formel |

**Regionen-Codes:**
- `Alpen/AT` = Oesterreich, Alpenraum
- `Global` = Weltweit verfuegbar
- Weitere Regionen koennen hinzugefuegt werden (z.B. `Korsika`, `Skandinavien`)

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

### 2. Open-Meteo (Sekundaer - nur fuer genehmigte Parameter!)

**API:** https://api.open-meteo.com/v1/forecast

**ACHTUNG:** Open-Meteo darf NUR fuer explizit genehmigte Parameter verwendet werden!

**Genehmigte Parameter:**

| Parameter | Feld in ForecastDataPoint | Genehmigt am | Status |
|-----------|---------------------------|--------------|--------|
| cloud_cover_low | cloud_low_pct | 2025-12-28 | approved |
| cloud_cover_mid | cloud_mid_pct | 2025-12-28 | approved |
| cloud_cover_high | cloud_high_pct | 2025-12-28 | approved |

**NICHT genehmigte Parameter (Beispiele):**

| Parameter | Status | Bemerkung |
|-----------|--------|-----------|
| sunshine_duration | REJECTED | Abgelehnt am 2025-12-31 |
| direct_radiation | NOT APPROVED | - |
| temperature_* | NOT APPROVED | Verwende GeoSphere |
| wind_* | NOT APPROVED | Verwende GeoSphere |

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

---

## Prozess fuer neue Datenquellen/Parameter

1. Claude erstellt Antrag in dieser Spec (als "PENDING")
2. Henning prueft und genehmigt/ablehnt
3. Erst nach Genehmigung darf implementiert werden

### Offene Antraege

Keine offenen Antraege.

### Abgelehnte Antraege

| Parameter | Quelle | Zweck | Status | Datum |
|-----------|--------|-------|--------|-------|
| sunshine_duration | Open-Meteo | Sonnenstunden-Berechnung | REJECTED | 2025-12-31 |
