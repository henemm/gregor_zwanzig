---
spec_file: docs/specs/modules/feat_2346_cockpit_paritaet.md
spec_sha256: 7b0ced54a9cef54e34713551bcf634650254b5e35741e52ea20491f61386af0b
spec_frozen_sha256: 104654c5adf5283201a9d378cee68aa29f3ad71b1a1a1df0f312e0176123250a
---

# PO-Briefing: feat-2346-s4-last-briefing

- **Spec:** docs/specs/modules/feat_2346_cockpit_paritaet.md
- **Issue:** #2346
- **Erstellt:** 2026-10-26

## Was gebaut wird

Die Trip-Kachel auf der Startseite zeigt den Zeitpunkt des letzten Versands statt „—", wie schon die Ortsvergleich-Kachel.

## Definition of Done

Beide Kacheln zeigen letzten und nächsten Versand aus einer Abfrage, nur eigene Daten; ohne bisherigen Versand steht „—".

## Wie geprüft wird

Automatische Tests prüfen Abfrage mit zwei Nutzern und Kachel-Zuordnung; das echte Aussehen auf Staging prüft nur ein Screenshot, kein Test.

## Kritische Anmerkungen

- Handversand zählt als letzter Versand, Alarme nicht; die Kachel zeigt also nicht zwingend das letzte planmäßige Briefing.
- Ein Logeintrag gilt als zugestellt; ob fehlgeschlagene Zustellungen dort stehen, belegt die Spec nicht.
- Alte Logeinträge ohne Zuordnung zählen pauschal als Trip-Versand.

## Freigabe-Frage

Gibst du S4 frei: letzter Versand auf der Trip-Kachel, Handversand zählt mit, Alarme nicht?
