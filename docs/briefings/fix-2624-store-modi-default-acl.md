---
spec_file: docs/specs/modules/store_dateimodi_default_acl.md
spec_sha256: 6e9bc759964f29a165f9cc1ce941f0db7d5bda8440d44457632221f5ec33774d
spec_frozen_sha256: 8fc0d7a0965932089a858d84b8d0cb92e1368ef441a76bdc90a2402a2b0ad4f2
---

# PO-Briefing: fix-2624-store-modi-default-acl

- **Spec:** docs/specs/modules/store_dateimodi_default_acl.md
- **Issue:** #2624
- **Erstellt:** 2026-10-27

## Was gebaut wird

Neu angelegte Nutzerkonten bleiben für die Dienstgruppe beschreibbar, weil Ordner und Dateien künftig gruppenschreibbar entstehen.

## Definition of Done

Ein neu registriertes Staging-Konto ist für den Dienstbenutzer beschreibbar, der Datenrechte-Wächter meldet nichts, und auf Prod öffnet sich kein zusätzlicher Zugriff.

## Wie geprüft wird

Automatische Tests prüfen Rechte neu angelegter Dateien und Ordner bei strenger Umask; die echte Wirkung unter Zugriffsliste zeigt erst die Staging-Messung.

## Kritische Anmerkungen

- Über das Ticket hinaus: Python-Sperrdateien, Scheduler, Einladungen, Telegram-Token, Wetter-Cache und neues Hilfspaket werden mitgezogen; größerer Prüfaufwand.
- Zugriffslisten-Test wird ohne passendes Dateisystem übersprungen; dann schützen nur Modus-Tests, die eigentliche Wirkung prüft allein Staging.
- Staging-Abnahme kann als „nicht messbar" enden.

## Freigabe-Frage

Soll die Rechte-Korrektur wie beschrieben, einschließlich der zusätzlich mitgezogenen Python- und Scheduler-Dateien, umgesetzt werden?
