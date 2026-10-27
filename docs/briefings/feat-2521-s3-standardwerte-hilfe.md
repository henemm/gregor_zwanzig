---
spec_file: docs/specs/modules/onboarding_standardwerte_hilfe.md
spec_sha256: e05df0023e250882bebb09cd9312bc286a769880089cac0c602394b133114b8c
spec_frozen_sha256: 33a5640a6990a0bfac636356d320d0b6a5d767688637bd34ad6a083d4b56d0a9
---

# PO-Briefing: feat-2521-s3-standardwerte-hilfe

- **Spec:** docs/specs/modules/onboarding_standardwerte_hilfe.md
- **Issue:** #2521
- **Erstellt:** 2026-10-17

## Was gebaut wird

Trip und Ortsvergleich bekommen den Knopf „Mit Standardwerten speichern", dazu eine Hilfeseite „So funktioniert Gregor".

## Definition of Done

Mit Standardwerten Gespeichertes gleicht dem Durchklicken aller Reiter; Hilfeseite öffnet sich über Checkliste, Seitenleiste und Konto-Menü.

## Wie geprüft wird

Tests prüfen Knopf-Freigabe, Texte und Befehlsliste automatisch; Gleichheit zum Durchklicken und kein Doppel-Trip beweist erst der Staging-Lauf.

## Kritische Anmerkungen

- Änderung seit Freigabe: Alarm-Erklärtext im Ortsvergleich bleibt, weil korrekt; nur der Wertebereiche-Text wird korrigiert.
- Gleichheit zum Durchklicken: Kerntest nur wahlweise, sonst Staging; Lücke möglich.
- Telegram-Versand bleibt im Trip aus, Telegram-Alarm an; bewusst nicht behoben.

## Freigabe-Frage

Soll der Knopf samt Hilfeseite und dem korrigierten Alarm-Hinweis so gebaut werden?
