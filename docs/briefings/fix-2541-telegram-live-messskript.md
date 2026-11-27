---
spec_file: docs/specs/modules/fix_2541_telegram_live_messskript.md
spec_sha256: 443f1d0e070a5f262ddbe652796e7617aae2e84529277fe217f44c5e94fc20df
spec_frozen_sha256: d6236d511957a8cd23d2d9aa0b9452fde414efe899a2dab7faa885291df9a467
---

# PO-Briefing: fix-2541-telegram-live-messskript

- **Spec:** docs/specs/modules/fix_2541_telegram_live_messskript.md
- **Issue:** #2541
- **Erstellt:** 2026-11-27

## Was gebaut wird

Ein Prüfskript testet Telegram auf Staging automatisch, ohne dass der Agent Zugangsdaten lesen muss.

## Definition of Done

Das Skript läuft auf Staging grün durch, schreibt einen Nachweis, und der Produktiv-Deploy lässt sich ohne Zugriff des Agenten auf Zugangsdaten freigeben.

## Wie geprüft wird

Automatische Tests prüfen Auswertung, Geheimhaltung und Freigabe-Sperre ohne Netz; der echte Telegram-Versand wird nur im Staging-Lauf nachgewiesen.

## Kritische Anmerkungen

- Ticket verlangt Test mit zwei Nutzern; Spec prüft nur, dass ein zweiter Nutzer unverändert bleibt, nicht dass er Befehle ausführt.
- Nachweis-Datei ist theoretisch von Hand schreibbar; Herkunftsschutz bewusst ausgeklammert (dokumentiert).

## Freigabe-Frage

Genügt als Zwei-Nutzer-Test, dass ein zweiter Nutzer unverändert bleibt, oder soll er wirklich Telegram-Befehle ausführen?

## Ampel

Ampel: rot
