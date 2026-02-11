---
entity_id: safari_subscriptions_fix
type: bugfix
created: 2026-01-15
updated: 2026-01-15
status: superseded_by_safari_websocket_and_factory_fix
version: "1.0"
tags: [ui, bugfix, subscriptions, safari, nicegui, tdd]
related_specs:
  - locations_add_button_fix
---

# Safari Subscriptions Page Fix

## Approval

- [ ] Approved

## Purpose

Fix non-functional buttons on the `/subscriptions` page in **Safari browser**. Currently, all 5 action buttons (New, Toggle, Run Now, Edit, Delete) fail to respond in Safari, preventing users from managing subscriptions through the web UI.

**Browser Compatibility:** Bug is Safari-specific. Works correctly in Chromium/Chrome/Firefox but fails in Safari due to different closure handling.

**Related:** This is the same bug pattern as `locations_add_button_fix` (completed 2026-01-15).

## Source

- **File:** `src/web/pages/subscriptions.py`
- **Function:** `render_subscriptions()` (lines 28-235)
- **Specific Issues:**
  - "New Subscription" button (lines 96-103)
  - Toggle enable/disable button (lines 160-181)
  - "Run Now" button (lines 184-213)
  - Edit button (lines 216-223)
  - Delete button (lines 226-234)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `open_new_dialog()` | Function (closure) | Opens dialog to create new subscription |
| `toggle_enabled()` | Function (closure) | Toggles subscription enabled/disabled state |
| `run_now()` | Async Function (closure) | Triggers immediate subscription run |
| `edit_sub()` | Function (closure) | Opens edit dialog for subscription |
| `delete_sub()` | Function (closure) | Deletes subscription after confirmation |
| `ui.button()` | NiceGUI Component | Renders button with click handler |
| `save_compare_subscription()` | Function | Persists subscription to JSON file |
| `delete_compare_subscription()` | Function | Removes subscription from storage |
| `refresh_fn.refresh()` | Function | Refreshes subscription list display |

## Root Cause Analysis

### Current Implementation (BROKEN in Safari)

All 5 buttons use **direct closure references** instead of **factory pattern**:

#### Button 1: New Subscription (Lines 96-103)
```python
def open_new_dialog() -> None:
    show_subscription_dialog(None, locations, subscription_list)

ui.button(
    "New Subscription",
    on_click=open_new_dialog,  # ❌ Direct closure reference
    icon="add",
).props("color=primary")
```

#### Button 2: Toggle Enable/Disable (Lines 160-181)
```python
def toggle_enabled(subscription=sub) -> None:
    updated = CompareSubscription(
        id=subscription.id,
        name=subscription.name,
        enabled=not subscription.enabled,  # Toggle state
        locations=subscription.locations,
        time=subscription.time,
        recipients=subscription.recipients,
    )
    save_compare_subscription(updated)
    ui.notify(f"{'Enabled' if updated.enabled else 'Disabled'} '{updated.name}'")
    refresh_fn.refresh()

ui.button(
    icon="play_arrow" if not sub.enabled else "pause",
    on_click=toggle_enabled,  # ❌ Direct closure with captured variable
).props("flat dense")
```

#### Button 3: Run Now (Lines 184-213)
```python
async def run_now(subscription=sub) -> None:
    # ... async implementation to run comparison immediately ...

ui.button(
    icon="send",
    on_click=run_now,  # ❌ Direct async closure
).props("flat dense")
```

#### Button 4: Edit (Lines 216-223)
```python
def edit_sub(subscription=sub) -> None:
    locs = load_all_locations()
    show_subscription_dialog(subscription, locs, refresh_fn)

ui.button(
    icon="edit",
    on_click=edit_sub,  # ❌ Direct closure with captured variable
).props("flat dense")
```

#### Button 5: Delete (Lines 226-234)
```python
def delete_sub(subscription=sub) -> None:
    delete_compare_subscription(subscription.id)
    refresh_fn.refresh()
    ui.notify(f"Deleted '{subscription.name}'", type="warning")

ui.button(
    icon="delete",
    on_click=delete_sub,  # ❌ Direct closure with captured variable
).props("flat dense color=red")
```

