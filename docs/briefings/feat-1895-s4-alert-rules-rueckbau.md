---
spec_file: docs/specs/modules/feat_1895_s4_alert_rules_rueckbau.md
spec_sha256: 0afd8fcf6e1ecc06deacfba6c5fe2f7c7a9a76a5e0b7d13e016deb286b26bf71
spec_frozen_sha256: 77656022c43fce4e72cfbe3197d4cdf665305262a75c8ef279fa28b12acc3bb6
---

# PO-Briefing: feat-1895-s4-alert-rules-rueckbau

- **Spec:** docs/specs/modules/feat_1895_s4_alert_rules_rueckbau.md
- **Issue:** #1895
- **Erstellt:** 2026-11-05

## Was gebaut wird

Ungenutzte, alte Alarm-Bedienelemente und eine ungenutzte Hilfsfunktion werden gelöscht; für Nutzer ändert sich nichts.

## Definition of Done

Die Alarme-Reiter auf allen vier Flächen sehen und funktionieren wie vorher, und der gelöschte Code ist nicht mehr auffindbar.

## Wie geprüft wird

Bestehende Tests und Importversuche belegen die Löschung; ob der Reiter unverändert aussieht, zeigt nur eine manuelle Sichtprüfung auf Staging.

## Kritische Anmerkungen

- Das Ticket verlangt Rückbau der Alarm-Regeln; geliefert wird nur toter Code, Regeln und Speicherung bleiben bis Ticket #2793.
- Das Ticket #1895 würde trotzdem geschlossen, obwohl die Alarm-Regeln weiter geschrieben und gelesen werden.

## Freigabe-Frage

Soll #1895 mit diesem reinen Aufräumen als erledigt gelten, obwohl der eigentliche Regel-Rückbau erst in #2793 erfolgt?

## Ampel

Ampel: rot
