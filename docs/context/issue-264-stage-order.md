# Issue #264 — GPX-Etappenreihenfolge beim Import

## Status
Phase 2 Analyse abgeschlossen — bereit für Spec.

## Bug-Beschreibung

Beim Hochladen von GPX-Dateien aus Sport-Apps (Komoot, Strava, Garmin) landen die Etappen in falscher Reihenfolge im gespeicherten Trip. Beispiel KHW 403: gespeicherte Reihenfolge war `02, 03, ..., 10, 01, 11, 00b, 00a` statt `00a, 00b, 01, 02, ..., 11`.

## Root Cause (bestätigt)

`naturalSort(pendingFiles, (f) => f.name)` in `commitPending()` sortiert nach **Dateinamen**. Komoot-Dateien haben Datum-Präfixe: `2026-03-22_2841530313_KHW_03_...gpx`. Der Sort sortiert nach Aufnahmedatum, nicht nach Etappennummer.

Konkret bei den 13 KHW-Dateien:
- Etappen 02–10 wurden am 2026-03-22 aufgenommen → landen bei Datei-Sort vorn
- Etappen 00a, 00b, 01, 11 wurden am 2026-03-24 aufgenommen → landen hinten
- Resultierende falsche Reihenfolge: `[02, 03, ..., 10, 01, 11, 00b, 00a]`

## Betroffene Dateien

| Datei | Zeile | Problem |
|-------|-------|---------|
| `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte` | 94 | `naturalSort(pendingFiles, (f) => f.name)` — sortiert nach Dateinamen vor Upload |
| `frontend/src/lib/components/edit/EditRouteSection.svelte` | 67 | Gleicher Code im Edit-Flow |

## Fix-Strategie

**Statt nach Dateinamen VOR dem Upload sortieren → Stage-Objekte NACH dem Upload sortieren.**

```typescript
// ALT (buggy):
const sorted = naturalSort(pendingFiles, (f) => f.name);
for (const file of sorted) {
    const stage = await uploadGpx(file, stageDate, 8);
    wizard.addStage(stage);
}

// NEU (korrekt):
const uploaded: Stage[] = [];
for (const file of pendingFiles) {
    const stage = await uploadGpx(file, start, 8);
    uploaded.push(stage);
}
const sorted = naturalSort(uploaded, (s) => s.name);
for (const stage of sorted) {
    wizard.addStage(stage);
}
wizard.recomputeStageDates(); // korrigiert alle Daten auf startDate+index
```

`stage.name` wird vom Backend aus dem GPX-Track-Namen extrahiert (`KHW_03: von Porzehütte...`). Dieser enthält keine Datums-Präfixe und sortiert korrekt.

## Scope

- **Dateien:** 2
- **LoC:** ~20–25
- **Risiko:** Niedrig

## Edge Cases

1. **GPX ohne Stage-Name:** `naturalSort` ist stabil — bei gleichen Keys bleibt Upload-Reihenfolge (neutraler Fallback)
2. **Einzeln-Upload:** naturalSort auf 1 Element ist no-op
3. **Upload-Fehler:** Nur erfolgreiche Stages landen in `uploaded[]`, Fehler-Handling bleibt gleich
4. **EditRouteSection tripName-Fallback:** Zeile 87 nutzte `sorted[0].name` (Dateiname) → wird zu `sorted[0].name` (Stage-Name, semantisch besser)

## Test-Verifikation

1. KHW-Trip neu anlegen, alle 13 GPX-Dateien mit Komoot-Datum-Präfix auf einmal hochladen
2. Trip speichern
3. JSON prüfen: `stages`-Array muss `[00a, 00b, 01, 02, ..., 11]` enthalten
