---
spec_file: docs/specs/fast/fix-2612-gpx-upload-id.md
spec_sha256: 1247fd894439d53b3f7c7581edcd7022a9191b41bdd4785c4c6a98c8a5a6a925
spec_frozen_sha256: 4a99b6f77cdc978fb13571d1900e2086fcee1377453c4010b2f88931eb887c8e
---

# PO-Briefing: fix-2612-gpx-upload-id

- **Spec:** docs/specs/fast/fix-2612-gpx-upload-id.md
- **Issue:** #2612
- **Erstellt:** 2026-11-02

## Was gebaut wird

Ein GPX-Upload ersetzt keinen vorhandenen Trip mit gleichem Namen mehr, sondern legt immer einen neuen Trip an.

## Definition of Done

Nach einem GPX-Upload mit dem Namen „GR20" gibt es zwei Trips „GR20", und der alte behält alle Etappen und Einstellungen.

## Wie geprüft wird

Automatische Tests belegen verschiedene Kennungen und die Namensprüfung; das Nicht-Überschreiben selbst wird nur im Staging-Test aus Nutzersicht nachgewiesen.

## Kritische Anmerkungen

- Wiederholte Uploads erzeugen Duplikate; eine Rückfrage „ersetzen?" gibt es bewusst nicht, passend zum normalen Anlegen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
