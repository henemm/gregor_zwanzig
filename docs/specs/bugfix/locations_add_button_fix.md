---
entity_id: locations_add_button_fix
type: bugfix
created: 2026-01-15
updated: 2026-01-15
status: draft
version: "1.0"
tags: [ui, bugfix, locations, nicegui, tdd]
---

# Locations Add Button Fix

## Approval

- [x] Approved

## Purpose

Fix the non-functional "Add Location" button on the `/locations` page. The button is currently visible but does not trigger the dialog when clicked in **Safari browser**. This prevents users from adding new locations through the web UI.

**Browser Compatibility:** Bug is Safari-specific. Works correctly in Chromium/Chrome but fails in Safari due to different closure handling.

## Source

- **File:** `src/web/pages/locations.py`
- **Identifier:** `render_content()` function (lines 81-220)
- **Specific Issue:** Button definition at lines 169-173, handler definition at lines 85-167

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `show_add_dialog()` | Function (closure) | Opens dialog with form to add new location |
| `ui.button()` | NiceGUI Component | Renders button with click handler |
| `ui.dialog()` | NiceGUI Component | Modal dialog container |
| `save_location()` | Function | Persists location to JSON file |
| `SavedLocation` | Dataclass | Location data model |
| `refresh_list()` | Function (closure) | Refreshes location list after changes |

## Root Cause Analysis

### Current Implementation (BROKEN)

```python
def render_content() -> None:
    """Render page content."""
    ui.label("Locations").classes("text-h4 mb-4")

    def show_add_dialog() -> None:  # Line 85
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            # ... dialog implementation ...
        dialog.open()

    # ... other code ...

    ui.button(  # Line 169
        "New Location",
        on_click=show_add_dialog,  # Reference to closure
        icon="add_location",
    ).props("color=primary")
```

**Problem:** The `on_click` handler references `show_add_dialog`, but this is a **nested closure** defined inside `render_content()`. NiceGUI's button binding mechanism may not correctly capture or invoke closures in this context, especially when `render_content()` is called via `refresh_list()` which uses `container.clear()`.

### Working Pattern (Edit/Delete Buttons)

```python
def make_edit_handler(location: SavedLocation):
    def do_edit() -> None:
        show_edit_dialog(location)
    return do_edit

ui.button(icon="edit", on_click=make_edit_handler(loc)).props("flat")
```

This **factory pattern** explicitly returns a callable at button creation time, ensuring proper binding.

## Implementation Strategy

### Solution: Use Factory Pattern

Apply the same factory pattern used for Edit/Delete buttons:

```python
def render_content() -> None:
    ui.label("Locations").classes("text-h4 mb-4")

    def show_add_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            # ... existing dialog code unchanged ...
        dialog.open()

    def make_add_handler():
        """Factory function to create add handler."""
        def do_add() -> None:
            show_add_dialog()
        return do_add

    ui.button(
        "New Location",
        on_click=make_add_handler(),  # Call factory to get callable
        icon="add_location",
    ).props("color=primary")
```

**Key Change:** Wrap the handler in a factory function that returns a callable, ensuring proper binding at button creation time.

## Expected Behavior

### Before Fix (Current State - RED)
- **Action:** User clicks "Add Location" button
- **Observed:** Nothing happens, no dialog appears
- **Browser Console:** No JavaScript errors
- **Server Logs:** No callback invocation

### After Fix (Expected - GREEN)
- **Action:** User clicks "Add Location" button
- **Expected:** Dialog appears with form fields:
  - Name (required)
  - Google Maps Coordinates (optional, auto-converts to lat/lon)
  - Latitude (decimal degrees)
  - Longitude (decimal degrees)
  - Elevation (meters)
  - Avalanche Region (optional)
  - Bergfex Slug (optional)
- **Validation:** Name field must be filled
- **Submit:** Creates `SavedLocation` object, saves to JSON, closes dialog, refreshes list
- **Feedback:** Toast notification "Location '[name]' saved"

## TDD Test Strategy

### Phase 1: RED Test (Verify Bug)

**Test File:** `tests/e2e/test_locations_add_button.py`

**Test:** `test_add_button_opens_dialog_RED()`

```python
def test_add_button_opens_dialog():
    """E2E test: Click Add Location button, dialog should appear."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('http://localhost:8080/locations')

        # Click "New Location" button
        page.locator('button:has-text("New Location")').click()

        # Assert dialog appears (check for dialog header text)
        dialog_visible = page.locator('text="New Location"').count() > 1
        assert dialog_visible, "Dialog did not appear after button click"

        browser.close()
```

**Expected Result:** Test FAILS (RED) - dialog does not appear

### Phase 2: GREEN Test (Verify Fix)

Same test, but should PASS after implementing the fix.

**Verification via E2E Hook:**

```bash
# RED Phase (before fix)
uv run python3 .claude/hooks/e2e_browser_test.py browser \
  --url "/locations" \
  --check "Name is required" \
  --expect-fail

# GREEN Phase (after fix)
uv run python3 .claude/hooks/e2e_browser_test.py browser \
  --url "/locations" \
  --check "Name is required"
```

## Files to Modify

### 1. Create Test File (NEW)
- **Path:** `tests/e2e/test_locations_add_button.py`
- **Purpose:** E2E browser test with Playwright
- **Content:** Test that clicks button and verifies dialog appears

### 2. Fix Implementation File
- **Path:** `src/web/pages/locations.py`
- **Lines:** 169-173 (button definition)
- **Change:** Wrap `show_add_dialog` in factory function `make_add_handler()`

## Known Limitations

- This fix only addresses the button click handler binding issue
- No changes to dialog functionality or form validation
- Assumes server is running on `localhost:8080` for tests
- E2E test requires Playwright browser automation (already installed)

## Validation Checklist

After implementation:

- [ ] E2E test passes (GREEN)
- [ ] Button click opens dialog in browser
- [ ] Dialog displays all form fields
- [ ] Form validation works (name required)
- [ ] Saving location persists to JSON
- [ ] List refreshes after save
- [ ] Toast notification appears
- [ ] No console errors in browser
- [ ] Server logs show no errors

## Changelog

- 2026-01-15: Initial spec created based on bug analysis
