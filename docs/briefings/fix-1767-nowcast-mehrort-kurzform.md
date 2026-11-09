---
spec_file: docs/specs/modules/fix_1767_nowcast_mehrort_kurzform.md
spec_sha256: ffb2fa8186c0e0eeb64df83d4082516791a16d80a32bf26e1fc42b09ce44bc0e
spec_frozen_sha256: 124f3af834177165ab62aff6e0a33d056edccc3a60a034ac10b9587e14140ab2
---

# PO-Briefing: fix-1767-nowcast-mehrort-kurzform

- **Spec:** docs/specs/modules/fix_1767_nowcast_mehrort_kurzform.md
- **Issue:** #1767
- **Erstellt:** 2026-11-09

## Was gebaut wird

Bei Regen-Anmarsch an mehreren Orten nennen SMS, Premium-SMS und Telegram alle betroffenen Orte statt nur den ersten.

## Definition of Done

Ein Alarm für zwei Orte liefert auf allen Kanälen beide Orte mit eigener Zeit, bei Platzmangel mit "+k", und Staging sowie Produktion bestehen.

## Wie geprüft wird

Tests senden echte Alarme über alle Kanäle und die Vorschau, auch auf Englisch und mit 20 Orten; reale Handy-Zustellung wird nicht geprüft.

## Kritische Anmerkungen

- Reihenfolge der Orte nach frühestem Beginn ist neu (Tech-Lead-Wahl, nicht verlangt) und ändert auch die E-Mail-Reihenfolge.
- Der frühere PO-Entscheid "nur führender Ort" aus #1948 wird ausdrücklich abgelöst und dokumentiert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
