---
spec_file: docs/specs/modules/feat_1442_s1_meteoalarm_ch.md
spec_sha256: fefbc43ba6c2916b6a3e49d64f5d649c465b0ffa1ad7d266f6b249505e866164
spec_frozen_sha256: 3e96189b79cb29ca1de7a96ffdd2b563e8f26e9ae5f26735b57f1b8871fe7fd8
---

# PO-Briefing: feat-1442-s1-meteoalarm-ch

- **Spec:** docs/specs/modules/feat_1442_s1_meteoalarm_ch.md
- **Issue:** #1442
- **Erstellt:** 2026-10-29

## Was gebaut wird

Wanderpunkte in der Schweiz bekommen amtliche Unwetterwarnungen (Wind, Gewitter, Hitze, Schnee) über alle vier Kanäle.

## Definition of Done

Auf Staging und Produktion zeigt ein gewarnter Schweizer Punkt die Warnung, Nachbarländer nicht; Selftest Exit 0, dann erst Issue-Close.

## Wie geprüft wird

Tests mit aufgezeichnetem Schweizer Feed und ein Live-Test auf Staging; nicht geprüft wird die Höhenlage der Warnung.

## Kritische Anmerkungen

- Höhenband ignoriert: Warnungen für Hochlagen erscheinen auch im Tal (wie IT/AT/DE).
- Schweizer Randpunkt außerhalb der Lawinenregionen wird nur bei aktiver Warnung erkannt, sonst stille Lücke.
- Ticket-AC „Chip in Compare-Mail per Live-API" nur auf Quellebene belegt; Abrufbudget entfällt.

## Freigabe-Frage

Soll die Schweiz mit diesen Einschränkungen als erstes Land angebunden werden?
