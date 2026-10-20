---
spec_file: docs/specs/modules/feat_2280_handversand_endpoint.md
spec_sha256: 7cfc265237e8075074630fd210f6d30124ee3067f7c973dba492664aedf6b0e3
spec_frozen_sha256: 84fc0c74130f9d70be0272ac37c283482f808bf3e94e32a9865b97274aa07f6f
---

# PO-Briefing: feat-2280-handversand-endpoint

- **Spec:** docs/specs/modules/feat_2280_handversand_endpoint.md
- **Issue:** #2280
- **Erstellt:** 2026-10-20

## Was gebaut wird

Ein Ortsvergleich meldet beim Senden ehrlich, warum nichts zugestellt wurde, genau wie ein Trip.

## Definition of Done

Ortsvergleich ohne Kanal, mit ausgefallenen Kanälen oder ohne Wetterdaten nennt den Grund; Doppelklick verschickt genau eine Mail.

## Wie geprüft wird

Tests prüfen Fehlerfälle, Trennung zwischen zwei Nutzern und Anzeige; die Einzelzustellung bei Doppelklick zählt nur live auf Staging.

## Kritische Anmerkungen

- Nicht verlangt: Auch der automatische Zeitplan-Versand ändert sich; Ortsvergleiche ohne E-Mail-Adresse gehen künftig an Telegram/SMS.
- Abweichung vom Ticket: Sperrschlüssel ohne Slot, Antwort ohne Gewinner und Empfängerzahl.
- Fehlertexte nur als „verständlich“ beschrieben; Wortlaut offen, Abnahme Geschmackssache.

## Freigabe-Frage

Soll der Handversand für Trip und Ortsvergleich so vereinheitlicht werden, inklusive geändertem automatischem Versand?
