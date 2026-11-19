---
spec_file: docs/specs/modules/feat_2969_elementliste_uebersicht.md
spec_sha256: 79fc00f2a9f956840b508a4ffa59210685015e70a1469fec5bf098dc013b5f8c
spec_frozen_sha256: ab3005ac111297411a38ed7b5082ca2a3104fc22a611725614f405cb27d0d4f8
---

# PO-Briefing: feat-2969-elementliste-uebersicht

- **Spec:** docs/specs/modules/feat_2969_elementliste_uebersicht.md
- **Issue:** #2969
- **Erstellt:** 2026-11-19

## Was gebaut wird

Der Seitenabgleich prüft künftig auch den Reiter Übersicht (Trip und Orte, Deutsch und Englisch) gegen das Mockup.

## Definition of Done

Der Abgleich läuft auf Staging für Deutsch und Englisch fehlerfrei durch, die Pauschal-Ausnahme für die Übersicht ist entfernt, die Oberfläche bleibt unverändert.

## Wie geprüft wird

Automatische Tests prüfen Liste, Ausnahmen und Erkennung unbekannter Texte; Staging-Läufe belegen den Abgleich, nur die Doku-Notiz hat keinen Test.

## Kritische Anmerkungen

- Das Mockup gestaltet nur Titel und Erklärsatz; der übrige Inhalt wird als heutiger Stand festgeschrieben, nicht aus dem Mockup erzeugt.
- Die Einzel-Ausnahmen entstehen erst beim Staging-Lesen; ändert sich der Übersichtsinhalt bewusst, müssen sie nachgezogen werden.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
