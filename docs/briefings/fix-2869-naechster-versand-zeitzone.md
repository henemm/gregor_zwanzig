---
spec_file: docs/specs/modules/fix_2869_naechster_versand_datum.md
spec_sha256: 156f21b0220aea1bf1fabaf4697f9af3648fdbc67edabd889ae05f961d372fe5
spec_frozen_sha256: 9ae49b4dd310943dcbf0e6ebbe0f2659adf0868780c70bb1ed0a90b898e84e4b
---

# PO-Briefing: fix-2869-naechster-versand-zeitzone

- **Spec:** docs/specs/modules/fix_2869_naechster_versand_datum.md
- **Issue:** #2869
- **Erstellt:** 2026-11-11

## Was gebaut wird

Der nächste Versandtermin zeigt überall Wochentag und Datum, damit Trip und Ortsvergleich nicht mehr widersprüchlich wirken.

## Definition of Done

Auf Staging zeigen Trip und Ortsvergleich den nächsten Termin gleich, etwa „So 08.11. 06:00 (CET)“, auf Deutsch und Englisch, an allen Stellen.

## Wie geprüft wird

Automatische Tests prüfen Wortlaut, beide Sprachen und korrekte Zeitzone; jede Anforderung hat einen Test, die Anzeige im Browser wird zusätzlich auf Staging angesehen.

## Kritische Anmerkungen

- Kein Zonenfehler vorhanden: Es waren zwei verschiedene Sonntage. Die Lösung (Datum zeigen) weicht vom Ticket ab, entspricht aber deiner Entscheidung.
- Das Jahr wird nicht angezeigt; Termine über ein Jahr entfernt blieben mehrdeutig (dokumentierte Einschränkung).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
