---
spec_file: docs/specs/modules/id_eindeutigkeit_trip_vergleich_2359.md
spec_sha256: 5c8d6dc74fee89dbde8092e625d67297b6857a14755bd03f1d1c0d9b98c63eec
spec_frozen_sha256: 18bba7de83141815fb1a8fa56dc135caa0849380099724cc89109a69b26ec1fc
---

# PO-Briefing: fix-2359-etag-schluesselraum

- **Spec:** docs/specs/modules/id_eindeutigkeit_trip_vergleich_2359.md
- **Issue:** #2359
- **Erstellt:** 2026-10-24

## Was gebaut wird

Ein neuer Trip überschreibt keinen gleichnamigen Ortsvergleich mehr still, stattdessen erscheint eine verständliche Fehlermeldung.

## Definition of Done

Trip mit Kennung eines Ortsvergleichs wird abgelehnt, der Ortsvergleich bleibt unverändert, eigene Trips lassen sich weiter aktualisieren.

## Wie geprüft wird

Tests belegen Ablehnung, Nutzertrennung und unveränderte Daten; ob im echten Bestand schon Kollisionen bestehen, belegen sie nicht.

## Kritische Anmerkungen

- Ticketfrage nach Kollisionen im Bestand bleibt offen: Daten nicht lesbar, bereits verlorene Ortsvergleiche blieben unentdeckt.
- Abweichung: Statt den Browser nach Art zu trennen, wird das Datenverlust-Loch am Server geschlossen.
- Rennfall beim Trip-Anlegen ist an der echten Stelle ungetestet; nur der gemeinsame Helfer ist geprüft.

## Freigabe-Frage

Soll der Datenverlust per serverseitiger Ablehnung geschlossen werden, auch wenn der Bestand ungeprüft bleibt?
