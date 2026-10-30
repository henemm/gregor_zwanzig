---
spec_file: docs/specs/modules/claude_md_verschlankung.md
spec_sha256: ff2bb600c27bf7f4318ea87e6fef283cd744cd10282062679b0072fac11401ad
spec_frozen_sha256: 109ea5807899bc9e75b9a0d37d74729cdced11a85ab4a1656a2848ad8cc923fc
---

# PO-Briefing: docs-2640-claude-md-verschlanken

- **Spec:** docs/specs/modules/claude_md_verschlankung.md
- **Issue:** #2640
- **Erstellt:** 2026-10-30

## Was gebaut wird

Die Projekt-Anleitung für Claude wird auf unter 120 Zeilen gekürzt, Details wandern verlustfrei in die Referenz-Dokumentation.

## Definition of Done

Die Anleitung hat höchstens 120 Zeilen und 12 KB, alle Verweise treffen existierende Dateien, und jede entfernte Regel steht andernorts.

## Wie geprüft wird

Ein neuer Größenwächter und bestehende Tests belegen Größe, Verweise und Pflichtinhalte; dass nichts verloren ging, prüft nur ein manueller Zeilenabgleich.

## Kritische Anmerkungen

- Reicht 12 KB nicht, schlägt die Umsetzung 14 KB vor; dann entscheidest du, nicht die Umsetzung.
- Zusätzlich zum Ticket: neuer Wächtertest und Korrektur der Workflow-Variable (OPENSPEC statt GZ) in der Doku.
- Zeilenabgleich gegen den Altbestand (AC-7) ist Handprüfung, kein automatischer Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
