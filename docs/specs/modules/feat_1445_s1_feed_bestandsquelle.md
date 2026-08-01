---
entity_id: feat_1445_s1_feed_bestandsquelle
type: feature
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, warn-egress, quota, italy]
workflow: feat-1445-s1-feed-bestandsquelle
---

<!-- Issue #1445 -->

# MeteoAlarm Italien: Auffrischung aus dem kontingentfreien öffentlichen Feed (Scheibe S1)

## Approval

- [ ] Approved

## Purpose

Der amtliche Warndienst `api.meteoalarm.org` sperrt seit dem 27.07.2026 täglich für 24 Stunden
(HTTP 429) — der bisherige EDR-Index für Italien ist damit den größten Teil des Tages veraltet,
und jede Budget-Anpassung ist geraten, weil die reale Anbietergrenze nicht stationär ist
(`docs/context/fix-1397-wiederanlauf-ausbruch.md`). Live geprüft existiert für dieselbe
Organisation ein zweiter, **kontingentfreier** Zugang: `feeds.meteoalarm.org` liefert eine
Momentaufnahme aller aktuell gültigen italienischen Warnungen mit vollem CAP-Inhalt in einem
einzigen Abruf, ohne Authentifizierung. Diese Scheibe stellt die Warnungsermittlung für Italien
auf diesen Feed um — der bisherige EDR-Weg entfällt für IT vollständig, Österreich bleibt in
dieser Scheibe unverändert am EDR-Index (Folge-Scheibe S3). Ziel: Netz-Abrufe gegen
`api.meteoalarm.org` für IT fallen auf **null**, ohne dass ein Wanderer je eine gültige
italienische Warnung seltener oder unvollständiger sieht als heute.

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py` (neu)
- **Identifier:** `MeteoAlarmFeedSource`, `_zone_for_point`, `_parse_feed`, `_get_cached_feed`

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`). Kein Go-,
> kein Frontend-Anteil. Kein Eingriff in `internal/scheduler/` — der Aufruf läuft weiterhin über
> denselben Weg wie jede andere `OfficialAlertSource` (`base.py::get_official_alerts_with_status`,
> aufgerufen aus `trip_alert.py`/`compare_official_alert.py`).

## Estimated Scope

- **LoC:** ~200–250 (Produktivcode + Test-Anpassungen, ohne diese Spec) — **eng am 250er-Limit**,
  siehe Implementation Details Punkt 8 zur möglichen Vorab-Scheibe für den Mapper-Umbau.
- **Files:** 6 (1 neue Python-Quelle, 2 geänderte Python-Quellen, 1 neue Testdatei, 2 neue
  versionierte Fixture-Dateien)
