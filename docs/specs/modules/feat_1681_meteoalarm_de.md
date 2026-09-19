---
entity_id: feat_1681_meteoalarm_de
type: feature
created: 2026-09-19
updated: 2026-09-19
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, germany, dwd, warn-egress]
workflow: feat-1681-meteoalarm-de
---

<!-- Issue #1681, Epic-Bezug #1419 (Rang 10/E6), #2258. Folgeschritt nach #1445 (S1 Italien, S3 Österreich). -->

# MeteoAlarm Deutschland: Anbindung an den kontingentfreien MeteoAlarm-Feed

## Approval

- [ ] Approved

## Purpose

Punkte in Deutschland bekommen heute keine amtlichen Unwetterwarnungen — die Registry kennt nur
Italien und Österreich. Diese Spec schließt die Lücke: `MeteoAlarmFeedSource("DE")` wird
registriert und bezieht amtliche DWD-Warnungen aus demselben kontingentfreien öffentlichen Feed
(`feeds.meteoalarm.org`), den IT und AT bereits nutzen. Die Punkt-zu-Warngebiet-Zuordnung läuft
über eine eingecheckte DWD-Kreisgeometrie und die im Feed enthaltene `WARNCELLID` — keine
Übersetzungstabelle nötig. Zwei bestehende Korrektheitslücken werden mit ausgeliefert: Aufhebungen
(`responseType: AllClear`) erscheinen sonst als aktive Warnung, und ein DE-Feed-Ausfall könnte in
den Bayerischen Alpen durch die zuständige, aber „nicht zuständig" antwortende österreichische
Quelle stumm überdeckt werden.

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py` (MODIFY — dritter Ländercode `DE`)
- **Identifier:** `MeteoAlarmFeedSource.__init__(country)`, `covers()`, `fetch()`,
  `_zone_for_point_de` (neu), `_emma_ids_for_alert`, `_info_entries_from_alert`

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`). Kein Go-,
> kein Frontend-Anteil.

## Estimated Scope

