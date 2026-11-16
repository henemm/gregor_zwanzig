---
entity_id: fix_3081_flaky_kerntests
type: bugfix
created: 2026-11-16
updated: 2026-11-16
status: draft
version: "1.0"
workflow: fix-3081-flaky-kerntests
tags: [tests, stabilitaet, kern-schicht, radar, alarm, "#3081", "#1196"]
---

# Kern-Tests stabilisieren (Issue #3081, Teil von #1196)

## Approval

- [ ] Approved

## Purpose

Zwei Kern-Tests der Alarm-/Radar-Familie wackeln und machen die Kern-Schicht zeitweise rot, obwohl der Produktionscode spec-konform arbeitet. Diese Spec benennt die Ursache je Test, stabilisiert den Testaufbau ohne Retry, Skip oder Aufweichen der Zusicherungen und hält ehrlich fest, wo die Ursache nicht belegt ist.

## Source

- **File:** `tests/tdd/test_radar_parallel_fetch.py`, `tests/tdd/test_alert_channel_threshold.py`, `tests/conftest.py`
- **Identifier:** `test_ac4_trip_grenzabbruch_im_worker_bricht_die_einheit_ab`, `test_ac5_compare_grenzabbruch…`, `test_ac11_ortsvergleich_alarm_unveraendert_trotz_trip_kanal_schwellen`, autouse-Fixture für `parallel_fetch._reset_for_tests()`

> Schicht-Hinweis: nur Tests (Python-Core-Testschicht `tests/`). Kein Frontend, keine Go-API, kein Produktionscode unter `src/`, `api/`.
> Querschnitt: keine Nutzerdaten bewegt (Mandantentrennung unberührt, Tests nutzen weiterhin eindeutige `uid` je Test); keine Änderung an Briefing- oder Alarm-Inhalt, alle vier Kanäle unberührt; kein Trip/Compare-Pendant-Baustein im Sinne der Editor-Teilung (AC-4 und AC-5 decken beide Seiten ab).

## Estimated Scope

