---
spec_file: docs/specs/modules/feat_2280_handversand_endpoint.md
spec_sha256: c386f3f0d25933f6a5d1c17039234354a35d7ebd6d3da0038df18078824bfa36
spec_frozen_sha256: e7bf4686f9cb5f19654e7dd93b6e855cd869bb2abcba0b3ce7f95685b098334b
---

# PO-Briefing: feat-2280-handversand-endpoint

- **Spec:** docs/specs/modules/feat_2280_handversand_endpoint.md
- **Issue:** #2280
- **Erstellt:** 2026-10-20
- **Hinweis:** Seit der Freigabe nur Spiegelstriche vor den Kriterien ergänzt (Formatierung); inhaltlich hat sich nichts geändert.

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
