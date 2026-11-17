---
spec_file: docs/specs/modules/feat_3098_telegram_resolver.md
spec_sha256: fe2b2869f13aed297ae9059ca314377f39f4fae43286ac076c84cb5048cde813
spec_frozen_sha256: a951da3f67ec648fdabb803fbc7677ed795682b3923694cbb718313c7e861ae8
---

# PO-Briefing: feature-3098-telegram-resolver

- **Spec:** docs/specs/modules/feat_3098_telegram_resolver.md
- **Issue:** #3098
- **Erstellt:** 2026-11-17

## Was gebaut wird

Die Telegram-Nachricht des Trips übernimmt Metriken, Reihenfolge und Roh/Einfach aus der gemeinsamen Einstellungsquelle; die Nachricht selbst bleibt unverändert.

## Definition of Done

Telegram-Nachrichten für Trip und Orte sind in allen bisherigen Fällen zeichengleich, die neue Telegram-Fallliste ist grün, und die Staging-Nachricht stimmt.

## Wie geprüft wird

Tests prüfen die echte Telegram-Ausgabe (Folge, Roh/Einfach, DE/EN, zwei Nutzer); ob echte Zustellung stimmt, zeigt nur die Staging-Prüfung.

## Kritische Anmerkungen

- Die zwei offenen Funde aus #3063 sind schon behoben; hier gibt es nur den Nachweis, dann wird #3063 geschlossen.
- Orte-Telegram nutzt den Resolver bereits; dort entsteht kein neuer Code, nur Prüffälle.
- Ohne Format-Angabe bleibt Trip bei Katalog-Darstellung, Orte bei Roh (frühere Entscheidung, dokumentiert).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
