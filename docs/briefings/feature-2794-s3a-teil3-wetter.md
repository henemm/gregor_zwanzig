---
spec_file: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
spec_sha256: 32edaab0a3473d00022b86c7ef72065b59a6632e1a26ab4194c2d9bf195551fc
spec_frozen_sha256: 475766a9c7061528bc9b392e5b5f51949dc6c8ea8fc36979b80292e07cbe8eb3
---

# PO-Briefing: feature-2794-s3a-teil3-wetter

- **Spec:** docs/specs/modules/feat_2794_s3a_teil3_wetter.md
- **Issue:** #2794
- **Erstellt:** 2026-11-10

## Was gebaut wird

Der Reiter Wetter für Trips und Orts-Briefings zeigt Metriken mit Ampel-Grenzen, Vorlagen und „Alarm ab“ nach dem Mockup.

## Definition of Done

Beide Reiter lassen sich bedienen, Einstellungen bleiben nach Neuladen erhalten, Alarme kommen passend zur gewählten Stufe, und Bestandsdaten gehen nicht verloren.

## Wie geprüft wird

Automatische Tests und Browser-Läufe auf Staging mit zwei Nutzern prüfen jede Anforderung; die Optik gegen das Mockup bleibt Augenmaß.

## Kritische Anmerkungen

- Alarm-Korrektur gilt nur für Abos mit gespeicherter Ampel; Bestandstrips ohne Ampel bleiben bewusst unverändert stumm.
- Alte Reiter-Bausteine und Standardvorlage beim Neuanlegen von Orts-Briefings folgen erst im nächsten Teilschritt; Issue bleibt offen.
- Beim Deploy muss die API kurz gestoppt werden (Vorlagen-Migration).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
