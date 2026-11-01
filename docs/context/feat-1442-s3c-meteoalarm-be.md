# Context: feat-1442-s3c-meteoalarm-be

## Request Summary
#1442 Slice S3c: MeteoAlarm-Feed Belgien (`feeds-belgium`) als amtliche Warnquelle anbinden. Der Feed mischt je Warnung genau eine Kennung: 50 Warnungen nur `NUTS2` (Provinzen BE21…BE35), 11 nur `EMMA_ID`. Vorarbeit: `docs/context/feat-1442-s3-rest-eu.md` (Messung 2026-10-30: 200, 240 KB, 61 Warnungen, Sprachen nl-BE, fr-BE, de-DE, en-GB).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/meteoalarm_feed.py` | `_FEED_PATHS` (:57), `_GEOCODE_NAME` (:79, heute str je Land), `_emma_ids_for_alert` (:223), `_area_desc` (:183), `_alerts_for_zone` (:311, Zweig "Zonenzugehörigkeit nicht bestimmbar" → `mark_fetch_incomplete`), `_zone_mappers` (:394, Länder FI/ES/PT/NL/PL), `_zones_for_point`/`_known_zones` (:552/558), `_log_unknown_zone_drift` (:239), `_fetch_zones` (:689), Konstruktor-`Literal` |
| `src/services/official_alerts/__init__.py` (:65-70) | Registrierung; BE ist dort ausdrücklich NICHT registriert; neue Zeile nach GB, vor DpcSource |
| `src/services/official_alerts/data/README.md` | Herkunft/Lizenz je Datendatei; Abschnitt für BE-Geometrie nötig |
| `src/services/official_alerts/data/meteoalarm_zones_{NL,PL,...}.geojson.json` | Vorlage Zonengeometrie (`properties.id`, `properties.name`) |
| `docs/specs/modules/feat_1442_s3a_meteoalarm_pt_nl_pl.md` (Out of Scope, :305) | benennt S3c, fordert zweite Geometriequelle (GISCO NUTS-2021) und Mehrfach-Kennung, Lizenz vorab prüfen |
| `tests/tdd/test_meteoalarm_feed_pt_nl_pl*.py`, `tests/fixtures/meteoalarm_feed/` | Vorbild für Kern-/Live-Tests und Fixtures |

