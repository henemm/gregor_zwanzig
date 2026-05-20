# Context: Issue #265 — Smart-Import Frontend: URL-Eingabe + Vorschau im Ort-anlegen-Wizard

## Request Summary

Im `NewLocationWizard.svelte` (Schritt 1 — Verortung) ein URL/Koordinaten-Eingabefeld einbauen, das `POST /api/locations/resolve` aufruft und eine Vorschau anzeigt. Bei Erfolg werden Lat/Lon/Elevation automatisch befüllt und `suggested_name` in Schritt 2 übernommen.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | **Einzige geänderte Datei** — Zeile 124–127 enthält den Platzhalter-Text, der durch das echte Eingabefeld ersetzt wird |
| `internal/handler/location_resolve.go` | Backend-Handler für `POST /api/locations/resolve` — bereits vollständig implementiert |
| `internal/resolver/resolver.go` | Definiert `ResolveResult` (lat, lon, elevation_m, timezone, suggested_name, region, source_type) und `ResolveError` (code, message) |
| `frontend/src/lib/api.ts` | `api.post<T>(path, body)` — wird für den Resolve-Call verwendet |
| `frontend/src/lib/types.ts` | `Location`-Interface — Felder `timezone`, `data_source`, `created_at` schon vorhanden |
| `docs/specs/modules/issue_249_locations_rail.md` | Vorgänger-Spec — NewLocationWizard ist darin beschrieben; URL-Import war als "Known Limitation" deklariert |

## Existing Patterns

- **API-Aufruf:** `api.post<T>('/api/locations/resolve', { input: '...' })` — identisch zur bestehenden `api.post`-Verwendung in `save()`
- **Fehlerbehandlung:** `catch (e: unknown) { const body = e as { detail?: string; error?: string; message?: string }; error = ... }` — gleiches Muster wie im bestehenden `save()`
- **State mit `$state()`:** Svelte 5 Runes — alle bestehenden Variablen (`lat`, `lon`, `error`, `saving`) nutzen dieses Muster

## Backend-Antwort (ResolveResult)

```typescript
interface ResolveResult {
  lat: number;
  lon: number;
  elevation_m?: number;
  timezone: string;
  suggested_name?: string;
  region?: string;
  source_type: string; // "komoot"|"google_maps"|"decimal"|"dms"|"utm"|"gpx"
}
```

Fehlerfall (HTTP 422):
```typescript
interface ResolveError {
  code: string;    // "unknown_format"|"unsupported_url"|"resolve_failed"
  message: string; // menschenlesbar
}
```

## Current State of NewLocationWizard (Step 1)

Zeilen 96–128: Nur manuelle Lat/Lon-Eingabe + statischer Hinweistext:
```
<p class="text-xs text-muted-foreground">
  URL-Import (Komoot, Google Maps) folgt in einem Update.
</p>
```

Dieser Platzhalter wird durch das funktionale Import-Block ersetzt.

## Dependencies

- **Upstream:** `POST /api/locations/resolve` ✅ deployiert (Issue #248)
- **Downstream:** `lat`, `lon`, `elevationM`, `name` (State im Wizard) — werden durch Resolve-Ergebnis befüllt

## Scope

Nur eine Datei: `frontend/src/lib/components/compare/NewLocationWizard.svelte`

**Neuer State:**
- `resolveInput = $state('')` — Texteingabe
- `resolving = $state(false)` — Lade-Indikator für Button
- `resolvePreview = $state<ResolveResult | null>(null)` — Vorschau nach Erfolg
- `resolveError = $state<string | null>(null)` — Fehlermeldung unter dem Eingabefeld

**Neue Funktion:**
- `async function resolveLocation()` — ruft `POST /api/locations/resolve` auf, befüllt preview und auto-füllt lat/lon/elevationM/name

**UI (Schritt 1, vor den manuellen Feldern):**
1. `<Input>` mit Placeholder "Komoot-Link, Google-Maps-URL oder Koordinaten…"
2. Button "Auflösen" (disabled while resolving)
3. Bei Erfolg: Preview-Box (lat, lon, elevation, timezone, source_type)
4. Bei Fehler: rote Fehlermeldung
5. Trennlinie "oder Koordinaten manuell eingeben"
6. Bestehende Lat/Lon/Elevation-Felder bleiben erhalten

## Risks & Considerations

- **suggested_name wird in `name` geschrieben** (Schritt 2) — nur wenn `name` noch leer ist, sonst überschreibt der User seinen eigenen Eintrag
- **Bestehende Koordinaten-Validierung** in `nextStep()` bleibt unverändert — funktioniert auch wenn Felder per Resolve befüllt wurden
- **resolveError vs. error:** zwei separate States — `resolveError` ist nur für den Import-Block, `error` für Wizard-Navigation. Das vermeidet gegenseitige Überschreibung.
- **LoC-Schätzung:** ~40–50 neue Zeilen, gut unter dem 250-LoC-Limit

## Changelog

- 2026-05-20: Initial context erstellt (Issue #265)
