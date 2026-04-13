---
entity_id: sveltekit_setup
type: module
created: 2026-04-13
updated: 2026-04-13
status: draft
version: "1.0"
tags: [migration, sveltekit, auth, frontend]
---

# M2: SvelteKit Frontend Setup + Auth

## Approval

- [ ] Approved

## Purpose

SvelteKit 5 Projekt aufsetzen als Ersatz fuer NiceGUI. Grundlagen-Infrastruktur: Projekt-Scaffold, UI-Library, TypeScript API Client, Cookie-basierte Auth und Layout Shell. Bildet das Fundament fuer alle spaeter portierten Frontend-Pages (M6).

## Scope

### In Scope (M2)

- SvelteKit 5 Scaffold mit TypeScript, Vite, adapter-node (Port 3000)
- shadcn-svelte (bits-ui) + Tailwind CSS Setup
- Hand-written TypeScript Types aus OpenAPI Spec
- Typed fetch API Client
- Cookie-basierte Session Auth (HMAC-SHA256, shared secret)
- SvelteKit Login-Page + hooks.server.ts Session-Validierung
- Go Auth-Middleware (Cookie-Validierung, userid-Extraktion)
- Layout Shell mit Sidebar-Navigation
- Dashboard-Stub (Health-Check Anzeige)

### Out of Scope

- Frontend Pages portieren (M6)
- Multi-User mit Datenbank (nach Cutover)
- CORS Middleware (nicht noetig: Vite-Proxy dev, Nginx prod)
- OAuth / Social Login
- Password Hashing / bcrypt (Single-User, Credentials aus ENV)

## Architecture

```
Browser
  |
  v
SvelteKit (:3000)                    Go API (:8090)
  |                                    |
  +-- /login                           +-- /api/* (auth middleware)
  |     POST: check ENV creds          |     validates gz_session cookie
  |     set gz_session cookie          |     extracts userId -> context
  |                                    |
  +-- hooks.server.ts                  +-- handlers (unchanged)
  |     validate gz_session            |     use userId from context
  |     redirect to /login             |
  |                                    |
  +-- /api proxy (dev: Vite)           |
  |     (prod: Nginx)                  |
  |                                    |
  +-- +layout.svelte                   |
        Sidebar: Dashboard, Trips,     |
        Locations, Settings            |
```

### Auth Flow

```
1. User oeffnet /          -> hooks.server.ts prueft Cookie
2. Kein Cookie             -> redirect /login
3. User gibt Creds ein     -> POST /login (SvelteKit form action)
4. SvelteKit prueft:       -> GZ_AUTH_USER + GZ_AUTH_PASS aus ENV
5. Match                   -> Cookie setzen: gz_session = {userId}.{ts}.{hmac}
6. Redirect /              -> hooks.server.ts validiert Cookie -> OK
7. Frontend fetcht /api/*  -> Go-Middleware validiert selben Cookie -> OK
```

### Cookie Format

```
gz_session = {userId}.{timestampSec}.{hmacHex}

hmac = HMAC-SHA256(GZ_SESSION_SECRET, "{userId}:{timestampSec}")

Beispiel: default.1744531200.a1b2c3d4e5f6...
```

Cookie-Attribute:
- `httpOnly: true` (kein JS-Zugriff)
- `sameSite: lax`
- `secure: true` (nur Produktion)
- `path: /`
- `maxAge: 86400` (24h)

## Source

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `frontend/package.json` | Dependencies: SvelteKit 5, adapter-node, shadcn-svelte, tailwind |
| `frontend/svelte.config.ts` | SvelteKit Config mit adapter-node |
| `frontend/vite.config.ts` | Vite Config mit /api Proxy auf :8090 |
| `frontend/tailwind.config.ts` | Tailwind + shadcn-svelte Preset |
| `frontend/src/app.css` | Tailwind Directives + shadcn Theme |
| `frontend/src/app.d.ts` | SvelteKit Type Augmentation (locals.userId) |
| `frontend/src/hooks.server.ts` | Session-Validierung, redirect /login |
| `frontend/src/lib/types.ts` | TS Interfaces aus OpenAPI (Location, Trip, etc.) |
| `frontend/src/lib/api.ts` | Typed fetch wrapper |
| `frontend/src/lib/auth.ts` | Cookie sign/verify Funktionen (shared) |
| `frontend/src/routes/login/+page.svelte` | Login-Formular |
| `frontend/src/routes/login/+page.server.ts` | Form Action: Credential-Check + Cookie |
| `frontend/src/routes/+layout.svelte` | Sidebar-Navigation |
| `frontend/src/routes/+layout.server.ts` | userId an Page Data |
| `frontend/src/routes/+page.svelte` | Dashboard-Stub (Health-Check) |
| `internal/middleware/auth.go` | Go Auth-Middleware (Cookie HMAC Validierung) |

