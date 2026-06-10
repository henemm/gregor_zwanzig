---
entity_id: bug720_tripeditview_spread_fix
type: bugfix
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, trip, data-integrity, partial-update, tripeditview]
---

# Bug #720 — TripEditView: { ...trip, ... } Anti-Pattern entfernen

## Approval

- [ ] Approved

## Problem

`TripEditView.svelte` baut in `makeSaveHandler()` (Zeilen 66–91) den PUT-Body als
`const updated: Trip = { ...trip, name, stages, report_config, alert_rules }` und
sendet das vollständige Objekt an `PUT /api/trips/{id}`. Der `...trip`-Spread
schleppt alle beim Seiten-Load geladenen Felder mit — darunter `display_config`,
`activity`, `region`, `aggregation` und `weather_config` — auch wenn sie in
`TripEditView` nie bearbeitet werden. Wenn `WeatherMetricsTab` in derselben Sitzung
ein neues `display_config` gespeichert hat, überschreibt der nächste Speicher-Vorgang
über `TripEditView` diesen Stand still mit dem veralteten Snapshot.

Ein Code-Kommentar in Zeilen 75–77 besagt explizit „display_config KEIN
Überschreiben" — der `...trip`-Spread macht genau das Gegenteil.

## Source

- **File:** `frontend/src/lib/components/edit/TripEditView.svelte`
- **Identifier:** `makeSaveHandler` (Zeilen 66–91)

## Estimated Scope

- **LoC:** ~4 geänderte Zeilen
- **Files:** 1
- **Effort:** low

## Root Cause

`makeSaveHandler` baut einen Intermediate-Object mit dem vollständigen `trip`-Spread:

```typescript
// TripEditView.svelte:71–81 — FALSCH
const updated: Trip = {
    ...trip,               // staler Snapshot — incl. display_config, activity, region, etc.
    name: tripName,
    stages: stages,
    report_config: reportConfig,
    alert_rules: alertRules,
};
await api.put(`/api/trips/${trip.id}`, updated);
goto('/trips');
```

`trip` ist der Zustand beim Seiten-Load. Felder wie `display_config`, die
`TripEditView` nie bearbeitet, werden via Spread trotzdem mit dem veralteten
Load-Stand in den PUT-Body aufgenommen. Das Go-Backend (`UpdateTripHandler`) behandelt
jeden gesendeten Wert als neue Wahrheit — der Spread überschreibt eine zwischenzeitlich
gespeicherte `display_config` ohne Warnung.