## Existing Patterns
- Zonenweg: Punkt → `RegionMapper.regions_at` → Menge `EMMA_ID` → `_alerts_for_zone(feed, zones, country, superseded)`; Update/Cancel ersetzen Vorgänger (S3a AC-7); keine Zone → `mark_not_covered`.
- Registrierung "zuerst registriert gewinnt" (#1427 S2); jede Quelle liefert nur Zonen des eigenen Landes → keine Doppelanzeige.
- Geometrie-Build: `geocodes.json` → vereinfachte GeoJSON (Puffer 0,05°, simplify 0,005), Build-Skript im README dokumentiert.

## Dependencies
- Upstream: MeteoAlarm-Feed (gleicher Egress-Host, kein neuer Host), `RegionMapper`, `warn_egress`, geteilter Feed-Cache (30 min TTL).
- Downstream: alle vier Kanäle über die geteilte Quellenauflösung (Trip-/Ortsvergleich-Briefing und Alarme); ein Kanal-Verdrahtungsschritt entfällt.

## Existing Specs
- `feat_1442_s3a_meteoalarm_pt_nl_pl.md`, `feat_1442_s3b_meteoalarm_uk.md`, `feat_1442_s2_meteoalarm_nordics.md` (Vorlagen)

## Risks & Considerations
- **Dauer-Fehlalarm ohne NUTS2-Geometrie:** NUTS2-only-Warnungen fallen in den Zweig "nicht bestimmbar" → jede belgische Abfrage "nicht abrufbar". Deshalb bisher nicht registriert.
- **Mehrfach-Kennung:** `_GEOCODE_NAME` muss von str auf Menge (EMMA_ID + NUTS2) erweitert werden; betrifft `_emma_ids_for_alert`, `_area_desc`, Drift-Wächter. Alle anderen Länder müssen unverändert bleiben (Regression NL/PL/ES/IT/AT/DE).
- **Lizenz:** Eurostat GISCO NUTS-2021 Level 2 (Attribution © EuroGeographics) vor Freigabe prüfen; zusätzlich bleibt die `geocodes.json`-Lizenz (PO-Thema) offen.
- **Zonenkonsistenz:** 8 NUTS2- und 2 EMMA-Zonen im Feed (BE004, BE801 EMMA). Beide Geometrien müssen zusammen jeden belgischen Punkt abdecken, sonst Lücken; Nordsee-Zone (BE801) beachten.
- **Grenzüberlappung** BE/NL, BE/DE, BE/FR/LU: `covers()` kann für zwei Länder wahr sein; Grenzpaar-Tests nötig, keine Doppel-Warnung.
- **Live-Nachweis** kann ausbleiben (SKIP bei fehlender aktiver Warnung wie PT/NL/UK) → Fixture aus echtem Feed; Selektor-Bug #2696 (Nebel) betrifft Live-Test.
- Größe: Prod ca. 60 LoC + Datei, Tests ca. 150 LoC; kein Mail-/UI-Pfad geändert (kein Mail-Validator).

## Analysis

### Type
Feature (Länder-Erweiterung, kein Bug).

### Messung 2026-10-31 (Live-Feed + GISCO)
- `feeds-belgium`: 200, 152 KB, 38 Warnungen; je Warnung genau eine Kennungsart: 30× nur `NUTS2` (BE21, BE22, BE23, BE25, BE32, BE34 in dieser Momentaufnahme), 8× nur `EMMA_ID` (BE004, BE801).
- GISCO NUTS-2021 Level 2 (1:1M, EPSG:4326): erreichbar (200, 18 MB); Belgien = 11 Regionen BE10, BE21–BE25, BE31–BE35 (BE10 Brüssel, BE24, BE31, BE33, BE35 kamen im Feed bisher nicht vor, müssen aber geometrisch vorhanden sein).
- Kein Build-Skript im Repo (`build_zones.py` nur im README beschrieben, Parameter 0,05° Puffer / 0,005 simplify) → Build für BE nachvollziehbar dokumentieren.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS["BE"]`; `_GEOCODE_NAME` von `str` auf Tupel/Menge (BE: `EMMA_ID`+`NUTS2`, übrige Länder unverändert); `_emma_ids_for_alert`, `_area_desc`, `_alerts_for_zone`, Drift-Wächter auf Mehrfach-Kennung; `_zone_mappers` + `"BE"`; `Literal` |
| `src/services/official_alerts/__init__.py` | MODIFY | Registrierung BE (nach GB, vor DpcSource) |
| `src/services/official_alerts/data/meteoalarm_zones_BE.geojson.json` | CREATE | Zonen: 11 NUTS2 (GISCO) + BE004/BE801 (aus `geocodes.json`); `properties.id` = Kennung |
| `src/services/official_alerts/data/README.md` | MODIFY | Herkunft/Lizenz/Build/Prüfpunkte für BE (Attribution © EuroGeographics) |
| `docs/specs/data_sources.md` | MODIFY | PENDING-Antrag S3c + Lizenzvermerk |
| `tests/fixtures/meteoalarm_feed/feed_belgium_sample.json` | CREATE | Auszug aus echtem Feed (beide Kennungsarten) |
| `tests/tdd/test_meteoalarm_feed_be*.py` | CREATE | Kern-/Live-Tests |
| `docs/specs/modules/feat_1442_s3c_meteoalarm_be.md` | CREATE | Spec (Phase 3) |

### Scope Assessment
- Files: 8 (davon 3 Prod-Code/Daten)
- Estimated LoC: Prod ca. +60/-10, Tests ca. +150, Datendatei neu
- Risk Level: MEDIUM — Mehrfach-Kennung berührt den gemeinsamen Zonenweg aller Zonenländer (Regression ES/FI/PT/NL/PL/DE nötig)

### Technical Approach
1. `_GEOCODE_NAME[country]` → Tupel von `valueName`; `_emma_ids_for_alert` sammelt über alle Namen. Für IT/AT/FI/ES/PT/NL/PL/DE bleibt das Ein-Element-Tupel → bitgleiches Verhalten (Regressionstests).
2. Zonengeometrie BE: NUTS2-Polygone (GISCO) und BE004/BE801 in EINER Datei, `properties.id` = jeweilige Kennung; `regions_at(lat,lon)` liefert die Menge (Provinz-NUTS2 + ggf. EMMA-Zone). Pipeline gleich NL/PL (Puffer 0,05°, simplify 0,005).
3. Bevor die Datei gebaut wird: BE004/BE801 in `geocodes.json` nachschlagen (Name/Lage); falls BE004 = Land-/Küsten-Teilgebiet, das NUTS2 überlappt, Doppelzählung vermeiden (`_alerts_for_zone` zählt je Warnung einmal — bereits abgesichert).
4. Drift-Wächter: unbekannte Kennung aus BEIDEN Namen → `log_zone_drift`; BE10 ohne Feed-Vorkommen ist unkritisch.
5. Registrierung erst, wenn Abdeckungstest (jeder belgische Punkt trifft ≥1 Zone, inkl. Nordsee/Küste) grün ist — sonst Dauer-Fehlalarm "nicht abrufbar".

### Dependencies
- Gleicher Egress-Host (`feeds.meteoalarm.org`), kein neuer Host; `RegionMapper`, `warn_egress`, geteilter 30-min-Feed-Cache.
- Downstream: alle vier Kanäle über die geteilte Quellenauflösung; keine Kanal-Verdrahtung, kein Mail-/UI-Pfad (kein Mail-Validator).
- Grenzfälle: BE/NL (Maastricht/Baarle), BE/DE (Eupen/Aachen), BE/FR/LU — "zuerst registriert gewinnt", jede Quelle liefert nur Zonen des eigenen Landes.

### Open Questions
- [ ] Lizenz GISCO NUTS (© EuroGeographics, Attribution/Weiterverwendung erlaubt?) — vor Freigabe in Spec/README belegen; `geocodes.json`-Lizenz bleibt offenes PO-Thema (bestehender gebündelter Antrag), kein neuer PO-Entscheid nötig.
- [ ] Was sind BE004 und BE801 (Name/Lage in `geocodes.json`)? In Phase 3/4 per Download klären (39 MB).
- [ ] Live-Nachweis kann SKIP sein (keine aktive Warnung) → Fixture aus echtem Feed trägt den Kern-Nachweis.

## Korrektur Phase 3 (2026-10-31) — GISCO verworfen, EMMA-Weg mit Zuordnungstabelle

**Lizenz GISCO (gemessen):** ec.europa.eu/eurostat/web/gisco/geodata/administrative-units: Nutzung nur unter der Bedingung „the data will not be used for commercial purposes"; Attribution „© EuroGeographics for the administrative boundaries". Für ein Multi-User-Produkt nicht tragbar ⇒ **GISCO wird nicht eingecheckt** (die Entscheidung aus „Technical Approach" Punkt 2 entfällt).

**Neuer Ansatz:** `geocodes.json` (gleiche Quelle/sha256 `0c8fe7b9…5dd0` wie FI/ES/PT/NL/PL, gleicher gebündelter Lizenzantrag) enthält für BE zehn `EMMA_ID`-Zonen: BE001 Luxembourg, BE002 Antwerpen, BE003 Oost Vlaanderen, BE004 Brabant, BE005 Hainaut, BE006 Namur, BE007 Limburg, BE008 Liege, BE009 West Vlaanderen, BE801 (Küstenstreifen, Wasser). Der Feed sendet NUTS2 für acht Provinzen und `EMMA_ID` nur für BE004 (= Brüssel + Vlaams-Brabant + Brabant Wallon) und BE801. Zuordnung NUTS2→EMMA per Tabelle: BE21→BE002, BE22→BE007, BE23→BE003, BE25→BE009, BE32→BE005, BE33→BE008, BE34→BE001, BE35→BE006, BE10/BE24/BE31→BE004. Namensabgleich Feed-`areaDesc` (nl-BE/en-GB) gegen `geocodes.json`: stimmig.

**Messung Feed 2026-10-31:** 38 Warnungen (24 Alert, 14 Update), Sprachen de-DE/en-GB/fr-BE/nl-BE; Kennungen NUTS2 BE21/22/23/25/32/34, EMMA BE004/BE801.

**Geometriegüte EMMA vs. GISCO (nur Build-Zeit-Vergleich, nichts eingecheckt):** Flächenübereinstimmung je Provinz 85–97 %; Gitterprüfung (0,01°) über 38 977 belgische Landpunkte: roh 945 Lücken (2,4 %), mit 0,05° Aufweitung 124 (0,3 %), mit 0,1° Aufweitung 12 (0,03 %). Arlon liegt roh in keiner Zone, mit Aufweitung in BE001. Brüssel, Leuven, Wavre roh in BE004; Ostende/Knokke/Küste 5 km in BE801; Nordsee 30 km vor der Küste in keiner Zone (BE801 reicht bis 51,65°N, 2,43–3,36°E).
