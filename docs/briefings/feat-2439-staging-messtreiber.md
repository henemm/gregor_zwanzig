---
spec_file: docs/specs/modules/feat_2439_staging_messtreiber.md
spec_sha256: 76a13ecbd2a29b3784768fc0c01a36083e09c49d91001a7e092490d06576fab1
spec_frozen_sha256: 55a50aac389c03a63ef7fc07cc036beadf2ade25969a8b1036f0decdd2ab49f0
---

# PO-Briefing: feat-2439-staging-messtreiber

- **Spec:** docs/specs/modules/feat_2439_staging_messtreiber.md
- **Issue:** #2439
- **Erstellt:** 2026-10-21

## Was gebaut wird

Ein Werkzeug löst auf der Test-Umgebung automatisch die Befehlsserien aus, damit die Antwortzeiten von Wetterbefehlen gemessen werden können.

## Definition of Done

Das Werkzeug läuft ohne Abbruch durch, räumt Testdaten weg, und der vorhandene Antwortzeit-Test wird damit gegen die Test-Umgebung grün.

## Wie geprüft wird

Automatische Tests mit Attrappen prüfen den Ablauf; die echten Antwortzeiten zeigt erst der spätere Live-Lauf, nicht diese Tests.

## Kritische Anmerkungen

- Telegram wird nur bis zur Verarbeitung gemessen, nicht echte Zustellung; scheitert die Verknüpfung, bleibt dieser Teil offen.
- Annahme „Orte sind kalt“ ungeprüft; ist der Probelauf warm, bricht alles ab und Issue #2439 bleibt offen.
- Lauf dauert 2–2,5 Stunden; Erfolg heißt nur „ausgelöst“, nicht „Zielwerte erreicht“.

## Freigabe-Frage

Soll dieses Messwerkzeug gebaut werden, obwohl Telegram nur bis zur Verarbeitung gemessen wird?
