---
entity_id: issue_233_type_drift
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, typescript, refactor, drift]
issue: 233
---

<!-- Issue #233 — Pre-Issue-#207 Type-Drift: activity_profile Union -->

# Issue #233 — `activity_profile` Drift-Konsolidierung

## Approval

- [ ] Approved

## Zweck

Issue #207 hat den `Trip.aggregation`-Pfad auf strukturiertes Typing migriert
(`ActivityProfile`-Alias in `frontend/src/lib/types.ts:68`, 4 Werte). Zwei
parallele Pfade (`Location.activity_profile`, `Subscription.activity_profile`)
und ein Spec-Codeblock blieben zurück:

- `types.ts:9` (Location) — Union nur 3 Werte, vermisst `'summer_trekking'`.
- `types.ts:137` (Subscription) — gleiches Muster.
- `epic_135_step5_right_column.md` §1 — illustrativer Codeblock zeigt
  Pre-#207-Lese-Pfad `(trip.aggregation as Record<...>)?.activity_profile`
  statt typisiert `trip.aggregation?.profile`.

Aufgedeckt vom Adversary-Validator während Issue #232 GREEN-Verifikation
(Finding F001).

**Tech-Lead-Entscheidung:** Statt die Unions einfach um den vierten Wert
zu erweitern (was die Drift-Ursache nicht behebt), referenzieren die zwei
parallelen Stellen den kanonischen `ActivityProfile`-Alias. So existiert
nur noch *eine* Quelle für die Profile-Werte, und der nächste neue Wert
muss nur einmal gepflegt werden.

Zusatz: Der TypeScript-Error in `compare/+page.svelte:732` (von Issue #233
erwähnt) verschwindet durch Union-Erweiterung allein **nicht** — die
Ursache ist `let activityProfile = $state('allgemein')` (Typ `string`).
Wird mit erledigt durch explizite Typ-Annotation `$state<ActivityProfile>`.

## Quelle / Source

- `frontend/src/lib/types.ts` (Zeilen 9, 137) — Typ-Definitionen
- `frontend/src/routes/compare/+page.svelte` (Zeile 38, Import) — State-Variable
- `docs/specs/modules/epic_135_step5_right_column.md` (§1, Zeilen 78, 106, 111) — Spec-Codeblock

## Acceptance Criteria

- **AC-1:** Given `frontend/src/lib/types.ts` / When eine Datei `Location.activity_profile` oder `Subscription.activity_profile` zuweist / Then ist der Typ der kanonische `ActivityProfile`-Alias (`'wintersport' | 'wandern' | 'summer_trekking' | 'allgemein'`), nicht eine inline-duplizierte Union mit weniger Werten

- **AC-2:** Given `frontend/src/routes/compare/+page.svelte` / When der Build läuft (`npx svelte-check`) / Then existiert der bisherige Error in Zeile 732 (`Type 'string' is not assignable to type '"wintersport" | "wandern" | "allgemein" | undefined'`) nicht mehr — `activityProfile` ist als `ActivityProfile` typisiert

- **AC-3:** Given `docs/specs/modules/epic_135_step5_right_column.md` §1-Blueprint-Codeblock / When ein Leser den Snippet kopiert / Then verwendet er `trip.aggregation?.profile` (typisiert), keine `Record<string, unknown>`-Casts, und keinen Verweis auf den entfernten `aggregation.activity_profile`-Pfad

- **AC-4:** Given alle bestehenden Konsumenten von `Location.activity_profile` und `Subscription.activity_profile` (`SubscriptionForm.svelte`, `LocationForm.svelte`, `compare/+page.svelte`, `locations/+page.svelte`) / When der Build läuft / Then treten keine neuen Type-Errors auf — `ActivityProfile` ist Obermenge der bisherigen 3-Wert-Union, Konsumenten brechen nicht

## Erwartetes Verhalten

### Type-Definitionen (`types.ts`)

```typescript
// Zeile 9
export interface Location {
  // ...
  activity_profile?: ActivityProfile;
  // ...
}

// Zeile 137
export interface Subscription {
  // ...
  activity_profile?: ActivityProfile;
}
```

### State-Variable (`compare/+page.svelte`)

```typescript
import type { ..., ActivityProfile } from '$lib/types';

let activityProfile = $state<ActivityProfile>('allgemein');
```

### Spec-Codeblock (`epic_135_step5_right_column.md` §1)

```typescript
export function getPresetLabel(trip: Trip): string {
  const profile = trip.aggregation?.profile;
  if (profile === 'wintersport')     return 'Wintersport-Standard';
  if (profile === 'wandern')         return 'Wandern-Standard';
  if (profile === 'summer_trekking') return 'Sommer-Trekking-Standard';
  if (profile === 'allgemein')       return DEFAULT_LABEL;
  return DEFAULT_LABEL;
}

export function getActiveMetrics(trip: Trip): string[] {
  const metrics = trip.weather_config?.metrics;
  if (Array.isArray(metrics) && metrics.every((m) => typeof m === 'string')) {
    return metrics as string[];
  }
  const profile = trip.aggregation?.profile;
  return getDefaultMetricsForProfile(profile);
}
```

(Hinweis: `getActiveMetrics` arbeitet im echten Code mit `WeatherConfigMetric[]`,
nicht mit `string[]` — die Spec-Illustration kann das vereinfacht zeigen, solange
der Lese-Pfad `trip.aggregation?.profile` korrekt ist.)

## Out-of-Scope

- Umstellung weiterer Module auf den `ActivityProfile`-Alias (z.B.
  `wizardHelpers.ts::AggregationProfile`) — Eigene Konsolidierung, eigener Issue.
- Migration von Persistenz-Strukturen — Wire-Format bleibt unverändert.
- Neue Profile (z.B. `'klettern'`) — separate Specs.

## Tests / Verifikation

- **TypeScript-Check:** `cd frontend && npx svelte-check` — der Error in
  `compare/+page.svelte:732` verschwindet, keine neuen Errors entstehen.
- **Bestehende Tests:** `rightColumn.test.ts` deckt den Trip-Pfad bereits
  ab (durch #232 mit `summer_trekking` erweitert) — Tests bleiben grün.
- **Keine neuen Tests nötig** — der TypeScript-Compiler ist der Test.
  Phase 5 (TDD RED) entfällt formal; statt eines RED-Tests dient der
  bestehende `svelte-check`-Error als RED-Beweis.

## Risiken & Migration

- **Risiko gering:** `ActivityProfile` ist Obermenge der bisherigen
  3-Wert-Union. Bestehende Konsumenten lesen nur Werte, die schon
  vorhanden waren — keine Runtime-Änderung.
- **Wire-Format unverändert:** Backend liefert `activity_profile` als
  String; Frontend nimmt ihn als `ActivityProfile`-Union entgegen.
  Backend-seitige Validierung garantiert weiterhin nur die 4
  kanonischen Werte (Single Source: `src/app/profile.py`).
- **Keine Datenbank-Migration nötig.**
