---
spec_file: docs/specs/modules/fix_3186_trip_pause_alarme.md
spec_sha256: 5306764373431a0c5716b2b4c19193ec6344a4252c46704f9b1b65ebfeb66a22
spec_frozen_sha256: 2ff97edd6832e2b7506560757f7b7a2c4b3aacd4331f8f696e244993f59cbbb5
---

# PO-Briefing: fix-3186-trip-pause-alarme

- **Spec:** docs/specs/modules/fix_3186_trip_pause_alarme.md
- **Issue:** #3186
- **Erstellt:** 2026-11-27

## Was gebaut wird

Ein pausierter Trip schickt keine Alarme mehr: weder Wetterabweichung, amtliche Unwetterwarnung noch Regenradar, auf keinem Kanal.

## Definition of Done

Pausierter Trip löst bei Abweichung, Warnung und Regen auf allen vier Kanälen nichts aus, nicht pausierter alarmiert weiter; Produktion und Selbsttest grün.

## Wie geprüft wird

Automatisierte Läufe mit echten Trips beweisen Schweigen bei Pause und Alarm ohne Pause, je Alarmart und Kanal.

## Kritische Anmerkungen

- Auch die befristete Pause („pause 2d“) schweigt; im Ticket nicht genannt, aber dieselbe Pause wie bei Briefings.
- Nach dem Fortsetzen kommt eine noch aktive Unwetterwarnung einmal; eine während der Pause beendete Warnung bekommt keine Entwarnung.
- Hilfetext des Befehls „pause“ nennt weiter nur Briefings; Korrektur als Nebenbefund.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