- **LoC:** ca. +45/-8
- **Files:** 3 (nur Tests)
- **Effort:** low (Risiko LOW)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/parallel_fetch.py` (`fetch_ordered`, `wait`, `_reset_for_tests`) | module | Prozessweiter Executor/Semaphor; Naht und Reset |
| `src/services/radar_service.py` (`hole_nowcasts`, `wirf_radar_grenze`, `RadarDeadlineExceeded`) | module | Grenzabbruch-Logik, unverändert |
| `src/services/trip_alert.py` | module | Radar-Lauf mit `hit_deadline`, unverändert |
| `src/services/compare_official_alert.py`, `official_alerts.py` | module | Compare-Amtswarnung in AC-11, unverändert |
| `tests/tdd/test_compare_official_alert.py` | test | Fixtures für AC-11 |
| `concurrent.futures.wait`, `threading.Event` | stdlib | Echtes Warten, Synchronisation im Test |
| freezegun | lib | Uhrsteuerung in Radar-Tests |

## Implementation Details

**Befund 1 (Ursache belegt): Radar AC-4.** Der Uhrsprung um ca. 1000 s passiert im Worker, während der Hauptfaden noch Aufgaben einreicht (Open-Meteo-Semaphor mit 3 Slots bei 4 Folgepunkten). Danach ist das Warte-Zeitlimit des Hauptfadens 0. Ob der Worker mit dem Grenzabbruch bis dahin fertig ist, entscheidet der Zufall: Ist er fertig, kommt der Abbruch als Fehler an (Neuwurf, Einheit abgebrochen, Test grün). Läuft er noch, wird er als `skipped="timeout"` eingesammelt (Lücke, `hit_deadline=False`, Test rot). Beide Zweige sind im Produktionscode gewollt (AC-8 bzw. AC-4 der Radar-Spec); der Test stellt seine Vorbedingung nicht her. Reproduziert: Datei allein 3 von 8 bzw. 2 von 4 Läufen rot.

**Fix nur im Test:**
- Dünne Naht: `monkeypatch.setattr(parallel_fetch, "wait", _wait_mit_signal)`. Die Funktion setzt ein `threading.Event` und delegiert unverändert an das echte `concurrent.futures.wait` (kein Mock-Theater, echtes Verhalten).
- Der Worker (`bei_anfrage` für AROME des 3. Soll-Punkts) wartet mit Zeitlimit auf dieses Event und springt erst dann mit der Uhr. Bei Ablauf des Zeitlimits bricht ein Testaufbau-Assert mit klarer Meldung ab (kein stilles Weiterlaufen).
- Das Warte-Zeitlimit des Hauptfadens ist dann vor dem Sprung berechnet und groß; der werfende Worker liefert sicher `error=RadarDeadlineExceeded`, der Neuwurf greift, die Einheit wird abgebrochen.
- Kein Deadlock: Der wartende Worker hält 1 von 3 Slots, die übrigen Punkte laufen über die 2 anderen.
- AC-5 (Compare-Grenzabbruch) bekommt dasselbe Muster statt `time.sleep(0.4)`, das den Wettlauf nur maskiert.
- Zusicherungen bleiben wörtlich gleich. Mutations-Gegenprobe: Mutation 6 der S4-Spec („RDE im Hauptfaden zu Lücke") muss AC-4 weiterhin rot machen.

**Befund 2 (Ursache NICHT belegt): AC-11.** Das gemeldete Symptom (`alerts_sent=0`, E-Mail leer, reihenfolgeabhängig) ließ sich nicht reproduzieren: 6 Batch-Läufe der `test_alert*`-Familie (4 davon gemischt), 1 breiter Batch (284 Dateien, AC-11 zuletzt), 7 Tageszeiten unter eingefrorener Uhr und Einzelläufe waren stets grün. Hypothesen „Modul-Import unter eingefrorener Uhr" und „Tageszeit" sind verworfen. Es gibt keinen Fix auf Verdacht. Stattdessen:
- (a) Testhygiene: autouse-Fixture in `tests/conftest.py` ruft nach jedem Test `parallel_fetch._reset_for_tests()` auf. Prozessweiter Executor (8 Worker) und Semaphor `official_alerts` (3 Slots) werden sonst zwischen Tests nicht zurückgesetzt; nachlaufende Worker früherer Tests könnten den Warn-Abruf des Compare-Dienstes verdrängen. Das ist der einzige gefundene testübergreifende Kanal, aber nur ein plausibler, nicht bewiesener Mechanismus.
- (b) Diagnose: Die Fehlermeldung von AC-11 nennt `last_failed_count` und `last_checked_count`; die Zusicherung bleibt unverändert. Ein künftiger Rotlauf benennt damit seine Ursache.
- (c) DoD-Nachweis: je 10 Läufe einzeln, im Batch mit `tests/tdd/test_alert*`-Dateien und in zufälliger Reihenfolge (Mischplugin im Scratchpad, nicht im Repo, Dateien wörtlich benannt wegen Gate gegen breite Läufe). Ergebnis wird im Issue dokumentiert. Ehrlich festgehalten: Ob (a) die ursprüngliche Beobachtung behebt, ist nicht belegbar.

**Befund 3 (AC-9-Trip-Flake):** In 8 Einzel- und 4 Batch-Läufen nicht aufgetreten. Nach dem AC-4-Fix 10× Datei-Lauf beobachten; kein eigener Fix.

**Nebenbefund (out of scope, eigenes Issue):** Unter echter Uhr endet `wait` genau an der Frist, ein Worker bemerkt sie erst an der nächsten Kettengrenze. Der AC-4-Zweig ist in Produktion damit praktisch unerreichbar; eine mitten in der Parallelphase ablaufende Frist führt in den AC-8-Zweig (Lücken, keine falsche Entwarnung, aber Abweichung von der Absicht aus ADR-0082). Bewertung gehört in ein eigenes Issue (Strang A).

## Expected Behavior

- **Input:** Die Kern-Tests Radar-AC-4, Radar-AC-5, AC-9 und Alarm-AC-11 laufen einzeln, im Batch und in zufälliger Reihenfolge.
- **Output:** Je 10 Läufe jeder Variante grün; Zusicherungen unverändert scharf; ein Rotlauf von AC-11 nennt failed/checked-Zähler.
- **Side effects:** Nach jedem Test ist der prozessweite Parallelabruf zurückgesetzt. Kein Produktionscode ändert sich.

## Scope

| Datei | Änderung | Geschätzte LoC |
|-------|----------|----------------|
| `tests/tdd/test_radar_parallel_fetch.py` | AC-4 und AC-5: Uhrsprung an „Hauptfaden wartet" koppeln (Event-Naht an `parallel_fetch.wait`) | ~+30/-6 |
| `tests/conftest.py` | autouse-Fixture: `parallel_fetch._reset_for_tests()` nach jedem Test | ~+8 |
| `tests/tdd/test_alert_channel_threshold.py` | AC-11-Fehlermeldung nennt failed/checked, Zusicherung unverändert | ~+7/-2 |
| **Total** | | **~+45/-8** |

### Out of Scope

- Produktionscode unter `src/`, `api/` (keine Änderung)
- Nebenbefund „AC-4-Zweig in Produktion praktisch unerreichbar" (ADR-0082): eigenes Issue
- Fix auf Verdacht an AC-11-Fixtures oder am Compare-Dienst
- Zufallsreihenfolge-Plugin dauerhaft ins Repo aufnehmen

## Definition of Done

- Ursache je Test benannt: Radar-AC-4 belegt (Wettlauf im Testaufbau), AC-11 ehrlich als nicht reproduzierbar dokumentiert (verworfene Hypothesen, Hygiene + Diagnose).
- Kein Retry, kein Skip, keine aufgeweichte Zusicherung.
- Je 10 Läufe grün: einzeln, im Batch mit `tests/tdd/test_alert*` und in zufälliger Reihenfolge (AC-7), Nachweis im Issue #3081.
- Mutations-Gegenprobe: Mutation 6 macht AC-4 weiter rot (AC-2).
- Eigenes Issue für den Nebenbefund angelegt (AC-9).

## Test Plan

### Kern-Tests (bestehende Dateien, Aufbau geändert)

- [ ] `tests/tdd/test_radar_parallel_fetch.py::test_ac4_trip_grenzabbruch_im_worker_bricht_die_einheit_ab`: 10× einzeln grün, `hit_deadline` wahr (AC-1)
- [ ] `tests/tdd/test_radar_parallel_fetch.py::test_ac5_compare_grenzabbruch…`: 10× grün, Zusicherungen wörtlich gleich (AC-3)
- [ ] Testaufbau-Zeitlimit: kein Hänger, eindeutige Meldung bei Ablauf (AC-4)
- [ ] Reset-Fixture: belegter Slot von `official_alerts` ist im Folgetest frei (AC-5)
- [ ] AC-11 mit Mutation „leere E-Mail": rot, Ausgabe nennt `last_failed_count`/`last_checked_count` (AC-6)

### Stabilitäts- und Mutationsnachweis

- [ ] 30 Läufe (einzeln / Batch / gemischt) für Radar-AC-4, AC-9, Alarm-AC-11 grün (AC-7)
- [ ] Mutation 6 der S4-Spec macht AC-4 rot (AC-2)

## Acceptance Criteria

- **AC-1:** Given der Radar-Test zum Grenzabbruch im Worker (Trip) mit synchronisiertem Uhrsprung / When die Testdatei 10-mal hintereinander einzeln ausgeführt wird / Then ist `test_ac4_trip_grenzabbruch_im_worker_bricht_die_einheit_ab` in allen 10 Läufen grün und `hit_deadline` ist jedes Mal wahr.
  - Test: 10 Einzelläufe von `tests/tdd/test_radar_parallel_fetch.py`, Exit-Code 0 je Lauf; kein Retry, kein Skip.

- **AC-2:** Given der Radar-Grenzabbruch im Hauptfaden wird gezielt zu einer Lücke verfälscht (Mutation 6 der S4-Spec, per String-Ersetzung mit externer Sicherung) / When der stabilisierte AC-4-Test läuft / Then wird er rot, die Zusicherung ist also so scharf wie zuvor.
  - Test: Mutations-Gegenprobe durch den implementation-validator; ohne Verfälschung grün, mit Verfälschung rot.

- **AC-3:** Given der Compare-Grenzabbruch-Test (AC-5) mit Event-Synchronisation statt fester Wartezeit von 0,4 Sekunden / When die Radar-Testdatei 10-mal ausgeführt wird / Then ist AC-5 in allen Läufen grün und die Zusicherungen sind wörtlich unverändert.
  - Test: 10 Läufe von `tests/tdd/test_radar_parallel_fetch.py`; Diff zeigt keine geänderte assert-Zusicherung, nur Aufbau.

- **AC-4:** Given der synchronisierte Aufbau wartet auf das Signal „Hauptfaden wartet auf Ergebnisse" / When dieses Signal nicht innerhalb des Zeitlimits eintrifft / Then bricht der Test mit einer eindeutigen Testaufbau-Meldung ab, statt zu hängen oder still weiterzulaufen.
  - Test: Der Aufbau enthält ein Zeitlimit mit Assert; bei normalem Lauf kommt das Signal sicher vor Ablauf (kein Hänger über alle Läufe).

- **AC-5:** Given der prozessweite Parallelabruf hat nach einem vorherigen Test Zustand hinterlassen / When der nächste Test beginnt / Then ist der Executor samt Semaphoren zurückgesetzt (autouse-Fixture nach jedem Test), sodass kein Test vom Zustand eines früheren abhängt.
  - Test: Ein Test belegt Slots des Semaphors `official_alerts` bewusst nach Testende; der folgende Test sieht freie Slots und einen frischen Executor.

- **AC-6:** Given der AC-11-Test (Ortsvergleich-Alarm unverändert trotz Trip-Kanal-Schwellen) / When er scheitert / Then nennt seine Fehlermeldung `last_failed_count` und `last_checked_count` des Compare-Dienstes, und die Zusicherung selbst ist gegenüber vorher unverändert.
  - Test (Verhalten): Bei absichtlich herbeigeführtem Scheitern (Mutation: Compare-Warnung liefert nichts ⇒ leere E-Mail) ist der Test rot, und die pytest-Ausgabe nennt `last_failed_count` und `last_checked_count`; ohne Mutation bleibt er grün.

- **AC-7:** Given Radar-AC-4, AC-9 und Alarm-AC-11 / When sie je 10-mal einzeln, 10-mal im Batch mit den `tests/tdd/test_alert*`-Dateien und 10-mal in zufälliger Reihenfolge laufen / Then sind alle 30 Läufe grün (Exit-Code 0), ohne Retry oder Skip.
  - Test: Läufe mit wörtlich benannten Dateien und Mischplugin (Seeds je Lauf notiert); Ergebnis als Kommentar im Issue #3081.

- **AC-8:** Given die Ursache von AC-11 ist nicht reproduzierbar / When die Ergebnisse im Issue #3081 dokumentiert werden / Then steht dort ehrlich, dass die AC-11-Ursache nicht belegt ist, welche Hypothesen verworfen wurden und dass der Reset (AC-5) eine Hygienemaßnahme ohne Beweis ist; für Radar-AC-4 steht die belegte Ursache.
  - Test: Issue-Kommentar vorhanden mit Ursache je Test (AC-4 belegt, AC-11 offen) und dem 30-Läufe-Nachweis.

- **AC-9:** Given der Nebenbefund zur praktisch unerreichbaren AC-4-Zweigs in Produktion (ADR-0082) / When der Fix abgeschlossen ist / Then existiert dafür ein eigenes GitHub-Issue, und im Produktionscode (`src/`, `api/`) hat sich nichts geändert.
  - Test: Issue-Nummer im #3081-Kommentar; Diff der Lieferung enthält ausschließlich Dateien unter `tests/` (und Doku).

## Known Limitations

- AC-11 bleibt ursächlich ungeklärt; der Fix ist Hygiene plus Diagnose, kein Beweis. Tritt der Rotlauf erneut auf, liefert die geschärfte Fehlermeldung die Ursache.
- Der AC-9-Trip-Flake ist nicht reproduziert; nur Beobachtung (10 Dateiläufe nach dem Fix).
- Die Naht patcht `parallel_fetch.wait` im Test; sie delegiert an das echte `wait`, ändert also kein Verhalten, koppelt den Test aber an diesen Importnamen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Stabilisierung ohne Änderung an Entscheidungsflächen; Produktionsverhalten (ADR-0082, Radar-Spec AC-4/AC-8) bleibt unverändert. Die Abweichung zwischen ADR-Absicht und Produktionsverhalten wird in einem eigenen Issue bewertet.

## Changelog

- 2026-11-16: Initial spec created
