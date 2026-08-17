---
entity_id: fix_1940_fixture_zeitkippkante
type: module
created: 2026-08-17
updated: 2026-08-17
status: draft
version: "1.0"
tags: [test-infrastruktur, ci, zeitzone]
---

# Fix #1940 — Zeitkippkante in `arrival_window_fixtures.fenster_minuten`

## Approval

- [ ] Approved

## Purpose

`fenster_minuten` in `tests/helpers/arrival_window_fixtures.py` verschiebt ein
Ankunftsfenster still nach vorne, wenn der lokale Etappentag noch nicht weit genug
fortgeschritten ist. Dabei bleibt der Abstand zwischen den Wegpunkten erhalten, aber das
Vorzeichen eines gewünschten Versatzes nicht: ein Wegpunkt, den ein Aufrufer bewusst in die
Vergangenheit legen wollte, kann so in die Zukunft rutschen. Drei Aufrufstellen in
`test_issue_822_radar_nowcast_segment.py` verlassen sich genau darauf und brechen dadurch
täglich zu bestimmten Wanduhrzeiten (CI-Job `test`, Issue #1940). Diese Spec beschreibt, wie
der Baustein diese Klasse von Fehlern laut statt still macht und wie die drei betroffenen
Aufrufstellen unabhängig von der Wanduhrzeit werden.

## Source

- **File:** `tests/helpers/arrival_window_fixtures.py`
- **Identifier:** `def fenster_minuten(minuten_jetzt: int, *offsets_min: int) -> tuple[int, ...]` (Zeile 99–153)

> **Schicht-Hinweis:** reine Test-Infrastruktur unter `tests/`. Kein Produktivcode betroffen —
> `src/services/trip_segments.py` verhält sich korrekt; die CI-Rot-Meldungen belegen das
> (gewählte Koordinaten entsprechen dem ersten Wegpunkt/Segment, korrekt gewählt anhand der
> gebrochenen Fixture-Zusicherung, nicht anhand eines Produktivfehlers).

## Estimated Scope

- **LoC:** ~270
- **Files:** 3
- **Effort:** medium

Das liegt über dem Standardbudget von 250 LoC/Workflow. Grund: der Nachweis ist größer als der
Eingriff selbst — der eigentliche Fix in `fenster_minuten` ist wenige Zeilen (ein `raise` statt
einer stillen Verschiebung), aber der Wächter (`test_arrival_window_fixtures.py`) muss auf den
neuen Vertrag umgestellt UND um eine Positivkontrolle über alle 1440 Ortsminuten ergänzt werden,
und die drei Aufrufstellen in `test_issue_822_radar_nowcast_segment.py` brauchen je eine
gestellte Uhr samt Begründung. `workflow.py set-field loc_limit_override 500` ist vorgesehen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/helpers/arrival_window_fixtures.py::past_window_offsets` | Bestandsmuster | Liefert bereits das Vorbild für „laut scheitern statt still liefern" (`ValueError`, Zeile 256) — der neue Vertrag in `fenster_minuten` folgt diesem Muster, keine neue Idee |
| `tests/unit/test_arrival_window_fixtures.py` | Wächter | Muss auf den neuen Vertrag (mögliches `ValueError`) umgestellt werden, sonst blockiert die eigene Ratsche den Fix |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py` | Konsument | Einzige Datei mit „erstes Segment muss bereits vorbei sein"-Bedarf (drei Stellen: Zeile 194, 260, 406); bekommt eine gestellte Uhr statt sich auf die Verschiebung zu verlassen |
| `freezegun` | Test-Library | Bereits im Wächter-Test im Einsatz (Zeile 47, Randzeit-Fälle Zeile 323/352) — etabliertes Mittel für „gestellte Uhr" in diesem Bereich, keine neue Abhängigkeit |

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `tests/helpers/arrival_window_fixtures.py` | MODIFY | `fenster_minuten` (Zeile 99–153): wirft `ValueError`, wenn ein negativ gewünschter Wegpunkt bei der gegebenen Ortsminute nicht mehr vor „jetzt" darstellbar ist, statt das Fenster still nach vorne zu verschieben |
| `tests/unit/test_arrival_window_fixtures.py` | MODIFY | Bestehende Schleifen (Zeile 91/111/129, `range(-1440, 2880)` × `FAMILIEN`) auf `try/except ValueError` umstellen; neue Positivkontrolle ergänzt, die über alle 1440 Ortsminuten beweist, dass außerhalb der Randzone tatsächlich ein „alles vor jetzt"-Fenster entsteht |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py` | MODIFY | Die drei Aufrufstellen mit „vergangenes erstes Segment"-Bedarf (AC-1 Zeile 194, AC-2 Zeile 260, AC-3 Zeile 406) stellen ihre Uhr per `freezegun` auf eine sichere Ortszeit (Tagesmitte), bevor sie `fenster_minuten`/`active_window_offsets` aufrufen |

## Implementation Details

Zwei zusammengehörende Maßnahmen:

1. **Wächter in `fenster_minuten` selbst:** Die Funktion prüft nach der bisherigen
   Vorwärtsverschiebung, ob dadurch ein ursprünglich negativ gewünschter Offset das Vorzeichen
   verloren hat (Wegpunkt läge jetzt bei oder nach `minuten_jetzt`, obwohl der Aufrufer ihn
   davor wollte). Ist das der Fall, wirft die Funktion `ValueError` mit einer Meldung, die die
   verletzte Zusicherung benennt (analog zur bestehenden Meldung in `past_window_offsets`,
   Zeile 256–261) — statt ein Fenster zurückzugeben, das die vom Aufrufer gewünschte
   Vergangenheits-Konstellation nicht mehr trägt. Das schließt die **Klasse** des Fehlers, nicht
   nur den einen im Ticket genannten Fall (AC-3); AC-2 (bisher nicht zugeordnet) und der latente
   AC-1-Fall werden vom selben Wächter mit erfasst.

2. **Reparatur an den drei betroffenen Aufrufstellen:** `test_issue_822_radar_nowcast_segment.py`
   Zeile 194, 260 und 406 stellen ihre Systemuhr per `freezegun.freeze_time` auf eine Ortszeit in
   der Tagesmitte (fern von Mitternacht), bevor sie das Ankunftsfenster über
   `active_window_offsets`/`fenster_minuten` aufbauen. Dadurch ist die von diesen Tests
   verlangte „erstes Segment ist bereits vorbei"-Konstellation zu jeder realen Wanduhrzeit
   herstellbar, und der neue laute Fehler aus Maßnahme 1 wird an diesen drei Stellen nie
   ausgelöst — er bewacht künftige Aufrufer, die denselben Fehler machen würden.

Die im Ticket erwogene Alternative „Etappentag auf morgen legen" scheidet aus: der Produktivpfad
sucht die Etappe über `trip_local_today` (Ortstag, ADR-0044), eine Etappe am Folgetag würde dort
nicht gefunden — das würde die Fixture von der Produktivlogik entkoppeln, die sie eigentlich
nachbilden soll.

## Expected Behavior

- **Input:** `fenster_minuten(minuten_jetzt: int, *offsets_min: int)` — Minute seit
  Ortszeit-Mitternacht des Etappentags, in der „jetzt" liegt (darf negativ oder >1439 sein), plus
  mindestens zwei gewünschte Offsets relativ zu „jetzt" (können negativ sein).
- **Output:** entweder ein Tupel von Wegpunkt-Minuten, das weiterhin allen drei bisherigen
  Zusicherungen genügt (0–1439 für den ersten Wegpunkt, streng monoton steigend, Abstand
  ≤1439) UND zusätzlich jeden negativ gewünschten Wegpunkt bei oder vor `minuten_jetzt` hält —
  oder ein `ValueError`, wenn diese zweite Bedingung an der gegebenen Ortsminute strukturell
  nicht erfüllbar ist.
- **Side effects:** keine (reine Funktion). Die drei Aufrufstellen in
  `test_issue_822_radar_nowcast_segment.py` bekommen als Seiteneffekt eine gestellte
  Systemuhr für die Dauer des jeweiligen Testkörpers.

## Acceptance Criteria

- **AC-1 (lauter Fehler):** Given ein Aufrufer verlangt per negativem Offset einen Wegpunkt in
  der Vergangenheit / When dieser Wegpunkt bei der aktuellen Ortsminute auf dem Etappentag nicht
  mehr vor „jetzt" darstellbar ist / Then scheitert `fenster_minuten` laut mit einer
  Fehlermeldung, die die verletzte Zusicherung benennt — statt ein Fenster zurückzugeben, in dem
  der Wegpunkt nach „jetzt" liegt.
  - Test: Parametrisierter Test ruft `fenster_minuten` für die drei bekannten kaputten
    Minutenbereiche der betroffenen Offset-Familien auf (`(-120, -30, 90)` bei Minute 0–89,
    `(-120, -60, 60)` bei Minute 0–59, `(-240, -120, 120)` bei Minute 0–119) und prüft, dass in
    jedem dieser Fälle `ValueError` geworfen wird — kein Rückgabewert wird akzeptiert.

- **AC-2 (Positivkontrolle, PFLICHT):** Given die aktuelle Ortsminute liegt außerhalb des nicht
  darstellbaren Bereichs einer Offset-Familie / When `fenster_minuten` aufgerufen wird / Then
  liefert es ein Fenster, in dem jeder negativ gewünschte Wegpunkt bei oder vor „jetzt" liegt —
  geprüft über alle Ortsminuten eines Tages und alle betroffenen Offset-Familien, nicht an einem
  einzelnen Stichzeitpunkt.
  - Test: Schleife über `range(0, 1440)` je betroffener Familie; außerhalb des jeweils kaputten
    Bereichs ruft der Test `fenster_minuten` auf und prüft für jeden negativen Offset, dass der
    zugehörige zurückgegebene Wert `<= minuten_jetzt` ist. Der Zähler der außerhalb der
    Randzone verletzten Minuten muss 0 sein. Ohne diesen Test bewacht AC-1 die leere Menge.

- **AC-3 (die Ampel wird grün):** Given die drei Aufrufstellen in
  `test_issue_822_radar_nowcast_segment.py`, die ein bereits vergangenes erstes Segment
  brauchen (Zeile 194 AC-1, Zeile 260 AC-2, Zeile 406 AC-3) / When diese Tests zu einer
  beliebigen Wanduhrzeit laufen — insbesondere in den heute roten Fenstern 12:00–13:30 UTC und
  23:00–00:00 UTC / Then sind sie grün, weil sie ihre Uhr selbst auf eine sichere Ortszeit
  (Tagesmitte) stellen, statt sich auf die Verschiebung in `fenster_minuten` zu verlassen.
  - Test: Die drei AC-Tests laufen je einmal unter `freeze_time` auf 12:30 UTC und einmal auf
    23:30 UTC (den vorher reproduzierbar roten Wanduhrzeiten) und bestehen in beiden Läufen;
    vor der Änderung ist derselbe Lauf ohne gestellte Uhr in genau diesen Fenstern rot.

- **AC-4 (bestehende Zusicherungen bleiben):** Given ein beliebiges Offset-Tupel und eine
  beliebige Ortsminute aus `range(-1440, 2880)` / When `fenster_minuten` aufgerufen wird und
  kein `ValueError` wirft / Then gelten für das zurückgegebene Fenster weiterhin unverändert
  alle drei bisherigen Zusicherungen: erster Wegpunkt liegt in `[0, 1439]`, die Folge ist streng
  monoton steigend, jeder Abstand ist höchstens 1439 Minuten. Der neue laute Fehler ersetzt
  keine dieser drei Prüfungen.
  - Test: Die bestehenden Wächter-Schleifen in `test_arrival_window_fixtures.py`
    (Zeile 91/111/129) werden um `try/except ValueError` ergänzt; für jeden Fall, der NICHT
    wirft, prüfen sie unverändert alle drei bisherigen Zusicherungen, über alle Familien und
    den vollen `range(-1440, 2880)`.

- **AC-5 (keine Kollateralschäden):** Given die 13 übrigen Testdateien nutzen `fenster_minuten`
  nur über die Offset-Familien `(-60, 120)`, `(-60, 180)`, `(-60, 60)` für „ein Segment ist
  jetzt aktiv" / When diese Familien über alle 1440 Ortsminuten eines Tages durchlaufen werden /
  Then wird der neue `ValueError` nie ausgelöst und die 13 Testdateien (samt Fan-out-Helfern
  `_trip()` in `test_briefing_anchor_survives_dispatch_failure.py` und `_radar_trip()` in
  `test_alert_channel_premium_sms.py`) bleiben unverändert grün.
  - Test: Schleife über `range(0, 1440)` für die drei harmlosen Familien ruft `fenster_minuten`
    auf und zählt `ValueError`-Auslösungen; erwarteter Zähler ist 0. Zusätzlich läuft der
    vollständige Testlauf der 13 betroffenen Dateien nach der Änderung unverändert grün durch
    (kein neu rot gewordener Testfall).

- **AC-6 (zweite Ursache im selben Zeitfenster):** Given
  `test_ac4_mail_body_contains_segment_label_and_cooldown`
  (`tests/tdd/test_issue_822_radar_nowcast_segment.py:484`) bestimmt den Etappentag über das
  **Server**datum (`datetime.now(timezone.utc).date()`) statt über den Ortstag / When die
  Testsuite zu einer Uhrzeit läuft, zu der Serverdatum und Ortsdatum auseinanderfallen
  (London UTC+1 ab 23:00 UTC) / Then wird die Etappe nicht gefunden und kein Alarm ausgelöst —
  nach der Änderung nutzt die Stelle `stage_date(lat, lon)` wie die fünf übrigen Stellen
  derselben Datei, und der Test ist zu jeder Wanduhrzeit grün.
  - Test: Die Uhrzeit-Matrix aus AC-3 nimmt diesen Testfall in den Messbereich auf; vor der
    Änderung weicht sein Ergebnis zwischen den gemessenen Uhrzeiten ab (rot an der Kippkante,
    grün sonst), nach der Änderung ist es an allen Messpunkten identisch grün.
  - Herkunft: in der RED-Phase gemessen, nicht aus dem Ticket. Andere Ursache als AC-1 bis
    AC-5 (Serverdatum statt Ortstag, nicht die stille Verschiebung), aber dasselbe
    Zeitfenster. Ohne AC-6 bliebe die CI-Ampel trotz bestandener AC-1 bis AC-5 täglich
    23:00–00:00 UTC rot — das Ticketziel wäre verfehlt. Vom PO am 2026-08-17 ausdrücklich in
    den Umfang aufgenommen.

- **AC-7 (dritte Fundstelle derselben Klasse — die Schwesterfunktion):** Given
  `past_window_offsets` (`tests/helpers/arrival_window_fixtures.py:220-277`) **staucht** das
  Fenster still auf `[0, obergrenze]`, wenn die gewünschte Spanne nicht mehr auf den
  vergangenen Teil des Etappentags passt (Z. 270–275) / When ein Aufrufer damit ein
  garantiert abgelaufenes Segment herstellen will und die Ortszeit früh ist (gemessen:
  Ortsminute 0–239 in Neuseeland = 12:00–16:00 UTC, Fenster schrumpft von zwei Stunden auf
  vier Minuten) / Then endet das Ziel-Segment erst in der Zukunft, ein Alarm feuert, und
  `test_issue_818_radar_briefing_integration.py::test_ac5_past_segment_no_alert_guard_test`
  scheitert — nach der Änderung verweigert `past_window_offsets` diesen Fall laut, wie
  `fenster_minuten` es nach AC-1 tut, und die Aufrufstelle stellt ihre Uhr selbst.
  - Test: Die Uhrzeit-Matrix nimmt `test_issue_818_radar_briefing_integration.py` in den
    Messbereich auf; vor der Änderung weicht das Ergebnis zwischen 11:55 und 12:05 UTC ab,
    nach der Änderung ist es an allen Messpunkten identisch grün. Zusätzlich ein
    Wächter-Test, der die laute Verweigerung im nicht darstellbaren Bereich erwartet, mit
    Zähler gegen trivial-grün.
  - Herkunft: in der GREEN-Phase gemessen und unabhängig gegengeprüft (Stauchung empirisch:
    11:55 UTC → `('19:55','21:55')`, 12:05 UTC → `('00:00','00:04')`). Dieselbe Fehlerklasse
    wie AC-1, andere Funktion. Ohne AC-7 bliebe die CI-Ampel täglich **vier Stunden**
    (12:00–16:00 UTC) rot — mehr als die im Ticket gemeldeten anderthalb. Vom PO am
    2026-08-17 in den Umfang aufgenommen, Zeilenbudget auf 800 erhöht.

## Known Limitations

- Ein latenter dritter Fall bleibt teilweise ungeprüft: die Aufrufstelle Zeile 194 (AC-1)
  verliert die Vergangenheits-Konstellation ebenfalls im Fenster 22:00–00:00 UTC, prüft das
  aber selbst nicht (nur Bit-Identität und Monotonie). Sie wird von dieser Spec mitgehärtet
  (gestellte Uhr, siehe AC-3), ist aber heute kein sichtbarer CI-Ausfall — die Härtung schließt
  eine Lücke, bevor sie sichtbar wird, nicht eine bereits beobachtete.
- Der reale Wertebereich von `minuten_jetzt` im Produktivpfad ist `[0, 1439]`
  (`_tagesbezug`, Zeile 208). Der Wächter (`test_arrival_window_fixtures.py`) prüft absichtlich
  weit darüber hinaus (`range(-1440, 2880)`); der neue Vertrag von `fenster_minuten`
  (`ValueError` bei nicht darstellbarer Vergangenheits-Konstellation, sonst die drei
  bestehenden Zusicherungen) muss auch für diesen erweiterten Bereich definiert und geprüft
  sein, nicht nur für den real vorkommenden.
- Die im Ticket erwogene Variante „Etappentag auf morgen legen" scheidet aus: der Produktivpfad
  sucht die Etappe über den Ortstag (`trip_local_today`, ADR-0044); eine Etappe am Folgetag
  würde dort nicht gefunden. Diese Spec verfolgt diese Richtung deshalb nicht weiter.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Test-Infrastruktur unter `tests/helpers/` und `tests/tdd/` — kein
  Produktivcode, keine Änderung an Kanälen, Providern, Datenmodell/Persistenz, Auth,
  Editor-Paradigma oder Test-/Deploy-Strategie. Der Fix folgt zudem einem bereits im selben
  Modul etablierten Muster (`past_window_offsets` scheitert bereits laut statt still zu
  liefern) und führt keine neue Entscheidungsfläche ein.

## Changelog

- 2026-08-17: Initial spec created
- 2026-08-17: AC-6 ergänzt — in der RED-Phase gemessener zweiter Ausfallgrund im selben
  Zeitfenster (Serverdatum statt Ortstag, `test_issue_822_radar_nowcast_segment.py:484`).
  Vom PO ausdrücklich in den Umfang aufgenommen, weil die CI-Ampel sonst trotz erfüllter
  AC-1 bis AC-5 täglich 23:00–00:00 UTC rot bliebe. Erste Limitation entsprechend
  entschärft: die Aufrufstelle Z. 194 bleibt der einzige verbliebene latente Fall.
