---
spec_file: docs/specs/modules/feat_2799_s7_ampel_weitere.md
spec_sha256: 27dd1cde7d60e13ef630cd4e132dcece61e80f686267a2398c778a333472f34a
spec_frozen_sha256: eb4bd838745e4cf1ce3cf75efe87d8b2b9d7fa300f0d6bdad3a00015abdea46c
---

# PO-Briefing: feat-2799-ampel-weitere

- **Spec:** docs/specs/modules/feat_2799_s7_ampel_weitere.md
- **Issue:** #2799
- **Erstellt:** 2026-11-28

## Was gebaut wird

Weitere Wetterwerte wie Bewölkung, Schneehöhe und Nullgradgrenze werden nach Vorlage farbig bewertet und lösen teils Alarme aus.

## Definition of Done

In E-Mail, Telegram, SMS und Premium-SMS zeigen diese Werte dieselbe Farbe, und Alarme kommen nur bei Stufenwechsel der vorgesehenen Werte.

## Wie geprüft wird

Automatische Tests prüfen Farben und Alarme in allen Kanälen, mit zwei Nutzern und echten Staging-Mails.

## Kritische Anmerkungen

- SMS-Kürzel FZ und SL zeigen künftig den Abstand zur Höhe mit Vorzeichen (FZ+250), nicht mehr die absolute Höhe (von dir entschieden).
- Ohne bekannte Höhe wird die Nullgradgrenze nicht bewertet und alarmiert nicht; es erscheint nur ein Hinweis.
- Die Lieferung erfolgt in zehn Teil-Releases; die alte Alarmlogik der Nullgradgrenze entfällt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
