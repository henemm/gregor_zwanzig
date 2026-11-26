---
spec_file: docs/specs/fast/fix-3430-radar-ein-ort.md
spec_sha256: 96ed6c8f0c8e49e93c109c71f6835098370eadf2d47540418f72f62d99843d3c
spec_frozen_sha256: a6462903739a4a9e533c15a0bfeb8b8fa708f08c6b2f73627bc1ecc534692e1c
---

# PO-Briefing: fix-3430-radar-ein-ort

- **Spec:** docs/specs/fast/fix-3430-radar-ein-ort.md
- **Issue:** #3430
- **Erstellt:** 2026-11-26

## Was gebaut wird

Im Reiter Wetter steht bei genau einem Ort „Regen auf deinen Ort“ statt „deine Orte“, auch auf Englisch.

## Definition of Done

Ein Orte-Abo mit einem Ort zeigt im Reiter Wetter „deinen Ort“ beziehungsweise „your location“; mehrere Orte und Trips zeigen weiter den bisherigen Text.

## Wie geprüft wird

Automatische Tests prüfen Auswahl und Anzeige in Deutsch und Englisch sowie die erweiterte Ein-Ort-Prüfung; die Darstellung auf Staging wird manuell geprüft.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
