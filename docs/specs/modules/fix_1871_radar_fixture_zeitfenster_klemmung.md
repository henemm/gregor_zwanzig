---
entity_id: fix_1871_radar_fixture_zeitfenster_klemmung
type: bugfix
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [radar, test-fixture, zeitfenster, wanduhr]
---

# Radar-Fixture-Zeitfenster-Klemmung (#1871)

## Approval

- [ ] Approved

## Purpose

`test_radarpfad_spaetankunft_faellt_nicht_in_alle_segmente_vorbei` ist im Fenster
01:03–04:03 UTC reproduzierbar rot, weil die Test-Fixture selbst (nicht der
Produktivcode) einen Wegpunkt mit unklem Datumskontext auf den Vortag zurückrechnet.
Diese Spec klemmt die Fixture-Zeitrechnung und erweitert den bestehenden
1440-Minuten-Wächter, damit dieselbe Fixture-Klasse künftig zu jeder Tageszeit
bewacht ist.

## Source

- **File:** `tests/unit/test_alarm_zeitfenster_ziel.py`
- **Identifier:** `_radar_mails_fuer_spaetankunft`, `test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster`

> **Schicht:** Python-Core-Testschicht (`tests/unit/`, `tests/tdd/`) — reiner Test-Fix,
> kein Produktivcode betroffen (`src/services/trip_segments.py:154-157` arbeitet
> spezifikationsgemäß).

## Estimated Scope

