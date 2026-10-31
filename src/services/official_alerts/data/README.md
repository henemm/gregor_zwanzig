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
- **Verwendung:** `meteoalarm_feed._zones_for_point("FI", …)` für `covers()` UND `fetch()` von
  `MeteoAlarmFeedSource("FI")` (Muster DE: eine Zonenfunktion für beide; seit #1442 S3 gemeinsamer
  Zonenweg mit ES über `_zone_mappers`).

## `meteoalarm_zones_ES.geojson.json` — MeteoAlarm-Warnzonen Spanien (`EMMA_ID`), Issue #1442 S3

Gleiche Quelle und gleiche **ungeklärte Lizenz** wie der FI-Auszug (gebündelt im bestehenden Antrag in
`docs/specs/data_sources.md`). Der Spanien-Feed (`feeds-spain`) trägt keine Polygone, nur `EMMA_ID`.

- **Herkunft:** MeteoAlarm `geocodes.json`, Google-Drive-Datei-ID `16s24hYHfYQhKMNcP1hpgQmg13Yb8j0hV`,
  abgerufen am 2026-10-30, 39 256 854 Byte, sha256
  `0c8fe7b9af4f86c72f1c28bb9cea02f673fee6d45d02681713e6ad3ebd615dd0` (identisch zur FI-Quelle,
  vor dem Bau geprüft). Eingecheckt ist nur der ES-Auszug (`type` = `EMMA_ID`, `code` mit Präfix `ES`):
  **233 Zonen** — Festland und Balearen `ES070`–`ES119`, `ES133`–`ES251`, Kanaren `ES120`–`ES132`,
  Küste/See `ES840`–`ES890` (inkl. Ceuta `ES871`, Melilla `ES872`). `properties.id` = `EMMA_ID`
  (umgeschrieben aus `code`, der Mapper liest nur `id`), `properties.name` = Name laut `geocodes.json`
  (unverändert, auch wo die Quelle Umlaute/Akzente verstümmelt). Ergebnis 206 949 Byte, sha256
  `5fced41799f51e2b38dcb75c61fb26aadac788c0aca915aa5f8c14510ba843a3`.
- **Bewusst verändert:** Landzonen **um 0,05° aufgeweitet** (`buffer(0.05)`) und mit
  `simplify(0.005, preserve_topology=True)` vereinfacht; Seezonen `ES840`–`ES890` (`Costa - …`)
  **unverändert**. Alle Koordinaten auf 4 Nachkommastellen gerundet (ca. 11 m, wie FI). Grund
  (Messung gegen die Rohgeometrie): Sa Dragonera (39,587/2,319) liegt 0,037° und Port d'Andratx
  (39,545/2,388) 0,001° außerhalb von `ES117` — beide fielen roh nur in die Seezone `ES874`.
  Folgen der Aufweitung: Küstenort = Land- UND Seezone; aufgeweitete Landzonen überlappen sich an
  ihren Grenzen (Lluc 39,822/2,887: roh `ES114`, aufgeweitet zusätzlich `ES115`/`ES116`); im
  französischen Grenzstreifen trifft z. B. Hendaye `ES233` und Bourg-Madame `ES182`. Jede Warnung
  zählt trotzdem nur einmal.
- **Skript-Parameter** (einmaliger Bau, shapely nur dafür, keine Laufzeit-Abhängigkeit):
  `uv run --no-project --with shapely python -I build_es_zones.py geocodes.json out.json 0.05 0.005 4`
  (Argumente: Quelle, Ziel, Aufweitung in Grad, `simplify`-Toleranz, Nachkommastellen). Seezone =
  Nummer 840–890; Ausgabe nach `id` sortiert. Wird die Datei größer als 400 KB, `simplify` erhöhen.
- **Beleg 1:1-Abgleich:** Live-Abruf `feeds-spain` am 2026-10-30 (97 Warnungen, 1,3 MB) nennt
  233 verschiedene `EMMA_ID`; Abgleich mit dem Auszug: 0 Feed-Zonen ohne Geometrie, 0 Zonen im
  Auszug ohne Feed-Bezug. Jede Zone der Fixture `tests/fixtures/meteoalarm_feed/feed_spain_sample.json`
  ist enthalten (Test AC-14).
- **Drift:** unbekannte Feed-Zone ⇒ Drift-Wächter (`log_zone_drift`, Service `meteoalarm_feed:ES`,
  `unknown_zone`); dann `geocodes.json` neu ziehen und mit denselben Parametern neu bauen.
- **Verwendung:** `meteoalarm_feed._zones_for_point("ES", …)` für `covers()` UND `fetch()` von
  `MeteoAlarmFeedSource("ES")` (gemeinsamer Zonenweg `_fetch_zones` mit FI).

## `meteoalarm_zones_{PT,NL,PL}.geojson.json` — MeteoAlarm-Warnzonen Portugal, Niederlande, Polen (`EMMA_ID`), Issue #1442 S3a

Gleiche Quelle und gleiche **ungeklärte Lizenz** wie die FI- und ES-Auszüge (gebündelt im bestehenden
Antrag in `docs/specs/data_sources.md`). Die drei Feeds (`feeds-portugal`, `feeds-netherlands`,
`feeds-poland`) tragen keine Polygone, nur `EMMA_ID`.

