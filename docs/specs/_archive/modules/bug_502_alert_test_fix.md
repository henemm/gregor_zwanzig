---
entity_id: bug_502_alert_test_fix
type: bugfix
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
tags: [frontend, alerts, e2e-test, trip-detail]
---

# Bug #502 — AC-8 alert-rules-editor.spec.ts: right-card-alerts-edit-link fehlt im DOM

## Approval

- [ ] Approved

## Purpose

`AlertsPreviewCard` (mit testid `right-card-alerts-edit-link`) wurde in Issue #487 durch `DetailCard` in `TripOverview.svelte` ersetzt. Der E2E-Test AC-8 sowie ein Unit-Test verweisen noch auf die alte Komponente und den alten Hash-Navigationsstil (`#alerts`). Alle drei Stellen werden auf den neuen Stand gebracht.

## Source

- **Schicht:** Frontend / User-UI
- **Files:**
  - `frontend/src/lib/components/trip-detail/TripOverview.svelte` (actionHref)
  - `frontend/src/lib/components/trip-detail/TripOverview.issue487.test.ts` (Unit-Test)
  - `frontend/e2e/alert-rules-editor.spec.ts` (E2E-Test AC-8)

## Estimated Scope

- **LoC:** ~4
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `DetailCard.svelte` | Lesen | Rendert `data-testid="detail-card-action-{testid}"` |
| `TripTabs.svelte` | Referenz | Navigiert via `?tab=alerts` (Issue #516) |

## Implementation Details

### 1. TripOverview.svelte — actionHref korrigieren

```svelte
<!-- Vorher -->
<DetailCard
  ...
  actionHref="#alerts"
  testid="card-alerts"
/>

<!-- Nachher -->
<DetailCard
  ...
  actionHref="?tab=alerts"
  testid="card-alerts"
/>
```

### 2. TripOverview.issue487.test.ts — Unit-Test anpassen

```ts
// Vorher
test('Alerts-Karte verlinkt auf #alerts', () => {
  assert.ok(source.includes('#alerts'), '...');
});

// Nachher
test('Alerts-Karte verlinkt auf ?tab=alerts', () => {
  assert.ok(source.includes('?tab=alerts'), '...');
});
```

### 3. alert-rules-editor.spec.ts AC-8 — testid + href anpassen

```ts
// Vorher
const link = page.locator('[data-testid="right-card-alerts-edit-link"]');
await expect(link).toBeVisible();
await expect(link).toHaveAttribute('href', `/trips/${id}/edit#alerts`);

// Nachher
const link = page.locator('[data-testid="detail-card-action-card-alerts"]');
await expect(link).toBeVisible();
await expect(link).toHaveAttribute('href', '?tab=alerts');
```

## Expected Behavior

- **Input:** Nutzer ruft `/trips/${id}` auf (Trip-Detail-Overview)
- **Output:** `[data-testid="detail-card-action-card-alerts"]` ist sichtbar mit `href="?tab=alerts"`
- **Side effects:** Keine Datenmodell-Änderungen, kein UI-Redesign

## Changelog

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0 | 2026-06-02 | Erstversion — Bug #502 Root Cause + Fix |

## Acceptance Criteria

**AC-1:** Given ein Trip mit mindestens einer aktiven Alert-Regel / When `/trips/${id}` aufgerufen wird / Then ist `[data-testid="detail-card-action-card-alerts"]` sichtbar mit `href="?tab=alerts"`
  - Test: `alert-rules-editor.spec.ts` AC-8 (angepasst)

**AC-2:** Given `TripOverview.svelte` / When Unit-Test auf actionHref prüft / Then enthält Source `?tab=alerts` (nicht `#alerts`)
  - Test: `TripOverview.issue487.test.ts` — Alerts-Karte-Test (angepasst)
