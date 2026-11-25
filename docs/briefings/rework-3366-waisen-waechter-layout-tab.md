---
spec_file: docs/specs/modules/rework_3366_waisen_waechter_layout_tab.md
spec_sha256: 2832ad1d85ab60f8bcdacce3c85fc51ec812677843b36712ddb5070efae777bb
spec_frozen_sha256: 5e95cc7d4d83a56d5b66e67f1ac67efc842a3020851e56663f3501f78443bbaf
---

# PO-Briefing: rework-3366-waisen-loeschen

- **Spec:** docs/specs/modules/rework_3366_waisen_waechter_layout_tab.md
- **Issue:** #3366
- **Erstellt:** 2026-11-25

## Was gebaut wird

Ungenutzte Altbausteine des Layout-Reiters werden gelöscht, und eine dauerhafte Sperre verhindert, dass solcher toter Code wiederkehrt.

## Definition of Done

Die 15 toten Dateien sind weg, die neue Sperre ist grün, und die Seiten sehen und verhalten sich unverändert.

## Wie geprüft wird

Automatische Tests belegen Löschung, Sperre und unveränderten Build; sie prüfen keine Optik, die Unverändertheit folgt nur aus grünen Gesamtläufen.

## Kritische Anmerkungen

- Nur 15 der über 40 Waisen fallen hier; der Rest folgt in den Issues #3383, #3384 und #3385.
- Eine Konventionsdatei und eine weitere Waise bleiben bewusst stehen; Begründungen stehen in der Spec.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
