# Context: feat-1442-s3b-meteoalarm-uk

## Request Summary
#1442 Teil S3b: MeteoAlarm-Feed fuer das Vereinigte Koenigreich (GB + Nordirland) als amtliche Warnquelle anbinden. Vorarbeit: `docs/context/feat-1442-s3-rest-eu.md` (Messung 2026-10-30: `feeds-united-kingdom` 200, 25 KB, 3 Warnungen, nur Polygone, kein Geocode, nur `en-GB`).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/official_alerts/meteoalarm_feed.py` | `_FEED_PATHS` (:57), `_POLYGON_COUNTRIES` (:387), `_nordic_outlines` (:386), `_in_outline` (:528), `_covers_polygon` (:535), `Literal` im Konstruktor (:566), `covers()`/`fetch()` Polygon-Verzweigung (:606, :617) |
| `src/services/official_alerts/__init__.py` (:40-41) | Registrierung der Laenderquellen; UK dort ergaenzen (Reihenfolge: zuerst registriert gewinnt) |
| `src/services/official_alerts/data/meteoalarm_outlines_nordics.geojson.json` | Vorbild Landesumriss NO/SE (Natural Earth, +0,1 Grad Puffer, simplify 0,01) |
| `src/services/official_alerts/data/README.md` | Herkunft/Lizenz jeder Datendatei; neuer Abschnitt fuer UK-Umriss noetig |
| `docs/specs/modules/feat_1442_s2_meteoalarm_nordics.md` | Vorlage Polygonweg NO/SE |
| `docs/specs/modules/feat_1442_s3a_meteoalarm_pt_nl_pl.md` | juengste Spec, Out-of-Scope-Abschnitt grenzt UK explizit als S3b ab |

## Existing Patterns
- Polygonweg: `covers()` = lokaler Landesumriss (bewusst aufgeweitet, lieber zu gross), Fallback Punkt in gecachtem Feed-Polygon; `fetch()` = Punkt-in-Polygon gegen Feed-Gebiete, Update/Cancel ersetzen Vorgaenger, Hoehenband ignoriert, unlesbare Polygone -> `mark_fetch_incomplete()`.
- Umrissdatei `…_nordics…` ist an NO/SE gebunden; fuer UK eigene Datei (`meteoalarm_outlines_UK`) statt Umbenennung (Umbenennung beruehrt README + Tests).
- Sprache: Mapper nimmt `de*`, sonst `en*`; UK liefert nur `en-GB`.

## Dependencies
- Upstream: Natural-Earth-Umriss (gemeinfrei, 5.1.1, ADM0_A3 = GBR), `RegionMapper`, geteilter Feed-Cache/`warn_egress`.
- Downstream: alle Kanaele (Trip- und Ortsvergleich-Briefing, Alarme) ueber die geteilte Quellenaufloesung; Egress-Host bleibt derselbe MeteoAlarm-Host (kein neuer Host).

## Existing Specs
- `docs/specs/modules/feat_1442_s3a_meteoalarm_pt_nl_pl.md` (Out of Scope: UK, Belgien nicht registriert)

## Risks & Considerations
- Natural Earth GBR enthaelt Nordirland; Irland (IE) ist nicht im Scope. Der Umriss steuert nur `covers()`, Treffer entstehen erst durch Punkt-in-Feed-Polygon.
- Kanalinseln / Isle of Man gehoeren nicht zu GBR im Datensatz; bewusst nicht abgedeckt (in Spec festhalten).
- Nur 3 Warnungen im Feed zum Messzeitpunkt: Live-Nachweis mit echter Warnung kann ausbleiben (wie bei PT/NL) -> Fixture aus echtem Feed noetig.
- Umriss muss auch Schottlands Inseln (Shetland, Hebriden) abdecken; kein Schwerpunkt-Filter wie bei Nordics.
- Bekannte Einschraenkung #2696 (Live-Test-Selektor ignoriert Nebel) betrifft den Live-Test-Nachweis.
- Groesse: Prod ca. +30 LoC + Umrissdatei, Tests ca. +120 LoC.

## Analysis

