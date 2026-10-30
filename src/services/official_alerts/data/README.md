# Eingecheckte Geometrien für amtliche Warnungen

## `dwd_warngebiete_kreise.json` — DWD-Warngebiete (Kreise), Issue #1681

Warngebiete: Deutscher Wetterdienst (DWD), CC BY 4.0; Copyright GeoBasis-DE / BKG (http://www.bkg.bund.de) 2019 (Daten modifiziert)

- **Herkunft:** DWD GeoServer WFS, Layer `dwd:Warngebiete_Kreise`, `srsName=EPSG:4326`
  (`https://maps.dwd.de/geoserver/dwd/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=dwd:Warngebiete_Kreise&outputFormat=application/json&srsName=EPSG:4326`),
  einmalig abgerufen am 2026-09-19 — zur Laufzeit wird nichts nachgeladen.
- **Umfang:** 402 Kreisflächen, je Fläche nur `WARNCELLID`, `name` und die Ringe
  (Außen- und Innenringe flach, `[lon, lat]`, Even-Odd-Regel beim Punkttest).
- **Bewusst nicht enthalten:** Küsten- und Seegebiete (`dwd:Warngebiete_Kueste`,
  `WARNCELLID`-Präfix `501…`) und Binnenseen — für Wanderpunkte irrelevant.
- **Verwendung:** `services/official_alerts/dwd_zones.py` (Punkt → `WARNCELLID`) für
  `MeteoAlarmFeedSource("DE")`.
- **Aktualisierung:** bei einer DWD-Kreisreform meldet der Drift-Wächter
  (`log_zone_drift`, Service `meteoalarm_feed:DE`) unbekannte `WARNCELLID`s aus dem Feed;
  dann den Layer mit obigem Aufruf neu ziehen.

## `avalanche_regions_{AT-07,IT-32-BZ,IT-32-TN,AT-02}.geojson.json` — EAWS-Mikroregionen, Issue #1441

Regionen-Geometrie: EAWS Micro-Regions, **CC0** (`regions.avalanches.org`).

- **Herkunft:** `https://regions.avalanches.org/micro-regions/latest/{X}_micro-regions.geojson.json`
  (nur `latest/`), einmalig abgerufen am 2026-10-13 — zur Laufzeit wird nichts nachgeladen.
  Byte-identisch zu `tests/fixtures/avalanche_report/regions/{X}_micro-regions.geojson.json`
  (Test `test_ac7_standardtabelle_...` vergleicht die Bytes).
- **Umfang:** je Mikroregion ein Feature, `properties.id` = CAAML-`regionID` (z. B. `AT-07-28`),
  Geometrie CRS84 `MultiPolygon` (`[lon, lat]`).
- **Verwendung:** `services/official_alerts/region_mapper.py` (Punkt → Mikroregionen) für
  `AvalancheReportSource` (`avalanche_report.py`, Konfigurationstabelle `AVALANCHE_REGION_TABLE`).
- **Aktualisierung:** bei einer Regionsreform der Warndienste die Datei aus `latest/` neu ziehen
  (Fixture und Paketkopie gemeinsam). Ein weiteres Land = neue Tabellenzeile + Regionsdatei hier.

## `avalanche_regions_CH.geojson.json` — EAWS-Mikroregionen der Schweiz, Issue #1441 S3

Regionen-Geometrie: EAWS Micro-Regions, **CC0** (`regions.avalanches.org`).

- **Herkunft:** `https://regions.avalanches.org/micro-regions/latest/CH_micro-regions.geojson.json`,
  einmalig abgerufen am 2026-10-17 — zur Laufzeit wird nichts nachgeladen. Byte-identisch zu
  `docs/artifacts/feat-1441-s3-slf/raw/CH_micro-regions.geojson.json` und
  `tests/fixtures/slf/CH_micro-regions.geojson.json`.
- **Umfang:** 149 Mikroregionen, `properties.id` = CAAML-`regionID` (z. B. `CH-7231`),
  Geometrie CRS84 `MultiPolygon` (`[lon, lat]`).
- **Verwendung:** `services/official_alerts/slf.py` (`SlfSource.covers()` und Punkt → Mikroregion
  per Polygon, keine Bounding-Box). Bewusst keine Liste nie bewerteter Regionen (Mittelland):
  eine im Bulletin fehlende Region gilt als „nicht zuständig".
- **Aktualisierung:** bei einer Regionsreform des SLF die Datei aus `latest/` neu ziehen
  (Paketkopie und Test-Fixture gemeinsam).

## `meteoalarm_outlines_nordics.geojson.json` — Landesumrisse Norwegen/Schweden, Issue #1442 S2

Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com (**gemeinfrei**).

- **Herkunft:** `https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip`,
  Natural Earth **5.1.1**, einmalig abgerufen am 2026-10-30 (sha256 der ZIP
  `ce1ac7036499a0edd641fbc093cd209a98f96a49d2eca8480aaacad35138a7f6`) — zur Laufzeit wird nichts
  nachgeladen.
- **Umfang:** zwei Features, `properties.id` = `NO` / `SE` (Auswahl `ADM0_A3` = `NOR`/`SWE`),
  `MultiPolygon` `[lon, lat]`, 4 Nachkommastellen.
- **Bewusst verändert:** nur Teilflächen mit Schwerpunkt nördlich 50° (Festland, Inseln,
  Svalbard), vereinigt, **um 0,1° aufgeweitet** (shapely `buffer(0.1)`), dann `simplify(0.01)`.
  Zweck: `covers()` lieber zu groß als zu klein (Küste, Inseln; Spec Impl. 3). Gemessen: alle
  14+14 Rand-/Küstenpunkte der Tests innen; Kopenhagen, Flensburg, Tallinn, Murmansk, Berlin,
  Wien und (75,0 N / 5,0 O) außen.
- **Ohne Finnland:** Natural Earth führt Åland als eigenes `ADM0` — ein FI-Umriss verfehlte
  Mariehamn. Finnland nutzt stattdessen die Zonengeometrie unten (Land + See).
- **Verwendung:** `meteoalarm_feed._in_outline()` für `MeteoAlarmFeedSource("NO"/"SE")`.

## `meteoalarm_zones_FI.geojson.json` — MeteoAlarm-Warnzonen Finnland (`EMMA_ID`), Issue #1442 S2

Zonengeometrie: EUMETNET-MeteoAlarm, Datei `geocodes.json` (offizielle Zuordnung `EMMA_ID` →
Geometrie). **Lizenz: ungeklärt** — am 2026-10-30 war auf meteoalarm.org (Nutzungsbedingungen,
JavaScript-Anwendung) keine Lizenzangabe zur Geocode-Datei auffindbar; mit dem PO zu klären
(Antrag in `docs/specs/data_sources.md`).

- **Herkunft:** Google-Drive-Datei-ID `16s24hYHfYQhKMNcP1hpgQmg13Yb8j0hV` (dieselbe ID nutzt
  KDE `foss-public-alert-server`, `alertHandler/generate_EMMA_ID.py`), einmalig abgerufen am
  2026-10-30, 39 MB, sha256 `0c8fe7b9af4f86c72f1c28bb9cea02f673fee6d45d02681713e6ad3ebd615dd0`.
  Eingecheckt ist nur der FI-Auszug (`country` = `FI`, `type` = `EMMA_ID`): 53 Zonen,
  `properties.id` = `EMMA_ID`, `properties.name` = Name laut `geocodes.json`.
- **Bewusst verändert:** Landzonen (`FI0xx`) **um 0,05° aufgeweitet** und mit `simplify(0.005)`
  vereinfacht — die Originalumrisse sind grob vereinfacht, Helsinki (0,029° außerhalb von FI034)
  und Kotka (0,019° außerhalb von FI036) fielen sonst nur ins Seegebiet. Seezonen (`FI8xx`)
  unverändert. Ein Küstenort liegt damit in Land- UND Seezone; `fetch()` wertet alle getroffenen
  Zonen aus (jede Warnung einmal).
- **Beleg der Zuordnung** (Feed-`areaDesc` in derselben Reihenfolge wie die `EMMA_ID`-Liste des
  Feeds, `tests/fixtures/meteoalarm_feed/feed_finland_sample.json`, gegen `name` in
  `geocodes.json`):

  | EMMA_ID | Feed (`fi-FI`) | `geocodes.json` |
  |---|---|---|
  | FI029 | Pohjanmaa | Pohjanmaa |
  | FI032 | Varsinais-Suomi | Varsinais-Suomi |
  | FI043 | Ahvenanmaa | Ahvenanmaa |
  | FI801 | Merenkurkku | The Quark |
  | FI802 | Selkämeren pohjoisosa | Northern Sea of Bothnia |
  | FI803 | Pohjois-Itämeren länsiosa | Western part of Northern Baltic |
  | FI806 | Suomenlahden länsiosa | Western Gulf of Finland |
  | FI807 | Selkämeren eteläosa | Southern Sea of Bothnia |
  | FI809 | Perämeren pohjoisosa | Northern Bay of Bothnia |
  | FI810 | Perämeren eteläosa | Southern Bay of Bothnia |
  | FI812 | Pohjois-Itämeren itäosa | Eastern part of Northern Baltic |
  | FI813 | Ahvenanmeri | Sea of Aaland |

- **Lücken:** `FI035` (vermutlich Itä-Uusimaa, 2011 in Uusimaa aufgegangen), `FI804`, `FI808`
  fehlen in `geocodes.json`. Taucht eine unbekannte Zone im Feed auf, meldet der Drift-Wächter
  (`log_zone_drift`, Service `meteoalarm_feed:FI`, `unknown_zone`); dann `geocodes.json` neu ziehen
  und den Auszug mit denselben Parametern neu bauen.
- **Verwendung:** `meteoalarm_feed._zones_for_point_fi()` für `covers()` UND `fetch()` von
  `MeteoAlarmFeedSource("FI")` (Muster DE: eine Zonenfunktion für beide).
