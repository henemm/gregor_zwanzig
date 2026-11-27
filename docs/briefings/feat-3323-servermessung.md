---
spec_file: docs/specs/modules/testsuite_servermessung_parallel.md
spec_sha256: 02e13f47e3f07d03f51ef8b059e21603277b69b4a3c80bf9cdeb48bc95872651
spec_frozen_sha256: f3c0606324fdc73c62d33f55c0021b6b3b17266ee2b9488c1d2c54e3bd641b5e
---

# PO-Briefing: feat-3323-servermessung

- **Spec:** docs/specs/modules/testsuite_servermessung_parallel.md
- **Issue:** #3323
- **Erstellt:** 2026-11-27

## Was gebaut wird

Auf dem Server wird gemessen, ob der parallele Testlauf wirklich schneller ist, ohne mehr Fehler oder Störung des Livebetriebs.

## Definition of Done

Ein Messprotokoll belegt: paralleler Lauf schneller als serieller, keine zusätzlichen roten Tests, Speicher und Prozessorlast gemessen, Prod-Selbsttest während des Laufs grün.

## Wie geprüft wird

Kein Code-Test; das Messprotokoll mit Zahlen beider Läufe ist der Nachweis, nur ein optionaler Dokumentations-Test prüft sein Vorhandensein.

## Kritische Anmerkungen

- Serverzugang wurde am 24.11. abgelehnt; die Messung hängt davon ab, dass er diesmal erlaubt wird.
- Jede zusätzliche rote Prüfung, auch ein einzelner Wackler, gilt als gescheitert; Einzelmessung, keine Wiederholung.
- Zusatz gegenüber dem Ticket: Sicherheitsabbruch bei unter 1 GB freiem Speicher, damit Prod nicht gefährdet wird.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