- **LoC:** ~30 (+25/-5, überwiegend Klemm-Logik + Assertion-Erweiterung + Kommentar-Korrektur)
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `radar_fixture_window/_tz/_ort` (`tests/unit/test_alarm_zeitfenster_ziel.py:302-369`) | Reine Hilfsfunktionen | Bleiben unverändert — andere Invariante (Fensterwahl), nicht wiederverwendbar für die W1-Klemmung |
| `src/services/trip_segments.py:154-157` (Rollover-Mechanismus) | Produktivcode | Bleibt unverändert — arbeitet korrekt für echte mehrtägige Treks (#1091/#1098), die Fixture erzeugt hier nur ein Artefakt |
| `KNOWN_VIOLATIONS` (`tests/tdd/test_fixture_wallclock_ratchet.py:209ff`) | Ratschen-Ausnahmeliste | Begründungskommentar zum Eintrag `_radar_mails_fuer_spaetankunft` wird korrigiert, Eintrag selbst bleibt bestehen |

## Implementation Details

### 1. Klemm-Fix in `_radar_mails_fuer_spaetankunft()` (Zeile 398)

Bisher:
```
start_local = (arrival - timedelta(hours=4)).astimezone(dest_tz)
```

Neu: eine reine Funktion `radar_fixture_start_local(arrival_utc, heute)` analog zu
`radar_fixture_window/_tz/_ort`, die bei `arrival_local.hour < 4` auf lokalen
Tagesbeginn (`00:00` desselben Ortstags) klemmt statt `arrival - 4h` naiv zu
rechnen, und sonst unverändert `arrival - 4h` liefert. Da `_island_taugt()`
(Zeile 323) `hour >= 1` erzwingt, ist `arrival_local.hour` im Bugfenster
garantiert 1–3 — die Klemmung liegt damit immer echt vor der Ankunft
(`00:00 <= arrival_local`), keine Gleichstand-Grenzfälle bei Minute 0.

`_radar_mails_fuer_spaetankunft()` ruft die neue Funktion anstelle der
Inline-Rechnung auf.

### 2. Wächter-Erweiterung (Zeile 551ff, `test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster`)

Keine neue Testfunktion (vermeidet redundante zweite 1440er-Schleife). In der
bestehenden Schleife über die 1440+3 synthetischen Zeitpunkte wird pro Fall
zusätzlich `radar_fixture_start_local(arrival, heute)` berechnet und geprüft:

```
start_local.strftime("%H:%M") <= arrival_local.strftime("%H:%M")
```

als String-Vergleich auf denselben Formatstrings, die `_radar_mails_fuer_spaetankunft()`
tatsächlich in `arrival_calculated` schreibt (Zeilen 407/410) — das ist genau
die Wegpunktfolge (W1 <= W2), die der Rollover-Mechanismus in
`trip_segments.py:154-157` interpretiert.

### 3. Kommentar-Korrektur in `tests/tdd/test_fixture_wallclock_ratchet.py:184-185`

Bisheriger Satz: „Der Schutz ist hier also NICHT schwaecher als die Ratsche,
sondern staerker." ist sachlich falsch — der 1440-Minuten-Wächter deckte bis
zu diesem Fix nur die Fensterwahl ab (`start_hour`/`end_hour`/Ortsdatum), nie
die W1-vs-W2-Wegpunktfolge. Der Satz wird durch eine Formulierung ersetzt, die
präzise beschreibt: der Wächter deckte ursprünglich nur die Fensterwahl ab;
mit diesem Fix (#1871) prüft dieselbe Schleife zusätzlich `start_local <=
arrival_local` und deckt damit auch die W1-vs-W2-Sequenz ab, die den Bug
verursacht hat.

## Expected Behavior

- **Input:** Ankunftszeitpunkt `arrival_utc` (relativ zu `datetime.now()`, keine
  gestellte Uhr), Ortsstunde 1–3 in Atlantic/Reykjavik (der bisherige Bugfall)
  sowie alle anderen 1437 Minuten eines synthetischen Tages plus die 3
  UTC-Mitternachts-Randminuten.
- **Output:** `_radar_mails_fuer_spaetankunft()` liefert bei JEDER Ankunftsstunde
  mindestens eine zugestellte Mail (Randfall-Guard greift, Zielsegment bleibt
  aktiv). Der 1440+3-Wächter bestätigt für jeden synthetischen Fall
  `start_local <= arrival_local` als Zeitstring.
- **Side effects:** keine — reiner Test-/Fixture-Code, keine Produktivpfad-Änderung.

## Acceptance Criteria

- **AC-1:** Given eine Ankunft am Tagesziel mit Ortsstunde 1–3 in Atlantic/Reykjavik
  (der bisher rote Zeitraum 01:03–04:03 UTC) / When `test_radarpfad_spaetankunft_faellt_nicht_in_alle_segmente_vorbei`
  läuft (echte Wanduhr, kein `freeze_time`) / Then liefert `_radar_mails_fuer_spaetankunft()`
  mindestens eine zugestellte Mail, der Test ist grün.
  - Test: `freeze_time` (freezegun) auf einen Zeitpunkt innerhalb 01:03–04:03 UTC
    gestellt (z.B. `2026-08-16T02:30:00`), **frischer Prozess je Datenpunkt**
    (Zustand sickert sonst zwischen mehreren `pytest.main()`-Läufen im selben
    Prozess durch — s. `reference_zeitmatrix_messen_frischer_prozess_je_datenpunkt`),
    `tests/unit/test_alarm_zeitfenster_ziel.py::test_radarpfad_spaetankunft_faellt_nicht_in_alle_segmente_vorbei`
    muss grün sein — vorher (ohne Klemm-Fix) bei diesem Zeitpunkt reproduzierbar rot.
    Zusätzlich Randstellen 01:00/01:03/03:59/04:03 UTC gegenmessen.

- **AC-2:** Given die 1440+3 synthetischen Zeitpunkte aus
  `test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster` / When für
  jeden Fall `radar_fixture_start_local(arrival, heute)` gegen
  `arrival.astimezone(radar_fixture_tz(...))` verglichen wird / Then gilt für
  ALLE 1443 Fälle `start_local.strftime("%H:%M") <= arrival_local.strftime("%H:%M")`
  als Zeitstring-Vergleich.
  - Test: `tests/unit/test_alarm_zeitfenster_ziel.py::test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster`
    (erweitert um die neue Assertion) läuft ohne `AssertionError` über die volle
    Schleife durch.

- **AC-3 (Mutations-Gegenprobe, PFLICHT):** Given die Klemmung in
  `radar_fixture_start_local()` wird per String-Ersetzung zurückgenommen (zurück
  auf `arrival - timedelta(hours=4)` ohne `if arrival_local.hour < 4: ...`-Zweig)
  / When beide Tests aus AC-1 und AC-2 erneut laufen / Then werden BEIDE rot —
  nicht nur einer der beiden.
  - Test: Adversary führt die Mutation an `radar_fixture_start_local()` mit
    externer Sicherungskopie durch (keine `git checkout/stash/reset`), führt
    `tests/unit/test_alarm_zeitfenster_ziel.py::test_radarpfad_spaetankunft_faellt_nicht_in_alle_segmente_vorbei`
    UND `tests/unit/test_alarm_zeitfenster_ziel.py::test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster`
    aus und dokumentiert, dass beide rot werden, bevor die Sicherungskopie
    zurückgespielt wird.

- **AC-4:** Given der KNOWN_VIOLATIONS-Kommentar in
  `tests/tdd/test_fixture_wallclock_ratchet.py:184-185` behauptet aktuell fälschlich
  vollständige Abdeckung durch den 1440-Minuten-Wächter / When der Kommentar auf
  die tatsächliche, jetzt erweiterte Abdeckung korrigiert wird / Then enthält der
  Kommentar keine Aussage mehr, die durch AC-1/AC-2 widerlegt ist (der Wächter
  deckte vor diesem Fix nur die Fensterwahl ab, nicht die W1-vs-W2-Sequenz).
  - Test: `# doc-compliance-test` — manuelle Prüfung, dass der Satz „Der Schutz ist
    hier also NICHT schwaecher als die Ratsche, sondern staerker." in
    `tests/tdd/test_fixture_wallclock_ratchet.py` durch eine sachlich korrekte
    Formulierung ersetzt wurde (kein Verhaltenstest nötig, reine Doku-Korrektur).

## Known Limitations

- Die Klemmung greift nur, weil `_island_taugt()` `hour >= 1` erzwingt — bei
  Ortsstunde 0 würde die Fixture ohnehin nach Auckland ausweichen
  (`radar_fixture_ort`), dieser Fall ist von dieser Spec nicht betroffen und
  bleibt unverändert.
- `radar_fixture_start_local()` ist ausschließlich für diese eine Fixture gedacht
  (`_radar_mails_fuer_spaetankunft`) — keine allgemeine Zeitfenster-Utility für
  andere Radar-Tests.
- Der KNOWN_VIOLATIONS-Eintrag selbst (Zeilen 173-185) bleibt bestehen, da die
  Fixture weiterhin `jetzt`/`heute` referenziert (strukturell notwendig laut
  bestehender Begründung) — nur die Abdeckungsaussage im Kommentar wird korrigiert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Test-Fixture-Fix ohne Berührung von Entscheidungsflächen
  (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma, Test-/Deploy-Strategie).

## Changelog

- 2026-08-16: Initial spec created
