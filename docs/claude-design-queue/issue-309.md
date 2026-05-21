# #309 — Design: Wetter-Drill-Down — eingebettet in Trip-Detail + Compare (Desktop + Mobile)

**Labels:** `priority:medium` `frontend` `area:trips` `area:compare` `area:weather` `for:claude-design`
**URL:** https://github.com/henemm/gregor_zwanzig/issues/309
**Erstellt:** 2026-05-21

---

## Was fehlt

Das UX-Redesign (`docs/specs/ux_redesign_navigation.md §2.3`) sieht vor, dass es **keine eigenständige Wetter-Seite** mehr gibt. Stattdessen soll ein Wetter-Drill-Down direkt aus einer Etappe (Trip-Detail) oder einem Ort (Compare) erreichbar sein.

Aktuell existiert `/weather` noch als separate Seite (Legacy). **Kein Design existiert für die neue eingebettete Form.**

## Was ich brauche

**Desktop + Mobile** für zwei Einstiegspunkte:

### Einstieg 1: Aus Trip-Detail (Etappe → Wetter)
- Wie kommt man dorthin? (Button an der Etappen-Karte? Tab? Modal? Slide-Panel?)
- Was wird gezeigt? Stündliche Tabelle für den Etappen-Tag (Wegpunkt-Koordinaten als Basis)
- Welche Metriken? Temp / Niederschlag / Wind / Böen / Richtung / Bewölkung / Symbol
- Wie groß? Ganzseitig oder Panel (Drawer)?

### Einstieg 2: Aus Compare (Ort → Wetter)
- Wie kommt man dorthin? (Klick auf Ort in der Compare-Matrix?)
- Gleiche Tabelle wie oben, aber für den gewählten Ort

## Aktueller Fallback

`/weather` (Standalone, bleibt bis Migration als Fallback):
- `frontend/src/routes/weather/+page.svelte`

## Ziel

Sobald das Design klar ist, wird `/weather` auf Redirect zu Compare umgestellt und der Drill-Down wird inline integriert.
