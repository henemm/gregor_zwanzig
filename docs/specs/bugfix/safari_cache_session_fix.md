---
entity_id: safari_cache_session_fix
type: bugfix
created: 2026-02-12
updated: 2026-02-12
status: draft
version: "1.1"
tags: [ui, bugfix, safari, nicegui, websocket, cache, session]
related_specs:
  - safari_websocket_and_factory_fix
---

# Safari Cache + Session Fix

## Approval

- [ ] Approved

## Purpose

Fix Safari buttons becoming unresponsive after server restart until user manually clears
browser cache and reloads. Despite existing no-cache headers and BFCache auto-reload,
Safari serves stale cached HTML with invalid session IDs. Button clicks send stale element
IDs that the server silently ignores.

**Root Cause (Three-Fold):**

1. **Safari ignores HTTP no-cache headers** for HTML pages, serving cached version
2. **Invalid session element IDs** after restart - old element IDs no longer exist on server
3. **Dead WebSocket goes undetected** - reconnect_timeout=14400 causes ping_interval=11520s
   (3.2 hours), so NiceGUI's reconnect logic doesn't trigger promptly

**Existing Mitigations (Already Implemented):**
- HTTP no-cache middleware (lines 88-96, only for text/html)
- BFCache pageshow auto-reload (lines 99-106)
- Factory pattern (100% implemented across all pages)
- NiceGUI 3.4.1 with URL-versioned static assets (correctly cached)

**Three New Measures:**

**Measure 1:** Meta Cache-Control tags (Safari sometimes respects meta when it ignores headers)
**Measure 2:** Extend no-cache to non-versioned responses (WebSocket handshakes, dynamic JS)
**Measure 3:** WebSocket health check with auto-reload (detect dead session, force reload)

## Source

- **File:** `src/web/main.py`
- **Identifier:** Middleware + head HTML injection

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `nicegui.app` | Framework | Middleware hook + head HTML injection |
| `nicegui.ui` | Framework | `ui.add_head_html()` for client-side scripts |
| `starlette` | Framework | HTTP middleware |

## Implementation Details

### Measure 1: Meta Cache-Control Tags (~3 LoC)

Safari sometimes respects `<meta>` tags when HTTP headers are ignored.

```python
# In main.py, add after line 106 (after existing head HTML)
ui.add_head_html('''
<meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
''', shared=True)
```

### Measure 2: Extend No-Cache Middleware (~3 LoC change)

Change existing middleware (lines 88-96) to apply no-cache to ALL responses
EXCEPT NiceGUI's versioned static assets.

**Current (text/html only):**
```python
if "text/html" in response.headers.get("content-type", ""):
```

**New (all non-versioned responses):**
```python
# Skip NiceGUI's versioned static assets (these SHOULD be cached)
if not ("/_nicegui/" in str(request.url) and "/static/" in str(request.url)):
```

Covers: HTML pages, WebSocket handshakes, dynamic JS, API responses.
Excludes: `/_nicegui/3.4.1/static/...` (correctly cached for performance).

### Measure 3: Server Instance ID Check with Auto-Reload (~20 LoC)

Server generates a unique UUID on startup, exposed via `/_health` endpoint.
Client-side JavaScript polls this every 3 seconds. When the ID changes, the
server was restarted and the page auto-reloads.

**Server-side** (in main.py):
```python
import uuid
from starlette.responses import PlainTextResponse

SERVER_INSTANCE_ID = str(uuid.uuid4())

@app.get("/_health")
async def health_check():
    return PlainTextResponse(SERVER_INSTANCE_ID)
```

**Client-side** (injected via ui.add_head_html):
```javascript
(function() {
    var serverInstanceId = null;
    function checkInstance() {
        fetch("/_health", {cache: "no-store"})
            .then(function(r) { return r.text(); })
            .then(function(id) {
                if (serverInstanceId === null) {
                    serverInstanceId = id;
                } else if (id !== serverInstanceId) {
                    console.log("[safari-fix] Server restarted, reloading");
                    window.location.reload();
                }
            })
            .catch(function() {});
    }
    setInterval(checkInstance, 3000);
})();
```

**Why This Works:**
- Detects server restarts regardless of WebSocket state (socket may reconnect
  but session is stale - this approach catches that)
- Forces reload within 3 seconds of server restart (proactive, not reactive)
- Leaves reconnect_timeout=14400 unchanged (4h session for background tabs)
- Minimal overhead - one lightweight HTTP request every 3 seconds

## Expected Behavior

### Before (Bug)

- **Aktion:** User stops server, restarts it, clicks a button in Safari
- **Ergebnis:** Button appears clickable but nothing happens (server ignores stale element ID)
- **Workaround:** Clear cache + Hard Reload (Cmd+Shift+R)

### After (Fix)

- **Aktion:** User stops server, restarts it, opens Safari tab
- **Ergebnis:** Page auto-reloads within 5 seconds, all buttons work immediately
- **Nebeneffekt:** Brief reload flash, but no user intervention required

## Files to Modify

| Datei | Aenderung | LoC |
|-------|-----------|-----|
| `src/web/main.py` | Meta tags | +4 |
| `src/web/main.py` | Extend no-cache middleware | ~1 (line 91 change) |
| `src/web/main.py` | WebSocket health check script | +28 |
| **Gesamt** | | **~33 LoC** |

## Implementation Plan

1. **Measure 1 (Meta Tags):** Add after line 106 in `main.py`
2. **Measure 2 (Middleware):** Replace line 91 condition in `no_cache_headers()`
3. **Measure 3 (Health Check):** Add after Measure 1 script via `ui.add_head_html()`

**Order matters:** Meta tags → middleware → health check (layered defense).

## Testing Strategy

**Manual Test (Safari Required):**
1. Start server, open Safari, click button → works
2. Stop server, restart server, open same Safari tab
3. **Expected:** Page reloads within 5s, button works immediately
4. **Verify:** No cache clear or manual reload needed

**E2E Test (Playwright + Safari):**
Not practical - requires real Safari, not WebKit engine. Manual testing required.

## Known Limitations

- WebSocket health check adds ~28 LoC of client-side JavaScript (minimal payload)
- 5-second reload delay after server restart (acceptable trade-off)
- Measure 2 may prevent caching of non-versioned static assets if any exist
  (currently none - all statics are versioned via NiceGUI)
- E2E tests use Chromium, not Safari - manual testing required for verification

## Why Previous Fixes Were Insufficient

| Fix | Lines | Limitation |
|-----|-------|------------|
| HTTP no-cache headers | 88-96 | Safari ignores HTTP headers sometimes |
| BFCache auto-reload | 99-106 | Only fires on back button, not server restart |
| Factory pattern | All pages | Correct closures but doesn't fix dead WebSocket |

**This spec adds three new layers on top of existing fixes.**

## Relation to reconnect_timeout

`reconnect_timeout=14400` (4 hours) is intentional for background tabs.
Default ping_interval = reconnect_timeout * 0.8 = 11520s (3.2 hours).

**Problem:** Dead WebSocket isn't detected for 3.2 hours.
**Solution:** Client-side health check (5s interval) detects it immediately.
**No need to change reconnect_timeout** - keeps background tabs alive.

## Changelog

- 2026-02-12: v1.0 Initial spec (Measure 1 + 2 + 3)
- 2026-02-12: v1.1 Measure 3 revised: WebSocket disconnect-based → Server Instance ID polling (disconnect event unreliable when socket reconnects to stale session)
