---
entity_id: feat_1442_s3_meteoalarm_spanien
type: feature
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [official-alerts, meteoalarm, spain, mallorca, gr221, zones, geocode, warn-egress]
workflow: feat-1442-s3-meteoalarm-spanien
---

<!-- Issue #1442, Scheibe S3, NUR Spanien. S1 (CH) und S2 (NO/SE/FI) sind live. PT, UK, NL/BE, PL bleiben offen. Vorlage: feat_1442_s2_meteoalarm_nordics.md (Teil B = FI-Zonenweg). -->

# MeteoAlarm Spanien: amtliche AEMET-Warnungen über den kontingentfreien Feed

## Approval

- [ ] Approved

## Purpose

Wanderpunkte in Spanien, vor allem auf Mallorca am GR221 (Reise 25.02.–07.03.2027), bekommen heute
keine amtlichen Unwetterwarnungen. Diese Spec registriert `MeteoAlarmFeedSource("ES")` und bezieht
die AEMET-Warnungen aus dem kontingentfreien Feed `feeds.meteoalarm.org`.

Messung 2026-10-30 (live): `feeds-spain` antwortet 200, 1,3 MB, 97 Warnungen, **kein einziges Polygon**,
nur `EMMA_ID`-Geocodes, 233 verschiedene Zonen (Land `ES070`–`ES251`, Kanaren `ES120`–`ES132`, Küste
`ES840`–`ES890`). Spanien ist damit derselbe Fall wie Finnland (Zonenweg), nicht wie CH/NO/SE. Der
Auszug aus der MeteoAlarm-`geocodes.json` enthält exakt dieselben 233 Zonen wie der Feed (keine
Lücke, keine ungenutzte Zone).

Statt einen ES-Zwilling von `_fetch_fi` zu bauen, wird der FI-Zonenweg auf „Zonenländer FI+ES"
verallgemeinert.

## Source

- **File:** `src/services/official_alerts/meteoalarm_feed.py` (MODIFY)
- **Identifier:** `_FEED_PATHS`, `_GEOCODE_NAME`, `MeteoAlarmFeedSource.__init__(country)` (Literal),
  `covers()`, `fetch()`, `_fi_zones`, `_zones_for_point_fi`, `_fi_known_zones`, `_fetch_fi`
  (werden zu `_zone_mappers`, `_zones_for_point(country, ...)`, `_known_zones(country)`,
  `_fetch_zones(country, ...)` verallgemeinert)

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/official_alerts/`). Kein Go-, kein
> Frontend-Anteil. Der Host `feeds.meteoalarm.org` ist im Egress-Inventar (`internal/egress/inventory.go`,
> `src/app/egress_guard.py`) bereits geführt; kein neuer Host.

> **Mandantentrennung:** Keine Nutzerdaten im Pfad. Die Quelle ist global (Cache-Schlüssel = Ländercode,
> Eingang nur `lat`/`lon` eines beobachteten Orts). Ein Zwei-Nutzer-Test ist gegenstandslos (gleiche
> Begründung wie S1, S2, #1681); die Nutzerbindung geschieht im geteilten Alarm-Pfad.

> **Kanäle:** Alle vier Kanäle (E-Mail · Telegram · SMS · Premium-SMS) bleiben unverändert. Die Quelle
> liefert `OfficialAlert` mit `source="meteoalarm"`; Briefing-, Alarm- und Entwarnungspfad (ADR-0090)
> werden nicht angefasst, gleicher Inhalt in kanalgerechter Form wie bei AT/IT/DE.

> **Trip/Ortsvergleich-Teilung:** gegenstandslos (reine Datenquelle, kein UI-Baustein). Trip und
> Ortsvergleich konsumieren dieselbe Registry.

## Estimated Scope

- **LoC:** Produktiv ca. +120 (netto weniger, weil FI-Weg verallgemeinert statt kopiert), Tests ca. +200;
  Datendatei ca. 150–300 KB generiert (zählt nicht zum LoC-Limit).
- **Files:** 8 (davon 1 Datendatei, 1 Fixture)
- **Effort:** medium. **Risk:** MEDIUM — Code folgt dem bewährten FI-Muster; das Risiko liegt in der
  Geometrie (Küste, Grenze) und in der ungeklärten Lizenz der Geocode-Datei.

### Affected Files (Scope)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/data/meteoalarm_zones_ES.geojson.json` | CREATE | ES-Auszug, 233 Zonen, `id` = EMMA_ID, Land aufgeweitet und vereinfacht, Seezonen unverändert |
| `src/services/official_alerts/meteoalarm_feed.py` | MODIFY | `_FEED_PATHS["ES"]`, `_GEOCODE_NAME["ES"]="EMMA_ID"`, Literal; FI-Zonenweg zu „Zonenländer FI+ES" verallgemeinern |
| `src/services/official_alerts/__init__.py` | MODIFY | `register_official_alert_source(MeteoAlarmFeedSource("ES"))` nach FI, vor `DpcSource` |
| `src/services/official_alerts/data/README.md` | MODIFY | ES-Abschnitt: Herkunft, sha256, Veränderungen, Skript-Parameter, Beleg 1:1-Abgleich |
| `docs/specs/data_sources.md` | MODIFY | ES in den bestehenden Lizenz-Antrag aufnehmen (gebündelt mit FI) |
| `tests/fixtures/meteoalarm_feed/feed_spain_sample.json` + `README.md` | CREATE/MODIFY | echte gekürzte Probe (Mallorca-Zonen u. a.) |
| `tests/test_meteoalarm_feed_es.py` | CREATE | Kern-Verhaltenstests ohne Netz |
| `tests/test_meteoalarm_feed_fi*.py` (bestehend) | REUSE | FI-Tests laufen unverändert grün (Regression) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `warn_egress.cached_fetch` / `mark_fetch_incomplete` / `mark_not_covered` / `log_zone_drift` | module | Abruf, Drei-Zustände-Regel, Drift-Journal |
| `region_mapper.RegionMapper` | module | Punkt -> Regionen-IDs; liest `properties.id` |
| `meteoalarm._group_and_map_info_entries` | module | geteilter CAP-Mapper (wählt `de*`, Fallback `en*`) |
| `base.get_official_alerts_with_status` | module | wertet `unavailable` über alle Quellen |
| `docs/adr/0039`, `0041`, `0074`, `0090` | adr | Feed-Weg, lokale Zuständigkeit, Auffrischraster, Entwarnung über Verschwinden |

