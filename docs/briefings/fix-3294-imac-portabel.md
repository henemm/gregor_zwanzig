---
spec_file: docs/specs/modules/imac_portabilitaet.md
spec_sha256: 263fb0338ab5703f75f18958d8ad2d0b8b7cfeee7f387b210079adea1ea0968a
spec_frozen_sha256: b55fee441688cd7753555d158845f99efbdab5d8869aa4781b1ef00fdea0c667
---

# PO-Briefing: fix-3294-imac-portabel

- **Spec:** docs/specs/modules/imac_portabilitaet.md
- **Issue:** #3294
- **Erstellt:** 2026-11-23

## Was gebaut wird

Gregor-Sitzungen laufen auf dem iMac ohne Handgriffe: zwei Tests werden plattformunabhängig, der Sitzungsstart prüft Nachrichten notfalls per Fernzugriff.

## Definition of Done

Auf Server und iMac laufen die Tests grün, und der Sitzungsstart endet ohne Server-Verbindung nach höchstens zehn Sekunden still ohne Fehler.

## Wie geprüft wird

Echte Testläufe unter alter und neuer Go-Version sowie reale Hook-Aufrufe; das Ausweichen auf die macOS-Adresse wird nur auf dem Server simuliert.

## Kritische Anmerkungen

- Abweichung vom Issue: Die vorgeschlagene Versionsfestlegung entfällt, weil wirkungslos; stattdessen wird die Ursache behoben. Ziel bleibt erfüllt, keine Produktwirkung.
- Fernzugriff setzt eingerichteten Zugang auf dem iMac voraus; fehlt er, bleibt die Nachrichtenprüfung still aus.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
