---
spec_file: docs/specs/modules/fix_3217_flaky_thunder_ac3.md
spec_sha256: 61da5ba968b8321743be394b1d7d4956e7dd2d6be0449f244a819303b585887c
spec_frozen_sha256: 04d5b0bd538bede6c84485af7874a118b5adb3424c2d51d201bef7fe45769b45
---

# PO-Briefing: fix-3217-flaky-thunder-ac3

- **Spec:** docs/specs/modules/fix_3217_flaky_thunder_ac3.md
- **Issue:** #3217
- **Erstellt:** 2026-11-21

## Was gebaut wird

Ein zufällig fehlschlagender Automatiktest zum Gewitter-Abruf wird stabilisiert, damit die Prüfung vor dem Ausliefern nicht grundlos rot wird.

## Definition of Done

Der Test besteht auch bei künstlich verlangsamtem Server mehrfach hintereinander, der alte Test scheitert dort nachweislich, und die Produktivfunktion bleibt unverändert.

## Wie geprüft wird

Nachgestellte Verzögerung zeigt alt rot, neu grün; drei gezielte Verfälschungen machen den Test rot; echte CPU-Last auf dem Server wird nicht erzeugt.

## Kritische Anmerkungen

- Der zweite Ausfall (PR #3211, Abbruch ohne roten Test) bleibt ungelöst; bei Wiederkehr entsteht ein eigenes Ticket.
- Statt fester Uhr werden Timeout und Wartezeiten vergrößert; das Ticket nannte die Uhr nur als Beispiel.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
