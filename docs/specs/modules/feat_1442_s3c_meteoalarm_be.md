---
entity_id: feat_1442_s3c_meteoalarm_be
type: feature
created: 2026-10-31
updated: 2026-10-31
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, belgium, zone, emma-id, nuts2, warn-egress]
workflow: feat-1442-s3c-meteoalarm-be
---

<!-- Issue #1442, Slice S3c (Belgien). S1 (CH), S2 (NO/SE/FI), S3a (PT/NL/PL) und S3b (GB) sind live bzw. gespeichert. Vorlagen: feat_1442_s3a_meteoalarm_pt_nl_pl.md (Zonenweg), feat_1442_s3b_meteoalarm_uk.md. Analyse: docs/context/feat-1442-s3c-meteoalarm-be.md (Abschnitt "Korrektur Phase 3" hat Vorrang vor dem Analyse-Abschnitt). -->

# MeteoAlarm Belgien über den kontingentfreien Feed

## Approval

- [ ] Approved

## Purpose

Punkte in Belgien bekommen heute keine amtlichen Unwetterwarnungen. Diese Spec registriert
`MeteoAlarmFeedSource("BE")` und bezieht die Warnungen aus dem kontingentfreien Feed
`feeds.meteoalarm.org` (`feeds-belgium`). Der belgische Feed ist der erste, der je Warnung
**unterschiedliche Kennungsarten** mischt: die meisten Warnungen tragen nur `NUTS2` (Provinz-Code
wie `BE23`), einige nur `EMMA_ID` (`BE004`, `BE801`). Gelöst wird das ohne neue Geometriequelle:
Die Geometrie bleibt `geocodes.json` (zehn EMMA-Zonen), und eine kleine **Zuordnungstabelle NUTS2 →
EMMA_ID** übersetzt die NUTS2-Codes an der einen Stelle, an der die Kennungen einer Warnung
eingesammelt werden. Danach läuft alles über den bestehenden Zonenweg (wie FI/ES/PT/NL/PL).

Messung 2026-10-31 (live): `feeds-belgium` 200, 152 KB, 38 Warnungen (24 Alert, 14 Update),
Sprachen `de-DE`, `en-GB`, `fr-BE`, `nl-BE`. 30 Warnungen tragen nur `NUTS2` (BE21 28x, BE23 28x,
BE22 24x, BE25 16x, BE32 16x, BE34 8x Vorkommen), 8 nur `EMMA_ID` (BE004 und BE801 je 16x
Vorkommen). Keine Warnung trägt beide Arten.

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py` (MODIFY)
- **Identifier:** `_FEED_PATHS`, `_GEOCODE_NAME`, `_emma_ids_for_alert`, `_alerts_for_zone`,
  `_info_entries_from_alert`, `_zone_mappers`, `_log_unknown_zone_drift`, `_fetch_zones`,
  `MeteoAlarmFeedSource.__init__(country)` (`Literal`); neu: `_BE_NUTS2_TO_EMMA`

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`). Kein Go-, kein
> Frontend-Anteil. Der Host `feeds.meteoalarm.org` ist in `internal/egress/inventory.go` und
> `src/app/egress_guard.py` bereits geführt; kein neuer Host.

> **Mandantentrennung:** Keine Nutzerdaten im Pfad. Die Quelle ist global (Cache-Schlüssel =
> Ländercode, Eingang nur `lat`/`lon` eines beobachteten Orts). Ein Zwei-Nutzer-Test ist
> gegenstandslos (gleiche Begründung wie S1/S2/S3a/S3b); die Nutzerbindung geschieht im geteilten
> Alarm-Pfad.

