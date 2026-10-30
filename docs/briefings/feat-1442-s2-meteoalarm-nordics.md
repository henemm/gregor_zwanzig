---
spec_file: docs/specs/modules/feat_1442_s2_meteoalarm_nordics.md
spec_sha256: 70f82557fbb8d15b7ad8f0fc89b84d4fdb8d56bd0879b960bd297fd6117a9ca9
spec_frozen_sha256: 37a0b5e57d5c8435fa68b8c91364a70802c36c6661cadd4940522a3d47efcdc5
---

# PO-Briefing: feat-1442-s2-meteoalarm-nordics

- **Spec:** docs/specs/modules/feat_1442_s2_meteoalarm_nordics.md
- **Issue:** #1442
- **Erstellt:** 2026-10-29

## Was gebaut wird

Wanderpunkte in Norwegen, Schweden und möglichst Finnland erhalten amtliche Unwetterwarnungen.

## Definition of Done

Warnungen für Norwegen und Schweden erscheinen in Trip und Ortsvergleich; Finnland ist erledigt oder ausdrücklich als offen gemeldet.

## Wie geprüft wird

Tests mit aufgezeichneten Feeds prüfen Treffer, Ausfall und Alarmwege; der echte Feed wird nur auf Staging geprüft.

## Kritische Anmerkungen

- Finnland kann offen bleiben (AC-12): Gebietsdaten fehlen noch, finnische Trip-Punkte bekämen dann weiter keine Warnungen.
- Abweichung: 24-Stunden-Abrufbudget aus dem Ticket entfällt, da der Feed kontingentfrei ist.
- Live-Test überspringt ohne aktuelle Warnung; Umbau des Schweiz-Wegs birgt Regressionsrisiko.

## Freigabe-Frage

Darf Finnland in diesem Schritt offen bleiben, wenn Norwegen und Schweden fertig sind?

## Ampel

Ampel: rot
