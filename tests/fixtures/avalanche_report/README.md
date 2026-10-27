# Fixtures: amtlicher Lawinen-Lagebericht (avalanche.report, CAAML v6)

Spec: `docs/specs/modules/avalanche_report_bulletin.md` (Issue #1441 Slice 1, Epic #2258)

Aufgezeichnet am **2026-10-13** per echtem HTTP-Abruf (ausserhalb von pytest, Redirect
`static.avalanche.report` -> `avalanche.report` gefolgt, Rohbytes unveraendert).
Pytest selbst ruft nie das Netz (autouse-Egress-Guard).

## Lizenz

- Bulletins: **CC BY 4.0** (Euregio Tirol-Suedtirol-Trentino, Lawinenwarndienst Kaernten;
  Namensnennung + Link zur Quelle). Es sind **nur** Euregio- und Kaernten-Dateien eingecheckt --
  keine Salzburg-/Bayern-Daten (Lizenz ungeklaert).
- Regionen-Geometrie (`regions/`): **CC0** (EAWS-Regions, `regions.avalanches.org`, nur `latest/`).

## ECHT (unveraendert aufgezeichnet)

| Datei | Quelle (URL) | Zweck |
|---|---|---|
| `bulletins/2026-01-30_AT-07_de_CAAMLv6.json` | `static.avalanche.report/bulletins/2026-01-30/2026-01-30_AT-07_de_CAAMLv6.json` | AC-1: Stufe 3 (`considerable`) oberhalb 2200 m, Bulletin `a6fb47953b5d` (u. a. AT-07-28) |
| `bulletins/2026-02-19/20/21_AT-07_de_CAAMLv6.json` | dto., Tage 19./20./21.02. | AC-12: Stufe 4 (`high`) oberhalb Waldgrenze an drei aufeinanderfolgenden Tagen (Region AT-07-25), Gueltigkeitsfenster beruehren sich (je 16:00Z) |
| `bulletins/2026-02-26_AT-07_de_CAAMLv6.json` | dto. | AC-2: Gleichstand der hoechsten Stufe in zwei Ratings mit unterschiedlicher Hoehenangabe (`earlier` ab Waldgrenze, `later` ohne Hoehe) |
| `bulletins/2026-03-01_AT-07/AT-02/IT-32-BZ/IT-32-TN_de_CAAMLv6.json` | dto. | Winter-Bulletins aller vier Eintraege der Konfigurationstabelle; AT-02 enthaelt Stufe 1 (`low`) in AT-02-05-02 |
| `bulletins/2026-04-06_AT-07_de_CAAMLv6.json` | dto. | AC-2: `later`-Rating mit eigenem Hoehensplit und hoeherer Stufe als `earlier` (Bulletin `5c52fdb0a96e`, u. a. AT-07-20: Stufe 3 **unterhalb** 2200 m am Nachmittag) |
| `bulletins/2026-05-02_AT-07_de_CAAMLv6.json` | dto. | AC-4: Mai-Bulletin, `validTime.endTime` = 2026-05-02T15:00Z (am 2026-10-13 abgelaufen) |
| `bulletins/latest_AT-07_recorded_2026-10-13.json` | `static.avalanche.report/bulletins/latest/AT-07_de_CAAMLv6.json` | die echte Antwort von `latest/` am Aufzeichnungstag: HTTP 200, aber `endTime` = **2026-05-03T15:00Z** (nicht 05-02) |
| `404_latest_AT-02.json` | `.../bulletins/latest/AT-02_de_CAAMLv6.json` | AC-5: echte 404-Antwort (Status, Header, leerer Body) fuer ein Land ohne Bulletin ausser Saison |
| `regions/{AT-07,IT-32-BZ,IT-32-TN,AT-02}_micro-regions.geojson.json` | `regions.avalanches.org/micro-regions/latest/{X}_micro-regions.geojson.json` | Regionen (CRS84 MultiPolygon, `properties.id`). **Entscheidung:** /40 legt sie NUR hier ab; /50 kopiert sie byte-identisch nach `src/services/official_alerts/data/avalanche_regions_{X}.geojson.json` |

## ABGELEITET (minimal veraendert, NICHT echt) -- Ordner `derived/`

Jede Datei ist eine Kopie von `bulletins/2026-02-20_AT-07_de_CAAMLv6.json` (echt) mit
**genau einem** geaenderten Feldwert. Kein anderes Feld wurde angefasst.

| Datei | Geaenderte Felder | Grund |
|---|---|---|
| `2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json` | im Bulletin der Region AT-07-25 (`bulletinID` unveraendert): jedes `dangerRatings[].mainValue == "high"` -> `"very_high"` | Stufe 5 kam in keiner der ~100 gescannten Winterdateien vor (Dez 2025 - Apr 2026) |
| `2026-02-20_AT-07_de_CAAMLv6_DERIVED_border_2_4.json` | im Bulletin der Region AT-07-04-02: jedes `mainValue == "considerable"` -> `"moderate"` (AT-07-16 bleibt echt `high`) | Grenzpunkt-Paar mit Stufe 2 / Stufe 4 (echt waere 3 / 4) |
| `2026-02-20_AT-07_de_CAAMLv6_DERIVED_border_4_4.json` | im Bulletin der Region AT-07-04-02: jedes `mainValue == "considerable"` -> `"high"` | Gleichstand 4 / 4 am Grenzpunkt (Tie-Break kleinste Regions-ID) |

### Nachtrag #1441 Fix-Loop 1 (Adversary F004)

Basis ist hier das **Bulletin der Region AT-07-05** aus `bulletins/2026-03-01_AT-07_de_CAAMLv6.json`
(echt, Bulletin `121dcdb3…`, unveraendert ausgeschnitten -- die uebrigen Bulletins des Tages sind
weggelassen) mit **genau einem** geaenderten Feldwert:

| Datei | Geaenderte Felder | Grund |
|---|---|---|
| `derived/2026-03-01_AT-07_de_CAAMLv6_DERIVED_no_rating.json` | `dangerRatings[0].mainValue`: `"moderate"` -> `"no_rating"` (im CAAML-Schema erlaubter Wert ohne EAWS-Stufe) | `no_rating` wird verworfen statt als Absturz behandelt: Stufe 3 bleibt, kein falsches "nicht abrufbar" |
| `derived/defekt/2026-03-01_AT-07_de_CAAMLv6_DERIVED_kaputte_endzeit.json` | `validTime.endTime`: `"2026-03-01T16:00:00Z"` -> `"kein-zeitpunkt"` | Auswertungsfehler nach erfolgreichem Abruf -> sichtbar "nicht abrufbar" (`mark_fetch_incomplete`) |

**SYNTHETISCH (nicht aufgezeichnet):** `derived/defekt/kein_caaml.json` -- gueltiges JSON ohne
`bulletins`-Liste (Wartungsantwort). Beweist: eine Antwort, die kein CAAML-Dokument ist, ist ein
Ausfall ("nicht abrufbar"), keine stille Leere.

Die Dateien unter `derived/defekt/` liegen bewusst in einem Unterordner: sie sind absichtlich
unparsbar und gehoeren nicht in die Eigenschaftspruefung "jede Region jeder Fixture wird geparst"
(`test_avalanche_report_parser.py`, globbt nur `derived/*.json`).

## Grenzpunkt (AC-9)

Die Mikroregionen `AT-07-04-02` und `AT-07-16` grenzen aneinander. Der Punkt
`lat=47.38545333996563, lon=11.770177360497602` ist ein echter Eckpunkt der gemeinsamen Kante und liegt
nach `services.official_alerts.geo_ray_cast._point_in_ring` in **beiden** Polygonen (die Geometrien
ueberlappen nicht in der Flaeche; ein Grenzpunkt ist per Definition so ein Randpunkt). Die Testdatei
prueft diese Voraussetzung selbst, damit ein Fixture-Fehler nicht als Mapper-Fehler erscheint.
Echte Stufen am 2026-02-20: AT-07-04-02 = 3, AT-07-16 = 4.

## Pruefpunkte (innere Punkte, je genau EINE Mikroregion)

| Punkt | lat, lon | Region |
|---|---|---|
| Tirol, AC-1 | 46.9394, 12.6844 | AT-07-28 (liegt zugleich in der Bounding-Box von AT-02) |
| Tirol, Stufe 4 | 46.9599, 12.4007 | AT-07-25 |
| Tirol, Splitt | 46.8831, 10.8102 | AT-07-20 |
| Tirol, Waldgrenze Stufe 3 | 47.4987, 11.7957 | AT-07-05 |
| Kaernten, Stufe 1 | 46.8947, 14.1901 | AT-02-05-02 |
| Suedtirol | 46.4266, 11.2584 | IT-32-BZ-16 |
| Trentino | 46.3281, 11.5104 | IT-32-TN-09 |
| ausserhalb (Bounding-Box ja, Polygon nein) | 47.3257, 12.7953 | Zell am See -- keine Region |