### Why Safari Fails

**Safari's JavaScript engine** handles closure binding differently than Chromium/Chrome/Firefox:

- **Direct closure reference** (`on_click=closure_func`) → Safari fails to bind or invoke the handler
- **Factory pattern** (`on_click=factory(param)`) → Explicitly returns callable at creation time ✅

When NiceGUI's Python UI framework generates JavaScript:
1. **Chrome/Chromium/Firefox:** Tolerates loose closure binding (works)
2. **Safari:** Requires explicit callable returned by factory (strict)

**Technical Reason:** Safari's V8 alternative (JavaScriptCore) has stricter closure lifetime management. Closures must be explicitly bound at creation time, not lazily resolved at invocation time.

### Reference: Locations Page (FIXED)

The locations page shows the correct factory pattern (completed 2026-01-15):

```python
# src/web/pages/locations.py:198-206
def make_edit_handler(location: SavedLocation):
    """Factory function to create edit handler (Safari compatibility)."""
    def do_edit() -> None:
        show_edit_dialog(location)
    return do_edit

ui.button(
    icon="edit",
    on_click=make_edit_handler(loc),  # ✅ Factory returns callable
).props("flat")
```

## Implementation Strategy

### Solution: Apply Factory Pattern to All 5 Buttons

Wrap each closure in a factory function that explicitly returns a callable:

#### Button 1: New Subscription
```python
def make_new_subscription_handler():
    """Factory function to create new subscription handler (Safari compatibility)."""
    def do_new() -> None:
        open_new_dialog()
    return do_new

ui.button(
    "New Subscription",
    on_click=make_new_subscription_handler(),
    icon="add",
).props("color=primary")
```

#### Button 2: Toggle Enable/Disable
```python
def make_toggle_handler(subscription):
    """Factory function to create toggle handler (Safari compatibility)."""
    def do_toggle() -> None:
        updated = CompareSubscription(
            id=subscription.id,
            name=subscription.name,
            enabled=not subscription.enabled,
            locations=subscription.locations,
            time=subscription.time,
            recipients=subscription.recipients,
        )
        save_compare_subscription(updated)
        ui.notify(f"{'Enabled' if updated.enabled else 'Disabled'} '{updated.name}'")
        refresh_fn.refresh()
    return do_toggle

ui.button(
    icon="play_arrow" if not sub.enabled else "pause",
    on_click=make_toggle_handler(sub),
).props("flat dense")
```

#### Button 3: Run Now
```python
def make_run_now_handler(subscription):
    """Factory function to create run now handler (Safari compatibility)."""
    async def do_run_now() -> None:
        # ... async implementation ...
    return do_run_now

ui.button(
    icon="send",
    on_click=make_run_now_handler(sub),
).props("flat dense")
```

#### Button 4: Edit
```python
def make_edit_handler(subscription):
    """Factory function to create edit handler (Safari compatibility)."""
    def do_edit() -> None:
        locs = load_all_locations()
        show_subscription_dialog(subscription, locs, refresh_fn)
    return do_edit

ui.button(
    icon="edit",
    on_click=make_edit_handler(sub),
).props("flat dense")
```

#### Button 5: Delete
```python
def make_delete_handler(subscription):
    """Factory function to create delete handler (Safari compatibility)."""
    def do_delete() -> None:
        delete_compare_subscription(subscription.id)
        refresh_fn.refresh()
        ui.notify(f"Deleted '{subscription.name}'", type="warning")
    return do_delete

ui.button(
    icon="delete",
    on_click=make_delete_handler(sub),
).props("flat dense color=red")
```

### Key Changes

1. **Wrap each closure** in a factory function
2. **Factory takes subscription as parameter** (explicit binding)
3. **Factory returns inner function** that closes over the parameter
4. **Button calls factory** at creation time: `on_click=make_handler(sub)`

## Expected Behavior

### Before Fix (Current State - RED)

