---
entity_id: issue_265_smart_import_frontend
type: module
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [compare, locations, frontend, wizard, import, resolve]
---

# Issue #265 — Smart Import: URL/Koordinaten-Auflösung in NewLocationWizard

## Approval

- [ ] Approved

## Purpose

Ergänzt Schritt 1 des `NewLocationWizard.svelte` um einen funktionalen Import-Block, der
dem User ermöglicht, eine Komoot-URL, Google-Maps-URL oder Koordinaten-String einzugeben
und automatisch in Lat/Lon/Elevation aufzulösen. Das Feature ersetzt den bisherigen
Platzhalter-Text (Zeilen 124–127) durch ein vollständig funktionales Eingabefeld, das
`POST /api/locations/resolve` aufruft, eine Vorschau der aufgelösten Werte anzeigt und
die Formularfelder automatisch befüllt — damit entfällt das manuelle Abtippen von
Koordinaten für den häufigsten Anwendungsfall.

## Source

- **File:** `frontend/src/lib/components/compare/NewLocationWizard.svelte`
- **Identifier:** `resolveLocation()` (neue Funktion), Import-Block-Template (Zeilen 124–127 ersetzt)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `POST /api/locations/resolve` | Go-Backend-Endpoint (Issue #248, deployed) | Nimmt `{"input": "..."}` entgegen, gibt `ResolveResult` mit lat/lon/elevation_m/timezone/suggested_name/region/source_type zurück |
| `frontend/src/lib/api.ts` — `api.post<T>()` | Utility (vorhanden) | Typisierter HTTP-POST mit Error-Handling |
| `frontend/src/lib/components/ui/input/` | UI-Bibliothek (vorhanden) | Text-Input-Feld für die URL/Koordinaten-Eingabe |
| `frontend/src/lib/components/ui/button/` | UI-Bibliothek (vorhanden) | "Auflösen"-Button mit disabled-State während Resolve-Aufruf |

## Scope

Ausschließlich Frontend, **eine Datei:**

- **Geändert:** `frontend/src/lib/components/compare/NewLocationWizard.svelte` (~55 LoC netto, Zeilen 124–127 ersetzt)

Keine Änderungen an:
- Go-Backend — `POST /api/locations/resolve` ist deployed
- `api.ts` — keine neuen Methoden erforderlich
- `types.ts` — kein neues exportiertes Interface
- `save()`-Funktion und `nextStep()`-Validierung — bleiben vollständig unverändert

## Implementation Details

### 1. ResolveResult-Interface und neuer State (nach Zeile 35)

```typescript
interface ResolveResult {
    lat: number;
    lon: number;
    elevation_m?: number;
    timezone: string;
    suggested_name?: string;
    region?: string;
    source_type: string;
}

let resolveInput = $state('');
let resolving = $state(false);
let resolvePreview = $state<ResolveResult | null>(null);
let resolveError = $state<string | null>(null);
```

`ResolveResult` ist ein dateilokal-definiertes Interface (kein Export), da es ausschließlich
innerhalb von `NewLocationWizard.svelte` verwendet wird.

### 2. resolveLocation()-Funktion

```typescript
async function resolveLocation() {
    if (!resolveInput.trim() || resolving) return;
    resolving = true;
    resolveError = null;
    resolvePreview = null;
    try {
        const result = await api.post<ResolveResult>('/api/locations/resolve', { input: resolveInput });
        resolvePreview = result;
        lat = String(result.lat);
        lon = String(result.lon);
        if (result.elevation_m !== undefined) elevationM = String(result.elevation_m);
        if (result.suggested_name && !name.trim()) name = result.suggested_name;
    } catch (e: unknown) {
        const apiErr = e as { code?: string; message?: string; error?: string };
        resolveError = apiErr.message ?? apiErr.error ?? 'Fehler beim Auflösen';
    } finally {
        resolving = false;
    }
}
```

`suggested_name` wird ONLY in `name` übernommen wenn `!name.trim()` — User-Eingaben werden
niemals überschrieben.

### 3. prevStep()-Anpassung

`prevStep()` erhält eine zusätzliche Zeile: `resolveError = null`. `resolvePreview` wird
bewusst NICHT geclearet, damit der User beim Zurücknavigieren die Vorschau noch sieht.

### 4. Template-Struktur Schritt 1 (vollständige Reihenfolge)

```
[Import-Block]
  <Input data-testid="location-wizard-resolve-input"
         placeholder="Komoot-Link, Google-Maps-URL oder Koordinaten…"
         bind:value={resolveInput}
         onkeydown={(e) => e.key === 'Enter' && resolveLocation()} />
  <Button data-testid="location-wizard-resolve-btn"
          onclick={resolveLocation}
          disabled={resolving || !resolveInput.trim()}>
    {resolving ? 'Auflösen…' : 'Auflösen'}
  </Button>

[Vorschau-Box — nur wenn resolvePreview gesetzt]
  <div data-testid="location-wizard-resolve-preview">
    lat: {resolvePreview.lat}, lon: {resolvePreview.lon}
    {#if resolvePreview.elevation_m !== undefined}
      | Höhe: {resolvePreview.elevation_m} m
    {/if}
    | Zeitzone: {resolvePreview.timezone}
    | Quelle: {resolvePreview.source_type}
  </div>

[Fehlermeldung — nur wenn resolveError gesetzt]
  <p data-testid="location-wizard-resolve-error" class="text-sm text-destructive">
    {resolveError}
  </p>

[Trennlinie]
  <p class="text-xs text-muted-foreground">oder Koordinaten manuell eingeben</p>

[Bestehende Koordinaten-Felder — unverändert, außer zusätzlicher oninput-Handler]
  <Input ... bind:value={lat}   oninput={() => (resolvePreview = null)} />
  <Input ... bind:value={lon}   oninput={() => (resolvePreview = null)} />
  <Input ... bind:value={elevationM} />   <!-- kein oninput nötig -->
```

`oninput={() => (resolvePreview = null)}` auf lat und lon signalisiert dem User visuell,
dass die Vorschau nicht mehr mit den manuell eingetippten Werten übereinstimmt.

### 5. Bestehende Validierung und save() — keine Änderungen

`nextStep()` validiert `lat !== 0 || lon !== 0` — das funktioniert identisch ob die Felder
manuell oder per Resolve befüllt wurden. `save()` liest `lat`, `lon`, `elevationM` als
reguläre State-Variablen — keine Abhängigkeit vom Resolve-Flow.

## Expected Behavior

- **Input:** User gibt eine URL oder Koordinaten-String in das Resolve-Eingabefeld ein und
  klickt "Auflösen" (oder drückt Enter).
- **Output (Erfolg):** `lat`, `lon`, `elevationM` werden befüllt. Eine Vorschau-Box
  (`data-testid="location-wizard-resolve-preview"`) zeigt lat, lon, ggf. elevation_m,
  timezone und source_type an. Wenn `name` noch leer ist, wird `suggested_name` übernommen.
- **Output (Fehler):** Fehlermeldung in `resolveError` erscheint in
  `data-testid="location-wizard-resolve-error"`. `lat`, `lon`, `elevationM` bleiben
  unverändert.
- **Side effects:** `resolveLocation()` führt einen `POST /api/locations/resolve`-Aufruf
  durch. Manuelles Editieren von lat oder lon setzt `resolvePreview = null`. `save()` und
  die restliche Wizard-Logik haben keine Kenntnis vom Resolve-Flow.

## Acceptance Criteria

**AC-1:** Given Schritt 1 des NewLocationWizard ist geöffnet und die Felder sind leer / When der User den Import-Block betrachtet / Then ist ein Eingabefeld mit placeholder "Komoot-Link, Google-Maps-URL oder Koordinaten…" (data-testid="location-wizard-resolve-input") und ein Button "Auflösen" (data-testid="location-wizard-resolve-btn") sichtbar, oberhalb der manuellen Koordinaten-Felder.

**AC-2:** Given der User hat eine gültige URL oder Koordinaten in das Resolve-Eingabefeld eingegeben / When er auf "Auflösen" klickt und das Backend antwortet mit 200 und einem ResolveResult / Then werden lat, lon und (falls vorhanden) elevation_m automatisch in die Koordinaten-Felder eingetragen, eine Vorschau-Box (data-testid="location-wizard-resolve-preview") mit den aufgelösten Werten erscheint, und der Button "Auflösen" ist während der Aufruf-Dauer deaktiviert.

**AC-3:** Given der User hat einen nicht auflösbaren String eingegeben / When er auf "Auflösen" klickt und das Backend antwortet mit 422 oder einem Netzwerkfehler / Then erscheint unter dem Import-Block eine Klartext-Fehlermeldung (data-testid="location-wizard-resolve-error") mit dem vom Backend gelieferten `message`-Feld; die Koordinaten-Felder bleiben unverändert und kein globaler Wizard-Error-State wird gesetzt.

**AC-4:** Given das Backend hat `suggested_name: "Innsbruck Nordkette"` geliefert und das Name-Feld in Schritt 2 ist noch leer / When der User nach erfolgreichem Resolve zu Schritt 2 wechselt / Then ist das Name-Feld mit "Innsbruck Nordkette" vorbelegt; hat der User im Name-Feld bereits einen Wert eingetragen, bleibt dieser unverändert.

**AC-5:** Given eine erfolgreiche Auflösung hat die Vorschau-Box angezeigt / When der User anschließend den lat- oder lon-Wert manuell editiert / Then verschwindet die Vorschau-Box (resolvePreview = null), um anzuzeigen dass die Werte nicht mehr mit dem aufgelösten Ergebnis übereinstimmen.

## Known Limitations

- **Enter-Key im Resolve-Feld** löst über `onkeydown` den Resolve-Aufruf aus; in seltenen Fällen kann dies mit Browser-Autofill-Navigation kollidieren.
- **Kein Debounce:** Der "Auflösen"-Button ist die einzige Trigger-Quelle — es gibt kein automatisches Auflösen bei Texteingabe. Das verhindert unnötige API-Aufrufe.
- **Region-Feld:** Das optionale `region`-Feld aus `ResolveResult` wird in der Vorschau nicht angezeigt und nicht in den Wizard-State übernommen, da das Location-Modell kein `region`-Feld besitzt.

## Changelog

- 2026-05-20: Initial spec erstellt (Issue #265 — Smart Import Frontend für NewLocationWizard).
