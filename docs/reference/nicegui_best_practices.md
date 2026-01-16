# NiceGUI Best Practices - Safari Compatibility

**Date:** 2026-01-15
**Purpose:** Prevent Safari browser compatibility issues in NiceGUI applications

## The Problem

NiceGUI translates Python code to JavaScript. Safari's JavaScript engine (JavaScriptCore) has **stricter closure handling** than Chrome/Firefox, causing button handlers to fail silently.

**Symptom:** Buttons work in Chrome/Firefox but not in Safari.

**Root Cause:** Direct closure references in `on_click` handlers.

---

## The Solution: Factory Pattern (Always!)

### ❌ WRONG - Direct Closure Reference

```python
# BROKEN in Safari!
def handle_click():
    do_something()

ui.button("Click Me", on_click=handle_click)
```

**Why it fails in Safari:**
- NiceGUI passes the closure reference to JavaScript
- Safari doesn't bind the closure correctly at invocation time
- No error messages, button just doesn't respond

### ✅ CORRECT - Factory Pattern

```python
# WORKS in Safari!
def handle_click():
    do_something()

def make_handler():
    """Factory function for Safari compatibility."""
    def do_click():
        handle_click()
    return do_click

ui.button("Click Me", on_click=make_handler())
```

**Why it works:**
- Factory explicitly returns a callable at button creation time
- Safari binds the returned function properly
- Works in Chrome, Firefox, Safari

---

## Pattern Templates

### 1. Simple Button (No Parameters)

```python
def open_dialog():
    with ui.dialog() as dialog:
        ui.label("Hello")
    dialog.open()

def make_dialog_handler():
    """Factory for dialog button (Safari compatibility)."""
    def do_open():
        open_dialog()
    return do_open

ui.button("Open Dialog", on_click=make_dialog_handler())
```

### 2. Button with Parameter (e.g., in a loop)

```python
for item in items:
    def delete_item(item_id=item.id):
        delete_from_db(item_id)
        refresh_list()

    def make_delete_handler(item_id):
        """Factory for delete button (Safari compatibility)."""
        def do_delete():
            delete_item(item_id)
        return do_delete

    ui.button(icon="delete", on_click=make_delete_handler(item.id))
```

### 3. Async Button Handler

```python
async def send_email(subscription):
    # ... async email sending ...
    ui.notify("Email sent")

def make_send_handler(sub):
    """Factory for async handler (Safari compatibility)."""
    async def do_send():
        await send_email(sub)
    return do_send

ui.button(icon="send", on_click=make_send_handler(subscription))
```

### 4. Toggle Button with State

```python
def toggle_enabled(item, current_state):
    item.enabled = not current_state
    save_item(item)
    refresh()

def make_toggle_handler(item, state):
    """Factory for toggle button (Safari compatibility)."""
    def do_toggle():
        toggle_enabled(item, state)
    return do_toggle

ui.button(
    icon="play_arrow" if not item.enabled else "pause",
    on_click=make_toggle_handler(item, item.enabled)
)
```

---

## Naming Convention

**Always use this naming pattern:**

```python
def make_<action>_handler(params):
    """Factory function to create <action> handler (Safari compatibility)."""
    def do_<action>():
        # Implementation
    return do_<action>
```

**Examples:**
- `make_delete_handler()` → `do_delete()`
- `make_edit_handler()` → `do_edit()`
- `make_save_handler()` → `do_save()`
- `make_toggle_handler()` → `do_toggle()`

**Why this convention?**
- Searchable: `grep "make_.*_handler"` finds all factories
- Consistent: Easy to recognize pattern
- Self-documenting: Name explains purpose

---

## When to Use Factory Pattern

### ✅ ALWAYS Use Factory Pattern For:

1. **All buttons with `on_click` handlers**
2. **All `ui.input().on()` event handlers** (keypress, blur, etc.)
3. **All `ui.select().on()` change handlers**
4. **All callback functions passed to NiceGUI components**

### ❌ NOT Needed For:

1. **Top-level page functions** (e.g., `@ui.page("/home")`)
2. **Async background tasks** (e.g., `asyncio.create_task()`)
3. **Plain Python functions** (no NiceGUI involvement)

