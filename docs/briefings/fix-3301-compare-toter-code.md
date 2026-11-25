---
spec_file: docs/specs/fast/fix-3301-compare-toter-code.md
spec_sha256: da0510302e9bf7c820b9c4bcc37c7e6e6077744daaf20ef4c7a16a291663dce9
spec_frozen_sha256: a62aee672939f5a69a72ef57f2afb792a43ce1f2c57f054b1bb0952d7f858b21
---

# PO-Briefing: fix-3301-compare-toter-code

- **Spec:** docs/specs/fast/fix-3301-compare-toter-code.md
- **Issue:** #3301
- **Erstellt:** 2026-11-25

## Was gebaut wird

Toter Programmcode des Ortsvergleichs wird entfernt; sichtbar ändert sich nichts, die Kanal-Layout-Karte ist bereits weg.

## Definition of Done

Beim Anlegen eines Ortsvergleichs erscheint keine Karte „Layout je Kanal“, und Speichern sowie Neuladen behalten alle Werte unverändert.

## Wie geprüft wird

Automatische Tests belegen, dass der Code gelöscht ist und Speichern die Stundenwerte erhält; die fehlende Karte selbst prüft nur die manuelle Staging-Abnahme.

## Kritische Anmerkungen

- Die Karte verschwand schon mit dem Trip-Rückbau (#3297); dieses Ticket räumt nur den Rest auf. Information, keine Entscheidung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
