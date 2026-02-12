---
entity_id: safari_websocket_and_factory_fix
type: bugfix
created: 2026-02-11
updated: 2026-02-12
status: draft
version: "1.1"
tags: [ui, bugfix, safari, nicegui, websocket, factory-pattern]
related_specs:
  - safari_subscriptions_fix
  - locations_add_button_fix
---

# Safari WebSocket + Factory Pattern Fix

## Approval

- [ ] Approved

## Purpose

Fix two layered Safari bugs that cause **all buttons in the WebUI to be unresponsive** after
the first page visit. Users must clear the cache and hard-reload (Cmd+Shift+R) for buttons
to work again.

**Bug 1 (WebSocket):** Safari caches HTML pages including stale Socket.IO session data.
On revisit, the page renders but the WebSocket connection is dead. No button events reach
the server. Known upstream issue: https://github.com/zauberzeug/nicegui/issues/5468

**Bug 2 (Factory Pattern):** 13 buttons still use direct closures instead of the Safari-safe
factory pattern. Even with a working WebSocket, these can fail silently in Safari.

## Source

### Bug 1: WebSocket Cache

- **File:** `src/web/main.py`
- **Identifier:** `run()` / app middleware (new)

### Bug 2: Factory Pattern

- **File:** `src/web/pages/subscriptions.py`
- **Identifier:** `render_subscriptions()`, `render_subscription_card()`, `show_subscription_dialog()`
- **File:** `src/web/pages/locations.py`
- **Identifier:** `render_content()`, `show_edit_dialog()`
- **File:** `src/web/pages/trips.py`
- **Identifier:** `render_content()`, `show_add_dialog()`, `show_edit_dialog()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `nicegui.app` | Framework | Middleware-Hook for HTTP headers |
| `starlette` | Framework | HTTP middleware via `@app.middleware("http")` |
| `subscriptions.py` | Page | 6 buttons ohne Factory Pattern |
| `locations.py` | Page | 3 buttons ohne Factory Pattern |
| `trips.py` | Page | 4 buttons ohne Factory Pattern |

## Implementation Details

### Bug 1: No-Cache Middleware (main.py)

```python
@app.middleware("http")
async def no_cache_headers(request, call_next):
    response = await call_next(request)
    if "text/html" in response.headers.get("content-type", ""):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
