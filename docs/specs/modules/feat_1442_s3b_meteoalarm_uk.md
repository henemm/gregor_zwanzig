---
entity_id: feat_1442_s3b_meteoalarm_uk
type: feature
created: 2026-10-31
updated: 2026-10-31
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, united-kingdom, polygon, outline, warn-egress]
workflow: feat-1442-s3b-meteoalarm-uk
---

<!-- Issue #1442, Slice S3b (Vereinigtes Königreich). S1 (CH), S2 (NO/SE/FI) und S3a (PT/NL/PL) sind live. S3c (BE) folgt separat. Vorlagen: feat_1442_s2_meteoalarm_nordics.md (Polygonweg), feat_1442_s3a_meteoalarm_pt_nl_pl.md. Analyse: docs/context/feat-1442-s3b-meteoalarm-uk.md. -->

# MeteoAlarm Vereinigtes Königreich über den kontingentfreien Feed

## Approval

- [ ] Approved

## Purpose

Punkte in England, Schottland, Wales und Nordirland bekommen heute keine amtlichen Unwetterwarnungen.
Diese Spec registriert `MeteoAlarmFeedSource("GB")` und bezieht die Warnungen aus dem
kontingentfreien Feed `feeds.meteoalarm.org` (`feeds-united-kingdom`). Der UK-Feed trägt ausschließlich
Polygone (kein Geocode, keine Zonenkennung) und läuft deshalb über den bestehenden Polygonweg
(wie CH/NO/SE): `covers()` prüft einen lokalen, bewusst aufgeweiteten Landesumriss, `fetch()` prüft
Punkt-in-Polygon gegen die Warngebiete des Feeds. Es gibt keinen neuen Algorithmus, nur Konfiguration,
eine Umrissdatei und die Registrierung.

Messung 2026-10-30 (live): `feeds-united-kingdom` 200, 25 KB, 3 Warnungen, nur Polygone, kein Geocode,
nur Sprache `en-GB`.

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py` (MODIFY)
- **Identifier:** `_FEED_PATHS`, `_POLYGON_COUNTRIES`, `_uk_outline` (neu), `_in_outline()`,
  `MeteoAlarmFeedSource.__init__(country)` (`Literal`)

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`). Kein Go-, kein
> Frontend-Anteil. Der Host `feeds.meteoalarm.org` ist in `internal/egress/inventory.go` und
> `src/app/egress_guard.py` bereits geführt; kein neuer Host.

> **Mandantentrennung:** Keine Nutzerdaten im Pfad. Die Quelle ist global (Cache-Schlüssel =
> Ländercode, Eingang nur `lat`/`lon` eines beobachteten Orts). Ein Zwei-Nutzer-Test ist
> gegenstandslos (gleiche Begründung wie S1/S2/S3a); die Nutzerbindung geschieht im geteilten
> Alarm-Pfad.

