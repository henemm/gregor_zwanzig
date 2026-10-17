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
