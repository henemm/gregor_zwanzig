---
spec_file: docs/specs/modules/fix_2946_sichtweite_einheit.md
spec_sha256: 1609991ab2f4a595ca129d9bf694e35f080257891130eb3f8f5563b818afb94d
spec_frozen_sha256: 215f02672447b7d01d11c5f16f4283a5ea8cdef06fac1bf962abff2c2148c796
---

# PO-Briefing: fix-2946-sichtweite-einheit

- **Spec:** docs/specs/modules/fix_2946_sichtweite_einheit.md
- **Issue:** #2946
- **Erstellt:** 2026-11-15

## Was gebaut wird

Sichtweite im Wetter-Reiter zeigt Grenzwerte in Metern statt fälschlich Kilometern, für Trip und Orts-Briefing, Deutsch wie Englisch.

## Definition of Done

Auf Staging und Produktion zeigt die Sichtweite-Zeile "m" (z. B. "ab 1000 m"), der Layout-Reiter weiter "km", alle Prüfungen und Selftest grün.

## Wie geprüft wird

Automatische Tests prüfen Texte und Schnittstelle, ein Staging-Test die Anzeige in beiden Sprachen; das genaue Aussehen der Leiste wird nicht gesondert getestet.

## Kritische Anmerkungen

- Anfrage nennt auch die Leistenbeschriftung; laut Spec zeigt die Leiste nur Zahlen, bleibt unverändert und hat keinen eigenen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
