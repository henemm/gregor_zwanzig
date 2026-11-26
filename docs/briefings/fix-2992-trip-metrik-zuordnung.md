---
spec_file: docs/specs/modules/compare_summary_trip_ids_from_catalog.md
spec_sha256: fb907ce7893009661a228d292450e4090b7aa927ebba45f48d554e61e4ca479e
spec_frozen_sha256: 291525388b9e995b6aaf2ec566424856341d338d8285877727c917aa9bf2a806
---

# PO-Briefing: fix-2992-trip-metrik-zuordnung

- **Spec:** docs/specs/modules/compare_summary_trip_ids_from_catalog.md
- **Issue:** #2992
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die Zusammenfassung der Vergleichsmail bezieht ihre Messgrössen-Zuordnung aus einer einzigen Quelle statt aus zwei von Hand gepflegten Listen.

## Definition of Done

Der Zusammenfassungssatz der Vergleichsmail lautet für alle geprüften Auswahlen wortgleich wie vorher, und die doppelt gepflegte Liste existiert nicht mehr.

## Wie geprüft wird

Tests vergleichen den Satz für drei Auswahlen mit dem früheren Wortlaut und prüfen die Zuordnung; andere Auswahlen bleiben ungeprüft.

## Kritische Anmerkungen

- Der im Ticket genannte Paritätstest bewacht diese Zuordnung gar nicht; ein neuer Wächtertest schliesst die Lücke.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
