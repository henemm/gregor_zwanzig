---
entity_id: feat_1442_s3a_meteoalarm_pt_nl_pl
type: feature
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, portugal, netherlands, poland, zone, emma-id, warn-egress]
workflow: feat-1442-s3-rest-eu
---

<!-- Issue #1442, Slice S3a (PT, NL, PL). S1 (CH) und S2 (NO/SE/FI) sind live. S3 Spanien liegt gebaut auf dem Branch origin/worktree-greedy-skipping-raven und ist Vorbedingung. S3b (UK) und S3c (BE) sind Folge-Workflows. Vorlage: feat_1442_s2_meteoalarm_nordics.md. Analyse: docs/context/feat-1442-s3-rest-eu.md. -->

# MeteoAlarm Portugal, Niederlande, Polen über den kontingentfreien Feed

## Approval

- [ ] Approved

## Purpose

Punkte in Portugal, den Niederlanden und Polen bekommen heute keine amtlichen Unwetterwarnungen.
Diese Spec registriert `MeteoAlarmFeedSource("PT")`, `("NL")` und `("PL")` und bezieht die Warnungen
aus dem kontingentfreien Feed `feeds.meteoalarm.org`. Alle drei Feeds tragen ausschließlich die
Zonenkennung `EMMA_ID` (kein Polygon, kein NUTS2); sie laufen deshalb über den Zonenweg, den
Spanien auf `main` verallgemeinert (Punkt → Zonen-ID über eingecheckte Geometrie, wie FI/ES).
Es gibt keinen neuen Algorithmus, nur Konfiguration, drei Zonendateien und die Registrierung.

Messung 2026-10-30 (live): PT 200, 9 KB, 5 Warnungen, 5 Zonen (`PT001`…`PT024`), `pt-PT`/`en-GB`;
NL 200, 1,4 MB, 754 Warnungen (alle Stufe grün/„Minor"), 15 Zonen (`NL007`…), `nl-NL`/`en-GB`;
PL 200, 371 KB, 156 Warnungen, 126 Zonen (`PL0202`…), `pl-PL`/`en-GB`. In `geocodes.json` (39 MB)
liegen PT 25, NL 20, PL 385 Features, ohne Lücke gegenüber den Feed-Zonen.

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py` (MODIFY)
- **Identifier:** `_FEED_PATHS`, `_GEOCODE_NAME`, `_zone_mappers`, `MeteoAlarmFeedSource.__init__(country)`
  (`Literal`), ggf. `_alerts_for_zone` (Update/Cancel, AC-7)

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`). Kein Go-, kein
> Frontend-Anteil. Der Host `feeds.meteoalarm.org` ist in `internal/egress/inventory.go` und
> `src/app/egress_guard.py` bereits geführt; kein neuer Host.

