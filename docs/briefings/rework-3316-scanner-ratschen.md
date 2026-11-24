---
spec_file: docs/specs/modules/rework_3316_scanner_ratschen_tempo_s2.md
spec_sha256: 0b44a023fa9b1546e9361754a969d2adc741fa653be9dc2e5963863db90b0beb
spec_frozen_sha256: 44f13c8385bee489b0b513eb4c68d9acd817f343ad3448880571e1e2c8a8daba
---

# PO-Briefing: rework-3316-scanner-ratschen

- **Spec:** docs/specs/modules/rework_3316_scanner_ratschen_tempo_s2.md
- **Issue:** #3316
- **Erstellt:** 2026-11-24

## Was gebaut wird

Drei langsame Wächter-Tests der Testsuite laufen schneller, ohne dass sie weniger prüfen.

## Definition of Done

Alle zehn Kriterien erfüllt, Vorher-Nachher-Zeiten dokumentiert, der Testlauf auf dem Server grün und die 180-Sekunden-Sondergrenze entfernt.

## Wie geprüft wird

Gepflanzte Verstöße und gezielt verfälschte Filter beweisen, dass die Wächter nichts übersehen; Laufzeit wird einmalig gemessen, nicht dauerhaft getestet.

## Kritische Anmerkungen

- Geschätzter Umfang 240–290 Zeilen, über der 250er-Grenze; die Spec sieht bei Überschreitung vor, Teile abzutrennen.
- Ein Wächter hat im echten Testbestand null Kandidaten; der Filter ist dort nur durch gepflanzte Fälle belegt.
- Gewinn auf dem Server unsicher: Messwerte schwanken stark, Hauptnutzen ist nur mehr Reserve zur 30-Sekunden-Grenze.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
