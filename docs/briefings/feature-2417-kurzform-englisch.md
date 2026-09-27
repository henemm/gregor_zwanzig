---
spec_file: docs/specs/modules/feat_2417_kurzform_englisch.md
spec_sha256: 3e5e114f168da2015bc83b2f4df4b2de372e26f357d0d14ae778087a53a98257
---

# PO-Briefing: feature-2417-kurzform-englisch

- **Spec:** docs/specs/modules/feat_2417_kurzform_englisch.md
- **Issue:** #2417
- **Erstellt:** 2026-09-27

## Was gebaut wird

SMS/Telegram-Kurzform antworten englisch mit verständlichen Befehlserklärungen; ein neuer Befehl listet alle Kürzel-Bedeutungen.

## Definition of Done

Fertig ist, wenn HELP und CODES auf Kurzform-Kanälen den freigegebenen Wortlaut liefern und alle Befehle deutsch wie englisch funktionieren.

## Wie geprüft wird

Tests prüfen Wortlaut, Sprache je Kanal, Kürzel-Eindeutigkeit; ob HELP per echter Premium-SMS ankommt, zeigt erst Ihr Handytest danach.

## Kritische Anmerkungen

- Fünf Warn-Kürzel ändern sich (Gewitter, Hochwasser, Starkregen, Sturmböen, Sperrung); die Analyse hatte das noch ausgeschlossen.
- Warn- und Format-Kürzel liegen in zwei weiteren Dateien, nicht der Metrik-Tabelle; passt das zu „ein zentraler Ort"?
- Temperatur-Kürzel wechselt von D auf T, auch in Alarm- und Ortsvergleich-SMS; wer D sendet, bekommt künftig den Tageshöchstwert.

## Freigabe-Frage

Sollen die neuen Warn-Kürzel und die verteilte Kürzel-Dokumentation so freigegeben werden?
