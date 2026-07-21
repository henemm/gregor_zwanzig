---
entity_id: issue_230_aggregation_mismatch
type: bugfix
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, types, bug, data-flow]
---

# Issue #230 — Bug: aggregation.profile vs activity_profile Mismatch

## Approval

- [ ] Approved

## Purpose

Frontend Read-Pfade in `rightColumn.ts` (Trip-Detail rechte Spalte) lesen `trip.aggregation?.activity_profile`. Live-Daten haben das Feld aber als `profile`. Konsequenz: Read-Pfade bekommen für **jeden** Trip `undefined` zurück und fallen auf generische Defaults. Sichtbares Symptom:
- Wetter-Metriken-Card zeigt für jeden Trip `'Standard-Metriken'` statt z.B. `'Wintersport-Standard'` (siehe `rightColumn.ts:17-22`).
- `getActiveMetrics()` gibt `[]` zurück, wenn `weather_config.metrics` nicht gesetzt ist (Profil-Default-Fallback greift nicht).

Fix: Read-Pfade + Interface auf `profile` umstellen — die Form, die in der DB liegt und vom Python-Backend kanonisch genutzt wird.

## Source

- **File:** `frontend/src/lib/utils/rightColumn.ts` (Zeilen 17, 44, 47)
- **File:** `frontend/src/lib/types.ts` (`Aggregation` Interface)
- **Identifier:** `interface Aggregation`, `getPresetLabel()`, `getActiveMetrics()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `data/users/*/trips/*.json` | Live-Daten | Format ist `aggregation: { profile: '...' }` |
| `src/app/loader.py` | Python-Backend (Read/Write) | Liest und schreibt `profile` als kanonische Form |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts:335` | Frontend-Wizard | Schreibt bereits `profile` (korrekt — bleibt unverändert) |
| `internal/handler/trip.go` / `internal/model/trip.go` | Go-Backend | Pass-Through (`map[string]interface{}`), keine Validierung |

## Implementation Details

### `frontend/src/lib/types.ts` — Aggregation umbenennen

```typescript
export interface Aggregation {
    profile?: ActivityProfile;     // statt activity_profile
}
```

### `frontend/src/lib/utils/rightColumn.ts` — 3 Stellen

```typescript
// Zeile 17 (getPresetLabel)
const profile = trip.aggregation?.profile;     // statt ?.activity_profile

// Zeile 44 (getActiveMetrics — Array vorhanden, aber Non-Strings)
const profile = trip.aggregation?.profile;

// Zeile 47 (getActiveMetrics — Array nicht vorhanden)
const profile = trip.aggregation?.profile;
```

### `frontend/src/lib/utils/rightColumn.test.ts` — Test-Fixtures

Test-Fixtures, die `aggregation: { activity_profile: '...' }` aufbauen, auf `profile` umstellen.

### `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts:333-336` — Escape entfernen

```typescript
// Vorher:
// TODO #230 — Mismatch noch nicht migriert
trip.aggregation = { profile: mapActivityToProfile(this.activity) } as unknown as Aggregation;

// Nachher:
trip.aggregation = { profile: mapActivityToProfile(this.activity) };
```

### `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts:74` — Cast entfernen

```typescript
// Vorher: (trip.aggregation as { profile: string }).profile
// Nachher: trip.aggregation?.profile
```

## Expected Behavior

- **Input:** Trip mit `aggregation: { profile: 'wintersport' }` (Standard-Format aller Live-Trips).
- **Output:**
  - `getPresetLabel(trip)` → `'Wintersport-Standard'`
  - `getActiveMetrics(trip)` → 6 Wintersport-Default-Metriken, wenn `weather_config.metrics` leer ist
  - Wetter-Metriken-Card auf Trip-Detail-Seite zeigt korrektes Profil-Label und passende Default-Metrik-Liste
- **Side effects:** Keine. JSON-Wire-Format unverändert (war schon immer `profile`). Backend unverändert.

## Acceptance Criteria

- **AC-1:** Given Live-Trip mit `aggregation: { profile: 'wintersport' }` / When Frontend lädt Trip-Detail-Seite / Then Wetter-Metriken-Card zeigt `'Wintersport-Standard'` als Preset-Label
  - Test: `rightColumn.test.ts::getPresetLabel returns 'Wintersport-Standard' for wintersport-trip`

- **AC-2:** Given Trip ohne `weather_config.metrics` und `aggregation.profile = 'wintersport'` / When `getActiveMetrics(trip)` aufgerufen wird / Then 6 Wintersport-Default-Metriken zurückgegeben (nicht leeres Array)
  - Test: `rightColumn.test.ts::getActiveMetrics falls back to profile defaults`

- **AC-3:** Given `Aggregation`-Interface in `types.ts` / When `grep -rn "aggregation.\?\.activity_profile" frontend/src/` / Then 0 Treffer im Production-Code (`src/`, ausgenommen Tests, die explizit Off-Spec-Cases dokumentieren)
  - Test: Grep-Check

- **AC-4:** Given Wizard-Schreibpfad / When `wizardState.svelte.ts:335` / Then keine `as unknown as Aggregation`-Escape mehr, `TODO #230`-Marker entfernt
  - Test: Grep auf `TODO #230` im Production-Code → 0 Treffer

- **AC-5:** Given Frontend-Tests / When `node --experimental-strip-types --test frontend/src/lib/utils/rightColumn.test.ts frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` / Then alle grün
  - Test: Test-Run

- **AC-6:** Given Staging-Trip via `/api/trips` / When durch `getPresetLabel` gerendert / Then nicht-trivialer Preset-Name (nicht `'Standard-Metriken'` für jeden Trip)
  - Test: Manueller Smoke gegen Staging nach Push

## Known Limitations

- **Keine Datenmigration nötig:** DB-Files haben bereits `profile`. Frontend liest jetzt auch `profile`. Es gibt keine Trips mit `activity_profile` in der DB (verifiziert via Staging-API-Roundtrip in #207).
- Falls in Zukunft Trips über andere Wege importiert werden (z.B. CSV, externe API), muss derselbe Feldname verwendet werden.

## Changelog

- 2026-05-16: Initial spec created
