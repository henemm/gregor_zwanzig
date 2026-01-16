---
entity_id: safari_preventive_fix
type: bugfix
created: 2026-01-15
updated: 2026-01-15
status: draft
version: "1.0"
tags: [safari, nicegui, browser-compatibility, preventive]
---

# Safari Preventive Fix - HIGH RISK Buttons

## Approval

- [ ] Approved

## Purpose

Preventive fix for 5 HIGH RISK Safari buttons in settings.py and compare.py that use direct closure references combined with mutable state capture. This creates a double vulnerability: Safari's closure binding issue + stale state capture. Fix prevents silent button failures where users click and nothing happens.

Related to completed fixes: `locations_add_button_fix.md`, `safari_subscriptions_fix.md`

## Root Cause

**Double Vulnerability:**
1. **Safari Closure Binding Issue**: Direct function references in `on_click` handlers don't bind correctly in Safari's JavaScriptCore engine
2. **Mutable State Capture**: Closures capture mutable UI elements (form inputs) or state dicts that change after button creation

**Result**: Safari executes handler with stale/incorrect values, or handler doesn't fire at all. No error messages.

## Affected Code

### File 1: `src/web/pages/settings.py`

**Button 1: Save Settings (HIGH RISK)**
- **Location**: Line 164-168
- **Current Code**:
  ```python
  def save() -> None:
      new_settings = {
          "GZ_SMTP_HOST": smtp_host.value or "",  # <-- Captures mutable UI element
          "GZ_SMTP_PORT": str(int(smtp_port.value or 587)),
          "GZ_SMTP_USER": smtp_user.value or "",
          "GZ_SMTP_PASS": smtp_pass.value or "",
          "GZ_MAIL_FROM": mail_from.value or "",
          "GZ_MAIL_TO": mail_to.value or "",
          "GZ_EMAIL_PLAIN_TEXT": "true" if email_plain_text.value else "false",
          "GZ_PROVIDER": provider.value or "geosphere",
          "GZ_LATITUDE": str(lat.value or 47.2692),
          "GZ_LONGITUDE": str(lon.value or 11.4041),
          "GZ_LOCATION_NAME": location_name.value or "Innsbruck",
      }
      save_env_settings(new_settings)
      ui.notify("Settings saved", type="positive")

  ui.button("Save", on_click=save, icon="save")  # <-- Direct closure reference
  ```
- **Risk**: Captures 11 mutable form inputs - Safari may execute with wrong/stale values
- **Impact**: Wrong settings saved to .env file

**Button 2: Send Test Email (HIGH RISK + ASYNC)**
- **Location**: Line 204-208
- **Current Code**:
  ```python
  async def test_email() -> None:
      save()  # <-- Inherits all mutable form capture issues
      # ... email sending logic ...

  ui.button("Send Test Email", on_click=test_email, icon="mail")  # <-- Direct closure
  ```
- **Risk**: Async + captures form inputs via `save()` call
- **Impact**: Test email sent with wrong settings, or doesn't send at all

### File 2: `src/web/pages/compare.py`

**Handler 1: Location Selection Change (HIGH RISK)**
- **Location**: Line 1112-1114 (handler), Line 1142 (registration)
- **Current Code**:
  ```python
  def on_location_change(e) -> None:
      state["selected_locations"] = e.value if e.value else []  # <-- Captures mutable state dict

  ui.select(..., on_change=on_location_change)  # <-- Direct closure reference
  ```
- **Risk**: Captures mutable `state` dict - Safari may not update state or may access stale state
- **Impact**: Wrong locations selected for comparison

**Handler 2: Run Comparison (HIGH RISK + ASYNC)**
- **Location**: Line 1203-1330 (handler), Line 1398 (registration)
- **Current Code**:
  ```python
  async def run_comparison() -> None:
      if not state["selected_locations"]:  # <-- Captures state dict
          ui.notify("Please select at least one location", type="warning")
          return

      selected_locs = [loc for loc in locations if loc.id in state["selected_locations"]]
      days_ahead = date_select.value or 1
      time_start = time_start_select.value or 9
      time_end = time_end_select.value or 16
      # ... comparison logic ...

  ui.button("Compare", on_click=run_comparison, icon="compare_arrows")  # <-- Direct closure
  ```
- **Risk**: Async + captures mutable `state` dict (8 fields)
- **Impact**: Comparison runs with wrong locations, wrong time window, or doesn't run at all

**Handler 3: Send Email (HIGH RISK + ASYNC)**
- **Location**: Line 1331-1389 (handler), Line 1405 (registration)
- **Current Code**:
  ```python
  async def send_email() -> None:
      if not state["results"]:  # <-- Captures mutable state dict
          ui.notify("Please run a comparison first", type="warning")
          return
      # ... email sending logic using state["results"], state["hourly_data"] ...

  ui.button("Per E-Mail senden", on_click=send_email, icon="email")  # <-- Direct closure
  ```
- **Risk**: Async + captures mutable `state` dict
- **Impact**: Email sent with stale/wrong comparison results, or doesn't send

## Solution: Factory Pattern

Apply factory pattern per `docs/reference/nicegui_best_practices.md` to all 5 handlers.

### Pattern Template

**For sync handlers:**
```python
def make_X_handler(params):
    """Factory for X button (Safari compatibility)."""
    def do_X():
        # implementation
    return do_X

ui.button(..., on_click=make_X_handler(params))
```

**For async handlers:**
```python
def make_X_handler(params):
    """Factory for async X handler (Safari compatibility)."""
    async def do_X():
        # async implementation
    return do_X

ui.button(..., on_click=make_X_handler(params))
```

### Fixed Code Examples

