---
spec_file: docs/specs/modules/fix_3061_ausblick_alle_groessen.md
spec_sha256: 66dd764546be1d78d4d39da19328a88a4325384ca5d4b851659e41947512d5bc
spec_frozen_sha256: c9443754ba14dcef959c5466b1051edaf376e61159c7bc9e5a1677cfe3d49747
---

# PO-Briefing: fix-3061-ausblick-alle-groessen

- **Spec:** docs/specs/modules/fix_3061_ausblick_alle_groessen.md
- **Issue:** #3061
- **Erstellt:** 2026-11-16

## Was gebaut wird

Wer im Orte-Vergleich bewusst alle Größen wählt, sieht im Editor-Ausblick dieselben Größen wie in der Mail.

## Definition of Done

Ein Orte-Vergleich mit gespeicherter Vollauswahl zeigt im Editor-Ausblick auf Staging dieselben Größen wie die zugestellte Mail; alte Vergleiche ohne Einstellung bleiben unverändert.

## Wie geprüft wird

Automatische Tests vergleichen Editor und Mail für Vollauswahl und Altbestand sowie Speichern ohne Änderung; die Staging-Sichtprüfung ist nur manuell.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
