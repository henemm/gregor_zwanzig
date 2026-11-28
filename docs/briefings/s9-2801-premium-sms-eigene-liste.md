---
spec_file: docs/specs/modules/feat_2801_alarm_schwelle_vorbelegung_je_kanal.md
spec_sha256: b72063675a11c2ffd272cbefd34537506dde87e1103f5c579a3541b9546ed285
spec_frozen_sha256: 96f6b654c07d22645121ad83624bb2245e366adf56ff07c52479cd76324e69fd
---

# PO-Briefing: s9-2801-premium-sms-eigene-liste

- **Spec:** docs/specs/modules/feat_2801_alarm_schwelle_vorbelegung_je_kanal.md
- **Issue:** #2801
- **Erstellt:** 2026-11-28

## Was gebaut wird

Ohne eigene Wahl melden E-Mail und Telegram ab gering, SMS ab mittel, Premium-SMS nur bei hoch; Premium-Text gleich SMS.

## Definition of Done

Alarm „mittel“ erreicht ohne gesetzte Stufe E-Mail, Telegram und SMS, nicht Premium-SMS; „hoch“ erreicht alle vier, auf Staging nachgewiesen.

## Wie geprüft wird

Automatische Tests prüfen Alarm-Verteilung, gesetzte Werte, zwei Nutzer und Texte; echter SMS-Empfang wird nur auf Staging geprüft.

## Kritische Anmerkungen

- Bestandsnutzer ohne gesetzte Stufe bekommen sofort weniger SMS- und Premium-Alarme; amtliche Warnungen „gering“ fehlen zudem im SMS-Briefing.
- Statt der im Ticket verlangten eigenen Premium-Auswahl gilt der SMS-Inhalt; von Ihnen am 28.11. so entschieden.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
