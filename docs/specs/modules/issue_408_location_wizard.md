---
entity_id: issue_408_location_wizard
type: module
created: 2026-05-27
updated: 2026-05-27
status: active
version: "1.0"
tags: [locations, wizard, frontend, svelte, issue-408]
---

# Issue #408 — Locations-Seite: NewLocationWizard verdrahten

## Approval

- [ ] Approved

## Zweck

Die Seite `/locations` zeigt beim Klick auf "Neuer Ort" noch den alten `LocationForm`-Dialog.
`NewLocationWizard.svelte` — ein vollständig implementierter 3-Schritt-Wizard mit Smart-Import
und Minimap-Vorschau — existiert bereits und läuft auf `/compare`. Dieses Modul verdrahtet den
Wizard auf der Locations-Seite, sodass beide Einstiegspunkte dasselbe, konsistente Erfassungs-UI
verwenden. `LocationForm` bleibt für den Edit-Flow erhalten und wird nicht verändert.

## Quelle / Source

**Layer:** Frontend / User-UI (`frontend/src/`)

**Geänderte Datei:**
- `frontend/src/routes/locations/+page.svelte` — einzige Änderung, ~12 LoC

**NICHT ändern:**
- `frontend/src/lib/components/compare/NewLocationWizard.svelte` (nur importiert)
- `frontend/src/lib/components/LocationForm.svelte` (bleibt für Edit unverändert)

> **Schicht-Hinweis:** Ausschließlich Frontend (`frontend/src/`). Go-API und Python-Backend werden nicht angefasst.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | Svelte-Komponente | Neuer Create-Wizard; speichert intern via `api.post('/api/locations', loc)`, ruft danach `onsave(loc)` |
| `frontend/src/lib/components/LocationForm.svelte` | Svelte-Komponente | Bestehender Edit-Dialog; bleibt für `dialogMode === 'edit'` unverändert |
| `frontend/src/routes/locations/+page.svelte` | Svelte-Route | Einzige geänderte Datei |

## Implementation Details

### 1. Import ergänzen

```svelte
import NewLocationWizard from '$lib/components/compare/NewLocationWizard.svelte';
```

### 2. Neuen Callback `handleNewLocationSave` hinzufügen

Der Wizard speichert die Location intern selbst (`api.post`). Der Callback darf keinen
zweiten API-Call machen — nur State-Refresh und Dialog schließen:

```ts
function handleNewLocationSave(loc: Location) {
    refetchLocations();
    dialogMode = null;
}
```

Der bestehende `handleSave` bleibt unverändert für den Edit-Pfad.

### 3. Dialog-Body — Create/Edit aufteilen

Im bestehenden "Create/Edit Dialog"-Block wird `dialogMode === 'create'` auf `NewLocationWizard`
umgeleitet; `dialogMode === 'edit'` bleibt auf `LocationForm`:

```svelte
{#if dialogMode === 'create'}
    <NewLocationWizard
        {locations}
        groups={[]}
        onsave={handleNewLocationSave}
        oncancel={closeDialog}
    />
{:else if dialogMode === 'edit'}
    <LocationForm
        location={editTarget ?? undefined}
        {locations}
        onsave={handleSave}
        oncancel={closeDialog}
    />
{/if}
```

`groups={[]}` ist korrekt: `/locations/+page.server.ts` lädt keine Gruppen-Daten.
Der Gruppe-Select im Wizard zeigt dann nur "Keine Gruppe" — das ist für diese Route akzeptabel.

### 4. LoC-Budget

| Änderung | Δ LoC |
|---|---|
| Import | +1 |
| `handleNewLocationSave`-Funktion | +4 |
| Dialog-Body umstrukturieren (if/else) | +5 |
| `{:else if dialogMode}` → spezifische Bedingungen | +2 |
| **Gesamt** | **~12 LoC** |

Weit unter dem 250-LoC-Limit.

## Expected Behavior

- **Input:** Nutzer klickt auf "Neuer Ort" auf `/locations`
- **Output:** `NewLocationWizard` öffnet sich im Dialog (3 Schritte: Smart-Import / Benennung / Aktivitätsprofil). Nach Abschluss des Wizards erscheint die neue Location in der Tabelle.
- **Side effects:** `LocationForm` bleibt für Edit-Flow aktiv. Der Wizard macht den API-Call intern — `handleNewLocationSave` macht keinen zweiten POST.

## Acceptance Criteria

- **AC-1:** Given die Locations-Seite ist geöffnet und keine Location existiert / When der Nutzer auf "Neuer Ort" klickt / Then öffnet sich `NewLocationWizard` (nicht `LocationForm`) im Dialog
  - Test: (populated after /tdd-red)

- **AC-2:** Given der Wizard wurde erfolgreich durchlaufen und die Location gespeichert / When `onsave(loc)` aufgerufen wird / Then wird `refetchLocations()` ausgelöst, der Dialog geschlossen (`dialogMode = null`), und kein zweiter `api.post('/api/locations', ...)` Call abgesetzt
  - Test: (populated after /tdd-red)

- **AC-3:** Given eine bestehende Location in der Tabelle / When der Nutzer auf den Bearbeiten-Button klickt / Then öffnet sich weiterhin `LocationForm` (Edit-Flow unverändert) und nicht `NewLocationWizard`
  - Test: (populated after /tdd-red)

- **AC-4:** Given der Wizard läuft auf `/locations` / When `groups` prop geprüft wird / Then erhält `NewLocationWizard` `groups={[]}`, da die Locations-Seite keine Gruppen-Daten lädt — der Wizard bleibt funktionsfähig
  - Test: (populated after /tdd-red)

- **AC-5:** Given `+page.svelte` nach dem Change / When `svelte-check` im `frontend/`-Verzeichnis ausgeführt wird / Then gibt es 0 Typ-Fehler und 0 Build-Fehler
  - Test: `svelte-check` (Compiler)

## Known Limitations

- **Keine Gruppen:** Der Wizard zeigt auf `/locations` nur "Keine Gruppe" im Gruppe-Select, da `+page.server.ts` keine Gruppen lädt. Das ist ein bewusst akzeptierter Kompromiss für diesen Scope.
- **Wizard-interne Fehler:** Fehlerbehandlung bei fehlschlagendem `api.post` liegt vollständig im Wizard. Die Locations-Seite zeigt kein `error`-State für Create-Fehler (anders als beim Edit-Flow via `handleSave`).

## Out of Scope

- Änderungen an `NewLocationWizard.svelte`
- Gruppen-Daten in `/locations/+page.server.ts` laden
- Edit-Flow auf `NewLocationWizard` umstellen
- Änderungen an Go-API oder Python-Backend

## Changelog

- 2026-05-27: Initial spec erstellt. Beschreibt Verdrahtung von `NewLocationWizard` auf `/locations` (Create-Pfad); 1 Datei, ~12 LoC, 5 Acceptance Criteria.
