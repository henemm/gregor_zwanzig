---
spec_file: docs/specs/fast/fix-2502-e2e-675-teardown.md
spec_sha256: 8abd3a914c31f7398252d7b0f1cdb970da1b7d8cb5c5be4e06ca2ed81a21e525
spec_frozen_sha256: fcb22ca3eb3ceb53acf7ec89caaba029ab010d01cb5937890c6c963436f903ca
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

Automatische Tests prüfen Aufräumen und Leeren-Verhalten; die Gegenprobe mit absichtlich rotem Lauf geschieht nur manuell.

## Kritische Anmerkungen

- Zusatz zum Ticket: Ein echter Produktfehler im Uhrzeitfeld (#2947) wird mitrepariert, nicht nur der Test.
- Aufräumen nach rotem Lauf hat keinen automatischen Test, nur manuelle Schritte.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