## Implementation Details

1. **Verallgemeinerung statt Kopie.** Der FI-Zonenweg wird zum Zonenweg für Länder mit eingechecktem
   `EMMA_ID`-Auszug: ein Wörterbuch `{"FI": RegionMapper(FI-Datei), "ES": RegionMapper(ES-Datei)}`,
   `_zones_for_point(country, lat, lon)`, `_known_zones(country)`, `_fetch_zones(country, lat, lon)`.
   Es gibt **keine** Funktion `_fetch_es`. `covers()` und `fetch()` verwenden dieselbe
   Zonenfunktion (Muster DE/FI). FI verhält sich danach byte-gleich wie vorher.
2. **ES-Auszug.** Einmalig per Skript aus `geocodes.json` (sha256 `0c8fe7b9…5dd0`, identisch zur FI-Quelle,
   39 MB): nur `type=EMMA_ID` mit Präfix `ES`; Eigenschaft **`code` -> `id`** umschreiben (der Mapper liest
   `properties.id`, sonst lädt er keine einzige Zone); Landzonen um **0,05°** aufgeweitet und mit
   `simplify(0.005)` vereinfacht; Seezonen `ES840`–`ES890` (Präfix `Costa - …`) **unverändert**. Alle
   233 Zonen bleiben enthalten, auch Kanaren, Ceuta und Melilla (sonst Dauerlärm im Drift-Journal;
   Zusatzgröße gering). Skript-Parameter stehen im `data/README.md`; shapely dient nur dem einmaligen
   Bau, nicht der Laufzeit.
3. **Größen-Obergrenze.** Die Datei ist höchstens **400 KB** groß (erwartet 150–300 KB). Wird sie größer,
   ist `simplify` zu erhöhen, nicht die Obergrenze.
4. **Aufweitung ist nötig (Messung 2026-10-30).** Ohne Aufweitung fallen Sa Dragonera (0,035° bis
   `ES117`) und Port d'Andratx (0,043° bis `ES117`) nur in die Seezone `ES874` und bekämen keine
   Land-Warnungen (Wind, Gewitter, Hitze). 0,05° deckt beide. Küstenort = Land- UND Seezone;
   `fetch()` wertet alle getroffenen Zonen aus, jede Warnung zählt einmal.
