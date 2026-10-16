---
spec_file: docs/specs/modules/onboarding_willkommen_checkliste.md
spec_sha256: f7dd80fe90c43bd347e36f0bf3064ea1177c5b8fd44c30c242a38c27469ad73e
spec_frozen_sha256: 9c0047faa6cfe7f27aeb2e5435c7e81e42ecac8e6d2d037700408343694dac60
---

# PO-Briefing: feat-2521-s2-willkommen

- **Spec:** docs/specs/modules/onboarding_willkommen_checkliste.md
- **Issue:** #2521
- **Erstellt:** 2026-10-16

## Was gebaut wird

Neue Nutzer sehen Willkommen und Startklar-Checkliste, können eine Testmail senden; „+ Neuer Vergleich" führt zum Anlegen.

## Definition of Done

Neuer Nutzer sieht Willkommen, bekommt Testmail an seine Adresse; Bestandsnutzer sehen nichts; Checkliste endet nach erstem planmäßigen Briefing.

## Wie geprüft wird

Tests prüfen Sichtbarkeit, Nutzertrennung, Mailempfänger und Link; echte Zustellung und erstes Briefing sind auf Staging nur eingeschränkt messbar.

## Kritische Anmerkungen

- Testmail nutzt für echte Nutzer den echten Versandweg; löst eine frühere freigegebene Regel ab (neues ADR).
- Zusatz: „Ausblenden" versteckt die Checkliste trotz offener Punkte; Issue verlangte „sichtbar bis erledigt".

## Freigabe-Frage

Sollen nur neu angelegte Nutzer Willkommen und Checkliste samt echter Testmail an ihre Adresse bekommen?
