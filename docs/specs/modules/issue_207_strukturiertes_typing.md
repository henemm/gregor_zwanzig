---
entity_id: issue_207_strukturiertes_typing
type: refactor
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, typing, refactor, types-ts]
---

# Issue #207 — Strukturiertes Typing für report_config, weather_config, aggregation

## Approval

- [ ] Approved

## Purpose

Drei Trip-Felder (`report_config`, `weather_config`, `aggregation`) sind in `frontend/src/lib/types.ts` als `Record<string, unknown>` typisiert. Konsequenz: jeder Zugriff in Konsumenten (Wizard, Edit-Dialog, Trip-Detail, Trip-Liste) braucht `as string`/`as boolean`-Casts; TypeScript erkennt Tippfehler erst zur Laufzeit. Refactor: strukturierte Interfaces mit den **tatsächlich** im Code genutzten Feldern einführen, alle Casts entfernen, Compiler verifiziert.

## Source

- **File:** `frontend/src/lib/types.ts` (Zeilen 70–75 — Trip-Interface)
- **Identifier:** `interface Trip`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/utils/rightColumn.ts` | Konsument | Liest `aggregation.activity_profile`, `weather_config.metrics` |
| `frontend/src/lib/utils/tripHero.ts` | Konsument | Liest `report_config.enabled`, `morning_time`, `evening_time` |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | Konsument (Schreib) | Baut `report_config`, `weather_config`, `aggregation` vor Save |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Konsument (Schreib + Lese) | Edit-Dialog für ReportConfig |
| `frontend/src/lib/components/edit/EditWeatherSection.svelte` | Konsument (Schreib + Lese) | Edit-Dialog für WeatherConfig |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Konsument | Top-Level Edit-View |
| `frontend/src/lib/components/TripForm.svelte` | Konsument | Trip-Form (pass-through) |
| `frontend/src/routes/trips/+page.svelte` | Konsument | Trip-Liste, liest 14 report_config-Felder mit Fallbacks |

**Tests betroffen:**
- `frontend/src/lib/utils/rightColumn.test.ts`
- `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts`

## Implementation Details

### Neue Interfaces in `frontend/src/lib/types.ts`

```typescript
export type ActivityProfile = 'wintersport' | 'wandern' | 'allgemein' | 'summer_trekking';

export interface Aggregation {
    activity_profile?: ActivityProfile;
}

export interface WeatherConfigMetric {
    metric_id: string;
    enabled: boolean;
}

export interface WeatherConfig {
    metrics?: WeatherConfigMetric[];
}

export interface ReportConfig {
    enabled?: boolean;
    morning_enabled?: boolean;
    evening_enabled?: boolean;
    morning_time?: string;
    evening_time?: string;
    send_email?: boolean;
    send_signal?: boolean;
    send_telegram?: boolean;
    send_sms?: boolean;
    alert_on_changes?: boolean;
    change_threshold_temp_c?: number;
    change_threshold_wind_kmh?: number;
    change_threshold_precip_mm?: number;
    show_compact_summary?: boolean;
    show_daylight?: boolean;
    wind_exposition_min_elevation_m?: number | null;
    multi_day_trend_morning?: boolean;
    multi_day_trend_evening?: boolean;
    multi_day_trend_reports?: string[];
}
```

### Trip-Interface ändern

```typescript
export interface Trip {
    // ...bestehende Felder...
    aggregation?: Aggregation;
    weather_config?: WeatherConfig;
    report_config?: ReportConfig;
    // display_config?: Record<string, unknown>;  ← bleibt unangetastet (out-of-scope #207)
}
```

### Konsumenten anpassen

- Alle `as string`, `as boolean`, `as number` für diese drei Felder ENTFERNEN.
- Type-Annotationen in Funktionen/Komponenten, die diese Configs als Parameter nehmen, von `Record<string, unknown>` auf das jeweilige Interface umstellen.

### Scope-Grenzen (explizit out-of-scope)

- **Backend (`internal/model/trip.go`):** bleibt `map[string]interface{}`. JSON-Serialisierung ist mit den neuen TS-Interfaces kompatibel (gleiche Feldnamen, gleiche Typen).
- **`display_config`:** wird in #207 nicht angefasst.
- **`aggregation.profile` vs `activity_profile` Mismatch:** Folge-Issue #230.
- **Zeit-Format HH:MM vs HH:MM:SS:** Folge-Issue #231.
- **`WeatherConfig.preset_name`/`preset_id`/`thresholds`:** stehen im Original-Issue, werden im Code **aktuell nicht** geschrieben/gelesen. Kommen sauber rein, sobald #206 (`weather_config.preset_name` einführen) angegangen wird. Nicht jetzt vorab definieren — würde Toten-Felder im Interface produzieren.

## Expected Behavior

- **Input:** Konsumenten greifen via `trip.report_config?.enabled` etc. auf die Felder zu.
- **Output:** TypeScript-Compiler kennt die exakten Typen, kein Cast nötig, Tippfehler in Feldnamen schlagen als Compile-Error fehl.
- **Side effects:** Keine Verhaltensänderung. JSON-Wire-Format identisch, Backend unverändert, alle E2E-Tests grün.

## Acceptance Criteria

- **AC-1:** Given `frontend/src/lib/types.ts` definiert `Trip` neu / When `npm run check` läuft / Then keine **neuen** Type-Errors gegenüber Baseline (24 Errors, 55 Warnings — Pre-Refactor-Snapshot in `docs/artifacts/issue-207-red.log`; bestehende Errors sind unverwandt zum Refactor)
  - Test: `cd frontend && npm run check` zeigt ≤ 24 Errors, keine neuen in den geänderten Dateien

- **AC-2:** Given Konsumenten benutzen die strukturierten Felder / When `grep -rE "(report_config|weather_config|aggregation)\?\.\w+\s+as\s+(string|boolean|number)" frontend/src/` läuft / Then 0 Treffer (alle alten Casts entfernt)
  - Test: Grep-Befehl gibt exit-code 1 (no matches)

- **AC-3:** Given alle bisher grünen Frontend-Tests / When `npm run test` (vitest) + relevante Playwright-Tests laufen / Then keine neuen Failures gegenüber Pre-Refactor-Baseline
  - Test: Test-Suite-Lauf grün, Liste der pre-existing failures dokumentiert (issue #217, #228, #229)

- **AC-4:** Given ein Trip wird im Wizard angelegt / When Save-Roundtrip durch Backend / Then JSON-Payload hat dieselben Feldnamen wie vor dem Refactor — Schema-kompatibel
  - Test: Manueller Smoke-Test gegen Staging nach Push: Trip anlegen, GET /api/trips/{id} prüfen

## Known Limitations

- `display_config` bleibt `Record<string, unknown>` — gehört in ein separates Cleanup-Issue.
- Backend-Strukturen (`internal/model/trip.go`) bleiben Maps. Vorteil von strukturiertem Go-Typing wäre Validierung, aber das ist ein eigenständiges Vorhaben.
- Wenn #230 (Mismatch) später `aggregation.profile` → `activity_profile` migriert, müssen ggf. bestehende JSON-Trips migriert werden. Tangiert #207 nicht direkt.

## Changelog

- 2026-05-16: Initial spec created
