---
spec_file: docs/specs/modules/fix_1895_alarm_modus_rueckbau.md
spec_sha256: 168e4fefa6508bd5483ee1aa77c8e76460e6d8e05c2d3305263d7304ebe92adf
---

# PO-Briefing: fix-1895-alarm-absolut-modus

- **Spec:** docs/specs/modules/fix_1895_alarm_modus_rueckbau.md
- **Issue:** #1895
- **Erstellt:** 2026-09-21

## Was gebaut wird

Im Alarmregel-Editor verschwinden Modus-Auswahl „Änderung/Absolut/Beides“ und Absolut-Schwellenfeld; die Kanalzuordnung bleibt.

## Definition of Done

Editor zeigt keine Modus-Karten und kein Absolut-Feld mehr; neue Regeln starten als Änderungsregel; Kanalauswahl funktioniert weiter.

## Wie geprüft wird

Browser- und Bausteintests belegen das Verschwinden und die Kanal-Chips; Alarmversand und Server-Speicherung werden nicht getestet.

## Kritische Anmerkungen

- Δ-Schwelle und Zeitfenster bleiben sichtbar, lösen aber nichts aus — Ihr Zielsatz „nur Empfindlichkeitsstufe“ ist nicht erreicht.
- Ihre Entwurfs-ACs zu Kanal-Alarmversand und Datenerhalt beim Speichern sind nur im Editor-Speicher geprüft, nicht am Server.
- Ortsvergleich nutzt diesen Editor nicht (AC-4 ohne Test); neue Regeln starten mit Schwelle 20 statt 50.

## Freigabe-Frage

Genügt es, dass Δ-Schwelle und Zeitfenster vorerst sichtbar bleiben und neue Regeln mit Schwelle 20 starten?
