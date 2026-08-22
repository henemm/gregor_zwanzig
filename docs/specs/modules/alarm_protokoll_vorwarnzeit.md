---
entity_id: alarm_protokoll_vorwarnzeit
type: feature
created: 2026-08-22
updated: 2026-08-22
status: approved
workflow: feat-2050-s6-protokoll-vorwarnzeit
version: "1.0"
tags: [alarm, protokoll, nachvollziehbarkeit]
---

# Alarm-Protokoll haelt Vorwarnzeit, Ereigniszeit, Messpunkt, Vergleichsbasis und Quelle fest (Scheibe S6, Issue #2050)

## Approval

- [x] Approved — PO-Freigabe ("go") am 2026-08-22

## Purpose

Anforderung **E-1** (Nachvollziehbarkeit) verlangt, dass sich nachtraeglich belegen laesst,
**warum ein Alarm kam oder ausblieb**. Das Alarm-Protokoll (`src/services/alert_log.py`) haelt
heute WAS gemeldet wurde (Register-Groesse, Schweregrad, Kanaele), aber NICHT WANN und WOMIT
begruendet: die gemeldete Vorwarnzeit fehlt vollstaendig — ein Vorfall "kam zu spaet" ist
nachtraeglich nicht belegbar. Diese Scheibe ergaenzt fuenf Groessen rein additiv: gemeldete
Vorwarnzeit, Ereigniszeit (Beginn/Ende), Messpunkt, Vergleichsbasis, Quelle.

## Source

- **File:** `src/services/alert_log.py` (`append_entry()`, `append_suppressed_entry()`)
- **Identifier:** neue optionale Schluesselwort-Argumente auf beiden Funktionen, plus eine neue
  Hilfsfunktion `unique_or_none()`

> Schicht: Python-Core (`src/services/`) — kein Go-, kein Frontend-Anteil (Nebenbedingung **D4**
> aus `feat_1459_alert_protokoll.md`: Go liest nur sechs Felder und verwirft den Rest still,
> `internal/store/log.go:48-56`).

## Estimated Scope

- **LoC:** produktiv ~100-150 (Standardlimit 250 reicht rechnerisch, der Workflow hebt es laut
  Auftrag vorsorglich auf 500 an — 5 Aufrufstellen-Dateien verteilen die Aenderung breit statt
  tief), Tests deutlich mehr (13 Aufrufstellen x mehrere Szenarien)
