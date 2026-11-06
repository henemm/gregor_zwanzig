---
spec_file: docs/specs/modules/fix_2581_demo_cache_vergiftung.md
spec_sha256: b8a95e36d159d6b621981092039db6de9fb72be1410123e16f13e03da7db8853
spec_frozen_sha256: 6b98dd33930c3044ba578a3fc4e01528daeb33c418c6f1a340178b6e067d28ac
---

# PO-Briefing: fix-2581-demo-cache-vergiftung

- **Spec:** docs/specs/modules/fix_2581_demo_cache_vergiftung.md
- **Issue:** #2581
- **Erstellt:** 2026-11-06

## Was gebaut wird

Demo-Vorschau und echter Wetterabruf werden getrennt, damit Beispielwerte nie in echten Briefings oder Alarmen landen.

## Definition of Done

Ein Demo-Abruf liefert immer Beispielwerte, ein echter Abruf immer echte Werte, in beiden Reihenfolgen und ohne Zwischenspeicher zu leeren.

## Wie geprüft wird

Automatische Tests ohne Internet prüfen beide Reihenfolgen, zwei Nutzer, die Nachtprognose und das Archiv; echte Live-Wetterdaten werden nicht geprüft.

## Kritische Anmerkungen

- Zusatz zum Ticket: Auch das Prognose-Archiv wird vor Beispielwerten geschützt, ein zweiter Vergiftungsweg, den das Ticket nicht nannte.
- Folge: Der Offline-Testmodus schreibt künftig keine Archivzeilen mehr; das ist gewollt und betrifft keine echten Nutzer.
- Bereits im Archiv liegende Demo-Zeilen aus der Zeit vor dem Fix werden nicht bereinigt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
