---
spec_file: docs/specs/modules/trip_schema_drift_gate.md
spec_sha256: 0ff8d50483438581bb15b3d76df1adc2293a2ffc3146ac74c2cf5fad523adde6
---

## Was gebaut wird

Zwei Tests (Python und Go) lesen dieselbe voll ausgefüllte Beispiel-Trip-Datei und melden Alarm, wenn ein Feld von Trip, Etappe oder Wegpunkt nur in einem Teil existiert. Der Go-Teil lernt zudem `suggestion_reason`, damit es beim Speichern nicht verloren geht.

## Definition of Done

- Beide Tests laufen grün, offline.
- `suggestion_reason` bleibt im Go-Teil erhalten.
- Ein einseitiges Testfeld macht den anderen Test rot, mit Feldname.

## Wie geprüft wird

Die Beispieldatei läuft durch den echten Lese- und Schreibweg. Ein Prüfer baut je ein Feld nur in Python bzw. Go ein; beides muss rot werden.

## Kritische Anmerkungen

- Umfang offen: Es können weitere einseitige Felder auftauchen.
- Listen werden weiter komplett ersetzt; das Gate verhindert nur neue Abweichungen.
- Ein in beiden Teilen vergessenes Feld bleibt unentdeckt.

## Freigabe-Frage

Genügt ein Test-Gate statt geänderter Speicherlogik?
