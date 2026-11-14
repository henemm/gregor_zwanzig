---
spec_file: docs/specs/modules/alert_preview_echte_segmente.md
spec_sha256: 11900e58e844ad8e8b1062f788d2b73e52adb8d56faca800d271ffffca2dec38
spec_frozen_sha256: da51594bc3835b070ddce110b90300fc0078d562c93b013e77e6d29fa11f1f78
---

# PO-Briefing: fix-2069-alert-preview-echte-segmente

- **Spec:** docs/specs/modules/alert_preview_echte_segmente.md
- **Issue:** #2069
- **Erstellt:** 2026-11-13

## Was gebaut wird

Die Beispiel-Warnung im Alarme-Reiter zeigt echte Kilometer und Höhenmeter der Etappen und weist erfundene Etappen-Nummern ab.

## Definition of Done

Auf Staging zeigt ein geplanter Trip echte Werte, ein Trip ohne Etappe einen Hinweis, und eine erfundene Etappen-Nummer wird abgelehnt.

## Wie geprüft wird

Automatische Tests ohne Attrappen prüfen Werte, Ablehnung, Nutzertrennung und Texte; die Anzeige im Reiter wird nur per Browsertest geprüft.

## Kritische Anmerkungen

- Abweichung vom Ticket: Geplante Trips behalten die Beispiel-Warnung (Vorschau für nächsten Etappentag), statt wie vorgeschlagen abgelehnt zu werden.
- Zusatz ohne Anfrage: neuer Hinweistext bei Trip ohne Etappe und zwei neue Antwortfelder (Bezugstag, Stundenreihe).

## Freigabe-Frage

Soll die Beispiel-Warnung für geplante, noch nicht laufende Trips erhalten bleiben, statt wie im Ticket vorgeschlagen abgeschaltet zu werden?

## Ampel

Ampel: rot
