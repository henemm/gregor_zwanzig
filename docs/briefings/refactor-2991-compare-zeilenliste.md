---
spec_file: docs/specs/modules/refactor_2991_compare_zeilenliste.md
spec_sha256: d95e3b8958a1a1eefe423a0dd84fc10429cbc5f1786c83d6901a17161d3012d3
spec_frozen_sha256: eee1ab6b9d203d8fd1c8aa680cef265c1f3166a37cd8ea459391c89ff064a581
---

# PO-Briefing: refactor-2991-compare-zeilenliste

- **Spec:** docs/specs/modules/refactor_2991_compare_zeilenliste.md
- **Issue:** #2991
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die Übersichtszeilen der Ortsvergleich-Mail kommen für Text- und HTML-Fassung aus einer gemeinsamen Liste statt aus zwei getrennten.

## Definition of Done

Text- und HTML-Mail zeigen immer dieselben Übersichtszeilen in derselben Reihenfolge, alle Kanäle bleiben unverändert, und die zugestellte Staging-Mail besteht die Prüfung.

## Wie geprüft wird

Automatische Tests vergleichen Text und HTML direkt und sichern Bestandsformate ab; die Optik der Mail beurteilt kein Test.

## Kritische Anmerkungen

- Einzige sichtbare Änderung: Eine doppelt gespeicherte Metrik erscheint im HTML nur noch einmal, wie schon im Text.
- Weitere Doppelungen (Stundenzellen, Abschnitte, Einfach-Form, Formatunterschiede) bleiben bewusst offen, Folge-Issue #3425.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
