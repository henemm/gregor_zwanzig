---
spec_file: docs/specs/modules/fix_3193_vorlage_abweichung_minimal.md
spec_sha256: 3d4b4173a89ff8c08bebfc4aff321b452c8efa2e0a83f1ac835010899df9bc0b
spec_frozen_sha256: 2681fee076ab5ce696257df6725a194a15cc0da7e8d8da6156785f740bc81bca
---

# PO-Briefing: fix-3193-vorlage-abweichung-minimal

- **Spec:** docs/specs/modules/fix_3193_vorlage_abweichung_minimal.md
- **Issue:** #3193
- **Erstellt:** 2026-11-20

## Was gebaut wird

Nach Übernehmen oder Zurücksetzen einer Vorlage zeigt und speichert der Reiter Wetter keine scheinbaren Abweichungen mehr.

## Definition of Done

Nach Übernehmen oder Zurücksetzen steht überall „unverändert“, der Zurücksetzen-Knopf verschwindet, und die Staging-Prüfungen für Trip und Orts-Vergleich laufen grün.

## Wie geprüft wird

Neue automatische Tests je Trip und Vergleich für alle Vorlagen, dazu Bestandsdaten und die Staging-Prüfung; ausgeschaltete Metriken zählen weiter als Abweichung.

## Kritische Anmerkungen

- Das Issue nennt 16 rote Fälle; die Spec behandelt nur vier Prüfungen je Trip und Vergleich. Rest bleibt ungeklärt (Ticket-Text war mir nicht zugänglich).
- Alte Rausch-Einträge in gespeicherten Daten werden nicht migriert, sondern verschwinden erst beim nächsten Speichern.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