### Geaenderte Dateien

| Datei | Aenderung |
|-------|-----------|
| `cmd/server/main.go` | Auth-Middleware einhaengen (+5 LOC) |
| `internal/config/config.go` | SessionSecret, AuthUser, AuthPass Felder (+4 LOC) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Go API (M1) | Service | REST Endpoints die das Frontend konsumiert |
| openapi.yaml | Spec | Source fuer TypeScript Types |
| Chi Router | Library | Middleware-Integration |
| shadcn-svelte | Library | UI Components (bits-ui based) |
| Tailwind CSS | Library | Utility-first CSS |

## Implementation Details

### Phase A: SvelteKit Scaffold (~80 LOC)

```bash
cd frontend
npm create svelte@latest . -- --template skeleton --types typescript
npm install -D @sveltejs/adapter-node tailwindcss @tailwindcss/vite
npx shadcn-svelte@next init
```

`vite.config.ts` — Dev Proxy:
```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8090',
      changeOrigin: true
    }
  }
}
```

### Phase B: TypeScript Types + API Client (~120 LOC)

`lib/types.ts` — Hand-written aus openapi.yaml:
```typescript
export interface Location {
  id: string;
  name: string;
  lat: number;
  lon: number;
  elevation_m?: number;
  region?: string;
  bergfex_slug?: string;
  activity_profile?: 'wintersport' | 'wandern' | 'allgemein';
  display_config?: Record<string, unknown>;
}

export interface Waypoint {
  id: string;
  name: string;
  lat: number;
  lon: number;
  elevation_m: number;
  time_window?: string;
}

export interface Stage {
  id: string;
  name: string;
  date: string;
  waypoints: Waypoint[];
  start_time?: string;
}

export interface Trip {
  id: string;
  name: string;
  stages: Stage[];
  avalanche_regions?: string[];
  aggregation?: Record<string, unknown>;
  weather_config?: Record<string, unknown>;
  display_config?: Record<string, unknown>;
  report_config?: Record<string, unknown>;
}

export interface HealthResponse {
  status: 'ok' | 'degraded';
  version: string;
  python_core: 'ok' | 'unavailable';
}

export interface ApiError {
  error: string;
  detail?: string;
}
```

`lib/api.ts` — Typed fetch:
```typescript
class ApiClient {
  constructor(private base = '') {}

  async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.base}${path}`);
    if (!res.ok) throw await res.json() as ApiError;
    return res.json();
  }

  async post<T>(path: string, body: unknown): Promise<T> { ... }
  async put<T>(path: string, body: unknown): Promise<T> { ... }
  async del(path: string): Promise<void> { ... }
}

export const api = new ApiClient();
```

### Phase C: Auth SvelteKit (~120 LOC)

`lib/auth.ts` — Cookie Signing:
```typescript
import { createHmac } from 'crypto';

export function signSession(userId: string, secret: string): string {
  const ts = Math.floor(Date.now() / 1000);
  const sig = createHmac('sha256', secret)
    .update(`${userId}:${ts}`)
    .digest('hex');
  return `${userId}.${ts}.${sig}`;
}

export function verifySession(cookie: string, secret: string, maxAge = 86400):
  { userId: string } | null {
  const [userId, tsStr, sig] = cookie.split('.');
  if (!userId || !tsStr || !sig) return null;
  const ts = parseInt(tsStr, 10);
  if (Date.now() / 1000 - ts > maxAge) return null;
  const expected = createHmac('sha256', secret)
    .update(`${userId}:${ts}`)
    .digest('hex');
  // Timing-safe vergleich nicht noetig bei HMAC, aber good practice
  if (sig !== expected) return null;
  return { userId };
}
```

`hooks.server.ts`:
```typescript
export const handle: Handle = async ({ event, resolve }) => {
  if (event.url.pathname === '/login') return resolve(event);

  const session = event.cookies.get('gz_session');
  const result = session ? verifySession(session, SECRET) : null;

  if (!result) return redirect(302, '/login');

  event.locals.userId = result.userId;
  return resolve(event);
};
```

### Phase D: Go Auth-Middleware (~95 LOC)

`internal/middleware/auth.go`:
```go
func AuthMiddleware(secret string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            // Health-Endpoint ohne Auth
            if r.URL.Path == "/api/health" {
                next.ServeHTTP(w, r)
                return
            }

            cookie, err := r.Cookie("gz_session")
            if err != nil {
                http.Error(w, `{"error":"unauthorized"}`, 401)
                return
            }

            userId, ok := validateSession(cookie.Value, secret)
            if !ok {
                http.Error(w, `{"error":"unauthorized"}`, 401)
                return
            }

            ctx := context.WithValue(r.Context(), userIDKey, userId)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}

