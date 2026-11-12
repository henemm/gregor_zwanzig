---
spec_file: docs/specs/modules/fix_2503_red_tests_gate.md
spec_sha256: aa79c30b016b88363591f79ab71972c3388321b361582ae61eeceb8d8ff8365d
spec_frozen_sha256: 7afdae325dada28b0fedc4906290e42132c85752c894bcc9d5028827a799fe1b
---

# PO-Briefing: fix-2503-red-tests-gate

- **Spec:** docs/specs/modules/fix_2503_red_tests_gate.md
- **Issue:** #2503
- **Erstellt:** 2026-11-12

## Was gebaut wird

Die Commit-Prüfung lässt neu geschriebene, absichtlich fehlschlagende Tests in der Rot-Phase durch, statt sie zu blockieren.

## Definition of Done

Ein neuer roter Test lässt sich in der Rot-Phase festhalten; in jeder anderen Phase und bei zuvor grünen Tests bleibt der Commit blockiert.

## Wie geprüft wird

Automatische Tests mit echten Probe-Projekten belegen alle acht Kriterien; die Umgehung durch Umbenennen eines Tests wird nur im Prüfdurchlauf untersucht.

## Kritische Anmerkungen

- Ein umbenannter und rot gemachter Test gilt als neu; Umgehung bleibt möglich, ist aber auf die Rot-Phase begrenzt und wird gemeldet.
- Zusatz zum Ticket: Auch Python- und Frontend-Tests werden einbezogen, nicht nur Go.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
