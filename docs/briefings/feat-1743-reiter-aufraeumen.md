---
spec_file: docs/specs/modules/feat_1743_reiter_aufraeumen.md
spec_sha256: de22491139529246a513d890a3b2c4477da7b2744a718bb8227caf8cb9103d42
spec_frozen_sha256: 5aa0ad2daca2a3ae4abca5b01ae4dd08e5fc99b9e862a7a964d023c83eba17d5
---

# PO-Briefing: feat-1743-reiter-aufraeumen

- **Spec:** docs/specs/modules/feat_1743_reiter_aufraeumen.md
- **Issue:** #1743
- **Erstellt:** 2026-10-22

## Was gebaut wird

Trip und Ortsvergleich bekommen je fünf Reiter; Versand steht unter Wetter-Metriken, die Briefing-Vorschau entfällt ersatzlos.

## Definition of Done

Beide Detailseiten und beide Anlegeseiten zeigen fünf Reiter, Versand unten bei Wetter-Metriken, keine Vorschau außer Alarm-Vorschau; zwei schnelle Änderungen gehen nie verloren.

## Wie geprüft wird

Tests prüfen Reiter, Alt-Links, gleichzeitiges Speichern und entfernte Schnittstellen; Anlegen ohne Versand-Berührung wird zusätzlich live auf Staging nachgewiesen.

## Kritische Anmerkungen

- Zwei Staging-Prüfungen werden gelöscht; deren Abdeckung gilt danach als verloren (Buchung in #1196).
- Zusatzumfang: drei weitere Server-Schnittstellen, Vorschau-Bausteine und tote Python-Hüllen entfallen; Briefing je Kanal nirgends mehr vorab sehbar.
- Alte Versand-Links landen auf Wetter-Metriken.

## Freigabe-Frage

Gibst du frei, dass die Briefing-Vorschau samt allen Resten und drei Server-Schnittstellen entfällt und zwei Staging-Prüfungen gelöscht werden?
