---
spec_file: docs/specs/modules/fix_2361_abruf_zeitlimit.md
spec_sha256: 0c68636d1d05effdd88fd54f65f33b2439d7114a9d820b848601ec53c19a2e4c
spec_frozen_sha256: ac4fb1ecf6950b1c718562098d052636b8ed472aedfb0a63a51cfac15dd76b3e
---

# PO-Briefing: fix-2361-abruf-zeitlimit

- **Spec:** docs/specs/modules/fix_2361_abruf_zeitlimit.md
- **Issue:** #2361
- **Erstellt:** 2026-10-17

## Was gebaut wird

Jeder App-Abruf bricht nach 25 Sekunden ab und meldet Verbindungsstörung, statt minutenlang stumm zu hängen.

## Definition of Done

Bei toter Verbindung zeigt die App nach etwa 25 Sekunden „offline“ und entsperrt sich nach Rückkehr selbst.

## Wie geprüft wird

Automatische Tests simulieren Funkloch, langsame Antworten und Speicherkonflikt mit verkürztem Limit; echtes Mobilfunknetz wird nicht getestet.

## Kritische Anmerkungen

- Nicht verlangt: Im Offline-Zustand prüft die App alle 15 Sekunden selbst die Verbindung.
- Langsame Verbindung kann die Oberfläche sperren; Versand, Export und Uploads bleiben ohne Zeitlimit.
- Fünf Aktionen bekommen Sonderlimits von 40–130 Sekunden; Wiederholung gibt es bewusst nicht.

## Freigabe-Frage

Soll die App nach 25 Sekunden Funkloch sperren und sich per automatischer Verbindungsprüfung selbst freigeben?
