---
spec_file: docs/specs/modules/fix_1814_s2_telegram_alt_route_entfernen.md
spec_sha256: eb80a1978f87f1ea8356dc8dd38f47717848c933923c61f858b126d759cbe31e
spec_frozen_sha256: 8b60719a2ce8e568a73848f6a965c369ce4e1d1747e00b06716cce1eff4bba67
---

# PO-Briefing: fix-1814-telegram-alt-route-entfernen

- **Spec:** docs/specs/modules/fix_1814_s2_telegram_alt_route_entfernen.md
- **Issue:** #1814
- **Erstellt:** 2026-11-01

## Was gebaut wird

Der alte Telegram-Eingang mit Geheimwort in der Adresse wird abgeschaltet, das Geheimwort danach ausgetauscht.

## Definition of Done

Befehle kommen in Test und Produktion über den neuen Eingang an, das alte Geheimwort ist ungültig.

## Wie geprüft wird

Tests belegen, dass nur der neue Eingang annimmt; echter Bot-Empfang und Tausch werden nur per Handy-Test belegt.

## Kritische Anmerkungen

- Du sendest vor dem Abschalten einen Befehl vom Handy an den Bot; ohne Beleg wird nichts entfernt.
- Beim Tausch gehen Nachrichten sekundenlang ins Leere, für Nutzer unsichtbar; daher nicht während eines Alarms.
- Tausch in Produktion geht über das Ticket hinaus, ist aber begründet: auch dort stand das Geheimwort in der Adresse.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
