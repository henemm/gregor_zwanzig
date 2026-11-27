---
spec_file: docs/specs/modules/fix_3458_alarm_vorschau_entfernen.md
spec_sha256: d70f5225560f2255ce4ab184384b38b7327c1f3617d0cafe725e715b1d029474
spec_frozen_sha256: 2b299e696fd55c5a37becd472bd5e5d07bed6c1a5b043209751f056bc5545208
---

# PO-Briefing: fix-3458-alarm-vorschau-entfernen

- **Spec:** docs/specs/modules/fix_3458_alarm_vorschau_entfernen.md
- **Issue:** #3458
- **Erstellt:** 2026-11-27

## Was gebaut wird

Die Alarm-Vorschau (Beispiel-Alarm, Beispiel-Warnung, „Vorschau laden“) verschwindet; Beispiel-Alarme gibt es nur noch über „Test schicken“.

## Definition of Done

In Trip und Orte (Hub und Anlegen) fehlen Beispiel-Alarm, Beispiel-Warnung und „Vorschau laden“, deutsch wie englisch; „Test schicken“ bietet weiter den Test-Alarm.

## Wie geprüft wird

Neue Render-Tests und umgedrehte Bestandstests belegen die Abwesenheit; die Server-Schnittstelle der Vorschau bleibt unverändert und wird weiter geprüft.

## Kritische Anmerkungen

- Statt „anpassen“ entfallen sieben Testdateien und vier Browser-Fälle ersatzlos, weil sie nur die Vorschau prüften; Gründe stehen in der Spec.
- Server-Schnittstellen der Vorschau bleiben ohne Oberfläche bestehen, wie im Ticket verlangt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
