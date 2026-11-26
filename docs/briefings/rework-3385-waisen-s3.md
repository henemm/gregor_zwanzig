---
spec_file: docs/specs/modules/rework_3385_waisen_s3.md
spec_sha256: de1476d10bf103b4a0f611134f8ba7db7433500bacc9df2d793b1e9ec50cd966
spec_frozen_sha256: c78e56f20be65e51ef9099b82e152584e1c54d4cad272fdbab0343878f495e3b
---

# PO-Briefing: rework-3385-waisen-s3

- **Spec:** docs/specs/modules/rework_3385_waisen_s3.md
- **Issue:** #3385
- **Erstellt:** 2026-11-26

## Was gebaut wird

Sieben ungenutzte Versand-Bausteine samt zugehöriger Tests werden gelöscht; für Nutzer ändert sich nichts Sichtbares.

## Definition of Done

Der Waisen-Wächter steht auf null, alle Tests, Build und CI sind grün, und die Anwendung sieht unverändert aus.

## Wie geprüft wird

Wächter, Löschnachweis, Testsuite und Build belegen sauberes Löschen; Unverändertheit wird nur indirekt belegt, nicht durch neue Browser-Tests.

## Kritische Anmerkungen

- Zwei Testfälle zur Telegram-Zeilengrenze im Ortsvergleich werden zu Ausnahmen herabgestuft; die Grenze ist dort nicht mehr prüfbar (Folge-Issue #3390).
- Tote Exporte aus #3020 sind nicht enthalten, sondern in #3389 abgespalten.

## Freigabe-Frage

Darf die Telegram-Zeilengrenze im Ortsvergleich vorerst ungeprüft bleiben, bis Issue #3390 sie wieder prüfbar macht?

## Ampel

Ampel: rot
