---
spec_file: docs/specs/modules/feat_2800_trip_radar_alarm.md
spec_sha256: 8e05b323805a95a27fbeb5a0d51e6e43f9ff99b4622a9e57e7c4a02de95a51d4
spec_frozen_sha256: 4781f48319d308b3419291d35cd864cfbd814e14fbfa7030f503d67617a21041
---

# PO-Briefing: feat-2800-trip-radar-alarm

- **Spec:** docs/specs/modules/feat_2800_trip_radar_alarm.md
- **Issue:** #2800
- **Erstellt:** 2026-11-19

## Was gebaut wird

Pro Trip lässt sich der Regen-Alarm „Regen in der nächsten Stunde auf deiner Etappe" im Reiter Wetter ein- und ausschalten.

## Definition of Done

Bei eingeschaltetem Schalter kommt auf Staging eine echte Radar-Mail (Validator Exit 0), bei ausgeschaltetem Schalter keine, und Bestandstrips alarmieren weiter.

## Wie geprüft wird

Automatische Tests decken jedes Abnahmekriterium ab, inklusive zwei Nutzern und Staging-Mail; ein Test-Alarm für Radar ist nicht enthalten.

## Kritische Anmerkungen

- Der Alarm läuft für Trips schon heute; neu ist nur der Schalter, Bestandstrips bleiben standardmäßig an (Ortsvergleich: aus).
- Test-Alarm für Radar fehlt bewusst, weil S5 (#2797) noch offen ist; das Issue erlaubt das.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
