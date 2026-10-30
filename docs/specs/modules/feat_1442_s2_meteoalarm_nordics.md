---
entity_id: feat_1442_s2_meteoalarm_nordics
type: feature
created: 2026-10-29
updated: 2026-10-29
status: approved
version: "1.0"
tags: [official-alerts, meteoalarm, norway, sweden, finland, polygon, geocode, warn-egress]
workflow: feat-1442-s2-meteoalarm-nordics
---

<!-- Issue #1442, Slice S2 (NO, SE, FI). S1 (CH) ist live (PR #2637). S3 folgt als eigener Workflow. Vorlage: feat_1442_s1_meteoalarm_ch.md. -->

# MeteoAlarm Skandinavien: Norwegen, Schweden, Finnland über den kontingentfreien Feed

## Approval

- [x] Approved

## Purpose

Punkte in Norwegen, Schweden und Finnland bekommen heute keine amtlichen Unwetterwarnungen. Die
Registry kennt Italien, Österreich, Deutschland und (seit S1) die Schweiz. Diese Spec registriert
`MeteoAlarmFeedSource("NO")`, `("SE")` und `("FI")` und bezieht die amtlichen Warnungen aus dem
kontingentfreien Feed `feeds.meteoalarm.org`.

Messung 2026-10-29 (live): NO 200, 592 KB, 69 Warnungen, Polygone (mit `altitude`/`ceiling`), kein
Geocode; SE 200, 402 KB, 28 Warnungen, Polygone, kein Geocode; FI 200, 103 KB, 27 Warnungen, **nur
`EMMA_ID`, kein Polygon** (Land `FI029`, `FI032`, `FI043`; Seegebiete `FI801`–`FI813`). Daraus zwei
Teile:

- **Teil A (NO, SE):** Punkt-in-Polygon direkt gegen die Feed-Polygone — derselbe Weg wie CH, der
  CH-Code wird auf einen Länderschlüssel verallgemeinert (kein zweiter Code).
- **Teil B (FI):** Geocode-Weg (`EMMA_ID`) wie IT/AT/DE. Dafür fehlt eine eingecheckte
  Zonengeometrie; ihre Beschaffung ist der erste Arbeitsschritt (Spike-Befund unten).

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py` (MODIFY)
- **Identifier:** `_FEED_PATHS`, `_GEOCODE_NAME`, `MeteoAlarmFeedSource.__init__(country)`, `covers()`,
  `fetch()`, `_ch_index`/`_ch_index_memo`, `_hit_area`, `_alerts_for_point_polygon`, `_covers_ch`,
  `_fetch_ch` (alle auf Länderschlüssel verallgemeinern)

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`). Kein Go-, kein
> Frontend-Anteil. Der Host `feeds.meteoalarm.org` ist in `internal/egress/inventory.go` und
> `src/app/egress_guard.py` bereits geführt; kein neuer Host.