**settings.py Button 1 (Sync):**
```python
def save() -> None:
    new_settings = {
        "GZ_SMTP_HOST": smtp_host.value or "",
        # ... all 11 fields ...
    }
    save_env_settings(new_settings)
    ui.notify("Settings saved", type="positive")

def make_save_handler():
    """Factory for save button (Safari compatibility)."""
    def do_save() -> None:
        save()
    return do_save

ui.button("Save", on_click=make_save_handler(), icon="save")
```

**settings.py Button 2 (Async):**
```python
async def test_email() -> None:
    save()
    # ... email logic ...

def make_test_email_handler():
    """Factory for test email button (Safari compatibility)."""
    async def do_test() -> None:
        await test_email()
    return do_test

ui.button("Send Test Email", on_click=make_test_email_handler(), icon="mail")
```

**compare.py Handlers (Async):**
```python
async def run_comparison() -> None:
    if not state["selected_locations"]:
        # ... logic ...

def make_comparison_handler():
    """Factory for comparison button (Safari compatibility)."""
    async def do_compare() -> None:
        await run_comparison()
    return do_compare

ui.button("Compare", on_click=make_comparison_handler(), icon="compare_arrows")
```

## Implementation Plan

### Phase 5: TDD RED

**Test**: E2E browser test with Playwright
- Navigate to `/settings` and `/compare`
- Click each button in Safari/Chromium
- Verify action happens (dialog opens, notification appears, etc.)
- **Expected**: Tests FAIL in current code (buttons don't respond)

### Phase 6: Implementation

1. **settings.py** (2 buttons)
   - Wrap `save()` in `make_save_handler()`
   - Wrap `test_email()` in `make_test_email_handler()`

2. **compare.py** (3 handlers)
   - Wrap `on_location_change()` in `make_location_change_handler()`
   - Wrap `run_comparison()` in `make_comparison_handler()`
   - Wrap `send_email()` in `make_email_handler()`

### Phase 7: Validation

**E2E Test Criteria (GREEN):**
- All 5 buttons respond in Safari/Chromium
- Correct values captured from forms/state
- No silent failures
- Async handlers complete successfully

## Test Plan

### E2E Test 1: Settings Page
```python
def test_settings_save_button():
    """Test Save button captures correct form values."""
    # 1. Navigate to /settings
    # 2. Fill form with test values
    # 3. Click Save button
    # 4. Verify notification "Settings saved"
    # 5. Check .env file contains correct values
```

### E2E Test 2: Settings Test Email
```python
def test_settings_test_email_button():
    """Test Send Test Email button works."""
    # 1. Navigate to /settings
    # 2. Configure SMTP settings
    # 3. Click Send Test Email
    # 4. Verify notification "Sending test email..."
    # 5. Verify notification "Test email sent to..."
```

### E2E Test 3: Compare Page Location Select
```python
def test_compare_location_select():
    """Test location select updates state."""
    # 1. Navigate to /compare
    # 2. Select 2 locations
    # 3. Verify state["selected_locations"] updated
    # 4. Click Compare button
    # 5. Verify comparison runs for selected locations
```

### E2E Test 4: Compare Button
```python
def test_compare_button():
    """Test Compare button runs comparison."""
    # 1. Navigate to /compare
    # 2. Select locations and time window
    # 3. Click Compare button
    # 4. Verify loading spinner appears
    # 5. Verify results table appears with correct data
```

### E2E Test 5: Compare Email Button
```python
def test_compare_email_button():
    """Test Send Email button sends comparison."""
    # 1. Navigate to /compare
    # 2. Run comparison first
    # 3. Click "Per E-Mail senden" button
    # 4. Verify notification "E-Mail gesendet an..."
    # 5. Check email received with comparison data
```

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/reference/nicegui_best_practices.md` | reference | Factory pattern templates and guidelines |
| `src/web/pages/settings.py` | module | Settings page with 2 broken buttons |
| `src/web/pages/compare.py` | module | Compare page with 3 broken handlers |
| `app/config.py` | module | Settings class for .env loading |
| `outputs/email.py` | module | EmailOutput for sending emails |
| NiceGUI framework | library | UI framework with Safari issues |

## Expected Behavior

**Before Fix (RED):**
- Buttons don't respond in Safari (silent failure)
- Forms may save wrong values
- Comparisons may run with wrong parameters
- Emails may not send or send wrong data

**After Fix (GREEN):**
- All 5 buttons/handlers respond correctly in Safari
- Form values captured accurately at click time
- State dict accessed correctly at handler invocation
- Async handlers complete successfully
- Identical behavior in Chrome/Firefox/Safari

## Known Limitations

- **Not a perfect fix**: Factory pattern only solves Safari's closure binding issue. If NiceGUI's Python→JavaScript translation has deeper bugs, those remain.
- **No regression risk**: Factory pattern is strictly additive - doesn't break Chrome/Firefox behavior
- **Future code**: Developers must remember to use factory pattern for all new buttons (documented in CLAUDE.md)

## Success Criteria

- [ ] All 5 handlers use factory pattern
- [ ] E2E tests pass in Safari/Chromium
- [ ] Form inputs captured correctly
- [ ] State dict accessed correctly
- [ ] Async handlers complete successfully
- [ ] No console errors in Safari
- [ ] Documentation updated (if needed)

## Related Bugs

- `docs/specs/bugfix/locations_add_button_fix.md` - First Safari closure bug discovered
- `docs/specs/bugfix/safari_subscriptions_fix.md` - 5 buttons on subscriptions page fixed with same pattern
- `docs/reference/nicegui_best_practices.md` - Comprehensive Safari compatibility guide

## Changelog

- 2026-01-15: Initial spec created (preventive fix for 5 HIGH RISK buttons)
