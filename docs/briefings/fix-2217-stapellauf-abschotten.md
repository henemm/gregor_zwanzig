---
spec_file: docs/specs/modules/fix_2217_stapellauf_abschotten.md
spec_sha256: c6fccfef6fabc3ae4a5fc47b7bfe4dfc1a94004156c64034b63ddf02276c81a0
---

# PO-Briefing: fix-2217-stapellauf-abschotten

- **Spec:** docs/specs/modules/fix_2217_stapellauf_abschotten.md
- **Issue:** #2217
- **Erstellt:** 2026-10-06

## Was gebaut wird

Ein fehlerhafter Trip oder Absturz eines Hintergrundjobs stoppt nicht mehr die Alarme und Briefings aller anderen.

## Definition of Done

Bei einem kaputten Trip erhalten alle übrigen weiter Alarme und Briefings; der Fehler bleibt als Status „error“ sichtbar.

## Wie geprüft wird

Automatische Tests mit kaputtem Trip, zwei Nutzern und simuliertem Absturz; ein echter Absturz ist auf Staging nicht herstellbar.

## Kritische Anmerkungen

- Umfang größer als im Issue: auch Briefings und Ortsvergleiche, ca. 1200 geänderte Zeilen, Limit-Erhöhung nötig.
- Überlappungsschutz aus dem Issue bewusst weggelassen, weil er mit bestehender Sperre kollidiert; Begründung plausibel.
- Dauerhaft kaputter Trip hält den Job bei jedem Lauf auf „error“.

## Freigabe-Frage

Soll der erweiterte Umfang (Alarme, Briefings, Ortsvergleiche) ohne den Überlappungsschutz aus dem Issue so umgesetzt werden?
