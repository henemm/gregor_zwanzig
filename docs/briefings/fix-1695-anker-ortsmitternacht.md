---
spec_file: docs/specs/modules/fix_1695_anker_ortsmitternacht.md
spec_sha256: aa40e09608a21ead8a3120c33eb2d96a2b43ea5f3df1652df3153dac81ee23cb
spec_frozen_sha256: c362afd62b7499f6f8e51bae3ac6835067e489a2927083afd1a32f3378ae8518
---

# PO-Briefing: fix-1695-anker-ortsmitternacht

- **Spec:** docs/specs/modules/fix_1695_anker_ortsmitternacht.md
- **Issue:** #1695
- **Erstellt:** 2026-11-05

## Was gebaut wird

Ortsvergleich-Änderungsalarme melden keine Scheinänderung mehr, wenn Mitternacht mitten im Speichern der Referenzwerte liegt.

## Definition of Done

Alle Referenzwerte eines Vergleichs tragen nach dem Versand denselben Kalendertag, auch wenn zwischen zwei Orten Mitternacht verstreicht.

## Wie geprüft wird

Automatische Tests simulieren den Mitternachtssprung zwischen zwei Orten und prüfen gleiche Tage; echte Zustellung auf den vier Kanälen wird nicht getestet.

## Kritische Anmerkungen

- Bekannte Restlücke: Mitternacht zwischen Fälligkeitsprüfung und Speichern kann den ganzen Satz einheitlich um einen Tag verschieben; bewusst nicht gelöst.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
