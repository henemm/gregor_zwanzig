---
spec_file: docs/specs/modules/fix_2744_uhrzeitunabhaengige_tests.md
spec_sha256: e92f8f21d698751c22a155a92a3347ec4019762c4b2f84c7e7715a9cf3f7fb6c
spec_frozen_sha256: 4350c67a787a8bf20fa44942971f23ff7ed8c9aca088891fe03aa539d5b8e392
---

# PO-Briefing: fix-2744-uhrzeitabhaengige-tests

- **Spec:** docs/specs/modules/fix_2744_uhrzeitunabhaengige_tests.md
- **Issue:** #2744
- **Erstellt:** 2026-11-06

## Was gebaut wird

Sechs Tests werden so umgestellt, dass sie zu jeder Tageszeit grün laufen und keine Merges mehr blockieren.

## Definition of Done

Die betroffenen Tests sind bei gestellter Uhr um 12:00, 23:40 und 23:58 UTC grün; Produktivcode bleibt unverändert.

## Wie geprüft wird

Drei Läufe mit gestellter Uhr sowie Gegenproben mit absichtlich eingebauten Fehlern; ob das Produkt um Mitternacht korrekt rechnet, wird nicht geprüft.

## Kritische Anmerkungen

- Ursprungsanfrage lag nur als Kontext-Zusammenfassung vor, der Issue-Text selbst war nicht abrufbar; Deckung dadurch nur gegen diese Zusammenfassung geprüft.
- Frage "Produktfehler bei Tageswechsel?" wird in der Spec als reines Testartefakt beantwortet, ohne Produktprüfung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
