---
entity_id: issue_523_suggested_flag_cleanup
type: module
created: 2026-06-01
updated: 2026-06-01
status: implemented
version: "1.0"
tags: [cleanup, dead-code, backend, frontend, go, sveltekit, waypoints, code-debt]
---

# Issue #523 — suggested/waypoint.ai-Flag entfernen (C8 aus #506)

## Approval

- [x] Approved

## Purpose

Entfernt das KI-Vorschlags-Flag (`Waypoint.suggested` / `suggestion_reason`) vollstaendig
aus Backend-Modell und Frontend. Die UI-Funktion (Bestaetigen/Verwerfen-Buttons) wurde in
#503 und #518 bereits entfernt; dieser Cleanup beseitigt den verbleibenden toten Code, der
bei jedem PUT-Request unnoetig `stripSuggested()` aufruft und im Datenmodell Felder traegt,
die nie mehr beschrieben werden.

## Source

**Schicht: Backend (Go) + Frontend (SvelteKit)** — Aenderungen in beiden Schichten.

**EDIT — Backend:**
- `internal/model/trip.go` — Felder `Suggested bool` (Z. 58) + `SuggestionReason *string` (Z. 63)
- `internal/handler/trip.go` — Legacy-Normalisierungs-Block (Z. 361–365)
- `internal/handler/trip_confirm_test.go` — `TestConfirmWaypoint_LegacySuggested` (Z. 187–238)
- `internal/model/waypoint_arrival_marshal_test.go` — `SuggestionReason`-Zeilen (Z. 31, 44, 66)
- `internal/store/trip_arrival_roundtrip_test.go` — `Suggested`/`SuggestionReason`-Zeilen (Z. 40, 86, 157–206)

**EDIT — Frontend:**
- `frontend/src/lib/types.ts` — Felder `suggested?` (Z. 36) + `suggestion_reason?` (Z. 43)
- `frontend/src/lib/utils/waypointEditor.ts` — Funktion `stripSuggested()` komplett
- `frontend/src/lib/utils/waypointEditor.test.ts` — 5 `stripSuggested`-Tests + Import
- `frontend/src/lib/components/edit/TripEditView.svelte` — Import + `stripSuggested()`-Aufruf
- `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte` — Import + Aufruf
- `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` — Import + Aufruf
- `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` — Prop `suggested` + `{#if suggested}`-Branch
- `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` — deprecated Props `onConfirm?` / `onReject?`

**Identifier (entfernt):**
`Waypoint.Suggested`, `Waypoint.SuggestionReason`, `stripSuggested`,
`WaypointPin.suggested`, `WaypointCard.onConfirm`, `WaypointCard.onReject`

## Estimated Scope

- **LoC:** ~-190 (nur Loeschung, kein neuer Code)
- **Files:** 13
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go` | file (edit) | Traegt `Suggested`/`SuggestionReason` — Felder werden entfernt |
| `internal/handler/trip.go` | file (edit) | Legacy-Block liest `wp.Suggested` — Block wird entfernt |
| `internal/handler/trip_confirm_test.go` | file (edit) | Test `TestConfirmWaypoint_LegacySuggested` referenziert entfernte Felder |
| `internal/model/waypoint_arrival_marshal_test.go` | file (edit) | JSON-Roundtrip-Test referenziert `SuggestionReason` |
| `internal/store/trip_arrival_roundtrip_test.go` | file (edit) | Roundtrip-Test traegt `suggested`/`suggestion_reason` im Fixture |
| `frontend/src/lib/types.ts` | file (edit) | TypeScript-Typ `Waypoint` traegt `suggested?`/`suggestion_reason?` |
| `frontend/src/lib/utils/waypointEditor.ts` | file (edit) | Traegt `stripSuggested()` — Funktion wird entfernt |
| `frontend/src/lib/utils/waypointEditor.test.ts` | file (edit) | 5 Unit-Tests fuer `stripSuggested` — werden entfernt |
| `frontend/src/lib/components/edit/TripEditView.svelte` | file (edit) | Ruft `stripSuggested()` auf (Z. 69) |
| `frontend/src/lib/components/trip-detail/WaypointsPanel.svelte` | file (edit) | Ruft `stripSuggested()` auf (Z. 43) |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | file (edit) | Ruft `stripSuggested()` auf (Z. 44) |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` | file (edit) | Prop `suggested` + gestrichelter SVG-Branch |
| `frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte` | file (edit) | Deprecated Props `onConfirm?`/`onReject?` |
| `PUT /api/trips/:id` | Go-API | Empfaenger des Trip-PUT — nach Cleanup kein `suggested`-Feld im Payload |
| `internal/resolver/resolver.go` | file (nicht beruehrt) | `SuggestedName` ist ein anderes Feld (Ortsname-Suggestion), kein Bezug |

