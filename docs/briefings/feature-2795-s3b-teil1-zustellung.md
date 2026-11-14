---
spec_file: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md
spec_sha256: 078bd6ee2c2eeb9175381bda078c81d05cd5557519c1b5182445af0c87cf291a
spec_frozen_sha256: c88ba33a5d389946d973a644099ebc9bce5b8a55ea3b2d2cdf88f0074d69ad8d
---

# PO-Briefing: feature-2795-s3b-teil1-zustellung

- **Spec:** docs/specs/modules/feat_2795_s3b_teil1_zustellung.md
- **Issue:** #2795
- **Erstellt:** 2026-11-12

## Was gebaut wird

Der Reiter Zustellung zeigt Briefing-Uhrzeiten (auch 06:45) und eine Kanal-Tabelle, über die Briefings und Alarme laufen.

## Definition of Done

Auf Staging und Produktion lässt sich 06:45 speichern und wird genau einmal um 06:45 versandt; Kanäle, Dringlichkeit, Stille Stunden funktionieren.

## Wie geprüft wird

Automatische Tests belegen jede Anforderung, ein Soll/Ist-Bild gegen das Mockup geht an dich; echtes Zustellen im Alltag bleibt ungeprüft.

## Kritische Anmerkungen

- Alarm-Sonderregeln je Wettergröße werden migriert: betroffene Alarme gehen künftig über alle Kanäle nach Dringlichkeit (dein Entscheid vom 12.11.).
- Ungültige Minuten (z. B. 06:50) werden abgelehnt statt gerundet; das ist eine technische Festlegung, nicht deine.
- Nicht verlangt, aber nötig: Versandtakt alle 15 Minuten; Oberfläche zeigt übergangsweise unfertigen Block.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
