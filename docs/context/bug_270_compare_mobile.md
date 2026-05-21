# Context: Bug #270 — Compare-Screen ohne Locations-Rail auf Mobile

## Request Summary

Der `/compare`-Screen ist auf Mobile (≤ 899 px) nicht nutzbar: Die `LocationsRail` ist eine Desktop-Only-Sidebar (`md:flex`), auf Mobile unsichtbar — damit kann der Nutzer keine Locations auswählen und keinen Vergleich starten.

## Problem-Details

- `LocationsRail.svelte:84` — `class="hidden w-60 … md:flex"` versteckt die Rail vollständig auf Mobile
- `+page.svelte:234` — `<div class="flex gap-6">` zeigt nur Content, keine mobile Alternative
- `md:flex` ist der alte Tailwind-Breakpoint (768px), der aktuelle Standard ist `desktop:` / `mobile:` via `@custom-variant` in `app.css` (900px)
- Im PresetHeader (`PresetHeader.svelte`) sind die Location-Checkboxen für Desktop eingebettet — kein mobiles Äquivalent

## Erwartetes Verhalten (lt. Issue #270)

| Element | Mobile (≤ 899px) |
|---------|-----------------|
| Ausgewählte Locations | Horizontale Chip-Reihe oben |
| Locations hinzufügen/auswählen | "Orte wählen"-Button → Bottom-Sheet mit LocationsRail-Inhalt |
| Vergleichs-Matrix | H-Scroll mit sticky erster Spalte |
| Score-Karten Top-3 | Card-Stack über der Matrix |
| Desktop-Sidebar | Unverändert (≥ 900px) |

## Relevante Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/compare/+page.svelte` | Haupt-Orchestrierung; muss mobile Bottom-Sheet-State + Chip-Reihe ergänzen |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | `md:flex` → `desktop:flex` korrigieren; Inhalt im Bottom-Sheet wiederverwendbar |
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | H-Scroll + sticky erste Spalte auf Mobile fehlt |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | Locations-Zähler wird angezeigt; kein Eingriff nötig |
| `frontend/src/app.css` | `@custom-variant mobile` (≤ 899px), `desktop` (≥ 900px), `--g-paper-deep`, `--g-rule-soft` |

## Referenz-Pattern: Bottom-Sheet (Issue #268)

`frontend/src/routes/trips/+page.svelte:555–605`:
- Backdrop: `fixed inset-0 z-[70] bg-black/50 desktop:hidden`
- Panel: `fixed bottom-0 left-0 right-0 z-[75] desktop:hidden rounded-t-2xl border-t`
- Style: `background: var(--g-paper-deep); border-color: var(--g-rule-soft); padding-bottom: env(safe-area-inset-bottom)`
- Handle: `w-10 h-1 rounded-full bg-muted-foreground/25`

## Referenz-Pattern: Responsive-Breakpoints (Issue #267/#268)

- `desktop:hidden` = nur auf Mobile sichtbar
- `hidden desktop:flex` = nur auf Desktop sichtbar
- `mobile:` / `desktop:` Variants sind in `app.css:49–50` definiert

## Abhängigkeiten

- **Upstream:** `LocationsRail.svelte` (Locations-Liste, Suche, Chip-Filter) — Inhalt kann im Bottom-Sheet wiederverwendet werden
- **Downstream:** `CompareMatrix.svelte` muss H-Scroll + sticky erhalten; keine Backend-Änderungen

## Bestehende Specs

- `docs/specs/modules/issue_249_locations_rail.md` — LocationsRail-Spezifikation
- `docs/specs/modules/issue_251_compare_main_stage.md` — Compare-Screen-Spezifikation (Desktop)

## Risiken

- `LocationsRail` aktuell monolithisch (Presentational, Props aus Page) — Bottom-Sheet kann denselben Props-Interface nutzen, kein Refactoring nötig
- `CompareMatrix` hat `overflow-x-auto` bereits; sticky braucht `position: sticky; left: 0` + `background`-Sicherung
- `md:flex` → `desktop:flex` — der Bruch liegt bei 900px statt 768px; auf Tablets (768–899px) war die Rail bisher sichtbar, neu ist sie es nicht mehr. Das ist korrekt gemäß Projekt-Konvention (Desktop = ≥ 900px)