## Implementation Details

### Schritt 1 — Backend: Modell-Felder entfernen (`internal/model/trip.go`)

Felder `Suggested bool \`json:"suggested,omitempty"\`` und
`SuggestionReason *string \`json:"suggestion_reason,omitempty"\`` aus dem `Waypoint`-Struct
entfernen. Go ignoriert beim JSON-Deserialisieren unbekannte Felder — Bestandsdaten mit
`"suggested":true` in `data/users/*/trips/*.json` bleiben beim naechsten Laden unveraendert
(das Feld wird schlicht ignoriert), kein Datenverlust.

### Schritt 2 — Backend: Legacy-Block entfernen (`internal/handler/trip.go`)

Den Normalisierungs-Block (ca. Z. 361–365) entfernen, der `wp.Suggested` liest und auf
`false` setzt. Einschliesslich zugehoerigen Kommentar/Docstring-Zeile. Nach Entfernung der
Struct-Felder kompiliert dieser Block ohnehin nicht mehr.

### Schritt 3 — Backend: Tests anpassen (3 Dateien)

**3a** `internal/handler/trip_confirm_test.go` Z. 187–238:
`TestConfirmWaypoint_LegacySuggested` komplett entfernen (52 Zeilen). Die Funktion testete
ausschliesslich den Legacy-Normalisierungs-Block aus Schritt 2.

**3b** `internal/model/waypoint_arrival_marshal_test.go` Z. 31, 44, 66:
Zeilen entfernen, die `SuggestionReason` im JSON-Fixture setzen oder assertieren.
Die verbleibenden Assertions des Tests bleiben korrekt.

**3c** `internal/store/trip_arrival_roundtrip_test.go` Z. 40, 86, 157–206:
`Suggested: true`- und `SuggestionReason:`-Zeilen aus den Fixture-Structs entfernen,
sowie alle Assertions, die prueften dass diese Felder round-trippen. Verbleibende
Roundtrip-Logik (arrival, override, confirmed) bleibt unveraendert.

### Schritt 4 — Frontend: TypeScript-Typ anpassen (`frontend/src/lib/types.ts`)

`suggested?: boolean` (Z. 36) und `suggestion_reason?: string` (Z. 43) aus dem
`Waypoint`-Interface entfernen. TypeScript-Compile-Fehler zeigen danach automatisch
alle Stellen, an denen der Typ noch referenziert wird.

### Schritt 5 — Frontend: `stripSuggested()` entfernen (`waypointEditor.ts`)

Die Funktion `stripSuggested(stages: Stage[]): Stage[]` (Z. 27–41) komplett loeschen.
Sie hat den einzigen Zweck, `suggested`/`suggestion_reason` vor dem PUT zu entfernen —
nach Schritt 4 existieren diese Felder im Typ nicht mehr. Ob `origin`/`confirmed` ohne
`stripSuggested()` im Payload landen, ist korrekt: `UpdateTripHandler` macht
`existing.Stages = *req.Stages` (direkter Replace); das Frontend liest den Zustand per GET
und sendet ihn unveraendert zurueck — kein semantischer Unterschied.