- **Files:** 5 (`alert_log.py` + 4 Aufrufer-Dateien), plus diese Spec
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/alert_log.py::append_entry()` (`:275`) | function | Bekommt die sechs neuen additiven kwargs (fuenf E-1-Groessen + Absenz-Logik) |
| `src/services/alert_log.py::append_suppressed_entry()` (`:402`) | function | Dieselben sechs kwargs, **nur soweit am jeweiligen Gate bereits bekannt** (Punkt 4 unten) |
| `src/services/alert_log.py` (neu) `unique_or_none()` | function | Geteilter Baustein: aus mehreren Werten (Segmenten/Orten/Zeitpunkten EINES Eintrags) den einen gemeinsamen liefern, sonst `None` — reine Mehrdeutigkeitspruefung, keine Neuberechnung |
| `src/services/trip_alert.py` (`:408`, `:1299`, `:1433`, `:1583`, `:1632`, `:2010`, `:2050`) | code | Drei `append_entry`- und vier `append_suppressed_entry`-Aufrufe, alle drei Zweige (Abweichung/Nowcast/amtlich) |
| `src/services/compare_alert.py` (`:327`) | code | `append_entry` Abweichungszweig, Ortsvergleich |
| `src/services/compare_radar_alert.py` (`:199`, `:243`, `:287`) | code | Ein `append_entry`, zwei `append_suppressed_entry`, Nowcast-Zweig Ortsvergleich |
| `src/services/compare_official_alert.py` (`:226`, `:265`) | code | Ein `append_entry`, ein `append_suppressed_entry`, amtlicher Zweig Ortsvergleich |
| `internal/store/log.go` (`:48-56`) | code | Liest **unveraendert** nur sechs Felder — Abnahme-Nachweis fuer D4, keine Aenderung noetig |

## Implementation Details

### Sechs neue additive Schluessel

Beide Schreibfunktionen bekommen dieselben sechs optionalen kwargs, alle default `None`, alle nach
dem etablierten Muster serialisiert (`if wert is not None: entry[schluessel] = wert`) — Absenz statt
`null`, Alt-Eintraege und Eintraege ohne bestimmbaren Wert bleiben schema-identisch zum Bestand:

| kwarg | Typ | Bedeutung |
|---|---|---|
| `lead_time_minutes` | `int \| None` | die **gemeldete** Vorwarnzeit — die Minutenzahl, die tatsaechlich beim Nutzer ankam. **Nur der Nowcast-Zweig** kennt dieses Konzept |
| `event_at` | `str (ISO) \| None` | Ereignisbeginn: Onset-Zeitpunkt (Nowcast) bzw. `valid_from` (amtlich) bzw. Zeitpunkt des ausloesenden Spitzenwerts (Abweichung, nur wenn eindeutig — s. u.) |
| `event_end_at` | `str (ISO) \| None` | voraussichtliches Ende: aus `event_end_minutes` (Nowcast) bzw. `valid_to` (amtlich). **Der Abweichungszweig kennt kein Ende** — strukturell immer `None` |
| `measurement_point` | `dict \| None` | `{"segment_id":, "km_from":, "km_to":}` (Trip) oder `{"location_id":}` (Ortsvergleich) — **nur gesetzt, wenn der Eintrag GENAU EINEN Ort/EIN Segment betrifft** |
| `reference_at` | `str (ISO) \| None` | Vergleichsbasis: Anker-Fetchzeitpunkt (Abweichung) bzw. Briefing-Schnappschusszeitpunkt (Nowcast/Trip). **Die amtliche Warnung hat keine Vergleichsbasis** — strukturell immer `None` |
| `source` | `str \| None` | roher Datenlieferant-Schluessel (`result.source` bzw. `OfficialAlert.source` bzw. `SegmentWeatherData.provider` — jeweils bereits vorhandene Rohwerte, keine neue Formatierung) |

**Der `reason`-Wert des Eintrags (bereits vorhanden: `forecast_change`/`nowcast`/`official_alert`)
ist der Diskriminator, der "diese Groesse gibt es hier strukturell nicht" von "sie war in diesem
Einzelfall nicht bestimmbar" unterscheidbar macht** — bei `reason=official_alert` sind
`lead_time_minutes`/`reference_at` IMMER `None` (kein Aufrufer uebergibt sie je), waehrend bei
`reason=nowcast` ihre Absenz einzelfallbedingt ist (z. B. `onset_minutes is None` im laufenden
Ereignis, S2b). Kein neues Feld noetig — die Unterscheidung steht bereits im Bestand.

### `unique_or_none()` — der einzige neue Verarbeitungsschritt

```python
def unique_or_none(values: Iterable) -> "Any | None":
    """Liefert den einen Wert, wenn alle NICHT-None-Werte uebereinstimmen und
    mindestens einer vorhanden ist; sonst None. Reine Mehrdeutigkeitspruefung
    -- es wird nichts abgeleitet, nur entschieden, ob ein bereits bekannter
    Wert EINDEUTIG genug ist, um ihn zu berichten."""
