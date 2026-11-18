---
spec_file: docs/specs/modules/feat_3100_premium_sms_fallliste.md
spec_sha256: f884ada208a9e678954401aa2dc0f84e7f123946d922a56d6600646d806d8628
spec_frozen_sha256: 8fc76e2682e5cb77ab2c096f77dc89e42677ae4940b9928dc501f273bee36743
---

# PO-Briefing: feat-3100-premium-sms-fallliste

- **Spec:** docs/specs/modules/feat_3100_premium_sms_fallliste.md
- **Issue:** #3100
- **Erstellt:** 2026-11-17

## Was gebaut wird

Ein Prüfkatalog belegt, dass die Premium-SMS auf Garmin-Befehle denselben Inhalt liefert wie die normale SMS.

## Definition of Done

Alle neun Kriterien sind durch grüne Tests belegt, der Wächter zählt die neue Fallliste mit, und die Produktion verhält sich unverändert.

## Wie geprüft wird

Tests spielen Garmin-Befehle zweier Nutzer durch den echten Empfangsweg ein; der Live-Empfang auf der zweiten Nummer ist nicht Teil davon.

## Kritische Anmerkungen

- Eigene Premium-Auswahl entfällt, wie von Ihnen am 17.11. entschieden (ADR-0124 Nr. 8); sie kommt frühestens mit #2801.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
