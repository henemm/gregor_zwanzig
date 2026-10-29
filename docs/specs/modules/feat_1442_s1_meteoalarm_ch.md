---
entity_id: feat_1442_s1_meteoalarm_ch
type: feature
created: 2026-10-29
updated: 2026-10-29
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, switzerland, polygon, warn-egress]
workflow: feat-1442-s1-meteoalarm-ch
---

<!-- Issue #1442, Slice S1 (nur Schweiz). S2 (NO/SE/FI) und S3 folgen als eigene Workflows. Vorlage: feat_1681_meteoalarm_de.md. -->

# MeteoAlarm Schweiz: Anbindung an den kontingentfreien MeteoAlarm-Feed

## Approval

- [ ] Approved

## Purpose

Punkte in der Schweiz bekommen heute keine amtlichen Unwetterwarnungen (Wind, Gewitter, Regen, Hitze,
Schnee/Eis) — die Registry kennt Italien, Österreich und Deutschland, aus der Schweiz nur die
Lawinen-Gefahrenstufe des SLF. Diese Spec schließt die Lücke: `MeteoAlarmFeedSource("CH")` wird
registriert und bezieht die amtlichen MeteoSchweiz-Warnungen aus dem kontingentfreien öffentlichen
Feed `feeds.meteoalarm.org`, den IT/AT/DE bereits nutzen.

Der Schweizer Feed unterscheidet sich in einem Punkt grundlegend von den drei bestehenden: er trägt
**keine Gebietskennung** (weder `EMMA_ID` noch eine Schweizer Warnregion), sondern je Gebiet nur den
Gemeindenamen und den **Gemeinde-Umriss** (`polygon`). Die Zuordnung Punkt → Warnung läuft deshalb
über Punkt-in-Polygon direkt gegen die Feed-Polygone — ein anderer Algorithmus als bei IT/AT/DE.

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py` (MODIFY — vierter Ländercode `CH`)
- **Identifier:** `MeteoAlarmFeedSource.__init__(country)`, `covers()`, `fetch()`,
  `_FEED_PATHS`, `_alerts_for_point_polygon` (neu), `_get_cached_feed`

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`). Kein Go-, kein
> Frontend-Anteil. Go-Prüfung (Grep in `internal/`, 2026-10-29): keine Länderliste für amtliche
> Warnungen vorhanden (weder `warn_service_health.go` noch `forecast_budget_health.go` kennen
> Ländercodes der Warnquellen); die Egress-Inventarliste `internal/egress/inventory.go` führt den Host
> `feeds.meteoalarm.org` bereits. Kein Go-Eingriff nötig.

