---
spec_file: docs/specs/modules/rework_3331_validatoren_tempo.md
spec_sha256: 16728d48ed33e1670cb246c2f296016405276f60dac0e54d18bb28733d0ade5f
spec_frozen_sha256: 7184957fae56d7d72fe8a9bf43792a8498422a1b1268bc3872e7a82397af82a3
---

# PO-Briefing: rework-3331-validatoren-tempo

- **Spec:** docs/specs/modules/rework_3331_validatoren_tempo.md
- **Issue:** #3331
- **Erstellt:** 2026-11-24

## Was gebaut wird

Die Mail-Prüfungen der Testsuite laufen rund 40 Prozent schneller, ohne dass eine Prüfung schwächer wird.

## Definition of Done

Mindestens 25 Prozent kürzere Laufzeit der Datei auf dem Mac gemessen, alle Tests grün; sonst wird der Umbau zurückgenommen.

## Wie geprüft wird

Tests vergleichen Server- und Prozesslauf auf Gleichheit, je Prüfer läuft weiter ein echter Prozess; Linux-Laufzeit im CI bleibt zunächst ungemessen.

## Kritische Anmerkungen

- Umfang bis 400 statt 250 Zeilen; die Freigabe bedeutet Zustimmung zur Überschreitung.
- Gewinn nur auf dem Mac gemessen; Tempo und Stabilität unter Linux-CI erst nach Umsetzung belegbar.

## Freigabe-Frage

Erlaubst du für diesen Umbau bis zu 400 statt der üblichen 250 Zeilen Änderung?

## Ampel

Ampel: rot