func validateSession(value, secret string) (string, bool) {
    parts := strings.SplitN(value, ".", 3)
    if len(parts) != 3 { return "", false }

    userId, tsStr, sig := parts[0], parts[1], parts[2]
    ts, err := strconv.ParseInt(tsStr, 10, 64)
    if err != nil { return "", false }
    if time.Now().Unix()-ts > 86400 { return "", false }

    mac := hmac.New(sha256.New, []byte(secret))
    mac.Write([]byte(userId + ":" + tsStr))
    expected := hex.EncodeToString(mac.Sum(nil))

    if !hmac.Equal([]byte(sig), []byte(expected)) { return "", false }
    return userId, true
}
```

`internal/config/config.go` — Neue Felder:
```go
SessionSecret string `envconfig:"SESSION_SECRET" default:"dev-secret-change-me"`
AuthUser      string `envconfig:"AUTH_USER" default:"admin"`
AuthPass      string `envconfig:"AUTH_PASS" default:""`
```

### Phase E: Layout Shell (~150 LOC)

`+layout.svelte` — Sidebar mit shadcn-svelte Button:
```svelte
<script>
  import { page } from '$app/stores';
</script>

<div class="flex h-screen">
  <nav class="w-60 border-r bg-muted/40 p-4">
    <h1 class="text-lg font-bold mb-6">Gregor 20</h1>
    {#each [
      { href: '/', label: 'Dashboard', icon: 'home' },
      { href: '/trips', label: 'Trips', icon: 'map' },
      { href: '/locations', label: 'Locations', icon: 'map-pin' },
      { href: '/settings', label: 'Settings', icon: 'settings' },
    ] as item}
      <a href={item.href}
         class="block px-3 py-2 rounded-md text-sm"
         class:bg-accent={$page.url.pathname === item.href}>
        {item.label}
      </a>
    {/each}
  </nav>
  <main class="flex-1 p-6 overflow-auto">
    <slot />
  </main>
</div>
```

## Expected Behavior

- **Unauthenticated User:** Redirect zu /login bei jedem Route-Zugriff
- **Login:** Credentials gegen ENV pruefen, bei Erfolg Cookie setzen, redirect /
- **Authenticated User:** Sidebar-Navigation, Dashboard zeigt Health-Status
- **API Calls:** Gehen durch Vite-Proxy (dev) / Nginx (prod), Cookie wird mitgesendet
- **Go API:** Validiert Cookie, extrahiert userId, gibt 401 bei ungueltigem Cookie
- **Logout:** Cookie loeschen, redirect /login

## ENV Variablen

| Variable | Default | Beschreibung |
|----------|---------|-------------|
| `GZ_SESSION_SECRET` | `dev-secret-change-me` | HMAC Signing Key (min 32 Zeichen in Prod) |
| `GZ_AUTH_USER` | `admin` | Login Username |
| `GZ_AUTH_PASS` | (leer) | Login Password (MUSS in Prod gesetzt werden) |

## Known Limitations

- Single-User: Nur ein Credential-Paar aus ENV, kein User-Management
- Kein Password-Hashing (Credentials sind ENV-Variablen, nicht in DB)
- Session ist stateless (kein Revoke moeglich ausser Secret zu aendern)
- Cookie MaxAge 24h fest, nicht konfigurierbar
- Go-Middleware prueft nur ob userId aus Cookie == config.UserID (V1)

## Testbarkeit

### SvelteKit Tests (Playwright)
- Login-Flow: Falsches Passwort -> bleibt auf /login
- Login-Flow: Richtiges Passwort -> redirect / + Cookie gesetzt
- Geschuetzte Route ohne Cookie -> redirect /login
- Dashboard laedt und zeigt Health-Status

### Go Middleware Tests (Go test)
- Gueltiger Cookie -> 200 + userId im Context
- Kein Cookie -> 401
- Abgelaufener Cookie -> 401
- Manipulierter HMAC -> 401
- /api/health ohne Cookie -> 200 (exempt)

## Changelog

- 2026-04-13: Initial spec created
