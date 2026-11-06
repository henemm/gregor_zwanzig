---
entity_id: fix_2744_uhrzeitunabhaengige_tests
type: bugfix
created: 2026-11-06
updated: 2026-11-06
status: draft
version: "1.0"
tags: [tests, ci, wanduhr, zeitzone, issue-2744, epic-1196]
---

# Fix #2744 — Python-Tests zu jeder Tageszeit grün (Uhr, Zonenwahl, Minutenwechsel)

## Approval

- [ ] Approved

## Purpose

Mehrere Python-Tests lesen die echte Uhr und werden kurz vor UTC-Mitternacht bzw. am Minutenwechsel rot
und blockieren dann Merges (CI-Job `test`). Diese Lieferung stellt sie so um, dass sie zu jeder Tageszeit
dasselbe Ergebnis liefern. Es ändert sich **ausschließlich Testcode**, kein Produktivcode.

## Source

- **Dateien (alle Tests):**
  - `tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py` (f002-Tests, Hilfen `fenster_um_jetzt`, `ortstag`, `trip_zwei_zonen`)
  - `tests/tdd/test_prozesszonen_schalter.py` (`_gestern_zone_fuer_jetzt`)
  - `tests/tdd/test_ortstag_helfer.py` (Zonenwahl im Test `test_utc_tag_unter_gestern_zone_weicht_vom_prozesstag_ab`)
  - `tests/unit/test_briefing_html_sprache.py` (`test_ac1_deutsch_ohne_lang_gleich_lang_de`)
  - `tests/tdd/test_alert_sms_location_positions.py` (Test um Zeile 1049, `R@HH:MM`)
  - ggf. gemeinsame Zonen-Hilfe unter `tests/helpers/`
- **Schicht:** Python-Tests; Prüflinge `trip_alert`, `alert_daily_limit`, `trip_day`, Briefing-Renderer bleiben unverändert.

## Ursachen (gemessen, 2026-11-06)

1. **f002-Tests:** lesen `datetime.now(UTC)` selbst; die heutige Etappe des Test-Trips liegt auf dem UTC-Tag. Bei 23:40 UTC
   ist in Auckland schon der Folgetag, das Kontingent in Los Angeles ist eine andere Zählerzone: beide Tests rot
   (nachgestellt mit `GZ_TEST_WALL_CLOCK_UTC=2026-11-05T23:40:00+00:00`, bei 12:00 UTC grün). Das entspricht der in
   `trip_day.anchor_tz` dokumentierten Grenze (Weltzeit-Tag trifft die Etappe, Ortstag kann einen Tag daneben liegen),
   ist also ein Testartefakt und kein Produktfehler.
2. **Gestern-Zone-Tests:** die gewählte Zone `<-2330>+23:30` trägt nur bis 23:30 UTC. Gemessen: die Zone `<-24>+24`
   liefert um 00:00:00, 23:45:00 und 23:59:59 UTC jeweils den UTC-Tag minus 1, trägt also den **ganzen** UTC-Tag.
   Zusätzlich ist die Grenze zwischen Marquesas und der zweiten Zone uneinheitlich (09:30 gegen 09:00 UTC).
3. **Briefing-HTML:** zweimaliges Rendern mit Erzeugungszeitstempel `HH:MM`; am Minutenwechsel unterscheiden sich die Läufe.
4. **`R@HH:MM`-SMS-Test:** der Konstruktor leitet `onset_time` aus `datetime.now()` ab; liegt „jetzt + Vorlauf“ nach
   Mitternacht, steht `R@Mo0:03` statt `R@0:03` im Text.

## Scope

