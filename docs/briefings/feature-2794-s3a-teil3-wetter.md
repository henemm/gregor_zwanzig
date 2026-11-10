---
spec_file: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
spec_sha256: 6983f1faa4996e74e2b6687cd84dd4454e4e9ec09344686b74b6fcb539a74b91
spec_frozen_sha256: 892669cb07da472e58c603b46dbbcf849bff0c515f0785360262a6a81db1916f
---

# PO-Briefing: feature-2794-s3a-teil3-wetter

- **Spec:** docs/specs/modules/feat_2794_s3a_teil3_wetter.md
- **Issue:** #2794
- **Erstellt:** 2026-11-10

## Was gebaut wird

Der Reiter Wetter für Trips und Orts-Briefings zeigt Metriken mit Ampel-Grenzen, Vorlagen und „Alarm ab“ nach dem Mockup.

## Definition of Done

Beide Reiter lassen sich bedienen, Einstellungen bleiben nach Neuladen erhalten, Alarme kommen passend zur gewählten Stufe, und alte Daten gehen nicht verloren.

## Wie geprüft wird

Automatische Tests und Browser-Läufe auf Staging mit zwei Nutzern prüfen jede Anforderung; das Aussehen gegen das Mockup bleibt Augenmaß.

## Kritische Anmerkungen

- Bewusst nicht enthalten: Standardvorlage beim Neuanlegen von Orts-Briefings wird erst im Folgeschritt vollständig; bis dahin fängt der Reiter es ab.
- Alte Reiter-Bausteine werden noch nicht gelöscht; Aufräumen folgt im nächsten Teilschritt, Issue bleibt offen.
- Beim Deploy muss die API kurz gestoppt werden (Datenmigration der Vorlagen).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