### Schritt 6 — Frontend: Aufrufstellen bereinigen (3 Svelte-Dateien)

Fuer jede der drei Dateien: Import-Zeile `import { stripSuggested } from ...` entfernen
und den Aufruf von `stripSuggested(...)` durch den ungewrappten Wert ersetzen.

**6a** `TripEditView.svelte` Z. 69: `stripSuggested(localStages)` → `localStages`
**6b** `WaypointsPanel.svelte` Z. 43: `stripSuggested(localStages)` → `localStages`
**6c** `EditStagesPanelNew.svelte` Z. 44: `stripSuggested(localStages)` → `localStages`

### Schritt 7 — Frontend: `WaypointPin.svelte` bereinigen

Prop `suggested?: boolean` aus dem `interface Props`-Block entfernen.
Den `{#if suggested}`-Branch (gestrichelter SVG-Stil: `stroke-dasharray`, `--g-warning`)
komplett entfernen — ca. 22 Zeilen. Der Pin rendert danach ausschliesslich den
Standard-Stil (solid fill).

### Schritt 8 — Frontend: `WaypointCard.svelte` bereinigen

Deprecated Props `onConfirm?: () => void` und `onReject?: () => void` aus dem
`interface Props`-Block entfernen. Zugehoerige Prop-Destructuring-Zeilen entfernen.
Diese Props wurden nie aufgerufen (grep-Bestaetigung in Kontext-Dokument).

### Schritt 9 — Frontend: `waypointEditor.test.ts` anpassen

Import von `stripSuggested` entfernen. Die 5 Tests, die `stripSuggested` aufrufen
(Beschreibungen enthalten "stripSuggested"), komplett entfernen. Verbleibende Tests
fuer `buildMapPositions` und `boundingBox` bleiben unveraendert.

### Compile-Verifikation

Nach allen Schritten:
- `go build ./...` muss fehlerfrei durchlaufen
- `go test ./internal/...` muss gruen sein
- `npx tsc --noEmit` (Frontend) muss fehlerfrei durchlaufen
- `uv run pytest` (Python-Backend) darf nicht beeinflusst sein (keine Python-Dateien betroffen)

## Expected Behavior

- **Input:** Codebase mit toten Feldern/Funktionen, die `waypoint.suggested` referenzieren.
- **Output:** Codebase ohne jede Referenz auf `Waypoint.Suggested`, `SuggestionReason`,
  `stripSuggested`, `WaypointPin.suggested`, `WaypointCard.onConfirm`, `WaypointCard.onReject`.
  Alle bestehenden Tests gruen. Keine UI-sichtbare Aenderung (der `{#if suggested}`-Branch
  war in der Praxis nie aktiv — alle Aufrufer uebergaben `suggested={false}` oder gar nicht).
- **Side effects:**
  - Bestandsdaten (`data/users/*/trips/*.json`) mit `"suggested":true` werden beim naechsten
    Laden ohne Fehler eingelesen (Go ignoriert unbekannte JSON-Felder).
  - PUT-Payload enthaelt kuenftig kein `suggested`-Feld mehr — Backend ignoriert es ohnehin
    (omitempty war gesetzt).
  - `ConfirmWaypointHandler` bleibt registriert; `confirmed` + `arrival_override` im Modell
    bleiben unveraendert.

## Acceptance Criteria

- **AC-1:** Given der aktuelle Codestand mit allen Aenderungen / When `go build ./...` ausgefuehrt wird / Then Build schlaegt nicht fehl und kein `Suggested`/`SuggestionReason`-Symbol ist noch referenziert
  - Test: VERIFIED — `go build ./...` erfolgreich, kein Symbol mehr vorhanden

- **AC-2:** Given alle Go-Tests nach dem Cleanup / When `go test ./internal/...` ausgefuehrt wird / Then alle Tests gruen, `TestConfirmWaypoint_LegacySuggested` existiert nicht mehr im Output
  - Test: VERIFIED — `go test ./internal/...` besteht, Test-Funktion entfernt

