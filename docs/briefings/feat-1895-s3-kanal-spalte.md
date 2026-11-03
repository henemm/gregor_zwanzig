---
spec_file: docs/specs/modules/alert_metric_channels.md
spec_sha256: bb9e710729e597ca5356172eac8b8431eb19e6b4ff87693c927faf80636a45b8
spec_frozen_sha256: e1c643c83d3ebf590700945f1b0ccfd421bd0a0b549df06924f51f186217663a
---

# PO-Briefing: feat-1895-s3-kanal-spalte

- **Spec:** docs/specs/modules/alert_metric_channels.md
- **Issue:** #1895
- **Erstellt:** 2026-11-03

## Was gebaut wird

Alarme erreichen auch bei gesperrtem Kanal immer jemanden; die technische Grundlage für die spätere Kanalwahl je Wettergröße entsteht.

## Definition of Done

Ein Alarm mit nur gesperrtem Wunschkanal geht per Abo-Kanal raus, die Schlüsselliste ist abrufbar, und Ortsvergleich-Kanalwahl geht nicht mehr verloren.

## Wie geprüft wird

Automatische Tests prüfen Versand, Schlüsselliste, Datenerhalt und zwei Nutzer; die sichtbare Oberfläche wird nicht geprüft, weil sie fehlt.

## Kritische Anmerkungen

- Nutzer sehen nichts Neues: die Kanal-Spalte selbst folgt erst in einer späteren Scheibe (S3b), nicht hier.
- Fehlender Empfänger und Kanal-Schwelle können einen Alarm weiterhin ausbremsen; nur als Restrisiko benannt, nicht behoben.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
