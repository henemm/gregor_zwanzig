---
entity_id: issue_229_test_drift_hero
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, test, e2e, fixture]
issue: 229
---

<!-- Issue #229 — Test-Drift trip-detail-hero AC-6 -->

# Issue #229 — Test-Drift `trip-detail-hero` AC-6

## Approval

- [ ] Approved

## Zweck

Playwright-Test `AC-6` in `frontend/e2e/trip-detail-hero.spec.ts` schlägt
fehl: der Shared-Test-Trip `e2e-cockpit-test` hat in `global.setup.ts:50-55`
inzwischen ein `report_config.enabled=true`, aber Test erwartet
"Briefings deaktiviert".

**Tech-Lead-Entscheidung:** Option B aus dem Issue — eigenen lokalen Test-Trip
im Test selbst anlegen (`request.post`), kein Shared-Fixture-Anfassen. Dieses
Pattern ist bereits in `trip-detail-overview-right.spec.ts:80-116` (AC-3
Empty-State) etabliert; AC-6 zieht nach.

## Quelle / Source

- `frontend/e2e/trip-detail-hero.spec.ts` (Zeilen 55-60) — AC-6 umstellen

## Acceptance Criteria

- **AC-1:** Given Playwright `trip-detail-hero.spec.ts` AC-6 / When der Test ausgeführt wird / Then legt er via `request.post('/api/trips', ...)` einen eigenen Trip mit einer einzigen heutigen Etappe und OHNE `report_config` an, navigiert zu dessen Detail-Seite, und der `trip-hero-stat-next-briefing` enthält "Briefings deaktiviert" — keine Abhängigkeit mehr vom Shared-Trip-Fixture

- **AC-2:** Given die übrigen Tests in `trip-detail-hero.spec.ts` (AC-2, AC-3, AC-6, AC-10, AC-11 etc.) / When der gesamte Test-Suite läuft / Then bleiben alle weiteren grün — keine Regression durch den AC-6-Umbau

- **AC-3:** Given der neue eigene Trip / When er angelegt wird / Then verwendet er eine eindeutige Trip-ID (z.B. `e2e-hero-no-briefing-trip`), kollisionsfrei zu existierenden E2E-Trip-IDs (`e2e-cockpit-test`, `e2e-no-briefing-trip` aus `overview-right.spec.ts`)

## Erwartetes Verhalten

### `trip-detail-hero.spec.ts` — AC-6 (Zeilen 55-60)

Vorher:
```typescript
test('AC-6: Trip ohne report_config zeigt "Briefings deaktiviert"', async ({ page }) => {
    await page.goto(`/trips/${TRIP_ID}`);
    const next = page.getByTestId('trip-hero-stat-next-briefing');
    // e2e-cockpit-test hat kein report_config gesetzt
    await expect(next).toContainText('Briefings deaktiviert');
});
```

Nachher (Pattern aus `trip-detail-overview-right.spec.ts:80-116` adaptiert):
```typescript
test('AC-6: Trip ohne report_config zeigt "Briefings deaktiviert"', async ({
    page,
    request
}) => {
    // Eigener Trip ohne report_config — Shared e2e-cockpit-test hat eines (#229).
    const NO_BRIEFING_TRIP_ID = 'e2e-hero-no-briefing-trip';
    await request.post('/api/trips', {
        data: {
            id: NO_BRIEFING_TRIP_ID,
            name: 'E2E Hero No-Briefing Trip',
            stages: [
                {
                    id: 'hero-nb-stage-1',
                    name: 'Etappe',
                    date: new Date().toISOString().slice(0, 10),
                    waypoints: [
                        { id: 'hero-nb-wp-1', name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }
                    ]
                }
            ]
        }
    });

    await page.goto(`/trips/${NO_BRIEFING_TRIP_ID}`);
    const next = page.getByTestId('trip-hero-stat-next-briefing');
    await expect(next).toContainText('Briefings deaktiviert');
});
```

## Out-of-Scope

- **Migration aller E2E-Tests auf Pattern "eigener Trip"** — andere Tests
  (AC-3, AC-10 etc.) brauchen den Shared-Trip wegen 3-Stages-Setup.
- **`global.setup.ts`-Aggregation auf `profile` migrieren** — Wire-Format-
  Drift (`activity_profile` statt `profile` in Zeile 60), Reader sind tolerant.
  Separater Issue.
- **`e2e-cockpit-test` ohne `report_config` machen** — bricht andere Tests
  die das Field brauchen (AC-11 z.B. setzt `morning_time` voraus).

## Tests / Verifikation

- **Playwright:** Ein Smoke-Run gegen die Hero-Suite:
  ```bash
  cd frontend && npx playwright test e2e/trip-detail-hero.spec.ts --project=chromium
  ```
  AC-6 grün, andere AC weiter grün.
- **Staging-Manual:** Nicht nötig — reine Test-Datei-Änderung, kein Code-Pfad
  ändert sich. Smoke-Verifikation am Prod-Endpoint reicht.

## Risiken & Migration

- **Risiko vernachlässigbar:** Test-Datei-Änderung, kein Komponenten-Code.
- **Backend-Idempotenz:** `POST /api/trips` mit gleicher ID überschreibt
  ggf. einen Bestand — bei parallelem Worker-Run gleicher Test-ID kein
  Problem, weil identischer Payload.
- **Trip-Cleanup:** E2E-Tests legen Trip-IDs an die nicht explizit gelöscht
  werden — bestehende Konvention. Trip bleibt nach Test-Lauf in der DB
  (idempotenter POST überschreibt beim nächsten Run).
