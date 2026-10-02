---
spec_file: docs/specs/modules/fix_2480_radar_alle_messpunkte.md
spec_sha256: b5c12f294ad3adbf7bfb8aa52ca64a7ff443aa5197b877eb995d2fdd2030dad9
---

# PO-Briefing: fix-2480-radar-alle-messpunkte

- **Spec:** docs/specs/modules/fix_2480_radar_alle_messpunkte.md
- **Issue:** #2480
- **Erstellt:** 2026-10-02

## Was gebaut wird

Trip-Regenalarm meldet sich auch, wenn Regen erst 2–10 km weiter vorn beginnt.

## Definition of Done

Regen binnen 55 Minuten weiter vorn löst in allen vier Kanälen Alarm aus; Alarme am eigenen Punkt bleiben unverändert.

## Wie geprüft wird

Testläufe mit nachgestellten Radardaten decken jede Anforderung; echte Radarabrufe und Textverständlichkeit prüfen sie nicht.

## Kritische Anmerkungen

- Springt der maßgebliche Punkt zwischen Läufen, droht Doppelalarm; Gegenmaßnahme fehlt bewusst, wird erst bei rotem Test nachgebaut.
- Uhrzeit ist Regenbeginn ab jetzt, nicht Ankunft; Kriterium „nicht irreführend“ ist Geschmackssache.
- Bei gedrosseltem eigenem Punkt (Abrufbudget) bleibt Alarm aus, selbst wenn vorn Regen liegt.

## Freigabe-Frage

Soll der Trip-Alarm künftig bei Regen weiter vorn auslösen, auch wenn der eigene Messpunkt ausfällt, mit diesen Lücken?
