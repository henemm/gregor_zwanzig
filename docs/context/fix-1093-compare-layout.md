# Context: fix-1093-compare-layout

## Request Summary
Im Orts-Vergleich-Editor (`/compare/new`, Tab **Layout**) hängt die Seite dauerhaft bei
„Lade Metriken-Katalog…" — das Layout lädt nicht (Issue #1093, aus #1092 Punkt 1).

## Root Cause (reproduziert auf Staging)
`frontend/src/lib/components/compare/LayoutPreview.svelte` (Z. 14–24):

```js
const DUMMY_LOCATIONS = [ { id: 'loc-01', ... }, { id: 'loc-07', ... }, { id: 'loc-08', ... } ];
const rows = $derived(
  pickedIds.length > 0
    ? DUMMY_LOCATIONS.filter(d => pickedIds.includes(d.id)).slice(0, 5)
    : DUMMY_LOCATIONS
);
```

Sobald echte Orte gewählt sind, enthält `pickedIds` echte Location-UUIDs. Der Filter
`DUMMY_LOCATIONS.filter(d => pickedIds.includes(d.id))` matcht **nie** (Dummy-IDs
`loc-01/07/08` ≠ echte IDs) → `rows = []`. Danach greift das Template auf `rows[0].name`
/ `rows[0].feels` zu (Z. 46–47, 57–59) → `Cannot read properties of undefined (reading
'feels')`. Der geworfene Fehler bricht den Render von Step4Layout ab, sodass der
Lade-Zustand („Lade Metriken-Katalog…", `data-testid="step4-loading"`) nie ersetzt wird.

Beweis (Playwright gegen Staging, eingeloggt, 2 echte Orte gewählt, Layout-Tab):
- `step4-loading` bleibt sichtbar (count 2 = Desktop+Mobile)
- `/api/metrics`, `/api/templates`, `/api/metric-presets` liefern alle 200 (API ist NICHT das Problem)
- `[pageerror] Cannot read properties of undefined (reading 'feels')`

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/LayoutPreview.svelte` | **Fehlerquelle** — `rows` wird leer, Template crasht |
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | Mountet LayoutPreview; Spinner `step4-loading` bleibt bei Crash stehen |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | Rendert Step4Layout in Tab `layout` (Desktop + Mobile → doppelt gemountet) |

## Fix-Richtung
`rows` darf nie leer werden. Da die Vorschau reine Illustration mit statischen Dummy-Daten
ist, ist das Filtern echter picked-IDs gegen Dummy-IDs bedeutungslos. Sinnvoll: Anzahl der
Vorschau-Zeilen an `pickedIds.length` koppeln (min. 1, max 5 / max verfügbare Dummys),
aber immer aus `DUMMY_LOCATIONS` nehmen — nie per ID-Match, der strukturell leer läuft.

## Invarianten (dürfen nicht brechen)
- Layout-Tab lädt und zeigt Metriken-Katalog + Vorschau, sobald ≥2 echte Orte gewählt sind.
- Kein Regress bei 0 picked (Detail-/Edit-Modus) — dort rendert die Seite bereits korrekt.

## Risks & Considerations
- Nur Frontend (Svelte). Kein Backend/DB betroffen.
- Reproduktion braucht echte gewählte Orte — der bisherige Codepfad wurde offensichtlich
  nur mit Dummy-pickedIds getestet (deshalb nie aufgefallen).
- Folge-Issues #1094 (Konfigurierbarkeit) / #1095 (Alerts) sind separat; dieser Fix
  entsperrt aber erst den Layout-Tab, in dem #1094 lebt.
