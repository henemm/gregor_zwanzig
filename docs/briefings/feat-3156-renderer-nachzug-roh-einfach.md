---
spec_file: docs/specs/modules/feat_3156_renderer_nachzug_roh_einfach.md
spec_sha256: f872276c9042cd3e13195d22740fa9f201ea00499172cb3fb72b33fe83c48050
spec_frozen_sha256: 1aa219a164c273b433711ee18cb4d58d99da4f74f1538122ebfbf7dc4223034b
---

# PO-Briefing: feat-3156-renderer-nachzug-roh-einfach

- **Spec:** docs/specs/modules/feat_3156_renderer_nachzug_roh_einfach.md
- **Issue:** #3156
- **Erstellt:** 2026-11-20

## Was gebaut wird

Die Regenwahrscheinlichkeit zeigt bei „Einfach" in der Trip-Textmail ein Stufenwort und in der Orte-Mailübersicht einen Ampelpunkt.

## Definition of Done

Auf Staging und live zeigen echt zugestellte Trip- und Orte-Mails (HTML und Text) an jeder Umschalter-Stelle beide Formen; das Prüfwerkzeug meldet grün.

## Wie geprüft wird

Tests erzeugen echte Mails in Roh und Einfach und belegen unveränderte SMS und Bestandsabos; nicht geprüft wird die Anzeige im Editor.

## Kritische Anmerkungen

- Gewollte Änderung: Je ein Orte-Bestandsabo (Mail, Telegram) wechselt bei Regenwahrscheinlichkeit von Zahl auf Stufenwort beziehungsweise Ampel.
- Stufenwörter nutzen die bestehende Skala (25/50/75 Prozent), überall dieselben Wörter; die Ampelfarben behalten ihre eigenen Schwellen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