- **Effort:** medium-high (Zonenzuordnung + Äquivalenznachweis sind sicherheitskritisch, s.
  Randbedingung 1 der Aufgabenstellung)

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/official_alerts/meteoalarm_feed.py` | CREATE | Neue Quelle `MeteoAlarmFeedSource`: Feed-Abruf über `warn_egress.cached_fetch()`, Punkt→EMMA-Zone über `dpc._zone_at()` + Präfix-Tabelle, Nutzung der geteilten Gruppieren/Mappen-Funktion aus `meteoalarm.py` |
| `src/services/official_alerts/meteoalarm.py` | MODIFY | `_extract_alerts_from_cap` in „Info-Einträge sammeln" (bleibt XML-spezifisch) und „gruppieren/mappen" (wird geteilt genutzt) aufgeteilt; Länderliste in `fetch()` von `("AT", "IT")` auf `("AT",)`; `covers()` verliert die IT-Bbox-Prüfung |
| `src/services/official_alerts/__init__.py` | MODIFY | Registrierung von `MeteoAlarmFeedSource` zwischen `MeteoAlarmSource` und `DpcSource` |
| `tests/tdd/test_meteoalarm_feed_source.py` | CREATE | Fetch-Mapping, Verbrauchsdisziplin, Ausfall-/Zonen-Ehrlichkeit, Äquivalenznachweis gegen aufgezeichnete EDR-Fixture |
| `tests/fixtures/meteoalarm/feed_italy_equivalence_snapshot.json` | CREATE | Aufgezeichneter Feed-Ausschnitt (reale Tourpunkte, Italien) für den Äquivalenztest |
| `tests/fixtures/meteoalarm/edr_italy_equivalence_snapshot.json` | CREATE | Zur selben Minute aufgezeichneter EDR-Ausschnitt für dieselben Punkte — Referenzmenge des Äquivalenztests |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.warn_egress.cached_fetch` | module | Einziger erlaubter Abrufweg (Randbedingung: Journal-Zeile, Verbrauch messbar) — kein 429-Sonderfall nötig, da der Feed kein Auth/keine bekannte Ratenbremse hat |
| `services.official_alerts.warn_egress.log_zone_drift` | module | Bereits vorhandener additiver Diagnose-Kanal (aus #1434), wird für „Punkt ohne auflösbare Zone" wiederverwendet statt neu erfunden — trägt bewusst kein `ok`-Feld, wird von der Go-Aggregation automatisch übersprungen |
| `services.official_alerts.dpc._zone_at` (`dpc.py:77-83`) | module | Fertige Punkt-in-Fläche-Auflösung gegen die eingecheckte Geometrie (187 Zonen) — keine neue Geodatei, kein neuer Netzabruf |
| `services.official_alerts.meteoalarm._TYPE_HAZARD_MAP`, `_leading_int`, `_pick_preferred_entry`, `_parse_iso` | module | Bestehende, reine Mapping-Helfer — unverändert wiederverwendet, nicht dupliziert |
| `services.official_alerts.meteoalarm` (neue geteilte Gruppieren/Mappen-Funktion, Implementation Details Punkt 2) | module | Zentrale CAP-Info→`OfficialAlert`-Übersetzung, jetzt von XML- UND JSON-Sammelweg gemeinsam genutzt |
| `services.official_alerts.base.get_official_alerts_with_status` (`base.py:90-146`) | module | Wertet `unavailable` weiterhin aus `covering`/`failed` je registrierter Quelle ab — Grund für Randbedingung 3 (kein Parallelbetrieb-Übersprechen) |
| `data/diagnostics/warn_service_calls.jsonl` | data | Nachweisquelle für AC-1/AC-2 (kein Eintrag mit `host=api.meteoalarm.org` für IT; Dienst-Label `meteoalarm_feed:IT`) |
| `docs/context/fix-1397-wiederanlauf-ausbruch.md` | reference | Vollständige Analyse (Ausgangsmessung, Befunde 1–5, Roadmap S1–S6); diese Spec entspricht der dortigen Scheibe „Feed-Quelle Italien" |
| `docs/specs/modules/fix_1397_meteoalarm_coverage_budget.md` | spec | Bisheriger EDR-Verbrauchsmechanismus für AT/IT — für IT durch diese Scheibe ersetzt, für AT unverändert gültig |
| `docs/specs/modules/fix_1434_dpc_zonen_drift.md` | spec | Vorbild für den „nicht abrufbar statt still leer"-Mechanismus bei Zonen-Auflösungsproblemen |

## Implementation Details

1. **Neue Quelle `MeteoAlarmFeedSource`** in `meteoalarm_feed.py`, strukturell wie `DpcSource`:
   `covers()` als reiner Bbox-Vorfilter (DPC-Bbox, kein Netzabruf), `fetch()` löst den Punkt auf
   eine EMMA-Zone auf, holt den gecachten Feed-Bestand und filtert auf Warnungen, deren
   `area[].geocode[]` diese EMMA-ID enthält.
2. **CAP-Mapper aufgetrennt statt nachgebaut** (Randbedingung, siehe Aufgabenstellung):
   `_extract_alerts_from_cap` in `meteoalarm.py` wird in zwei Funktionen zerlegt — eine
   XML-spezifische „Info-Einträge sammeln"-Hälfte (unverändertes Verhalten für den
   AT-Abrufweg) und eine formatunabhängige „gruppieren/mappen"-Hälfte (Level-Filter ≥2,
   `_TYPE_HAZARD_MAP`-Übersetzung, Sprachpräferenz über `_pick_preferred_entry`,
   `_parse_iso` für `onset`/`expires`). `meteoalarm_feed.py` baut aus dem JSON-Feed
   (`alert.info[]`, `parameter[]` für `awareness_level`/`awareness_type`, `area[].areaDesc`)
   dieselbe normalisierte Info-Struktur und ruft die geteilte Funktion auf — identische
   Filterregeln, ein Ort der Wahrheit für „was zählt als Warnung".