### Type
Feature (Slice S3b von Epic #1442: MeteoAlarm Vereinigtes Königreich)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS["GB"]` = `/api/v1/warnings/feeds-united-kingdom`; `"GB"` in `_POLYGON_COUNTRIES`; eigener Umriss-Mapper `_uk_outline` + `_in_outline()`-Zweig; `Literal` im Konstruktor um `"GB"` ergänzen |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(MeteoAlarmFeedSource("GB"))` nach PL, vor DpcSource (Tie-Break „zuerst registriert gewinnt“); Kommentar |
| `src/services/official_alerts/data/meteoalarm_outlines_uk.geojson.json` | CREATE | Natural Earth 5.1.1, `ADM0_A3 = GBR`, `properties.id = "GB"`, +0,1° Puffer, simplify 0,01 |
| `src/services/official_alerts/data/README.md` | MODIFY | Abschnitt Herkunft/Lizenz/Umfang des UK-Umrisses (Muster Nordics) |
| `tests/fixtures/meteoalarm_feed/feed_uk_sample.json` | CREATE | gekürzter echter Feed (Messung 2026-10-30) |
| `tests/tdd/test_meteoalarm_feed_uk.py` (+ ggf. `_live`) | CREATE | Kern-Tests (Grenzpunkte, Update/Cancel, unlesbares Polygon, Sprache en) und Live-Test mit Skip bei fehlender Warnung |
| `docs/specs/modules/feat_1442_s3b_meteoalarm_uk.md` | CREATE | Spec (Phase 3) |

### Scope Assessment
- Files: 4 Produktiv-/Datendateien + Tests + Spec
- Estimated LoC: Prod +30/-0 (ohne Umrissdatei), Tests ca. +120
- Risk Level: LOW — additive Quelle auf dem bestehenden Polygonweg (CH/NO/SE); kein neuer Egress-Host; kein Mail-/UI-Pfad geändert (kein Mail-Validator).

### Technical Approach
Länderkürzel **`GB`** (ISO-Code, passt zu `ADM0_A3`-Mapping und zu den anderen Kürzeln). Polygonweg wiederverwenden: `covers()` = lokaler, bewusst aufgeweiteter Landesumriss, Fallback Punkt in gecachtem Feed-Polygon; `fetch()` = Punkt-in-Polygon gegen Feed-Gebiete. Eigene Umrissdatei statt Umbenennung der Nordics-Datei (Umbenennung würde README und Tests berühren). `_in_outline()` bekommt einen `GB`-Zweig auf den neuen Mapper. Kein Schwerpunkt-Filter (anders als Nordics): Shetland, Hebriden und Nordirland müssen drin sein. Sprache: UK liefert nur `en-GB`, der bestehende Mapper fällt auf `en*` zurück — kein Code nötig, aber per Test belegen. Kanalparität: geteilte Quellenauflösung ⇒ alle vier Kanäle (Trip/Ortsvergleich, Briefing und Alarme) bekommen UK ohne weitere Verdrahtung.

### Dependencies
- Upstream: Natural-Earth-Umriss (gemeinfrei), `RegionMapper`, geteilter Feed-Cache und `warn_egress`.
- Downstream: Quellenauflösung für alle Kanäle; Nationalquellen überlappen UK nicht (an Grenzpunkten zu Irland/Frankreich liefert jede Quelle nur Warnungen ihres eigenen Feed-Polygons).
- Reihenfolge: PR #2702/#2703 sind gemerged; S3a (PT/NL/PL) live, S3c (BE) folgt separat.

### Open Questions
- [x] Kürzel GB statt UK — entschieden (ISO).
- [x] Kanalinseln / Isle of Man nicht in GBR — bewusst nicht abgedeckt, in Spec festhalten.
- [x] Irland (IE) nicht im Scope; Umriss steuert nur `covers()`, Treffer entstehen erst durch Punkt-in-Feed-Polygon.
- [ ] Live-Nachweis mit echter Warnung kann ausbleiben (nur 3 Warnungen im Feed, wie PT/NL) ⇒ Fixture aus echtem Feed ist Pflicht; Live-Test darf bei fehlender Warnung skippen (Einschränkung #2696 zum Nebel-Selektor im Abschlusskommentar nennen).
