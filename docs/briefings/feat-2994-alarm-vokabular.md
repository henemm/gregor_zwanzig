---
spec_file: docs/specs/modules/feat_2994_alertable_metrics_vocab.md
spec_sha256: a0c36d21a3346cd1de96f096b439db72760404f947cad6aed78ce44c61c758d9
spec_frozen_sha256: 5db792521fd6e5f708f957320a3bedf85310d7f4e4d082129c15b2b6507c4880
---

# PO-Briefing: feat-2994-alarm-vokabular

- **Spec:** docs/specs/modules/feat_2994_alertable_metrics_vocab.md
- **Issue:** #2994
- **Erstellt:** 2026-11-27

## Was gebaut wird

Die Liste der alarmfähigen Wettermetriken wird nur noch an einer Stelle gepflegt; für Nutzer ändert sich nichts.

## Definition of Done

Alarmregeln und Zuordnung verhalten sich mit den sechs Metriken unverändert, und vergessene Neugenerierung oder fehlende Schwelle machen Tests sofort rot.

## Wie geprüft wird

Automatische Tests prüfen Generator, Fehlerfälle und die sechs Metriken; bestehende Alarmtests laufen unverändert weiter, echte Alarmzustellung wird nicht neu getestet.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
