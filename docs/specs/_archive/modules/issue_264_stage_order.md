---
entity_id: issue_264_stage_order
type: bugfix
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [bugfix, frontend, gpx-import, stage-sort, wizard, edit-flow, issue-264]
---

<!-- Issue #264 — GPX-Etappenreihenfolge beim Import: Sort nach Stage-Name statt Dateiname -->

# Issue #264 — Bug-Fix: GPX-Etappenreihenfolge nach Stage-Name sortieren, nicht nach Dateiname

## Approval

- [ ] Approved

## Zweck

`commitPending()` in beiden Import-Flows (Wizard Step 2 und Edit-Route) sortiert GPX-Dateien vor dem Upload nach dem Dateinamen. Apps wie Komoot, Strava und Garmin exportieren GPX-Dateien mit einem Datum-Präfix (z.B. `2026-03-22_2841530313_KHW_03_...gpx`), was dazu führt, dass die gespeicherte Etappenreihenfolge dem Upload-Datum folgt statt der tatsächlichen Etappennummer. Der Fix verlagert den Sort-Schritt: GPX-Dateien werden unsortiert hochgeladen, und die vom Backend zurückgelieferten `Stage`-Objekte werden anschliessend nach `stage.name` sortiert — dem inhaltlichen Namen aus dem GPX, der die korrekte Etappenbezeichnung trägt.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` — `commitPending()`, Zeile ~94 (Wizard-Flow)
- `frontend/src/lib/components/edit/EditRouteSection.svelte` — `commitPending()`, Zeile ~67 (Edit-Flow)

**NICHT ändern:** Backend-Code, API-Endpoints, Datenmodell — der Bug liegt ausschliesslich in der Frontend-Sortierlogik.

> **Schicht-Hinweis:** Beide Dateien liegen im SvelteKit-Frontend-Layer (`frontend/src/`). Go-API und Python-Backend sind nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `naturalSort` | Utility-Funktion (Frontend) | Alphanumerisch-stabile Sortierfunktion, wird nach dem Fix auf `Stage[]` statt auf `File[]` angewendet |
| `uploadGpx()` | Async-Funktion (Frontend) | Lädt eine GPX-Datei hoch und gibt ein `Stage`-Objekt zurück; liefert `stage.name` aus GPX-Inhalt |
| `Stage` | TypeScript-Interface | `name: string` ist laut Interface immer gesetzt (nicht optional); wird als Sortierschlüssel verwendet |
| `wizard.addStage()` | WizardState-Methode | Hängt ein Stage-Objekt an den Wizard-State an |
| `wizard.recomputeStageDates()` | WizardState-Methode | Neu berechnet Etappen-Daten nach dem Sortieren; muss nach dem letzten `addStage`-Aufruf kommen |
| `stages` (EditRouteSection) | Svelte-Store / Array | Lokales Array im Edit-Flow, das analog zu `wizard.addStage()` befüllt wird |

## Implementation Details

### 1. `Step2Stages.svelte` — `commitPending()`

**Vorher (buggy):** Sort läuft auf Dateinamen vor dem Upload.

```typescript
const sorted = naturalSort(pendingFiles, (f) => f.name);
for (const file of sorted) {
    const stage = await uploadGpx(file, stageDate, 8);
    wizard.addStage(stage);
}
wizard.recomputeStageDates();
```

**Nachher (korrekt):** Alle Dateien zuerst hochladen, dann `Stage`-Objekte nach `stage.name` sortieren, dann in den Wizard-State übernehmen.

```typescript
const uploaded: Stage[] = [];
for (const file of pendingFiles) {
    const stage = await uploadGpx(file, start, 8);
    uploaded.push(stage);
}
const sorted = naturalSort(uploaded, (s) => s.name);
for (const stage of sorted) {
    wizard.addStage(stage);
}
wizard.recomputeStageDates();
```

Der `naturalSort`-Import bleibt erhalten — nur das Argument ändert sich von `File[]` zu `Stage[]`.

### 2. `EditRouteSection.svelte` — `commitPending()`

**Vorher (buggy):** Gleiche Dateiname-Sort-Logik wie im Wizard. Zusätzlich: Trip-Name wird aus dem Dateinamen der ersten sortierten Datei abgeleitet (`sorted[0].name.replace(...)`), was zur falschen Etappe führen kann.

```typescript
const sorted = naturalSort(pendingFiles, (f) => f.name);
for (const file of sorted) {
    const stage = await uploadGpx(file, stageDate, 8);
    stages.push(stage);
}
if (!tripName && sorted.length > 0) {
    tripName = sorted[0].name.replace(/\.gpx$/i, '');
}
```

**Nachher (korrekt):** Upload-Schleife mit Index für Datum-Offset, dann Sort auf `Stage`-Objekten, Trip-Name aus `stage.name`.

```typescript
const uploaded: Stage[] = [];
let uploadIndex = 0;
for (const file of pendingFiles) {
    const stage = await uploadGpx(file, addDays(start, uploadIndex), 8);
    uploaded.push(stage);
    uploadIndex += 1;
}
const sorted = naturalSort(uploaded, (s) => s.name);
for (const stage of sorted) {
    stages.push(stage);
}
if (!tripName && sorted.length > 0) {
    tripName = sorted[0].name;
}
```

### 3. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | +4 / -3 | nein (Frontend-Asset) |
| `frontend/src/lib/components/edit/EditRouteSection.svelte` | +5 / -3 | nein (Frontend-Asset) |
| **Gesamt (zählend)** | **0** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Array von `File`-Objekten in `pendingFiles` mit beliebigen Dateinamen (Datum-Präfix oder ohne)
- **Output:** `Stage`-Objekte werden in der Reihenfolge aufsteigend nach `stage.name` (alphanumerisch) zum Wizard-State bzw. zum `stages`-Array hinzugefügt
- **Side effects:** `wizard.recomputeStageDates()` korrigiert Etappen-Daten nach dem Sortieren automatisch — kein manueller Datum-Fix nötig. `tripName` im Edit-Flow erhält den inhaltlichen Stage-Namen statt des Dateinamens.

## Acceptance Criteria

- **AC-1:** Given 13 GPX-Dateien mit Komoot-Datum-Präfix (z.B. `2026-03-22_..._KHW_03_...gpx`) / When im Wizard-Flow hochgeladen / Then ist die gespeicherte Etappenreihenfolge `KHW 00a, KHW 00b, KHW 01, KHW 02, ..., KHW 11` (nach `stage.name`), nicht nach Upload-Datum sortiert
  - Test: (populated after /tdd-red)

- **AC-2:** Given dieselbe Datei-Menge mit Datum-Präfix / When im Edit-Flow (`EditRouteSection`) hochgeladen / Then ist die resultierende Stage-Reihenfolge identisch mit der Wizard-Flow-Reihenfolge aus AC-1
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Upload, bei dem eine einzelne GPX-Datei einen Fehler zurückgibt / When die übrigen Dateien erfolgreich hochgeladen werden / Then werden die erfolgreich zurückgelieferten `Stage`-Objekte korrekt nach `stage.name` sortiert und übernommen; kein Absturz durch fehlenden Eintrag
  - Test: (populated after /tdd-red)

- **AC-4:** Given GPX-Dateien ohne Datum-Präfix (z.B. `etappe_01.gpx`, `etappe_02.gpx`) / When hochgeladen / Then bleibt die Reihenfolge korrekt nach `stage.name` — kein Regressionsfall
  - Test: (populated after /tdd-red)

## Known Limitations

- **Keine Backend-Änderung:** Der Fix korrigiert ausschliesslich die Frontend-Sortierlogik. Bereits gespeicherte Trips mit falsch sortierter Reihenfolge (vor dem Fix importiert) werden nicht rückwirkend korrigiert — das wäre ein separates Migrations-Issue.
- **`stage.name` als Sortierschlüssel:** Der Name wird aus dem GPX-Inhalt extrahiert (Backend-Verantwortung). Sind GPX-Dateien ohne sprechenden Namen exportiert (z.B. nur `Activity`), kann die Sort-Reihenfolge unintuintiv sein — das liegt ausserhalb des Scopes dieses Fixes.

## Out of Scope

- Rückwirkende Korrektur bereits gespeicherter Trips
- Änderungen am Upload-Endpoint oder am Backend-GPX-Parser
- Drag-Drop-Reorder nach dem Import (separates Feature)

## Changelog

- 2026-05-20: Initial spec erstellt. Beschreibt Fix für falsche GPX-Etappenreihenfolge in Wizard- und Edit-Flow: Sort von Dateinamen auf Stage-Namen verlagern.
