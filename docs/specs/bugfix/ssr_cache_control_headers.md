---
entity_id: ssr_cache_control_headers
type: bugfix
created: 2026-05-04
updated: 2026-05-04
status: draft
version: "1.0"
tags: [frontend, sveltekit, http-headers, safari, issue-125]
---

# Bug #125 — Fehlender Cache-Control-Header auf SSR-HTML-Responses

## Approval

- [ ] Approved

## Purpose

SvelteKit setzt auf SSR-HTML-Responses keinen `Cache-Control`-Header, weshalb Safari heuristisches Caching aktiviert. Nach einem Frontend-Deploy liefert Safari gecachtes HTML mit veralteten Build-Hash-Referenzen aus; die neu deployten Asset-Chunks stimmen nicht überein, Hydration schlägt still fehl, und Click-Handler (z. B. „Neuer Trip" auf `/trips`) reagieren nicht. Der Fix ergänzt `hooks.server.ts` um einen Content-Type-gefilterten `cache-control: no-cache`-Header, der ausschließlich auf HTML-Responses gesetzt wird; Asset-Chunks und API-JSON-Responses bleiben unberührt.

## Source

- **File:** `frontend/src/hooks.server.ts`
- **Identifier:** `handle` (`export const handle: Handle`)

## Root Cause

Nginx (`gregor20.henemm.com.conf`) leitet Responses ohne eigene Cache-Header durch. SvelteKit setzt für SSR-HTML ebenfalls keinen `Cache-Control`-Header. Ohne expliziten Wert schätzt Safari anhand der `Last-Modified`- oder `ETag`-Werte eine eigene Cache-Dauer ab (RFC 7234 § 4.2.2). Chrome und Firefox sind konservativer; Playwright (Chromium + WebKit headless) nutzt keinen persistenten Disk-Cache und reproduziert den Bug deshalb nicht.

```
$ curl -D - https://gregor20.henemm.com/trips
Content-Type: text/html
etag: "..."
X-Content-Type-Options: nosniff
# kein Cache-Control → Safari nutzt heuristisches Caching
```

## Dependencies

| Entity | Typ | Zweck |
|---|---|---|
| `@sveltejs/kit` | Library | `Handle`-Typ, `RequestEvent`, `resolve` |
| `frontend/src/hooks.server.ts` | Zu ändern | Einziger serverseitiger Request-/Response-Hook |
| `frontend/src/routes/api/[...path]/+server.ts` | Read-only | API-Proxy; setzt eigene Headers — darf nicht überschrieben werden |

## Implementation Details

### BEFORE

```ts
import { redirect, type Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { verifySession } from '$lib/auth.js';

export const handle: Handle = async ({ event, resolve }) => {
    const publicPaths = ['/login', '/register', '/logout', '/forgot-password', '/reset-password'];
    if (publicPaths.includes(event.url.pathname)) {
        return resolve(event);
    }

    const secret = env.GZ_SESSION_SECRET ?? 'dev-secret-change-me';
    const session = event.cookies.get('gz_session');
    const result = session ? verifySession(session, secret) : null;

    if (!result) {
        redirect(302, '/login');
    }

    event.locals.userId = result.userId;
    return resolve(event);
};
```

### AFTER

```ts
import { redirect, type Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { verifySession } from '$lib/auth.js';

export const handle: Handle = async ({ event, resolve }) => {
    const publicPaths = ['/login', '/register', '/logout', '/forgot-password', '/reset-password'];
    if (publicPaths.includes(event.url.pathname)) {
        const response = await resolve(event);
        const ct = response.headers.get('content-type') ?? '';
        if (ct.includes('text/html')) {
            response.headers.set('cache-control', 'no-cache');
        }
        return response;
    }

    const secret = env.GZ_SESSION_SECRET ?? 'dev-secret-change-me';
    const session = event.cookies.get('gz_session');
    const result = session ? verifySession(session, secret) : null;

    if (!result) {
        redirect(302, '/login');
    }

    event.locals.userId = result.userId;
    const response = await resolve(event);
    const ct = response.headers.get('content-type') ?? '';
    if (ct.includes('text/html')) {
        response.headers.set('cache-control', 'no-cache');
    }
    return response;
};
```

**Implementierungsschritte:**

1. In `handle` alle `return resolve(event)`-Stellen auf `const response = await resolve(event)` umstellen.
2. Nach jedem `resolve`-Aufruf: Content-Type-Filter auf `text/html`; falls wahr, `response.headers.set('cache-control', 'no-cache')` setzen.
3. `response` zurückgeben statt direktem `resolve`-Ergebnis.
4. Keine Änderungen an `redirect(302, '/login')` — diese Responses sind ohnehin kurzlebig und nicht HTML-Body-Responses.

**Filterregel:** `response.headers.get('content-type')?.includes('text/html')` — trifft genau auf SvelteKit-SSR-Pages, nicht auf API-JSON, nicht auf Asset-Chunks (letztere werden vom statischen File-Server ausgeliefert, nie durch `handle` geroutet).

## Expected Behavior

| Case | URL-Muster | Content-Type Response | Erwarteter `cache-control`-Header |
|---|---|---|---|
| HTML-Response (SSR-Page) | `/`, `/trips`, `/login`, … | `text/html` | `no-cache` (gesetzt durch Fix) |
| Asset-Chunk (statisch) | `/_app/immutable/…` | `application/javascript` / `text/css` | `public,max-age=31536000,immutable` (unverändert) |
| API-JSON-Response | `/api/…` | `application/json` | kein `no-cache` von `handle` gesetzt |

- **Input:** HTTP-Request an SvelteKit-Frontend
- **Output:** Response mit `cache-control: no-cache` auf HTML-Responses; alle anderen Responses unverändert
- **Side effects:** Safari cached SSR-HTML nicht mehr heuristisch; nach Frontend-Deploys keine stale-HTML-Auslieferung

## Test Plan

**Datei:** `tests/tdd/test_ssr_cache_headers.py`

Tests laufen gegen einen echten HTTP-Server (kein Mock) — entweder lokaler Build (`node build/index.js` auf Test-Port) oder Staging nach Auto-Deploy. Pattern orientiert sich an `tests/tdd/test_safari_cache_fix.py`.

```python
import httpx
import pytest

BASE_URL = "https://staging.gregor20.henemm.com"  # oder lokaler Test-Server

def test_html_response_has_no_cache_header():
    """SSR-HTML-Response muss cache-control: no-cache enthalten."""
    r = httpx.get(f"{BASE_URL}/trips", follow_redirects=True)
    ct = r.headers.get("content-type", "")
    assert "text/html" in ct
    assert "no-cache" in r.headers.get("cache-control", "")

def test_asset_chunk_keeps_immutable_header():
    """Asset-Chunks (/_app/immutable/…) dürfen keinen no-cache erhalten."""
    # Chunk-Pfad aus HTML extrahieren oder statisch aus bekanntem Build
    r = httpx.get(f"{BASE_URL}/_app/immutable/start.js", follow_redirects=True)
    cc = r.headers.get("cache-control", "")
    assert "immutable" in cc
    assert "no-cache" not in cc

def test_api_response_not_affected():
    """API-JSON-Responses erhalten keinen no-cache-Header vom Handle-Hook."""
    r = httpx.get(f"{BASE_URL}/api/health", follow_redirects=True)
    ct = r.headers.get("content-type", "")
    assert "application/json" in ct
    cc = r.headers.get("cache-control", "")
    assert "no-cache" not in cc
```

**Keine Mocks.** Alle drei Tests machen echte HTTP-Requests. TDD-RED: vor dem Fix schlägt `test_html_response_has_no_cache_header` fehl. TDD-GREEN: alle drei Tests grün nach dem Fix.

## Known Limitations

- **Nginx-Layer nicht adressiert:** `gregor20.henemm.com.conf` setzt keine Cache-Header analog zu `henemm.com.conf`. Defense-in-Depth wäre ein eigenes Follow-up-Issue — kein Bestandteil dieses Bugfix.
- **Keine Route-Differenzierung:** Alle HTML-Responses bekommen `no-cache`, unabhängig von der Route. Bewusste Entscheidung — vereinfacht die Logik und vermeidet Ausnahme-Pflege.
- **Service-Worker:** Existiert nicht (`/service-worker.js` gibt 302) — nicht relevant.
- **`ETag`-Caching:** `no-cache` bedeutet, Safari fragt den Server bei jedem Aufruf per Conditional GET (If-None-Match). Bei unverändertem HTML antwortet SvelteKit mit `304 Not Modified` — keine zusätzliche Serverlast durch vollständige HTML-Übertragung.

## Success Criteria

- [ ] `curl -D - https://gregor20.henemm.com/trips` enthält `cache-control: no-cache`
- [ ] `curl -D - https://gregor20.henemm.com/_app/immutable/<chunk>.js` enthält weiterhin `cache-control: public,max-age=31536000,immutable`
- [ ] `curl -D - https://gregor20.henemm.com/api/health` enthält kein `no-cache` von `handle`
- [ ] Real-User-Test Safari Mac: Frontend deployen → ohne Cache-Leeren `/trips` öffnen → „Neuer Trip"-Button reagiert

## Bezug

- GitHub Issue #125
- Analyse-Doku: `docs/context/bug-125-safari-html-cache.md`
- Referenz-Test-Pattern: `tests/tdd/test_safari_cache_fix.py`

## Changelog

- 2026-05-04: Initial spec erstellt (Bug #125, SSR-HTML ohne Cache-Control-Header)
