---
spec_file: docs/specs/modules/fix_2261_a2s1_alarmlauf_reihenfolge.md
spec_sha256: 8d68ed27b46f3bde92ed59f77c2bd4400befde6f413729d3ee29c6bf745ef665
---

# PO-Briefing: fix-2261-a2s1-alarmlauf-reihenfolge

- **Spec:** docs/specs/modules/fix_2261_a2s1_alarmlauf_reihenfolge.md
- **Issue:** #2261
- **Erstellt:** 2026-10-03

## Was gebaut wird

Bei langsamen Alarmprüfungen kommen alle Trips abwechselnd dran, statt dass immer dieselben ausgelassen werden.

## Definition of Done

Ausgelassene Trips stehen im Protokoll, und der nächste Prüflauf beginnt genau mit ihnen.

## Wie geprüft wird

Automatische Tests mit echten Wartezeiten und zwei Nutzern belegen die Reihenfolge; die gespeicherte Merkdatei ist auf Staging nicht prüfbar.

## Kritische Anmerkungen

- Bei schwerer Provider-Störung reicht auch die neue 180-Sekunden-Grenze eventuell nicht; dann wird womöglich kein einziger Trip geschafft.
- Die längere Grenze frisst Zeitbudget: bei Störungen kommen weniger Nutzer pro Lauf dran.
- Die gewünschte Verkürzung der Alarm-Verzögerung liefert diese Scheibe nicht; sie folgt erst in S2 bis S4.

## Freigabe-Frage

Soll die Prüfung fair rotieren und die Zeitgrenze von 90 auf 180 Sekunden steigen, obwohl bei Störungen weniger Nutzer drankommen?
