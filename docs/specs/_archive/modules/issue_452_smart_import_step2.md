---
entity_id: issue_452_smart_import_step2
type: module
created: 2026-05-29
updated: 2026-05-29
status: active
version: "1.0"
issue: 452
tags: [compare, wizard, step2, smart-import, frontend, svelte, epic-246]
---

# Issue #452 — Smart-Import Vervollständigung (Step2Orte)

## Approval

- [ ] Approved

## Purpose

Vervollständigt die Orts-Vorschau in `Step2Orte.svelte` um Höhe und Zeitzone (AC-5), die bereits vom Backend geliefert, aber bisher nicht angezeigt werden. Zusätzlich wird ein Koordinaten-Fallback-Eingabefeld ergänzt (AC-4), das erscheint wenn die automatische URL-Auflösung fehlschlägt — damit kann der User einen Ort auch bei unbekannten Formaten manuell per lat/lon hinzufügen, ohne den Wizard zu verlassen.

> **Schicht-Zuordnung:** Rein Frontend (`frontend/src/`). Kein Backend-Change — `POST /api/locations/resolve` und `POST /api/locations` sind bereits deployed und vollständig implementiert. Die `ResolveResult`-Interface in der Komponente enthält `elevation_m?` und `timezone` schon; sie werden nur nicht gerendert.

## Source

