---
spec_file: docs/specs/modules/fix_1405_s4b_erfolg_heisst_wirkung.md
spec_sha256: dd8fac4ab01a0d0336a1a54f2c5e17310219c281da9b2fc27d45bbe373086e46
spec_frozen_sha256: a0a54471d915ba6b4e05a4065c4f6c68225aeece0591fb0aeb08b4036cfed3d8
---

# PO-Briefing: fix-1405-s4b-erfolg-heisst-wirkung

- **Spec:** docs/specs/modules/fix_1405_s4b_erfolg_heisst_wirkung.md
- **Issue:** #1405
- **Erstellt:** 2026-10-26

## Was gebaut wird

Das System meldet gescheiterte Briefings, Befehlsantworten und Postfach-Abrufe ehrlich auf der Statusseite, statt immer „ok“.

## Definition of Done

Die Liste bekannter Falschmeldungen ist leer, und die Statusseite zeigt bei gescheiterten Zustellungen „teilweise“ oder „Fehler“ statt „ok“.

## Wie geprüft wird

Tests lösen echte Fehler aus und prüfen Antwort und Statusseite; Versandtexte und Monitoring-Alarme werden nicht neu getestet.

## Kritische Anmerkungen

- Gescheiterte Hinweise bei zugestelltem Briefing zeigen nur „teilweise“; das Monitoring alarmiert das nicht.
- Postfach-Ausfall löst künftig Alarm aus; bisher blieb er stumm.
- Umfang groß: 27 Kriterien, Python und Go, Zeilenlimit wird überschritten.

## Freigabe-Frage

Sollen Fehler bei Hinweisen zugestellter Briefings nur „teilweise“ anzeigen, ohne Sofort-Alarm, und Postfach-Ausfälle künftig alarmieren?