- **LoC:** ~120–170 Produktivcode (Analyse-Schätzung) + separater Testumfang
- **Files:** ~6 Code/Test + 2 Daten
- **Effort:** medium (Alarmpfad aller vier Kanäle betroffen, gemeinsamer Umsetzer mit IT/AT)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS["DE"] = "/api/v1/warnings/feeds-germany"` (Z. 50-54); `Literal["IT","AT","DE"]` (Z. 281); neue `_zone_for_point_de(lat, lon)` (Ray-Cast gegen die eingecheckte DWD-Kreisgeometrie, liefert `WARNCELLID` oder `None`); `covers()`/`fetch()` (Z. 288-352) von binärer AT/sonst-Verzweigung auf echte Drei-Wege-Verzweigung IT/AT/DE umgebaut, DE nutzt **dieselbe** `_zone_for_point_de` in `covers()` UND `fetch()`; `_emma_ids_for_alert` (Z. 167-176) auf Geocode-Art parametrisiert (`EMMA_ID` für IT/AT, `WARNCELLID` für DE); `_info_entries_from_alert` (Z. 145-164) übernimmt `responseType` |
| `src/services/official_alerts/meteoalarm.py` | MODIFY | `_group_and_map_info_entries` (Z. 595-644) verwirft Info-Einträge mit `responseType: AllClear` als nicht-aktive Warnung, statt sie wie bisher unbeachtet weiterzureichen |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(MeteoAlarmFeedSource("DE"))` nach AT, vor DPC (Z. 22-42), mit Reihenfolge-Kommentar |
| `src/services/official_alerts/base.py` | MODIFY (klein) | „nicht zuständig" der österreichischen Quelle (ZAMG 404) darf nach DE-Registrierung nicht mehr automatisch als erfolgreiche, zuständige Quelle in der `covering`/`failed`-Bilanz (Z. 119-225) zählen — sonst maskiert AT einen DE-Ausfall in den Bayerischen Alpen |
| `src/services/official_alerts/warn_egress.py` | MODIFY (klein) | Generisches Signal `mark_not_covered()` im bestehenden `observe_fetch_failure()`-Kontext (Schlüssel `not_covered`); `cached_fetch` setzt es bei ZAMG-404 (frisch und aus dem Cache) — Grundlage für den `base.py`-Abzug (AC-3) |
| `src/services/official_alerts/dpc.py` | MODIFY (1 Zeile) | `DpcSource.fetch` meldet „keine DPC-Zone" als `mark_not_covered()` — in Garmisch reicht die DPC-Radar-Bbox bis 47,5 N und hätte den DE-Ausfall sonst mitkompensiert (AC-3) |
| `src/services/official_alerts/data/dwd_warngebiete_kreise.json` | CREATE | DWD-Layer `dwd:Warngebiete_Kreise` (402 Flächen, WGS84, ~0,9 MB), Kopf mit Quellenvermerk |
| `src/services/official_alerts/dwd_zones.py` (oder gleichwertiges Kleinmodul) | CREATE | Loader für die Kreisgeometrie, analog `dpc.py:62-88` (`_ZONES_PATH`, `_load_zones`), nutzt den bestehenden `geo_ray_cast.py` weiter |
| `tests/tdd/test_meteoalarm_feed_deutschland.py` | CREATE | Verhaltenstests gegen die aufgezeichnete Fixture, Drei-Zustände-Regel, Grenzpunkte, AllClear, Südbayern-Kompensation |
| `tests/fixtures/meteoalarm_feed/feed_germany_sample.json` + `README.md` | CREATE/MODIFY | Stichprobe des echten DE-Feeds: mindestens ein `AllClear`-Eintrag, ein `9…`-Sammelkreis, eine Küstenzelle (`501…`), ein Eintrag ohne `expires`, ein Kreis aus den Bayerischen Alpen (Garmisch-Partenkirchen) |
| `tests/tdd/test_meteoalarm_feed_italien.py`, `test_meteoalarm_feed_oesterreich.py` | MODIFY (Regression) | AllClear-Filterung ändert den gemeinsamen Umsetzer — bestehende Ergebnisse müssen unverändert grün bleiben |
| Drift-Wächter (neue Testdatei, analog `test_dpc_zone_drift.py`) | CREATE | WARNCELLIDs aus dem Feed gegen die eingecheckte Geometrie abgleichen |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.warn_egress.cached_fetch` | module | Einziger erlaubter Abrufweg für den DE-Feed, wie bereits für IT/AT |
| `services.official_alerts.warn_egress.log_zone_drift` / `mark_fetch_incomplete` | module | Diagnose-/Ausfall-Kanal, jetzt zusätzlich vom DE-Drift-Wächter genutzt |
| `services.official_alerts.geo_ray_cast._point_in_ring` | module | Wiederverwendeter Ray-Cast, kein neuer Algorithmus für DE |
| `services.official_alerts.data/dwd_warngebiete_kreise.json` | data | Eingecheckte DWD-Kreisgeometrie, Muster A nach ADR-0041 |
| `services.official_alerts.meteoalarm._group_and_map_info_entries` | module | Geteilter Mapper IT/AT/DE — AllClear-Filter wirkt für alle drei Länder gleich |
| `services.official_alerts.base.get_official_alerts_with_status` | module | Wertet `unavailable` über ALLE registrierten Quellen ab — Grund für den Südbayern-Fix (AC-3) |
| `services.official_alerts.radar_service` (INCA-Bbox) | module | Referenz für die Überschneidung DE/AT in den Bayerischen Alpen |
| `services.trip_alert`, `services.comparison_engine`, `services.compare_official_alert`, `services.trip_report_scheduler` | module | Konsumieren `OfficialAlert` unverändert über die Registry — bekommen DE automatisch mit, kein eigener Code nötig |
| `docs/context/feat-1681-meteoalarm-de.md` | reference | Vollständige Analyse (Live-Messung, Risiken, Entscheidungen 1–7) |
| `docs/specs/modules/feat_1445_s3_oesterreich_feed.md` | spec | Schwesterscheibe Österreich, gleiche Bauart |
| `docs/adr/0039-amtliche-warnungen-aus-kontingentfreiem-feed.md` | adr | Grundsatzentscheidung Feed statt EDR-Index — DE folgt demselben Muster, kein neues ADR nötig |

## Implementation Details

1. **Zuordnung über `WARNCELLID`** statt über `EMMA_ID`: Der DE-Feed führt pro Gebiet beide
   Kennungen 1:1 (290 distinkte Zellen). Eine eigene EMMA-Übersetzungstabelle ist damit
   überflüssig — die eingecheckte DWD-Kreisgeometrie trägt `WARNCELLID` bereits als Feld.
2. **Dieselbe Zonenfunktion in `covers()` und `fetch()`.** Genau die Divergenz zwischen grober
   Bbox in `covers()` und echter Geometrie in `fetch()` hatte bei Italien 39 falsche „nicht
   abrufbar"-Meldungen auf einer Tour erzeugt (#1397 S4). `_zone_for_point_de` wird als eine
   Funktion für beide Aufrufer verwendet.
3. **Küstenzellen bewusst ausgenommen.** 8 der 290 Feed-Zellen (`WARNCELLID`-Präfix `501…`)
   liegen nicht im Kreis-Layer. Alle Info-Einträge ohne `expires` tragen ausschließlich diesen
   Präfix und können mangels Geometrie ohnehin keinem Wanderpunkt zugeordnet werden — kein
   Eingriff in `filter_alerts_to_window` nötig, Known Limitation statt Sonderfall.
4. **AllClear-Filterung auf Alert-Ebene.** `responseType` ist je Alert einheitlich (nicht je
   Sprachvariante unterschiedlich). Ein Alert mit `responseType: AllClear` wird im gemeinsamen
   Mapper `_group_and_map_info_entries` verworfen, bevor er als aktive Warnung gerendert werden
   kann. Das betrifft ausschließlich das Verschwinden einer aufgehobenen Warnung aus der Liste
   aktiver Warnungen — eine aktive Meldung „Warnung X wurde aufgehoben" ist eine eigene
   Produktfrage und nicht Teil dieser Spec (s. Out of Scope).
5. **Südbayern-Kompensationslücke.** `MeteoAlarmFeedSource("AT").covers()` ist eine reine
   INCA-Bbox und schließt die Bayerischen Alpen ein; ein ZAMG-404 dort zählt heute als
   „zuständige, erfolgreiche Quelle". Fällt nach dieser Spec der DE-Feed aus, würde die
   Ausfall-Bilanz in `base.py` fälschlich „1 von mehreren zuständigen Quellen ausgefallen"
   statt „die einzig wirklich zuständige deutsche Quelle ist ausgefallen" zeigen und keinen
   Hinweis erzeugen. Diese Spec behebt das, weil der Fehler erst durch die DE-Registrierung
   entsteht.
6. **TTL und Timeout bleiben unverändert** (Entscheidungen 6/7 der Analyse, s. unten).

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in oder nahe Deutschland.
- **Output:** unverändert `list[OfficialAlert]` über `get_official_alerts_for_location()` /
  `get_official_alerts_with_status()`, jetzt zusätzlich aus dem DE-Feed gespeist; `source` bleibt
  `"meteoalarm"`.
- **Side effects:** ein zusätzlicher Feed-Abruf gegen `feeds.meteoalarm.org/.../feeds-germany`
  je Auffrischungsfenster (~5 MB, gemessen 2026-09-19); zusätzliche Journal-Einträge bei
  Drift-Funden (WARNCELLID im Feed ohne eingecheckte Geometrie).

## Test Plan

### Automated Tests (TDD RED)

Kern-Tests laufen ohne Netz gegen die aufgezeichnete Fixture
`tests/fixtures/meteoalarm_feed/feed_germany_sample.json` (kein Mock der Fachlogik). Live-Abrufe
gegen den echten DE-Feed nur in `/e2e-verify`.

- [ ] Test 1: GIVEN ein Punkt liegt im Landkreis Garmisch-Partenkirchen UND der aufgezeichnete
  DE-Feed enthält für dessen `WARNCELLID` eine aktive gelbe Warnung WHEN die amtlichen Warnungen
  für diesen Punkt ermittelt werden THEN erscheint genau diese Warnung mit Stufe, Ereignisart und
  Zeitraum im Ergebnis.
- [ ] Test 2: GIVEN ein Punkt liegt in Deutschland, dessen Warngebiet im aufgezeichneten Feed
  keinen aktiven Alert trägt WHEN die amtlichen Warnungen ermittelt werden THEN liefert das
  Ergebnis eine leere Liste UND `unavailable=False`.
- [ ] Test 3: GIVEN der DE-Feed-Abruf schlägt fehl WHEN die amtlichen Warnungen für einen Punkt
  in den Bayerischen Alpen ermittelt werden, wo zusätzlich die österreichische Quelle regulär mit
  „nicht zuständig" antwortet, THEN meldet das Ergebnis `unavailable=True` statt fälschlich eine
  warnungsfreie Lage zu zeigen.
- [ ] Test 4: GIVEN ein Punkt liegt außerhalb Deutschlands (Innsbruck, Salzburg oder Basel) WHEN
  sowohl `covers()` als auch `fetch()` der deutschen Quelle für diesen Punkt aufgerufen werden
  THEN antwortet die deutsche Quelle in beiden Fällen konsistent mit „nicht zuständig", ohne
  einen Ausfallhinweis auszulösen.
- [ ] Test 5: GIVEN der aufgezeichnete Feed enthält für das Warngebiet eines abgefragten Punkts
  ausschließlich einen `AllClear`-Eintrag mit einem in der Zukunft liegenden `expires` WHEN die
  amtlichen Warnungen für diesen Punkt ermittelt werden THEN erscheint diese Warnung NICHT als
  aktive Warnung im Ergebnis.
- [ ] Test 6 (Regression): GIVEN die bestehenden Italien- und Österreich-Tests laufen nach dem
  gemeinsamen AllClear-Filter erneut WHEN sie ausgeführt werden THEN bleibt jedes bisherige
  Testergebnis für IT und AT unverändert grün.
- [ ] Test 7: GIVEN der aufgezeichnete Feed enthält einen Info-Eintrag ohne `expires`, dessen
  `WARNCELLID` mit dem Präfix `501` beginnt (Küstenzelle) WHEN die amtlichen Warnungen für einen
  Wanderpunkt in Deutschland ermittelt werden THEN kann dieser Eintrag keinem Punkt zugeordnet
  werden, weil die eingecheckte Geometrie keine Küstenflächen enthält.
- [ ] Test 8 (Drift-Wächter): GIVEN eine `WARNCELLID` taucht im aufgezeichneten Feed auf, die in
  der eingecheckten DWD-Kreisgeometrie fehlt UND ihr Präfix ist nicht `501` (Küste) WHEN der
  Drift-Wächter läuft THEN wird dieser Fund gemeldet statt still ignoriert zu werden.
- [ ] Test 9 (Alarmweg-Parität): GIVEN zwei amtliche Warnungen gleicher Stufe (orange) und
  gleicher Art — eine aus dem aufgezeichneten DE-Feed über `MeteoAlarmFeedSource("DE")`
  umgesetzt, eine aus dem aufgezeichneten AT-Feed — UND ein Trip bzw. Ortsvergleich, dessen
  Nutzer Empfänger auf allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS) konfiguriert hat,
  WHEN die geteilte Alarm-Kanal-Auflösung für beide Warnungen läuft (Trip-Alarm und
  Ortsvergleichs-Alarm) THEN liefert sie für die DE-Warnung exakt dieselbe Kanalmenge wie für die
  AT-Warnung, und diese Menge enthält alle vier Kanäle.
- [ ] Test 10 (Grenzraum DE/AT): GIVEN ein Punkt in den Bayerischen Alpen (Garmisch-Partenkirchen),
  für dessen Warngebiet der aufgezeichnete DE-Feed eine aktive Warnung führt, UND die
  österreichischen Quellen antworten für diesen Punkt regulär mit „nicht zuständig" WHEN die
  amtlichen Warnungen über die Registry ermittelt werden (alle registrierten Quellen, echte
  Registrierungsreihenfolge) THEN enthält das Ergebnis diese Warnung genau einmal, mit deutscher
  Herkunft, und `unavailable=False`.
- [ ] Test 11 (Südtirol, Folgewirkung des generischen „nicht zuständig"-Signals, nachgetragen
  2026-09-19): GIVEN ein Punkt in Bozen, registriert sind nur GeoSphere und
  `MeteoAlarmFeedSource("IT")`, ZAMG antwortet mit 404 („nicht zuständig") WHEN der IT-Feed
  ausfällt THEN `unavailable=True`; WHEN der IT-Feed erreichbar ist THEN `unavailable=False`
  (`test_f002_suedtirol_zamg_404_kompensiert_it_ausfall_nicht`). Die bisherigen IT/AT-Testfälle
  (Test 6) bleiben unverändert grün.
- [ ] Test 12 (Enklaven, nachgetragen 2026-09-19): GIVEN ein Punkt in Baden-Baden (Enklave im
  Landkreis Rastatt) WHEN das Warngebiet ermittelt wird THEN liefert es Baden-Baden, nicht
  Rastatt — unabhängig von der Reihenfolge der Kreise in der Geometrie
  (`test_f003_enklave_baden_baden_gehoert_nicht_zum_umschliessenden_kreis_rastatt`).

## Acceptance Criteria

- **AC-1:** Given ein Wanderpunkt liegt in einem deutschen Landkreis mit einer amtlich aktiven
  Warnung (z. B. Garmisch-Partenkirchen), When die amtlichen Warnungen für diesen Punkt abgerufen
  werden, Then erscheint diese Warnung mit Warnstufe, Ereignisart und Gültigkeitszeitraum im
  Ergebnis.
  - Test: Test 1 oben.

- **AC-2:** Given ein Wanderpunkt liegt in Deutschland und für sein Warngebiet besteht amtlich
  keine aktive Warnung, When die amtlichen Warnungen für diesen Punkt abgerufen werden, Then
  meldet das Ergebnis „keine Warnung" und NICHT „amtliche Warnungen nicht abrufbar".
  - Test: Test 2 oben.

- **AC-3:** Given der deutsche Warndienst ist zum Abrufzeitpunkt nicht erreichbar, auch wenn der
  Punkt in den Bayerischen Alpen liegt und die österreichische Quelle für denselben Punkt mit
  „nicht zuständig" antwortet, When die amtlichen Warnungen für diesen Punkt abgerufen werden,
  Then meldet das Ergebnis „amtliche Warnungen aktuell nicht abrufbar" statt fälschlich eine
  warnungsfreie Lage zu zeigen.
  - Test: Test 3 oben.

- **AC-4:** Given ein Wanderpunkt liegt außerhalb Deutschlands (z. B. Innsbruck, Salzburg oder
  Basel), When die amtlichen Warnungen für diesen Punkt abgerufen werden, Then schweigt die
  deutsche Quelle folgenlos — kein deutscher Ausfallhinweis, keine deutsche Warnung — weil sie
  für diesen Punkt erkennbar nicht zuständig ist.
  - Test: Test 4 oben.

- **AC-5:** Given eine amtliche deutsche Warnung wurde offiziell aufgehoben (Meldungstyp
  „Aufhebung"), When die amtlichen Warnungen für den betroffenen Punkt abgerufen werden, Then
  erscheint diese Warnung nicht als aktive Warnung im Ergebnis. Eine eigene aktive Meldung „diese
  Warnung wurde aufgehoben" ist nicht Teil dieser Änderung und berührt nicht die bestehende
  Entwarnungs-Dringlichkeitsregel für hauseigene Gewitterstufen (#2177).
  - Test: Test 5 oben.

- **AC-6:** Given die bestehenden Warnungen für Italien und Österreich, When dieselben
  Testfälle nach dieser Änderung erneut laufen, Then liefern sie unverändert dieselben
  Ergebnisse wie vor der Änderung.
  - Test: Test 6 oben.

- **AC-7:** Given ein Warnungseintrag betrifft ausschließlich eine deutsche Küsten- oder
  Seegebietszelle ohne hinterlegte Ablaufzeit, When die amtlichen Warnungen für Wanderpunkte
  abgerufen werden, Then kann dieser Eintrag keinem Wanderpunkt zugeordnet werden, weil
  Küstengebiete bewusst nicht in der Geometrie enthalten sind (bekannte Einschränkung, kein
  Fehler).
  - Test: Test 7 oben.

- **AC-8:** Given die eingecheckte Quellenangabe für die deutschen Warngebiete, When diese Datei
  eingesehen wird, Then trägt sie den zweiteiligen Quellenvermerk „Warngebiete: Deutscher
  Wetterdienst (DWD), CC BY 4.0; Copyright GeoBasis-DE / BKG (http://www.bkg.bund.de) 2019 (Daten
  modifiziert)" wörtlich.
  - Test: Prüfung der README/Docstring-Datei bei `dwd_warngebiete_kreise.json` (doc-compliance,
    kein Verhaltenstest).

- **AC-9:** Given eine im Feed auftauchende deutsche Warnzellen-Kennung fehlt in der eingecheckten
  Geometrie und ist keine der bekannten Küstenzellen, When der Drift-Wächter läuft, Then wird
  dieser Fund gemeldet, statt unbemerkt zu bleiben.
  - Test: Test 8 oben.

- **AC-10:** Given eine deutsche amtliche Warnung erreicht die für Alarme maßgebliche Warnstufe,
  When ein Trip- oder Ortsvergleichs-Alarm für den betroffenen Punkt ausgelöst wird, Then
  erreicht diese Warnung dieselben Kanäle (E-Mail, Telegram, SMS, Premium-SMS) wie eine
  österreichische oder italienische Warnung derselben Stufe — ohne eigenen Sonderweg, weil
  Trip-Alarme (`trip_alert.py`) und Ortsvergleichs-Alarme jede `OfficialAlert` unabhängig vom
  Herkunftsland gleich behandeln.
  - Test: Test 9 oben — kein neuer Produktivcode für diesen Pfad nötig; der Test beweist die
    Parität am Wirkort (Kanal-Auflösung), nicht nur am Umsetzer.

- **AC-11:** Given ein Wanderpunkt in den Bayerischen Alpen, für den sowohl die deutsche als auch
  die österreichische Quelle angefragt werden, und für sein deutsches Warngebiet gilt eine aktive
  Warnung, When die amtlichen Warnungen für diesen Punkt abgerufen werden, Then erscheint diese
  Warnung genau einmal (nicht doppelt, nicht verschluckt) und ohne Ausfallhinweis — unabhängig
  davon, in welcher Reihenfolge die Quellen registriert sind.
  - Test: Test 10 oben.

## Known Limitations

- **Küsten- und Seegebiete sind bewusst nicht enthalten.** Die eingecheckte DWD-Kreisgeometrie
  deckt nur die 402 Landkreis-Flächen ab, nicht `dwd:Warngebiete_Kueste`. Warnungen für die 8
  Küstenzellen (`WARNCELLID`-Präfix `501…`) können keinem Wanderpunkt zugeordnet werden. Für das
  Wanderer-Produkt ist das irrelevant — eine spätere Erweiterung wäre eine eigene Scheibe.
- **Aktive Entwarnungs-Meldung bei Aufhebung amtlicher Warnungen ist eine eigene Produktfrage**
  und nicht Teil dieser Spec (s. AC-5). Das Verhalten entspricht dem bisherigen, stillen
  Verschwinden bei IT/AT.
- **Drift der Warnzellen bei DWD-Kreisreformen.** Der Drift-Wächter meldet nur bereits im Feed
  aufgetauchte, unbekannte `WARNCELLID`s — er verhindert keine veraltete Geometrie, solange
  keine neue Kennung im Feed erscheint.
- **Keine EMMA-Übersetzungstabelle** wird geführt; die Zuordnung läuft ausschließlich über
  `WARNCELLID`. Sollte eine künftige Feed-Version `WARNCELLID` entfernen, bräuchte DE eine neue
  Zuordnungsquelle.

## Out of Scope

- Aktive Entwarnungs-Meldung bei Aufhebung amtlicher Warnungen (eigene Produktfrage, siehe Known
  Limitations).
- Küsten- und Seegebiete (`dwd:Warngebiete_Kueste`, `dwd:Warngebiete_Binnenseen`).
- Komprimierter Abruf: am 2026-09-19 gemessen — der Feed-Server liefert auch mit
  `Accept-Encoding: gzip` unkomprimiert (5,5 MB, identische Bytezahl mit/ohne Header, kein
  `Content-Encoding`). Kompression ist damit serverseitig nicht verfügbar; der Header wird
  trotzdem gesendet, damit eine spätere Serverumstellung ohne Codeänderung wirkt. Die Folge
  (~240 MB/Tag) trägt ADR-0074.
- Änderung der Erfolgs-/Fehlschlag-TTL (bleibt 1800 s / 60 s, Parität mit IT/AT — bewusste
  Entscheidung, s. unten) und des Timeouts (bleibt 15 s, gemessen 1,5–2,0 s für den DE-Feed am
  2026-09-19, Reserve-Faktor ≥7).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** **ADR-0074** (neu, `docs/adr/0074-auffrischraster-meteoalarm-feed-deutschland.md`) —
  konkretisiert die Folgepflicht aus ADR-0039 („Für weitere Länder ist deshalb ein eigenes
  Auffrischraster vorzusehen") für Deutschland. Daneben gelten ADR-0039 (Bezugsweg Feed) und
  ADR-0041 (Zuständigkeit, Muster A: eingecheckte Geometrie) unverändert.
- **Rationale:** ADR-0039 verlangt die Abwägung, nicht eine bestimmte Drosselung. Deutschland
  bekommt einen eigenen Cache-Eintrag (Schlüssel = Ländercode) mit 1800 s Erfolg / 60 s Fehler.
  Der Preis — ca. 240 MB/Tag je Umgebung, weil der Feed unkomprimiert kommt (gemessen 5,5 MB,
  19.09.2026) — wird bewusst getragen: Bandbreite kostet auf dem Server nichts Messbares, eine
  bis zu einer Stunde veraltete amtliche Unwetterwarnung auf allen vier Alarmkanälen schon.
  Eine gröbere Drosselung (45–60 min) wurde deshalb verworfen.

## Changelog

- 2026-09-19: Implementierung — „nicht zuständig" als generisches Signal (`warn_egress.mark_not_covered()`,
  gesetzt von ZAMG-404, AT Fall 1, DPC ohne Zone); `base.py` nimmt solche Quellen aus der
  `covering`-Bilanz. Folgewirkung über DE hinaus (Tech-Lead-Entscheid, gleiches Prinzip wie AC-3):
  in Südtirol kompensiert ein ZAMG-404 einen Ausfall des IT-Feeds nicht mehr — dort erscheint
  jetzt „amtliche Warnungen nicht abrufbar" statt einer scheinbar warnungsfreien Lage.
  `warn_egress.py` und `dpc.py` in die Dateitabelle aufgenommen.
- 2026-09-19: Initial spec created (Issue #1681, Analyse-Grundlage
  `docs/context/feat-1681-meteoalarm-de.md`, Entscheidungen 1–7 unverändert übernommen).
