---
spec_file: docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md
spec_sha256: 7fd25847c40f30ba1a3e29ab194268eb3c808e7a6754cdb56247fd71d853ca80
spec_frozen_sha256: 5811e13c3b7f29beff1703e689e50003d0364c3e3caef2fac9423f323e2e5830
---

# PO-Briefing: refactor-2266-meteoalarm-edr-rueckbau

- **Spec:** docs/specs/modules/refactor_2266_meteoalarm_edr_rueckbau.md
- **Issue:** #2266
- **Erstellt:** 2026-10-27

## Was gebaut wird

Veralteter MeteoAlarm-Abrufweg wird entfernt; amtliche Warnungen für Österreich, Italien und Deutschland kommen unverändert aus dem Feed.

## Definition of Done

Alte Abrufklasse, Budget und Wiederholungslogik sind entfernt, der alte MeteoAlarm-Host steht in keiner Liste mehr, alle Kern-Tests sind grün.

## Wie geprüft wird

Tests vergleichen Feed-Warnungen mit eingefrorenen Aufzeichnungen vom 1. August; sie beweisen keine Gleichheit bei künftigen Warnlagen.

## Kritische Anmerkungen

- Lizenzfrage nicht geklärt: Keine Primärquelle zur 5–10-Minuten-Auflage; 30-Minuten-Zwischenspeicher bleibt, nur als Annahme „reicht“ dokumentiert.
- Umfang größer als Ticket: zusätzlich Wiederholungslogik und Budget-Statusanzeige entfernt; Monitoring-Skript muss fehlenden Block vertragen.
- Aufzeichnungsskript existierte nie; wird nur als nicht vorhanden dokumentiert, Fixtures bleiben.

## Freigabe-Frage

Soll der Rückbau so umgesetzt werden, bei unverändertem 30-Minuten-Zwischenspeicher und offen dokumentierter Lizenzfrage?
