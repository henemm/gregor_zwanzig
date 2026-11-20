---
spec_file: docs/specs/modules/feat_3156_renderer_nachzug_roh_einfach.md
spec_sha256: 4540a38f21c2bbcd5df55414aaeee7c0150d33fd88009de0b57a760887a31755
spec_frozen_sha256: b237d64bdd162945711e22dd326fe29feec1e106e144c5daaba7c31d197cffbd
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
- Trip-Telegram ändert sich bei Regenwahrscheinlichkeit ebenfalls, hat aber keinen eigenen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
