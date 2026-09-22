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
