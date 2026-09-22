---
spec_file: docs/specs/modules/alert_metric_channels.md
spec_sha256: 05497c9af6f94ecda6a044aee87abb02397bfd33100a69e1933e5d2dec0192f2
---

# PO-Briefing: feat-1895-kanalzuordnung-je-metrik

- **Spec:** docs/specs/modules/alert_metric_channels.md
- **Issue:** #1895
- **Erstellt:** 2026-09-22

## Was gebaut wird

Ein neuer, noch ungenutzter Speicherplatz für künftige Kanal-Zuordnungen je Wettergröße wird angelegt, ohne App-Auswirkung.

## Definition of Done

Das Feld ist angelegt, Daten bleiben beim Speichern erhalten, ohne Bedienoberfläche, Migration oder Änderung bestehender Alarme.

## Wie geprüft wird

Automatisierte Tests bestätigen den Datenerhalt für zwei Nutzer; sie prüfen keine sichtbare Funktion in der App.

## Kritische Anmerkungen

- Liefert nichts Sichtbares; die Ticket-Frage „wohin wandert die Kanalzuordnung" beantworten erst spätere, noch nicht beauftragte Schritte.
- Zwei von neun Abnahmekriterien (AC-8, AC-9) prüfen nur Dokumentation und CI, keine Produkteigenschaft trotz gleicher Zählung.
- Spec erweitert den Speicherplatz zusätzlich auf den Ortsvergleich, den das Ticket nicht erwähnt (Konsistenz-Regel).

## Freigabe-Frage

Ist eine für Nutzer unsichtbare Datenvorbereitung freizugeben, obwohl die eigentliche Kanal-Zuordnung erst in späteren, separaten Aufträgen folgt?
