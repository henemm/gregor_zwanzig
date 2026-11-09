---
spec_file: docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md
spec_sha256: 5c3ae89068e8cb42388ae11e5784a356ab86dd67da9df213971aed081260e9cb
spec_frozen_sha256: 0ca6226db8b572ef0e30ec3ba5515f95b58886f5a4ed9d05aafa8b17a29675b5
---

# PO-Briefing: deliver-2860-alarm-ab-migration

- **Spec:** docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md
- **Issue:** #2860
- **Erstellt:** 2026-11-08

## Was gebaut wird

Alarme folgen künftig der Ampel-Farbe statt der alten Empfindlichkeitsstufen; vorhandene Einstellungen werden vorher auf Staging und Produktion übernommen.

## Definition of Done

Migration meldet auf Staging und Produktion „Nichts zu tun“, Alarme laufen danach produktiv nach Ampel, Prüfung in Deutsch und Englisch bestanden.

## Wie geprüft wird

Tests belegen alle 20 Kriterien, echte Staging-Alarme in vier Kanälen und beiden Sprachen, Migration per Probelauf und Kontroll-Lauf; Alarm-Mails ohne eigenen Validator.

## Kritische Anmerkungen

- Bis zur Folgearbeit S3a kann niemand „Alarm ab“ ändern; die alte Tabelle ist nur lesbar.
- Die Übernahme der Altstufen ist eine Annäherung: „sensibel“ bedeutet eine Stufe empfindlicher, nicht dasselbe Verhalten.
- Alarm-Mails haben keinen automatischen Validator; Nachweis nur über echt zugestellte Staging-Mails.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
