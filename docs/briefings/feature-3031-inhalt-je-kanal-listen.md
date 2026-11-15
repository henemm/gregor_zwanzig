---
spec_file: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md
spec_sha256: 80667b4801674b6d061fc2a133b5d1760e0994c9f4c0bae3434e81a5662bcdee
spec_frozen_sha256: d84c2e95ce5ea71f99cec6a03c73fb271653fba498e466613f14e9ebcddab637
---

# PO-Briefing: feature-3031-inhalt-je-kanal-listen

- **Spec:** docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md
- **Issue:** #3031
- **Erstellt:** 2026-11-15

## Was gebaut wird

Im Reiter Wetter legt der Nutzer je Kanal Reihenfolge, An/Aus und Roh/Einfach der Wetterwerte fest, für Trip und Ortsvergleich.

## Definition of Done

Jede Änderung je Kanal erscheint nach Speichern und Neuladen im jeweiligen Bericht, der alte Abschnitt in Zustellung ist weg, Soll/Ist-Bild liegt vor.

## Wie geprüft wird

Automatische Tests prüfen Bedienung, Speichern ohne Datenverlust, zwei Nutzer und Wirkung im Bericht; der Bildvergleich mit dem Mockup bleibt manuell.

## Kritische Anmerkungen

- Der Ortsvergleich wirkt erst, wenn die Vorarbeit #3039 live ist; vorher wird nicht ausgeliefert.
- Premium-SMS ist bis S9 nur Anzeige der SMS-Liste, nicht bearbeitbar.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
