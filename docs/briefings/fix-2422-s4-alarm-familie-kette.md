---
spec_file: docs/specs/modules/fix_2422_s4_alarm_familie_kette.md
spec_sha256: ae0e9b21fc804c1c9585e125bc100bcd0f69f76a5a97639ea2ff24667e258cfb
---

# PO-Briefing: fix-2422-s4-alarm-familie-kette

- **Spec:** docs/specs/modules/fix_2422_s4_alarm_familie_kette.md
- **Issue:** #2422
- **Erstellt:** 2026-09-29

## Was gebaut wird

Zwei echte Alarm-Fehler werden behoben, und Schwellen/Radar/amtliche Warnungen werden gegen alle vier Kanäle geprüft.

## Definition of Done

Ein Trip, der amtliche Warnungen aktiviert hat, bekommt sie wirklich zugestellt; die SMS nennt amtliche Warnungen künftig auch kurz.

## Wie geprüft wird

Automatisierte Tests spielen reale gespeicherte Trip-Daten durch die Alarm-Logik; sie prüfen nicht den Vergleichs-Ortsalarm, der ausgeklammert bleibt.

## Kritische Anmerkungen

- Zwei echte Alarm-Fehler in Produktion werden hier repariert — das ist mehr als nur zusätzliche Tests.
- Alarme beim Ortsvergleich (Radar, amtliche Warnungen) bleiben ungeprüft, nur als spätere Aufgabe vermerkt.
- Der genaue SMS-Hinweistext zur amtlichen Warnung ist noch nicht festgelegt, nur dass einer kommt.

## Freigabe-Frage

Sollen die zwei gefundenen Fehler (amtliche Warnung wird übersprungen, SMS ohne Hinweis) in dieser Scheibe sofort behoben werden?
