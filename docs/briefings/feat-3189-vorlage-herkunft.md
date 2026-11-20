---
spec_file: docs/specs/modules/feat_3189_vorlage_herkunft.md
spec_sha256: 8668f2175644e8b0b06b880ecd5a0c58d29523f75b4b7e942c3314e5dcc5359d
spec_frozen_sha256: a20650ed07f53a34f98b495501976beb82a66fed0f6190940c8c39fdfbe671ab
---

# PO-Briefing: feat-3189-vorlage-herkunft

- **Spec:** docs/specs/modules/feat_3189_vorlage_herkunft.md
- **Issue:** #3189
- **Erstellt:** 2026-11-20

## Was gebaut wird

Eigene Wetter-Vorlagen merken sich automatisch ihren Trip bzw. Orts-Vergleich und zeigen „eigene · aus <Name> gespeichert“, wenn keine Beschreibung existiert.

## Definition of Done

Auf Staging gespeicherte Vorlagen ohne Beschreibung zeigen aus Trip und Orts-Vergleich sofort ohne Neuladen „eigene · aus <Name> gespeichert“; Bestandsvorlagen bleiben gültig.

## Wie geprüft wird

Go-Tests, Frontend-Tests und ein Browser-Test auf Staging belegen jede Anforderung; ob die Unterzeile gefällt, beurteilt nur der PO.

## Kritische Anmerkungen

- Python-Teil („Python-DTO“) aus dem Ticket entfällt, weil dort keine Vorlagen gespiegelt werden; für Nutzer ohne Folge.
- Name bleibt eingefroren: Umbenennen oder Löschen des Trips ändert die Unterzeile nicht; Bestandsvorlagen erhalten keine Herkunft.
- Besitzer-Einträge: laut Spec keine mehr vorhanden, passend zur PO-Entscheidung nach #3151; nichts zu übernehmen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
