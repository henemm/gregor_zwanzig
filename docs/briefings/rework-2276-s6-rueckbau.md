---
spec_file: docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md
spec_sha256: 95c4a07902c5ebf983c673becdf6cda1125ccc0d040c1bd1d33f8058784b243a
---

# PO-Briefing: rework-2276-s6-rueckbau

- **Spec:** docs/specs/modules/rework_2276_s6a_totcode_und_ratsche.md
- **Issue:** #2276
- **Erstellt:** 2026-09-20

## Was gebaut wird

Entfernt: nie aufgerufene Speicherfunktion, doppelter Typname, vier Legacy-Felder, immer wahre Bedingung, alte Kommentare. Neues Prüfwerkzeug hält 69 heutige Stellen mit Datei und Zeile fest — Messlatte für Folgescheiben.

## Definition of Done

Tests bleiben grün, neue Prüfung hält heutige Stellenzahl exakt fest.

## Wie geprüft wird

Automatische Tests plus Gegenprobe: eine Zeile aus der Liste entfernen — Prüfung muss fehlschlagen, sonst gilt Scheibe als nicht erfüllt.

## Kritische Anmerkungen

- Scheibe zeigt nichts sichtbar; Anforderungen folgen erst in fünf weiteren Scheiben.
- Ticket-Bedingung wird fürs Restprojekt neu gefasst, braucht Ihre Freigabe.
- Sechs statt vier Teilschritte verlängern die Gesamtlaufzeit.

## Freigabe-Frage

Alt: „nur sachlich begründete Unterschiede bleiben." Neu: „keine Stelle unterscheidet nach Herkunft oder Speicherort; optische Unterschiede bleiben, einzeln begründet." Gilt fürs Restvorhaben — zustimmen?