- **Enthalten:** Umstellung der unter „Source“ genannten Tests auf feste Uhr bzw. tragende Zonenwahl; eine gemeinsame Zonen-Hilfe in `tests/helpers/`.
- **Nicht enthalten:** Produktivcode, Wanduhr-Schalter (#2096), Prozesszonen-Knopf (#2314), Briefing-Zeitstempel im Produkt.

## Definition of Done

Die betroffenen Tests sind mit gestellter Uhr (`GZ_TEST_WALL_CLOCK_UTC`) um 12:00, 23:40 und 23:58 UTC sowie im Normallauf grün; die beiden Mutations-Gegenproben (AC-2, AC-6) sind rot nachgewiesen; es ändert sich kein Produktivcode.

## Test Plan

- Zuerst RED: Die Tests unter gestellter Uhr 23:40 UTC (f002), 23:55 UTC (`R@HH:MM`) und am Minutenwechsel (Briefing) rot nachweisen; Zonenwahl-Test für 23:45 UTC rot nachweisen.
- Dann GREEN: Umbau gemäß Implementation Details.
- Prüfung: dieselben benannten Testdateien bei 12:00, 23:40 und 23:58 UTC; Mutations-Gegenproben per String-Ersetzung mit externer Sicherungskopie (kein `git checkout/stash/reset`); `uv run pytest` immer mit benannten Testdateien.

## Estimated Scope

- **LoC:** ~80–120
- **Files:** 5–6
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| freezegun (`freeze_time`) | Testbibliothek | feste Uhr pro Test, Suite-Standard |
| `tests/conftest.py` `_gestellte_wanduhr`, `GZ_TEST_WALL_CLOCK_UTC` | Schalter (#2096) | Nachweis-Werkzeug, bleibt unverändert |
| `GZ_TEST_PROCESS_TZ` im Root-`conftest.py` (#2314) | Schalter | Prozesszone, bleibt unverändert |

## Implementation Details

- **Festzeitpunkt für f002:** `freeze_time("2026-08-12 09:30:00+00:00")` je f002-Test (nur diese Datei-Abschnitte,
  ohne `tick`). Begründung: Auckland (UTC+12 im August) und Los Angeles (UTC−7) liegen dann beide am selben Kalendertag
  wie UTC (Auckland 21:30, Los Angeles 02:30, Wien 11:30); die ±45-Minuten-Fenster bleiben unterscheidbar.
  Gilt für alle Zeitquellen im Test (`fenster_um_jetzt`, `ortstag`, `trip_zwei_zonen`, `local_today`, Prüfling).
- **Gestern-Zone:** eine gemeinsame Hilfsfunktion (`tests/helpers/`) liefert für die echte Startzeit eine tragende Zone.
  Sie wählt durchgehend `<-24>+24`. Beide Testdateien benutzen sie statt eigener Stundengrenzen. Die echte Zeit wird
  weiter per `date -u` im Subprozess gelesen (#2096), damit die Aussage „Schalter wirkt im echten Prozess“ erhalten bleibt.
- **Briefing-HTML:** beide `render_reich()`-Aufrufe in einem gemeinsamen `freeze_time`-Block.
- **`R@HH:MM`:** `freeze_time` auf Mittag UTC um den Aufruf, sodass „jetzt + Vorlauf“ am selben Tag bleibt.

## Expected Behavior

- **Input:** Testlauf zu beliebiger Tageszeit, auch mit `GZ_TEST_WALL_CLOCK_UTC` zwischen 23:30 und 24:00 UTC.
- **Output:** dieselben Tests sind grün, mit demselben fachlichen Inhalt.
- **Side effects:** keine; Produktivcode unverändert.

## Acceptance Criteria

- **AC-1:** Given die beiden f002-Tests (`..._ruhezeit_folgt_der_heutigen_etappe_nicht_der_ersten`, `..._tageszaehler_folgt_der_heutigen_etappe_nicht_der_ersten`) und die gestellte Wanduhr `GZ_TEST_WALL_CLOCK_UTC=2026-11-05T23:40:00+00:00` / When sie laufen / Then sind beide grün (vorher rot), und bei 12:00 UTC bleiben sie grün.
  - Test: beide Läufe aus Nutzersicht der Suite (Wanduhr gestellt), vorher rot belegt.
- **AC-2:** Given die Verfälschung `anchor_tz(trip, now)` → `trip_tz(trip)` im Prüfling `trip_alert` / When die f002-Tests unter der festen Uhr laufen / Then werden beide rot (Mutations-Gegenprobe, die Zusicherung wirkt dort, wo sie gilt).
  - Test: Mutation per String-Ersetzung mit externer Sicherungskopie, durch den Validator.
- **AC-3:** Given die Gestern-Zone-Tests (`test_ac2_gestern_zone_liefert_prozesstag_gleich_utc_tag_minus_eins`, `test_utc_tag_unter_gestern_zone_weicht_vom_prozesstag_ab`) / When sie zu einer echten Startzeit zwischen 23:30 und 24:00 UTC laufen / Then wählen sie eine tragende Zone und sind grün; die Zonenwahl steht an EINER Stelle für beide Dateien.
  - Test: die Hilfsfunktion wird für jeweils eine echte Zeit um 00:00, 09:15, 09:45, 23:45 UTC in einem Subprozess mit der gewählten Zone gegengeprüft (Prozesstag = UTC-Tag − 1).
- **AC-4:** Given der Test `test_ac1_deutsch_ohne_lang_gleich_lang_de` / When die beiden Renderläufe über einen Minutenwechsel laufen würden / Then bleiben die Ergebnisse gleich, weil die Uhr um beide Läufe fest steht; der Test bleibt grün.
  - Test: Uhr so gesetzt, dass ohne Einfrieren ein Minutenwechsel zwischen den Läufen läge (z. B. `tick` über die Minute), vorher rot.
- **AC-5:** Given der SMS-Test des Ortsvergleich-Radar-Alarms (`Zermatt: R@\d{1,2}:\d{2}`) / When er bei 23:55 UTC läuft / Then ist er grün (vorher `R@Mo0:03`-Fehlschlag).
  - Test: Lauf mit gestellter Wanduhr 23:55 UTC, vorher rot.
- **AC-6:** Given die Gestern-Zone-Tests und die gestellte Wanduhr / When die Wanduhr gesetzt ist / Then lesen diese Tests weiterhin die echte Zeit per `date -u` (kein stilles Einfrieren der Prüfaussage, #2096).
  - Test: Mutations-Gegenprobe: Ersetzt man `_echte_utc_jetzt()` durch `datetime.now(timezone.utc)`, wird mindestens ein Test unter gestellter Uhr rot.
- **AC-7:** Given die gesamte betroffene Testmenge / When sie mit `GZ_TEST_WALL_CLOCK_UTC` auf 12:00, 23:40 und 23:58 UTC läuft / Then ist das Ergebnis jeweils grün (Zeitunabhängigkeit, wie #2096 AC-10).
  - Test: drei Läufe derselben benannten Testdateien.

## Known Limitations

- Die Gestern-Zone `<-24>+24` ist eine POSIX-Zone ohne Namen; sie wird nur für den Prozesstag-Test benutzt, nicht für Produktlogik.
- Der Erzeugungszeitstempel im Briefing ist Produktverhalten und bleibt bewusst unverändert (nur der Test friert ein).
- Die Wanduhr-Ratsche (#1940) bleibt unverändert; neue `freeze_time`-Stellen müssen sie nicht umgehen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Testkorrektur im Rahmen der bestehenden Entscheidungen #2096 (Wanduhr-Schalter) und #2314 (Prozesszone).

## Changelog

- 2026-11-06: Initial spec created
