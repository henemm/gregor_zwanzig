---
spec_file: docs/specs/modules/fix_2063_onset_minute_exakt.md
spec_sha256: bb58677567c358f9687a603914f6a70fdcaaefbe1550b01bb1e4c7370d4710af
spec_frozen_sha256: d7ea4e2b6f102ab9d0595d6dd796eb05e8d46a4e097240f2cf2a827cd1eefd5b
---

# PO-Briefing: fix-2063-onset-minute

- **Spec:** docs/specs/modules/fix_2063_onset_minute_exakt.md
- **Issue:** #2063
- **Erstellt:** 2026-11-27

## Was gebaut wird

Radar-Alarme nennen die Uhrzeit exakt wie die Radar-Quelle, nicht mehr in jedem zweiten Lauf eine Minute zu früh.

## Definition of Done

Alarm, Wetter-Abfrage, Briefing und Streckenantwort nennen in allen vier Kanälen dieselbe Frame-Uhrzeit, unabhängig von der Startsekunde; Staging und Produktion bestanden.

## Wie geprüft wird

Automatisierte Tests mit gesteuerter Uhr decken jede Anforderung ab; echte Radar-Quelle und echte Zustellung werden nur im Staging-Lauf geprüft.

## Kritische Anmerkungen

- Umfang über das Ticket hinaus: auch Reichweite, Wetter-Abfrage, Briefing, Streckenantwort; gleiche Ursache, aber acht Dateien betroffen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
