---
spec_file: docs/specs/modules/fix_3219_selftest_botmenue_timeout.md
spec_sha256: 8240d7444b944d8668a49ea8b105d10209442b648d45c5facd064471d463f630
spec_frozen_sha256: 1d2e3d312b4affd81f24d43a5cace6b1eebe43f0aefcfbeac07f0cb25ed437ac
---

# PO-Briefing: fix-3219-selftest-botmenue-timeout

- **Spec:** docs/specs/modules/fix_3219_selftest_botmenue_timeout.md
- **Issue:** #3219
- **Erstellt:** 2026-11-27

## Was gebaut wird

Ein kurzer Telegram-Hänger lässt den Prod-Selbsttest nicht mehr scheitern; er versucht es bis zu dreimal und benennt Ausfälle ehrlich.

## Definition of Done

Nach dem nächsten Deploy zeigt der Selbsttest-Bericht bei Telegram-Ausfall "nicht erreichbar" statt "Regression", ein falsches Menü bleibt rot.

## Wie geprüft wird

Automatische Tests mit echtem lokalem Testserver decken Hänger, Fehlercodes und falsches Menü ab; echtes Telegram wird dabei nicht angesprochen.

## Kritische Anmerkungen

- Bei dauerhaftem Telegram-Ausfall endet der Selbsttest grün (Exit 0), ein echter Menüfehler bliebe unbemerkt, aber im Bericht sichtbar.
- Ursache der Langsamkeit nicht in Python gefunden, sondern Telegram oder Netz; Fix ist nur Toleranz.
- Der Selbsttest dauert im Störfall bis zu 42 Sekunden länger.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
