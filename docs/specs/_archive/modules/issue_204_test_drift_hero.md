---
entity_id: issue_204_test_drift_hero
type: bugfix
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, e2e, test-drift]
---

# Issue #204 — Test-Drift: trip-detail-hero AC-11 hartkodiertes Datum

## Approval

- [ ] Approved

## Purpose

E2E-Test `AC-11: Date-Range zeigt Mai 2026 (kompakt)` prüft das Date-Range-Label mit hartkodierten Tag-Strings `11.` und `13.` — die Testdaten in `global.setup.ts` werden aber dynamisch an `now` ausgerichtet. Sobald `now` weiterwandert, läuft der Test fehl. Fix: Tag-Strings dynamisch aus `new Date()` herleiten.

## Source

- **File:** `frontend/e2e/trip-detail-hero.spec.ts`
- **Identifier:** `test('AC-11: Date-Range zeigt Mai 2026 (kompakt)')` (Zeilen 68–75)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/global.setup.ts` | Test-Fixture | Setzt Stages dynamisch auf yesterday/today/tomorrow |
| `frontend/e2e/trip-detail-overview-left.spec.ts` | Test-Datei | Referenz-Pattern (AC-8, Zeilen 200–206) für dynamische Datum-Ableitung |

## Implementation Details

Hartkodierte Tag-Strings durch dynamische Ableitung ersetzen:

```typescript
test('AC-11: Date-Range zeigt Mai 2026 (kompakt)', async ({ page }) => {
    await page.goto(`/trips/${TRIP_ID}`);
    const range = page.getByTestId('trip-hero-date-range');
    // Stages werden in global.setup.ts dynamisch auf yesterday/today/tomorrow gesetzt
    const today = new Date();
    const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
    const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1);
    await expect(range).toContainText('Mai 2026');
    await expect(range).toContainText(`${yesterday.getDate()}.`);
    await expect(range).toContainText(`${tomorrow.getDate()}.`);
});
```

## Expected Behavior

- **Input:** Test-Lauf an beliebigem Tag im Mai 2026
- **Output:** Test prüft, dass das Date-Range-Label die dynamisch berechneten Tag-Strings (gestern und morgen) enthält
- **Side effects:** Keine — nur Test-Datei

## Acceptance Criteria

- **AC-1:** Given `now` ist ein beliebiger Tag im Mai 2026 / When `npx playwright test trip-detail-hero.spec.ts --grep "AC-11"` läuft / Then der Test ist grün
  - Test: `frontend/e2e/trip-detail-hero.spec.ts::AC-11`

- **AC-2:** Given die Stages in `global.setup.ts` setzen yesterday/today/tomorrow dynamisch / When der Test ausgeführt wird / Then prüft er `Mai 2026` plus die Tag-Strings von `yesterday.getDate()` und `tomorrow.getDate()` — keine hartkodierten Zahlen mehr
  - Test: Code-Review der Test-Datei (kein `'11.'`/`'13.'` Literal mehr im AC-11 Block)

## Known Limitations

- Bei einem Monatswechsel (z.B. 31. Mai → 1. Juni) prüft der Test weiterhin auf `'Mai 2026'`. Out-of-Scope dieses Tickets — gehört in ein separates Folge-Issue, wenn der Monatswechsel-Drift in Produktion auftritt.

## Changelog

- 2026-05-16: Initial spec created
