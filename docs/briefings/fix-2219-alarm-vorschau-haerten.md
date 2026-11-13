---
spec_file: docs/specs/modules/fix_2219_alarm_vorschau_haerten.md
spec_sha256: def8f3999fae9fa6589afe2a1d8fcb2833cddaf53beb9977647386024211e82e
spec_frozen_sha256: 40dbad91030bbd1ae977298bcb47cd560df2e0285de03e0863bdd7a4991998db
---

# PO-Briefing: fix-2219-alarm-vorschau-haerten

- **Spec:** docs/specs/modules/fix_2219_alarm_vorschau_haerten.md
- **Issue:** #2219
- **Erstellt:** 2026-11-13

## Was gebaut wird

Die Alarm-Vorschau meldet fehlerhafte Eingaben verständlich statt mit Absturz und zeigt den Beginn mit Wochentag wie der echte Versand.

## Definition of Done

Auf Staging liefern die vier Fehleingaben eine lokalisierte Fehlermeldung statt Absturz, gültige Aufrufe funktionieren unverändert, und die Replay-Vorschau zeigt Beginn und Ende mit Wochentag.

## Wie geprüft wird

Automatische Tests rufen die Vorschau echt auf und belegen alle 13 Kriterien; der echte Alarmversand wird nur durch unveränderte Bestandstests abgesichert.

## Kritische Anmerkungen

- Beginn-Befund C5-18 (falsche Zeitzone) ist laut Spec widerlegt: kein Fix, nur Schutztest. Das Ticket verlangte einen Fix.
- Fehlerhafte Eingaben werden abgelehnt (422), nicht repariert; der Renderer selbst bleibt unverändert, auch bei „0 h früher".
- Verschiebungs-Untergrenze gilt stufenunabhängig; Vorschau kann Verschiebungen zeigen, die der Versand bei strenger Stufe nicht melden würde.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