**Safari:**
- **Action:** User clicks any of the 5 buttons
- **Observed:** Nothing happens, no dialog, no action
- **Browser Console:** No JavaScript errors
- **Server Logs:** No callback invocation

**Chrome/Firefox:**
- **Action:** User clicks buttons
- **Observed:** ✅ Works correctly (forgiving closure handling)

### After Fix (Expected - GREEN)

**Safari:**
- **Action:** User clicks "New Subscription"
- **Expected:** Dialog appears with form to create subscription ✅

- **Action:** User clicks Toggle button
- **Expected:** Subscription enabled/disabled state changes, UI updates ✅

- **Action:** User clicks "Run Now"
- **Expected:** Comparison runs immediately, toast notification appears ✅

- **Action:** User clicks "Edit"
- **Expected:** Edit dialog appears with subscription data ✅

- **Action:** User clicks "Delete"
- **Expected:** Subscription deleted, list refreshes, toast notification ✅

**Chrome/Firefox:**
- **Action:** User clicks any button
- **Expected:** ✅ Continues to work (no regression)

## TDD Test Strategy

### Phase 1: RED Test (Verify Bug)

**Test File:** `tests/e2e/test_subscriptions_safari.py`

**Test:** `test_subscription_buttons_safari()`

```python
def test_subscription_buttons_safari():
    """E2E test: Subscription buttons should work in Safari (Chromium proxy)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        page.goto('http://localhost:8080/subscriptions', timeout=10000)
        time.sleep(2)

        # Test 1: New Subscription button
        new_button = page.locator('button:has-text("New Subscription")')
        assert new_button.count() > 0, "New Subscription button not found"

        new_button.click()
        time.sleep(1)

        # Verify dialog appeared
        name_input = page.locator('input[aria-label="Name"]')
        assert name_input.count() > 0, "Dialog did not appear after New Subscription click"

        # Test 2-5: Toggle, Run, Edit, Delete buttons
        # (Similar pattern for each button)

        browser.close()
```

**Expected Result (RED):** Test PASSES in Chromium (because Chromium is forgiving), but user confirms failure in Safari

**Actual Bug Evidence:** User manual test in Safari

### Phase 2: GREEN Test (Verify Fix)

Same test, should continue to PASS in Chromium (no regression), and user confirms it works in Safari.

**Verification via E2E Hook:**

```bash
# After fix
uv run pytest tests/e2e/test_subscriptions_safari.py -v
```

## Files to Modify

### 1. Primary File
- **Path:** `src/web/pages/subscriptions.py`
- **Lines:** 96-103, 160-181, 184-213, 216-223, 226-234
- **Change:** Wrap all 5 button handlers in factory functions

### 2. Test File (NEW)
- **Path:** `tests/e2e/test_subscriptions_safari.py`
- **Purpose:** E2E browser test for subscription buttons
- **Content:** Test all 5 buttons with Playwright

### 3. Legacy Entities (UPDATE)
- **Path:** `.claude/hooks/legacy_entities.txt`
- **Change:** Add test function names to skip spec enforcement

## Known Limitations

- This fix only addresses Safari closure binding issues
- No changes to dialog functionality or subscription logic
- Assumes server running on localhost:8080 for tests (or 192.168.1.120:8080)
- E2E test uses Chromium as proxy (cannot run Safari in headless mode easily)

## Validation Checklist

After implementation:

- [ ] E2E tests pass (Chromium - no regression)
- [ ] "New Subscription" button opens dialog in Safari
- [ ] Toggle button changes enabled/disabled state in Safari
- [ ] "Run Now" button triggers comparison in Safari
- [ ] "Edit" button opens edit dialog in Safari
- [ ] "Delete" button removes subscription in Safari
- [ ] All buttons continue to work in Chrome/Firefox (no regression)
- [ ] No console errors in Safari DevTools
- [ ] Server logs show correct callback invocations

## Related Specifications

- **Parent Bug:** `docs/specs/bugfix/locations_add_button_fix.md` (same pattern)
- **Analysis:** `docs/analysis/browser_compatibility_analysis.md`

## Changelog

- 2026-01-15: Initial spec created based on Safari button failure analysis
