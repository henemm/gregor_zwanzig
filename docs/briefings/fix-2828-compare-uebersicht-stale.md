---
spec_file: docs/specs/bugfix/bug_2828_compare_uebersicht_stale.md
spec_sha256: dd43567970d853fd6a0cd47bb62f996c8f1da1a9921c41ae27cab81f1efa14df
spec_frozen_sha256: 0c4c05b8a08b7c9378eeefb0166399a76020eb9f56e9ceaefa3e222c84ed366c
---

# PO-Briefing: fix-2828-compare-uebersicht-stale

- **Spec:** docs/specs/bugfix/bug_2828_compare_uebersicht_stale.md
- **Issue:** #2828
- **Erstellt:** 2026-11-06

## Was gebaut wird

Die Übersicht im Ortsvergleich zeigt nach dem Speichern in einem Reiter sofort den neuen Stand, ohne Neuladen.

## Definition of Done

Nach Speichern von Orten oder Versand zeigt die Übersicht ohne Neuladen die neuen Werte; Pausieren ändert den Status sofort, Trip-Übersicht bleibt unverändert.

## Wie geprüft wird

Browser-Tests ändern, speichern und lesen die Übersicht; Wertebereiche und der Konfliktfall sind nur über Quelltext-Verdrahtung bzw. Review belegt, nicht im Verhalten.

## Kritische Anmerkungen

- AC-1 wurde abgeschwächt (Wertebereiche gesperrt durch #2792); Nachweis nur Quelltext-Prüfung, kein Verhaltenstest.
- Testplan verlangt noch Werteänderung im Wertebereiche-Reiter, obwohl gesperrt; Plan widerspricht AC-1.
- AC-4 „in sich stimmig" ist vage; AC-7 (Konflikt) evtl. ohne automatischen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
