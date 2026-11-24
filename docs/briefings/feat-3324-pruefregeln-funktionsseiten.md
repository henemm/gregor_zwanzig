---
spec_file: docs/specs/modules/pruefregeln_funktionsseiten_3324.md
spec_sha256: ca1916c33dcf0fe1d8821002d058cecaefecd908a64ec6ceb31c6257ca24d47b
spec_frozen_sha256: 1a5464b49376d1dbffd4439ad2598b30df8282ce45558d1ba0997c842ca0ba77
---

# PO-Briefing: feat-3324-pruefregeln-funktionsseiten

- **Spec:** docs/specs/modules/pruefregeln_funktionsseiten_3324.md
- **Issue:** #3324
- **Erstellt:** 2026-11-24

## Was gebaut wird

Automatische Prüfungen der Funktionsseiten erkennen mehr Ratschläge, schützen alle Bilder vor Personendaten und halten Befehlstexte aktuell.

## Definition of Done

Alle neuen Prüfregeln laufen grün, jede Gegenprobe schlägt gezielt rot an, und öffentliche Seiten und Bilder bleiben unverändert.

## Wie geprüft wird

Tests mit Beispielsätzen und echtem Browser belegen Erkennung und Abbruch; nicht erfasst bleiben Personendaten in Bildpixeln und ungewöhnliche Ratschlag-Formulierungen.

## Kritische Anmerkungen

- Archiv-Bild bleibt leer; als eigenes Ticket 3327 abgespalten, wie im Ticket-Kommentar vorgesehen.
- Ratschlag-Erkennung bleibt eine Heuristik; „check“ und „note that“ sind bewusst nicht erfasst.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
