---
entity_id: data_sources
type: reference
created: 2025-12-31
updated: 2025-12-31
status: implemented
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
| Lawinengefahrenstufe (EAWS 1-5) | avalanche.report (CAAML v6) | - | Tirol, Suedtirol, Trentino, Kaernten | Amtlicher Lagebericht, CC BY 4.0, siehe Antrag #6 |

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
| elevation | ForecastMeta.model_elevation_m (Antwort) | 2026-08-20 | approved (Antrag #4) |

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
| direct_radiation | NOT APPROVED | wird auch nicht gesendet — der Code fragt stattdessen `direct_normal_irradiance` (DNI) ab, s. Ist-Tabelle unten (#2236 B2-67) |
| snowfall | NOT APPROVED | Verwende GeoSphere SNOWGRID |
| snow_depth | NOT APPROVED | Verwende GeoSphere/Bergfex |

**Produktiv gesendet, aber in dieser Positivliste nicht gefuehrt (Befund #2236 B2-67, Stand 2026-09-09):**

`src/providers/openmeteo.py::fetch_forecast` sendet acht Parameter, die hier weder genehmigt noch
abgelehnt stehen. Diese Tabelle ist der **Ist-Stand**, kein Freigabe-Nachweis — die Freigabe ist
PO-Entscheid und als Antrag #5 (unten) vorbereitet.

| Parameter | Feld in ForecastDataPoint | Spec-Spur | Status |
|-----------|---------------------------|-----------|--------|
| apparent_temperature | wind_chill_c | #1887 E6 (herstellereigene gefuehlte Temperatur, keine Windchill-Formel) | in Betrieb, Freigabe offen |
| visibility | visibility_m | #846 (Sichtweite-Alarm), `feat_1492_s2b_fallback_sichtbarkeit.md` | in Betrieb, Freigabe offen |
| precipitation_probability | pop_pct | `feat_1492_s2b_fallback_sichtbarkeit.md` | in Betrieb, Freigabe offen |
| cape | cape_jkg | #1592 / #1679 (Gewitter-Fusion, ADR-0048) | in Betrieb, Freigabe offen |
| freezing_level_height | freezing_level_m | #959 (Nullgradgrenze) | in Betrieb, Freigabe offen |
| uv_index | uv_index | `provider_openmeteo.md` (bei allen 5 Wettermodellen `null`; produktiv ueber die Air-Quality-API `/v1/air-quality`, CAMS) | in Betrieb, Freigabe offen |
| direct_normal_irradiance | dni_wm2 | `weather_emoji_dni.md` (Spec selbst nicht freigegeben) | in Betrieb, Freigabe offen |
| is_day | is_day | `weather_emoji_dni.md` | in Betrieb, Freigabe offen |

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
| 2026-08-01 | 1.2 | Amtliche Warnungen nachgetragen: MeteoAlarm (Bestand, war nie eingetragen) + Wechsel des Bezugswegs auf den kontingentfreien Feed `feeds.meteoalarm.org`. Siehe ADR-0039. | Henning (PO-Entscheidung 2026-08-01) |
| 2026-10-13 | 1.3 | Amtlicher Lawinen-Lagebericht ueber avalanche.report (Tirol, Suedtirol, Trentino, Kaernten), Issue #1441. Siehe ADR-0089. | Henning (Spec-Freigabe 2026-10-13) |
| 2026-10-17 | 1.4 | Amtlicher Lawinen-Lagebericht des SLF (Schweiz, `aws.slf.ch`), Issue #1441 S3, Antrag #7, genehmigt mit Auflagen (Quellenangabe, Link, schriftliche Anfrage beim SLF, Abschaltbarkeit). Siehe ADR-0091. | Henning (PO-Entscheid 2026-10-17) |

---

## Prozess fuer neue Datenquellen/Parameter

1. Claude erstellt Antrag in dieser Spec (als "PENDING")
2. Henning prueft und genehmigt/ablehnt
3. Erst nach Genehmigung darf implementiert werden

### Offene Antraege

- Antrag #2, Zeile „Amtliche Warnungen CH" (Issue #1442 S1): Laenderscope Schweiz ueber den
  bereits genehmigten MeteoAlarm-Feed — PENDING bis zur Spec-Freigabe.
- Antrag #2, Zeile „Amtliche Warnungen NO/SE/FI" (Issue #1442 S2): Laenderscope Norwegen,
  Schweden, Finnland ueber denselben Feed — PENDING bis zur Spec-Freigabe
  (`feat_1442_s2_meteoalarm_nordics.md`). Lizenz der eingecheckten FI-Zonengeometrie
  (MeteoAlarm `geocodes.json`) ist noch ungeklaert, s. `src/services/official_alerts/data/README.md`.
- Antrag #2, Zeile „Amtliche Warnungen ES" (Issue #1442 S3): Laenderscope Spanien (AEMET) ueber
  denselben Feed (`feeds-spain`) — PENDING bis zur Spec-Freigabe (`feat_1442_s3_meteoalarm_spanien.md`).
  Die eingecheckte Spanien-Zonengeometrie `meteoalarm_zones_ES.geojson.json` stammt aus derselben
  MeteoAlarm `geocodes.json` wie die FI-Datei; ihre Lizenz wird **gebuendelt mit Finnland** im selben
  Antrag geklaert (nicht neu entschieden), s. `src/services/official_alerts/data/README.md`.

### Genehmigte Antraege

#### Antrag #7: Lawinen-Lagebericht des SLF (Schweiz, CAAML v6)

**Datum:** 2026-10-17
**Status:** ✅ APPROVED mit Auflagen (2026-10-17, Henning — PO-Entscheid vor der Spec-Freigabe)
**Antragsteller:** Claude (Issue #1441 Scheibe S3)
**Spec:** `docs/specs/modules/feat_1441_s3_slf.md`
**ADR:** [ADR-0091](../adr/0091-slf-eigene-lawinenquelle.md)

**Zusammenfassung:** Der amtliche Lawinen-Lagebericht des WSL-Instituts fuer Schnee- und
Lawinenforschung SLF (EAWS-Gefahrenstufe 1-5 mit amtlicher Feinstufe, Hoehengrenze und
Lawinenproblem fuer die ganze Schweiz), bezogen als CAAML-v6-JSON von `aws.slf.ch`
(`/api/bulletin/caaml/de/json`, ohne Schluessel). Ein Abruf fuer die ganze Schweiz ueber
`warn_egress.cached_fetch` (TTL 1800 s). Die Schnittstelle traegt **keine ausdrueckliche
Weiterverwendungs-Lizenz**; die Rechtliches-Seite des SLF enthaelt nur Haftungsausschluss und
Eigenverantwortung.

| Daten | Status | Bemerkung |
|-------|--------|-----------|
| Lawinen-Lagebericht SLF (Stufe, Feinstufe, Hoehe, Problem, Gueltigkeit) | approved mit Auflagen | Host `aws.slf.ch`; Auflagen siehe unten |
| Mikroregionen-Geometrie CH (EAWS Regions, `regions.avalanches.org`, nur `latest/`) | approved | **CC0**, eine Datei eingecheckt (`avalanche_regions_CH.geojson.json`), kein Laufzeitabruf |

**Auflagen des PO (2026-10-17):**
1. **Quellenangabe** „WSL-Institut fuer Schnee- und Lawinenforschung SLF" in Mail und Telegram-Langform,
   dazu der Link zum Originalbericht `https://www.slf.ch/de/lawinenbulletin-und-schneesituation/`
   (die API hat kein Link-Feld) und der Hinweis, dass der Originalbericht massgeblich ist.
2. **Schriftliche Anfrage beim SLF** zur Weiterverwendung (Entwurf:
   `docs/artifacts/feat-1441-s3-slf/anfrage_slf_entwurf.md`; Versand durch den PO).
3. **Abschaltbar mit einer Zeile:** Lehnt das SLF ab, wird die Quelle abgeschaltet, indem die
   Registrierung in `src/services/official_alerts/__init__.py` entfernt wird; die Spec sichert das
   mit einem Test ab.
4. Stufe, Feinstufe, Hoehe und Problemnamen bleiben Wortlaut des SLF (Haftung); nur Daten, keine
   Handlungsempfehlung.

**Begruendung:** Der SLF-Bericht ist fuer Weitwanderer in der Schweiz die amtliche
Lawineninformation; die Awareness-Warnungen von MeteoAlarm sind dafuer zu grob und fuer die
Schweiz nicht angebunden.

#### Antrag #6: Lawinen-Lagebericht ueber avalanche.report (CAAML v6)

**Datum:** 2026-10-13
**Status:** ✅ APPROVED (2026-10-13, Henning — mit der Freigabe der Spec)
**Antragsteller:** Claude (Issue #1441 Slice 1, Epic #2258)
**Spec:** `docs/specs/modules/avalanche_report_bulletin.md`
**ADR:** [ADR-0089](../adr/0089-lawinen-lagebericht-zweite-skala.md)

**Zusammenfassung:** Der amtliche Lawinen-Lagebericht (EAWS-Gefahrenstufe 1-5 mit Hoehengrenze
und Lawinenproblem) der Euregio Tirol-Suedtirol-Trentino und des Lawinenwarndienstes Kaernten,
bezogen als statische CAAML-v6-Dateien von `static.avalanche.report` (leitet per 301 auf
`avalanche.report` weiter). Kein Schluessel, kein veroeffentlichtes Limit; Abruf nur ueber
`warn_egress.cached_fetch` (TTL 1800 s).

| Daten | Status | Bemerkung |
|-------|--------|-----------|
| Lawinen-Lagebericht AT-07, IT-32-BZ, IT-32-TN, AT-02 (Stufe, Hoehe, Problem, Gueltigkeit) | approved | Hosts `static.avalanche.report` + `avalanche.report`; Lizenz **CC BY 4.0** — Quellenname und Bulletin-Link in Mail und Telegram |
| Mikroregionen-Geometrie (EAWS Regions, `regions.avalanches.org`, nur `latest/`) | approved | **CC0**, vier Dateien eingecheckt, kein Laufzeitabruf |
| Salzburg, Bayern, uebrige AT-Laender | **nicht beantragt** | Lizenz der Dienste nicht belegt; Freischaltung spaeter per Tabelleneintrag nach Lizenzzusage |
| `lawinen-warnung.eu`, EU-Sammelfeed `eaws_bulletins`, SLF | **nicht beantragt** | SLF (Schweiz) = Slice 2 |

**Begruendung:** Der Lagebericht ist fuer Weitwanderer im Winter und Fruehjahr die zentrale
Sicherheitsinformation; MeteoAlarm liefert nur eine grobe Awareness-Stufe 1-4.

#### Antrag #2: MeteoAlarm — amtliche Unwetterwarnungen ueber den kontingentfreien Feed

**Datum:** 2026-08-01
**Status:** ✅ APPROVED (2026-08-01, Henning)
**Antragsteller:** Claude (Issue #1445, ausgeloest durch #1397)
**Spec:** `docs/specs/modules/feat_1445_s1_feed_bestandsquelle.md`, `feat_1445_s3_oesterreich_feed.md`
**ADR:** [ADR-0039](../adr/0039-amtliche-warnungen-aus-kontingentfreiem-feed.md)

**Zusammenfassung:** MeteoAlarm (EUMETNET) war als Quelle amtlicher Unwetterwarnungen fuer
Oesterreich und Italien seit Issue #1086 im Einsatz, aber in dieser Spec **nie eingetragen** —
das wird hier nachgeholt. Zugleich wechselt der Bezugsweg.

| Daten | Status | Bemerkung |
|-------|--------|-----------|
| Amtliche Warnungen AT/IT (Ereignis, Warnstufe, Gefahrenart, Gueltigkeit, Gebiet) | approved | Quelle: `feeds.meteoalarm.org/api/v1/warnings/feeds-<land>`, ohne Auth, **ohne Mengenbegrenzung**, ein Abruf je Land und Auffrischung |
| Amtliche Warnungen CH (MeteoSchweiz, Issue #1442 S1) | **PENDING** (Freigabe mit Spec `feat_1442_s1_meteoalarm_ch.md`) | Gleicher Feed-Weg: `feeds.meteoalarm.org/api/v1/warnings/feeds-switzerland`, ohne Auth, kontingentfrei, kein neuer Host. **Kein** Tagesbudget, **kein** EDR (`api.meteoalarm.org`) — beides mit #2266 zurueckgebaut; nur 30-min-Cache (1800 s / 60 s). Zuordnung per Punkt-in-Polygon gegen die Gemeinde-Umrisse des Feeds (kein Geocode), Zustaendigkeit lokal ueber die SLF-Regionspolygone |
| Amtliche Warnungen NO/SE/FI (MET Norway, SMHI, FMI, Issue #1442 S2) | **PENDING** (Freigabe mit Spec `feat_1442_s2_meteoalarm_nordics.md`) | Gleicher Feed-Weg: `feeds.meteoalarm.org/api/v1/warnings/feeds-norway` / `-sweden` / `-finland`, ohne Auth, kontingentfrei, kein neuer Host, kein Tagesbudget (Ticket-AC-2 gegenstandslos), nur 30-min-Cache (1800 s / 60 s). NO/SE: Punkt-in-Polygon gegen die Feed-Polygone, Zustaendigkeit lokal ueber aufgeweitete Natural-Earth-Landesumrisse (gemeinfrei). FI: `EMMA_ID` gegen eingecheckte MeteoAlarm-Zonengeometrie (`geocodes.json`, Lizenz ungeklaert) — kein Laufzeitzugriff auf FMI |
| Amtliche Warnungen ES (AEMET, Issue #1442 S3) | **PENDING** (Freigabe mit Spec `feat_1442_s3_meteoalarm_spanien.md`) | Gleicher Feed-Weg: `feeds.meteoalarm.org/api/v1/warnings/feeds-spain`, ohne Auth, kontingentfrei, kein neuer Host, nur 30-min-Cache (1800 s / 60 s). Feed ohne Polygone: `EMMA_ID` gegen eingecheckte Zonengeometrie `meteoalarm_zones_ES.geojson.json` (aus MeteoAlarm `geocodes.json`, Lizenz ungeklaert, gebuendelt mit FI) — kein Laufzeitzugriff auf AEMET |
| Zonen-Geometrie (Punkt-in-Flaeche) | approved | IT ueber eingecheckte DPC-Zonen, AT ueber die Gemeindenummer aus der ohnehin abgerufenen ZAMG-Antwort — keine zusaetzlichen Abrufe |
| `api.meteoalarm.org` (EDR-Index, authentifiziert) | **zurueckgebaut** | Mengenbegrenzt und nicht stationaer (durchgelassene Menge sank 138 → 95 → 64). Seit #1445 S3 nicht mehr registriert; mit #2266 zurueckgebaut (EDR-Klasse, Tagesbudget und Egress-Inventar-Eintrag entfernt, Aequivalenz ueber eingefrorene Snapshots im Kern-Test belegt) |
| CAP-XML / Geometrie-Nachladen (`meteo.fra1.digitaloceanspaces.com`) | **entfallen** | praesigniert, auth-frei, zaehlt nicht gegen ein Kontingent. Wurde nur vom EDR-Weg nachgeladen; mit dessen Rueckbau (#2266) ohne Abruf |
| MQTT-Echtzeitkanal (`mqtt.meteoalarm.org:8883`) | **noch nicht genutzt** | Zugang verifiziert, liefert aber keinen Bestand (keine Retained Messages). Als spaetere Ergaenzung vorgesehen, nicht als Ersatz |

**Begruendung:** Gleicher Anbieter, gleiche Daten, anderer Transport. Der bisherige Weg sperrte
uns taeglich fuer 24 h aus; amtliche Warnungen waren dadurch den groessten Teil des Tages
veraltet — bei einem Sicherheitswerkzeug fuer Weitwanderungen nicht hinnehmbar. Der Feed liefert
zusaetzlich eine laengere Rueckschau (5,8 Tage statt 23 h) und deutschsprachige Texte fuer AT.

**Lizenz-Pruefergebnis zur Feed-TTL (Nachtrag 2026-10-27, #2266):** Geprueft wurde, ob die
Feed-TTL von 30 Minuten zur EUMETNET-Weitergabe-Auflage passt (kolportiert als „5–10 min Verzug").
Im Repo liegt keine Primaerquelle fuer diese Auflage vor; auch die Recherche nannte nur einen
moeglichen Verzug gegenueber meteoalarm.eu, ohne Minutenangabe. Soweit bekannt verlangt die Auflage
einen Mindest-Verzug; ein Cache von 30 Minuten erfuellt diesen Mindest-Verzug, und eine Obergrenze
ist nicht belegt. Die TTL von 1800 s bleibt unveraendert (Entscheidung ADR-0074, dort im Abschnitt
„Lizenz-Pruefergebnis"). Wiedervorlage nur, wenn eine Primaerquelle auftaucht.

#### Antrag #3 (Nachtrag): Open-Meteo `minutely_15` — Radar-Nowcast

**Datum:** 2026-08-07
**Status:** ✅ APPROVED (Nachtrag — bereits seit #656 produktiv genutzt)
**Antragsteller:** Claude (Issue #1439, Governance-Nachtrag zu Issue #656)
**Spec:** `docs/specs/modules/feat_1439_starkregen_kurzfristhinweis.md`

**Zusammenfassung:** `minutely_15` (Open-Meteo, Parameter `precipitation`/`weather_code`) ist der
globale Fallback des bereits produktiven `RadarNowcastService` (Issue #656, `src/services/radar_service.py`)
fuer den Regen-/Gewitter-Nowcast (Horizont `NOWCAST_HORIZON_MIN`, 180 Min seit #1945, zuvor 60 Min) —
ausserhalb der RADOLAN/INCA/DPC/AROME-Bounding-Boxen sowie
als Sidecar-Quelle fuer den Konvektions-Check. War in dieser Spec bisher nicht eingetragen; kein neuer
Parameter, reiner Nachtrag.

| Daten | Status | Bemerkung |
|-------|--------|-----------|
| `minutely_15` (precipitation, weather_code) | approved (Nachtrag) | Open-Meteo, seit #656 produktiv im Nowcast-Pfad (Fallback + Konvektions-Sidecar) |

#### Antrag #5: Open-Meteo — acht bereits produktiv gesendete Parameter nachtraeglich freigeben

**Datum:** 2026-09-09
**Status:** ⏳ OFFEN — PO-Entscheid ausstehend
**Antragsteller:** Claude (Issue #2236, Befund B2-67 aus #1199)
**Spec:** dieses Dokument (Ist-Tabelle unter „2. Open-Meteo")

**Zusammenfassung:** `fetch_forecast` sendet seit laengerem `apparent_temperature`, `visibility`,
`precipitation_probability`, `cape`, `freezing_level_height`, `uv_index`,
`direct_normal_irradiance` und `is_day`, ohne dass diese Positivliste sie fuehrt. Die Parameter
tragen produktive Funktionen (Windchill-Spalte, Sichtweite-Alarm, Gewitter-Fusion, Nullgradgrenze,
UV, Wetter-Emoji Tag/Nacht). Der Antrag legalisiert den Bestand; er fuehrt **keinen** neuen
Parameter ein. Bei Ablehnung eines Eintrags ist der Rueckbau ein eigenes Issue.

**Genehmigt durch:** — (offen)

#### Antrag #4: Open-Meteo `elevation` — Wegpunkt-Hoehe an den Provider

**Datum:** 2026-08-20
**Status:** ✅ APPROVED (2026-08-20, Henning)
**Antragsteller:** Claude (Issue #1991)
**Spec:** `docs/specs/modules/wegpunkt_hoehe_provider.md`
**ADR:** [ADR-0058](../adr/0058-wegpunkt-hoehe-an-provider-api.md)

**Zusammenfassung:** `elevation` wird bei jeder Open-Meteo-Anfrage (Hauptvorhersage, Ensemble-
Anreicherung, Wolken-Abruf ueber GeoSphere, Radar-Nowcast) mitgeschickt, wenn der angefragte
Wegpunkt eine Hoehe kennt — damit rechnet der Provider seine Vorhersage auf die echte Hoehe
herunter statt auf die Hoehe seiner eigenen, geglaetteten Geländekarte (gemessen bis 6,2 °C
Abweichung an einem einzigen Punkt). Kein neuer Datenwert, sondern ein bestehender, bislang nicht
gesendeter Anfrage-Parameter samt seines Antwort-Gegenstuecks `elevation` (die vom Modell
tatsaechlich verwendete Hoehe, landet in `ForecastMeta.model_elevation_m`).

| Daten | Status | Bemerkung |
|-------|--------|-----------|
| `elevation` (Anfrage-Parameter) | approved | NUR gesendet wenn die Hoehe des Wegpunkts bekannt ist; sonst kein Parameter (kein Platzhalter) |
| `elevation` (Antwort-Feld, `ForecastMeta.model_elevation_m`) | approved | vom Provider gemeldete, tatsaechlich verwendete Hoehe |

**Begruendung:** PO-Entscheid 2026-08-20 — Hoehe an die Schnittstelle durchreichen, Korrektur
macht die Quelle, keine eigene Hoehenphysik (ADR-0058).

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