---

## Testing Strategy

### 1. Always Test in Safari First

Safari is the **strictest browser**. If it works in Safari, it works everywhere.

**Test Order:**
1. ✅ Safari (strictest)
2. ✅ Firefox (middle)
3. ✅ Chrome (most forgiving)

### 2. E2E Tests with Playwright

```python
# tests/e2e/test_buttons.py
def test_button_works_in_safari():
    with sync_playwright() as p:
        browser = p.chromium.launch()  # Proxy for Safari
        page = browser.new_page()
        page.goto("http://localhost:8080/page")

        # Click button
        page.locator('button:has-text("Click Me")').click()

        # Verify action happened
        assert page.locator('text="Success"').count() > 0
```

### 3. Manual Safari Test Checklist

After any UI changes:
- [ ] Hard reload Safari (Cmd+Shift+R)
- [ ] Clear Safari cache
- [ ] Test all buttons on the page
- [ ] Check DevTools console for errors

---

## Common Pitfalls

### Pitfall 1: Nested Closures in Loops

```python
# ❌ WRONG
for item in items:
    ui.button("Delete", on_click=lambda: delete(item.id))  # BROKEN!
```

**Why it fails:**
- Lambda captures `item` by reference
- Last item in loop overwrites previous captures
- All buttons delete the same (last) item

```python
# ✅ CORRECT
for item in items:
    def make_handler(item_id):
        def do_delete():
            delete(item_id)
        return do_delete

    ui.button("Delete", on_click=make_handler(item.id))
```

### Pitfall 2: Default Parameter Capture

```python
# ❌ RISKY (works but not Safari-safe)
def delete_item(item=item):
    delete(item.id)

ui.button("Delete", on_click=delete_item)
```

```python
# ✅ CORRECT
def delete_item(item=item):
    delete(item.id)

def make_handler(item):
    def do_delete():
        delete_item(item)
    return do_delete

ui.button("Delete", on_click=make_handler(item))
```

### Pitfall 3: Async Without Factory

```python
# ❌ WRONG
async def send_email():
    await send()

ui.button("Send", on_click=send_email)  # BROKEN in Safari!
```

```python
# ✅ CORRECT
async def send_email():
    await send()

def make_handler():
    async def do_send():
        await send_email()
    return do_send

ui.button("Send", on_click=make_handler())
```

---

## Migration Checklist

When fixing existing code:

1. **Find all buttons:**
   ```bash
   grep -r "ui.button.*on_click" src/web/pages/
   ```

2. **For each button:**
   - [ ] Does it use direct closure reference? → Add factory
   - [ ] Is it in a loop? → Capture loop variable in factory parameter
   - [ ] Is it async? → Factory returns async function
   - [ ] Add docstring: `"""Factory for X button (Safari compatibility)."""`

3. **Test:**
   - [ ] Hard reload Safari
   - [ ] Click every button
   - [ ] Verify action happens
   - [ ] Check console for errors

---

## File-Level Template

Add this comment to every page file:

```python
"""
Page: /my-page

IMPORTANT: Safari Compatibility
- All ui.button() handlers MUST use factory pattern
- Pattern: make_<action>_handler() returns do_<action>()
- See: docs/reference/nicegui_best_practices.md
"""
```

---

## References

- **Fixed Bugs:**
  - `docs/specs/bugfix/locations_add_button_fix.md` (2026-01-15)
  - `docs/specs/bugfix/safari_subscriptions_fix.md` (2026-01-15)

- **Analysis:**
  - `docs/analysis/browser_compatibility_analysis.md`

- **NiceGUI Docs:**
  - https://nicegui.io/documentation/section_action_events

---

## TL;DR - Quick Rule

**Every `ui.button(on_click=X)` MUST follow this pattern:**

```python
def make_X_handler(params):
    """Factory for X button (Safari compatibility)."""
    def do_X():
        # implementation
    return do_X

ui.button(..., on_click=make_X_handler(params))
```

**No exceptions. Safari will break otherwise.**
