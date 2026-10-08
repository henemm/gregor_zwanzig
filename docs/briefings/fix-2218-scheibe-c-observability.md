---
spec_file: docs/specs/modules/fix_2218_scheibe_c_observability.md
spec_sha256: 2590db960ab4c094d8ba85d0252d42f86b7e5e88030099da9734ea8833559b01
---

# PO-Briefing: fix-2218-scheibe-c-observability

- **Spec:** docs/specs/modules/fix_2218_scheibe_c_observability.md
- **Issue:** #2218
- **Erstellt:** 2026-10-08

## Was gebaut wird

Mails, Alarme und Statusanzeige melden Ausfälle und Zustellungen nachprüfbar, statt still zu schweigen.

## Definition of Done

Jede versandte Mail hat eine im Log wiederfindbare Kennung, Staging zeigt Scheduler aus, Prod läuft, und die Tests der sechs Punkte sind grün.

## Wie geprüft wird

Automatische Tests prüfen 30 Kriterien an echten Mails, Dateien und Antworten; Zustellung im Postfach und die neuen Prod-Trigger bleiben unbewiesen.

## Kritische Anmerkungen

- Die vier neuen Alarm-Auslöser werden auf Prod nie ausprobiert; nur Routing-Tests belegen sie.
- Fenster-Protokoll und Ausfallmeldung gelten nur für Trip-Alarme, nicht für Ortsvergleich-Alarme.
- Mitschnitte bleiben 24 Stunden statt 50 Dateien; das belegt bis zu 256 MB Platz je Ordner.

## Freigabe-Frage

Ist die zusätzliche Mail-Kennung samt dem höheren Speicherverbrauch für die Alarm-Mitschnitte für dich so freigegeben?