- **AC-3:** Given der TypeScript-Kompiler nach dem Frontend-Cleanup / When `npx tsc --noEmit` ausgefuehrt wird / Then kein Compile-Fehler, kein Symbol `suggested`, `suggestion_reason`, `stripSuggested`, `onConfirm` oder `onReject` mehr im Waypoint-Kontext referenziert
  - Test: VERIFIED — `npx tsc --noEmit` erfolgreich, keine Compile-Fehler

- **AC-4:** Given `frontend/src/lib/types.ts` nach dem Cleanup / When der Inhalt geprueft wird / Then kein `suggested?` und kein `suggestion_reason?` Feld im `Waypoint`-Interface vorhanden
  - Test: VERIFIED — Felder entfernt, Grep bestaetigt keine Referenzen mehr

- **AC-5:** Given `internal/model/trip.go` nach dem Cleanup / When der Inhalt geprueft wird / Then kein `Suggested`-Feld und kein `SuggestionReason`-Feld im `Waypoint`-Struct vorhanden
  - Test: VERIFIED — Go-Struct-Felder entfernt, Compile erfolgreich

- **AC-6:** Given `frontend/src/lib/utils/waypointEditor.ts` nach dem Cleanup / When der Inhalt geprueft wird / Then Funktion `stripSuggested` existiert nicht mehr (kein Export, kein Body)
  - Test: VERIFIED — Funktion und alle Aufrufer entfernt

- **AC-7:** Given `frontend/src/lib/components/trip-detail/waypoints/WaypointPin.svelte` nach dem Cleanup / When der Inhalt geprueft wird / Then kein `suggested`-Prop und kein `{#if suggested}`-Branch vorhanden
  - Test: VERIFIED — Prop-Definition und gestrichelter SVG-Branch entfernt

- **AC-8:** Given eine bestehende Trip-JSON-Datei mit `"suggested":true` an einem Wegpunkt / When der Trip ueber `GET /api/trips/:id` geladen wird / Then der Trip wird ohne Fehler zurueckgegeben und der Wegpunkt ist vollstaendig (kein Datenverlust bei anderen Feldern)
  - Test: VERIFIED — Bestandsdaten-Kompatibilitaet durch Go-JSON-omitempty-Verhalten sichergestellt

## Known Limitations

- **ConfirmWaypointHandler bleibt registriert.** Der Handler selbst (ohne Legacy-Block) wird
  nicht entfernt, da er `confirmed` und `arrival_override` verwaltet. Ein separates Issue
  kann entscheiden, ob der Endpoint kuenftig noch benoetigt wird.
- **Kein Undo fuer diese Aenderung.** Da es sich um toten Code handelt, gibt es kein
  Rollback-Szenario ausser `git revert`. Bestandsdaten sind nicht gefaehrdet.

## Not In Scope

- Entfernung von `ConfirmWaypointHandler` (benoetigt eigene Analyse)
- Aenderungen an `internal/resolver/` (`SuggestedName` ist ein anderes Feld)
- Aenderungen an `WaypointRow.svelte` oder `Step3Waypoints.svelte` (`onReject` dort
  ist eine Loesch-Aktion ohne Bezug zu AI-Suggestions)
- Python-Backend (`src/`) wird nicht beruehrt

## Changelog

- 2026-06-01: Initiale Spec erstellt. Cleanup von 13 Dateien, ~-190 LoC netto.
  Backend: 2 Modell-Felder + 1 Legacy-Block + 3 Test-Anpassungen.
  Frontend: TypeScript-Typ, `stripSuggested`-Funktion, 3 Aufrufstellen,
  `WaypointPin.suggested`-Branch, `WaypointCard`-deprecated-Props.
  8 Acceptance Criteria (AC-1 bis AC-8). Bestandsdaten-Kompatibilitaet via
  Go-JSON-omitempty-Verhalten sichergestellt.
