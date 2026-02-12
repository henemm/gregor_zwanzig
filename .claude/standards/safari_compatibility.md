# Safari Compatibility Standard

**Domain:** NiceGUI Web UI (Gregor Zwanziger)

## The Problem

Safari is **STRICTER** than Chrome/Firefox with JavaScript closures.
NiceGUI's Python→JavaScript translation has **closure binding issues in Safari**.

## The Rule

**ALL `ui.button(on_click=X)` MUST use Factory Pattern**

## Why Factory Pattern?

Direct closure references fail in Safari (button doesn't respond, no error):
```python
# ❌ FAILS in Safari (direct closure)
for item in items:
    ui.button("Click", on_click=lambda: handle(item))
    # Safari: button doesn't work (closure binding broken)
```

Factory Pattern works in Safari (binds callable correctly):
```python
# ✅ WORKS in Safari (factory pattern)
def make_click_handler(item):
    def do_click():
        handle(item)
    return do_click

for item in items:
    ui.button("Click", on_click=make_click_handler(item))
    # Safari: button works correctly
```

## Naming Convention

**Factory:** `make_<action>_handler()`
**Callable:** `do_<action>()`

```python
def make_delete_handler(location_id: str):
    def do_delete():
        locations.delete(location_id)
        refresh_ui()
    return do_delete

ui.button("Delete", on_click=make_delete_handler(loc.id))
```

## Pattern Templates

### Simple Handler (No Arguments)

```python
# Factory
def make_save_handler():
    def do_save():
        save_data()
        refresh()
    return do_save

# Usage
ui.button("Save", on_click=make_save_handler())
```

### Handler with Item ID

```python
# Factory
def make_edit_handler(item_id: str):
    def do_edit():
        item = get_item(item_id)
        edit_dialog(item)
    return do_edit

# Usage
for item in items:
    ui.button("Edit", on_click=make_edit_handler(item.id))
```

### Handler with Multiple Arguments

```python
# Factory
def make_compare_handler(location_a: str, location_b: str):
    def do_compare():
        result = compare(location_a, location_b)
        show_result(result)
    return do_compare

# Usage
ui.button("Compare",
    on_click=make_compare_handler(loc_a.id, loc_b.id))
```

### Handler with UI State

```python
# Factory
def make_toggle_handler(checkbox: ui.checkbox):
    def do_toggle():
        new_state = not checkbox.value
        checkbox.value = new_state
        update_server(new_state)
    return do_toggle

# Usage
cb = ui.checkbox("Enable")
ui.button("Toggle", on_click=make_toggle_handler(cb))
```

## Testing Protocol

**ALWAYS test in this order:**

1. **Safari FIRST** (strictest browser)
   - If Safari works → Chrome/Firefox will work
   - Hard reload: `Cmd+Shift+R` (clear cache)

2. **Firefox** (second strictest)

3. **Chrome** (most permissive)

**After ANY UI change:**
- Test in Safari with hard reload
- Verify button responds
- Check console for errors

## Common Violations

### ❌ Don't: Lambda in Loop

```python
for loc in locations:
    ui.button("Delete", on_click=lambda: delete(loc))
    # Safari: all buttons delete LAST item (closure issue)
```

### ❌ Don't: Direct Method Reference with Args

```python
ui.button("Save", on_click=save_data(item_id))
# Calls immediately, doesn't work as handler
```

### ❌ Don't: Nested Lambda

```python
ui.button("Click",
    on_click=lambda: (update(), refresh()))
# Safari: closure binding unreliable
```

### ✅ Do: Factory Pattern

```python
def make_delete_handler(loc):
    def do_delete():
        delete(loc)
        refresh()
    return do_delete

for loc in locations:
    ui.button("Delete", on_click=make_delete_handler(loc))
```

## High-Risk UI Elements

**These ALWAYS need factory pattern:**
- Buttons in loops (e.g., location list)
- Buttons with dynamic IDs (e.g., edit/delete)
- Buttons that modify state (e.g., toggle, save)
- Buttons in dialogs (e.g., confirm/cancel)

**These are safe without factory:**
- Static buttons (no arguments)
- Single-instance buttons (not in loop)
- Simple navigation (`on_click=lambda: ui.open('/')`)

## Enforcement

### Pre-Implementation Check

Before writing UI code with buttons:
1. Will button be in loop? → Factory required
2. Does handler need arguments? → Factory required
3. Does handler modify state? → Factory recommended

### Code Review Check

During spec review:
1. Find all `ui.button(on_click=...)`
2. Check if using factory pattern (if needed)
3. Reject if direct closure in loop

### E2E Test Check

```bash
# MANDATORY for UI changes
uv run python3 .claude/hooks/e2e_browser_test.py browser \
    --check "Feature" \
    --action "compare"
```

Must test in Safari specifically!

## Migration Pattern

When fixing existing broken button:

**Before (broken):**
```python
for loc in locations:
    ui.button("Delete", on_click=lambda: delete(loc))
```

**After (fixed):**
```python
def make_delete_location_handler(location_id: str):
    def do_delete_location():
        delete(location_id)
        refresh_locations()
    return do_delete_location

for loc in locations:
    ui.button("Delete",
        on_click=make_delete_location_handler(loc.id))
```

## References

- Best Practices: `docs/reference/nicegui_best_practices.md`
- Bug Fix Examples:
  - `docs/specs/bugfix/locations_add_button_fix.md`
  - `docs/specs/bugfix/safari_subscriptions_fix.md`
- Preventive Fix: `docs/artifacts/safari_preventive_fix/`

## Why This Matters

Safari is used by many hikers (iPhone, iPad).
If buttons don't work in Safari → app is broken for those users.

Factory Pattern = Safari compatibility = Working app for all users.
