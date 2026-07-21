# Spec: Bug #484 — Dropdown-Menü per bits-ui Portal fixieren

- **Issue:** #484
- **Workflow:** fix-484-dropdown-portal
- **Datum:** 2026-05-31

## Problem

Das "⋯"-Aktionsmenü in der Trip-Liste (`/trips`) wird unten abgeschnitten.
Ursache: Das Dropdown (`position: absolute; top: 100%`) liegt innerhalb von zwei
verschachtelten `overflow-x-auto`-Containern. Per CSS-Spec erzwingt `overflow-x: auto`
auch `overflow-y: auto` — die Container schneiden das Dropdown vertikal ab.

Betroffene Container:
- `frontend/src/routes/trips/+page.svelte:377` — äußerer Wrapper `overflow-x-auto`
- `frontend/src/lib/components/ui/table/table.svelte:13` — Table-Container `overflow-x-auto`

## Lösung

Ersetze das händisch gebaute Dropdown durch `bits-ui` `DropdownMenu` (bereits installiert:
`bits-ui: ^2.17.3`). Das Komponenten-System rendert via Portal in `<body>` und positioniert
via Floating UI — entkommt allen overflow-Containern ohne manuelle JS-Berechnung.

## Scope

Nur `frontend/src/routes/trips/+page.svelte`. Keine anderen Dateien außer ggf.
einem neuen Import. Keine Backend-Änderungen.

## Acceptance Criteria

**AC-1:** Given die Trip-Liste hat mindestens einen Trip / When der User auf "⋯" klickt /
Then erscheint das vollständige Dropdown (alle 6 Einträge: Bearbeiten, Test-Briefing Morgen,
Test-Briefing Abend, Wetter-Konfiguration, Report-Konfiguration, Löschen) ohne Abschneiden.

**AC-2:** Given das Dropdown ist offen / When der User außerhalb klickt oder Escape drückt /
Then schließt das Dropdown (Schließ-Verhalten erhalten).

**AC-3:** Given das Dropdown ist offen / When der User einen Eintrag klickt /
Then wird die jeweilige Aktion ausgeführt und das Dropdown schließt (alle 6 Aktionen intakt).

**AC-4:** Given die Trips-Tabelle auf einem kleinen Desktop-Fenster / When das Dropdown
den unteren Viewport-Rand erreichen würde / Then klappt es nach oben auf (Floating UI
Flip-Verhalten, automatisch durch bits-ui).

## Nicht im Scope

- Mobile Action-Sheet (existierender `trip-action-sheet` bleibt unverändert)
- Andere Seiten (`/locations`, `/subscriptions` — nutzen keine Dropdowns)
- Table-Komponente selbst (`table.svelte` — `overflow-x-auto` bleibt für korrekte horizontale Scrollbar)