- **Herkunft:** MeteoAlarm `geocodes.json`, Google-Drive-Datei-ID `16s24hYHfYQhKMNcP1hpgQmg13Yb8j0hV`,
  abgerufen am 2026-10-30, 39 256 854 Byte, sha256
  `0c8fe7b9af4f86c72f1c28bb9cea02f673fee6d45d02681713e6ad3ebd615dd0` (identisch zur FI-/ES-Quelle,
  vor dem Bau geprüft). Eingecheckt ist je Land nur der Auszug `type` = `EMMA_ID`, `code` mit
  Länderpräfix; `properties.id` = `EMMA_ID` (umgeschrieben aus `code`), `properties.name` = Name laut
  `geocodes.json` (unverändert; in PT lautet er bei allen Zonen nur „Portugal").

  | Datei | Zonen | davon Wasser (unverändert) | Byte | sha256 |
  |---|---|---|---|---|
  | `meteoalarm_zones_PT.geojson.json` | 25 (Festland `PT005`–`PT022`, Azoren `PT001`–`PT003`, Madeira `PT023`–`PT026`) | keine | 34 769 | `9d4cb926bf592798a94875073503ef4d923e58db45451e2b328553e48c270b45` |
  | `meteoalarm_zones_NL.geojson.json` | 20 (13 Provinzen `NL007`–`NL019` + 7 Wasserzonen) | 7: `NL801`–`NL805` Küstenstreifen (Vlissingen … Rottum), `NL806` Waddenzee, `NL807` IJsselmeer | 28 495 | `3ccb88e850c62ee2c5269da6450edc071e588349f39bbcf1114a1e21462ce8dd` |
  | `meteoalarm_zones_PL.geojson.json` | 385 (380 Kreise/Powiats, **vierstellig** `PL0201`…`PL3263`, + 5 Seezonen) | 5: **dreistellig** `PL801`–`PL805` (Strefa brzegowa / Coastal Zone) | 241 503 | `1408601f0d2a9f75881195434af5b388e7584b6195d334e9238ad7b141cca72d` |

- **Seezonen-Regel je Land** (gemessen an Code + Name in `geocodes.json`, NICHT die spanische Regel
  „840–890"): PT hat keine Seezone; NL: Nummer ≥ 800; PL: nur die **dreistelligen** Nummern 8xx.
  **Falle beim Neubau:** `PL0801`, `PL0805` usw. (vierstellig, Woiwodschaft Lubuskie) sind Landkreise
  und werden aufgeweitet; nur `PL801`–`PL805` sind See.
- **Bewusst verändert:** Landzonen **um 0,05° aufgeweitet** (`buffer(0.05)`) und mit
  `simplify(0.005, preserve_topology=True)` vereinfacht; Wasserzonen unverändert. Alle Koordinaten auf
  4 Nachkommastellen gerundet (wie FI/ES). Messung der Testorte (roh → gebaut): Den Helder Stadt
  `NL011` → `NL011`+`NL019`; Hafen Den Helder (52,96/4,78) roh nur `NL806` → `NL011`+`NL019`+`NL806`;
  West-Terschelling roh nur `NL806` → `NL019`+`NL806`; Hafen Danzig (54,42/18,68) roh nur
  `PL801`+`PL805` → zusätzlich `PL2261`; Hel roh nur `PL801` → `PL2211`+`PL801`; Funchal `PT024` →
  `PT023`+`PT024`; Lissabon `PT016` → `PT016`+`PT020`; Krakau `PL1261` → `PL1206`+`PL1261`. Alle
  übrigen Land-, Küsten- und Grenzorte der Spec-Tabelle (Porto, Faro, Cabo da Roca, Elvas, Amsterdam,
  Maastricht, Terschelling, Venlo, Baarle-Nassau, Warschau, Zakopane, Danzig, Słubice) liegen in ihrer
  Rohzone. Grenzstreifen: Kaldenkirchen (DE) trifft aufgeweitet `NL012`, Frankfurt (Oder) `PL0805`;
  Badajoz (ES), Madrid, Paris, Berlin, Prag, Vilnius liegen in keiner PT/NL/PL-Zone. Jede Warnung
  zählt trotzdem nur einmal; das Nachbarland führt im Feed nur eigene Zonen.
- **Skript-Parameter** (einmaliger Bau, shapely nur dafür, keine Laufzeit-Abhängigkeit; abgeleitet aus
  dem ES-Skript mit Seezonen-Regel je Land):
  `uv run --no-project --with shapely python -I build_zones.py geocodes.json <PT|NL|PL> out.json 0.05 0.005 4`
  (Argumente: Quelle, Land, Ziel, Aufweitung in Grad, `simplify`-Toleranz, Nachkommastellen). Ausgabe
  nach `id` sortiert. Wird eine Datei größer als 400 KB, `simplify` erhöhen.
- **Beleg 1:1-Abgleich:** Live-Abrufe am 2026-10-30: `feeds-portugal` 5 Warnungen / 5 verschiedene
  `EMMA_ID`, `feeds-netherlands` 754 / 15, `feeds-poland` 156 / 126; einzige Geocode-Art jeweils
  `EMMA_ID`. Abgleich mit den Auszügen: 0 Feed-Zonen ohne Geometrie (PT 5/25, NL 15/20, PL 126/385).
  Jede Zone der Fixtures `tests/fixtures/meteoalarm_feed/feed_{portugal,netherlands,poland}_sample.json`
  ist enthalten (Test AC-11 `test_ac11_zonendatei_deckt_feed_zonen_vollstaendig`).
- **Drift:** unbekannte Feed-Zone ⇒ Drift-Wächter (`log_zone_drift`, Service `meteoalarm_feed:<Land>`,
  `unknown_zone`); dann `geocodes.json` neu ziehen und mit denselben Parametern neu bauen.
- **Verwendung:** `meteoalarm_feed._zones_for_point("PT"|"NL"|"PL", …)` für `covers()` UND `fetch()` von
  `MeteoAlarmFeedSource("PT"/"NL"/"PL")` (gemeinsamer Zonenweg `_fetch_zones` mit FI/ES).
