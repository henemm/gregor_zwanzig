---
spec_file: docs/specs/fast/fix-2502-e2e-675-teardown.md
spec_sha256: 9b876413fcc11becdbdbc9c4207d22e43c27e5c7ff1253ee55bac4857abd617a
spec_frozen_sha256: 5858207b1753c49bbd90d46dc64c1dce06b9ab890174b277f458dba82564a550
---

# PO-Briefing: fix-2502-e2e-675-teardown

- **Spec:** docs/specs/fast/fix-2502-e2e-675-teardown.md
- **Issue:** #2502
- **Erstellt:** 2026-11-12

## Was gebaut wird

Der automatische Browser-Test für Etappen-Startzeiten räumt seinen Test-Trip immer wieder weg, auch wenn er fehlschlägt.

## Definition of Done

Nach jedem Testlauf, rot oder grün, existiert der Test-Trip im Konto des Test-Nutzers nicht mehr, und die vier Testfälle laufen grün.

## Wie geprüft wird

Per manuellem Lauf gegen Staging mit Gegenproben (absichtlich roter Test, Aufräumschritt entfernt); es gibt keinen dauerhaft automatischen Nachweis.

## Kritische Anmerkungen

- Das Ticket wollte die zwei kaputten Testfälle aktualisieren; sie wurden stattdessen früher entfernt (#2243). Weniger Testabdeckung, bereits entschieden.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
