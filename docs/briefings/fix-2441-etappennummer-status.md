---
spec_file: docs/specs/modules/fix_2441_etappennummer_status.md
spec_sha256: 4396fb39bbf8a12584a351db081c8d47cffb4d912b929f0b0d8211a9b77d5387
---

# PO-Briefing: fix-2441-etappennummer-status

- **Spec:** docs/specs/modules/fix_2441_etappennummer_status.md
- **Issue:** #2441
- **Erstellt:** 2026-10-07

## Was gebaut wird

`status` und die Bestätigung einer STARTDATUM-Verschiebung nennen jede Etappe mit der gezählten Nummer, etwa „Etappe 4: Obstansersee-Hütte nach Porzehütte“, wie `heute`. Eine im Namen mit Doppelpunkt oder Strich vergebene Zahl („02: X“) wird ersetzt. Gespeicherte Namen bleiben unverändert.

## Definition of Done

`status` und `heute` nennen auf allen vier Kanälen dieselbe Nummer. Bestehende Ausgaben bleiben grün.

## Wie geprüft wird

Neue Tests über den echten Befehlseingang aller vier Kanäle, plus Gegenprobe mit Rohnamen.

## Kritische Anmerkungen

- Die gezählte Nummer wird ohne Rückfrage festgelegt.
- Ein mit Punkt geschriebenes Autorpräfix („2. X“) erscheint weiter doppelt, bewusst nicht erkannt.
- Die STARTDATUM-Verschiebung ist Spec-Ergänzung, nicht im Ticket.

## Freigabe-Frage

Soll die Namenszahl mit Doppelpunkt oder Strich durch die gezählte Nummer ersetzt werden?
