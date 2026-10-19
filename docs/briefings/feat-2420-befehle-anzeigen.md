---
spec_file: docs/specs/modules/feat_2420_befehle_anzeigen.md
spec_sha256: 855ee8383d9d52526f2a2e32c59886604894217856248dbb01011405bb251880
spec_frozen_sha256: b12ed71e45bec7ffb5b50522fc096dfc0fa0501108c7b01d47ed06bf311ada33
---

# PO-Briefing: feat-2420-befehle-anzeigen

- **Spec:** docs/specs/modules/feat_2420_befehle_anzeigen.md
- **Issue:** #2420
- **Erstellt:** 2026-10-19

## Was gebaut wird

Hilfe, Trip-Mail und Telegram-Menü nennen zusätzlich STARTDATUM und REPORT; die Ortsvergleichs-Mail erhält eine Befehlsliste.

## Definition of Done

Trip-Mail zeigt 15 Befehle, Ortsvergleichs-Mail zeigt PAUSE, WEITER, HILFE, KUERZEL, und STARTDATUM/REPORT funktionieren per Premium-SMS.

## Wie geprüft wird

Tests schicken Befehle durch die echten Eingänge und prüfen beide Mail-Blöcke; das Telegram-Menü wird nur formal geprüft.

## Kritische Anmerkungen

- COLUMNS wird weder angeboten noch entfernt, ABBRUCH nur als Hinweis bei STOP; Anfrage verlangte anbieten oder entfernen.
- Neu: Premium-SMS erkennt STARTDATUM/REPORT als Einzelwort; REPORT versendet real, ohne neue Drosselung.
- Premium-SMS-Kurzhilfe hat nur 1 Zeichen Reserve zum Drei-Nachrichten-Limit.

## Freigabe-Frage

Gebe ich frei, dass STARTDATUM und REPORT angeboten werden, COLUMNS unlisted bleibt und ABBRUCH nur als STOP-Hinweis erscheint?