5. **Drei Zustände.** Punkt in keiner ES-Zone -> `mark_not_covered()`; zuständig, Feed nicht abrufbar ->
   `mark_fetch_incomplete()` (keine stille Leere); sonst Treffer oder leere Liste ohne Ausfall.
   Entwarnung nur über Verschwinden (ADR-0090).
6. **Drift-Wächter.** `_log_unknown_zone_drift(feed, "ES", _known_zones("ES"), "unknown_zone")`: jede
   Feed-Zone außerhalb der eingecheckten Datei landet im Warn-Dienst-Journal, kein Ausfall-Signal.
   Aktuell 0 Lücken; der Wächter bleibt scharf.
7. **Sprache.** Der Feed liefert je Warnung `es-ES` und `en-GB`. Der Mapper wählt `de*`, sonst `en*`, das
   greift als `en-GB`. Wird per Test belegt, nicht angenommen.
8. **Registrierung.** Nach `MeteoAlarmFeedSource("FI")`, vor `DpcSource`, mit Reihenfolge-Kommentar
   (Gewitter-Tie-Break „zuerst registriert gewinnt", #1427 S2).
9. **Grenze zu FR/PT.** Die Aufweitung von 0,05° (ca. 5 km) kann einen Punkt knapp jenseits der Grenze
   treffen. Zuständig ist jede Quelle, deren Zonen den Punkt enthalten; ES liefert nur Warnungen der
   getroffenen ES-Zonen, jede ES-Warnung genau einmal. Ein Punkt in Frankreich weiter als der
   Aufweitungsstreifen von der Grenze ist für ES nicht zuständig. **Im französischen Grenzstreifen
   (bis 0,05°) ist zusätzlich `VigilanceSource` (Météo-France) zuständig:** der Punkt bekommt dort
   je Gefahrenart genau **eine** Warnung: der bestehende Quellen-Kollaps
   (`get_official_alerts_for_location`, #1086, „nie doppelt") behält die Quelle mit der höchsten
   Stufe, bei Gleichstand die zuerst registrierte (Vigilance vor ES). Eine höhere ES-Stufe verdrängt
   dort also die französische Warnung. Dieses Verhalten ist unverändert und gewollt; S3 ändert es nicht.
10. **Budget.** Feed kontingentfrei; Last höchstens ein Abruf je 30 min (1,3 MB, TTL 1800 s Erfolg /
    60 s Fehler, Timeout 15 s, unverändert).
11. **Doku.** `data/README.md` und `docs/specs/data_sources.md` führen ES im **bestehenden** Lizenz-Antrag
    zur Geocode-Datei mit (gebündelt mit FI). Die Lizenzfrage wird hier nicht neu entschieden.

## Expected Behavior

- **Input:** Koordinate eines beobachteten Orts in oder nahe Spanien (Festland, Balearen, Kanaren, Ceuta, Melilla).
- **Output:** unverändert `list[OfficialAlert]` über `get_official_alerts_for_location()` /
  `get_official_alerts_with_status()`, `source` bleibt `"meteoalarm"`.
- **Side effects:** höchstens ein Feed-Abruf je 30 min; Journal-Eintrag bei unbekannter Feed-Zone.

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/test_meteoalarm_feed_es.py`, ohne Netz, gegen `tests/fixtures/meteoalarm_feed/feed_spain_sample.json`
(gekürzte **echte** Aufzeichnung des Spanien-Feeds mit Mallorca-Zonen `ES114`–`ES118`, Küstenzonen
`ES873`–`ES878` und weiteren Zonen). Kein Mock-Theater: weder `Mock()` noch `patch()` der eigenen
Annahme; der Netzabruf wird über den vorhandenen, von Tests umlenkbaren `FEED_BASE_URL`
(lokaler Server) bzw. die Fixture-Datei gespeist. Synthetische Ableitungen (z. B. unbekannte Zone,
`Cancel`) werden im Fixture-README als solche gekennzeichnet.

- [ ] Test 1 (GR221 Land): Sóller, Lluc, Sa Calobra mit Warnung für `ES114` -> Warnung mit Stufe, Art, Zeitraum.
- [ ] Test 2 (Küste Land+See): Sa Dragonera, Port d'Andratx mit Warnungen für `ES117` UND `ES874` -> beide
  erscheinen, jede einmal.
- [ ] Test 3 (Seezonen unverändert): Punkt knapp auf See vor Sa Dragonera trifft `ES874`, aber keine Landzone
  außerhalb der 0,05°-Aufweitung.
- [ ] Test 4 (außerhalb): Punkt in Frankreich (Perpignan) und in Marokko (Tanger) -> `covers()` False,
  `mark_not_covered`, keine Warnung, kein Ausfallhinweis.
- [ ] Test 5 (Feed ausgefallen): Abruf schlägt fehl -> `unavailable=True` für einen Punkt auf Mallorca.
- [ ] Test 6 (ruhig): Punkt in ES ohne Warnung im Feed -> leere Liste, `unavailable=False`.
- [ ] Test 7 (Drift): Feed mit einer Zone, die nicht in der Datei steht -> Eintrag `unknown_zone` im
  Journal, kein Ausfallhinweis, andere Warnungen bleiben.
- [ ] Test 8 (Sprache): Eintrag mit `es-ES` und `en-GB` -> Text aus `en-GB`, nicht leer, nicht spanisch.
- [ ] Test 9 (Registrierung): echte Registry enthält `ES` nach `FI` und vor `DpcSource`.
- [ ] Test 10 (Grenzpunkt): Punkt in Frankreich nahe den Pyrenäen -> keine ES-Warnung außerhalb des
  Aufweitungsstreifens; Punkt im Streifen -> jede ES-Warnung genau einmal. Messpunkte: Hendaye
  (43,37 / -1,78) und Bourg-Madame (42,43 / 1,95), beide FR, im Streifen (ES233 / ES182); Perpignan
  und Tanger bleiben Test 4 (klar außerhalb).
- [ ] Test 11 (FI-Regression): bestehende FI-Tests unverändert grün; IT/AT/DE/CH/NO/SE ebenfalls.
- [ ] Test 12 (Verallgemeinerung): FI und ES laufen über denselben Zonenweg; kein `_fetch_es` im Modul.
- [ ] Test 13 (Auszug id): jede Zone der ES-Datei trägt `properties.id` im Muster `ES\d{3}`; `code` fehlt;
  der `RegionMapper` lädt alle Zonen.
- [ ] Test 14 (Auszug vollständig und klein): Datei enthält genau 233 Zonen inkl. Kanaren
  (`ES120`–`ES132`), Ceuta und Melilla und ist <= 400 KB; jede Feed-Zone der Fixture ist enthalten.
- [ ] Test 15 (Alarmweg Ende-zu-Ende): Warnung der Alarmstufe aus der Fixture über die echte Registry bis
  zur Kanal-Auflösung eines Nutzers mit Empfängern auf allen vier Kanälen -> wie bei einer AT-Warnung
  gleicher Stufe.
- [ ] Test 16 (Live, Marker `live`, nur `/e2e-verify`, lokal): aktuell gewarnte Zone aus dem echten Feed ->
  mindestens 1 Warnung ohne Ausfall im Timeout; ohne aktuelle Warnung SKIP mit Grund, nicht PASS
  (Staging blockt Warn-Hosts per Egress-Guard).

## Acceptance Criteria

- **AC-1:** Given ein Wanderpunkt am GR221 (Sóller, Lluc oder Sa Calobra) und der Feed führt eine aktive
  Warnung für die Zone Sierra Tramontana (`ES114`), When die amtlichen Warnungen abgerufen werden, Then
  erscheint die Warnung mit Warnstufe, Ereignisart und Gültigkeitszeitraum im Ergebnis.
  - Test: Test 1.

- **AC-2:** Given ein Küstenpunkt an der Südwestküste Mallorcas (Sa Dragonera oder Port d'Andratx) und der
  Feed führt Warnungen für die Landzone `ES117` und die Seezone `ES874`, When die Warnungen abgerufen
  werden, Then liefert die Quelle beide Warnungen, jede genau einmal. Im geteilten Pfad gilt weiter der
  Quellen-Kollaps (#1086): gleiche Gefahrenart im identischen Zeitraum erscheint dort als eine Karte.
  - Test: Test 2.

- **AC-3:** Given die Landzonen sind um 0,05° aufgeweitet und die Seezonen `ES840`–`ES890` bleiben
  unverändert, When ein Punkt knapp auf See außerhalb der Aufweitung abgefragt wird, Then trifft er nur
  die Seezone und keine Landzone.
  - Test: Test 3.

- **AC-4:** Given ein Punkt liegt außerhalb Spaniens (Perpignan in Frankreich, Tanger in Marokko), When die
  Zuständigkeit geprüft wird, Then schweigt die Spanien-Quelle folgenlos: keine Warnung, kein
  Ausfallhinweis, und die Quelle meldet sich als „nicht zuständig" (`mark_not_covered`).
  - Test: Test 4.

- **AC-5:** Given der Warndienst (Feed) ist zum Abrufzeitpunkt nicht erreichbar, When die Warnungen für
  einen Punkt auf Mallorca abgerufen werden, Then meldet das Ergebnis „amtliche Warnungen aktuell nicht
  abrufbar" statt fälschlich eine warnungsfreie Lage zu zeigen.
  - Test: Test 5.

- **AC-6:** Given ein Wanderpunkt in Spanien, für dessen Zone amtlich keine aktive Warnung besteht, When die
  Warnungen abgerufen werden, Then meldet das Ergebnis „keine Warnung" und NICHT „amtliche Warnungen
  nicht abrufbar".
  - Test: Test 6.

- **AC-7:** Given der Feed nennt eine Zone, die in der eingecheckten Zonendatei fehlt, When ein Punkt
  abgefragt wird, Then steht die unbekannte Zone im Warn-Dienst-Journal (`unknown_zone`), der Ort
  bekommt keinen Ausfallhinweis und alle bekannten Warnungen bleiben erhalten.
  - Test: Test 7.

- **AC-8:** Given der Feed liefert Texte in `es-ES` und `en-GB`, When die Warnung ausgegeben wird, Then ist
  ihr Text vorhanden und stammt aus `en-GB` (Fallback `en*`), nicht leer und nicht aus `es-ES`.
  - Test: Test 8.

- **AC-9:** Given die Registry der amtlichen Quellen, When sie aufgebaut wird, Then steht die Spanien-Quelle
  nach Finnland und vor der italienischen Quelle (`DpcSource`), damit der Gewitter-Tie-Break „zuerst
  registriert gewinnt" unverändert greift.
  - Test: Test 9.

- **AC-10:** Given ein Punkt in Frankreich nahe der Pyrenäen-Grenze, When die Warnungen abgerufen werden,
  Then erscheint jenseits des 0,05°-Streifens keine spanische Warnung, und im Streifen erscheint jede
  spanische Warnung genau einmal (kein Doppel-Chip innerhalb der ES-Quelle). Der Quellen-Kollaps
  (#1086) bleibt unverändert: je Gefahrenart erscheint höchstens eine Warnung, auch wenn zusätzlich
  `VigilanceSource` zuständig wäre. Test 10 ist netzfrei und prüft nur die ES-Seite.
  - Test: Test 10.

- **AC-11:** Given die bestehenden Warnungen für Finnland, Italien, Österreich, Deutschland, die Schweiz,
  Norwegen und Schweden, When deren Testfälle nach dieser Änderung unverändert erneut laufen, Then
  liefern sie dieselben Ergebnisse.
  - Test: Test 11.

- **AC-12:** Given der Zonenweg für Finnland und Spanien, When der Code geprüft wird, Then laufen beide
  Länder über denselben verallgemeinerten Zonenweg (`_fetch_zones(country, ...)`), und es gibt keine
  zweite, kopierte Spanien-Abrufroutine.
  - Test: Test 12.

- **AC-13:** Given der eingecheckte Spanien-Auszug, When der Zonenweg ihn lädt, Then trägt jede Zone ihre
  Kennung unter `id` (umgeschrieben aus `code`) im Muster `ES` plus drei Ziffern und der Zonenweg lädt
  alle Zonen; ein Auszug mit `code` statt `id` würde keine Zone laden.
  - Test: Test 13.

- **AC-14:** Given der eingecheckte Spanien-Auszug, When seine Größe und sein Inhalt geprüft werden, Then
  enthält er genau 233 Zonen einschließlich Kanaren, Ceuta und Melilla, deckt jede Zone des
  Feed-Musters ab und ist höchstens 400 KB groß.
  - Test: Test 14.

- **AC-15:** Given eine Warnung aus Spanien erreicht die für Alarme maßgebliche Warnstufe, When sie den
  geteilten Alarm-Pfad eines Trip- oder Ortsvergleichs-Alarms durchläuft, Then erreicht sie bei der
  Kanal-Auflösung alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) wie eine österreichische Warnung
  derselben Stufe.
  - Test: Test 15.

- **AC-16:** Given der echte Spanien-Feed mit einer aktuell gewarnten Zone, When die Quelle für einen Punkt
  in dieser Zone abgefragt wird, Then liefert sie mindestens eine Warnung ohne Ausfallhinweis im
  Timeout; ohne aktuelle Warnung im Feed ist das Ergebnis ein SKIP mit Grund, kein Bestehen.
  - Test: Test 16.

- **AC-17:** Given die Dokumentation der Datendateien und Datenquellen, When ein Leser nach Herkunft und
  Lizenz der Spanien-Zonendatei sucht, Then findet er im `data/README.md` einen ES-Abschnitt (Herkunft,
  sha256, Veränderungen, Skript-Parameter) und in `docs/specs/data_sources.md` Spanien im bestehenden
  Lizenz-Antrag, gebündelt mit Finnland.
  - Test: `# doc-compliance-test` (Dokumentationspflicht, kein Verhaltensnachweis); die Verhaltensnachweise
    stehen in AC-1 bis AC-16.

## Abweichungen vom Ticket (#1442)

- **Ticket-AC-2 (24h-Abrufbudget) gegenstandslos:** `feeds.meteoalarm.org` ist kontingentfrei, es gilt nur
  der 30-min-Cache (wie S1/S2).
- **Bezugsweg Feed statt `api.meteoalarm.org`/MQTT** (#1445, ADR-0039).
- **Zuordnung:** Spanien per `EMMA_ID` mit eingecheckter Zonengeometrie (Feed ohne Polygone), nicht per
  Punkt-in-Polygon.
- **Ticket-AC-3 (Dedup):** Für Spanien gibt es keine überlappende Nationalquelle. Einzige Überlappung:
  der französische Grenzstreifen (Aufweitung 0,05°), dort zusätzlich `VigilanceSource`; der bestehende
  Quellen-Kollaps (#1086) lässt je Gefahrenart nur eine Warnung zu, siehe Punkt 9 und AC-10.
- **Ticket-AC-1 (Live-Test):** gilt für Spanien (AC-16).

## Known Limitations

- **Höhenband** wird nicht ausgewertet (wie IT/AT/DE/CH/NO/SE): lieber eine Warnung zu viel als zu wenig.
- **Geometrie grob:** MeteoAlarm-Umrisse sind grob; die Aufweitung um 0,05° (ca. 5 km) kompensiert das
  an Mallorcas Küste, kann aber an der Grenze zu FR/PT und in Gibraltar (0,054° bis `ES077`) einen
  Streifen jenseits der Grenze mit abdecken. Folge: dort erscheint genau eine spanische Warnung, kein Ausfall.
- **Lizenz der Geocode-Datei weiterhin ungeklärt** (bei FI offen, Antrag in `docs/specs/data_sources.md`);
  ES wird dort mitgeführt, nicht neu entschieden.
- **Statische Datei:** Änderungen der Zonen bei EUMETNET erkennt der Drift-Wächter; die Datei wird dann manuell
  nachgeführt.
- **Latenz:** EUMETNET-Weitergabe mit 5–10 min Verzug; Feed 1,3 MB unkomprimiert (ADR-0074).
- **Entwarnung** nur über Verschwinden bei gesunder Quelle (ADR-0090).

## Out of Scope

- PT, UK, NL/BE, PL (weitere Scheiben von #1442).
- Höhenband-Auswertung, Teilflächen.
- Neue Egress-Hosts, Änderung von TTL (1800 s/60 s) und Timeout (15 s), Änderungen an Kanälen und Downstream.
- Neuentscheidung der Lizenzfrage der Geocode-Datei.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neu. Es gelten ADR-0039, 0041, 0074 und 0090 unverändert.
- **Rationale:** Der Zonenweg ist eine bestehende Implementierungsvariante (FI); ein Länderschlüssel statt
  fester Konstante ist Verallgemeinerung, keine Grundsatzentscheidung.

## Changelog

- 2026-10-30: Initial spec created (Issue #1442 S3, nur Spanien; Analyse-Grundlage
  `docs/context/feat-1442-s3-meteoalarm-spanien.md`).
