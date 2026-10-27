---
spec_file: docs/specs/modules/feat_2439_befehle_antwortzeit.md
spec_sha256: 3d0e36c28b9e7e236b565ea69482b1f17a7df2a535cd0066ca4598a2753802cb
spec_frozen_sha256: 9c344c807dc2c7e33973e2546e0ad10b789f3355e47c33b6170460608b370170
---

# PO-Briefing: feat-2439-befehle-antwortzeit

- **Spec:** docs/specs/modules/feat_2439_befehle_antwortzeit.md
- **Issue:** #2439
- **Erstellt:** 2026-10-18

## Was gebaut wird

HEUTE/MORGEN antworten in unter 60 Sekunden, HELP/CODES/STATUS in unter 30 — auf allen Kanälen.

## Definition of Done

Jeder kalte Staging-Lauf bleibt unter 60 bzw. 30 Sekunden; Prod-Befehle werden per Push sofort übernommen.

## Wie geprüft wird

Kern-Tests belegen Parallelität und unveränderten Inhalt; Live-Läufe messen Staging-Zeiten, Prod-Zeiten werden nicht gemessen.

## Kritische Anmerkungen

- Abweichung: Berichtsumfang bleibt komplett; gewünschtes „nur angefragte Etappe rechnen“ entfällt bewusst, Zeitgewinn nur durch Parallelität.
- Zielzeiten gelten nur für Staging; auf Prod, wo das Problem auftrat, bleibt der Effekt ungemessen.
- HELP hinter laufendem HEUTE darf bis 90 Sekunden dauern, obwohl das Ziel unter 30 liegt.

## Freigabe-Frage

Akzeptieren Sie schnellere Rechenzeit ohne Kürzung des Berichts, nur auf Staging belegt, als Erfüllung von Issue 2439?
