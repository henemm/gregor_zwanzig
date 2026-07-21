---
entity_id: bug_601_round_trip_catchblocks
type: module
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [bug, frontend, backend, quality]
---

# Bug #601: Round-Trip-Validierung und stille Catch-Blöcke

## Approval

- [ ] Approved

## Purpose

Zwei verwandte Bug-Klassen systematisch beheben: (1) API-Fehler werden in leeren `catch {}`-Blöcken
im Frontend verschluckt — ohne Log, ohne Nutzer-Feedback. (2) Backend-Validatoren sind auf
Round-Trip-Konsistenz auditiert; fehlende Round-Trip-Tests werden ergänzt.
Der `profil`-Bug in `compare_preset.go` wurde bereits durch #591 behoben.

## Source

- **Frontend:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts:131`
- **Frontend:** `frontend/src/routes/trips/[id]/+page.svelte:110`
- **Frontend:** `frontend/src/lib/components/compare/CompareTabs.svelte:42`
- **Frontend:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte:232`
- **Frontend:** `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte:90`
- **Backend:** `internal/handler/subscription.go` — `validateSubscription`
- **Backend:** `internal/handler/location.go` — `validateLocation`
- **Backend:** `internal/handler/trip.go` — `validateTrip`

## Estimated Scope

- **LoC:** ~80
- **Files:** 8 (5 Svelte/TS + 3 Go-Testdateien)
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/compare_preset.go` | Fixed | `normalizeProfile` bereits in #591 ergänzt |
| `internal/handler/compare_preset_test.go` | Fixed | Round-Trip-Tests für profil bereits in #591 |

## Implementation Details

### Frontend: `console.error(e)` in allen API-catch-Blöcken

Alle catch-Blöcke die API-Calls abfangen müssen mindestens `console.error(e)` enthalten.
Bei Mutation-Calls (PUT/POST) zusätzlich sichtbares Nutzer-Feedback wenn sinnvoll.

Betroffene catch-Blöcke (API-Calls):

| Datei | Zeile | API-Call | Mutation | Priorität |
|-------|-------|----------|----------|-----------|
| `compareWizardState.svelte.ts` | 131 | `PUT /api/subscriptions/{id}` | Ja | Hoch |
| `trips/[id]/+page.svelte` | 110 | `POST /api/scheduler/trip-reports` | Ja | Mittel |
| `CompareTabs.svelte` | 42 | `GET /api/auth/profile` | Nein | Niedrig |
| `WeatherMetricsTab.svelte` | 232 | `GET /api/metrics/snapshot` | Nein | Niedrig |
| `Step3Weather.svelte` | 90 | `GET /api/metrics` | Nein | Niedrig |

Catch-Blöcke die bereits Nutzer-Feedback enthalten und NICHT geändert werden:
- `CompareGrid.svelte:54` — zeigt `'Löschen fehlgeschlagen'`
- `compare/[id]/+page.svelte:40` — zeigt `'Netzwerkfehler'`
- `account/+page.svelte` — hat Fehler-State-Variablen
- `LocationNewModal.svelte:47` — UI-Preview-Fallback, kein API-Fehler
- `previewHelpers.ts:52` — JSON.parse-Fallback, kein API-Call

### Backend: Round-Trip-Tests für verbleibende Validator-Funktionen

Pattern: POST (create) → GET (read) → PUT (unverändert) → 200 erwarten.

Auditbefund der Validator-Funktionen:
- `validateLocation` — validiert ID, Name, Koordinaten; keine Enum-Felder → kein Round-Trip-Risiko
- `validateTrip` — validiert ID, Name, Waypoint-Koordinaten; keine Enum-Felder → kein Round-Trip-Risiko
- `validateSubscription` — `activity_profile` validiert gegen Kleinbuchstaben-Set → konsistent mit Speicherformat → kein Round-Trip-Risiko, aber Test fehlt

Neue Testdateien:
- `internal/handler/subscription_roundtrip_test.go`
- `internal/handler/location_roundtrip_test.go`
- `internal/handler/trip_roundtrip_test.go`

## Expected Behavior

- **Frontend:** Jeder catch-Block der einen API-Fehler schluckt, loggt `console.error(e)` → sichtbar im Browser-DevTools
- **Frontend:** PUT-Fehler beim Subscription-Toggle schlägt nicht mehr lautlos fehl
- **Backend:** Für alle drei verbleibenden CRUD-Handler existiert ein Round-Trip-Test der POST→GET→PUT→200 durchläuft

## Acceptance Criteria

**AC-1:** Given ein Frontend-catch-Block der einen API-Call umschließt / When der API-Call fehlschlägt / Then ist der Fehler per `console.error(e)` im Browser-DevTools sichtbar (gilt für alle 5 betroffenen Stellen)

**AC-2:** Given ein bestehender Subscription-Datensatz per POST angelegt / When ein PUT mit identischem Body ausgeführt wird / Then antwortet der Handler mit HTTP 200 (Round-Trip-Test in Go)

**AC-3:** Given ein bestehender Location-Datensatz per POST angelegt / When ein PUT mit identischem Body ausgeführt wird / Then antwortet der Handler mit HTTP 200 (Round-Trip-Test in Go)

**AC-4:** Given ein bestehender Trip-Datensatz per POST angelegt / When ein PUT mit identischem Body ausgeführt wird / Then antwortet der Handler mit HTTP 200 (Round-Trip-Test in Go)

**AC-5:** Given der Subscription-Validator `validateSubscription` / When `activity_profile: "allgemein"` (Kleinbuchstaben) übergeben wird / Then ist die Validierung erfolgreich (Audit-Nachweis via Test)

## Known Limitations

- `compareWizardState.svelte.ts:131` hat explizit keinen User-facing Error-State vorgesehen.
  Wir ergänzen nur `console.error(e)`, kein Toast — der Kommentar erklärt das Design.
- Round-Trip-Tests für Location und Trip testen nur die Validator-Ebene (kein Datenverlust-Risiko
  da keine Enum-Felder), dienen als Regressionsnetz.

## Changelog

- 2026-06-04: Spec erstellt nach Bug-Analyse #601
