---
spec_file: docs/specs/modules/rework_3263_doppelte_zusicherungen_2795.md
spec_sha256: c2bd4adf23da3a148a24b790b4f206a6f1558141d5fde6863603653f5dbed58f
spec_frozen_sha256: 06e1ad8d5c44826e40d0c8a9135489b7604c031c10565f82c7b5a95787f25cc6
---

# PO-Briefing: rework-3263-doppelte-tests-2795

- **Spec:** docs/specs/modules/rework_3263_doppelte_zusicherungen_2795.md
- **Issue:** #3263
- **Erstellt:** 2026-11-23

## Was gebaut wird

Ein doppelt vorhandener Prüfschritt der Migrations-Tests wird entfernt; die übrigen sieben geprüften Testdateien bleiben unverändert.

## Definition of Done

Der überflüssige Test ist weg, die Prüfung bleibt an einer Stelle erhalten, und alle betroffenen Tests sowie alle sechs CI-Prüfungen sind grün.

## Wie geprüft wird

Gezielte Verfälschungen des Migrationsskripts zeigen vorher und nachher, dass der bleibende Test dieselben Fehler fängt; Produktivcode bleibt unberührt.

## Kritische Anmerkungen

- Ausbeute klein: nur ein Test entfernt, die Fix-Runden-Dateien sind inhaltlich verschieden. Das ist als Befund dokumentiert.
- Dateiunverändertheit und Produktcode-Freiheit werden per Diff-Prüfung im Review belegt, nicht durch einen automatischen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
