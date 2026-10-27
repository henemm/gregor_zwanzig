---
spec_file: docs/specs/modules/feat_1405_s3_mengenerhalt.md
spec_sha256: 2c27db3afcc8e19cd35907d5af6dd661e1aa6edfdbdc3fc726d8c4a55a943034
spec_frozen_sha256: bcfe9cab1f1ddbc775a0f90a9b1e24e46ef853ae6f473af576e7fcd3ed442127
---

# PO-Briefing: feat-1405-s3-mengenerhalt

- **Spec:** docs/specs/modules/feat_1405_s3_mengenerhalt.md
- **Issue:** #1405
- **Erstellt:** 2026-10-27

## Was gebaut wird

Fehlt eine gewählte Wettergröße im Ortsvergleich, nennen alle vier Kanäle deren Anzahl, statt sie zu verschweigen.

## Definition of Done

Bei fehlender Größe zeigen E-Mail, Telegram, SMS und Premium-SMS einen Hinweis mit Zahl; sonst bleibt alles unverändert.

## Wie geprüft wird

Tests lesen den fertigen Text jedes Kanals samt Zustellung, plus echte Staging-Mail; künftig neu entstehende Verluststellen deckt das nicht ab.

## Kritische Anmerkungen

- Neu: SMS-Zähler "?N" und Mail-Zeile "ohne Wert in diesem Vergleich"; Wortlaute sind Vorschläge, nicht abgesprochen.
- Verhaltensänderung im Trip: Alle Größen abgewählt ergibt keine Spalten statt aller; im Ticket nicht genannt.
- Umfang etwa +250 Zeilen, Limit muss auf 500 steigen.

## Freigabe-Frage

Soll der Ortsvergleich fehlende Größen mit "?N" und Mail-Hinweis melden und der Trip bei "alles abgewählt" keine Spalten zeigen?
