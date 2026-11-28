---
spec_file: docs/specs/modules/fix_3436_tempo_abschnitt.md
spec_sha256: c3fcf07dbb13334e5a0e4af0a3e0759daeaf2eded6cdb3fa13d8eeae3d60e294
spec_frozen_sha256: 6c26a8d0df63e318ecbd79f09c951c60b5b47a51a8696e92f849fbfd1b1b1483
---

# PO-Briefing: fix-3436-tempo-abschnitt

- **Spec:** docs/specs/modules/fix_3436_tempo_abschnitt.md
- **Issue:** #3436
- **Erstellt:** 2026-11-28

## Was gebaut wird

Die Prüfung des Reiters Etappen erkennt die Tempo-Karte und akzeptiert Grundtempo samt Hinweistext als bewusste Abweichung vom Mockup.

## Definition of Done

Der Abgleich gegen die Testumgebung meldet für den Tempo-Bereich in Deutsch und Englisch keine Abweichung und keinen herrenlosen Text mehr.

## Wie geprüft wird

Automatische Tests belegen Markierung, Freigaben und Ausnahmen; der Abgleich auf der Testumgebung wird nur als Messlauf dokumentiert, nicht automatisiert.

## Kritische Anmerkungen

- Das Mockup wird nicht nachgebaut: Grundtempo bleibt, wie von dir in #3196 entschieden. Für Nutzer ändert sich nichts Sichtbares.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
