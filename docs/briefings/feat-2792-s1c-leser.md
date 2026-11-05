---
spec_file: docs/specs/modules/feat_2792_s1_profil_ampel.md
spec_sha256: 291dafc5ca7d2b16899a012efbd9215d8e620c82980059282be6a0ca56ab13a9
spec_frozen_sha256: 6b16f7b15eace08bf157d4090b0ff131f0464c4820991f5f44d35708da69de98
---

# PO-Briefing: feat-2792-s1c-leser

- **Spec:** docs/specs/modules/feat_2792_s1_profil_ampel.md
- **Issue:** #2792
- **Erstellt:** 2026-11-04

## Was gebaut wird

Mail, Telegram, SMS und Premium-SMS färben und markieren Werte einheitlich nach der Profil-Ampel des jeweiligen Trips oder Ortsvergleichs.

## Definition of Done

Derselbe Wert ist je nach Vorlage unterschiedlich gefärbt, in allen vier Kanälen gleich; alte Wertebereiche sind nur lesbar, ihre Werte migriert.

## Wie geprüft wird

Automatische Tests prüfen Farben, Hervorhebung, Migration und Sperre; die Mail-Prüfprogramme kontrollieren keine Farben.

## Kritische Anmerkungen

- Wertebereich-Markierung entfällt komplett; Gewitter- und CAPE-Wertebereiche werden nicht migriert, ihre Markierung geht verloren.
- Auch Vorlage "Allgemein" ändert sich sichtbar: CAPE ohne Farbe, Temperatur im Ausblick gefärbt, einheitliche Gewitterfarbe.
- SMS und Telegram zeigen Spitzenwerte erst ab Gelb (bewusst, Entscheidung E1).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