```

### Bug 2: Factory Pattern (3 Dateien)

**subscriptions.py** - 6 Buttons umstellen:

| Button | Zeile | Aktuell | Neu |
|--------|-------|---------|-----|
| New Subscription | 101 | `on_click=open_new_dialog` | `on_click=make_new_handler()` |
| Toggle | 178 | `on_click=toggle_enabled` | `on_click=make_toggle_handler(sub)` |
| Run Now | 212 | `on_click=run_now` | `on_click=make_run_now_handler(sub)` |
| Edit | 222 | `on_click=edit_sub` | `on_click=make_edit_handler(sub)` |
| Delete | 233 | `on_click=delete_sub` | `on_click=make_delete_handler(sub)` |
| Save (Dialog) | 385 | `on_click=save` | `on_click=make_save_handler()` |

**locations.py** - 3 Buttons umstellen:

| Button | Zeile | Aktuell | Neu |
|--------|-------|---------|-----|
| New Location | 171 | `on_click=show_add_dialog` | `on_click=make_add_handler()` |
| Save (Edit) | 77 | `on_click=save_edit` | `on_click=make_save_edit_handler()` |
| Save (Add) | 165 | `on_click=save` | `on_click=make_save_handler()` |

**trips.py** - 4 Buttons umstellen:

| Button | Zeile | Aktuell | Neu |
|--------|-------|---------|-----|
| New Trip | 437 | `on_click=show_add_dialog` | `on_click=make_add_handler()` |
| Add Stage | 80 | `on_click=add_stage` | `on_click=make_add_stage_handler()` |
| Save (Add) | 227 | `on_click=save` | `on_click=make_save_handler()` |
| Add Stage (Edit) | 284 | `on_click=add_stage_edit` | `on_click=make_add_stage_edit_handler()` |
| Save (Edit) | 431 | `on_click=save_edit` | `on_click=make_save_edit_handler()` |

## Expected Behavior

### Vorher (Bug)

- **Aktion:** User besucht eine Seite erneut in Safari
- **Ergebnis:** Seite sieht normal aus, aber kein Button reagiert
- **Workaround:** Cache leeren + Hard Reload (Cmd+Shift+R)

### Nachher (Fix)

- **Aktion:** User besucht eine Seite erneut in Safari
- **Ergebnis:** Alle Buttons reagieren sofort, kein Cache-Clear noetig
- **Nebeneffekt:** Keine (Chrome/Firefox weiterhin kompatibel)

## Files to Modify

| Datei | Aenderung | LoC |
|-------|-----------|-----|
| `src/web/main.py` | No-Cache Middleware hinzufuegen | +8 |
| `src/web/pages/subscriptions.py` | 6 Buttons auf Factory Pattern | ~60 |
| `src/web/pages/locations.py` | 3 Buttons auf Factory Pattern | ~25 |
| `src/web/pages/trips.py` | 4-5 Buttons auf Factory Pattern | ~30 |
| **Gesamt** | | **~123 LoC** |

## Status: Bug 1 + Bug 2 implementiert, Problem besteht weiter

Bug 1 (no-cache Middleware) und Bug 2 (Factory Pattern auf allen Seiten) sind
implementiert, aber der User muss **immer noch Cache leeren + Reload** in Safari.

**Root Cause:** Safari's **Back-Forward Cache (bfcache)** ignoriert HTTP `no-cache`
Headers komplett. Beim Zurueck-Navigieren oder Tab-Wechsel restauriert Safari die
gesamte Seite aus dem Speicher – inklusive totem WebSocket. Die Seite sieht normal
aus, aber kein Button-Event erreicht den Server.

## Bug 3: BFCache Auto-Reload (Stufe 3)

### Loesung

JavaScript `pageshow` Event erkennt, wenn Safari die Seite aus dem bfcache laedt
(`event.persisted === true`), und erzwingt einen echten Reload:

```javascript
window.addEventListener('pageshow', function(event) {
    if (event.persisted) {
        window.location.reload();
    }
});
```

Zusaetzlich: `Vary: *` Header verhindert bfcache bei manchen Safari-Versionen.

### Implementation

In `src/web/main.py`:

```python
# Inject BFCache detection script into every page
app.add_static_head_html('''<script>
window.addEventListener('pageshow', function(e) {
    if (e.persisted) { window.location.reload(); }
});
</script>''')
```

Middleware-Erweiterung:
```python
response.headers["Vary"] = "*"
```

### Warum das funktioniert

- `pageshow` Event feuert bei **jedem** Seitenaufruf (normal + bfcache)
- `event.persisted === true` NUR wenn die Seite aus dem bfcache kam
- `window.location.reload()` erzwingt frische HTTP-Anfrage + neuen WebSocket
- User sieht kurzen Reload-Flash, aber alles funktioniert sofort

### Dateien

| Datei | Aenderung | LoC |
|-------|-----------|-----|
| `src/web/main.py` | `add_static_head_html` + `Vary` Header | +6 |

## Known Limitations

- Factory Pattern ist ein Workaround fuer NiceGUI + Safari, nicht ein genereller Fix.
- E2E-Tests mit Playwright nutzen Chromium, nicht Safari - der bfcache-Bug
  ist nur in echtem Safari reproduzierbar.
- Der `pageshow` Reload verursacht einen kurzen Flash beim Zurueck-Navigieren.

## Supersedes

Diese Spec ersetzt `safari_subscriptions_fix.md` (draft, nie implementiert) und
erweitert den Scope auf alle drei betroffenen Dateien plus den WebSocket-Fix.

## Changelog

- 2026-02-12: v1.1 Bug 3 (bfcache auto-reload) als Stufe 3 hinzugefuegt
- 2026-02-11: v1.0 Initial spec (Bug 1 + Bug 2)