> **Kanäle:** Alle vier (E-Mail, Telegram, SMS, Premium-SMS) ohne Sonderlogik, Trip UND
> Ortsvergleich, weil nur die Registry erweitert wird (Epic #2133, ADR-0095). Es entsteht kein
> Frontend- oder Editor-Baustein, daher kein Trip/Ortsvergleich-Pendant-Thema, kein Mail-Pfad und
> kein Mail-Validator.

## Estimated Scope

- **LoC:** Produktiv ca. +40/-5 (Daten zählen nicht), Tests ca. +150
- **Files:** 3 Produktiv-/Datendateien, 2 Dokumentationsdateien (`data/README.md`,
  `docs/specs/data_sources.md`), 1 Fixture (+README), 1 Testdatei, Anpassung vorhandener Tests, Spec
- **Effort:** low-medium. Risk: MEDIUM (die Übersetzung berührt den gemeinsamen Zonenweg aller
  Zonenländer; Regression ist deshalb Pflicht)

### Affected Files (Scope)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS["BE"]` = `/api/v1/warnings/feeds-belgium`; `_GEOCODE_NAME` für BE auf zwei Namen (`EMMA_ID`, `NUTS2`; übrige Länder ein Name, bitgleich); Tabelle `_BE_NUTS2_TO_EMMA` und Übersetzung nur für Land BE im Einsammeln der Kennungen (`_emma_ids_for_alert`-Pfad, Aufrufer in `_alerts_for_zone` und `_log_unknown_zone_drift`); `"BE"` in `_zone_mappers`; `Literal` im Konstruktor um `"BE"` ergänzt; Länder-Docstrings nachgezogen |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(MeteoAlarmFeedSource("BE"))` nach GB, vor `DpcSource`; Kommentar "Belgien (S3c) ist bewusst NICHT registriert" ersetzen |
| `src/services/official_alerts/data/meteoalarm_zones_BE.geojson.json` | CREATE | Auszug aus MeteoAlarm `geocodes.json`, 10 EMMA-Zonen, `properties.id` = EMMA_ID, `properties.name` = Name laut `geocodes.json`; Ziel < 400 KB |
| `src/services/official_alerts/data/README.md` | MODIFY | Abschnitt BE: Herkunft, sha256 von `geocodes.json`, Lizenz ungeklärt (gebündelter Antrag), Zonentabelle, Zuordnungstabelle NUTS2→EMMA, Aufweitung 0,1° samt Messwerten, Seezonen-Regel, Verzicht auf GISCO samt Lizenzbegründung, Drift-Hinweis |
| `docs/specs/data_sources.md` | MODIFY | BE in den gebündelten `geocodes.json`-Lizenzantrag; Vermerk "GISCO/NUTS nicht verwendet (nur nicht-kommerzielle Nutzung)" |
| `tests/fixtures/meteoalarm_feed/feed_belgium_sample.json` + `README.md` | CREATE/MODIFY | gekürzter echter Feed (2026-10-31), beide Kennungsarten und mindestens ein `Update`; synthetische Fälle gekennzeichnet |
| `tests/tdd/test_meteoalarm_feed_be.py` | CREATE | Kern-Verhaltenstests ohne Netz; Live-Test mit Marker `live` im selben Muster wie S3a/S3b |
| `tests/tdd/test_meteoalarm_feed_pt_nl_pl.py`, `tests/tdd/test_meteoalarm_feed_uk.py` (und weitere Tests mit der Annahme "BE nicht registriert") | MODIFY | Reihenfolge-/Registryprüfung akzeptiert die erweiterte Registry (BE nach GB, vor `DpcSource`); die Aussage "Belgien nicht registriert" wird gestrichen |
| `src/services/official_alerts/meteoalarm.py` | REUSE | CAP-Mapper; Sprachwahl `de*` → `en*` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| MeteoAlarm `geocodes.json` (Google-Drive-ID `16s24hYHfYQhKMNcP1hpgQmg13Yb8j0hV`, 39 256 854 Byte, sha256 `0c8fe7b9af4f86c72f1c28bb9cea02f673fee6d45d02681713e6ad3ebd615dd0`) | data | Quelle der Zonengeometrie, identisch zu FI/ES/PT/NL/PL |
| `region_mapper.RegionMapper.regions_at` | module | Punkt → Zonen-IDs |
| `warn_egress.cached_fetch` / `mark_fetch_incomplete` / `mark_not_covered` / `log_zone_drift` | module | Abruf, Drei-Zustände-Regel, Drift-Wächter |
| `meteoalarm._group_and_map_info_entries` | module | geteilter CAP-Mapper |
| `base.get_official_alerts_with_status` | module | wertet `unavailable` über alle Quellen |
| Alarm-/Briefing-Pfade (`trip_alert`, `comparison_engine`, `compare_official_alert`, `trip_report_scheduler`) | module | konsumieren `OfficialAlert` unverändert |
| `docs/adr/0039`, `0041`, `0074`, `0090`, `0095` | adr | Feed-Weg, lokale Zuständigkeit, Auffrischraster, Entwarnung über Verschwinden, Kanalparität |

## Implementation Details

1. **Konfiguration.** `_FEED_PATHS["BE"]` = `/api/v1/warnings/feeds-belgium`. `_zone_mappers`
   bekommt `"BE"` (Zonendatei `meteoalarm_zones_BE.geojson.json`). Der `Literal` im Konstruktor wird
   um `"BE"` ergänzt. `_GEOCODE_NAME` ist heute ein `str` je Land; für BE muss `EMMA_ID` UND `NUTS2`
   gelesen werden. Die Form (Tupel je Land mit einem Element für alle übrigen Länder, oder
   Sonderfall nur für BE) wählt der Developer; Bedingung ist, dass alle anderen Länder bitgleich
   dasselbe Ergebnis liefern (AC-12).
2. **Zonendatei.** Neue Datei `meteoalarm_zones_BE.geojson.json` mit den zehn EMMA-Zonen aus
   `geocodes.json`: BE001 Luxembourg, BE002 Antwerpen, BE003 Oost Vlaanderen, BE004 Brabant,
   BE005 Hainaut, BE006 Namur, BE007 Limburg, BE008 Liege, BE009 West Vlaanderen, BE801
   (Küstenstreifen, Wasser). `properties.id` = EMMA_ID, `properties.name` = Name laut
   `geocodes.json`. Landzonen werden um **0,1°** aufgeweitet (NL/PL: 0,05°; Begründung unten),
   Vereinfachung 0,005, vier Nachkommastellen. **Seezonen-Regel BE:** nur `BE801` ist Wasser und
   bleibt unverändert, nicht aufgeweitet (Umschlagrechteck 51,09-51,65°N, 2,43-3,36°E; das
   Polygon selbst ist kleiner: der Testpunkt Nordsee 30 km vor der Küste, 51,6/2,6, liegt
   gemessen in keiner Zone). Build wie im README
   (NL/PL): `uv run --no-project --with shapely python -I build_zones.py geocodes.json BE out.json
   0.1 0.005 4`. Zur Laufzeit wird nichts nachgeladen. Die Dateigröße bleibt unter 400 KB.
3. **Zuordnungstabelle NUTS2 → EMMA_ID** (`_BE_NUTS2_TO_EMMA`; Namensabgleich Feed-`areaDesc`
   gegen `geocodes.json` bestätigt):

   | NUTS2 | Provinz | EMMA_ID |
   |---|---|---|
   | BE21 | Antwerpen | BE002 |
   | BE22 | Limburg | BE007 |
   | BE23 | Oost-Vlaanderen | BE003 |
   | BE25 | West-Vlaanderen | BE009 |
   | BE32 | Hainaut | BE005 |
   | BE33 | Liège | BE008 |
   | BE34 | Luxembourg | BE001 |
   | BE35 | Namur | BE006 |
   | BE10 | Brüssel | BE004 |
   | BE24 | Vlaams-Brabant | BE004 |
   | BE31 | Brabant Wallon | BE004 |

   EMMA kennt nur das ungeteilte "Brabant" (BE004). Eine reine BE24- oder BE31-Warnung gilt daher
   auch in Brüssel und im jeweils anderen Brabant ("lieber eine Warnung zu viel", Known
   Limitations). BE10, BE24, BE31 und BE33/BE35 kamen im Feed bisher nie vor, sind aber über die
   Tabelle bekannt.
4. **Übersetzung nur für BE und nur an einer Stelle.** Dort, wo die Kennungen einer Warnung
   eingesammelt werden (`_emma_ids_for_alert`-Pfad), liest BE beide Namen; ein `NUTS2`-Wert wird
   über die Tabelle zur EMMA_ID, ein `EMMA_ID`-Wert bleibt, was er ist. Die Ergebnismenge ist eine
   Menge: hat eine Warnung z. B. `BE10` UND `BE004`, entsteht daraus einmal `BE004`, die Warnung
   zählt je Punkt weiterhin nur einmal. Alle anderen Länder (IT/AT/DE/FI/ES/PT/NL/PL sowie die
   Polygonländer CH/NO/SE/GB) laufen unverändert über ihren einen Namen ohne Tabelle. Dieselbe Einsammelfunktion speist den
   Drift-Wächter, damit Warnung und Wächter dieselbe Sicht haben. Der Mapper-Aufruf
   (`_info_entries_from_alert`) bekommt für BE keine Sonderbehandlung; der Developer prüft, dass
   sein `geocode_name`-Parameter dort mit zwei Namen nicht bricht.
5. **Unbekannter NUTS2-Code** (nicht in der Tabelle, z. B. ein künftiger Code): der rohe Code
   bleibt in der Kennungsmenge. Die Warnung gilt damit als "nachweislich eine andere Zone" und
   trägt NICHT zu `mark_fetch_incomplete` bei (sonst würde jede belgische Abfrage "nicht
   abrufbar"). Der Drift-Wächter loggt `unknown_zone` (Service `meteoalarm_feed:BE`). Bekannt für
   den Wächter sind: BE001-BE009, BE801 (Zonendatei) sowie alle Schlüssel der Tabelle (BE10, BE21,
   BE22, BE23, BE24, BE25, BE31-BE35).
6. **Drei Zustände.** Punkt außerhalb aller BE-Zonen ⇒ `mark_not_covered()`; Zone getroffen,
   Feed gesund, keine Warnung ⇒ leere Liste ohne Ausfall; Feed nicht abrufbar/unlesbar oder ohne
   jede auswertbare Kennung ⇒ `mark_fetch_incomplete()` (bestehender Zweig, unverändert).
   Entwarnung nur über Verschwinden (ADR-0090). `Update` und `Cancel` ersetzen ihre Vorgänger über
   `_superseded_ids` (S3a AC-7, gilt für BE automatisch, weil der Zonenweg `superseded` übergibt).
7. **Geometriegüte und Aufweitung (Messung 2026-10-31, nur Build-Zeit, nichts davon eingecheckt).**
   Die EMMA-Provinzzonen stimmen mit den amtlichen NUTS2-Flächen zu 85-97 % überein. Gitterprüfung
   (0,01°) über 38 977 belgische Landpunkte gegen eine Referenz-Landmaske: roh 945 Punkte ohne Zone
   (2,4 %), mit 0,05° Aufweitung 124 (0,3 %), mit 0,1° 12 (0,03 %; nur Randstreifen bei
   49,64-49,71°N / 5,88-5,90°E und bei 51,45°N / 5,09°E). Deshalb 0,1° statt 0,05°. Die
   Referenzmaske ist ein Mess-Hilfsmittel und wird nicht eingecheckt; das README nennt nur die
   Messwerte. Folge der Aufweitung: benachbarte Zonen überlappen, dann liefert `regions_at` beide
   Zonen und beide Warnungen erscheinen (jede einmal). An Provinzgrenzen kann ein Punkt dadurch
   in der Nachbarzone liegen ("lieber eine Warnung zu viel").
8. **Sprache.** Der Feed führt `de-DE`, `en-GB`, `fr-BE`, `nl-BE`. Der Mapper nimmt `de*`, sonst
   `en*`: Ist `de-DE` vorhanden, kommt der deutsche Text, sonst `en-GB`. Kein Code nötig, per Test
   belegt.
9. **Registrierung und Reihenfolge der Umsetzung.** `MeteoAlarmFeedSource("BE")` steht in
   `__init__.py` nach GB und vor `DpcSource` (Gewitter-Tie-Break "zuerst registriert gewinnt",
   #1427 S2); an der NL-Grenze (Maastricht liegt in der Aufweitung von BE007/BE008) gewinnt NL
   (registriert vor BE), an der Grenze zu DE/FR/LU liefert BE nur Warnungen mit eigenen Zonen.
   **Die Registrierung geschieht erst, wenn der Abdeckungstest (AC-3) und der Übersetzungstest
   grün sind**, sonst droht ein Dauer-Fehlalarm bzw. eine stille Lücke. Reihenfolge: Zonendatei →
   Tabelle/Übersetzung → Abdeckungs-/Regressionstests grün → Registrierung → Reihenfolgetests.
10. **Kanalparität.** Die geteilte Quellenauflösung gibt BE-Warnungen an alle vier Kanäle (E-Mail,
    Telegram, SMS, Premium-SMS) in Trip und Ortsvergleich weiter, ohne weitere Verdrahtung.
11. **Budget.** Feed kontingentfrei, höchstens ein Abruf je 30 min (TTL 1800 s Erfolg / 60 s
    Fehler, Timeout unverändert).

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in oder nahe Belgien.
- **Output:** unverändert `list[OfficialAlert]` über `get_official_alerts_for_location()` /
  `get_official_alerts_with_status()`, `source` bleibt `"meteoalarm"`.
- **Side effects:** ein Feed-Abruf pro Auffrischungsfenster (30 min).

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht ohne Netz, Datei `tests/tdd/test_meteoalarm_feed_be.py`, gegen die echte gekürzte
Feed-Probe `tests/fixtures/meteoalarm_feed/feed_belgium_sample.json` (aus dem echten Feed vom
2026-10-31; beide Kennungsarten, mindestens ein `Update`; kein Mock-Theater). Fälle, die die Probe
nicht enthält (`Cancel`, unlesbarer Eintrag, unbekannter NUTS2-Code, Doppelkennung, BE24/BE10/BE31),
werden synthetisch aus einem echten Eintrag abgeleitet und im Fixture-README gekennzeichnet.

Testorte (lat, lon), Sollwerte der Messung; der Developer verifiziert und justiert sie in der
Umsetzung:

| Zone | Orte (roh, ohne Aufweitung) |
|---|---|
| BE004 | Brüssel (50.85, 4.35), Grand-Place, Leuven (50.88, 4.70), Wavre (50.72, 4.61) |
| BE801 | Ostende (51.23, 2.92), Knokke (51.35, 3.29), Küste 5 km (51.28, 2.80) |
| BE008 | Eupen (50.63, 6.08), Sankt Vith |
| BE001 | Bastogne, Bouillon, Virton; **Arlon (49.68, 5.81) roh in keiner Zone, nur aufgeweitet in BE001** |
| BE003 | Gent |
| keine Zone | Nordsee 30 km vor der Küste (51.60, 2.60): bewusst ohne Zuständigkeit, folgenlos |
| außerhalb Belgiens | Aachen (50.78, 6.08), Lille (50.63, 3.06), Luxemburg-Stadt (49.61, 6.13) |
| Grenzfall | Maastricht (50.85, 5.69): `covers()` kann für BE UND NL wahr sein, keine Doppelwarnung |

- [ ] Test 1 (Feed-Pfad): `_FEED_PATHS["BE"]` ist `/api/v1/warnings/feeds-belgium`; kein neuer
  Egress-Host.
- [ ] Test 2 (Zuständigkeit): `covers()` ist für alle benannten belgischen Orte wahr (Brüssel,
  Leuven, Wavre, Ostende, Knokke, Küste 5 km, Eupen, Bastogne, Bouillon, Virton, Arlon, Gent); für
  Nordsee 30 km, Aachen, Lille und Luxemburg-Stadt falsch bzw. folgenlos (`mark_not_covered`, keine
  Warnung, kein Ausfallhinweis). Aachen/Lille/Luxemburg-Stadt dürfen nur im Randstreifen der
  Aufweitung wahr sein; ihre Abfrage liefert dennoch keine BE-Warnung.
- [ ] Test 3 (Abdeckung): Über ein Gitter von 0,01° im belgischen Landgebiet liegt der Anteil
  Punkte ohne Zone bei höchstens 0,1 %. Die Landmaske liegt nicht im Repo; der Test nutzt eine
  im Test erzeugte Punktemenge (benannte Orte plus dichte Stichprobe innerhalb der Zonendatei-
  Hülle, Messwert und Referenz im README), nie eine eingecheckte GISCO-Geometrie. Arlon ist
  Pflichtort.
- [ ] Test 4 (NUTS2-only trifft Provinz): BE23-Warnung der Probe ⇒ Gent erhält sie mit Stufe,
  Ereignisart, Zeitraum; Ort in einer anderen Provinz (z. B. Namur oder Eupen) erhält sie NICHT, ohne
  Ausfallhinweis.
- [ ] Test 5 (EMMA_ID-Warnungen): BE004-Warnung der Probe ⇒ Brüssel, Leuven und Wavre erhalten sie;
  BE801-Warnung ⇒ Ostende, Knokke und Küste 5 km erhalten sie.
- [ ] Test 6 (Brabant-Tabelle): synthetische Warnungen mit `NUTS2` BE24, BE10, BE31 ⇒ jeweils in
  Brüssel/Leuven/Wavre sichtbar (Vergröberung), nicht in Gent.
- [ ] Test 7 (Doppelkennung): eine Warnung mit `NUTS2 = BE10` UND `EMMA_ID = BE004` ⇒ in Brüssel
  genau einmal; Überlappung zweier Zonen (Provinzgrenze) ⇒ jede Warnung genau einmal.
- [ ] Test 8 (Update/Cancel): `Update` aus der Probe ersetzt den Vorgänger ⇒ genau einmal;
  synthetisches `Cancel` ⇒ nicht aktiv.
- [ ] Test 9 (unbekannter NUTS2-Code): synthetische Warnung mit z. B. `NUTS2 = BE99` ⇒ kein
  Ausfallhinweis (`unavailable=False`), Orte mit eigener Warnung behalten sie, `unknown_zone`-
  Eintrag für `meteoalarm_feed:BE`.
- [ ] Test 10 (Feed ohne Kennung / kaputter Eintrag): Feed, in dem keine Warnung ein auswertbares
  Geocode trägt ⇒ `mark_fetch_incomplete()`, `unavailable=True`; ein einzelner kaputter Eintrag
  unter lesbaren ⇒ gewarnter Ort behält seine Warnung, ruhiger Ort bleibt ruhig, beide
  `unavailable=False`.
- [ ] Test 11 (Sprache): Probe mit `de-DE` und `en-GB` ⇒ Text aus `de-DE`; derselbe Eintrag ohne
  `de-DE` (synthetisch) ⇒ Text aus `en-GB`, nicht leer.
- [ ] Test 12 (Regression): Feedtests FI/ES/PT/NL/PL/IT/AT/DE/CH/NO/SE/GB laufen unverändert grün;
  `_emma_ids_for_alert` liefert für diese Länder dieselben Mengen wie vorher (Ein-Kennung bitgleich,
  keine Tabelle angewendet; ein `NUTS2`-Wert in einem NL-Eintrag wird NICHT übersetzt).
- [ ] Test 13 (Registry/Reihenfolge): `BE` steht nach GB und vor `DpcSource`; NL steht vor BE
  (Maastricht-Grenzfall: keine Doppelwarnung); die Reihenfolgeprüfung in
  `test_meteoalarm_feed_pt_nl_pl.py` und `test_meteoalarm_feed_uk.py` akzeptiert die erweiterte
  Registry, die dortige Aussage "Belgien nicht registriert" ist gestrichen.
- [ ] Test 14 (Zonendatei/Abgleich): `meteoalarm_zones_BE.geojson.json` enthält genau die zehn Zonen
  BE001-BE009 und BE801 mit `properties.id`/`name`, ist < 400 KB; jede aus der Probe übersetzte
  Zonen-ID steht in der Datei (wie S3a AC-11); jeder Wert der Tabelle steht in der Datei; README-
  Abschnitt BE ist vorhanden (`# doc-compliance-test` nur für die README-Prüfung), nennt Herkunft,
  sha256, Aufweitung 0,1°, Zuordnungstabelle und den Verzicht auf GISCO samt Lizenzbegründung.
- [ ] Test 15 (Alarmweg Ende-zu-Ende): Warnung der Alarmstufe aus der BE-Probe über die echte
  Registry bis zur Kanal-Auflösung eines Nutzers mit Empfängern auf allen vier Kanälen ⇒ E-Mail,
  Telegram, SMS, Premium-SMS wie bei einer AT-Warnung gleicher Stufe (Trip und Ortsvergleich),
  Muster S3b Test 9.
- [ ] Test 16 (Live, Marker `live`, nur `/e2e-verify`): aktuell gewarntes Gebiet aus dem echten Feed
  ⇒ mindestens 1 Warnung ohne Ausfall im Timeout; ohne gültige Warnung SKIP mit Grund, nicht PASS.

## Acceptance Criteria

- **AC-1:** Given die Konfiguration der Landesquelle `BE`, When der Feed-Pfad abgefragt wird, Then
  lautet er `/api/v1/warnings/feeds-belgium` und es wird kein neuer Egress-Host benötigt.
  - Test: Test 1.

- **AC-2:** Given ein Wanderpunkt liegt in Belgien, auch an der Küste (Ostende, Knokke), in
  Brüssel, in den Ostkantonen (Eupen) oder im Süden (Bastogne, Arlon), When die Zuständigkeit
  geprüft wird, Then ist die belgische Quelle zuständig; Given ein Punkt liegt in der Nordsee weit
  vor der Küste oder in Aachen, Lille oder Luxemburg-Stadt, Then schweigt die Quelle folgenlos,
  ohne Warnung und ohne Ausfallhinweis.
  - Test: Test 2.

- **AC-3:** Given die eingecheckte belgische Zonengeometrie (aufgeweitet um 0,1°), When ein Gitter
  von 0,01° über das belgische Landgebiet gelegt wird, Then liegen alle benannten Testorte
  (inklusive Arlon) in mindestens einer Zone und der Anteil unabgedeckter Landpunkte beträgt höchstens
  0,1 %; verbleibende Randlücken sind als Known Limitation dokumentiert (dort schweigt die Quelle
  folgenlos).
  - Test: Test 3.

- **AC-4:** Given der Feed führt eine Warnung nur mit `NUTS2`-Kennung (z. B. BE23), When die
  Warnungen für einen Punkt in der zugeordneten Provinz (Gent) abgerufen werden, Then erscheint die
  Warnung mit Warnstufe, Ereignisart und Gültigkeitszeitraum; Given der Punkt liegt in einer anderen
  Provinz, Then erscheint sie nicht und es entsteht kein Ausfallhinweis.
  - Test: Test 4.

- **AC-5:** Given der Feed führt eine Warnung mit `EMMA_ID` `BE004` bzw. `BE801`, When die
  Warnungen für Brüssel, Leuven, Wavre bzw. für die Küste abgerufen werden, Then erscheint die
  jeweilige Warnung mit Stufe, Ereignisart und Zeitraum.
  - Test: Test 5.

- **AC-6:** Given eine Warnung trägt `NUTS2` BE10 (Brüssel), BE24 (Vlaams-Brabant) oder BE31
  (Brabant Wallon), When die Warnungen für Brüssel, Leuven oder Wavre abgerufen werden, Then
  erscheint sie dort (alle drei werden der ungeteilten EMMA-Zone BE004 zugeordnet), nicht aber in
  einer Provinz außerhalb von BE004; die Vergröberung ist als Known Limitation dokumentiert.
  - Test: Test 6.

- **AC-7:** Given eine Warnung trägt mehrere Kennungen, die auf dieselbe Zone zeigen (BE10 und
  BE004), oder ein Punkt liegt in zwei überlappenden Zonen, When die Warnungen abgerufen werden,
  Then erscheint jede Warnung je Punkt genau einmal.
  - Test: Test 7.

- **AC-8:** Given eine belgische Warnung wurde aufgehoben (`Cancel`) oder durch eine neuere Fassung
  ersetzt (`Update`), When die Warnungen abgerufen werden, Then erscheint die aufgehobene nicht als
  aktiv und die aktualisierte genau einmal, ohne die ersetzte Fassung zusätzlich.
  - Test: Test 8.

- **AC-9:** Given der Feed führt eine Warnung mit einem NUTS2-Code, der nicht in der
  Zuordnungstabelle steht, When die Warnungen für einen belgischen Punkt abgerufen werden, Then
  meldet das Ergebnis weiterhin "keine Warnung" bzw. die Warnungen des Orts und NICHT "amtliche
  Warnungen nicht abrufbar", und die Abweichung steht im Drift-Journal (`unknown_zone`,
  `meteoalarm_feed:BE`).
  - Test: Test 9.

- **AC-10:** Given der belgische Feed enthält keinen einzigen Eintrag mit auswertbarer Kennung, When
  die Warnungen für einen belgischen Punkt abgerufen werden, Then meldet das Ergebnis "amtliche
  Warnungen aktuell nicht abrufbar" (`mark_fetch_incomplete`) statt fälschlich eine warnungsfreie
  Lage zu zeigen; Given nur ein einzelner Eintrag ist unlesbar und andere sind lesbar, Then behalten
  gewarnte Orte ihre Warnung und kein Ort wird als Ausfall gemeldet.
  - Test: Test 10.

- **AC-11:** Given der Feed führt Texte in `de-DE`, `en-GB`, `fr-BE` und `nl-BE`, When die Warnung
  ausgegeben wird, Then stammt ihr Text aus `de-DE`, und fehlt `de-DE`, aus `en-GB`; er ist in
  beiden Fällen nicht leer.
  - Test: Test 11.

- **AC-12:** Given die bestehenden Warnungen für Italien, Österreich, Deutschland, die Schweiz,
  Norwegen, Schweden, Finnland, Spanien, Portugal, die Niederlande, Polen und das Vereinigte
  Königreich, When deren Testfälle nach dieser Änderung erneut laufen, Then liefern sie unverändert
  dieselben Ergebnisse; die NUTS2-Übersetzung wirkt ausschließlich für Land BE.
  - Test: Test 12.

- **AC-13:** Given die Quellenregistrierung, When die Registry aufgebaut wird, Then steht
  `MeteoAlarmFeedSource("BE")` in `__init__.py` nach GB und vor `DpcSource`, die Reihenfolge NL vor
  BE ist gewahrt (Grenzfall Maastricht ohne Doppelwarnung), und die Registrierung erfolgt erst
  nachdem Abdeckungs- (AC-3) und Übersetzungstests (AC-4 bis AC-7) grün sind.
  - Test: Test 13.

- **AC-14:** Given die Datenhaltung der belgischen Zonen, When die Dateien geprüft werden, Then
  liegt `meteoalarm_zones_BE.geojson.json` (zehn EMMA-Zonen aus `geocodes.json`, `properties.id` =
  EMMA_ID, Landzonen um 0,1° aufgeweitet, BE801 unverändert, < 400 KB) im Datenordner, und
  `data/README.md` sowie `docs/specs/data_sources.md` dokumentieren Herkunft, sha256, Lizenzstatus
  (gebündelter ungeklärter Antrag wie FI/ES/PT/NL/PL), Zuordnungstabelle und den Verzicht auf
  Eurostat-GISCO wegen der nur nicht-kommerziellen Nutzbarkeit; es wird keine GISCO-Geometrie
  eingecheckt.
  - Test: Test 14.

- **AC-15:** Given eine belgische Warnung erreicht die für Alarme maßgebliche Warnstufe, When sie
  den geteilten Alarm-Pfad eines Trip- oder Ortsvergleichs-Alarms durchläuft, Then erreicht sie bei
  der Kanal-Auflösung alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) wie eine
  österreichische Warnung derselben Stufe, ohne weitere Verdrahtung.
  - Test: Test 15.

- **AC-16:** Given der echte belgische Feed auf Staging und eine aktuell gewarnte Provinz, When die
  Quelle für einen Punkt darin abgefragt wird, Then liefert sie mindestens eine Warnung ohne
  Ausfallhinweis im Timeout; Given der Feed führt zum Zeitpunkt keine Warnung, Then ist das Ergebnis
  des Live-Tests ein SKIP mit Grund und kein Bestehen; die Kern-Tests stützen sich auf eine Fixture
  aus dem echten Feed.
  - Test: Test 16 (Live) sowie Fixture-Grundlage der Tests 4 bis 11.

## Abweichungen vom Ticket (#1442, Stand 31.07.) und von der Analyse

- **Keine GISCO/NUTS-Geometrie (Abweichung von Analyse und S3a-"Out of Scope"):** Die Analyse und
  S3a sahen als zweite Geometriequelle Eurostat GISCO NUTS-2021 vor. Messung 2026-10-31: Die
  GISCO-Seite erlaubt Verwaltungsgrenzen nur unter der Bedingung "will not be used for commercial
  purposes". Ein Multi-User-Produkt kann das nicht tragen, GISCO wird deshalb nicht eingecheckt.
  Stattdessen: nur `geocodes.json` plus Zuordnungstabelle NUTS2 → EMMA_ID. GISCO diente
  ausschließlich als Build-Zeit-Messhilfe (Flächenvergleich, Gitterprüfung) und ist nirgends
  abgelegt.
- **`geocodes.json`-Lizenz ungeklärt:** unverändert der gebündelte Antrag in
  `docs/specs/data_sources.md` (wie FI/ES/PT/NL/PL); BE wird hinzugefügt, kein neuer PO-Entscheid.
- **Aufweitung 0,1° statt 0,05° (NL/PL):** gemessen, 0,05° ließe 0,3 % belgischer Landpunkte
  unabgedeckt, 0,1° nur 0,03 %.
- **Ticket-AC-2 (24h-Abrufbudget) gegenstandslos:** `feeds.meteoalarm.org` ist kontingentfrei, es
  gilt nur der 30-min-Cache (siehe S3a).
- **Bezugsweg Feed statt `api.meteoalarm.org`/MQTT** (ADR-0039).
- **Zuschnitt:** Ticket-Slice S3 wird in S3a (PT, NL, PL), S3b (GB) und S3c (BE) zerlegt.

## Known Limitations

- **Brabant vergröbert:** EMMA kennt nur das ungeteilte "Brabant" (BE004). Eine reine BE24-
  (Vlaams-Brabant) oder BE31-Warnung (Brabant Wallon) gilt auch in Brüssel und im jeweils anderen
  Brabant; Folge höchstens eine Warnung zu viel, nie eine zu wenig.
- **Provinzgrenzen unscharf:** EMMA-Provinz und amtliche NUTS2 stimmen zu 85-97 % überein; an
  Grenzen kann ein Punkt in der Nachbarzone liegen, die Aufweitung lässt Zonen überlappen (beide
  Warnungen erscheinen, jede einmal).
- **Restlücken der Abdeckung:** Auch mit 0,1° bleiben rund 0,03 % belgischer Landpunkte ohne Zone
  (Randstreifen bei 49,64-49,71°N / 5,88-5,90°E und 51,45°N / 5,09°E). Dort schweigt die Quelle
  folgenlos ("keine Zuständigkeit"), es entsteht kein Fehlalarm. Die Nordsee weit vor der Küste
  (über BE801 hinaus) ist bewusst nicht abgedeckt.
- **Grenzstreifen:** Wegen der Aufweitung kann `covers()` für BE und ein Nachbarland (NL, DE, FR, LU)
  wahr sein (Maastricht); folgenlos, weil jeder Feed nur Warnungen mit Zonen seines Landes führt.
- **Höhenband ignoriert** (wie übrige Länder): lieber eine Warnung zu viel als zu wenig.
- **Lizenz von `geocodes.json` ungeklärt** (seit S2 offen): dokumentiertes Risiko, kein Blocker;
  BE kommt in den gebündelten Antrag. Die Klärung liegt beim PO, die Auslieferung wartet nicht.
- **Zonengeometrie und Tabelle statisch:** Änderungen bei EUMETNET erkennt der Drift-Wächter
  (`unknown_zone`), Datei bzw. Tabelle werden dann manuell nachgeführt.
- **Dünne Live-Evidenz:** Der Live-Nachweis kann mangels aktiver Warnung als SKIP enden; die
  Fixture aus dem echten Feed trägt den Kern-Nachweis.
- **#2696 (bekannt):** Der Live-Test-Selektor ignoriert Nebel-Warnungen; eine reine Nebelwarnung im
  BE-Feed wird vom Live-Selektor deshalb nicht als "gewarntes Gebiet" gewählt. Das betrifft nur den
  Live-Nachweis, nicht die Quelle. Im Abschlusskommentar von #1442 zu nennen.
- **Entwarnung** nur über Verschwinden bei gesunder Quelle (ADR-0090).
- **Latenz:** EUMETNET-Weitergabe mit 5-10 min Verzug (Rahmen ADR-0074).
- **Reiner Zonenweg-Fall ohne auswertbare Kennung:** Ein Eintrag ganz ohne auswertbare Zonenangabe
  meldet das ganze Land als "nicht abrufbar" (geteilte Abwägung aus S3a, gilt unverändert auch für
  BE).

## Out of Scope

- **Eurostat-GISCO/NUTS-Geometrie:** wegen der Lizenzbedingung (nur nicht-kommerziell) nicht
  verwendet, nicht eingecheckt.
- **Trennung der Brabant-Teile** (BE10/BE24/BE31 einzeln): ohne eigene Geometrie nicht möglich.
- **Klärung der `geocodes.json`-Lizenz** (PO-Thema, gebündelter Antrag).
- **Länder außer BE:** keine Änderung an IT/AT/DE/FI/ES/PT/NL/PL/CH/NO/SE/GB (außer
  Registry-Reihenfolgetests).
- Höhenband-Auswertung, Teilflächen, neue Egress-Hosts, Änderung von TTL und Timeout, Behebung von
  #2696, Kanal-Verdrahtung, Mail-/UI-Pfade.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neu. Es gelten ADR-0039, 0041, 0074, 0090 und 0095 unverändert.
- **Rationale:** Ein weiteres Zonenland mit einer kleinen länderspezifischen Kennungs-Übersetzung ist
  Konfiguration des bestehenden Zonenwegs, keine Grundsatzentscheidung. Der Verzicht auf GISCO ist
  eine Datenquellen-Entscheidung innerhalb des bereits geführten `geocodes.json`-Wegs und steht in
  `data/README.md` und `docs/specs/data_sources.md`.

## Changelog

- 2026-10-31: Initial spec created (Issue #1442 S3c, Analyse-Grundlage
  `docs/context/feat-1442-s3c-meteoalarm-be.md`, Abschnitt "Korrektur Phase 3").
