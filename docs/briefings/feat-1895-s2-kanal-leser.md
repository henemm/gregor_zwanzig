---
spec_file: docs/specs/modules/alert_metric_channels.md
spec_sha256: 9f7617785d3b77d07b57e71b7781e241fcbca92fcf4b8c81044a5350a57ce14f
---

# PO-Briefing: feat-1895-s2-kanal-leser

- **Spec:** docs/specs/modules/alert_metric_channels.md
- **Issue:** #1895
- **Erstellt:** 2026-09-22

## Was gebaut wird

Alarme nutzen künftig die je Wettergröße hinterlegten Kanäle statt der bisherigen Kanal-Liste an falscher Stelle.

## Definition of Done

Ein Testlauf weist nach: jeder Alarm erreicht die zur ausgelösten Wettergröße hinterlegten Kanäle, alte Einstellungen bleiben erhalten.

## Wie geprüft wird

Automatisierte Tests für Trip und Ortsvergleich plus eine echte Test-Mail-Prüfung; die Editor-Oberfläche wird nicht geprüft.

## Kritische Anmerkungen

- Wer eine Regen-Regel auf Telegram und Wind-Regel auf E-Mail hat: der Regen-Alarm geht heute auf beiden Wegen, künftig nur Telegram.
- Eine im Ticket nicht genannte Datei wird bereinigt (doppelte Übersetzung entfernt); Mails bleiben unverändert, nur ein zusätzlicher Prüfschritt kommt hinzu.
- Der Alarm-Editor zeigt nach dieser Auslieferung noch keine sichtbare Änderung — die Kanalwahl bleibt vorerst unsichtbar.

## Freigabe-Frage

Sollen bestehende Alarmregeln mit unterschiedlichen Kanälen künftig automatisch auf weniger Kanäle verengt werden, ohne dass Nutzer etwas tun?
