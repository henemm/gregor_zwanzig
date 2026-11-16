---
spec_file: docs/specs/modules/fix_3048_altbestand_telegram_kopf.md
spec_sha256: ba2ca394fd05e89d19d4600f0fccec0eeea0d3b259197cade66a7d821bc30ae3
spec_frozen_sha256: f959efdd64bed9e47146dda36377a7ce76c947a5d36699ad5158b728ad6596a1
---

# PO-Briefing: fix-3048-altbestand-telegram-kopf

- **Spec:** docs/specs/modules/fix_3048_altbestand_telegram_kopf.md
- **Issue:** #3048 (zusammen mit #3052)
- **Erstellt:** 2026-11-16

## Was gebaut wird

Trips ohne Metrik-Auswahl zeigen in Mail-Tabellen die Standardspalten, und der Telegram-Kopf nennt die Briefing-Art auf Deutsch.

## Definition of Done

Auf Staging zeigt eine deutsche Telegram-Nachricht „Abend/Morgen“ im Kopf, Mail-Tabellen stimmen mit dem Überblick überein, danach ist alles auf Produktion.

## Wie geprüft wird

Automatische Tests gegen die echte Kette belegen alle neun Kriterien; Staging-Prüfung per Telegram und Mail folgt, echte Altbestände existieren nicht.

## Kritische Anmerkungen

- Issue schlug bei Fällen eine Migration vor; die Spec ergänzt den Standardsatz stattdessen beim Laden, ohne Daten umzuschreiben.
- Bestand enthält keinen betroffenen Trip: Korrektur ist reine Absicherung für künftige Importe.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
