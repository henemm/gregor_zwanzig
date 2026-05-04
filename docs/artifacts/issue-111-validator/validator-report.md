---
spec: docs/specs/modules/loader_display_config_default.md
date: 2026-05-03
server: https://staging.gregor20.henemm.com
issue: 111
---

# External Validator Report

**Spec:** `docs/specs/modules/loader_display_config_default.md`
**Datum:** 2026-05-03
**Server:** https://staging.gregor20.henemm.com
**Auth:** Cookie `gz_session=validator-issue110.*`

## Methodik

Test-Trips wurden via `POST /api/trips` mit User `validator-issue110` angelegt — gezielt OHNE `display_config` im Request-Body. Der Loader-Default wurde via `GET /api/_internal/trip/{id}/loaded` geprueft. Die persistierte Disk-Form wurde via `GET /api/trips/{id}` geprueft (gibt das Trip ohne Loader-Verarbeitung zurueck).

| Trip-ID | aggregation im POST | display_config im POST |
|---------|---------------------|------------------------|
| `validator-no-config` | (fehlt) | (fehlt) |
| `validator-wintersport` | `{profile:"wintersport"}` | (fehlt) |
| `validator-agg-no-profile` | `{}` | (fehlt) |

## Checklist

| # | Expected Behavior (aus Spec) | Beweis | Verdict |
|---|------------------------------|--------|---------|
| 1 | Trip ohne `display_config` + ohne `weather_config` → `display_config` ist niemals `None` | `loaded-validator-no-config.json` hat `display_config` mit 24 Metriken; Test 2/3 ebenso | **PASS** |
| 2 | Profil wird aus `aggregation.profile` gelesen | `validator-wintersport`: enabled=`[temperature, wind_chill, wind, gust, precipitation, cloud_total, visibility, sunshine, snow_depth, fresh_snow]` (Wintersport-typische Metriken wie `snow_depth`/`fresh_snow` aktiv) | **PASS** |
| 3 | Fehlt `aggregation` → `ActivityProfile.ALLGEMEIN` | `validator-no-config` (kein `aggregation`-Key im POST) → Loader liefert `aggregation.profile = "allgemein"` und enabled=`[temperature, wind, gust, precipitation, rain_probability, cloud_total, sunshine]` | **PASS** |
| 4 | Fehlt `aggregation.profile` → `ActivityProfile.ALLGEMEIN` | `validator-agg-no-profile` (POST mit `aggregation:{}`) → Loader liefert `aggregation.profile = "allgemein"`, gleiche enabled-Metriken wie Test 3 | **PASS** |
| 5 | Side effects: Keine — JSON auf Platte unveraendert | `GET /api/trips/{id}` (raw, ohne Loader) liefert fuer alle 3 Trips den Body OHNE `display_config`-Feld zurueck — siehe `raw-persisted-trips.json` | **PASS** |
| 6 | Vermeidung von `AttributeError` bei nachgelagerten Konsumenten | Loader-Endpoint lieferte fuer alle 3 Trips `200 OK` mit konsistenter `display_config`-Struktur — kein Crash | **PASS** |

## Findings

### Beleg fuer Side-Effect-Freiheit (Behavior #5)

`GET /api/trips` Response-Auszug (raw persistiert, ohne Loader):

```json
[
  {"id":"validator-agg-no-profile","name":"...","stages":[...]},
  {"id":"validator-no-config","name":"...","stages":[...]},
  {"id":"validator-wintersport","name":"...","stages":[...],"aggregation":{"profile":"wintersport"}}
]
```

Kein einziger der drei Trips hat `display_config` im persistierten JSON. Der Loader-Default existiert ausschliesslich in-memory.

### Profilabhaengige Metriken-Differenz

| Profil | Enabled-Metriken |
|--------|-------------------|
| `allgemein` (Test 1+3) | temperature, wind, gust, precipitation, rain_probability, cloud_total, sunshine |
| `wintersport` (Test 2) | temperature, wind_chill, wind, gust, precipitation, cloud_total, visibility, sunshine, snow_depth, fresh_snow |

Wintersport hat zusaetzlich `wind_chill`, `visibility`, `snow_depth`, `fresh_snow` aktiv — kein `rain_probability` (im Winter weniger relevant). Das ist plausibel und konsistent mit "profil-abhaengiger Default".

### Beobachtung (kein Finding)

- **Severity:** INFO
- **Detail:** Spec dokumentiert in den "Known Limitations" `29 Metriken` im Default. Tatsaechlich beobachtet: 24 Metriken pro Profil. Die "Known Limitations" sind keine Expected-Behavior-Anforderungen, daher kein FAIL — aber die Doku in der Spec ist um ~5 Metriken zu hoch.
- **Evidence:** `loaded-validator-no-config.json`, `loaded-validator-wintersport.json`

## Cleanup

Alle Test-Trips wurden via `DELETE /api/trips/{id}` entfernt (alle 3 Responses: `204 No Content`).

## Verdict: **VERIFIED**

### Begruendung

Alle 6 testbaren Expected-Behavior-Punkte aus der Spec sind durch Live-Tests gegen Staging belegt:

1. Loader injiziert `display_config` zuverlaessig fuer Trips, die weder `display_config` noch `weather_config` haben.
2. Profil wird korrekt aus `aggregation.profile` uebernommen (Wintersport-Default unterscheidet sich klar von Allgemein-Default).
3. Beide Edge-Faelle (fehlende `aggregation`, `aggregation` ohne `profile`) faellen wie spezifiziert auf `ALLGEMEIN` zurueck.
4. Persistierte JSON-Files wurden vom Loader nicht modifiziert — `display_config` ist nur in-memory.
5. Kein `AttributeError` mehr — der Pipeline-relevante Endpoint laedt jeden Trip erfolgreich.

Die im Purpose genannte Regression aus Issue #111 ist behoben.