> **Mandantentrennung:** Keine Nutzerdaten im Pfad. Die Quelle ist global (Cache-Schlüssel =
> Ländercode, Eingang nur `lat`/`lon` eines beobachteten Orts). Ein Zwei-Nutzer-Test ist
> gegenstandslos (gleiche Begründung wie S1/S2/#1681); die Nutzerbindung geschieht im geteilten
> Alarm-Pfad.

> **Kanäle:** Alle vier (E-Mail, Telegram, SMS, Premium-SMS) ohne Sonderlogik, Trip UND
> Ortsvergleich, weil nur die Registry erweitert wird (Epic #2133, ADR-0095). Trip/Ortsvergleich-
> Teilung: Es entsteht kein Frontend- oder Editor-Baustein, daher kein Pendant-Thema.

## Vorbedingung (harte Abhängigkeit)

Die Spanien-Scheibe (Branch `origin/worktree-greedy-skipping-raven`, Commits `904d33c6c` RED,
`dcfa0bb79` GREEN, Adversary VERIFIED, Workflow `feat-1442-s3-meteoalarm-spanien`) muss **vor Phase 5**
auf `main` liegen (PR, CI 6/6, Deploy, Selftest). Sie liefert die Verallgemeinerung `_zone_mappers`,
`_zones_for_point(country)`, `_known_zones(country)`, `_fetch_zones(country)` und die Registrierung
von ES. Diese Spec baut darauf auf und führt **keine zweite Verallgemeinerung** ein. Ist ES zu
Beginn von Phase 5 nicht auf `main`, stoppt die Implementierung.

## Estimated Scope

- **LoC:** Produktiv ca. +40/-5 (Daten zählen nicht), Tests ca. +250
- **Files:** ca. 12 (3 Datendateien, 3 Fixtures)
- **Effort:** low–medium. Risk: MEDIUM (Grenzgeometrie, Update/Cancel im Zonenweg, ungeklärte Lizenz)

### Affected Files (Scope)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS` (+PT/NL/PL), `_GEOCODE_NAME` (`EMMA_ID`), je ein Eintrag in `_zone_mappers`, `Literal` im Konstruktor; veraltete Länder-Docstrings korrigieren; ggf. Update/Cancel-Ergänzung (AC-7) |
| `src/services/official_alerts/data/meteoalarm_zones_PT.geojson.json` | CREATE | Auszug aus MeteoAlarm `geocodes.json`, `properties.id` = EMMA_ID |
| `src/services/official_alerts/data/meteoalarm_zones_NL.geojson.json` | CREATE | dito |
| `src/services/official_alerts/data/meteoalarm_zones_PL.geojson.json` | CREATE | dito (ca. 273 KB vereinfacht) |
| `src/services/official_alerts/data/README.md` | MODIFY | Abschnitte PT/NL/PL: Herkunft, sha256, Vereinfachung, 1:1-Abgleich Feed-Zonen ↔ Datei, Lizenzvermerk |
| `src/services/official_alerts/__init__.py` | MODIFY | Registrierung PT → NL → PL nach ES, vor `DpcSource`, mit Reihenfolge-Kommentar |
| `docs/specs/data_sources.md` | MODIFY | PT/NL/PL in den gebündelten `geocodes.json`-Lizenzantrag (wie FI/ES) |
| `tests/fixtures/meteoalarm_feed/feed_portugal_sample.json`, `feed_netherlands_sample.json`, `feed_poland_sample.json` + `README.md` | CREATE/MODIFY | gekürzte echte Proben; synthetische Fälle gekennzeichnet |
| `tests/tdd/test_meteoalarm_feed_pt_nl_pl.py` | CREATE | Kern-Verhaltenstests ohne Netz, Land parametrisiert |
| `tests/tdd/test_meteoalarm_feed_pt_nl_pl_live.py` | CREATE | Live-Tests (Marker `live`, nur `/e2e-verify`) |
| `tests/tdd/test_meteoalarm_feed_es.py` | MODIFY | Reihenfolge-/Länderprüfung (ac9/ac12) erweitern statt brechen |
| `src/services/official_alerts/meteoalarm.py` | REUSE | CAP-Mapper; Stufe-1-Filter (`level < 2: continue`, Z. 178–180), Sprachwahl `de*` → `en*` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Spanien-Scheibe (`origin/worktree-greedy-skipping-raven`) | branch | Verallgemeinerter Zonenweg, Voraussetzung |
| `warn_egress.cached_fetch` / `mark_fetch_incomplete` / `mark_not_covered` / `log_zone_drift` | module | Abruf, Drei-Zustände-Regel, Drift-Wächter |
| `region_mapper.RegionMapper.regions_at` | module | Punkt → Zonen-IDs |
| `meteoalarm._group_and_map_info_entries` | module | geteilter CAP-Mapper |
| `base.get_official_alerts_with_status` | module | wertet `unavailable` über alle Quellen |
| Alarm-/Briefing-Pfade (`trip_alert`, `comparison_engine`, `compare_official_alert`, `trip_report_scheduler`) | module | konsumieren `OfficialAlert` unverändert |
| `docs/adr/0039`, `0041`, `0074`, `0090`, `0095` | adr | Feed-Weg, lokale Zuständigkeit, Auffrischraster, Entwarnung über Verschwinden, Kanalparität |

## Implementation Details

1. **Konfiguration.** `_FEED_PATHS` erhält `feeds-portugal`, `feeds-netherlands`, `feeds-poland`;
   `_GEOCODE_NAME` jeweils `EMMA_ID`; `_zone_mappers` je Land den `RegionMapper` auf die eigene
   Zonendatei; `Literal` im Konstruktor um PT/NL/PL erweitert. Veraltete Docstrings (Länderlisten)
   werden mitkorrigiert.
2. **Zonendateien.** Je Land ein Auszug aus MeteoAlarm `geocodes.json` (`properties.id` = EMMA_ID),
   nach dem ES-Rezept aus `data/README.md`. Belegt wird ein 1:1-Abgleich: jede im Feed vorkommende
   Zonen-ID steht in der Datei (PT 5/25, NL 15/20, PL 126/385 Features; 0 Lücken). Herkunft, sha256
   von `geocodes.json`, Vereinfachungstoleranz und Abgleich stehen in `data/README.md`. Zur Laufzeit
   wird nichts nachgeladen.
3. **Registrierung** PT → NL → PL direkt nach ES, vor `DpcSource` (gilt für den Gewitter-Tie-Break
   „zuerst registriert gewinnt", #1427 S2). Belgien wird **nicht** registriert (siehe Out of Scope).
4. **NL-Grünstufe.** 754 NL-Warnungen sind fast alle Stufe grün. Der geteilte CAP-Mapper verwirft
   Stufe 1 bereits (`meteoalarm.py` Z. 178–180). Es entsteht weder Alarm noch Briefing-Zeile; das
   wird per Test belegt, nicht angenommen. Kosten: nur Parse-Last (1,4 MB je 30 min, wie IT/DE).
5. **Drei Zustände.** Punkt außerhalb aller Zonen des Landes ⇒ `mark_not_covered()`; Zone getroffen,
   Feed gesund, keine Warnung ⇒ leere Liste ohne Ausfall; Feed nicht abrufbar/unlesbar ⇒
   `mark_fetch_incomplete()`. Entwarnung nur über Verschwinden (ADR-0090).
6. **Küstenort und Grenzen.** Ein Küstenort liegt in Land- und Seezone; `_alerts_for_zone` nimmt die
   Zonen-Menge, jede Warnung zählt einmal. An Grenzen kann `covers()` für zwei Länder wahr sein
   (vereinfachte Zonen überlappen). Das ist folgenlos, weil jeder Feed nur Warnungen mit den
   Zonen-IDs seines Landes führt; das Nachbarland liefert für den Punkt keine Warnung und keinen
   Ausfall. Je Grenzpaar ein Test (PT/ES, NL/DE, NL/BE, PL/DE).
7. **Update/Cancel im Zonenweg (zu prüfen).** `_alerts_for_zone` kennt kein `superseded` (nur der
   Polygonweg wertet `_referenced_ids` aus). In Phase 5 wird an den echten PL/NL-Proben geprüft, ob
   eine ersetzte (`Update`) oder aufgehobene (`Cancel`) Warnung stehen bleibt oder doppelt erscheint.
   Zeigt sich das, kommt eine **kleine gemeinsame Ergänzung** in den Zonenweg (wirkt auch für FI/ES)
   mit Test; zeigt es sich nicht, wird der Befund im Test belegt und kein Code geändert.
8. **Drift-Wächter.** Unbekannte Zonen-ID im Feed (nicht in der Zonendatei) ⇒ `log_zone_drift` je
   Land und Feed-Momentaufnahme (`meteoalarm_feed:<Land>`), kein Ausfallhinweis für den Nutzer.
9. **Sprache.** Alle drei Feeds führen `en-GB` neben der Landessprache. Der Mapper nimmt `de*`,
   sonst `en*` ⇒ `en-GB`; per Test belegt.
10. **Budget.** Der Feed ist kontingentfrei, Last höchstens ein Abruf je Land und 30 min
    (TTL 1800 s Erfolg / 60 s Fehler, Timeout unverändert). Ticket-AC-2 (24h-Budget) ist gegenstandslos.

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in oder nahe PT, NL oder PL.
- **Output:** unverändert `list[OfficialAlert]` über `get_official_alerts_for_location()` /
  `get_official_alerts_with_status()`, `source` bleibt `"meteoalarm"`.
- **Side effects:** je Land ein Feed-Abruf pro Auffrischungsfenster (30 min).

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht ohne Netz, Datei `tests/tdd/test_meteoalarm_feed_pt_nl_pl.py`, gegen echte gekürzte
Feed-Proben in `tests/fixtures/meteoalarm_feed/` (kein Mock-Theater; `Cancel`, `Update` und fehlende
Sprache nur, wenn die echte Probe sie nicht enthält, synthetisch aus einem echten Eintrag abgeleitet
und im README gekennzeichnet). Testorte (lat, lon):

| Land | Landorte | Küste / See | Grenzorte |
|---|---|---|---|
| PT | Lissabon (38.72, -9.14), Porto (41.15, -8.61), Faro (37.02, -7.93) | Cabo da Roca (38.78, -9.50) | Elvas (38.88, -7.16) ⇔ Badajoz (38.88, -6.97) |
| NL | Amsterdam (52.37, 4.90), Maastricht (50.85, 5.69) | Den Helder Küste (52.96, 4.76), Terschelling (53.40, 5.35) | Venlo (51.37, 6.17) ⇔ Kaldenkirchen DE (51.31, 6.20); Baarle-Nassau (51.44, 4.93) ⇔ Baarle-Hertog BE |
| PL | Warschau (52.23, 21.01), Krakau (50.06, 19.94), Zakopane (49.30, 19.95) | Danzig Küste (54.35, 18.65), Hel (54.61, 18.80) | Słubice (52.35, 14.56) ⇔ Frankfurt (Oder) (52.35, 14.55) |

- [ ] Test 1 (Treffer je Land): Orte mit aktiver Warnung in der Probe ⇒ genau diese Warnung mit Stufe,
  Ereignisart, Zeitraum (PT Lissabon/Porto, NL Amsterdam, PL Warschau/Krakau).
- [ ] Test 2 (ruhig): Ort in einer Zone ohne Warnung ⇒ leere Liste, `unavailable=False` (je Land).
- [ ] Test 3 (Ausfall): Feed-Abruf schlägt fehl (HTTP-Fehler/Timeout/unlesbar) ⇒ `unavailable=True`
  für einen Punkt in PT/NL/PL.
- [ ] Test 4 (Zuständigkeit, Messung): alle Land- und Küstenorte der Tabelle ⇒ `covers()` `True`;
  Orte außerhalb (Madrid, Paris, Berlin, Prag, Vilnius) ⇒ `False`, `mark_not_covered`, keine Warnung,
  kein Ausfallhinweis.
- [ ] Test 5 (Küste): Den Helder/Terschelling/Danzig/Hel mit Warnung für die Seezone ⇒ erscheint;
  Küstenort mit Warnung in Land- UND Seezone ⇒ beide, jede genau einmal.
- [ ] Test 6 (NL-Grünstufe): NL-Probe mit überwiegend grünen Warnungen ⇒ für Amsterdam keine Warnung,
  keine Briefing-Zeile, kein Alarm; eine Gelb-oder-höher-Warnung der Probe erscheint dennoch.
- [ ] Test 7 (Update/Cancel): `Cancel` ⇒ nicht aktiv; `Update` ersetzt Vorgänger ⇒ genau einmal.
  Belegt zuerst an echten Proben, ob der Zonenweg das heute korrekt tut; rot ⇒ gemeinsame Ergänzung.
- [ ] Test 8 (Sprachfallback): Eintrag mit Landessprache + `en-GB` ⇒ Text aus `en-GB`, nicht leer.
- [ ] Test 9 (Malformation): ein andersförmiger Eintrag ⇒ Punkte mit korrekter Warnung bekommen sie
  ohne Ausfallhinweis.
- [ ] Test 10 (Grenzpaare): Elvas/Badajoz, Venlo/Kaldenkirchen, Baarle-Nassau, Słubice/Frankfurt
  (Oder) ⇒ Warnung nur im eigenen Land, nie doppelt; Nachbarland-Punkt bekommt keine Warnung des
  Nachbarfeeds und keinen Ausfallhinweis.
- [ ] Test 11 (Drift): Zonen-ID im Feed ohne Eintrag in der Zonendatei ⇒ `log_zone_drift`-Eintrag
  `meteoalarm_feed:<Land>`, Ort in bekannter Zone bekommt seine Warnung.
- [ ] Test 12 (Abgleich Zonendatei): jede Zonen-ID der drei Feed-Proben steht in der jeweiligen
  Zonendatei (1:1), kein Land hat eine leere Datei.
- [ ] Test 13 (Registry/Reihenfolge): Registry enthält PT, NL, PL nach ES und vor `DpcSource`, BE ist
  nicht registriert; `test_meteoalarm_feed_es.py` (ac9/ac12) akzeptiert die erweiterte Reihenfolge.
- [ ] Test 14 (Regression): IT/AT/DE/CH/NO/SE/FI/ES-Feedtests laufen unverändert grün.
- [ ] Test 15 (Alarmweg Ende-zu-Ende): Warnung der Alarmstufe aus einer PT-/NL-/PL-Probe über echte
  Registry bis zur Kanal-Auflösung eines Nutzers mit Empfängern auf allen vier Kanälen ⇒ E-Mail,
  Telegram, SMS, Premium-SMS wie bei einer AT-Warnung gleicher Stufe (Trip und Ortsvergleich).
- [ ] Test 16 (Live, `tests/tdd/test_meteoalarm_feed_pt_nl_pl_live.py`, Marker `live`, nur
  `/e2e-verify`): je Land ein aktuell gewarntes Gebiet aus dem echten Feed ⇒ mindestens 1 Warnung
  ohne Ausfall im Timeout; ohne gültige Warnung SKIP mit Grund, nicht PASS.

## Acceptance Criteria

- **AC-1:** Given ein Wanderpunkt liegt in Portugal, den Niederlanden oder Polen in einem Gebiet mit
  amtlich aktiver Warnung (z. B. Lissabon, Amsterdam, Warschau), When die amtlichen Warnungen
  abgerufen werden, Then erscheint die Warnung mit Warnstufe, Ereignisart und Gültigkeitszeitraum.
  - Test: Test 1.

- **AC-2:** Given ein Wanderpunkt liegt in Portugal, den Niederlanden oder Polen und für sein Gebiet
  besteht amtlich keine aktive Warnung, When die Warnungen abgerufen werden, Then meldet das
  Ergebnis „keine Warnung" und NICHT „amtliche Warnungen nicht abrufbar".
  - Test: Test 2.

- **AC-3:** Given der Warndienst (Feed) ist zum Abrufzeitpunkt nicht erreichbar oder unlesbar, When
  die Warnungen für einen Punkt in Portugal, den Niederlanden oder Polen abgerufen werden, Then
  meldet das Ergebnis „amtliche Warnungen aktuell nicht abrufbar" statt fälschlich eine
  warnungsfreie Lage zu zeigen.
  - Test: Test 3.

- **AC-4:** Given ein Wanderpunkt liegt in Portugal, den Niederlanden oder Polen, auch an Küste und
  Landesrand (Cabo da Roca, Den Helder, Terschelling, Danzig, Hel, Zakopane), When die Zuständigkeit
  geprüft wird, Then ist die jeweilige Landesquelle zuständig; Given ein Punkt liegt außerhalb aller
  Zonen dieser Länder (Madrid, Berlin, Prag), Then schweigt die Quelle folgenlos, ohne Warnung und
  ohne Ausfallhinweis.
  - Test: Test 4.

- **AC-5:** Given ein Küstenort liegt in einer Land- und einer Seezone mit je einer aktiven Warnung
  (Den Helder, Danzig), When die Warnungen abgerufen werden, Then erscheinen beide Warnungen, jede
  genau einmal; Given nur die Seezone ist gewarnt, Then erscheint diese Warnung ebenfalls.
  - Test: Test 5.

- **AC-6:** Given der niederländische Feed führt hunderte Warnungen der Stufe grün („Minor"), When
  die Warnungen für einen niederländischen Ort abgerufen werden, Then entsteht aus Grünstufen weder
  ein Alarm noch eine Briefing-Zeile, während eine Warnung ab Stufe gelb weiterhin erscheint.
  - Test: Test 6.

- **AC-7:** Given eine Warnung wurde aufgehoben (`Cancel`) oder durch eine neuere Fassung ersetzt
  (`Update`), When die Warnungen abgerufen werden, Then erscheint die aufgehobene nicht als aktiv und
  die aktualisierte genau einmal, die ersetzte Fassung nicht zusätzlich; Entwarnung läuft nur über
  das Verschwinden bei gesunder Quelle (ADR-0090). Ergibt die Prüfung an echten Proben, dass der
  Zonenweg ersetzte Warnungen stehen lässt, wird er gemeinsam für alle Zonenländer (auch FI und ES)
  korrigiert.
  - Test: Test 7.

- **AC-8:** Given der Feed liefert Texte in Landessprache und Englisch (`pt-PT`, `nl-NL`, `pl-PL`
  plus `en-GB`), When die Warnung ausgegeben wird, Then ist ihr Text vorhanden und stammt aus
  `en-GB`, nicht leer.
  - Test: Test 8.

- **AC-9:** Given ein einzelner andersförmiger Eintrag im Feed, When ein Punkt mit korrekter Warnung
  abgefragt wird, Then erhält er seine Warnung und keinen Ausfallhinweis.
  - Test: Test 9.

- **AC-10:** Given ein Punkt liegt an einer Landesgrenze (Elvas/Badajoz, Venlo/Kaldenkirchen,
  Baarle-Nassau, Słubice/Frankfurt (Oder)), When nur eines der Länder dort eine Warnung führt, Then
  erscheint genau diese Warnung einmal, ohne Doppel-Chip, und die Quelle des Nachbarlands liefert
  weder eine Warnung noch einen Ausfallhinweis.
  - Test: Test 10.

- **AC-11:** Given eine Zonenkennung im Feed fehlt in der eingecheckten Zonendatei (Änderung bei
  EUMETNET), When die Warnungen abgerufen werden, Then wird die Abweichung im Drift-Journal
  festgehalten und Orte in bekannten Zonen erhalten ihre Warnungen unverändert ohne Ausfallhinweis.
  - Test: Tests 11 und 12.

- **AC-12:** Given die bestehenden Warnungen für Italien, Österreich, Deutschland, die Schweiz, Norwegen,
  Schweden, Finnland und Spanien, When deren Testfälle nach dieser Änderung erneut laufen, Then liefern
  sie unverändert dieselben Ergebnisse, und die Registrierungsreihenfolge (PT, NL, PL nach ES, vor
  der Gewitterquelle DPC; Belgien nicht registriert) ist eingehalten.
  - Test: Tests 13 und 14.

- **AC-13:** Given eine Warnung aus Portugal, den Niederlanden oder Polen erreicht die für Alarme
  maßgebliche Warnstufe, When sie den geteilten Alarm-Pfad eines Trip- oder Ortsvergleichs-Alarms
  durchläuft, Then erreicht sie bei der Kanal-Auflösung alle vier Kanäle (E-Mail, Telegram, SMS,
  Premium-SMS) wie eine österreichische Warnung derselben Stufe.
  - Test: Test 15.

- **AC-14:** Given die echten Feeds von Portugal, den Niederlanden und Polen auf Staging mit je einer
  aktuell gewarnten Zone, When die Quelle für einen Punkt in dieser Zone abgefragt wird, Then liefert
  sie mindestens eine Warnung ohne Ausfallhinweis im Timeout; ohne aktuelle Warnung im Feed ist das
  Ergebnis ein SKIP mit Grund, kein Bestehen.
  - Test: Test 16.

## Abweichungen vom Ticket (#1442, Stand 31.07.)

- **Ticket-AC-2 (24h-Abrufbudget) gegenstandslos:** Budget-Gate und EDR-Klasse sind mit #2266
  zurückgebaut; `feeds.meteoalarm.org` ist kontingentfrei, es gilt nur der 30-min-Cache.
- **Bezugsweg Feed statt `api.meteoalarm.org`/MQTT** (siehe #1445, ADR-0039).
- **Zuordnung:** PT/NL/PL per `EMMA_ID` mit eingecheckter Zonengeometrie (Zonenweg), nicht per Polygon.
- **Ticket-AC-3 (Dedup):** Für PT/NL/PL gibt es keine Nationalquelle im Code, gegen die dedupliziert
  werden müsste; AC-10 belegt, dass an Grenzpunkten keine Doppelanzeige entsteht.
- **Zuschnitt:** Ticket-Slice S3 (sechs Länder) wird in S3a (PT, NL, PL), S3b (UK) und S3c (BE)
  zerlegt; ES läuft als eigener Workflow. Der Orchestrator aktualisiert den Text von #1442.

## Known Limitations

- **Höhenband ignoriert** (wie IT/AT/DE/CH/Nordics): lieber eine Warnung zu viel als zu wenig.
- **Vereinfachte Zonen überlappen an Grenzen:** `covers()` kann für zwei Länder wahr sein; Folge
  höchstens ein Abruf mit „keine Warnung", nie eine Doppel-Warnung.
- **Lizenz von `geocodes.json` ungeklärt** (seit S2 offen). Dies ist eine dokumentierte Annahme/ein
  Risiko, kein Blocker: PT/NL/PL kommen in den gebündelten Antrag in `docs/specs/data_sources.md`
  (wie FI/ES). Die Klärung liegt beim PO, die Auslieferung wartet nicht darauf.
- **Zonengeometrie statisch:** Änderungen der Zonen bei EUMETNET erkennt der Drift-Wächter, die
  Datei wird dann manuell nachgeführt.
- **Latenz:** EUMETNET-Weitergabe mit 5–10 min Verzug; NL-Feed 1,4 MB unkomprimiert je 30 min
  (Rahmen ADR-0074, wie IT/DE).
- **Entwarnung** nur über Verschwinden bei gesunder Quelle (ADR-0090).
- **AC-9 gilt für zuordenbare Einträge:** Ein andersförmiger Eintrag, der ein Zonen-Geocode trägt,
  färbt fremde Abfragen nicht ein (Test 9). Ein Eintrag **ganz ohne** auswertbare Zonenangabe (kein
  `info[]` als Liste bzw. Liste ohne jedes Geocode, kein `Cancel`) meldet dagegen das ganze Land als
  „nicht abrufbar" — bewusste Abwägung aus der Gegenprüfung (F003/F005: „lieber einmal zu viel
  gewarnt"), gilt unverändert auch für IT/AT/DE/FI/ES im geteilten Zonenweg.

## Out of Scope

- **Vereinigtes Königreich (S3b):** Der UK-Feed trägt nur Polygone (kein Geocode) und braucht den
  Polygonweg mit eigenem Landesumriss (Großbritannien inkl. Nordirland). Eigener Mechanismus, eigener
  Workflow.
- **Belgien (S3c):** Der Feed mischt `EMMA_ID` (11 Warnungen) und `NUTS2` (50 Warnungen); `geocodes.json`
  hat keine NUTS2-Geometrie. Ohne sie landen NUTS2-Warnungen im Zweig „Zonenzugehörigkeit nicht
  bestimmbar" und würden jede belgische Abfrage dauerhaft als „nicht abrufbar" melden. Braucht eine
  zweite Geometriequelle (Eurostat GISCO NUTS-2021, Lizenz vorab prüfen) und Mehrfach-Kennung. **Belgien
  wird bis dahin NICHT registriert.**
- **Spanien/Mallorca:** eigener Workflow `feat-1442-s3-meteoalarm-spanien` (Vorbedingung, nicht Teil
  dieser Lieferung).
- Höhenband-Auswertung, Teilflächen, neue Egress-Hosts, Änderung von TTL und Timeout.
- Klärung der `geocodes.json`-Lizenz (PO-Thema).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neu. Es gelten ADR-0039, 0041, 0074, 0090 und 0095 unverändert.
- **Rationale:** Weitere Zonenländer sind Konfiguration des bestehenden Zonenwegs, keine
  Grundsatzentscheidung.

## Changelog

- 2026-10-30: Initial spec created (Issue #1442 S3a, Analyse-Grundlage
  `docs/context/feat-1442-s3-rest-eu.md`).
- 2026-10-31: Validierung — Known Limitation zur Reichweite von AC-9 ergänzt.
