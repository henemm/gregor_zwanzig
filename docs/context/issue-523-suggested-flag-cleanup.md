# Context: Issue #523 — suggested/waypoint.ai-Flag entfernen (C8 aus #506)

## Request Summary
Constraint C8 aus Issue #506 fordert die vollständige Entfernung des KI-Vorschlags-Flags
(`waypoint.suggested` / `suggestion_reason`) aus Backend-Modell und Frontend. Die UI-Funktion
wurde in #503 und #518 bereits entfernt — der zugehörige Code (toter Code) blieb übrig.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `internal/model/trip.go:58,63` | Felder `Suggested` + `SuggestionReason` → entfernen |
| `internal/handler/trip.go:361–365` | Legacy-Normalisierung liest `wp.Suggested` → entfernen |
| `internal/handler/trip_confirm_test.go:187–238` | `TestConfirmWaypoint_LegacySuggested` mit `Suggested:true` → entfernen |
| `internal/model/waypoint_arrival_marshal_test.go:31,44,66` | Referenziert `SuggestionReason` → anpassen |
| `internal/store/trip_arrival_roundtrip_test.go:40,86,157–205` | `suggested` + `suggestion_reason` im JSON → anpassen |
| `frontend/src/lib/types.ts:36,43` | `suggested?` + `suggestion_reason?` → entfernen |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` | Prop `suggested` + {#if suggested}-Branch → entfernen |
| `frontend/src/lib/utils/waypointEditor.ts:27–41` | `stripSuggested()` — siehe Sonderstatus unten |
| `frontend/src/lib/utils/waypointEditor.test.ts` | Tests für `stripSuggested` → anpassen/entfernen |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte:26,28` | Deprecated Props `onConfirm?`/`onReject?` → entfernen |
| `frontend/src/lib/components/edit/TripEditView.svelte:69` | Ruft `stripSuggested()` auf |
| `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte:43` | Ruft `stripSuggested()` auf |

## Entscheidung: stripSuggested() → ENTFERNEN (Option B)

Die Funktion wird in **3 Dateien** aufgerufen (nicht 2):
- `EditStagesPanelNew.svelte:44`
- `TripEditView.svelte:69`
- `WaypointsPanel.svelte:43`

Sie entfernt neben `suggested`/`suggestion_reason` auch `origin`/`confirmed` aus dem PUT-Payload.
Der `UpdateTripHandler` macht `existing.Stages = *req.Stages` (direkter Replace) — `origin`/`confirmed`
würden also round-trippen. Das ist korrekt: das Frontend liest den Zustand aus dem Backend-GET und
sendet ihn zurück. Der `ConfirmWaypointHandler` wird vom Frontend nirgends aufgerufen (grep bestätigt).

→ **Funktion komplett entfernen**, alle 3 Aufrufstellen bereinigen.

## Implementierungsstrategie (Plan-Agent)

**Reihenfolge:** Backend-Änderungen zuerst, dann Frontend — in einem atomaren Commit.

| Schritt | Datei | Was | Netto-LoC |
|---------|-------|-----|-----------|
| 1 | `internal/model/trip.go` | `Suggested` + `SuggestionReason` entfernen | -2 |
| 2 | `internal/handler/trip.go` | Legacy-Block Zeilen 361–365 + Docstring-Zeile entfernen | -6 |
| 3a | `internal/handler/trip_confirm_test.go` | `TestConfirmWaypoint_LegacySuggested` entfernen | -52 |
| 3b | `internal/model/waypoint_arrival_marshal_test.go` | `SuggestionReason`-Zeilen entfernen | -2 |
| 3c | `internal/store/trip_arrival_roundtrip_test.go` | `Suggested`/`SuggestionReason`-Assertions entfernen | -11 |
| 4 | `frontend/src/lib/types.ts` | `suggested?`+`suggestion_reason?` entfernen | -1 |
| 5 | `frontend/src/lib/utils/waypointEditor.ts` | `stripSuggested()` entfernen | -25 |
| 6a | `frontend/.../TripEditView.svelte` | Import + Aufruf entfernen | -1 |
| 6b | `frontend/.../WaypointsPanel.svelte` | Import + Aufruf entfernen | -1 |
| 6c | `frontend/.../EditStagesPanelNew.svelte` | Import + Aufruf entfernen | -1 |
| 7 | `frontend/.../WaypointPin.svelte` | Prop + `{#if suggested}`-Branch entfernen | -22 |
| 8 | `frontend/.../WaypointCard.svelte` | Deprecated Props entfernen | -3 |
| 9 | `frontend/src/lib/utils/waypointEditor.test.ts` | `stripSuggested`-Tests entfernen | -63 |

**Gesamt: ~-190 LoC** — unter dem 250er-Limit

## Nicht berührt

- `internal/resolver/resolver.go:17` — `SuggestedName` (völlig anderes Feld, Ortsname-Suggestion)
- `internal/resolver/coords.go:195` + `komoot.go:102` — gleicher Grund: andere Domäne
- `WaypointRow.svelte` + `Step3Waypoints.svelte` — `onReject` dort = Löschen-Aktion, kein Bezug zur AI-Suggestion
- `ConfirmWaypointHandler` selbst (ohne Legacy-Block) — bleibt registriert; `confirmed`+`arrival_override` bleiben im Model
- `frontend/src/lib/issue_518_suggested_cleanup.test.ts` — existierender Test, der prüft dass Wizard-State
  kein `confirmWaypoint`/`stripSuggested` mehr hat; passt nach unserer Änderung automatisch

## Existing Patterns

- Toter-Code-Cleanup erfolgte bei #503 (UI) und #518 (Wizard): Schritt für Schritt, nie alles auf einmal
- Backend-Feldentfernung: `omitempty`-Felder werden einfach gelöscht; JSON-Deserialisierung ignoriert
  unbekannte Felder → Bestandsdaten mit `suggested:true` werden beim nächsten Laden schlicht ignoriert
- Frontend-Type-Entfernung: TypeScript-Compile-Fehler zeigen alle Nutzungsstellen automatisch

## Dependencies

- Upstream: keine neuen — reines Löschen
- Downstream: alle Komponenten die `Waypoint.suggested` oder `suggestion_reason` verwenden

## Risks & Considerations

1. **Bestandsdaten:** Bestehende JSON-Dateien in `data/users/*/trips/*.json` können noch
   `"suggested":true` enthalten. Go ignoriert unbekannte JSON-Felder beim Laden — kein Datenverlust.
2. **stripSuggested-Entscheidung:** Wenn `origin`/`confirmed` nicht mehr gestrippt werden und ein
   Bug im PUT-Handler liegt, könnten confirm-Endpoint-Werte versehentlich überschrieben werden.
3. **Keine UI-sichtbare Änderung:** Der `{#if suggested}`-Branch war in der Praxis nie aktiv
   (alle Aufrufer übergaben `suggested={false}`), also kein Regressions-Risiko bei der UI.