3. **Zonenzuordnung ohne neue Geodatei:** `_zone_for_point(lat, lon)` ruft
   `dpc._zone_at(lat, lon)` (liefert einen DPC-Zonencode wie `VDAo-A`) und schlägt dessen
   Regions-Anteil in einer neuen, 20-zeiligen Tabelle `_REGION_PREFIX_TO_EMMA` nach
   (verifiziert: `VDAo`→`IT004`, `Lazi`→`IT012`, `Ligu`→`IT007`). Die exakte Grenze des
   Regions-Anteils (feste Zeichenzahl vs. Trennung am ersten Ziffern-/Kleinbuchstabenwechsel)
   wird in der RED-Phase an allen 187 echten Zonencodes verifiziert und dort als Tabelle
   festgeschrieben — verbindlich für Implementierung und Tests.
4. **Kein auflösbarer Zonencode ⇒ `unavailable=True`, kein Kilometer-Rückfall in S1**
   (Randbedingung 5 der Aufgabenstellung, hier entschieden): Ein Punkt außerhalb aller 187
   DPC-Zonen (Küste, Lagune, See) markiert den Abruf über `warn_egress.mark_fetch_incomplete()`
   als unvollständig UND schreibt eine `log_zone_drift("meteoalarm_feed", None,
   True, "point_unmapped")`-Zeile (Wiederverwendung des in #1434 geschaffenen Kanals) für die
   Beobachtung. **Begründung gegen einen sofortigen Nächste-Zone-Rückfall:** ein falsch
   geratener Nachbarzonen-Wert kann sowohl eine tatsächlich zutreffende Warnung einer anderen
   Zone verdecken (falsches Negativ) als auch eine nicht zutreffende Warnung anzeigen (falsches
   Positiv) — bei der obersten Randbedingung „keine übersehene Warnung" ist der explizite
   Ausfall-Hinweis der sicherere Default. Der Kilometer-Rückfall (Muster
   `department_mapper.py:263`) bleibt Folge-Scheibe.
5. **Abruf ausschließlich über `warn_egress.cached_fetch()`:** `service="meteoalarm_feed:IT"`,
   `host="feeds.meteoalarm.org"`, `success_ttl`/`failure_ttl` analog dem bestehenden
   Erfolgs-/Fehler-Fenster (`WARN_SUCCESS_TTL`/`WARN_FAILURE_TTL`, 30 min / 60 s) — ein Cache-Treffer
   innerhalb der TTL löst **keinen** Netz-Call aus (AC-2). Kein `rate_limit_retry` (kein Auth,
   keine dokumentierte Ratenbremse, Präzedenz: `DpcSource` verwendet denselben schlanken Weg).
6. **Kein kumulierender Bestand, keine Supersede-Filterung nötig:** anders als der EDR-Index ist
   der Feed bei jedem Abruf bereits eine Momentaufnahme der aktuell gültigen Fassungen
   (verifiziert im Kontext-Dokument: 0 von 335 referenzierten Vorgängern im Snapshot enthalten)
   — AC-6 folgt direkt aus dem TTL-Cache, ohne `_is_superseded`/`expires`-Aufbewahrungslogik wie
   in `meteoalarm.py`.
7. **Randbedingung 3 (kein Parallelbetrieb-Übersprechen):** in `meteoalarm.py` wird nicht nur
   die Länderliste in `fetch()` von `("AT", "IT")` auf `("AT",)` verengt, sondern **zusätzlich**
   die `in_it`-Bbox-Prüfung in `covers()` entfernt. Begründung über die Aufgabenstellung hinaus:
   bliebe `covers()` unverändert, würde ein italienischer Punkt weiterhin als von
   `MeteoAlarmSource` „abgedeckt" gezählt (`covering+=1`), obwohl dessen `fetch()` für IT nie
   mehr etwas liefert — schlägt dann der (jetzt reine AT-)Indexabruf fehl, würde das
   fälschlich `unavailable=True` für italienische Punkte auslösen, obwohl die neue Feed-Quelle
   ihre Daten unabhängig davon liefert. Das ist exakt das in Randbedingung 3 beschriebene
   Risiko, nur eine Ebene tiefer als die reine Länderschleife.
8. **Registrierung** in `__init__.py`: `MeteoAlarmFeedSource` NACH `MeteoAlarmSource`, VOR
   `DpcSource` — behält die bestehende Tie-Break-Reihenfolge bei (MeteoAlarm-Marke gewinnt bei
   Stufengleichstand weiterhin vor DPC). `OfficialAlert.source` bleibt der String `"meteoalarm"`
   (nicht `"meteoalarm_feed"`) — nur der interne Abrufweg ändert sich, bestehende Downstream-Verträge
   (Cross-Source-Dedup-Tie-Break, ggf. UI-Beschriftung, bestehende Tests, die auf den String
   prüfen) bleiben unberührt.
9. **LoC-Risiko explizit benannt (Punkt 4 der Aufgabenstellung):** Das LoC-Gate zählt
   hinzugefügte UND gelöschte Zeilen — eine Zerlegung von `_extract_alerts_from_cap` (Punkt 2)
   kann trotz unveränderter Semantik einen größeren Diff erzeugen als der reine Netto-Zuwachs.
   **Entscheidung für diese Spec:** der Mapper-Umbau bleibt Teil von S1, weil er die
   Voraussetzung für Wiederverwendung statt Nachbau ist (explizite Vorgabe) und isoliert klein
   ist (~60–90 Zeilen Diff geschätzt). **Sollte der tatsächliche Diff beim Commit-Gate über das
   250er-Limit treiben**, wird Punkt 2 als eigene Vorab-Scheibe `S1a` (reine Umbenennung/Trennung
   in `meteoalarm.py`, kein Verhaltensunterschied, kein neuer Test außer einem Regressionstest
   „AT-CAP-Mapping unverändert") ausgekoppelt — die Akzeptanzkriterien dieser Spec sind davon
   unabhängig, unabhängig davon, welche Scheibe den Umbau liefert.

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in Italien.
- **Output:** unverändert `list[OfficialAlert]` über `get_official_alerts_for_location()` /
  `get_official_alerts_with_status()` — jetzt gespeist aus dem öffentlichen Feed statt dem
  kontingentierten EDR-Index; bei nicht erreichbarem Feed oder nicht auflösbarer Zone bleibt
  `unavailable=True`.
- **Side effects:** Netz-Abrufe gegen `api.meteoalarm.org` fallen für IT auf null; ein Abruf je
  Auffrischungsfenster gegen `feeds.meteoalarm.org` (~1,4 MB, keine Kompression); zusätzliche
  Journal-Zeilen im bestehenden Diagnose-Kanal bei nicht auflösbaren Punkten.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (`tests/tdd/test_meteoalarm_feed_source.py`): GIVEN eine aufgezeichnete Feed-Antwort
  enthält eine aktuell gültige Warnung für eine EMMA-Zone, WHEN `MeteoAlarmFeedSource.fetch()`
  für einen Punkt in dieser Zone aufgerufen wird THEN erscheint die Warnung im Ergebnis UND im
  Diagnose-Journal (injizierter Pfad) taucht kein Eintrag mit `host=api.meteoalarm.org` für
  diesen Punkt auf.
- [ ] Test 2 (`tests/tdd/test_meteoalarm_feed_source.py`): GIVEN mehrere Abfragen für
  verschiedene italienische Punkte fallen in dasselbe Auffrischungsfenster WHEN sie
  nacheinander ausgewertet werden THEN löst genau ein Aufruf der injizierten `request_fn`
  einen echten Netz-Call aus, alle weiteren werden aus dem Cache bedient.
- [ ] Test 3 (`tests/tdd/test_meteoalarm_feed_source.py`, Äquivalenz-Pflicht-Gate): GIVEN die
  beiden zur selben Minute aufgezeichneten Fixtures (EDR-Ausschnitt, Feed-Ausschnitt) für eine
  Liste realer Tourpunkte WHEN beide Ergebnismengen für dieselben Punkte gebildet werden THEN
  ist die Feed-Ergebnismenge eine Obermenge der EDR-Ergebnismenge (jede EDR-Warnung erscheint
  auch im Feed-Ergebnis desselben Punkts).
- [ ] Test 4 (`tests/tdd/test_meteoalarm_feed_source.py`): GIVEN der Feed-Abruf schlägt fehl
  (Netzwerkfehler oder HTTP-Fehlerstatus, injizierte `request_fn`) WHEN die amtlichen Warnungen
  für einen abgedeckten italienischen Ort ermittelt werden THEN liefert der Aufruf
  `unavailable=True` statt einer leeren, als „keine Warnung" interpretierbaren Liste.
- [ ] Test 5 (`tests/tdd/test_meteoalarm_feed_source.py`): GIVEN ein Punkt liegt innerhalb der
  DPC-Bbox, aber außerhalb aller 187 bekannten Zonenpolygone (z.B. Küstenpunkt) WHEN die
  amtlichen Warnungen für diesen Punkt ermittelt werden THEN liefert der Aufruf
  `unavailable=True` UND im Diagnose-Journal erscheint eine zählbare `log_zone_drift`-Zeile mit
  `drift="point_unmapped"`.
- [ ] Test 6 (`tests/tdd/test_meteoalarm_feed_source.py`): GIVEN eine Feed-Fixture, deren
  frühere Fassung einer Warnung in der aktuellen Momentaufnahme nicht mehr enthalten ist
  (abgelaufen/zurückgezogen) WHEN das Ergebnis für den betroffenen Punkt gebildet wird THEN
  erscheint nur die aktuell im Feed enthaltene Fassung, keine überholte zusätzlich.
- [ ] Test 7 (`tests/tdd/test_meteoalarm_source.py`, Regression): GIVEN die Länderliste in
  `MeteoAlarmSource.fetch()` ist auf `("AT",)` verengt UND `covers()` erkennt einen
  italienischen Punkt nicht mehr als abgedeckt WHEN ein fehlgeschlagener AT-Indexabruf mit
  einem gleichzeitig erfolgreichen Feed-Abruf für einen italienischen Punkt kombiniert wird
  THEN bleibt `unavailable` für den italienischen Punkt `False` — ein AT-Fehler färbt IT nicht
  mehr ein (Randbedingung 3).
- [ ] Test 8 (`tests/tdd/test_meteoalarm.py`, Regression): GIVEN dieselbe reale CAP-XML-Fixture
  wie vor dem Mapper-Umbau WHEN `_extract_alerts_from_cap()` über den unveränderten
  AT-Abrufweg aufgerufen wird THEN ist das Ergebnis bit-identisch zum Stand vor dieser Scheibe
  (Regressionsschutz für die Trennung „sammeln"/„gruppieren").

## Acceptance Criteria

- **AC-1:** Given ein Ort in Italien liegt in einer Zone, für die aktuell eine gültige amtliche
  Warnung besteht, When die amtlichen Warnungen für diesen Ort ermittelt werden, Then erscheint
  die Warnung im Ergebnis, ohne dass im Diagnose-Journal ein Abruf gegen den bisherigen
  kontingentierten Warndienst für Italien verzeichnet wird.
  - Test: Test 1 oben — Ergebnis + Journal-Abwesenheit von `host=api.meteoalarm.org` für IT.

- **AC-2:** Given mehrere Orte in Italien werden innerhalb desselben Auffrischungsfensters
  abgefragt, When die amtlichen Warnungen ermittelt werden, Then löst höchstens ein echter
  Netzabruf gegen die neue Quelle dieses Fenster aus — jede weitere Abfrage im selben Fenster
  wird aus dem Bestand bedient.
  - Test: Test 2 oben — Zählung echter `request_fn`-Aufrufe über mehrere Abfragen.

- **AC-3:** Given ein zur selben Minute aufgezeichneter Vergleichsabruf über den bisherigen
  kontingentierten Weg und die neue Quelle liegen für eine Liste realer Tourpunkte vor, When
  beide Ergebnismengen gegenübergestellt werden, Then enthält die neue Quelle mindestens alle
  Warnungen, die der bisherige Weg für dieselben Punkte lieferte.
  - Test: Test 3 oben — Obermengen-Vergleich gegen die aufgezeichneten Fixtures (Pflicht-Gate
    vor Freigabe, Randbedingung 1).
  - **PO-Entscheidung 2026-08-01:** Der Product Owner hat die Auslieferung freigegeben, bevor
    dieser Nachweis (`edr_snapshot_it.json`) vorliegt — Grundlage ist ein am selben Tag geführter
    Kreuzvergleich gegen die Ursprungsquelle GeoSphere Austria an acht realen Orten (darunter
    Sillian und Lienz am Karnischen Höhenweg), der keine einzige fehlende Warnung zeigte, dazu
    117 grüne Tests und zwei bestandene Gegenproben. Der zugehörige Test
    (`test_ac3_feed_menge_ist_obermenge_der_edr_menge_fuer_reale_tourpunkte`) bleibt
    `@pytest.mark.xfail(strict=True, ...)`, bis das eigentliche Anbieter-Tageskontingent
    (gesperrt bis 2026-08-01T15:45 UTC) wieder verfügbar ist und der Vergleich nachgezogen wird —
    danach wird die Markierung entfernt.

- **AC-4:** Given die neue Quelle ist zum Abrufzeitpunkt nicht erreichbar, When die amtlichen
  Warnungen für einen betroffenen italienischen Ort ermittelt werden, Then meldet das Ergebnis
  „amtliche Warnungen aktuell nicht abrufbar" statt fälschlich eine warnungsfreie Lage zu
  zeigen.
  - Test: Test 4 oben — `unavailable=True` bei fehlgeschlagenem Feed-Abruf.

- **AC-5:** Given ein Ort in Italien lässt sich keiner amtlichen Warnzone zuordnen (z.B. Küste,
  Lagune, See), When die amtlichen Warnungen für diesen Ort ermittelt werden, Then meldet das
  Ergebnis ebenfalls „amtliche Warnungen aktuell nicht abrufbar" und der Vorfall bleibt im
  Betrieb zählbar nachvollziehbar.
  - Test: Test 5 oben — `unavailable=True` plus additive Diagnose-Zeile bei nicht auflösbarem
    Punkt.

- **AC-6:** Given eine zuvor gültige italienische Warnung ist inzwischen abgelaufen oder durch
  eine neuere Fassung ersetzt, When die amtlichen Warnungen für den betroffenen Ort ermittelt
  werden, Then erscheint im Ergebnis nur die aktuell gültige Fassung, nicht die überholte.
  - Test: Test 6 oben — nur die aktuelle Feed-Momentaufnahme erscheint, keine überholte
    Zusatzfassung.

- **AC-7:** Given der bisherige kontingentierte Weg für Österreich fällt zum Abrufzeitpunkt aus,
  When die amtlichen Warnungen für einen italienischen Ort ermittelt werden, Then bleibt das
  Ergebnis für diesen Ort davon unberührt — ein Ausfall des einen Landes darf die
  Warnungsermittlung des anderen nicht als „nicht abrufbar" einfärben.
  - Test: Test 7 oben — AT-Indexfehlschlag plus erfolgreicher IT-Feed-Abruf, `unavailable` für
    IT bleibt `False`.

## Antrag für `docs/specs/data_sources.md`

**Status:** PENDING — Genehmigung durch den Product Owner erforderlich vor Umsetzung dieser
Scheibe (Governance-Regel: „Claude erstellt Antrag in dieser Spec, Henning prüft, erst danach
implementieren").

**Neue Quelle:** `feeds.meteoalarm.org` (öffentlicher CAP-Feed derselben Organisation, die
bereits über `api.meteoalarm.org` als amtliche Warnquelle genutzt wird — gleiche Datenbasis,
anderer Transport).

| Merkmal | Wert |
|---|---|
| Endpunkt | `https://feeds.meteoalarm.org/api/v1/warnings/feeds-italy` |
| Auth | keine (öffentlich, kein API-Key) |
| Kontingent | keines bekannt/dokumentiert (im Gegensatz zur EDR-API mit unbekannter, schrumpfender Tagesgrenze) |
| Inhalt | vollständiger CAP-Inhalt je Warnung (`event`, `severity`, `urgency`, `certainty`, `onset`, `expires`, `headline`, `description`, `senderName`, `area[].areaDesc`, `area[].geocode[]`, `parameter[]` mit `awareness_level`/`awareness_type`) — inhaltlich identisch zur bisher genehmigten MeteoAlarm-Datenbasis, nur ohne Index-Zwischenschritt |
| Umfang je Abruf | ~1,4 MB / 457 Einträge (195 aktuell gültig), < 1,4 s Antwortzeit (live gemessen 2026-07-31) |

**Begründung:** ersetzt für Italien ausschließlich den Transportweg der bereits genutzten
MeteoAlarm-Warndaten (kein neuer Datenlieferant, keine neue Datenkategorie) — löst das in
Issue #1397 dokumentierte Kontingentproblem strukturell statt durch Dosierung.

**Risiko:** niedrig-mittel — kein ETag/gzip (jede Auffrischung kostet die volle Größe), keine
dokumentierte Versionsgarantie der JSON-Struktur seitens des Anbieters (Mapper-Tests fangen
eine Strukturänderung als Fehlschlag ab, nicht als stille Fehlinterpretation, da der
`_TYPE_HAZARD_MAP`-Filter unbekannte `awareness_type`-Werte bereits verwirft).

**Vorlage/Präzedenz:** identisches Prozessmuster wie „Antrag #1: Open-Meteo Wetter-Parameter"
in `docs/specs/data_sources.md`.

## Known Limitations

- **Österreich bleibt am kontingentierten EDR-Weg.** Diese Scheibe löst das Kontingentproblem
  nur für Italien. Österreich ist laut Kontext-Dokument der deutlich größere Verbraucher
  (17–21 Seiten je Zyklus) — die eigentliche Entlastung kommt erst mit Folge-Scheibe S3
  (analoge Feed-Quelle für AT über die `gemeindenr`→EMMA-Ableitung aus `geosphere_warn.py`).
- **Kein Push (MQTT) in dieser Scheibe.** Jede Auffrischung ist ein Voll-Abruf (~1,4 MB); die
  Aktualität bleibt an das Poll-Intervall gebunden, nicht an die vom Anbieter beworbene
  „near-realtime"-Latenz des separat geprüften MQTT-Kanals (Folge-Scheibe S4).
- **Kein ETag/gzip beim Feed** — jede Auffrischung überträgt die volle Größe; für die aktuelle
  Skalierung (ein Land, moderates Poll-Intervall) unkritisch, wird mit weiteren Ländern
  (#1442) relevanter.
- **`Cancel`-CAP-Verhalten unbeobachtet.** Im live geprüften Snapshot kamen nur `Alert`/`Update`
  vor. Da der Feed eine reine Momentaufnahme der aktuell gültigen Fassungen ist (kein
  Ereignis-Log), verschwindet eine zurückgezogene Warnung ohnehin aus der nächsten
  Momentaufnahme — ein separates `Cancel`-Handling ist für das beobachtete Verhalten nicht
  erforderlich, aber nicht durch einen echten Fall belegt.
- **Kein Kilometer-Rückfall für Punkte ohne auflösbare Zone** (Implementation Details Punkt 4,
  bewusste Entscheidung dieser Scheibe): Küsten-/Lagunen-/Seepunkte melden „nicht abrufbar"
  statt einer geratenen Nachbarzonen-Warnung. Ein Nächste-Zone-Rückfall (Muster
  `department_mapper.py:263`) ist eine mögliche Folge-Scheibe, sobald gemessen ist, wie oft der
  Fall in der Praxis auftritt.
- **Kein Bestand über Prozessneustarts persistiert.** Ein Neustart erzwingt einen neuen
  Feed-Abruf je Land — kostenlos (kein Kontingent), aber nicht Teil dieser Scheibe optimiert
  (z.B. gegen einen kurzen Doppelabruf bei parallelen Arbeitsprozessen).
- **Kreuzvalidierung nur punktuell, nicht dauerhaft.** Der Äquivalenznachweis (AC-3) ist ein
  einmalig aufgezeichneter Fixture-Vergleich zum Zeitpunkt der Implementierung, kein
  fortlaufender Live-Abgleich — eine spätere strukturelle Abweichung zwischen EDR-Fläche und
  EMMA-Zone bliebe unbemerkt, bis sie erneut manuell verglichen wird.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0039 (`docs/adr/0039-amtliche-warnungen-aus-kontingentfreiem-feed.md`) — nachgetragen 2026-08-01, nachdem S3 den Wechsel auf **beide** Länder ausgedehnt und die EDR-Quelle vollständig aus der Registrierung genommen hat. Die ursprüngliche Einschätzung dieser Spec („keine", siehe unten) galt für den Zwischenstand mit nur einem Land und bleibt als Begründung dokumentiert.
- **Ursprüngliche Rationale (Stand S1, überholt):** Der Transportweg wechselt (EDR-Index mit Auth/Kontingent → öffentlicher
  CAP-Feed ohne Auth/Kontingent), der Datenlieferant (MeteoAlarm/MeteoGate) und die
  Architektur-Rolle bleiben identisch — weiterhin eine additive externe Alert-Quelle in der
  bestehenden `official_alerts`-Registry (ADR-0016 bleibt gültig), weiterhin fail-soft ohne
  Kaschieren eines Ausfalls (ADR-0018 bleibt gültig, hier sogar geschärft: Punkt-ohne-Zone wird
  jetzt explizit statt still leer). Es entsteht keine neue Entscheidungsfläche im Sinne von
  CLAUDE.md (kein neuer Kanal, kein neues Datenmodell, keine Auth-/Editor-/Test-Deploy-Strategie-
  Änderung) — Analogie zu `fix_1397_meteoalarm_coverage_budget.md` und
  `fix_1434_dpc_zonen_drift.md`, die aus demselben Grund „ADR-Nr.: keine" tragen. **Vorbehalt:**
  sobald eine spätere Scheibe (S4, MQTT-Push) den Bezugsweg für ALLE Länder dauerhaft von
  Poll auf Push umstellt, ist zu diesem Zeitpunkt erneut zu prüfen, ob das als eigenständige
  Provider-Architekturentscheidung ein ADR verdient — für die hier vorliegende, auf Italien und
  Poll begrenzte Scheibe nicht.

## Changelog

- 2026-08-01: Initial spec created (Issue #1445, Scheibe S1 — Feed-Bestandsquelle Italien,
  EDR-Index für IT entfällt; AT unverändert; Folge-Scheiben S2 Registrierung/Rollout-Feinschliff
  falls nötig, S3 Österreich, S4 MQTT laut `docs/context/fix-1397-wiederanlauf-ausbruch.md`)
