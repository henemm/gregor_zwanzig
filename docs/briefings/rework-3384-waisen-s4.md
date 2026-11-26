---
spec_file: docs/specs/modules/rework_3384_waisen_s4.md
spec_sha256: fd74a88651988805a7dbab3dee7bc235cb2c65904fa9264c6ff564107166ea85
spec_frozen_sha256: 70e3e2b4a5755b4382e2a34f1c733bb88581c3106e302921703dcb3af7649db5
---

# PO-Briefing: rework-3384-waisen-s4

- **Spec:** docs/specs/modules/rework_3384_waisen_s4.md
- **Issue:** #3384
- **Erstellt:** 2026-11-26

## Was gebaut wird

Ungenutzter Alt-Code der Oberfläche wird entfernt und der automatische Aufräum-Wächter verschärft; für Nutzer ändert sich nichts.

## Definition of Done

Die ungenutzten Dateien samt ihrer Tests sind gelöscht, alle Prüfungen laufen grün, und die Seiten sehen unverändert aus.

## Wie geprüft wird

Der Wächter, die Testsuite, der Build und ein Seitenvergleich belegen die unveränderte Oberfläche; echte Bildschirmansichten prüft kein Mensch.

## Kritische Anmerkungen

- Abweichung: 19 statt der im Ticket genannten 18 Dateien; die Wächterliste ist maßgeblich und die Spec begründet es.
- Zusatz: Ein Browser-Test samt Konfiguration wird mitgelöscht, weil er nur eine gelöschte Datei prüft; CI-Mindestzahlen sinken.
- Die drei Nachbesserungen F001, F002 und F004 aus dem Kommentar sind enthalten und je getestet.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
