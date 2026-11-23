---
spec_file: docs/specs/modules/rework_3264_nowcast_dubletten.md
spec_sha256: a59300b965328fc3e14646900f17a1f751d1621f5b244d0a878281819af97030
spec_frozen_sha256: 328e95e097c06ad661803665a0b1b9614b0f4c906c2d6026f70855b796899013
---

# PO-Briefing: rework-3264-nowcast-dubletten

- **Spec:** docs/specs/modules/rework_3264_nowcast_dubletten.md
- **Issue:** #3264
- **Erstellt:** 2026-11-23

## Was gebaut wird

Doppelte Prüfungen in den Regen- und Radar-Tests werden entfernt, ohne dass sich für Nutzer etwas ändert.

## Definition of Done

Ein doppelter Test und zwei doppelte Prüfzeilen sind weg, alle übrigen Tests der vier Dateien laufen grün, Produktcode bleibt unverändert.

## Wie geprüft wird

Gezielt eingebaute Fehler werden vor und nach dem Aufräumen noch von den verbleibenden Tests erkannt; ein Teil davon nur im Live-Lauf.

## Kritische Anmerkungen

- Das Ticket nennt drei wortgleiche Prüfzeilen, die Spec entfernt nur zwei; die dritte gilt nach dem Ticket-Kriterium als ähnlich und bleibt.
- Der Schutz der entfernten Routing-Zeilen lässt sich nur im Live-Lauf nachweisen, nicht in der Standard-Testschicht.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
