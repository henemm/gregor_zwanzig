---
spec_file: docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md
spec_sha256: 328e4e20c48ef512c52351c8c726c501f267b58d2aa1390b37fe6225e0867c77
---

# PO-Briefing: fix-2422-s2-editor-gleich-gespeichert

- **Spec:** docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md
- **Issue:** #2422
- **Erstellt:** 2026-09-27

## Was gebaut wird

Was im Trip-Editor eingestellt ist, kommt künftig genauso in SMS, Telegram und E-Mail an.

## Definition of Done

Automatisierte Tests bestätigen: Anzeige, Speichern und Auslieferung stimmen überein — für unveränderte Einstellungen und vier Änderungsbeispiele, einmal live geprüft.

## Wie geprüft wird

Geprüft wird der gespeicherte Stand und die berechnete Reihenfolge, nicht die tatsächlich zugestellte SMS, Telegram- oder Garmin-Nachricht.

## Kritische Anmerkungen

- Vier bekannte Fehler aus Teil 1 bleiben weiterhin nur registriert, nicht behoben.
- Die einmalige Reihenfolge-Änderung betrifft nicht nur SMS, sondern ebenso Garmin-Satellitennachrichten und die Telegram-Kurzform.
- Bekannte Lücken bei Alarmen, Versandzeiten und Ortsvergleich bleiben hier unbehoben.

## Freigabe-Frage

Einverstanden, dass vier bekannte Fehler vorerst registriert bleiben und Garmin/Telegram-Kurzform die Reihenfolge-Änderung mitmachen?