> **Mandantentrennung:** Keine Nutzerdaten im Pfad. Die Quelle ist global (Cache-Schlüssel =
> Ländercode, Eingang nur `lat`/`lon` eines beobachteten Orts). Ein Zwei-Nutzer-Test ist
> gegenstandslos (gleiche Begründung wie S1 und #1681); die Nutzerbindung geschieht im geteilten
> Alarm-Pfad.

## Spike-Befund Finnland (2026-10-29, vor dieser Spec gemessen)

- FMI-WFS `opendata.fmi.fi/wfs`: `describeStoredQueries` antwortet, enthält aber **keine**
  Warnzonen-/Gebiets-Abfrage.
- FMI-CAP `alerts.fmi.fi/cap/` (CC BY 4.0): jede Warnung trägt `area` mit `areaDesc` und **Polygon**,
  aber als Kennung `METAREA` (Seegebiete, z. B. `B5W`), **nicht** `EMMA_ID`. Eine fertige Zuordnung
  `EMMA_ID` → Geometrie liegt dort nicht vor.
- Folge: Teil B beginnt mit einer Geometrie-Beschaffung (siehe Implementation Details 7). Ist sie
  nicht in vertretbarem Umfang möglich, **bleibt FI in S2 offen und wird nicht als erledigt
  gemeldet** (AC-12).

## Estimation

- **Teil A (NO+SE):** Produktiv ca. +90 LoC (Verallgemeinerung CH + zwei Länder + zwei Registrierungen).
- **Teil B (FI):** Produktiv ca. +80 LoC plus Datendatei (Daten zählen nicht zum LoC-Limit).
- **Gesamt Produktiv:** ca. 170 LoC (unter 250). Effort: medium. Risk: MEDIUM — Umbau des gerade live
  gegangenen CH-Wegs (S1-Tests müssen grün bleiben), FI-Geometriequelle.

### Affected Files (Scope)

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS` +NO/SE/FI; `Literal` erweitern; CH-Polygonweg per Länderschlüssel; `covers()`/`fetch()` je Land; Drift-Log `meteoalarm_feed:<Land>` |
| `src/services/official_alerts/__init__.py` | MODIFY | drei Registrierungen nach CH, vor `DpcSource`, mit Reihenfolge-Kommentar |
| `src/services/official_alerts/data/` | CREATE | vereinfachte, großzügige Landesumrisse NO/SE/FI (Quelle Natural Earth, gemeinfrei) für `covers()`; für FI zusätzlich Zonengeometrie `FI0xx`/`FI8xx`; `data/README.md` mit Herkunft und Lizenz |
| `src/services/official_alerts/geo_ray_cast.py` | REUSE | `_point_in_ring` unverändert |
| `src/services/official_alerts/meteoalarm.py` | REUSE | CAP-Mapper wählt `de*`, Fallback `en*` — greift als `en-GB` |
| `tests/fixtures/meteoalarm_feed/` | CREATE | gekürzte echte Proben NO/SE/FI + README (Herkunft, synthetische Fälle gekennzeichnet) |
| `tests/tdd/test_meteoalarm_feed_nordics.py` | CREATE | Kern-Verhaltenstests ohne Netz |
| `tests/tdd/test_meteoalarm_feed_nordics_live.py` | CREATE | Live-Tests (Marker `live`) |
| `tests/tdd/test_meteoalarm_feed_ch.py` | REUSE | S1-Tests laufen unverändert grün (Regression) |
| `docs/specs/data_sources.md` | MODIFY | PENDING-Antrag nachführen (S2 Feed-Weg, Budget gegenstandslos) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `warn_egress.cached_fetch` / `mark_fetch_incomplete` / `mark_not_covered` / `log_zone_drift` | module | Abruf, Drei-Zustände-Regel, Drift-Log |
| `geo_ray_cast._point_in_ring` | module | Punkt-in-Polygon |
| `meteoalarm._group_and_map_info_entries` | module | geteilter CAP-Mapper |
| `base.get_official_alerts_with_status` | module | wertet `unavailable` über alle Quellen |
| Alarm-/Briefing-Pfade (`trip_alert`, `comparison_engine`, `compare_official_alert`, `trip_report_scheduler`) | module | konsumieren `OfficialAlert` unverändert |
| `docs/adr/0039`, `0041`, `0074`, `0090` | adr | Feed-Weg, lokale Zuständigkeit, Auffrischraster, Entwarnung über Verschwinden |

## Implementation Details

1. **Verallgemeinerung statt Kopie.** Die fest auf `"CH"` verdrahteten Stellen (`_cache.get("CH")`,
   `_ch_index_memo` als einzelner globaler Schlüssel, Drift-Log `meteoalarm_feed:CH`, `_covers_ch`,
   `_fetch_ch`) werden auf den Ländercode der Instanz umgestellt. CH verhält sich danach
   byte-gleich wie vorher (AC-10).
2. **NO/SE Punkt-in-Polygon.** Wie CH: BBox-Vorfilter je Area, Index zusammen mit dem geparsten Feed
   30 min gecacht (Cache-Schlüssel = Ländercode, TTL 1800 s Erfolg / 60 s Fehler, Timeout unverändert).
   Höhenband (`altitude`/`ceiling`) wird ignoriert (wie IT/AT/DE/CH).
3. **`covers()` lokal und großzügig.** Anders als CH gibt es für NO/SE keine vorhandene
   Regionsgeometrie. „Nur gecachter Feed" würde den ersten Abruf nie auslösen. Daher eingecheckte,
   bewusst aufgeweitete Landesumrisse (Küste!). Ein Falsch-Ja kostet nur einen Abruf mit Ergebnis
   „keine Warnung"; ein Falsch-Nein wäre stilles Schweigen — der Umriss wird deshalb lieber zu groß.
   Zusätzlich gilt wie bei CH der Fallback: Punkt im gecachten Feed-Polygon ⇒ zuständig. Kein Netz in
   `covers()`.
4. **Grenzpunkte.** Umrisse überlappen sich (NO/SE/FI sowie DK, DE, EE, RU). Zuständig ist jede
   Quelle, deren Umriss den Punkt enthält; jede liefert nur Warnungen, deren Feed-Polygon den Punkt
   enthält. Eine Warnung erscheint daher nie doppelt (Polygone verschiedener Länder überlappen nicht
   inhaltlich), und es gibt keine Nationalquelle für NO/SE/FI, gegen die dedupliziert werden müsste.
5. **Drei Zustände, Cancel/Update, Malformation** wie S1: nicht zuständig ⇒ `mark_not_covered()`;
   zuständig, Feed gesund, kein Treffer ⇒ leere Liste ohne Ausfall; Feed nicht abrufbar/unlesbar ⇒
   `mark_fetch_incomplete()`. Einzelner andersförmiger Eintrag färbt nicht jeden Ort als Ausfall.
   Entwarnung nur über Verschwinden (ADR-0090).
6. **Sprache.** Die Feeds tragen `no`/`en-GB` (NO), `sv-SE`/`en-GB` (SE), `fi-FI`/`sv-SE`/`en-GB` (FI).
   Der Mapper nimmt `de*`, sonst `en*` ⇒ `en-GB`. Das wird per Test belegt, nicht angenommen.
7. **Teil B FI.** Zuerst Geometrie beschaffen: Zuordnung Punkt → `FI0xx` (Land) bzw. `FI8xx` (See) aus
   einer lizenzierten, aufgezeichneten Quelle (Kandidaten: FMI-Open-Data CC BY 4.0; alternativ
   Landkreis-/Seegebiets-Polygone mit manuell belegter Zuordnung zu den EMMA_ID). Eingecheckt wird
   die Geometrie mit Herkunft, Datum und Lizenz in `data/README.md`. Danach läuft FI über den
   bestehenden Zonenweg (`_alerts_for_zone` mit `EMMA_ID`). Kein neuer Live-Zugriff auf FMI zur
   Laufzeit. Gelingt die Zuordnung der Landzonen (`FI029`, `FI032`, `FI043` und die übrigen im Feed
   vorkommenden) nicht belegbar, wird FI nicht registriert (AC-12).
8. **Registrierung.** Nach `MeteoAlarmFeedSource("CH")`, vor `DpcSource`/SLF. Gewitter-Tie-Break
   „zuerst registriert gewinnt" (#1427 S2); Reihenfolge NO, SE, FI.
9. **Budget.** Der Feed ist kontingentfrei; Last = höchstens ein Abruf je Land und 30 min (NO 592 KB
   am größten, FI 103 KB). Ticket-AC-2 (24h-Abrufbudget) ist gegenstandslos.

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in oder nahe NO, SE oder FI.
- **Output:** unverändert `list[OfficialAlert]` über `get_official_alerts_for_location()` /
  `get_official_alerts_with_status()`, `source` bleibt `"meteoalarm"`.
- **Side effects:** je Land ein Feed-Abruf pro Auffrischungsfenster (30 min).

## Test Plan

### Automated Tests (TDD RED)

Kern-Tests ohne Netz gegen `tests/fixtures/meteoalarm_feed/` (gekürzte **echte** Aufzeichnungen je
Land; `Cancel`, Loch/Mehrfachring und fehlende Sprache sind synthetisch aus einem echten Eintrag
abgeleitet und im README gekennzeichnet). Datei `test_meteoalarm_feed_nordics.py`.

- [ ] Test 1 (NO/SE Treffer): Punkt in einem gewarnten Polygon in Norwegen bzw. Schweden ⇒ genau diese
  Warnung mit Stufe, Art, Zeitraum.
- [ ] Test 2 (kein Treffer): Punkt in NO/SE ohne Treffer-Polygon ⇒ leere Liste, `unavailable=False`.
- [ ] Test 3 (ruhig/Ausfall): Feed-Abruf schlägt fehl ⇒ `unavailable=True` für einen Punkt in NO/SE/FI.
- [ ] Test 4 (Zuständigkeit, Messung): ≥12 Rand-/Küstenpunkte je Land (z. B. Kirkenes, Tromsø, Lofoten,
  Oslo, Bergen, Kiruna, Malmö, Haparanda, Helsinki, Utsjoki, Mariehamn, Hanko) ⇒ `covers()` überall
  `True`; Nachbarland-Punkte (Kopenhagen, Flensburg, Tallinn, Murmansk) ⇒ `False`, kein Ausfallhinweis,
  keine Warnung.
- [ ] Test 5 (Cancel/Update): `Cancel` ⇒ nicht aktiv; `Update` ⇒ genau einmal.
- [ ] Test 6 (Höhenband): Warnung mit `altitude`/`ceiling` wird unabhängig von der Punkthöhe ausgegeben.
- [ ] Test 7 (Sprachfallback): Feed-Eintrag ohne `de*` ⇒ Text kommt aus `en-GB`, nicht leer und nicht
  aus `no`/`sv-SE`/`fi-FI`.
- [ ] Test 8 (Malformation): ein andersförmiger Eintrag ⇒ Punkte mit korrekter Warnung bekommen sie ohne
  Ausfallhinweis.
- [ ] Test 9 (Grenzpunkt): Punkt nahe der NO/SE-Grenze mit Warnung nur in einem Land ⇒ genau diese
  Warnung, keine doppelte.
- [ ] Test 10 (Alarmweg Ende-zu-Ende): Warnung der Alarmstufe aus der Fixture über echte Registry bis zur
  Kanal-Auflösung eines Nutzers mit Empfängern auf allen vier Kanälen ⇒ E-Mail, Telegram, SMS,
  Premium-SMS wie bei einer AT-Warnung gleicher Stufe (Trip und Ortsvergleich).
- [ ] Test 11 (FI Land): Punkt in Pohjanmaa/Varsinais-Suomi/Ahvenanmaa mit Warnung für `FI029`/`FI032`/
  `FI043` ⇒ Warnung erscheint; Punkt in anderer Zone ⇒ nicht.
- [ ] Test 12 (FI See): Küstenpunkt in einem Seegebiet mit Warnung `FI80x` ⇒ Warnung erscheint.
- [ ] Test 13 (Regression): S1-CH-Tests und IT/AT/DE-Feed-Tests laufen unverändert grün; CH-Ergebnis für
  Fixture-Punkte unverändert.
- [ ] Test 14 (Live, Marker `live`, nur `/e2e-verify`): je Land ein aktuell gewarntes Gebiet aus dem
  echten Feed ⇒ mindestens 1 Warnung, ohne Ausfall, im Timeout. Führt ein Feed gerade keine gültige
  Warnung, ist das Ergebnis SKIP mit Grund, nicht PASS.

## Acceptance Criteria

- **AC-1:** Given ein Wanderpunkt liegt in Norwegen oder Schweden in einem Gebiet mit amtlich aktiver
  Warnung, When die amtlichen Warnungen abgerufen werden, Then erscheint diese Warnung mit Warnstufe,
  Ereignisart und Gültigkeitszeitraum im Ergebnis.
  - Test: Test 1.

- **AC-2:** Given ein Wanderpunkt liegt in Norwegen, Schweden oder Finnland und für sein Gebiet besteht
  amtlich keine aktive Warnung, When die Warnungen abgerufen werden, Then meldet das Ergebnis „keine
  Warnung" und NICHT „amtliche Warnungen nicht abrufbar".
  - Test: Test 2.

- **AC-3:** Given der Warndienst (Feed) ist zum Abrufzeitpunkt nicht erreichbar, When die Warnungen für
  einen Punkt in Norwegen, Schweden oder Finnland abgerufen werden, Then meldet das Ergebnis „amtliche
  Warnungen aktuell nicht abrufbar" statt fälschlich eine warnungsfreie Lage zu zeigen.
  - Test: Test 3.

- **AC-4:** Given ein Wanderpunkt liegt in Norwegen, Schweden oder Finnland — auch an Küste und Landesrand
  (Lofoten, Haparanda, Hanko, Mariehamn) —, When die Zuständigkeit geprüft wird, Then ist die jeweilige
  Landesquelle zuständig; Given ein Punkt liegt in einem Nachbarland (Kopenhagen, Flensburg, Tallinn,
  Murmansk), Then schweigt die Quelle folgenlos, ohne Warnung und ohne Ausfallhinweis.
  - Test: Test 4.

- **AC-5:** Given eine Warnung wurde aufgehoben (`Cancel`) oder durch eine neuere Fassung ersetzt
  (`Update`), When die Warnungen abgerufen werden, Then erscheint die aufgehobene nicht als aktiv und
  die aktualisierte genau einmal; die Entwarnung läuft über das Verschwinden bei gesunder Quelle
  (ADR-0090) ohne Sonderweg.
  - Test: Test 5.

- **AC-6:** Given eine Warnung gilt für ein Gebiet mit Höhenband, When ein Wanderpunkt im Gebiet liegt,
  Then wird sie unabhängig von der Höhe des Punkts ausgegeben (bewusst wie IT/AT/DE/CH).
  - Test: Test 6.

- **AC-7:** Given der Feed liefert Texte in Landessprache und Englisch (`no`/`sv-SE`/`fi-FI` plus
  `en-GB`), When die Warnung ausgegeben wird, Then ist ihr Text vorhanden und stammt aus `en-GB`,
  nicht leer.
  - Test: Test 7.

- **AC-8:** Given ein einzelner andersförmiger Eintrag im Feed, When ein Punkt mit korrekter Warnung
  abgefragt wird, Then erhält er seine Warnung und keinen Ausfallhinweis.
  - Test: Test 8.

- **AC-9:** Given ein Punkt nahe einer Landesgrenze (Norwegen/Schweden), When nur eines der Länder dort
  eine Warnung führt, Then erscheint genau diese Warnung einmal, ohne Doppel-Chip.
  - Test: Test 9.

- **AC-10:** Given die bestehenden Warnungen für Italien, Österreich, Deutschland und die Schweiz, When
  deren Testfälle nach dieser Änderung erneut laufen, Then liefern sie unverändert dieselben
  Ergebnisse.
  - Test: Test 13.

- **AC-11:** Given eine Warnung aus NO, SE oder FI erreicht die für Alarme maßgebliche Warnstufe, When
  sie den geteilten Alarm-Pfad eines Trip- oder Ortsvergleichs-Alarms durchläuft, Then erreicht sie bei
  der Kanal-Auflösung alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) wie eine österreichische
  Warnung derselben Stufe.
  - Test: Test 10.

- **AC-12:** Given ein Wanderpunkt liegt in Finnland (Land oder Küstenmeer) und der Feed führt für die
  zugehörige Zone (`FI029`, `FI032`, `FI043`, `FI801`–`FI813`) eine aktive Warnung, When die Warnungen
  abgerufen werden, Then erscheint sie. Given die Zonengeometrie lässt sich nicht belegbar den
  Feed-Kennungen zuordnen, Then wird Finnland NICHT registriert und in der Auslieferung ausdrücklich
  als offen gemeldet, nicht als erledigt.
  - Test: Tests 11 und 12.

- **AC-13:** Given die echten Feeds von Norwegen, Schweden und Finnland auf Staging mit je einer aktuell
  gewarnten Zone, When die Quelle für einen Punkt in dieser Zone abgefragt wird, Then liefert sie
  mindestens eine Warnung ohne Ausfallhinweis im Timeout; ohne aktuelle Warnung im Feed ist das
  Ergebnis ein SKIP mit Grund, kein Bestehen.
  - Test: Test 14.

## Abweichungen vom Ticket (#1442, Stand 31.07.)

- **Ticket-AC-2 (24h-Abrufbudget) gegenstandslos:** Budget-Gate und EDR-Klasse sind mit #2266
  zurückgebaut; `feeds.meteoalarm.org` ist kontingentfrei, es gilt nur der 30-min-Cache.
- **Bezugsweg Feed statt `api.meteoalarm.org`/MQTT** (siehe #1445, ADR-0039).
- **Zuordnung:** NO/SE per Punkt-in-Polygon (kein Geocode im Feed), FI per `EMMA_ID` mit neu
  eingecheckter Geometrie.
- **Ticket-AC-3 (Dedup):** Für NO/SE/FI gibt es keine überlappende Nationalquelle; AC-9 belegt, dass an
  Grenzpunkten keine Doppelanzeige entsteht.
- **Ticket-AC-1 (Live-Test):** gilt je Land (AC-13); Teil B kann offen bleiben (AC-12).
- **Ticket-Update nach Freigabe:** Orchestrator aktualisiert den Text von #1442 (Budget streichen,
  Feed-Weg, FI-Befund). `docs/specs/data_sources.md` ist im Scope.

## Known Limitations

- **Höhenband ignoriert** (wie IT/AT/DE/CH): lieber eine Warnung zu viel als zu wenig.
- **Landesumrisse großzügig:** an der Küste kann `covers()` für einen Punkt knapp auf See `True`
  liefern; Folge ist höchstens ein Abruf mit „keine Warnung".
- **Latenz:** EUMETNET-Weitergabe mit 5–10 min Verzug; Feeds unkomprimiert (NO 592 KB, SE 402 KB,
  FI 103 KB), Rahmen ADR-0074.
- **Entwarnung** nur über Verschwinden bei gesunder Quelle (ADR-0090).
- **FI-Geometrie statisch:** Änderungen der Zonen bei FMI/EUMETNET erkennt `log_zone_drift`, die Datei
  wird dann manuell nachgeführt.

## Out of Scope

- Weitere Länder (Slice S3: ES, PT, UK, NL/BE, PL).
- Höhenband-Auswertung, Teilflächen.
- Neue Egress-Hosts, Laufzeit-Zugriff auf FMI, Änderung von TTL (1800 s/60 s) und Timeout (15 s).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neu. Es gelten ADR-0039, 0041, 0074 und 0090 unverändert.
- **Rationale:** Polygon- und Geocode-Weg sind bestehende Implementierungsvarianten; Länderschlüssel
  statt fester Konstante ist Verallgemeinerung, keine Grundsatzentscheidung.

## Changelog

- 2026-10-29: Initial spec created (Issue #1442 S2, Analyse-Grundlage
  `docs/context/feat-1442-s2-meteoalarm-nordics.md`).
