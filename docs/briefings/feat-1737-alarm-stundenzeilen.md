---
spec_file: docs/specs/modules/feat_1737_alarm_stundenzeilen.md
spec_sha256: 773028633af2151431c1ebd6587b8ed57e49aae816e6f0cf45c3842a2f63ce7c
spec_frozen_sha256: 4942b620c8ece328b5befcc47c7af77b96af007cfba7960d02734436e72e5539
---

# PO-Briefing: feat-1737-alarm-stundenzeilen

- **Spec:** docs/specs/modules/feat_1737_alarm_stundenzeilen.md
- **Issue:** #1737
- **Erstellt:** 2026-10-20

## Was gebaut wird

Der Abweichungsalarm zeigt je betroffener Stunde Uhrzeit und alten → neuen Wert, in derselben Darstellung wie das Briefing.

## Definition of Done

Eine Trip-Alarm-Mail zeigt je Stunde „14:00 | alt → neu" im Briefing-Stil; die SMS nennt die Zeitspanne.

## Wie geprüft wird

Tests prüfen die gerenderten Texte aller vier Kanäle mit aufgezeichneten Daten; sie beweisen nicht, ob die Mail verständlich wirkt.

## Kritische Anmerkungen

- Regen-Alarme (Radar) und amtliche Alarme bekommen keine Stundenzeilen; dort bleibt das „wann" offen.
- Ungefragt: höchstens 6 Zeilen je Ereignis, längere Bereiche werden gekürzt.

## Freigabe-Frage

Gibst du frei, dass der Abweichungsalarm Stundenzeilen mit Kappung auf 6 und nur Zeitspanne in der SMS bekommt?
