---
spec_file: docs/specs/modules/feat_1743_reiter_aufraeumen.md
spec_sha256: 2a459c8e20c5bd41bef9fb858e8fbf9f477e29732d41212fcc363116ab913810
spec_frozen_sha256: 8e3b90e5db7e737dde155b98c573072ab34f8c81ab37de8c3b3fd2c4b13fa05d
---

# PO-Briefing: feat-1743-reiter-aufraeumen

- **Spec:** docs/specs/modules/feat_1743_reiter_aufraeumen.md
- **Issue:** #1743
- **Erstellt:** 2026-10-22

## Was gebaut wird

Trip- und Ortsvergleich-Seiten haben fünf statt sieben Reiter; Versand steht unten bei Wetter-Metriken, die Briefing-Vorschau entfällt.

## Definition of Done

Beide Detailseiten und beide Anlege-Seiten zeigen fünf Reiter, Versand-Einstellungen liegen unten bei Wetter-Metriken, alte Links führen dorthin, Speichern verliert nichts.

## Wie geprüft wird

Tests prüfen Reiter, alte Links, gleichzeitiges Speichern und Anlegen; ob die Wetter-Metriken-Seite durch den Anhang noch übersichtlich bleibt, prüft kein Test.

## Kritische Anmerkungen

- Briefing-Vorschau je Kanal entfällt ersatzlos: Vorab sieht niemand mehr das ganze Briefing, nur Mini-Vorschauen und Alarm-Vorschau bleiben.
- Zusätzlich zum Ticket: Speicher-Fehler wird mitbehoben und Vorschau-Schnittstelle im Server gelöscht; breiter Umbau, mittleres bis hohes Risiko.

## Freigabe-Frage

Soll die Briefing-Vorschau je Kanal ersatzlos entfallen, obwohl Nutzer das Briefing dann nirgends mehr vorab sehen können?
