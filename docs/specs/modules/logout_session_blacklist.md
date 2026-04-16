---
entity_id: logout_session_blacklist
type: module
created: 2026-04-16
updated: 2026-04-16
status: draft
version: "1.0"
tags: [go, sveltekit, auth, logout, session, f15]
---

# F15 Phase 1 — Logout + Session-Blacklist

## Approval

- [ ] Approved

## Purpose

Logout-Endpoint der die Session serverseitig invalidiert und den Cookie loescht. Middleware prueft eine In-Memory-Blacklist damit ausgeloggte Sessions nicht weiterverwendet werden koennen. Logout-Button im SvelteKit Frontend.

## Scope

### In Scope

- `POST /api/auth/logout` — Session blacklisten + Cookie loeschen
- AuthMiddleware prueft Blacklist
- Logout-Button im SvelteKit Layout
- SvelteKit Action fuer Logout

### Out of Scope

- Persistente Blacklist (File-basiert) — In-Memory reicht, Sessions laufen nach 24h ab
- Multi-Device Session Management
- Session-Liste anzeigen

## Architecture

```
Logout-Button (SvelteKit)
    │ POST /logout (SvelteKit Action)
    ▼
SvelteKit Server
    ├── POST /api/auth/logout (an Go mit Cookie)
    └── Cookie loeschen (im Browser)

Go API:
POST /api/auth/logout
    ├── Session-Token aus Cookie lesen
    ├── Token zur In-Memory-Blacklist hinzufuegen
    └── 200 OK

AuthMiddleware (bei jedem Request):
    ├── Cookie validieren (HMAC) — wie bisher
    └── NEU: Pruefen ob Token in Blacklist → 401
```

## Source

- **File:** `internal/middleware/auth.go` **(ERWEITERT)** — Blacklist + Check
- **File:** `internal/handler/auth.go` **(ERWEITERT)** — LogoutHandler
- **File:** `cmd/server/main.go` **(ERWEITERT)** — Route
- **File:** `frontend/src/routes/+layout.svelte` **(ERWEITERT)** — Logout-Button
- **File:** `frontend/src/routes/logout/+page.server.ts` **(NEU)** — Logout Action

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/middleware/auth.go` | go package | Blacklist-Verwaltung und -Pruefung |
| `sync` | go stdlib | `sync.Map` fuer thread-safe Blacklist |

## Implementation Details

### Step 1: In-Memory Blacklist in Middleware (`internal/middleware/auth.go`, +20 LoC)

```go
var sessionBlacklist sync.Map // token → struct{}

func BlacklistSession(token string) {
    sessionBlacklist.Store(token, struct{}{})
}

func IsBlacklisted(token string) bool {
    _, ok := sessionBlacklist.Load(token)
    return ok
}
```

In `AuthMiddleware`, nach `validateSession`:
```go
if IsBlacklisted(cookie.Value) {
    http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
    return
}
```

`sync.Map` ist thread-safe, kein Mutex noetig. Blacklist wird beim Server-Restart geleert — akzeptabel, Sessions laufen sowieso nach 24h ab.

### Step 2: LogoutHandler (`internal/handler/auth.go`, +20 LoC)

```go
func LogoutHandler() http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        cookie, err := r.Cookie("gz_session")
        if err == nil && cookie.Value != "" {
            middleware.BlacklistSession(cookie.Value)
        }

        // Clear cookie
        http.SetCookie(w, &http.Cookie{
            Name:     "gz_session",
            Value:    "",
            Path:     "/",
            HttpOnly: true,
            MaxAge:   -1,
        })

        w.Header().Set("Content-Type", "application/json")
        w.Write([]byte(`{"status":"ok"}`))
    }
}
```

Kein Store noetig — Logout braucht nur den Cookie-Token. Auch ohne Auth-Context aufrufbar (falls Cookie abgelaufen aber noch vorhanden).

### Step 3: Route (`cmd/server/main.go`, +1 LoC)

```go
r.Post("/api/auth/logout", handler.LogoutHandler())
```

Exempt-Liste in Middleware NICHT erweitern — Logout soll auch mit abgelaufenem Cookie funktionieren. Stattdessen: Logout-Endpoint zur Exempt-Liste hinzufuegen.

### Step 4: SvelteKit Logout Action (`frontend/src/routes/logout/+page.server.ts`, NEU ~15 LoC)

```typescript
import { redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const actions = {
    default: async ({ cookies }) => {
        const session = cookies.get('gz_session');
        if (session) {
            await fetch(`${API()}/api/auth/logout`, {
                method: 'POST',
                headers: { Cookie: `gz_session=${session}` },
            });
        }
        cookies.delete('gz_session', { path: '/' });
        redirect(302, '/login');
    },
} satisfies Actions;
```

### Step 5: Logout-Button im Layout (`frontend/src/routes/+layout.svelte`, +5 LoC)

Unter dem userId-Display:
```svelte
<form method="POST" action="/logout">
    <button type="submit" class="text-xs text-muted-foreground hover:text-foreground">
        Logout
    </button>
</form>
```

## Expected Behavior

- **Logout-Button klicken:** Cookie wird geloescht, Session blacklisted, Redirect zu /login
- **Blacklisted Session wiederverwenden:** 401 Unauthorized
- **Server-Restart:** Blacklist wird geleert — akzeptabel (Sessions laufen nach 24h ab)

## Known Limitations

- In-Memory Blacklist geht bei Restart verloren
- Kein Limit auf Blacklist-Groesse (maximal 24h Sessions, selbstreinigend durch Expiry)

## Changelog

- 2026-04-16: Initial spec (F15 Phase 1 — Logout, GitHub Issue #53)
