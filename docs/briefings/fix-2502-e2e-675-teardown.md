---
spec_file: docs/specs/fast/fix-2502-e2e-675-teardown.md
spec_sha256: 1ffddaf01e6af1b2ad3f150cb6d56033182ffcc94532badfc39e15486e41c1f2
spec_frozen_sha256: f7fc438700de5070068da160fe7fa07641a0395882b1ea1f7617f5ee529d6dcb
---

# PO-Briefing: fix-2502-e2e-675-teardown

- **Spec:** docs/specs/fast/fix-2502-e2e-675-teardown.md
- **Issue:** #2502
- **Erstellt:** 2026-11-12

## Was gebaut wird

Der Testlauf räumt seinen Test-Trip immer ab, und eine geleerte Startzeit fällt wieder auf 08:00 zurück.

## Definition of Done

Nach grünem wie rotem Testlauf auf Staging ist der Test-Trip weg, und das Leeren von 15:00 ergibt 08:00 statt 01:00.

## Wie geprüft wird

Ein Komponententest und der Staging-Lauf prüfen Leeren und Aufräumen; der Aufräum-Nachweis nach rotem Lauf erfolgt nur manuell.

## Kritische Anmerkungen

- Zusatz zum Ticket: Ein echter Produktfehler im Uhrzeitfeld (#2947) wird mitrepariert, nicht nur der Test.
- Aufräumen nach rotem Lauf hat keinen automatischen Test, nur manuelle Schritte.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
