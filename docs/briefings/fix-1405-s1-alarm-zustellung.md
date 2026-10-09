---
spec_file: docs/specs/modules/fix_1405_s1_alarm_zustellung.md
spec_sha256: d5055fd0d3bfe4421ae3f2c10a9fad6c2366ca01d00c1200f321b29e35b5d1fb
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

- Kein Wiederholungsdeckel: bei Dauerausfall bis zu 48 Versuche täglich, bei unklaren Fehlschlägen bis zu 48 doppelte Alarme.
- Neu: Alarme, die nur am SMS-Tageslimit scheitern, gelten endgültig als erledigt und werden nie nachgeholt.
- "Zugestellt" heißt nur: Versandweg hat angenommen, nicht: Empfänger hat gelesen.

## Freigabe-Frage

Soll ein komplett gescheiterter Alarm alle 30 Minuten ohne Obergrenze wiederholt werden, auch auf Risiko doppelter Nachrichten?
