---
spec_file: docs/specs/modules/fix_2982_onset_event_baustein.md
spec_sha256: 1b27e2cbc1d750008fa1504c58af60cf2b05d5dfdc6ae6de5532da05c17bdbca
spec_frozen_sha256: 561e63a1a915a6c4f5ac5ef6cc1cbd51d050e6b40eee17c8ac6fc108ecb4c6f5
---

# PO-Briefing: fix-2982-onset-event-baustein

- **Spec:** docs/specs/modules/fix_2982_onset_event_baustein.md
- **Issue:** #2982
- **Erstellt:** 2026-11-17

## Was gebaut wird

Der Beginn eines Regenalarms wird intern nur noch an einer Stelle zusammengesetzt, die Alarmtexte bleiben für Nutzer unverändert.

## Definition of Done

Alle Alarmtexte in E-Mail, Telegram, SMS und Premium-SMS sind für Trip, Ortsvergleich und Vorschau Zeichen für Zeichen identisch zu vorher.

## Wie geprüft wird

Automatische Tests vergleichen die Alarmtexte aller vier Kanäle mit dem eingefrorenen Stand und melden künftig vergessene Felder; ein Live-Alarm wird nicht ausgelöst.

## Kritische Anmerkungen

- Die Feldlisten im Trip-Versandpaket bleiben doppelt vorhanden; ein Prüftest bewacht sie nur, statt sie zu beseitigen.
- Die Vorschau zeigt weiterhin keine Etappennummer, keinen Abstand und kein "läuft bereits"; bewusst nicht angeglichen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