> **Kanäle:** Alle vier (E-Mail, Telegram, SMS, Premium-SMS) ohne Sonderlogik, Trip UND
> Ortsvergleich, weil nur die Registry erweitert wird (Epic #2133, ADR-0095). Es entsteht kein
> Frontend- oder Editor-Baustein, daher kein Trip/Ortsvergleich-Pendant-Thema und kein Mail-Validator.

## Estimated Scope

- **LoC:** Produktiv ca. +30/-0 (Umrissdatei zählt nicht), Tests ca. +120
- **Files:** 4 Produktiv-/Datendateien, 1 Fixture, 1 Testdatei (plus Live-Test), Spec
- **Effort:** low. Risk: LOW (additive Quelle auf dem bestehenden Polygonweg, kein neuer Egress-Host)

### Affected Files (Scope)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS["GB"]` = `/api/v1/warnings/feeds-united-kingdom`; `"GB"` in `_POLYGON_COUNTRIES`; eigener Umriss-Mapper `_uk_outline` und `GB`-Zweig in `_in_outline()`; `Literal` im Konstruktor um `"GB"` ergänzt |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(MeteoAlarmFeedSource("GB"))` nach PL, vor `DpcSource`, mit Reihenfolge-Kommentar |
| `src/services/official_alerts/data/meteoalarm_outlines_uk.geojson.json` | CREATE | Natural Earth 5.1.1, `ADM0_A3 = GBR`, `properties.id = "GB"`, +0,1° Puffer, simplify 0,01 |
| `src/services/official_alerts/data/README.md` | MODIFY | Abschnitt Herkunft, Lizenz und Umfang des UK-Umrisses (Muster Nordics) |
| `tests/fixtures/meteoalarm_feed/feed_uk_sample.json` | CREATE | gekürzter echter Feed (Messung 2026-10-30) |
| `tests/tdd/test_meteoalarm_feed_uk.py` | CREATE | Kern-Verhaltenstests ohne Netz; Live-Test mit Marker `live` im selben Muster wie S3a |
| `src/services/official_alerts/meteoalarm.py` | REUSE | CAP-Mapper; Sprachwahl `de*` → `en*` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Natural Earth Admin-0 (5.1.1, gemeinfrei) | data | Quelle des Landesumrisses (`ADM0_A3 = GBR`) |
| `region_mapper.RegionMapper.regions_at` | module | Punkt → Umriss-Kennung |
| `warn_egress.cached_fetch` / `mark_fetch_incomplete` / `mark_not_covered` | module | Abruf, Drei-Zustände-Regel |
| `meteoalarm._group_and_map_info_entries` | module | geteilter CAP-Mapper |
| `base.get_official_alerts_with_status` | module | wertet `unavailable` über alle Quellen |
| Alarm-/Briefing-Pfade (`trip_alert`, `comparison_engine`, `compare_official_alert`, `trip_report_scheduler`) | module | konsumieren `OfficialAlert` unverändert |
| `docs/adr/0039`, `0041`, `0074`, `0090`, `0095` | adr | Feed-Weg, lokale Zuständigkeit, Auffrischraster, Entwarnung über Verschwinden, Kanalparität |

## Implementation Details

1. **Konfiguration.** Länderkürzel `GB` (ISO-Code, passend zu den übrigen Kürzeln). `_FEED_PATHS`
   erhält `GB` → `/api/v1/warnings/feeds-united-kingdom`; `"GB"` kommt in `_POLYGON_COUNTRIES`; der
   `Literal` im Konstruktor wird um `"GB"` ergänzt.
2. **Umriss.** Eigene Datei `meteoalarm_outlines_uk.geojson.json` (Natural Earth 5.1.1, gemeinfrei,
   `ADM0_A3 = GBR`, `properties.id = "GB"`) statt Umbenennung der Nordics-Datei (Umbenennung würde
   README und Tests berühren). Puffer +0,1°, Vereinfachung 0,01. Der Umriss enthält Großbritannien
   samt Nordirland und alle Inseln der Hauptpolygone (Shetland, Orkney, Hebriden); es gibt keinen
   Schwerpunkt-Filter wie bei den Nordics. `_in_outline()` bekommt einen `GB`-Zweig auf `_uk_outline`.
3. **Zuständigkeit.** `covers()` = Punkt im Umriss (bewusst zu groß), Fallback Punkt in einem
   gecachten Feed-Polygon. Der Umriss steuert nur `covers()`; ein Treffer entsteht erst durch
   Punkt-in-Feed-Polygon in `fetch()`. Irland (IE) liegt außerhalb des Umrisses und ist nicht im
   Scope; Nordirland ist enthalten.
4. **Warnungen.** `fetch()` wie CH/NO/SE: Punkt-in-Polygon gegen die Warngebiete, Höhenband
   ignoriert, `Update` und `Cancel` ersetzen ihre Vorgänger über `_referenced_ids`. Enthält der
   Feed keinen einzigen Eintrag mit lesbarem Polygon, markiert das den Abruf mit
   `mark_fetch_incomplete()`; ein einzelner kaputter Eintrag unter lesbaren färbt nicht jeden Ort
   als Ausfall (geteilte Polygonregel wie S1/S2). Entwarnung nur über Verschwinden
   (ADR-0090).
5. **Sprache.** Der Feed führt nur `en-GB`. Der Mapper nimmt `de*`, sonst `en*` und liefert `en-GB`;
   kein Code nötig, per Test belegt.
6. **Registrierung.** Nach PL, vor `DpcSource` (Gewitter-Tie-Break „zuerst registriert gewinnt",
   #1427 S2). Nationalquellen überlappen UK nicht; an Grenzpunkten zu Irland/Frankreich liefert jede
   Quelle nur Warnungen ihres eigenen Feed-Polygons.
7. **Kanalparität.** Die geteilte Quellenauflösung gibt UK-Warnungen an alle vier Kanäle (E-Mail,
   Telegram, SMS, Premium-SMS) in Trip und Ortsvergleich weiter, ohne weitere Verdrahtung.
8. **Budget.** Feed kontingentfrei, höchstens ein Abruf je 30 min (TTL 1800 s Erfolg / 60 s Fehler,
   Timeout unverändert).

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in oder nahe dem Vereinigten Königreich.
- **Output:** unverändert `list[OfficialAlert]` über `get_official_alerts_for_location()` /
  `get_official_alerts_with_status()`, `source` bleibt `"meteoalarm"`.
- **Side effects:** ein Feed-Abruf pro Auffrischungsfenster (30 min).

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht ohne Netz, Datei `tests/tdd/test_meteoalarm_feed_uk.py`, gegen die echte gekürzte
Feed-Probe `tests/fixtures/meteoalarm_feed/feed_uk_sample.json` (aus dem echten Feed vom 2026-10-30;
kein Mock-Theater). Fälle, die die Probe nicht enthält (`Update`, `Cancel`, unlesbares Polygon),
werden synthetisch aus einem echten Eintrag abgeleitet und im Fixture-README gekennzeichnet.
Testorte (lat, lon): London (51.51, -0.13), Edinburgh (55.95, -3.19), Lerwick/Shetland (60.15, -1.15),
Stornoway/Hebriden (58.21, -6.39), Belfast (54.60, -5.93), Cardiff (51.48, -3.18); außerhalb: Paris
(48.86, 2.35), Dublin-Mitte (53.35, -6.26).

- [ ] Test 1 (Feed-Pfad): `_FEED_PATHS["GB"]` ist `/api/v1/warnings/feeds-united-kingdom`.
- [ ] Test 2 (Zuständigkeit): `covers()` ist für London, Edinburgh, Lerwick, Stornoway, Belfast und
  Cardiff wahr, für Paris und Dublin-Mitte falsch (`mark_not_covered`, keine Warnung, kein
  Ausfallhinweis).
- [ ] Test 3 (Treffer): Ort innerhalb eines Warn-Polygons der Probe ⇒ genau diese Warnung mit Stufe,
  Ereignisart und Zeitraum; Ort außerhalb aller Polygone ⇒ leere Liste, `unavailable=False`.
- [ ] Test 4 (Update/Cancel): `Cancel` ⇒ nicht aktiv; `Update` ersetzt den Vorgänger ⇒ genau einmal.
- [ ] Test 5 (unlesbares Polygon): Feed ohne einen einzigen lesbaren Polygon-Eintrag ⇒
  `mark_fetch_incomplete()`, keine Warnung, `unavailable=True`; ein einzelner kaputter Eintrag unter
  lesbaren ⇒ gewarnter Ort behält seine Warnung, ruhiger Ort bleibt ruhig, beide `unavailable=False`.
- [ ] Test 6 (Sprache): Probe nur mit `en-GB` ⇒ Text aus `en-GB`, nicht leer.
- [ ] Test 7 (Registry): `GB` ist nach PL und vor `DpcSource` registriert; kein neuer Egress-Host.
- [ ] Test 8 (Umrissdatei): `meteoalarm_outlines_uk.geojson.json` ist nicht leer, trägt
  `properties.id = "GB"`; README-Abschnitt zur Herkunft ist vorhanden
  (`# doc-compliance-test` nur für die README-Prüfung).
- [ ] Test 9 (Alarmweg Ende-zu-Ende): Warnung der Alarmstufe aus der UK-Probe über die echte
  Registry bis zur Kanal-Auflösung eines Nutzers mit Empfängern auf allen vier Kanälen ⇒ E-Mail,
  Telegram, SMS, Premium-SMS wie bei einer AT-Warnung gleicher Stufe (Trip und Ortsvergleich).
- [ ] Test 10 (Regression): CH/NO/SE/FI/ES/PT/NL/PL-Feedtests laufen unverändert grün; die
  Reihenfolgeprüfung in den S3a-Tests akzeptiert die erweiterte Registry.
- [ ] Test 11 (Live, Marker `live`, nur `/e2e-verify`): aktuell gewarntes Gebiet aus dem echten Feed
  ⇒ mindestens 1 Warnung ohne Ausfall im Timeout; ohne gültige Warnung SKIP mit Grund, nicht PASS.

## Acceptance Criteria

- **AC-1:** Given die Konfiguration der Landesquelle `GB`, When der Feed-Pfad abgefragt wird, Then
  lautet er `/api/v1/warnings/feeds-united-kingdom` und es wird kein neuer Egress-Host benötigt.
  - Test: Tests 1 und 7.

- **AC-2:** Given ein Wanderpunkt liegt in England, Schottland, Wales oder Nordirland, auch auf
  Shetland, den Hebriden oder in Belfast, When die Zuständigkeit geprüft wird, Then ist die UK-Quelle
  zuständig; Given ein Punkt liegt in Paris oder in der Mitte von Dublin (Irland ist nicht im Scope),
  Then schweigt die Quelle folgenlos, ohne Warnung und ohne Ausfallhinweis.
  - Test: Test 2.

- **AC-3:** Given ein Wanderpunkt liegt im Polygon einer aktiven UK-Warnung, When die amtlichen
  Warnungen abgerufen werden, Then erscheint diese Warnung mit Warnstufe, Ereignisart und
  Gültigkeitszeitraum; Given der Punkt liegt außerhalb aller Warn-Polygone, Then meldet das Ergebnis
  „keine Warnung" und nicht „amtliche Warnungen nicht abrufbar".
  - Test: Test 3.

- **AC-4:** Given eine UK-Warnung wurde aufgehoben (`Cancel`) oder durch eine neuere Fassung ersetzt
  (`Update`), When die Warnungen abgerufen werden, Then erscheint die aufgehobene nicht als aktiv und
  die aktualisierte genau einmal, ohne die ersetzte Fassung zusätzlich.
  - Test: Test 4.

- **AC-5:** Given der UK-Feed enthält keinen einzigen Warn-Eintrag mit lesbarem Polygon, When die
  Warnungen für einen UK-Punkt abgerufen werden, Then meldet das Ergebnis „amtliche Warnungen
  aktuell nicht abrufbar" (`mark_fetch_incomplete`) statt fälschlich eine warnungsfreie Lage zu
  zeigen; Given nur ein einzelner Eintrag ist unlesbar und andere sind lesbar, Then behalten
  gewarnte Orte ihre Warnung und kein Ort wird als Ausfall gemeldet (wie S2).
  - Test: Test 5.

- **AC-6:** Given der UK-Feed führt nur Texte in `en-GB`, When die Warnung ausgegeben wird, Then ist
  ihr Text vorhanden und stammt über den Rückfall auf `en*` aus `en-GB`, nicht leer; ein Test belegt
  das ohne neuen Code.
  - Test: Test 6.

- **AC-7:** Given die Quellenregistrierung, When die Registry aufgebaut wird, Then steht
  `MeteoAlarmFeedSource("GB")` in `__init__.py` nach PL und vor `DpcSource`, die Quellen für
  CH/NO/SE/FI/ES/PT/NL/PL liefern unverändert dieselben Ergebnisse, und es entsteht kein neuer
  Egress-Host.
  - Test: Tests 7 und 10.

- **AC-8:** Given die Datenhaltung des Landesumrisses, When die Dateien geprüft werden, Then liegt
  `meteoalarm_outlines_uk.geojson.json` (Natural Earth 5.1.1, gemeinfrei, +0,1° Puffer, simplify 0,01,
  `properties.id = "GB"`) im Datenordner, und `data/README.md` dokumentiert Herkunft und Lizenz; die
  Kanalinseln und die Isle of Man sind bewusst nicht abgedeckt und dort so vermerkt.
  - Test: Test 8.

- **AC-9:** Given eine UK-Warnung erreicht die für Alarme maßgebliche Warnstufe, When sie den
  geteilten Alarm-Pfad eines Trip- oder Ortsvergleichs-Alarms durchläuft, Then erreicht sie bei der
  Kanal-Auflösung alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) wie eine österreichische
  Warnung derselben Stufe, ohne weitere Verdrahtung.
  - Test: Test 9.

- **AC-10:** Given der echte UK-Feed auf Staging und eine aktuell gewarnte Fläche, When die Quelle
  für einen Punkt darin abgefragt wird, Then liefert sie mindestens eine Warnung ohne Ausfallhinweis
  im Timeout; Given der Feed führt zum Zeitpunkt keine Warnung, Then ist das Ergebnis des Live-Tests
  ein SKIP mit Grund und kein Bestehen; die Kern-Tests stützen sich auf eine Fixture aus dem echten
  Feed.
  - Test: Test 11 (Live) sowie Fixture-Grundlage der Tests 3 bis 6.

## Abweichungen vom Ticket (#1442, Stand 31.07.)

- **Ticket-AC-2 (24h-Abrufbudget) gegenstandslos:** `feeds.meteoalarm.org` ist kontingentfrei, es
  gilt nur der 30-min-Cache (siehe S3a).
- **Bezugsweg Feed statt `api.meteoalarm.org`/MQTT** (ADR-0039).
- **Zuordnung:** UK per Polygon-Punkt-Test mit eigenem Landesumriss, nicht per Zonenkennung.
- **Zuschnitt:** Ticket-Slice S3 wird in S3a (PT, NL, PL), S3b (UK) und S3c (BE) zerlegt.

## Known Limitations

- **Höhenband ignoriert** (wie übrige Länder): lieber eine Warnung zu viel als zu wenig.
- **Umriss ist bewusst aufgeweitet:** `covers()` kann für Küstenpunkte knapp vor dem Land wahr sein;
  Folge höchstens ein Abruf mit „keine Warnung", nie eine Doppel-Warnung.
- **Kanalinseln und Isle of Man** gehören im Natural-Earth-Datensatz nicht zu `GBR` und sind
  bewusst nicht abgedeckt.
- **Dünne Live-Evidenz:** Im Feed standen zur Messung nur 3 Warnungen; ein Live-Nachweis mit echter
  Warnung kann ausbleiben (wie bei PT/NL). Deshalb ist die Fixture aus dem echten Feed Pflicht und
  der Live-Test darf mit SKIP enden.
- **#2696 (bekannt):** Der Live-Test-Selektor ignoriert Nebel-Warnungen; eine reine Nebelwarnung im
  UK-Feed wird vom Live-Selektor deshalb nicht als „gewarntes Gebiet" gewählt. Das betrifft nur den
  Live-Nachweis, nicht die Quelle selbst. Im Abschlusskommentar von #1442 zu nennen.
- **Entwarnung** nur über Verschwinden bei gesunder Quelle (ADR-0090).
- **Latenz:** EUMETNET-Weitergabe mit 5–10 min Verzug (Rahmen ADR-0074).

## Out of Scope

- **Belgien (S3c):** eigener Workflow (gemischte `EMMA_ID`/`NUTS2`-Kennungen); wird bis dahin nicht
  registriert.
- **Irland (IE):** nicht im Scope; Punkte in Irland werden nicht von der UK-Quelle beansprucht.
- **Kanalinseln und Isle of Man:** bewusst nicht abgedeckt (siehe Known Limitations).
- Höhenband-Auswertung, Teilflächen, neue Egress-Hosts, Änderung von TTL und Timeout.
- Behebung von #2696 (Nebel im Live-Selektor).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neu. Es gelten ADR-0039, 0041, 0074, 0090 und 0095 unverändert.
- **Rationale:** Ein weiteres Polygonland ist Konfiguration des bestehenden Polygonwegs, keine
  Grundsatzentscheidung.

## Changelog

- 2026-10-31: Initial spec created (Issue #1442 S3b, Analyse-Grundlage
  `docs/context/feat-1442-s3b-meteoalarm-uk.md`).
