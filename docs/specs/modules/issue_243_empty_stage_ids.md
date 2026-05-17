---
entity_id: issue_243_empty_stage_ids
type: bugfix
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
tags: [bug, frontend, backend, data-integrity]
---

# Bug #243: Leere Stage-IDs führen zu each_key_duplicate

## Approval

- [ ] Approved

## Purpose

Verhindert, dass Etappen ohne `id` gespeichert werden, und schützt die
Trip-Detail-Seite vor einem kompletten Ausfall bei korrupten Daten.

## Ursache

`gpx-upload/+page.svelte` sendet Etappen ohne `id`-Feld ans Backend. Das
Go-Backend akzeptiert leere Stage-IDs (`id: ""`) ohne Fehler. Svelte's
`{#each}` mit `(stage.id)` als Key wirft `each_key_duplicate`, weil alle
leeren Strings identisch sind — die Seite wird weiß.

## Affected Files

- **Frontend:** `frontend/src/routes/gpx-upload/+page.svelte` (Stage ohne ID erzeugen)
- **Go-API:** `internal/handler/trip.go` (validateTrip prüft Stage-IDs nicht)
- **Frontend:** `frontend/src/lib/components/trip-detail/StageList.svelte` (kein Fallback)
- **Daten:** `data/users/default/trips/5f534011.json` (einmalige Migration)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/trip.go` | Go-API | validateTrip + UpdateTripHandler |
| `frontend/src/routes/gpx-upload/+page.svelte` | Frontend | GPX-Upload-Flow |
| `frontend/src/lib/components/trip-detail/StageList.svelte` | Frontend | Stage-Liste rendert |

## Implementation Details

### Fix 1 — Go-Backend: Stage-IDs auto-generieren (Primär-Fix)

In `internal/handler/trip.go`, in beiden Handlern die Stages normalisieren,
bevor `validateTrip` und `SaveTrip` aufgerufen werden. Stages mit leerem
`ID`-Feld erhalten eine kurze zufällige ID (8 Hex-Zeichen via
`crypto/rand`).

```go
// ensureStageIDs belegt leere Stage.ID-Felder mit einer zufaelligen ID.
func ensureStageIDs(stages []model.Stage) []model.Stage {
    for i := range stages {
        if stages[i].ID == "" {
            stages[i].ID = randomShortID()
        }
    }
    return stages
}
```

Aufruf in `CreateTripHandler` und `UpdateTripHandler` vor `validateTrip`.

### Fix 2 — Frontend GPX-Upload: Stage-ID vergeben

In `gpx-upload/+page.svelte`, beim Aufbau des Trip-Objekts die Stage mit
einer generierten ID ausstatten (gleiche `generateId`-Funktion + Suffix):

```js
stages: [{
    id: generateId(tripName) + '-t1',
    name: parsedStage.name,
    date: parsedStage.date,
    waypoints: parsedStage.waypoints
}]
```

### Fix 3 — Frontend StageList: Crash-Schutz

In `StageList.svelte:38`, Fallback auf Index wenn `stage.id` leer ist:

```svelte
{#each trip.stages as stage, index (stage.id || `idx-${index}`)}
```

### Fix 4 — Datenmigration (einmalig)

Skript `scripts/fix_243_stage_ids.py` erzeugt für alle Etappen in
`5f534011.json` mit leerem `id` neue kurze IDs und schreibt die Datei.

## Expected Behavior

- **Input:** Trip mit Etappen, von denen einige `id: ""` haben
- **Output:** Alle Etappen erhalten eindeutige IDs; Trip-Detail-Seite lädt normal
- **Side effects:** Bestehende Etappen-Referenzen (WaypointsPanel, FullProfile) funktionieren, da sie ebenfalls `stage.id` nutzen — nach Migration stimmen die Werte

## Acceptance Criteria

**AC-1:** Given Trip `5f534011` mit 13 Etappen (alle `id: ""`), When `/trips/5f534011` geöffnet wird, Then Tabs und Etappenliste werden angezeigt (keine weiße Seite, kein Console-Error `each_key_duplicate`)
- Test: (populated after /tdd-red)

**AC-2:** Given GPX-Upload-Seite, When eine GPX-Datei hochgeladen und als Trip gespeichert wird, Then hat die Etappe im gespeicherten JSON eine nicht-leere `id`
- Test: (populated after /tdd-red)

**AC-3:** Given PUT `/api/trips/{id}` mit Etappe ohne `id`-Feld, When Backend die Anfrage verarbeitet, Then wird die Etappe mit einer generierten ID gespeichert (kein leerer String im JSON)
- Test: (populated after /tdd-red)

## Known Limitations

- Datenmigration läuft einmalig manuell; falls es weitere Trips mit leeren
  Stage-IDs gibt, muss das Skript breit ausgeführt werden.

## Changelog

- 2026-05-17: Spec erstellt (Bug #243)
