---
spec_file: docs/specs/modules/fix_2275_compare_premium_sms_versand.md
spec_sha256: 73d72a2c6ecd33643c8401ac3f374500dedb3f3ee514d31a8cd63d86b4e505e8
---

# PO-Briefing: fix-2275-compare-premium-sms

- **Spec:** docs/specs/modules/fix_2275_compare_premium_sms_versand.md
- **Issue:** #2275
- **Erstellt:** 2026-09-26

## Was gebaut wird

Der Premium-SMS-Schalter im Ortsvergleich sendet die Kurz-SMS tatsächlich; Fehlschläge werden sichtbar gebucht.

## Definition of Done

Test-Vergleich auf Staging kommt als Kurz-SMS am Empfangsgerät an, Tageslimit-Zähler steigt um eins.

## Wie geprüft wird

Tests mit simuliertem Versand prüfen Erfolg, Fehler, Sperren, Nutzertrennung; echte Zustellung am Gerät belegt nur der Live-Test.

## Kritische Anmerkungen

- Gemeinsame Kanal-Schleife aus dem Issue entfällt bewusst; danach existieren vier Kopien des Premium-SMS-Codes.
- Gescheiterte Premium-SMS bricht nichts ab und erscheint nur im Log, nicht in der Oberfläche; kein Nachversand.
- Live-Nachweis am Gerät ist kein Akzeptanzkriterium, nur Testplan-Punkt.

## Freigabe-Frage

Ist es für dich in Ordnung, dass der Kanal nur nachgezogen wird und Fehlschläge ohne Nachversand nur im Log stehen?
