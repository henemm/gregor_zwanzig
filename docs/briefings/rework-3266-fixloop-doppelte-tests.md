---
spec_file: docs/specs/modules/rework_3266_fixloop_dubletten.md
spec_sha256: 12b51fc899c11d0a4caf029f790e72fe7b813e99ed8afd530629fa6cbcaff580
spec_frozen_sha256: ab44aeab667c6dae516301b212230512b486b0159edbe29ddc16e4750529fe28
---

# PO-Briefing: rework-3266-fixloop-doppelte-tests

- **Spec:** docs/specs/modules/rework_3266_fixloop_dubletten.md
- **Issue:** #3266
- **Erstellt:** 2026-11-23

## Was gebaut wird

Zwei doppelte Prüfzeilen in der Testsammlung werden entfernt; für Nutzer ändert sich nichts.

## Definition of Done

Zwei Zeilen sind entfernt, alle 14 betroffenen Testdateien laufen grün, und absichtlich eingebaute Fehler werden danach weiterhin von den Tests erkannt.

## Wie geprüft wird

Gezielt eingebaute Fehler im Programm werden vor und nach dem Umbau von den Tests gefangen; das Produktverhalten bleibt unberührt.

## Kritische Anmerkungen

- Ticket nennt 11 Dateien, die Spec prüft 14; der Ertrag ist winzig (eine Teilmenge), ein Schutzverlust ist nicht zu erwarten.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
