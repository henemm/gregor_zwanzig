---
spec_file: docs/specs/modules/fix_1981_alarm_abwahl_alt_vokabular.md
spec_sha256: cccbc20d255bff3a9300bf834209d71e15964c8d159d483dece252d55d548447
---

# PO-Briefing: fix-1981-alarm-abwahl-vokabular

- **Spec:** docs/specs/modules/fix_1981_alarm_abwahl_alt_vokabular.md
- **Issue:** #1981
- **Erstellt:** 2026-10-08

## Was gebaut wird

Im Ortsvergleich verstummt ein im Alarme-Reiter abgewählter Alarm auch dann, wenn die Abwahl in alter Schreibweise gespeichert ist.

## Definition of Done

Ein Ortsvergleich mit altem Eintrag „aus" für Temperatur, Böen oder Gewitter löst für diese Metrik keinen Alarm mehr aus, Editor zeigt „aus".

## Wie geprüft wird

Automatische Tests laden gespeicherte Vergleiche und prüfen die entstehenden Alarmregeln; echte Alarm-Zustellung auf Staging wird nicht geprüft.

## Kritische Anmerkungen

- Das Ticket nennt eine Auffüllung, die Abwahlen auf „Standard" zurücksetzt; die Spec behandelt sie nicht ausdrücklich, Abwahl könnte zurückkehren.
- Bisher feuernde Alarme verstummen; Zahl betroffener Vergleiche ist ungemessen, Daten waren nicht lesbar.
- Windchill-Einträge werden stillschweigend gelöscht; verlangt hat das niemand.

## Freigabe-Frage

Dürfen Alarme, die trotz gespeicherter Abwahl bisher kamen, künftig ausbleiben, und Windchill-Einträge dabei gelöscht werden?
