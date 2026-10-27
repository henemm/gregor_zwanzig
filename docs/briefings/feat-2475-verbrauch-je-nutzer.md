---
spec_file: docs/specs/modules/forecast_budget_verbrauch_je_nutzer.md
spec_sha256: 6a35c332eadceaa4b0711a686ef63b73fdc375aaa4014c701f3b63feb342152c
---

# PO-Briefing: feat-2475-verbrauch-je-nutzer

- **Spec:** docs/specs/modules/forecast_budget_verbrauch_je_nutzer.md
- **Issue:** #2475
- **Erstellt:** 2026-10-01

## Was gebaut wird

Administratoren sehen, wie viele Wetterabrufe jeder Nutzer heute verbraucht hat; der Scheduler-Status zeigt nur anonyme Summenzahlen.

## Definition of Done

Die Admin-Seite zeigt je Nutzer die heutigen Abrufe in einer Spalte „Verbrauch"; der Scheduler-Status enthält vier Zahlen ohne Nutzerbezug.

## Wie geprüft wird

Tests belegen richtige Zahl je Nutzer, Null bei fehlenden Daten und Admin-Schutz; echter Browser und Live-Betrieb werden nicht geprüft.

## Kritische Anmerkungen

- Abweichung vom Ticket: Nutzerbezug steht nicht im Scheduler-Status, sondern nur im Admin-Bereich; der Status zeigt nur anonyme Zahlen.
- Der „faire Anteil" im Status ist nur eine Anzeigerechnung; ob gedrosselt wird, entscheidet weiter Python.
- Nur heutige Open-Meteo-Abrufe; keine Historie, keine Kosten in Euro (das ist #1702).

## Freigabe-Frage

Genügt es für Ticket #2475, dass Nutzerzahlen nur im Admin-Bereich stehen und der Scheduler-Status nur anonyme Kennzahlen zeigt?