Dasselbe Anti-Pattern wurde bereits in `TripHeader.svelte` und
`BriefingScheduleTab.svelte` (Issue #707) sowie `WaypointsPanel.svelte` (Issue #717)
behoben. `TripEditView` ist der vierte Fundort.

## Fix

Das `const updated`-Intermediate-Object entfernen und nur die 4 tatsächlich
bearbeiteten Felder direkt im `api.put`-Aufruf senden:

```typescript
// TripEditView.svelte:71–81 — KORREKT
await api.put(`/api/trips/${trip.id}`, {
    name: tripName,
    stages: stages,
    report_config: reportConfig,
    alert_rules: alertRules,
});
goto('/trips');
```

Der Go-`UpdateTripHandler` wendet ein Pointer-basiertes Merge-Schema an: nur
gesendete Felder werden übernommen, alle übrigen Felder (`display_config`, `activity`,
`region`, `aggregation`, `weather_config`) bleiben unverändert. Der minimale Body ist
daher ausreichend und korrekt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripEditView.svelte` | Frontend-Komponente | Enthält `makeSaveHandler` — zu ändernder PUT-Aufruf |
| `internal/handler/trip.go` | Go-API | `UpdateTripHandler`: Pointer-basiertes Merge-Schema — kein Change nötig, Backend ist korrekt |
| `api.put` | Frontend-Utility | HTTP-Client (`$lib/api.js`) — sendet JSON-Body an Go-API |
| `bug707_trip_datum_overwrite.md` | Spec | Präzedenz: identischer Fix für TripHeader + BriefingScheduleTab |
| `bug717_waypointspanel_spread_fix.md` | Spec | Letzte Präzedenz: identischer Fix für WaypointsPanel |

## Expected Behavior

- **Input:** PUT `/api/trips/{id}` mit Body `{ name: tripName, stages, report_config: reportConfig, alert_rules: alertRules }` — ausschließlich die von `TripEditView` tatsächlich bearbeiteten Felder
- **Output:** Go-Backend merged nur die 4 gesendeten Felder; alle anderen Trip-Felder (`display_config`, `activity`, `region`, `aggregation`, `weather_config`) bleiben unverändert
- **Side effects:** `goto('/trips')` navigiert nach dem Speichern weg — kein gleichzeitiger In-Tab-Save-Konflikt möglich

## Acceptance Criteria

**AC-1:** Given `TripEditView.svelte` enthält `makeSaveHandler` / When der Quellcode auf das Anti-Pattern `{ ...trip,` in einem `api.put()`-Aufruf geprüft wird / Then ist dieses Muster nicht vorhanden — der stale Spread wurde entfernt.
- Test: `# doc-compliance-test` — prüft via Dateiinhalt-Analyse, dass `{ ...trip,` in keinem `api.put`-Aufruf in `TripEditView.svelte` vorkommt. Rot vor Fix (Muster vorhanden), grün nach Fix (Muster entfernt). Gilt als Source-Code-Compliance-Guard für Anti-Pattern-Regression.

**AC-2:** Given `TripEditView.svelte` enthält `makeSaveHandler` / When der Quellcode auf den korrekten minimalen PUT-Body geprüft wird / Then sendet `api.put` exakt `{ name: tripName, stages, report_config: reportConfig, alert_rules: alertRules }` ohne `...trip`-Spread.
- Test: `# doc-compliance-test` (analog AC-1) — komplementäre Assertion: das korrekte minimale Muster ist vorhanden, kein Spread-Operator.

**AC-3:** Given ein Trip mit einem via `WeatherMetricsTab` gespeicherten `display_config` / When via HTTP `PUT /api/trips/{id}` nur `{ name, stages, report_config, alert_rules }` ohne `display_config` gesendet wird / Then enthält der Trip-Zustand nach dem PUT denselben `display_config`-Wert wie zuvor — das Backend-Partial-Update überschreibt keine nicht-gesendeten Felder.
- Test: HTTP-Integrationstest gegen lokale Go-API: Trip mit `display_config` anlegen, PUT ohne `display_config` absetzen, Trip abrufen und `display_config` auf Unveränderlichkeit prüfen. Belegt das Partial-Update-Versprechen des Go-Backends, auf das der minimale Frontend-Body aufbaut. Analoges Vorgehen wie AC-3 in Bug #717.

## Known Limitations

- `TripEditView` navigiert nach dem Speichern sofort via `goto('/trips')` — ein Playwright-E2E-Test, der den überschriebenen `display_config`-Stand auf derselben Seite sichtbar macht, ist daher nicht direkt möglich. AC-1/AC-2 liefern den Source-Code-Compliance-Nachweis, AC-3 liefert den Backend-Verhaltensnachweis via HTTP-Integrationstest.
- Das `const updated: Trip`-Intermediate-Object kann nach dem Fix vollständig entfernt werden; der Code-Kommentar in Zeilen 75–77 („display_config KEIN Überschreiben") wird durch den Fix wahrheitsgemäß und kann als Erklärung für den minimalen Body erhalten bleiben oder entfernt werden — Entscheidung dem Implementierer überlassen.

## Changelog

- 2026-06-10: Spec erstellt — Anti-Pattern `{ ...trip, name, stages, report_config, alert_rules }` in `TripEditView.svelte:makeSaveHandler` (Z.71–81) identifiziert; Fix und doc-compliance-Teststrategie spezifiziert (Präzedenz: Bug #707, Bug #717).
