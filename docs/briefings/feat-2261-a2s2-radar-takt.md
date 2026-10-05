---
spec_file: docs/specs/modules/feat_2261_a2s2_radar_takt.md
spec_sha256: 15c943f94b8446cceac9c6bd3b2057cf4b26b95c9f7d51a1f0ba15ac5d67bd5b
---

# PO-Briefing: feat-2261-a2s2-radar-takt

- **Spec:** docs/specs/modules/feat_2261_a2s2_radar_takt.md
- **Issue:** #2261
- **Erstellt:** 2026-10-05

## Was gebaut wird

Regen-Alarme werden alle 5 statt 15 Minuten geprüft, sodass Regenbeginn rund 15 statt 32 Minuten später gemeldet wird.

## Definition of Done

Beide Radar-Prüfläufe laufen auf Produktion im 5-Minuten-Abstand ohne Überlappung, und das Monitoring prüft sie gegen 12 Minuten.

## Wie geprüft wird

Tests belegen Takt, Zeitbudgets, faire Reihenfolge und höchstens eine Meldung bei drei Läufen; die tatsächliche Meldeverzögerung wird nicht gemessen.

## Kritische Anmerkungen

- Die 15-Minuten-Zusage ist nur gerechnet, nicht gemessen; Quellen mit 15-Minuten-Rhythmus liegen darüber.
- Ausfall-Störmeldungen kommen dreimal früher (nach 15 statt 45 Minuten); Fehlalarme möglich.
- Dreifache Prüfhäufigkeit belastet das Open-Meteo-Tageskontingent; Auswirkung nicht gemessen.

## Freigabe-Frage

Gibst du den 5-Minuten-Takt samt früheren Störmeldungen frei, obwohl die 15-Minuten-Zusage nur gerechnet ist?
