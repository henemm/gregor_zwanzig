---
spec_file: docs/specs/modules/fix_1430_meteoalarm_lawine.md
spec_sha256: 99d2ff3ed1f8898aa7c81080096b00484e739f3645aa7dc6a34f864f0336dd0b
---

# PO-Briefing: fix-1430-lawinenwarnung-meteoalarm-typ9

- **Spec:** docs/specs/modules/fix_1430_meteoalarm_lawine.md
- **Issue:** #1430
- **Erstellt:** 2026-10-12

## Was gebaut wird

Amtliche Lawinenwarnungen erscheinen in Trip-Berichten und Ortsvergleichen, statt stillschweigend verworfen zu werden.

## Definition of Done

Eine orange Lawinenwarnung erscheint als „Lawine“ in E-Mail, Telegram, SMS (Kürzel AW) und Premium-SMS.

## Wie geprüft wird

Tests mit aufgezeichneter Warnung belegen die Ankunft in allen vier Kanälen; echter Versand an Garmin oder Postfach wird nicht geprüft.

## Kritische Anmerkungen

- Gelbe Lawinenwarnungen erscheinen weiterhin nicht in SMS und Telegram (bestehender Orange-Filter).
- Kürzel AW unterscheidet sich nur um einen Buchstaben von AV (Lawinenstufe); Verwechslungsgefahr.
- Nebel und Küste bleiben für Nutzer unsichtbar (nur Debug-Log); Feed-Test nutzt abgeleitete Daten.

## Freigabe-Frage

Soll Lawine als eigene Gefahrenart mit Kürzel AW eingeführt werden, während Nebel und Küste bewusst unsichtbar bleiben?
