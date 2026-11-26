---
spec_file: docs/specs/modules/rework_3375_wsw_browserpruefungen.md
spec_sha256: 640e61bcab0013e9c0a335656c94478c661ec885dbc38865cde06facacf0a483
spec_frozen_sha256: 3e7c95b6defdeb5e32228df132c0c18f833b1fb7c1c320656d29366a9bbbe897
---

# PO-Briefing: rework-3375-wsw-browserpruefungen

- **Spec:** docs/specs/modules/rework_3375_wsw_browserpruefungen.md
- **Issue:** #3375
- **Erstellt:** 2026-11-26

## Was gebaut wird

Zwei Browser-Prüfungen weisen nach: Telegram zeigt ab der 8. Metrik nur Tageswert, und Marken werden bei keiner Breite abgeschnitten.

## Definition of Done

Beide neuen Browser-Prüfungen laufen gegen den echten Server grün und werden bei absichtlich eingebauten Fehlern nachweislich rot.

## Wie geprüft wird

Die Prüfungen öffnen die Karte im Browser, auch bei 14 Fensterbreiten; sie ändern kein Produktverhalten und prüfen nur diese beiden Zusicherungen.

## Kritische Anmerkungen

- Spec prüft bis 1920 Pixel statt verlangter 1440 und zusätzlich den Ortsvergleich; strenger als gefordert, unkritisch.
- Im Ortsvergleich genügt notfalls irgendeine Marke, falls der Server keine „passt nicht mehr“-Marke liefert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
