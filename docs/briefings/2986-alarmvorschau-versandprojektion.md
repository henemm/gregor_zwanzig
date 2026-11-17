---
spec_file: docs/specs/modules/alert_channel_texts.md
spec_sha256: 4d5414d38bf253056fde79cdbc4dbc1f8a24df1fe194a11e2a03208bdbaecc1b
spec_frozen_sha256: 3ca05169d9ab5a7b3188f2240dc5fcfb8bd45319f360d28d5a4af1a695107967
---

# PO-Briefing: 2986-alarmvorschau-versandprojektion

- **Spec:** docs/specs/modules/alert_channel_texts.md
- **Issue:** #2986
- **Erstellt:** 2026-11-17

## Was gebaut wird

Alarm-Vorschau und echter Versand im Ortsvergleich bauen ihre Texte künftig aus einem gemeinsamen Baustein, sichtbar ändert sich nichts.

## Definition of Done

Vorschau und Zustellung zeigen auf allen Kanälen unverändert dieselben Texte, auch bei Trip-Alarmen, nachgewiesen auf Staging und nach dem Produktivgang.

## Wie geprüft wird

Automatische Tests vergleichen Vorschau und echten Versand Zeichen für Zeichen; absichtlich eingebaute Fehler müssen auffallen. Nicht geprüft: das Zeitzonen-Verhalten bei Delta-Alarmen.

## Kritische Anmerkungen

- Zeitzonen-Inkonsistenz bei Delta-Alarmen bleibt bewusst unverändert und liegt als eigenes Ticket vor; keine Entscheidung nötig.
- Trip-Alarme laufen über denselben Versandweg; Risiko mittel, durch bestehende Tests abgesichert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
