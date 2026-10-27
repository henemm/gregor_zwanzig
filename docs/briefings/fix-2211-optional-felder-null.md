---
spec_file: docs/specs/bugfix/optional_felder_null_leert.md
spec_sha256: 47539c11670a18b3b17cc14287ee751403d5338d162afd2a52f8c92b70e3003f
---

# PO-Briefing: fix-2211-optional-felder-null

- **Spec:** docs/specs/bugfix/optional_felder_null_leert.md
- **Issue:** #2211
- **Erstellt:** 2026-10-03

## Was gebaut wird

Geleerte Alarm-Pause und Ruhezeit bleiben bei Trip und Ortsvergleich nach dem Speichern leer, statt den alten Wert zurückzubekommen.

## Definition of Done

Nach Leeren und Speichern zeigt der Abruf von Trip und Ortsvergleich keinen Wert mehr; ungeänderte Felder bleiben erhalten.

## Wie geprüft wird

Automatische Tests prüfen Leeren, Behalten und Setzen samt Zwei-Nutzer-Trennung; Staging-Durchklicken im Alarme-Reiter ist vorgesehen, aber kein automatischer Test.

## Kritische Anmerkungen

- Zusatz: Der Ortsvergleich ist mit eingebaut, das Issue nennt nur Trips.
- Leeres Alarm-Pause-Feld bedeutet Standard 120 Minuten, nicht „keine Pause".
- Halbes Ruhezeit-Paar wird gespeichert, aber als „keine Ruhezeit" gelesen.

## Freigabe-Frage

Soll Leeren bedeuten, dass der Standard gilt (120 Minuten Pause, keine Ruhezeit), und das auch für Ortsvergleiche umgesetzt werden?
