---
spec_file: docs/specs/modules/hand_cursor_boden_regel.md
spec_sha256: 69cb3734ed62557582867df8beb7a528f765ea66d15142348b79b10958acbd2d
spec_frozen_sha256: cf19aeab07f7c54138c8f507f5d9775b5d35fc16fc929b161e2d1644ad41f6c5
---

# PO-Briefing: fix-2621-hand-cursor

- **Spec:** docs/specs/modules/hand_cursor_boden_regel.md
- **Issue:** #2621
- **Erstellt:** 2026-11-10

## Was gebaut wird

Aktive Knöpfe zeigen beim Darüberfahren überall die Hand, auch der Bestätigen-Knopf auf der Seite zur E-Mail-Bestätigung.

## Definition of Done

Auf allen sechs Anmeldeseiten und in der App zeigen aktive Knöpfe die Hand, gesperrte nicht, auf Staging nachgewiesen und ausgeliefert.

## Wie geprüft wird

Browser-Tests messen den Mauszeiger auf allen Anmeldeseiten, in der App und bei gesperrten Knöpfen; Klick-Elemente ohne Knopf-Auszeichnung bleiben ungeprüft.

## Kritische Anmerkungen

- Spec wirkt app-weit (alle Knöpfe, Beschriftungen, aufklappbare Bereiche), nicht nur auf Anmeldeseiten wie im Ticket verlangt; Tech-Lead-Entscheidung.
- Neuer Browser-Test kommt nur bei dreimal grün in die CI-Pflichtliste, sonst Folge-Ticket.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
