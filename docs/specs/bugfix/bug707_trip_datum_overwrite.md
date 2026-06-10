---
entity_id: bug707_trip_datum_overwrite
type: bugfix
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, trip, stages, data-integrity, partial-update]
---

# Bug #707 — Trip-Datum-Änderungen werden durch spätere Speicheroperationen überschrieben

## Approval

- [ ] Approved

## Problem

Zwei Komponenten senden beim Speichern den kompletten `trip`-Spread als Request-Body
an `PUT /api/trips/{id}`, obwohl sie nur ein einzelnes Feld ändern wollen. Wenn
zwischenzeitlich Etappen-Daten gespeichert wurden, enthält `trip` noch den alten
Stage-Stand aus dem initialen Seiten-Load — dieser veralte Stand überschreibt die
neu gespeicherten Stage-Daten (z.B. angepasste Etappen-Daten) still und unwiederbringlich.

## Source

- **File:** `frontend/src/lib/components/trip-detail/TripHeader.svelte`
- **Identifier:** `makeNameSaveHandler` (Zeile 36)

- **File:** `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte`
- **Identifier:** `makeSaveHandler` (Zeile 31)

## Estimated Scope

- **LoC:** ~2 geänderte Zeilen (je eine pro Datei)
- **Files:** 2
- **Effort:** low

## Root Cause

Beide Aufrufe nutzen `{ ...trip, <feld>: neuerWert }` als Request-Body:

```typescript
// TripHeader.svelte:36 — FALSCH
await api.put(`/api/trips/${trip.id}`, { ...trip, name: editName });

// BriefingScheduleTab.svelte:31 — FALSCH
await api.put<Trip>(`/api/trips/${trip.id}`, { ...trip, report_config: reportConfig });
```

`trip` ist der Zustand beim Seiten-Load. Wenn der Nutzer in der Zwischenzeit auf
dem Etappen-Tab Datumsfelder ändert und speichert, kennt `TripHeader` / `BriefingScheduleTab`
diese neuen Werte nicht — `trip.stages` ist veraltet. Der spread überschreibt den
aktuellen DB-Stand mit dem alten.

Das Go-Backend (`internal/handler/trip.go`, `UpdateTripHandler`) akzeptiert `stages`
im Request-Body und merged nur Pointer-Felder, die nicht `nil` sind. Ein gefülltes
`stages`-Array aus dem Spread wird also als neue Wahrheit behandelt und überschreibt
die aktuellen Stage-Daten in der Datenbank.

## Fix

Nur das tatsächlich geänderte Feld im Request-Body senden:

```typescript
// TripHeader.svelte:36 — KORREKT
await api.put(`/api/trips/${trip.id}`, { name: editName });

// BriefingScheduleTab.svelte:31 — KORREKT
await api.put<Trip>(`/api/trips/${trip.id}`, { report_config: reportConfig });
```

Der lokale `onTripUpdate`-Callback (der den In-Memory-State der Seite updatet) bleibt
unverändert — dort ist der `trip`-Spread korrekt, weil er nur den UI-State neu
konstruiert, nicht die Datenbank beschreibt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripHeader.svelte` | Frontend-Komponente | Enthält `makeNameSaveHandler` — PUT-Aufruf zum Umbenennen |
| `BriefingScheduleTab.svelte` | Frontend-Komponente | Enthält `makeSaveHandler` — PUT-Aufruf zum Speichern des Briefing-Zeitplans |
| `internal/handler/trip.go` | Go-API | `UpdateTripHandler`: Pointer-basiertes Merge-Schema — kein Change nötig, Backend ist korrekt |
| `api.put` | Frontend-Utility | HTTP-Client (`$lib/api.js`) — sendet JSON-Body an Go-API |

## Expected Behavior

- **Input:** PUT `/api/trips/{id}` mit minimalem Body — nur das tatsächlich geänderte Feld (`name` bzw. `report_config`)
- **Output:** Go-Backend merged ausschließlich das gesendete Feld; alle anderen Felder (insbesondere `stages`) bleiben unverändert
- **Side effects:** `onTripUpdate`-Callback updatet weiterhin den lokalen React-ähnlichen State der Seite — bleibt unverändert

## Acceptance Criteria

**AC-1:** Given ein Trip mit angepasstem Stage-Datum (Etappe gespeichert, Datum abweichend vom initialen Load-Zustand) / When der Nutzer den Trip-Namen bearbeitet und „Umbenennen" bestätigt / Then zeigt die Seite nach dem nächsten Laden das korrekte (zuletzt gespeicherte) Stage-Datum — kein Revert auf den alten Stand.
- Test: Playwright-E2E gegen Staging: Stage-Datum ändern + speichern, dann Trip umbenennen, dann Seite neu laden und Datum prüfen. Rot-vor-Fix (Datum wird zurückgesetzt), grün-nach-Fix (Datum bleibt).

**AC-2:** Given ein Trip mit angepasstem Stage-Datum (Etappe gespeichert) / When der Nutzer den Briefing-Zeitplan im Tab „Briefing & Zeitplan" speichert / Then zeigt die Seite nach dem nächsten Laden das korrekte Stage-Datum — kein Revert.
- Test: Playwright-E2E gegen Staging: Stage-Datum ändern + speichern, dann Briefing-Zeitplan speichern, dann Seite neu laden und Datum prüfen. Rot-vor-Fix (Datum wird zurückgesetzt), grün-nach-Fix (Datum bleibt).

**AC-3:** Given ein Trip mit mehreren Etappen / When der Nutzer nur den Trip-Namen ändert (keine Etappen-Edits) / Then sind nach dem Speichern alle Etappen unverändert (Anzahl, IDs und Daten identisch zu vorher) — kein Stage-Verlust.
- Test: Playwright-E2E gegen Staging: Trip mit mind. 2 Etappen umbenennen, danach GET `/api/trips/{id}` absetzen und `stages`-Array auf Länge + ID-Gleichheit prüfen.

**AC-4:** Given ein Trip-Name-Save und ein Briefing-Zeitplan-Save in derselben Sitzung / When beide Operationen nacheinander ausgeführt werden / Then enthält der finale DB-Zustand die Änderungen beider Operationen ohne gegenseitige Überschreibung.
- Test: Playwright-E2E: Trip umbenennen → speichern; Briefing-Zeitplan ändern → speichern; Seite neu laden; prüfen, dass neuer Name UND neuer Briefing-Zeitplan gespeichert sind.

## Known Limitations

- Der `onTripUpdate`-Callback aktualisiert den lokalen UI-State weiterhin mit `{ ...trip, name: editName }`. Dieser lokale State kann somit immer noch veraltete `stages` aus dem initialen Load tragen, falls Stage-Änderungen in einem anderen Tab vorgenommen wurden. Da der lokale State jedoch beim nächsten Seiten-Load neu aus der API bezogen wird, ist dies kein Datenverlust-Risiko, sondern allenfalls ein temporäres Stale-Display in der laufenden Session. Ein vollständiges Re-Fetch nach jedem Save wäre die sauberere Lösung, ist aber Out of Scope für diesen Bug-Fix.

## Changelog

- 2026-06-10: Initial spec created (Bug #707 — Trip-Datum-Overwrite durch stalen `trip`-Spread)
