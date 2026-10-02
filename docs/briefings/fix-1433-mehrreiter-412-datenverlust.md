---
spec_file: docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md
spec_sha256: 863a8b631001d0768e5c6a50c7d0e2315ac32ac89a224085fbcf0e737978c5df
---

# PO-Briefing: fix-1433-mehrreiter-412-datenverlust

- **Spec:** docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md
- **Issue:** #1433
- **Erstellt:** 2026-10-01

## Was gebaut wird

Nach einem Speicherkonflikt überschreibt kein anderer Reiter der Trip-Seite mehr still fremde Änderungen.

## Definition of Done

Nach einem Konflikt bleibt „Nochmal speichern“ sichtbar, danach stehen fremde und eigene Änderungen gemeinsam gespeichert; ein per Telegram gesetztes Überspringen bleibt erhalten.

## Wie geprüft wird

Automatische Tests simulieren mehrere Reiter und Fremdschreiber; das echte Telegram-Zusammenspiel prüft erst der Staging-Lauf nach dem Merge.

## Kritische Anmerkungen

- Zusatz: Spec behebt auch das stille Zurückschreiben von „Briefing überspringen“ und ändert den Ortsvergleich mit; das verlangte das Ticket nicht.
- Nach einem Konflikt werden Änderungen anderer Reiter abgelehnt, bis „Nochmal speichern“ gedrückt wird.
- Die Anforderungen zu Doku und „kein Server-Code geändert“ haben keinen automatischen Test.

## Freigabe-Frage

Freigabe, dass Ortsvergleich und „Briefing überspringen“ mit repariert werden?
