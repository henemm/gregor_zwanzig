---
spec_file: docs/specs/modules/feat_3390_ortsvergleich_telegram_zeilen.md
spec_sha256: 58a8e84028590911bb8c5541ff43f8256981dad48d906dc15c449a62b0b7be61
spec_frozen_sha256: dcd4a813941e898750de8f42ce98e81d51607b7d37fd1312f2404e3b8f713baf
---

# PO-Briefing: feat-3390-ortsvergleich-telegram-zeilen

- **Spec:** docs/specs/modules/feat_3390_ortsvergleich_telegram_zeilen.md
- **Issue:** #3390
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die Fallliste beweist künftig, dass der Ortsvergleich in Telegram jede gewählte Metrik zeigt, statt sie als Ausnahme zu führen.

## Definition of Done

Beide Telegram-Fälle des Ortsvergleichs (Deutsch, Englisch) stehen als grün geführt, verweisen auf bestehende grüne Tests, am Produkt ändert sich nichts.

## Wie geprüft wird

Ein neuer Test sichert beide Fälle und ihren Verweis; er beweist nicht die Telegram-Nachricht selbst, nur die Kartenanzeige.

## Kritische Anmerkungen

- Ursprungsanfrage nur über den Auftrag bekannt; Issue-Text selbst nicht gelesen, Abgleich stützt sich auf PO-Entscheidung vom 26.11.
- Zweite Zeile ab Platz 8 wird nicht angezeigt; bewusst, Prüfung der Telegram-Ausgabe folgt in Issue 3404.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