> **Mandantentrennung:** Keine Nutzerdaten im Pfad. Die Quelle ist global (ein Feed für alle,
> Cache-Schlüssel = Ländercode, Eingang nur `lat`/`lon` eines beobachteten Orts); es wird nichts
> nutzerbezogen gelesen, geschrieben oder gecacht. Ein Zwei-Nutzer-Test ist deshalb gegenstandslos
> (gleiche Begründung wie bei #1681). Die Nutzerbindung geschieht unverändert erst im geteilten
> Alarm-Pfad (Empfänger des jeweiligen Nutzers).

> **Trip/Ortsvergleich-Teilung:** Kein Pendant nötig — die Quelle hängt in der Registry und wird von
> Trip-Briefing, Trip-Alarm, Ortsvergleich-Briefing und Ortsvergleich-Alarm gleichermaßen über
> `get_official_alerts_*` konsumiert (ein Code).

> **Kanäle:** Alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) hängen am geteilten Alarm-Pfad
> (`trip_alert.py`, Ortsvergleichs-Alarm, #1701/#1533). Die CH-Warnung ist eine gewöhnliche
> `OfficialAlert`; es wird **keine Kanal-Sonderlogik** eingeführt.

## Estimated Scope

- **LoC:** ~+120 / −5 (Produktiv ~80, Rest Tests/Fixture)
- **Files:** 2 Produktiv + Fixture + README + 1 Testdatei (+ 1 Live-Test)
- **Effort:** medium (Risk MEDIUM: 5,6-MB-Feed, Polygonrechnung pro Punkt, Grenzfälle Nachbarländer)

### Affected Files (Scope)

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS["CH"] = "/api/v1/warnings/feeds-switzerland"` (Z. 51); `Literal["IT","AT","DE","CH"]` (Z. 339); `covers()` (Z. 346) um CH-Zweig: lokal über `SlfSource`-Regionspolygone (`RegionMapper.regions_at`), kein Netz; `fetch()` (Z. 382) um CH-Zweig; neue `_alerts_for_point_polygon(feed, lat, lon)` (Punkt-in-Polygon gegen `info[].area[].polygon`, vorab Bounding-Box je Area; Malformation-/Cancel-Schutz wie `_alerts_for_zone` Z. 273); Parse-Ergebnis samt vorberechneten BBoxen wird 30 min mitgecacht |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(MeteoAlarmFeedSource("CH"))` nach DE, vor `DpcSource`/SLF, mit Reihenfolge-Kommentar |
| `src/services/official_alerts/geo_ray_cast.py` | REUSE | `_point_in_ring` (Z. 12) unverändert; Außenring-/Loch-Behandlung im neuen Aufrufer |
| `src/services/official_alerts/slf.py` | REUSE | `SlfSource.covers()` / `RegionMapper.regions_at` (Z. 72-74) als lokale CH-Geometrie; keine Änderung |
| `src/services/official_alerts/meteoalarm.py` | REUSE | geteilter CAP-Mapper (`_group_and_map_info_entries`) wählt `de*`, Fallback `en*` (Z. 103) — keine Änderung |
| `src/services/official_alerts/meteoalarm_feed.py` (Fallback) | MODIFY | `covers()`-Fallback: liegt ein Punkt außerhalb der SLF-Regionen, aber in einem gecachten Feed-Polygon, gilt die CH-Quelle als zuständig (siehe Implementation Details Punkt 3) |
| `tests/fixtures/meteoalarm_feed/feed_switzerland_sample.json` | CREATE | gekürzte Probe des echten CH-Feeds: `Alert`/`Update` aus echter Aufzeichnung; `Cancel`-, Loch- und Höhenband-Fälle bewusst synthetisch aus einem echten Eintrag abgeleitet |
| `tests/fixtures/meteoalarm_feed/README.md` | MODIFY | Abschnitt zur CH-Fixture (Herkunft, Aufzeichnungsdatum, Auswahl, Kürzung); synthetische Einträge ausdrücklich als „synthetisch" gekennzeichnet |
| `docs/specs/data_sources.md` | MODIFY | PENDING-Antrag auf Feed-Weg und CH-Scope umstellen (Budget/EDR streichen) |
| `tests/tdd/test_meteoalarm_feed_ch.py` | CREATE | Kern-Verhaltenstests gegen die Fixture (Treffer, Kein-Treffer, Ausfall, Ausland, Cancel/Update, Dedup, Tie-Break, Alarmweg-Parität) |
| `tests/tdd/test_meteoalarm_feed_ch_live.py` | CREATE | ein Live-Test (Marker `live`) gegen den echten Feed als Staging-Nachweis |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.warn_egress.cached_fetch` | module | einziger erlaubter Abrufweg für den CH-Feed |
| `warn_egress.mark_fetch_incomplete` / `mark_not_covered` | module | Drei-Zustände-Regel: Ausfall vs. nicht zuständig |
| `services.official_alerts.geo_ray_cast._point_in_ring` | module | Punkt-in-Polygon, kein neuer Algorithmus |
| `services.official_alerts.slf.RegionMapper.regions_at` | module | lokale CH-Zuständigkeit für `covers()` |
| `services.official_alerts.meteoalarm._group_and_map_info_entries` | module | geteilter CAP-Mapper (Stufe/Typ aus `awareness_level`/`awareness_type`) |
| `services.official_alerts.base.get_official_alerts_with_status` | module | wertet `unavailable` über alle Quellen; `not_covered` kompensiert keinen Ausfall |
| `services.trip_alert`, `services.comparison_engine`, `services.compare_official_alert`, `services.trip_report_scheduler` | module | konsumieren `OfficialAlert` unverändert — bekommen CH automatisch |
| `docs/context/feat-1442-s1-meteoalarm-ch.md` | reference | Analyse mit Messbefunden (2026-10-28) |
| `docs/specs/modules/feat_1681_meteoalarm_de.md`, `feat_1445_s3_oesterreich_feed.md`, `refactor_2266_meteoalarm_edr_rueckbau.md` | spec | Schwester-/Vorgängerspecs |
| `docs/adr/0039-amtliche-warnungen-aus-kontingentfreiem-feed.md`, `0090` | adr | Bezugsweg Feed; Entwarnung über Verschwinden |

## Implementation Details

1. **Zuordnung per Punkt-in-Polygon, nicht per Kennung.** Messung 2026-10-28
   (`GET .../feeds-switzerland`, 200, 5,6 MB, 143 Einträge: 136 Alert, 7 Update; je Eintrag 5
   Sprachblöcke en/de/fr/it/rm × 1 `info`): jede `area` hat nur `areaDesc` (Gemeindename),
   `altitude`, `ceiling` und `polygon` (Gemeinde-Umriss); 715 Areas insgesamt, **kein Geocode**.
   `_alerts_for_point_polygon` prüft den Punkt gegen die Ringe aller Areas der aktuellen Warnungen;
   Mehrfachringe und Löcher werden beachtet (Punkt im Außenring und nicht in einem Loch).
2. **Bounding-Box-Vorfilter.** Je Area wird beim Parsen einmal die BBox berechnet; nur Areas, deren
   BBox den Punkt enthält, werden voll gerechnet. BBoxen werden zusammen mit dem geparsten Feed
   30 min gecacht (Cache-Schlüssel `CH`, TTL unverändert 1800 s Erfolg / 60 s Fehler wie IT/AT/DE),
   damit die 5,6 MB nicht je Trip-Punkt neu ausgewertet werden.
3. **Zuständigkeit (`covers`) lokal, mit Fallback.** `covers(lat, lon)` ist `True`, wenn der Punkt in
   mindestens einer SLF-Regionspolygon-Fläche liegt (`RegionMapper.regions_at`) — kein Netz, keine
   neue Datei. Gemessen (2026-10-28, nur 7 Städte): deckt Zürich, Bern, Basel, Genf, Lugano, Davos,
   Schaffhausen ab und schließt Konstanz, Lörrach, Annemasse, Bregenz, Feldkirch, Como, Livigno,
   Chamonix, Domodossola, Mulhouse korrekt aus. Weil diese Stichprobe klein ist, wird die Abdeckung
   an ≥15 Rand-/Grenzpunkten als Teil des RED-Tests gemessen (Test 4). **Fallback (verbindlich):**
   liegt ein Punkt außerhalb der SLF-Regionen, prüft `covers()` zusätzlich Punkt-in-Polygon gegen die
   bereits gecachten Feed-Polygone (BBox-Vorfilter); enthält der Feed den Punkt, ist die Quelle
   zuständig. So bleibt ein CH-Punkt, den der Feed kennt, nie still „nicht zuständig". Ist der Feed
   dabei nicht im Cache und nicht abrufbar, wird nicht über das Netz nachgeladen (kein Netz in
   `covers()`), der Punkt gilt dann als nicht zuständig.
4. **Drei Zustände.** Punkt außerhalb CH → `mark_not_covered()`, leere Liste, kein Ausfall.
   Punkt in CH, Feed abrufbar, kein Treffer-Polygon → leere Liste, **kein** Ausfall (der Feed führt
   nur aktuell gewarnte Gemeinden). Feed nicht abrufbar oder unlesbar → `mark_fetch_incomplete()`
   (Muster DE) — dann `unavailable=True`.
5. **Cancel/Update/Malformation wie `_alerts_for_zone`.** `Cancel` ohne `info` wird nicht als
   Warnung ausgegeben; ein `Update` ersetzt die referenzierte Vorgängerwarnung (keine
   Doppelanzeige); ein einzelner andersförmiger Eintrag irgendwo im Land darf nicht jede Ortsabfrage
   als „nicht abrufbar" färben (Zonenzugehörigkeit vor Malformationsprüfung, vgl. F005 aus #1445 S1).
   Entwarnung folgt ADR-0090 (Verschwinden bei gesunder Quelle, zwei Läufe) — kein eigener Pfad.
6. **Registrierung.** Nach `MeteoAlarmFeedSource("DE")`, vor `DpcSource`/SLF. Gewitter-Tie-Break
   „zuerst registriert gewinnt" (#1427 S2). SLF liefert die andere Gefahrenart (`avalanche_bulletin`),
   daher keine inhaltliche Überlappung.
7. **Sprache.** Der geteilte Mapper wählt `de*`, Fallback `en*`; die fünf Sprachblöcke je Alert
   brauchen keine Änderung.
8. **Egress.** Host `feeds.meteoalarm.org` ist bereits in `src/app/egress_guard.py` und
   `internal/egress/inventory.go` gelistet — kein neuer Host.

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in oder nahe der Schweiz.
- **Output:** unverändert `list[OfficialAlert]` über `get_official_alerts_for_location()` /
  `get_official_alerts_with_status()`, jetzt zusätzlich aus dem CH-Feed gespeist; `source` bleibt
  `"meteoalarm"`.
- **Side effects:** ein zusätzlicher Feed-Abruf (`.../feeds-switzerland`, ~5,6 MB, unkomprimiert,
  gemessen 2026-10-28) je Auffrischungsfenster (30 min); Folgekosten wie bei DE (ADR-0074-Rahmen).

## Test Plan

### Automated Tests (TDD RED)

Kern-Tests laufen ohne Netz gegen `tests/fixtures/meteoalarm_feed/feed_switzerland_sample.json`
(gekürzte Aufzeichnung, kein Mock der Fachlogik; Testdateien nach Verhalten benannt:
`test_meteoalarm_feed_ch.py`). Herkunft der Fixture-Einträge (verbindlich): `Alert` und `Update`
stammen aus echter Aufzeichnung (Messbefund: 136 Alert, 7 Update, **kein** `Cancel` im Feed); die
Fälle `Cancel`, Loch/Mehrfachring und Höhenband sind **bewusst synthetisch** aus einem echten Eintrag
abgeleitet und im Fixture-README als „synthetisch" gekennzeichnet. Enthalten sind: eine aktive
Warnung für eine Gemeinde im Raum Zürich oder Bern, ein `Update` samt Vorgänger, ein synthetischer
`Cancel`, eine synthetische Area mit Loch, und eine Area mit Höhenband (`altitude`/`ceiling`).

- [ ] Test 1: GIVEN ein Punkt in einer Gemeinde mit aktiver Warnung in der Fixture (Zürich/Bern)
  WHEN die amtlichen Warnungen ermittelt werden THEN erscheint genau diese Warnung mit Stufe,
  Ereignisart und Zeitraum.
- [ ] Test 2: GIVEN ein Punkt in der Schweiz (Lugano) ohne Treffer-Polygon in der Fixture WHEN die
  Warnungen ermittelt werden THEN leere Liste UND `unavailable=False`.
- [ ] Test 3: GIVEN der CH-Feed-Abruf schlägt fehl WHEN die Warnungen für einen Punkt in der Schweiz
  ermittelt werden THEN `unavailable=True`.
- [ ] Test 4 (Zuständigkeits-Messung): GIVEN ≥15 Schweizer Rand-/Grenzpunkte (u. a. Chiasso, Basel,
  Genf, Schaffhausen, Müstair, Samnaun, Sargans, Brig, Disentis, Porrentruy, St-Gingolph, dazu Zürich,
  Bern, Lugano, Davos) WHEN `covers()` für jeden Punkt läuft THEN ist es überall `True` (über
  SLF-Regionen oder, falls dort nicht enthalten, über den Feed-Polygon-Fallback aus der Fixture);
  GIVEN Nachbarland-Punkte (Konstanz DE, Bregenz AT, Como IT, Chamonix FR, Lörrach, Feldkirch,
  Mulhouse) WHEN `covers()` und die Registry-Abfrage laufen THEN ist die CH-Quelle `False`, löst
  keinen Ausfallhinweis aus und liefert keine Warnung. Ein dazu ergänzter Fallback-Fall: ein Punkt
  außerhalb der SLF-Regionen, aber im Fixture-Polygon, ist zuständig.
- [ ] Test 5: GIVEN die Fixture enthält einen `Cancel` zu einer Warnung für die Gemeinde des Punkts
  WHEN die Warnungen ermittelt werden THEN erscheint die aufgehobene Warnung nicht als aktiv.
- [ ] Test 6: GIVEN die Fixture enthält `Update` zu einer früheren `Alert` derselben Gemeinde WHEN die
  Warnungen ermittelt werden THEN erscheint die Warnung genau einmal (Update-Stand).
- [ ] Test 7: GIVEN die Fixture enthält eine Area mit Höhenband WHEN ein Punkt unabhängig von seiner
  Höhe in der Gemeinde liegt THEN wird die Warnung ausgegeben (Höhenband ignoriert, wie IT/AT/DE).
- [ ] Test 8 (Dedup/Tie-Break): GIVEN ein Punkt in den Alpen, für den CH-Feed (Warnung) und SLF
  (Lawinenstufe) liefern, mit echter Registrierungsreihenfolge WHEN die Warnungen über die Registry
  ermittelt werden THEN erscheinen beide als getrennte Gefahrenarten (kein Doppel-Chip, keine
  gegenseitige Verdrängung), und die Reihenfolge entspricht der Registrierung (CH vor SLF).
- [ ] Test 9 (Alarmweg Ende-zu-Ende bis Kanal-Auflösung): GIVEN eine CH-Warnung der Alarmstufe, die
  aus der Fixture über `MeteoAlarmFeedSource("CH")` und die echte Registry entsteht, UND ein Nutzer
  mit Empfängern auf allen vier Kanälen WHEN diese Warnung den geteilten Alarm-Pfad (Trip-Alarm und
  Ortsvergleichs-Alarm, echte Funktionen, kein Mock der Eigen-Annahme) bis zur Kanal-Auflösung
  durchläuft THEN wird sie nicht verworfen und die Auflösung liefert E-Mail, Telegram, SMS und
  Premium-SMS — dieselbe Kanalmenge wie für eine AT-Warnung derselben Stufe.
- [ ] Test 10 (Malformation): GIVEN ein einzelner andersförmiger Eintrag irgendwo in der Fixture
  WHEN ein Punkt mit korrekter Warnung abgefragt wird THEN erhält er seine Warnung und keinen
  Ausfallhinweis.
- [ ] Test 11 (Regression): GIVEN die bestehenden IT/AT/DE-Feed-Tests WHEN sie nach der Änderung laufen
  THEN bleiben sie unverändert grün.
- [ ] Test 12 (Live, Marker `live`, nur `/e2e-verify`/Staging): GIVEN der echte CH-Feed WHEN der Test
  daraus ein aktuell gewarntes Gemeinde-Polygon wählt (Punkt im Ring/Mittelpunkt) und `fetch()` an
  diesem Punkt aufruft THEN liefert die Quelle mindestens 1 Warnung, ohne Ausfall, innerhalb des
  Timeouts. Führt der Feed gerade keine aktuell gültige Warnung, ist das Ergebnis **SKIP mit Grund**,
  nicht PASS (leere Liste besteht den Test nicht).

## Acceptance Criteria

- **AC-1:** Given ein Wanderpunkt liegt in einer Schweizer Gemeinde mit einer amtlich aktiven
  Warnung, When die amtlichen Warnungen für diesen Punkt abgerufen werden, Then erscheint diese
  Warnung mit Warnstufe, Ereignisart und Gültigkeitszeitraum im Ergebnis.
  - Test: Test 1 oben.

- **AC-2:** Given ein Wanderpunkt liegt in der Schweiz und für seine Gemeinde besteht amtlich keine
  aktive Warnung, When die amtlichen Warnungen abgerufen werden, Then meldet das Ergebnis „keine
  Warnung" und NICHT „amtliche Warnungen nicht abrufbar".
  - Test: Test 2 oben.

- **AC-3:** Given der Schweizer Warndienst (Feed) ist zum Abrufzeitpunkt nicht erreichbar, When die
  amtlichen Warnungen für einen Punkt in der Schweiz abgerufen werden, Then meldet das Ergebnis
  „amtliche Warnungen aktuell nicht abrufbar" statt fälschlich eine warnungsfreie Lage zu zeigen.
  - Test: Test 3 oben.

- **AC-4:** Given ein Wanderpunkt liegt in einem Nachbarland (Konstanz, Bregenz, Como oder Chamonix),
  When die amtlichen Warnungen abgerufen werden, Then schweigt die Schweizer Quelle folgenlos —
  keine Schweizer Warnung, kein Schweizer Ausfallhinweis — weil sie erkennbar nicht zuständig ist.
  - Test: Test 4 oben.

- **AC-5:** Given eine amtliche Schweizer Warnung wurde offiziell aufgehoben (`Cancel`) oder durch eine
  neuere Fassung ersetzt (`Update`), When die Warnungen für den betroffenen Punkt abgerufen werden,
  Then erscheint die aufgehobene Warnung nicht als aktiv und die aktualisierte genau einmal. Die
  Entwarnung läuft unverändert über das Verschwinden bei gesunder Quelle (ADR-0090), ohne eigenen
  Schweizer Sonderweg.
  - Test: Tests 5 und 6 oben.

- **AC-6:** Given eine Schweizer Warnung gilt für ein Gebiet mit Höhenband (`altitude`/`ceiling`),
  When ein Wanderpunkt in der Gemeinde liegt, Then wird die Warnung unabhängig von der Höhe des
  Punkts ausgegeben (bewusst wie bei IT/AT/DE, siehe Known Limitations).
  - Test: Test 7 oben.

- **AC-7:** Given ein Punkt in den Schweizer Alpen, für den sowohl der Warnfeed (z. B. Wind/Gewitter)
  als auch der SLF-Lawinenbericht Daten führen, When die amtlichen Warnungen abgerufen werden, Then
  erscheinen beide als getrennte Gefahrenarten genau einmal, ohne dass eine die andere verdrängt oder
  verdoppelt, und die Reihenfolge folgt der Registrierung (Warnfeed vor SLF).
  - Test: Test 8 oben (belegt Ticket-AC „Dedup": andere Gefahrenart als SLF-Lawine).

- **AC-8:** Given eine Schweizer amtliche Warnung aus dem Feed erreicht die für Alarme maßgebliche
  Warnstufe, When sie den geteilten Alarm-Pfad eines Trip- oder Ortsvergleichs-Alarms durchläuft,
  Then erreicht sie bei der Kanal-Auflösung alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) wie
  eine österreichische Warnung derselben Stufe — ohne Kanal-Sonderweg.
  - Test: Test 9 oben (Ende-zu-Ende von der Fixture bis zur Kanal-Auflösung).

- **AC-9:** Given ein einzelner andersförmiger Eintrag im Schweizer Feed, When ein Punkt mit korrekter
  Warnung abgefragt wird, Then erhält er seine Warnung und keinen Ausfallhinweis.
  - Test: Test 10 oben.

- **AC-10:** Given die bestehenden Warnungen für Italien, Österreich und Deutschland, When deren
  Testfälle nach dieser Änderung erneut laufen, Then liefern sie unverändert dieselben Ergebnisse.
  - Test: Test 11 oben.

- **AC-11:** Given der echte Schweizer Feed auf Staging enthält eine aktuell gewarnte Gemeinde, When
  die Quelle für einen Punkt in dieser Gemeinde abgefragt wird, Then liefert sie mindestens eine
  Warnung, ohne Ausfallhinweis und innerhalb des Timeouts; gibt es gerade keine Warnung im Feed, ist
  das Ergebnis ein SKIP mit Grund und kein Bestehen. Das löst Ticket-AC-1 am echten Feed ein.
  - Test: Test 12 oben (Marker `live`, Staging-Nachweis).

## Abweichungen vom Ticket (#1442, Stand 31.07.)

- **Ticket-AC-2 (24h-Abrufbudget) ist gegenstandslos.** Das Budget-Gate und die kontingentierte
  EDR-Klasse sind mit #2266 zurückgebaut; der Feed `feeds.meteoalarm.org` ist kontingentfrei. Es gibt
  nur den 30-min-Cache (1800 s Erfolg / 60 s Fehler).
- **Bezugsweg Feed statt `api.meteoalarm.org`/MQTT.** #1445 hat den Feed-Weg etabliert; #1397 und
  #1445 sind erledigt, MQTT entfällt. Egress-Host bereits gelistet.
- **Zuordnung per Punkt-in-Polygon statt Geocode.** Der Schweizer Feed hat keinen Geocode (Messung
  2026-10-28: 715 Gemeinde-Polygone, kein `EMMA_ID`); der Zonen-Weg `_emma_ids_for_alert` greift nicht.
- **Ticket-AC-3 (Dedup) = andere Gefahrenart als SLF-Lawine.** Die CH-Quelle liefert Wetterwarnungen
  (`awareness_type` Wind/Gewitter/…), SLF die Lawinenstufe (`avalanche_bulletin`) — per Test 8
  belegt (AC-7), kein gemeinsamer Chip.
- **Label `needs-po-approval`:** Die Quelle (MeteoAlarm-Feed) ist bereits genehmigt; der Länderscope
  CH wird mit der Spec-Freigabe durch den PO bestätigt.
- **Ticket-Update (Schritt dieses Workflows):** Nach der Freigabe aktualisiert der Orchestrator den
  Text von #1442 (Budget streichen, Feed-Weg, Polygon-Befund) und setzt/entfernt das Label
  `needs-po-approval`. Die Datei `docs/specs/data_sources.md` ist Teil des Scopes (siehe Tabelle).

## Known Limitations

- **Höhenband ignoriert.** `altitude`/`ceiling` der Area werden nicht ausgewertet (Entscheidung, wie
  bei IT/AT/DE): eine Warnung gilt für den ganzen Gemeinde-Umriss, auch wenn sie nur für ein
  Höhenband amtlich ausgegeben ist. Akzeptabel, weil die Warnung amtlich der Gemeinde zugeordnet ist,
  der Chip Gemeindename und Quelle zeigt (der Nutzer sieht, woher sie stammt) und die Wahl bewusst
  konservativ ist: lieber eine Warnung zu viel als zu wenig.
- **Vaduz/Liechtenstein zählt als CH.** `covers()` nutzt die SLF-Regionspolygone, die FL einschließen;
  vernachlässigbar, kein Fehlalarm-Risiko, da der Feed dort keine Polygone führt (Punkt ohne Treffer =
  keine Warnung).
- **Zuständigkeit primär über SLF-Regionspolygone, Fallback über Feed-Polygone.** Ein Schweizer Punkt
  außerhalb der SLF-Regionen gilt nur dann als zuständig, wenn der gecachte Feed ihn in einem Polygon
  enthält; ohne Cache und ohne Feed-Treffer schweigt die Quelle (kein Ausfallhinweis).
- **Gemeinde-Auflösung.** Warnungen gelten pro Gemeinde-Polygon; nur aktuell gewarnte Gebiete stehen
  im Feed (kein Treffer = keine Warnung).
- **Latenz und Weitergabe.** EUMETNET-Weitergabe mit 5–10 min Verzug (#2266, Prüfpunkt 4); der Feed
  kommt unkomprimiert (5,6 MB, ca. 240 MB/Tag je Umgebung bei 30-min-Takt, Rahmen ADR-0074).
- **Entwarnung** nur über Verschwinden bei gesunder Quelle (ADR-0090), nicht über `AllClear`.

## Out of Scope

- NO/SE/FI (Slice S2), weitere Länder (S3).
- Höhenband-Auswertung, Gemeinde-Teilflächen jenseits des Umrisses.
- Neue Egress-Hosts, neue Datendateien (CH-Geometrie wird aus SLF/Feed gewonnen).
- Änderung von TTL (1800 s/60 s) oder Timeout (15 s).
- (Kein offener Rest: `data_sources.md` steht im Scope, das Ticket-Update ist ein Workflow-Schritt
  nach der Freigabe, siehe „Abweichungen vom Ticket".)

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neu. Es gelten ADR-0039 (Bezugsweg Feed), ADR-0041 (Zuständigkeit lokal), ADR-0074
  (Auffrischraster) und ADR-0090 (Entwarnung über Verschwinden) unverändert.
- **Rationale:** Punkt-in-Polygon gegen Feed-Polygone ist eine Implementierungsvariante der
  Zuordnung, keine Grundsatzentscheidung; Feed-Weg und Cache-Raster sind bereits entschieden.

## Changelog

- 2026-10-29: Initial spec created (Issue #1442 S1, Analyse-Grundlage
  `docs/context/feat-1442-s1-meteoalarm-ch.md`).
