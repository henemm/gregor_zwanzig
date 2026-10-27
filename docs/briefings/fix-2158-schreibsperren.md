---
spec_file: docs/specs/bugfix/fix_2158_schreibsperren.md
spec_sha256: 9d835cb27a15fd5f27ca640225b98947858ba8d209f9c43b770835335ef86972
---

# PO-Briefing: fix-2158-schreibsperren

- **Spec:** docs/specs/bugfix/fix_2158_schreibsperren.md
- **Issue:** #2158
- **Erstellt:** 2026-10-05

## Was gebaut wird

Gleichzeitige Änderungen an Trips, Orten, Gruppen und Vorlagen überschreiben sich nicht mehr, alle bleiben erhalten.

## Definition of Done

Parallele Änderungen aus Browser, Telegram und Briefing-Lauf gehen nie verloren; bei Überlastung erscheint eine Fehlermeldung.

## Wie geprüft wird

Tests mit echten parallelen Schreibern belegen jede Anforderung; der echte Server mit Nutzerdaten wird nicht geprüft.

## Kritische Anmerkungen

- Größtes Risiko: Umbau der Trip-Befehle und Etappen-Ankunftszeiten; Fehler träfe laufende Trips, Staging-Nachweis fehlt.
- Bei Sperr-Wartezeit über 5 Sekunden wird der Trip im Briefing-Lauf übersprungen und kommt erst im nächsten Lauf.
- Zusatz: neue Grundsatzentscheidung löst die alte ab; Ticket-Test "zwei Orte parallel" ersetzt, da schon grün.

## Freigabe-Frage

Geben Sie die Spec frei, obwohl sie größer ausfällt als üblich und die bisherige Grundsatzentscheidung zu Schreibrechten ersetzt wird?
