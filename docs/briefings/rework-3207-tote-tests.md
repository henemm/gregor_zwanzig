---
spec_file: docs/specs/modules/tote_tests_inventur.md
spec_sha256: 2a96dac1bc5e96adc8b66916bf0e0a4fef716aa5382400c89d744fbb4f9266c8
spec_frozen_sha256: 79086d3f8eceb11912151e47844b2f57d2b91659477f2b248d9ccf8c7f41a67f
---

# PO-Briefing: rework-3207-tote-tests

- **Spec:** docs/specs/modules/tote_tests_inventur.md
- **Issue:** #3207
- **Erstellt:** 2026-11-21

## Was gebaut wird

Veraltete Tests für längst entfernte Funktionen werden gelöscht, und eine Regel sorgt künftig dafür, dass das nicht wieder liegen bleibt.

## Definition of Done

Jede gelöschte Datei ist belegt, drei Stichproben-Verfälschungen machen Nachfolgetests rot, die Regel mit Prüfdatum steht, alle Prüfungen sind grün.

## Wie geprüft wird

Nur die Regel hat einen automatischen Test; Löschbelege, Stichproben und Testlisten-Vergleiche werden von Hand geprüft, dazu laufen alle sechs Auslieferungs-Prüfungen.

## Kritische Anmerkungen

- Inventur ist Stichprobe: nur etwa 45 Dateien betroffen, nicht alle 287 geprüft; Rest bleibt unbewertet.
- Löschbelege und Gegenproben sind nur manuell prüfbar; die Regel selbst ist nicht automatisch durchsetzbar.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
