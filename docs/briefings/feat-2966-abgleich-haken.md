---
spec_file: docs/specs/modules/feat_2966_abgleich_haken.md
spec_sha256: db28e35a716e25422c82009a6e73aff799ef12bb059696eb6dcf28cf05d23027
spec_frozen_sha256: 75805eea306e86a2ad87a74e942f1c1f486a3ca09d5e1e3e052cdc4fc801acd3
---

# PO-Briefing: feat-2966-abgleich-haken

- **Spec:** docs/specs/modules/feat_2966_abgleich_haken.md
- **Issue:** #2966
- **Erstellt:** 2026-11-17

## Was gebaut wird

Der Seitenabgleich findet im Reiter Wetter Titel, Lade- und Fehlerzustand sowie Grenzen- und Vorlagen-Dialoge künftig selbst.

## Definition of Done

Der Staging-Abgleich meldet für alle 35 bisherigen Abschnitte „gefunden“ oder „abweichend“ mit Grund, und nichts wird dabei gespeichert.

## Wie geprüft wird

Automatische Tests prüfen Markierungen und Bedienplan; ein Staging-Lauf in Deutsch und Englisch prüft alle 35 Abschnitte, nicht aber die Optik.

## Kritische Anmerkungen

- Die Fehlermeldung beim Laden wird sichtbar in zwei Absätze geteilt, Wortlaut gleich; das verlangte das Ticket nicht ausdrücklich.
- Echte Restabweichungen (Beispieldaten, Anführungszeichen, Platzhalter) werden nicht behoben, sondern nur neuen Tickets zugeordnet.
- Metriken ohne Grenzen-Knopf bleiben „nicht prüfbar“, mit Begründung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