```

Wird an den Aufrufstellen gebraucht, deren Eintrag MEHRERE Segmente/Orte/Zeitpunkte buendeln kann
(Abweichungszweig: `to_report` mehrere `WeatherChange`; amtlicher Zweig: mehrere Warnungen bzw.
mehrere `_segment_ids`/`loc_ids` je Warnung; Nowcast-Ortsvergleich: mehrere getriggerte Orte in
`triggered`). Ohne diese Pruefung waere ein Eintrag mit zwei Segmenten gezwungen, WILLKUERLICH
eines davon als "den" Messpunkt zu behaupten — genau die Verfaelschung, die E-1 verhindern soll.

### Je Aufrufstelle: was ist WIRKLICH bekannt (geprueft am Code, `5fd9008f`)

**`append_entry()` — immer NACH dem Versandversuch, alles unten Genannte liegt vor:**

| Aufrufstelle | `lead_time_minutes` | `event_at`/`event_end_at` | `measurement_point` | `reference_at` | `source` |
|---|---|---|---|---|---|
| `trip_alert.py:408` (Abweichung) | strukturell `None` | `unique_or_none([c.occurred_at for c in to_report])` | `unique_or_none([c.segment_id for c in to_report])` als `{"segment_id":}` | `anchor_fetched.isoformat()` (`:389`, bereits vorhanden), `None` falls `cached_weather` leer (Erstlauf) | `cached_weather[0].provider` (`SegmentWeatherData.provider`), `None` im Erstlauf |
| `trip_alert.py:1632` (Nowcast) | `result.onset_minutes` | `_onset_dt.isoformat()` (`:1395`, immer gesetzt) / `event_end_minutes`-Ableitung, `None` falls kein Ende bestimmbar | `{"segment_id": active.segment_id, "km_from":, "km_to":}` (immer EIN Segment je Trip-Lauf) | `_snapshot[0].fetched_at.isoformat()` (`weather_snapshot.py:173`, der ECHTE Erzeugungszeitpunkt der Briefing-Momentaufnahme, nicht nur das Datum), `None` falls kein Snapshot fuer den Tag existiert | `result.source` — der ROHE Schluessel, NICHT `radar_svc.source_label(...)` (Korrektur 2026-08-22, s. u. "Korrektur: `source` ist immer der rohe Schluessel") |
| `trip_alert.py:2050` (amtlich) | strukturell `None` | `_alert.valid_from.isoformat()` / `_alert.valid_to.isoformat()`, je Warnung | `unique_or_none(alle _segment_ids ueber die Warnungen dieses Eintrags)` | strukturell `None` | `unique_or_none([a.source for a, _ in official_notices])` |
| `compare_alert.py:327` (Abweichung, Compare) | strukturell `None` | analog Trip, ueber `alle_changes` | analog Trip ueber `t["loc"].id` je Gruppe | `first_anchor_fetched_at.isoformat()` (`:287`, bereits vorhanden) | `cached[0].provider` (`PointWeatherData.provider`) an der Stelle, wo `anchor_fetched_at` heute schon gebaut wird (`:464`) — additiv mitgefuehrt |
| `compare_radar_alert.py:287` (Nowcast, Compare) | `unique_or_none([nc.onset_minutes for _,_,nc in triggered])` | analog, `unique_or_none` ueber alle `triggered`-Nowcasts | `unique_or_none([loc.id for _,loc,_ in triggered])` als `{"location_id":}` | strukturell `None` — es gibt in diesem Pfad KEINE "bereits im Briefing angekuendigt"-Pruefung (anders als Trip) | `unique_or_none([nc.source for _,_,nc in triggered])` |
| `compare_official_alert.py:265` (amtlich, Compare) | strukturell `None` | analog Trip, je Warnung ueber `tagged_alerts` | `unique_or_none(alle loc_ids ueber die Warnungen)` | strukturell `None` | `unique_or_none([a.source for a, _ in tagged_alerts])` |

**`append_suppressed_entry()` — Bekanntheitsgrad haengt vom GATE ab, nicht generell "noch nichts
bekannt" (der bestehende Docstring, `alert_log.py:415-420`, behauptet das pauschal falsch fuer
6 von 7 Aufrufstellen):**

| Aufrufstelle | Gate | Was ist bekannt |
|---|---|---|
| `trip_alert.py:1299` | Cooldown/Ruhezeit, VOR dem Nowcast-Abruf | **Wirklich nichts** — kein `result` existiert noch. Alle sechs Felder `None`. Einzige Stelle, an der der heutige Docstring stimmt |
| `compare_radar_alert.py:199` | Cooldown/Ruhezeit, VOR `_detect_triggered_locations()` | **Wirklich nichts** — analog zu oben |
| `trip_alert.py:1433` | Briefing-Ueberholung | `result` liegt bereits vor (`get_nowcast` lief bei `:1373`) — `lead_time_minutes`, `event_at`/`event_end_at`, `measurement_point`, `source` bekannt; `reference_at` = GENAU der Briefing-Schnappschuss, dessen Ankuendigung hier die Unterdrueckung begruendet — hier am wertvollsten |
| `trip_alert.py:1583` | Ereignis-Identitaet (Entdopplung) | Alles bekannt; `source` aus dem ROHEN `result.source` (nicht aus `_radar_request.source_label`) |
| `trip_alert.py:2010` | Ereignis-Identitaet, amtlich | `_alert.valid_from`/`valid_to`/`.source` bekannt; `measurement_point` bekannt, wenn `_segment_ids` dieser EINEN Warnung genau ein Segment traegt; `lead_time_minutes`/`reference_at` strukturell `None` |
| `compare_radar_alert.py:243` | Ereignis-Identitaet, Nowcast Compare | `nowcast`/`loc` liegen bereits vor (innerhalb der `for name, loc, nowcast in triggered:`-Schleife) — alles bekannt bis auf `reference_at` (strukturell `None`, wie bei `append_entry` dieses Zweigs) |
| `compare_official_alert.py:226` | Ereignis-Identitaet, amtlich Compare | `alert`/`loc_id` liegen einzeln vor (innere Schleife) — `measurement_point={"location_id": loc_id}` immer eindeutig; `event_at`/`event_end_at`/`source` bekannt; `lead_time_minutes`/`reference_at` strukturell `None` |

## Expected Behavior

- **Input:** dieselben lokalen Variablen, die an jeder Aufrufstelle bereits existieren (Beleg-Tabelle
  oben) — keine neue Datenbeschaffung.
- **Output:** `entries`- bzw. `not_delivered`-Eintraege tragen zusaetzlich bis zu sechs neue
  Schluessel, nur wenn bestimmbar. Alt-Eintraege und Eintraege ohne bestimmbaren Wert bleiben
  schema-identisch zum Bestand (byte-identisch fuer Alt-Eintraege).
- **Side effects:** keine neuen. Versand, Kanal-Auswertung, Cooldown, Entdopplung — alles
  unveraendert. Ein Fehler beim Feldbau darf laut Auftrag NIE den Alarm verhindern (Punkt 5,
  Risiko 1 aus dem Kontext-Dokument) — durchgesetzt durch defensive Feldableitung INNERHALB
  `alert_log.py` (jede `None`-Eingabe -> Absenz, nie eine Ausnahme), nicht durch `try/except` an
  den ungeschuetzten `append_entry()`-Aufrufstellen in `trip_alert.py` (`:408`, `:1632`, `:2050`).

## Acceptance Criteria

- **AC-1:** Given ein Trip-Nowcast-Alarm mit bestimmbarem Beginn (`onset_minutes` gesetzt), When
  der Alarm zugestellt und protokolliert wird, Then traegt der `entries`-Eintrag
  `lead_time_minutes` (= `onset_minutes`), `event_at`, `measurement_point` (mit `segment_id`,
  `km_from`, `km_to`) und `source`.
  - Test: `AlarmPruefstrecke.lauf(zweig="radar", ...)` mit einem Segment und bestimmbarem
    Beginn; das geschriebene JSON traegt alle vier Schluessel mit den erwarteten Werten.

- **AC-2:** Given derselbe Trip-Nowcast-Alarm, aber das Ereignis endet nachweislich (bekanntes
  `event_end_minutes`), When protokolliert wird, Then traegt der Eintrag zusaetzlich
  `event_end_at`.
  - Test: Frames mit trockenem Folge-Frame vor Sichtfensterende (Muster aus S2b AC-4); der
    Eintrag traegt `event_end_at` als ISO-Zeitpunkt.

- **AC-3:** Given eine Vorhersage-Aenderung ueber GENAU EIN Segment (ein einzelner `WeatherChange`
  in `to_report`), When der Aenderungsalarm protokolliert wird, Then traegt der Eintrag
  `measurement_point={"segment_id": <das eine Segment>}` und `reference_at` (Anker-Fetchzeitpunkt).
  - Test: `AlarmPruefstrecke.lauf(zweig="deviation", ...)` mit einer Aenderung an einem Segment;
    der Eintrag traegt beide Schluessel.

- **AC-4 (Positivkontrolle zu AC-3):** Given dieselbe Vorhersage-Aenderung, aber ueber ZWEI
  VERSCHIEDENE Segmente in EINEM Protokoll-Eintrag, When protokolliert wird, Then FEHLT
  `measurement_point` in diesem Eintrag vollstaendig (kein willkuerlich gewaehltes Segment).
  - Test: zwei `WeatherChange` mit unterschiedlichem `segment_id` im selben Lauf; der Eintrag
    enthaelt den Schluessel `measurement_point` NICHT. Gegenprobe: mit nur EINEM der beiden
    Segmente (AC-3-Fixture) ist der Schluessel vorhanden — der Unterschied beweist, dass die
    Mehrdeutigkeit tatsaechlich der Grund fuer die Absenz ist, nicht ein durchgehend leerer Pfad.

- **AC-5 (Zweig-Abdeckung amtlich):** Given eine zugestellte amtliche Warnung mit `valid_from`/
  `valid_to`, When protokolliert wird, Then traegt der Eintrag `event_at`/`event_end_at` und
  `source` (= `OfficialAlert.source`), aber NIEMALS `lead_time_minutes` oder `reference_at` —
  auch nicht als `null`, der Schluessel fehlt.
  - Test: `AlarmPruefstrecke.lauf(zweig="official", ...)` mit einer Warnung; `event_at`/
    `event_end_at`/`source` vorhanden, `"lead_time_minutes" not in entry` und
    `"reference_at" not in entry`.

- **AC-6 (Zweig-Abdeckung Abweichung, Positivkontrolle zu AC-5):** Given eine Vorhersage-
  Aenderung wird protokolliert, When derselbe Eintrag gepruft wird, Then fehlt
  `lead_time_minutes` UND `event_end_at` ebenfalls vollstaendig (strukturell, nicht nur in diesem
  Einzelfall) — waehrend derselbe Eintrag `event_at` sehr wohl tragen KANN (AC-3). Der
  Unterschied zwischen "kommt hier nie vor" (`lead_time_minutes`) und "kommt vor, wenn eindeutig"
  (`event_at`) ist am Schema selbst ablesbar.
  - Test: Fixture aus AC-3; `"lead_time_minutes" not in entry` und `"event_end_at" not in entry`,
    waehrend `"event_at" in entry`.

- **AC-7 (Ortsvergleich, Nowcast, Positivkontrolle Ambiguitaet):** Given ein Ortsvergleichs-
  Nowcast-Alarm, der GENAU EINEN Ort ausloest, When protokolliert wird, Then traegt der Eintrag
  `measurement_point={"location_id": <der eine Ort>}`; ausloesend an ZWEI Orten GLEICHZEITIG,
  wenn protokolliert wird, dann fehlt `measurement_point` in diesem zweiten Fall vollstaendig.
  - Test: zwei Compare-Radar-Laeufe ueber die Pruefstrecke, einer mit einem, einer mit zwei
    getriggerten Orten; nur der Ein-Ort-Fall traegt `measurement_point`.

- **AC-8 (Fail-soft, PFLICHT):** Given ein Alarm, bei dem ALLE sechs neuen Groessen nicht
  bestimmbar sind (z. B. eine Vorhersage-Aenderung ohne Vergleichs-Anker — Erstlauf-Situation —
  ueber mehr als ein Segment gleichzeitig), When der Alarm ausgeloest wird, Then wird er TROTZDEM
  zugestellt (mindestens ein Kanal in `channels_sent`) UND vollstaendig protokolliert — der
  Eintrag entsteht ohne Ausnahme, nur ohne die sechs neuen Schluessel.
  - Test: echter Lauf ueber `AlarmPruefstrecke` mit leerem Anker-Snapshot und zwei Segmenten;
    `triggered_count == 1`, der Eintrag existiert und enthaelt keinen der sechs neuen Schluessel.

- **AC-9 (Unterdrueckung, fruehes Gate — nichts bekannt):** Given ein Nowcast-Alarm wird durch
  das Cooldown-/Ruhezeit-Gate VOR dem eigentlichen Radar-Abruf unterdrueckt, When der
  Unterdrueckungs-Eintrag geschrieben wird, Then enthaelt er KEINEN der sechs neuen Schluessel
  (strukturell nichts bekannt an dieser Stelle).
  - Test: Trip mit aktivem Cooldown, Radar-Zweig ausgeloest; der `not_delivered`-Eintrag hat
    `gate_reason` wie bisher, aber keinen der sechs neuen Schluessel.

- **AC-10 (Unterdrueckung, spaetes Gate — Vergleichsbasis ist die Begruendung):** Given ein
  Nowcast-Alarm wird unterdrueckt, WEIL das Briefing die Menge bereits angekuendigt hatte (Gate
  NACH dem Radar-Abruf), When der Unterdrueckungs-Eintrag geschrieben wird, Then traegt er
  `reference_at` (der Briefing-Schnappschusszeitpunkt, der die Unterdrueckung begruendet) sowie
  `lead_time_minutes`/`event_at`/`measurement_point`/`source`.
  - Test: Trip mit vorhandenem, ausreichend angekuendigtem Briefing-Schnappschuss, Nowcast lost
    aus, wird aber wegen Ankuendigung unterdrueckt; der Eintrag traegt alle fuenf genannten
    Schluessel (`event_end_at` ggf. zusaetzlich, wenn ein Ende bestimmbar ist).

- **AC-11 (Mandantentrennung, PFLICHT):** Given zwei verschiedene Nutzer A und B loesen im
  selben Testlauf je einen Nowcast-Alarm fuer ihren jeweils eigenen Trip aus, When beide
  protokolliert werden, Then traegt Nutzer As Eintrag in `data/users/<A>/alert_log.json` As
  eigenen Messpunkt/Vorwarnzeit, Nutzer Bs Eintrag in `data/users/<B>/alert_log.json` Bs eigenen
  — keine Vermischung, keiner der Werte des anderen Nutzers erscheint in der falschen Datei.
  - Test: `AlarmPruefstrecke.lauf(...)` zweimal mit unterschiedlicher `user_id` und
    unterschiedlichen Segment-/Ort-Daten; beide Protokolldateien getrennt gelesen und auf die
    JEWEILS EIGENEN Werte geprueft.

- **AC-12 (Alt-Eintraege unangetastet, PFLICHT mit Gegenprobe):** Given eine bestehende
  `alert_log.json` mit einem Eintrag aus VOR dieser Scheibe (ohne die sechs neuen Schluessel),
  When ein neuer Alarm fuer denselben Nutzer protokolliert wird, Then bleibt der ALTE Eintrag
  byte-identisch (keiner der sechs Schluessel wird nachtraeglich ergaenzt), WAEHREND der NEUE
  Eintrag in DERSELBEN Datei die neuen Schluessel traegt, wo bestimmbar.
  - Test: Fixture-Datei mit einem Alt-Eintrag laden, `append_entry()` fuer denselben `user_id`
    aufrufen, Datei neu einlesen; alter Eintrag `==` Fixture-Alt-Eintrag (dict-Vergleich), neuer
    Eintrag hat mindestens einen der sechs Schluessel. Der Kontrast zwischen den beiden
    Eintraegen in derselben Datei ist die Positivkontrolle: er zeigt, dass die neuen Schluessel
    technisch geschrieben WERDEN, nur eben nicht rueckwirkend.

- **AC-13 (D4-Invarianz, PFLICHT mit Gegenprobe):** Given zwei sonst identische
  `alert_log.json`-Dateien fuer denselben Nutzer, eine MIT den sechs neuen Schluesseln in ihren
  Eintraegen befuellt, eine OHNE, When `internal/store/log.go LoadAlertLog()` bzw.
  `AlertCountByEntity()` auf beide angewendet wird, Then liefern beide Dateien EXAKT dieselbe
  Zahl fuer dieselbe `entity_id`.
  - Test: **Go-Test** in `internal/store/` (Geschwister von `archive_stats_test.go`) — eine
    Python-seitige Nachbildung des Lesevertrags ist AUSDRUECKLICH NICHT zulaessig: sie pruefte
    die Zusicherung dort, wo unser Code steht, nicht dort, wo sie WIRKT. Genau die Schicht,
    die unbekannte Felder verwerfen soll, ist die zu pruefende.
    Zwei Fixture-Dateien, identisch bis auf die sechs neuen Schluessel; beide durch den
    Zaehl-Pfad gejagt; Ergebnis-Zahl identisch. Gegenprobe: eine dritte Fixture mit einem
    ECHT geaenderten der sechs BESTEHENDEN Felder (z. B. `changes_count` erhoeht) MUSS eine
    andere Zahl liefern — das zeigt, dass der Zaehl-Pfad ueberhaupt etwas misst und nicht
    zufaellig immer gleich zaehlt.

- **AC-14 (`unique_or_none()` selbst, PFLICHT mit Gegenprobe):** Given eine Werteliste mit genau
  einem wiederkehrenden Nicht-`None`-Wert (z. B. `["seg-1", "seg-1"]` oder `["seg-1", None]`),
  When `unique_or_none()` aufgerufen wird, Then liefert es diesen einen Wert. Given eine Liste
  mit ZWEI VERSCHIEDENEN Nicht-`None`-Werten (z. B. `["seg-1", "seg-2"]`) ODER einer leeren
  Liste, When aufgerufen wird, Then liefert es `None`.
  - Test: reiner Funktionstest mit den drei Fallgruppen (eindeutig direkt, eindeutig mit
    `None`-Rauschen, mehrdeutig) plus Leerfall; alle vier Erwartungen in einem Test.

- **AC-15 (Protokollfehler darf Alarm nie verhindern, PFLICHT):** Given eine der sechs neuen
  Eingaben an einer ungeschuetzten `append_entry()`-Aufrufstelle (`trip_alert.py:408`, `:1632`
  oder `:2050`) ist unerwartet fehlerhaft geformt (z. B. ein nicht-serialisierbares Objekt statt
  `None`/`str`/`dict`), When der Alarm ausgeloest wird, Then wirft `append_entry()` KEINE
  Ausnahme, die den Alarm verhindert — die defensive Feldableitung in `alert_log.py` faengt den
  Fall ab, der Eintrag entsteht ohne den betroffenen Schluessel statt den Lauf abzubrechen.
  Das Abfangen ist jedoch **nicht still**: es schreibt eine `logger.warning`-Zeile, die den
  betroffenen Schluessel und die `entity_id` nennt. Ein stilles Verschlucken wuerde genau den
  Zweck von E-1 aufheben — das Protokoll behauptete dann "diese Groesse gab es hier nicht",
  wo in Wahrheit ein Defekt vorlag.
  - Test: `append_entry()` direkt mit einem absichtlich falsch geformten Wert fuer eines der
    sechs kwargs aufrufen (z. B. `measurement_point` als String statt `dict`); der Aufruf
    schliesst ohne Ausnahme ab, der geschriebene Eintrag hat den Schluessel entweder korrekt
    oder gar nicht, die Funktion terminiert normal — UND die Warnung ist im Log nachweisbar
    (`caplog`). Gegenprobe: derselbe Aufruf mit einem korrekt geformten Wert erzeugt KEINE
    Warnung; der Unterschied beweist, dass die Warnung den Fehlerfall anzeigt und nicht immer
    erscheint.

## Korrektur: `source` ist immer der rohe Schluessel (2026-08-22)

Die Feldtabelle oben ("roher Datenlieferant-Schluessel ... keine neue Formatierung") und die
Aufrufstellen-Tabelle widersprachen sich: letztere nannte fuer den Trip-Radar-Zweig
`radar_svc.source_label(result.source)`. **Es gilt die Feldtabelle** — `source` traegt in ALLEN
Zweigen und auf BEIDEN Flaechen den rohen Schluessel.

`radar_service.py:531-537` zeigt, was `source_label()` ist: `self._SOURCE_LABELS.get(source, source)`
— eine menschenlesbare **Beschriftung** fuer `format_now_text` und die Anzeige. Zwei Gruende, warum
sie im Protokoll nichts zu suchen hat:

1. **Zwei Vokabulare in einem Feld.** Der Trip-Radar-Zweig schriebe die Beschriftung, der
   Ortsvergleich-Radar-Zweig den rohen Schluessel — dieselbe Quelle staende je nach Flaeche
   unterschiedlich im Protokoll und waere nicht auswertbar. Genau die Regel **O1** aus
   `feat_1459_alert_protokoll.md`: "keine Liste darf ein eigenes Vokabular erfinden".
2. **Beschriftungen aendern sich.** Eine Anpassung an `_SOURCE_LABELS` verschoebe rueckwirkend die
   Bedeutung alter Protokolleintraege, ohne dass sich der Sachverhalt geaendert haette. Ein
   Protokoll haelt fest, was war — nicht, wie es heute heissen wuerde.

Die Aufloesung zur Beschriftung ist beim LESEN billig; die Rueckrichtung ist es nicht.

## Known Limitations

- **Luecke O3** bleibt unberuehrt: der Vorhersage-Aenderungsalarm protokolliert seine
  Unterdrueckungen weiterhin GAR NICHT (eigene Scheibe, D-2, nicht E-1).
- **`compare_radar_alert.py` hat keine "bereits im Briefing angekuendigt"-Pruefung** — anders als
  der Trip-Pfad. `reference_at` bleibt dort deshalb STRUKTURELL immer `None`, nicht einzelfall-
  bedingt. Sollte diese Pruefung je fuer den Ortsvergleich nachgezogen werden, muesste
  `reference_at` dort neu bewertet werden.
- **Keine Migration bestehender Dateien** — Bestandseintraege bleiben unveraendert (Muster
  `capture_id`/#1948, `is_addendum`/#2018).
- **Keine Sichtbarmachung** — weder Go noch Frontend lesen die neuen Felder; das Protokoll bleibt
  internes Werkzeug (D4).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rein additive Feld-Erweiterung nach dem bereits zweimal etablierten Muster
  (`capture_id` #1948, `is_addendum`/`addendum_reported_at` #2018) — keine neue Route, kein neues
  Datenmodell, keine Rueknahme einer bestehenden Architekturentscheidung. Die einzige neue
  Verarbeitungslogik (`unique_or_none()`) ist eine reine Mehrdeutigkeitspruefung ueber bereits
  vorhandene Werte, keine neue Berechnung.

## Changelog

- 2026-08-22: Initial spec created (Scheibe S6 aus #2050, Anforderung E-1, verdichtet aus
  `docs/context/feat-2050-s6-protokoll-vorwarnzeit.md`).
