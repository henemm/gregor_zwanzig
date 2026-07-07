# Bug #1080 — compare/new: Ort per URL hinzufügen bleibt unsichtbar

## Analysis

### Type
Bug (+ kleine Erweiterung: Benennung vor dem Hinzufügen)

### Symptom (Nutzersicht)
Auf `/compare/new` einen Ort per URL (`https://maps.app.goo.gl/…`) auflösen → Vorschau
„ERKANNT · (kein Name) · 43.0421, 6.1049 · 0 m" → Klick „＋ Zum Vergleich hinzufügen" →
nichts sichtbar. Der Ort erscheint nicht in der „Im Vergleich"-Liste.

### Root Cause (code-belegt)
`frontend/src/lib/components/compare/steps/Step2Orte.svelte`

1. **Unsichtbar (Kern-Bug):** `pickedLocations` (Z. 48–50) löst `ws.pickedIds` gegen den
   **statischen** `locations`-Prop auf (`data.locations` vom Seiten-Load, in CompareEditor
   `locations={data.locations}`, kein Reload/`invalidate`). `addLocation()` (Z. 85–105) legt
   den Ort per `POST /api/locations` (Backend `CreateLocationHandler`, HTTP 201) korrekt an und
   schiebt die ID in `ws.pickedIds`, aber die neue Location ist **nicht** in `locations` →
   `.map(...).find(...)` = `undefined` → `.filter(Boolean)` verwirft sie → kein Eintrag,
   Zähler bleibt 0. Gleicher Fehler in `addLocationFromFallback()` (Z. 107–128).

2. **Name = rohe URL:** Google-/`goo.gl`-Resolver setzt nie `SuggestedName`
   (`internal/resolver/googlemaps.go`), Feld `omitempty` (`internal/resolver/resolver.go:17`) →
   Frontend `undefined` → Anzeige „(kein Name)". `addLocation()` (Z. 90) nimmt dann
   `name: preview.suggested_name ?? importInput` → die rohe URL wird Name (und via `toKebab`
   die ID). Kein Eingabefeld zum Benennen; „(kein Name)" nicht klickbar.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/compare/steps/Step2Orte.svelte | MODIFY | Neu angelegte Location lokal in resolvbare Liste aufnehmen; Namensfeld für erkannte Vorschau |
| frontend/src/lib/components/compare/__tests__/… (E2E) | CREATE | Playwright-E2E: URL auflösen → benennen → hinzufügen → in Picked-Liste sichtbar |

### Scope Assessment
- Files: 1 Komponente (+ 1 E2E-Test)
- Estimated LoC: ~ +40 / -5
- Risk Level: LOW (nur Frontend, keine Persistenz-/Schema-Änderung)

### Technical Approach
- `Step2Orte` hält eine lokale reaktive Liste aller resolvbaren Orte (initial = `locations`-Prop),
  die bei jedem erfolgreichen Create (`addLocation` + `addLocationFromFallback`) um das
  zurückgegebene `loc`-Objekt ergänzt wird. `pickedLocations` löst gegen diese lokale Liste auf.
- Vorschau-Sektion bekommt ein editierbares Namensfeld (Default = Koordinaten-String, **nicht**
  die URL); dieser Name geht an `POST /api/locations`.

### Dependencies
- `compareWizardState.svelte` (`ws.pickedIds`), `$lib/api` `POST /api/locations`, `$lib/types` `Location`.
- Backend unverändert (Create funktioniert bereits).

### Open Questions
- keine (Root Cause eindeutig; ACs in Spec-Phase)
