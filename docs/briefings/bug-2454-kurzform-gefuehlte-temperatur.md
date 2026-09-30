---
spec_file: docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md
spec_sha256: 11f544926f2a665b9669a4320b44f84abd7e83b12658a3a297741175554e28d7
---

# PO-Briefing: bug-2454-kurzform-gefuehlte-temperatur

- **Spec:** docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md
- **Issue:** #2454
- **Erstellt:** 2026-09-28

## Was gebaut wird

Kurzform-Nachrichten (SMS, Premium-SMS, Telegram) zeigen künftig gewählte gefühlte Temperatur an; zudem entfällt im Trip-Kontext das Kürzel „TF".

## Definition of Done

Wer im Editor gefühlte Temperatur wählt und speichert, bekommt Tag-/Nachtwerte in der Kurzform; belegt am Trip KHW 403 per Premium-SMS.

## Wie geprüft wird

Tests prüfen Editor, Speicherung und Kurzform-Text automatisiert; Zustellung und Bereinigung der echten Daten nur manuell nachgewiesen.

## Kritische Anmerkungen

- Ohne diese Zusatzregel bleibt der Fehler bei frisch gewählten Werten bestehen; eine bewusst abgewählte Zeile kann später zurückkommen.
- Eine Datenbereinigung ändert echte Bestandsdaten, auch Ihren Trip KHW 403; eng begrenzt auf das Fehlermuster.
- Telegram-Kurzform mit abweichender Spaltenauswahl bleibt defekt, wird separat in Issue #2455 behandelt.

## Freigabe-Frage

Sollen die automatische Werte-Mitnahme und die Bereinigung der eingefrorenen Einträge (heute nur KHW 403) freigegeben werden?
