---
spec_file: docs/specs/modules/rework_3279_scanner_ratschen_tempo_s1.md
spec_sha256: 87c18e500555217e26834e45a0d5dc2a1ca47ff2e044bdfdcd43fb752538d5fe
spec_frozen_sha256: dc499142c823fe5f463934ef98cdf330438ca0dabdb03a8c6394a355364cf8a2
---

# PO-Briefing: rework-3279-testsuite-tempo

- **Spec:** docs/specs/modules/rework_3279_scanner_ratschen_tempo_s1.md
- **Issue:** #3279
- **Erstellt:** 2026-11-24

## Was gebaut wird

Drei langsame Wächter-Tests der Testsuite laufen deutlich schneller, ohne weniger Fehler zu finden.

## Definition of Done

Alle acht Kriterien erfüllt, die drei Wächter bleiben unter 30 Sekunden mit unverändertem Limit, Messnachweise liegen vor, alle CI-Checks grün.

## Wie geprüft wird

Gepflanzte Verstöße und Cache-Tests laufen dauerhaft; Gleichheit zum Vorher, Zeitgewinn und Mutationsproben sind nur einmalige Messprotokolle.

## Kritische Anmerkungen

- Abweichung: Statt gemeinsamem Datei-Index (Ticket) wird vor dem Parsen nach Bezeichnern gefiltert; Begründung steht in der Spec.
- Nur drei der genannten Dateien werden umgebaut; Rest (Wartezeiten, Validator-Fälle) wandert in Folge-Tickets.

## Freigabe-Frage

Ist es in Ordnung, dass diese Scheibe nur drei Wächter per Vorfilter beschleunigt und der Rest in Folge-Tickets folgt?

## Ampel

Ampel: rot
