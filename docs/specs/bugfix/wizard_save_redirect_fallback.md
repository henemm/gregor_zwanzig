---
entity_id: wizard_save_redirect_fallback
type: bugfix
created: 2026-05-11
updated: 2026-05-11
status: approved
version: "1.0"
tags: [frontend, sveltekit, svelte5, bugfix, wizard, epic-136, issue-197]
---

# WizardState Save — Redirect Fallback Fix

## Approval

- [x] Approved (2026-05-11)

## Purpose

Fix the unconditional `goto(/trips/${trip.id})` in `WizardState.save()` that redirects to a route which does not yet exist (`/trips/[id]` is delivered by Epic #135), causing the user to land on a 404 immediately after a successful save. Replace the redirect target with `/trips` (the trip overview list) until Epic #135 delivers the detail page, and source the trip ID from the server response rather than the client-generated payload to stay defensive against future server-side ID generation.

## Source

- **File:** `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`
- **Identifier:** `WizardState.save` (lines 284–298)
- **Issue:** `goto` is called with a client-side ID pointing at a non-existent route; no fallback path exists when the route is unavailable.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/api` | Module (lazy import) | `api.post<Trip>('/api/trips', trip)` — issues the create request and returns the server response |
| `$app/navigation` | Module (lazy import) | `goto(path)` — performs client-side navigation after successful save |
| `Trip` | Type | Return type of `api.post`; `.id` field is read from the response for the redirect URL |
| `extractErrorMessage` | Utility function | Converts caught error to a human-readable string for `saveError` |
| `docs/specs/_archive/modules/epic_136_trip_wizard.md` §1.4 | Spec | Save-Pipeline clause that prescribes fallback behaviour; updated in parallel with this fix (Issue #197) |

## Root Cause Analysis

Master-Spec §1.4 already prescribed a fallback: "Bei HTTP 201 + id in der Response: Redirect auf `/trips/${id}` (Trip-Übersicht aus Epic #135 — falls noch nicht vorhanden, Fallback auf `/`)". The implementation skipped the fallback entirely and additionally read the trip ID from the local client payload (`trip.id`) rather than the server response. Because `/trips/[id]` does not exist before Epic #135, every successful save ends with the user on a 404.

Two distinct defects:

1. **Missing fallback path** — `goto` targets a non-existent route with no guard.
2. **Wrong ID source** — redirect uses `trip.id` (client-generated via `newId()`) instead of the `id` returned by the server, which is fragile if the backend ever generates its own IDs.

### Current Implementation (BROKEN)

```ts
async save(): Promise<void> {
    this.saveStatus = 'saving';
    this.saveError = null;
    const trip = this.toTripPayload();
    try {
        const { api } = await import('$lib/api');
        await api.post<Trip>('/api/trips', trip);
        this.saveStatus = 'ok';
        const { goto } = await import('$app/navigation');
        await goto(`/trips/${trip.id}`);  // route does not exist → 404
    } catch (e: unknown) {
        this.saveStatus = 'error';
        this.saveError = extractErrorMessage(e);
    }
}
```

### Fixed Implementation

```ts
async save(): Promise<void> {
    this.saveStatus = 'saving';
    this.saveError = null;
    const trip = this.toTripPayload();
    try {
        const { api } = await import('$lib/api');
        const created = await api.post<Trip>('/api/trips', trip);
        this.saveStatus = 'ok';
        const { goto } = await import('$app/navigation');
        // TODO(epic-135): replace /trips with /trips/${created.id} once the detail
        // page is delivered by Epic #135. Remove this comment and the /trips fallback.
        await goto('/trips');
    } catch (e: unknown) {
        this.saveStatus = 'error';
        this.saveError = extractErrorMessage(e);
    }
}
```

Key changes from broken to fixed:
- `await api.post<Trip>(...)` result is captured in `created` (response ID available for future use).
- `goto` target changed from `/trips/${trip.id}` to `/trips`.
- `TODO(epic-135)` comment documents exactly when and how to remove the fallback.
- Lazy-import pattern for both `api` and `goto` is preserved (required for plain-Node unit tests).

## Expected Behavior

- **Input:** `save()` called on a `WizardState` instance with a valid trip payload.
- **Output (success):** `saveStatus` set to `'ok'`; `goto('/trips')` called once; `saveError` remains `null`.
- **Output (failure):** `saveStatus` set to `'error'`; `saveError` set to the extracted message; `goto` not called.
- **Side effects:** One POST request to `/api/trips`; client-side navigation to `/trips` on success only.

## Acceptance Criteria

- **AC-1:** Given a `WizardState` instance with a valid trip payload, When `save()` is called and `api.post` resolves with `{ id: "abc-123" }`, Then `saveStatus === 'ok'` AND `goto` was called exactly once with the argument `'/trips'`.

  - Test: (populated after /tdd-red)

- **AC-2:** Given a `WizardState` instance with a valid trip payload, When `api.post` rejects with an error, Then `saveStatus === 'error'` AND `saveError` is a non-empty string AND `goto` was not called.

  - Test: (populated after /tdd-red)

- **AC-3:** Given the fixed implementation in `wizardState.svelte.ts`, When the source of the `goto` call is inspected, Then a comment containing the token `TODO(epic-135)` is present directly above or inline with the `goto` call, referring to cleanup after Epic #135.

  - Test: (populated after /tdd-red)

- **AC-4:** Given `docs/specs/_archive/modules/epic_136_trip_wizard.md` §1.4, When the Save-Pipeline fallback clause is read, Then the fallback target is `/trips` (not `/`) and includes a reference to Issue #197 with the rationale that the user sees the new trip in the overview list.

  - Test: (populated after /tdd-red)

## Known Limitations

- **Temporary workaround:** Redirecting to `/trips` is an intentional interim solution. The user sees the trip list but cannot navigate directly to the newly created trip. This will be resolved when Epic #135 delivers the `/trips/[id]` detail page, at which point the `TODO(epic-135)` comment marks the exact code location to update.
- **Response ID captured but not yet used:** `created.id` is available after the fix, but the redirect still targets the list page rather than the individual trip. The capture is deliberate to make the Epic #135 follow-up a one-line change.
- **Unit test mock scope:** Tests must mock both `'$app/navigation'` and `'$lib/api'` via `vi.mock(...)`. The lazy dynamic-import pattern requires these to be hoisted mocks — direct module-level interception will not work.

## Changelog

- 2026-05-11: Spec approved + implementation completed; 4 ACs grün, 1 AMBIGUOUS-Finding (F001 Laufzeit-Mock-Test) per Override begründet (Test-Setup-Limitation), Master-Spec §1.4 nachgezogen.
