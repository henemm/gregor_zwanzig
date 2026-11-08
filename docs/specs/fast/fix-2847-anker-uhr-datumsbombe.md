---
issue: 2847
created: 2026-11-08
status: draft
---
# Mini-Spec: fix-2847-anker-uhr-datumsbombe

## Was ändert sich
- In `tests/tdd/test_compare_anker_ortsmitternacht.py` stellen AC-5, AC-6 und AC-8 beide Uhren
  (`uhr_quelle`, `uhr_dispatch`) fest auf einen Moment innerhalb der Testdaten (`TAG` = 5.11.2026,
  Mittag Ortszeit), wie es AC-1 bereits tut.
- Damit rechnen die drei Tests nicht mehr mit der echten Uhr; ab dem 8.11.2026 liegt „jetzt"
  außerhalb der Wetter-Testdaten (4.–7.11.) und die Tests waren dauerhaft rot.

## Was darf sich nicht ändern
- Kein Produktivcode (`src/`, `api/`, `internal/`).
- Die Zusicherungen von AC-5 (fail-soft je Ort), AC-6 (Nutzer-Isolation, kein `default`) und
  AC-8 (dasselbe `now` an alle Orte, kein `None`) bleiben unverändert.
- Übrige Tests der Datei (AC-1 bis AC-4) unverändert.

## Acceptance Criteria
**AC-1:** Given die echte Uhr steht nach dem 7.11.2026, When die Testdatei läuft, Then sind AC-5, AC-6 und AC-8 grün, weil beide Uhren fest auf den Testtag gestellt sind.
**AC-2:** Given die Implementierung wird verfälscht (z. B. AC-8: `now` nicht durchgereicht, AC-6: Anker unter `default`), When die Testdatei läuft, Then wird der betroffene Test weiterhin rot — die Uhr-Feststellung entschärft keine Zusicherung.

## Manuelle Test-Schritte
1. `uv run pytest tests/tdd/test_compare_anker_ortsmitternacht.py -q` → alle grün (heute, 8.11.).
2. CI-Job `test` auf dem PR grün.

## Inline-Test
- [ ] Die drei bestehenden Tests sind selbst der Nachweis (vorher rot am 8.11., nachher grün).
