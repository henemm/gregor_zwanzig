# Context: Issue #266 — Mini-Map mit Topo-Hintergrund + Pin im NewLocationWizard Schritt 1

## Request Summary
Nach erfolgreicher Koordinaten-Auflösung in Schritt 1 des `NewLocationWizard.svelte` eine kleine, nicht-interaktive Kartenvorschau einblenden: Topo-Hintergrund + Akzent-Pin auf den aufgelösten Koordinaten.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | Zieldatei — hier wird die Mini-Map eingebaut (Step 1, unterhalb Koordinatenfelder) |
| `frontend/src/lib/components/trip-detail/waypoints/MapCanvas.svelte` | Referenz: Vorhandene Karten-Komponente mit TopoBg + SVG-Overlay |
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Topo-Hintergrund-Komponente (CSS radial-gradient, kein echter Kartentile) |
| `frontend/src/lib/components/ui/topo/index.ts` | Export TopoBg |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` | SVG-Pin-Marker — für Orientierungsvorschau wiederverwendbar (oder vereinfacht) |
| `frontend/src/lib/utils/waypointEditor.ts` | `buildMapPositions()` — benötigt Stage-Objekt, für Einzelpunkt nicht nötig |
| `frontend/src/app.css` | `.g-topo` CSS-Klasse (decorative radial-gradient-Pattern) |

## Existing Patterns

### Topo-Hintergrund
`TopoBg.svelte` ist eine reine CSS-Dekorations-Komponente: mehrere konzentrische `radial-gradient`s erzeugen Höhenlinien-Optik. Kein echter Kartentile-Layer (kein Leaflet, kein MapLibre, kein OpenTopoMap-HTTP-Request). Die Klasse `.g-topo` ist in `app.css` definiert.

### MapCanvas-Muster
`MapCanvas.svelte` kombiniert:
1. `<TopoBg />` als absolute-positioned Hintergrund
2. Ein `<svg viewBox="0 0 400 300">` als absolute-positioned Overlay
3. `WaypointPin` als SVG-`<g>`-Elemente innerhalb des SVGs
4. Zoom-Buttons + Layer-Toggle (für Mini-Map nicht benötigt)

### Für Einzelpunkt reicht deutlich weniger
`buildMapPositions()` arbeitet mit mehreren Waypoints und einem `Stage`-Objekt. Für eine einzelne Koordinatenvorschau wird nur ein zentrierter Pin benötigt — keine Positionsberechnung erforderlich.

## Entscheidung: Neue `LocationPreviewMap.svelte`-Komponente

Eine neue, schlanke Komponente erstellen (kein Umbau von MapCanvas, da sie andere Anforderungen hat):
- Props: `lat: number, lon: number` (immer zentriert)
- Größe: ca. 300×180px (kleinere Vorschau als MapCanvas 400×300)
- Kein Zoom, kein Layer-Toggle
- Wiederverwendbar für andere Stellen (z.B. Location-Detail künftig)
- Platzierung in `compare/` neben NewLocationWizard

## Dependencies

- Upstream: `TopoBg`, `WaypointPin` (bereits vorhanden)
- Downstream: `NewLocationWizard.svelte` — bindet neue Komponente ein

## Existing Specs
- `docs/specs/modules/issue_249_locations_rail.md` — Basis-Spec für NewLocationWizard (Step 1 beschreibt Mini-Map-Anforderung ursprünglich)
- `docs/specs/modules/epic_246_*` — Epic-Spec prüfen ob vorhanden

## Risks & Considerations
- **TopoBg ist dekorativ, kein echter Kartentile** — Koordinaten-Genauigkeit wird nicht abgebildet. Der Pin ist immer mittig. Das ist für eine Orientierungsvorschau ausreichend (das Issue spricht nur von "Orientierungsvorschau").
- **Kein Zoom/Drag** — explizit vom Issue gefordert ("reine Orientierungsvorschau")
- **Erscheint erst wenn lat+lon valide** — reaktive Bedingung `{#if}` auf numerische Gültigkeit
- **Wenn resolvePreview gesetzt** → Koordinaten kommen vom Smart-Import; bei manueller Eingabe → direkt aus lat/lon-State
