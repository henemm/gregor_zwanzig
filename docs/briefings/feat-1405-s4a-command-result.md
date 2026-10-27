---
spec_file: docs/specs/modules/feat_1405_s4a_befehlsantwort_erfolg_wirkung.md
spec_sha256: 13ce028e2e14193b83706f7f76e9f048da2d0d9d0c90d499ceea73074941453d
---

# PO-Briefing: feat-1405-s4a-command-result

- **Spec:** docs/specs/modules/feat_1405_s4a_befehlsantwort_erfolg_wirkung.md
- **Issue:** #1405
- **Erstellt:** 2026-10-14

## Was gebaut wird

Befehlsantworten per Mail, SMS, Premium-SMS und Telegram melden Erfolg nur, wenn der Befehl wirklich gewirkt hat.

## Definition of Done

Bei gesperrtem Trip, Wetterausfall oder Programmfehler antwortet jeder Kanal ehrlich „nicht ausgeführt“ oder „keine Daten“ statt Erfolg oder Schweigen.

## Wie geprüft wird

Tests senden Befehle über die echten Eingänge aller Kanäle und prüfen die ankommende Antwort; echte Zustellung folgt erst auf Staging.

## Kritische Anmerkungen

- Zusatz: Bei Programmfehlern gibt es neu eine Fehlermeldung — nicht verlangt, betrifft aber alle Befehle.
- Abweichung: Hilfe und Status melden bewusst weiter immer Erfolg; nur 18 der 21 Funde werden repariert.

## Freigabe-Frage

Gibst du frei, dass Befehlsantworten künftig ehrlich Fehler melden, inklusive neuer Fehlermeldung bei Programmfehlern?