- **UPDATE** `frontend/src/lib/components/compare/steps/Step2Orte.svelte` — Preview-Block um Höhe/Zeitzone erweitern (~5 LoC); Fallback-Felder lat/lon + Button unter Fehlermeldung ergänzen (~40 LoC); zwei neue `$state`-Variablen + Funktion `addLocationFromFallback` hinzufügen

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/locations/resolve` | Go-Backend (deployed) | Löst URLs und Koordinaten auf; liefert `elevation_m?`, `timezone`, `lat`, `lon`, `suggested_name` — kein Change nötig |
| `POST /api/locations` | Go-Backend (deployed) | Speichert neuen Ort; wird von `addLocationFromFallback` direkt aufgerufen (ohne vorherigen Resolve) |
| `api.post<T>()` (`frontend/src/lib/api.ts`) | Utility (vorhanden) | HTTP-Wrapper für beide Backend-Calls — kein Change nötig |
| `Location` (`frontend/src/lib/types.ts`) | Interface (vorhanden) | Rückgabetyp von `POST /api/locations`; `elevation_m?` und `timezone?` sind bereits definiert |
| `ResolveResult` (inline in `Step2Orte.svelte`) | Interface (vorhanden) | Typisiert die Antwort von `POST /api/locations/resolve`; `elevation_m?` und `timezone` sind bereits Teil des Interface |
| `CompareWizardState` (`frontend/src/lib/components/compare/compareWizardState.svelte.ts`) | Context (vorhanden) | `state.pickedIds` — Fallback-Funktion fügt neue Location-ID direkt an |
| `NewLocationWizard.svelte` (`frontend/src/lib/components/compare/NewLocationWizard.svelte`) | Referenz-Implementierung | Zeilen 154–178: exaktes Preview-Pattern für elevation_m + timezone — übernehmen |

## Implementation Details

### §1 AC-5: Preview-Block um Höhe und Zeitzone erweitern (~5 LoC)

Im bestehenden `{#if preview}`-Block in `Step2Orte.svelte` (aktuell Zeilen 131–146) direkt nach der lat/lon-Zeile einfügen:

```svelte
{#if preview.elevation_m !== undefined}
  <p class="text-[var(--g-ink-muted)]">Höhe: {preview.elevation_m} m</p>
{/if}
<p class="text-[var(--g-ink-muted)]">Zeitzone: {preview.timezone}</p>
```

Muster kommt aus `NewLocationWizard.svelte` Zeilen 163–173 — dort wird `elevation_m` nur gerendert wenn `!== undefined` (Backend liefert den Wert nur wenn Open-Elevation eine Antwort gibt), `timezone` hingegen immer (Pflichtfeld im `ResolveResult`).

### §2 AC-4: Neue State-Variablen im `<script>`-Block

Unmittelbar nach den bestehenden `$state`-Deklarationen einfügen:

```ts
let fallbackLat = $state('');
let fallbackLon = $state('');
```

### §3 AC-4: Funktion `addLocationFromFallback`

Nach der bestehenden Funktion `addLocation` einfügen:

```ts
async function addLocationFromFallback() {
  const lat = parseFloat(fallbackLat);
  const lon = parseFloat(fallbackLon);
  if (isNaN(lat) || isNaN(lon)) return;
  adding = true;
  try {
    const loc = await api.post<Location>('/api/locations', {
      name: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
      lat,
      lon
    });
    state.pickedIds = [...state.pickedIds, loc.id];
    importInput = '';
    resolveError = null;
    fallbackLat = '';
    fallbackLon = '';
  } catch (e: unknown) {
    resolveError = extractMsg(e) ?? 'Fehler beim Hinzufügen';
  } finally {
    adding = false;
  }
}
```

Kein Resolve-Call. Name-Fallback: `"${lat.toFixed(4)}, ${lon.toFixed(4)}"`. Felder `elevation_m`, `timezone` und `region` werden bewusst weggelassen — das Backend setzt Defaults.

### §4 AC-4: Fallback-UI unter der Fehlermeldung

Im Template, direkt nach dem bestehenden `{#if resolveError}`-Block, einfügen:

```svelte
{#if resolveError}
  <div class="space-y-2 mt-2">
    <p class="text-xs text-[var(--g-ink-muted)]">Koordinaten manuell eingeben:</p>
    <div class="flex gap-2">
      <input
        data-testid="compare-step2-fallback-lat"
        type="number"
        step="any"
        placeholder="Breitengrad (z.B. 47.2692)"
        bind:value={fallbackLat}
        class="flex-1 border rounded px-2 py-1 text-sm bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
      />
      <input
        data-testid="compare-step2-fallback-lon"
        type="number"
        step="any"
        placeholder="Längengrad (z.B. 11.4041)"
        bind:value={fallbackLon}
        class="flex-1 border rounded px-2 py-1 text-sm bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
      />
    </div>
    <button
      data-testid="compare-step2-fallback-add-btn"
      type="button"
      disabled={adding || !fallbackLat || !fallbackLon}
      onclick={addLocationFromFallback}
      class="px-3 py-1 text-xs rounded bg-[var(--g-accent)] text-white disabled:opacity-40"
    >
      {adding ? 'Wird hinzugefügt…' : 'Hinzufügen'}
    </button>
  </div>
{/if}
```

Kein Debounce — der Button ist der einzige Trigger (zuverlässig, testbar).

### §5 LoC-Schätzung

| Änderung | LoC |
|----------|-----|
| Preview-Erweiterung Höhe/Zeitzone (AC-5) | ~5 |
| State-Variablen `fallbackLat`, `fallbackLon` | ~2 |
| Funktion `addLocationFromFallback` | ~20 |
| Fallback-UI im Template | ~22 |
| **Summe** | **~49 LoC** |

Kein LoC-Override nötig (Limit 250, Änderung ~49 LoC).

## Expected Behavior

- **Input:**
  - Erfolgreiche Auflösung (`preview` gesetzt): Zeigt Name, Koordinaten, optional Höhe (`elevation_m !== undefined`), immer Zeitzone (`timezone`)
  - Fehlgeschlagene Auflösung (`resolveError` gesetzt): Zeigt Fehlermeldung + Fallback-Felder für lat/lon + "Hinzufügen"-Button
  - User gibt lat + lon in Fallback-Felder ein und klickt "Hinzufügen"
- **Output:**
  - AC-5: Preview-Block zeigt `elevation_m` (nur wenn vorhanden) und `timezone` (immer)
  - AC-4: `POST /api/locations` mit `name="${lat.toFixed(4)}, ${lon.toFixed(4)}"`, `lat`, `lon`; neue Location-ID wird an `state.pickedIds` angehängt; Felder und Fehlermeldung werden zurückgesetzt
- **Side effects:**
  - Nach erfolgreichem Fallback-Hinzufügen: `importInput`, `resolveError`, `fallbackLat`, `fallbackLon` werden auf `''`/`null` zurückgesetzt; der neue Ort erscheint als ausgewählt im Counter

## Acceptance Criteria

**AC-1:** Given eine Komoot-Highlight-URL im Eingabefeld / When "Auflösen" geklickt / Then Vorschau zeigt Name, Koordinaten, Höhe (falls vorhanden) und Zeitzone.
  - Test: (populated after /tdd-red)

**AC-2:** Given eine Google-Maps-Share-URL im Eingabefeld / When "Auflösen" geklickt / Then Vorschau zeigt Koordinaten und Zeitzone (Höhe via Open-Elevation sofern verfügbar).
  - Test: (populated after /tdd-red)

**AC-3:** Given Dezimalkoordinaten (z.B. "47.2692, 11.4041") im Eingabefeld / When "Auflösen" geklickt / Then Felder werden direkt übernommen, Vorschau erscheint.
  - Test: (populated after /tdd-red)

**AC-4:** Given ein unbekanntes Format im Eingabefeld / When "Auflösen" geklickt / Then erscheinen unter der Fehlermeldung zwei Zahlenfelder (`data-testid="compare-step2-fallback-lat"`, `data-testid="compare-step2-fallback-lon"`) und ein Button (`data-testid="compare-step2-fallback-add-btn"`); nach manueller Eingabe von lat und lon und Klick auf "Hinzufügen" wird der Ort mit Name `"${lat.toFixed(4)}, ${lon.toFixed(4)}"` via `POST /api/locations` gespeichert und zur Vergleichs-Auswahl hinzugefügt.
  - Test: (populated after /tdd-red)

**AC-5:** Given eine erfolgreiche Auflösung / When Vorschau angezeigt / Then ist Höhe (wenn `elevation_m !== undefined`) und Zeitzone sichtbar im Preview-Block.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein Name-Input im Fallback:** Der Name wird automatisch als `"${lat.toFixed(4)}, ${lon.toFixed(4)}"` gesetzt. Der User kann ihn später in der Orte-Verwaltung umbenennen.
- **Keine Höhen-/Zeitzonenauflösung im Fallback:** `addLocationFromFallback` sendet `elevation_m` und `timezone` nicht mit — das Backend setzt Defaults. Wer einen vollständigen Ort mit Höhe und Zeitzone braucht, nutzt den `NewLocationWizard`.
- **Fallback nur sichtbar bei `resolveError`:** Ist kein Fehler gesetzt (leeres Feld, Erfolg), bleibt das Fallback-Panel ausgeblendet. Das ist by design — Fallback ist kein primärer Workflow.
- **`step="any"` bei Zahleneingabe:** Erlaubt beliebige Dezimalzahlen; keine Frontend-Validierung über `parseFloat()`/`isNaN()`-Check hinaus. Ungültige Werte (NaN) blockieren den Button nicht, lösen aber beim Klick keine API-Call aus.

## Changelog

- 2026-05-29: Initial spec erstellt für Issue #452 (Smart-Import Vervollständigung Step2Orte). Rein Frontend, eine Datei (~49 LoC netto). AC-5: Preview-Erweiterung Höhe+Zeitzone. AC-4: Koordinaten-Fallback-Felder + addLocationFromFallback. Referenz-Muster: NewLocationWizard.svelte Zeilen 154–178.
