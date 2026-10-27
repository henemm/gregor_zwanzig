---
spec_file: docs/specs/modules/fix_1405_s1_alarm_zustellung.md
spec_sha256: e546bfbece141f3abcb00e3122b7bfd3af4c9a9c16f71a64bef32bbed9a82fb3
---

# PO-Briefing: fix-1405-s1-alarm-zustellung

- **Spec:** docs/specs/modules/fix_1405_s1_alarm_zustellung.md
- **Issue:** #1405
- **Erstellt:** 2026-10-09

## Was gebaut wird

Ein Alarm gilt nur noch als gesendet, wenn ein Kanal wirklich zugestellt hat; sonst wird nach 30 Minuten erneut versucht.

## Definition of Done

Bei Totalausfall wird derselbe Alarm höchstens alle 30 Minuten wiederholt; "report" meldet nur bei echtem Versand Erfolg.

## Wie geprüft wird

Echte Versandklassen gegen Fake-Server prüfen Ausfall, Teilerfolg, Sperre und Wartezeit; reale Ankunft beim Empfänger beweist das nicht.

## Kritische Anmerkungen

- Kein Wiederholungsdeckel: bei Dauerausfall bis zu 48 Versuche täglich, bei unklarem Fehlschlag bis zu 48 Dubletten.
- Neu: Alarm, der nur am SMS-Tageslimit scheitert, gilt als erledigt und wird nie nachgeholt.
- Zwei Regen-Alarme gleicher Art, höchstens 30 Minuten auseinander, gelten als ein Ereignis; der zweite kann 30 Minuten warten.

## Freigabe-Frage

Soll ein komplett gescheiterter Alarm alle 30 Minuten ohne Obergrenze wiederholt werden, auch auf Risiko doppelter Nachrichten?
